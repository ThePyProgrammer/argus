# Architecture Patterns

**Domain:** Pluggable object detection + 3D bounding box regression extending an existing multi-robot 3D reconstruction system
**Researched:** 2026-04-13
**Confidence:** HIGH — derived from direct read of the v2.0 shipped codebase (`src/slam/protocol.py`, `src/slam/registry.py`, `src/slam/backends/subprocess_bridge.py`, `src/slam/backends/orbslam3_backend.py`, `src/coordination/coordinator.py`, `src/perception/detector.py`, `src/perception/detection_3d.py`, `backend/web/slam_routes.py`, `backend/web/server.py`, `backend/web/streaming_viz.py`, `frontend/src/stores/slamStore.ts`, `frontend/src/stores/pipelineStore.ts`, `frontend/src/utils/pipelineTypes.ts`, `frontend/src/utils/nodeDefinitions.ts`, `frontend/src/utils/pipelineValidation.ts`, `frontend/src/components/DetectionBoxes.ts`, `frontend/src/components/pipeline/PipelineNode.tsx`) and the v2.0 research archive (`.planning/milestones/v2.0-research/ARCHITECTURE.md`).

## Recommended Architecture

### Design Principle: Mirror the SLAM v2.0 Strategy-Registry Pattern with a Two-Stage Perception Pipeline

v3.0 introduces a clean split that the current `ObjectDetector` monolith conflates:

1. **Detection2D stage** — takes an RGB frame (optionally RGBD), returns 2D detections (class, score, bbox) plus backend-specific auxiliaries (mask, features, text logits).
2. **Detection3D stage** — takes 2D detections + depth + pose + optional `slam_cloud`, returns oriented 3D bounding boxes in world frame.

Both stages are independently pluggable through their own Protocol + Registry pair, modelled exactly on `SLAMProtocol` / `SLAMRegistry`. This gives three axes of variation instead of one:

```
DetectorRegistry (2D)  ×  Detection3DRegistry (3D lifter)  ×  [optional] TrackerRegistry (temporal)
```

A `YOLOv11 + MedianDepthLifter` pipe is behaviourally equivalent to v2.x today; a `BoxeR + PointCluster3DLifter` pipe produces real oriented 3D boxes; a `GroundingDINO + OmniBox3DLifter` pipe is open-vocabulary. No backend needs to own both stages.

### Current Data Flow (v2.0 — what is)

```
Coordinator._send_viz_update (every 10 sim steps)
  -> ObjectDetector.submit_frame(rid, rgb, depth, pose, slam_cloud=None)
     (stores in _pending_frames dict; background thread)
  -> ObjectDetector._detect (YOLO, single thread for ALL robots)
     -> median-depth projection inline inside _detect()
     -> writes to _results[rid]: list[Detection(bbox, center_3d, depth_m)]
  -> Coordinator reads detector.get_detections(rid), serializes to dict
  -> RobotVizData.detections (list[dict])
  -> streaming_viz emits WS message {"type":"detections", "robot_id":rid,
                                      "payload":{"detections":[{class, bbox, pos_3d, depth}]}}
  -> frontend DetectionBoxManager reconstructs AABB from (pos_3d, bbox, depth)
     using hardcoded 70° FOV and imgH=480 to back-compute worldW/worldH
```

Pain points this architecture must remove:
- `ObjectDetector` is a class, not a Protocol — no pluggability
- 2D→3D is hard-coded median-depth projection with duplicated math in Python (`detection_3d.py`) AND JS (`DetectionBoxes.ts`)
- Frontend re-derives bbox size from pixel bbox + depth — implicit coupling to camera intrinsics the frontend should not know about
- No per-robot backend selection, no parameter schema, no capability advertising, no crash isolation for heavy models
- Detection path is invisible to the pipeline editor (which already has typed ports and SLAM/merger nodes)

### Proposed Data Flow (v3.0)

```
MuJoCoBridge.step() -> SensorFrame(rgb, depth, sim_time, ground_truth_pose)
  -> Coordinator.run() inner loop (existing, once per sim step):
       For each robot rid:
         DetectorWorker[rid].submit(SensorFrame, cam_pose, slam_cloud?)
             (non-blocking; drops if queue full -- backpressure)
       
       DetectorWorker[rid]  -- one thread per robot, per Coordinator:
         detector_2d.process_frame(frame) -> Detections2D
         detection_3d.lift(detections_2d, frame, pose, slam_cloud)
             -> Detections3D (oriented boxes, class, score, track_id?)
         writes to latest_detections[rid] (lock-protected)
  -> Coordinator._send_viz_update (every 10 sim steps):
       reads latest_detections[rid]
       packs into RobotVizData.detections_3d (NEW field) + legacy detections (2D)
  -> WebStreamingViz emits:
       {"type":"detections_3d", "robot_id":rid, "payload": Detections3DPayload}
       (supersedes legacy "detections"; legacy kept during transition)
  -> Frontend DetectionBoxManager consumes oriented boxes directly
     (center, half_extents, quaternion -- no intrinsics recomputation)
```

Crash path (mirrors SLAM):
```
SubprocessDetectorBridge hangs (>5s) or subprocess dies
  -> DetectorWorker catches None return from bridge.send_frame()
  -> Falls back to registry default "yolo11n_median" for this robot
  -> Coordinator emits WS {"type":"crash_fallback", ..., "subsystem":"detector"}
  -> Frontend CrashToast surfaces "BoxeR crashed, falling back to YOLO11n"
```

## Component Boundaries

### New Components (Python)

| Component | File | Responsibility | Communicates With |
|-----------|------|----------------|-------------------|
| `Detections2D` | `src/perception/protocol.py` | Immutable dataclass: N detections × {class_id, class_name, score, bbox xyxy, mask?, features?, instance_id?} | Detector backends (produce), Detection3D backends (consume) |
| `OrientedBox3D` | `src/perception/protocol.py` | Immutable dataclass: center (3,), half_extents (3,), quaternion (4,), class_id, class_name, score, track_id?, source_2d_idx | Detection3D backends (produce), Coordinator, WS serialization |
| `Detections3D` | `src/perception/protocol.py` | Immutable wrapper: list[OrientedBox3D] + per-frame metrics (inference_ms, lifter_ms, n_raw, n_filtered) | viz, MetricsPanel |
| `DetectorInput` | `src/perception/protocol.py` | Enum-like capability: `RGB_ONLY`, `RGBD`, `RGB_STEREO`, `RGB_TEXT_PROMPT` | Registry (advertises on backends) |
| `DetectorProtocol` | `src/perception/protocol.py` | `@runtime_checkable Protocol` mirroring `SLAMProtocol`. Methods: `process_frame(SensorFrame, text_prompt: str \| None) -> Detections2D`, `reset()`, `get_metrics()`. Class attrs: `CAPABILITIES`, `PARAMETER_SCHEMA`, `INPUT_TYPE: DetectorInput`, `CLASS_NAMES: list[str] \| None`. | DetectorRegistry, DetectorWorker |
| `Detection3DProtocol` | `src/perception/protocol.py` | `@runtime_checkable Protocol`. Methods: `lift(Detections2D, SensorFrame, pose: (4,4), slam_cloud: (N,3) \| None, intrinsics) -> Detections3D`, `reset()`. Class attrs: `CAPABILITIES` (e.g. `requires_depth`, `requires_point_cloud`, `outputs_oriented`), `PARAMETER_SCHEMA`. | DetectorWorker |
| `DetectorRegistry` | `src/perception/registry.py` | Exact clone of `SLAMRegistry`: `_backends: dict[str, {class_path, display}]`, `register`, `list_backends`, `create`, `get_default`. Default = `"yolo11n"`. | FastAPI routes, main.py discovery |
| `Detection3DRegistry` | `src/perception/registry.py` | Same pattern, separate class. Default = `"median_depth"` (replicates current behaviour). | FastAPI routes |
| `@detector` decorator | `src/perception/registry.py` | `@detector(name="boxer", display="BoxeR", input=DetectorInput.RGB_ONLY)` — mirror of `@slam_backend`. | Backend modules |
| `@detection_3d` decorator | `src/perception/registry.py` | Same pattern for 3D lifters. | Backend modules |
| `YOLOv11Backend` | `src/perception/backends/yolov11_backend.py` | In-process wrapper of `ObjectDetector._detect()` logic, conforming to `DetectorProtocol`. Optional: `torch.no_grad()`. INPUT_TYPE = `RGB_ONLY`. | Registry |
| `BoxeRBackend` | `src/perception/backends/boxer_backend.py` | Composes `SubprocessDetectorBridge`, mirrors `OpenVINSBackend` pattern — out-of-process because transformer + torch weights risk crash / memory. INPUT_TYPE = `RGB_ONLY`. | SubprocessDetectorBridge |
| `GroundingDINOBackend` | `src/perception/backends/grounding_dino_backend.py` | Composes `SubprocessDetectorBridge`. INPUT_TYPE = `RGB_TEXT_PROMPT` — backend advertises that it expects a text prompt param. | SubprocessDetectorBridge |
| `SubprocessDetectorBridge` | `src/perception/subprocess_bridge.py` | **Separate file** (not `SLAM` bridge) but mirrors its structure exactly. Same ZMQ PAIR + msgpack + multipart protocol, same 5s `HANG_TIMEOUT_MS`, same crash detection + cleanup. Multipart: `[header, rgb_bytes, depth_bytes?, text_prompt_bytes?] -> [header, det_array_bytes]`. See "Subprocess Protocol" section. | BoxeR, GroundingDINO, any future heavy backend |
| `MedianDepthLifter` | `src/perception/lifters/median_depth.py` | Wraps current `project_detections_to_3d` logic; returns **AABB** `OrientedBox3D` (identity quaternion). Advertises `outputs_oriented=False`. | Detection3DRegistry |
| `PointClusterLifter` | `src/perception/lifters/point_cluster.py` | For each 2D bbox: carve depth pixels inside bbox → project to camera frame → transform to world → **PCA + RANSAC plane fit** → oriented box via PCA eigenvectors. Optional: use `slam_cloud` for better point support. Advertises `outputs_oriented=True`, `requires_depth=True`. | Detection3DRegistry |
| `OmniBox3DLifter` | `src/perception/lifters/omnibox3d.py` | Learned RGBD → 3D box regressor (discovered by FEATURES research). Subprocess-gated (heavy torch model). Advertises `outputs_oriented=True`, `requires_depth=True`, `uses_learned_model=True`. | SubprocessDetectorBridge |
| `DetectorWorker` | `src/perception/detector_worker.py` | **One per robot**. Owns a `DetectorProtocol` instance + `Detection3DProtocol` instance. Has a single-slot queue (`_pending`) and a thread that runs detect → lift. Writes to `_latest: Detections3D`. Implements `submit(frame, pose, slam_cloud)`, `get_latest()`, `apply_params(dict) -> dict`, `reset()`, `stop()`. | Coordinator |
| `DetectorWorkerPool` | `src/perception/detector_worker.py` | `{rid -> DetectorWorker}`. Constructed by Coordinator at startup / restart based on app.state pending backend names. Supports *different backend per robot* (stretch) but defaults to same backend for all robots. | Coordinator |
| `detector_routes.py` | `backend/web/detector_routes.py` | FastAPI router `/api/detectors/*` and `/api/detectors/lifter-*`. Exact clone of `slam_routes.py` shape. | server.py, SLAMRegistry patterns |

### New Components (Frontend)

| Component | File | Responsibility |
|-----------|------|----------------|
| `DetectorBackend` type + `detectorStore` | `frontend/src/stores/detectorStore.ts` | Mirror of `slamStore.ts`. State: `backends`, `activeBackend`, `activeDisplay`, `activeParameters`, `stagedParams`, `isRestarting`, `crashMessage`, plus **`lifters`, `activeLifter`** (the 3D stage is displayed alongside but is its own registry). `fetchDetectorState()` fetches `/api/detectors/backends` + `/api/detectors/active` + `/api/detectors/lifters` + `/api/detectors/active-lifter`. |
| `DetectorDropdown` | `frontend/src/components/DetectorDropdown.tsx` | Mirror of `AlgorithmDropdown`. Shows available detector backends; triggers `POST /api/detectors/select`. |
| `LifterDropdown` | `frontend/src/components/LifterDropdown.tsx` | Same pattern for 3D lifter. Hidden when the active detector advertises `outputs_3d_natively = True` (e.g. OmniBox3D). |
| `DetectorSection` | `frontend/src/components/DetectorSection.tsx` | Sidebar section bundling DetectorDropdown + LifterDropdown + ParameterPanel rewired to `detectorStore`. |
| `DetectionMetricsCard` | `frontend/src/components/DetectionMetricsCard.tsx` | Live detection FPS, #detections, mean confidence per robot. Added to `MetricsPanel`. |
| `DetectorNode`, `Detection3DNode`, `TrackerNode` definitions | `frontend/src/utils/nodeDefinitions.ts` | Three new `NodeDefinition` entries (see "Pipeline Editor Integration"). |

### Modified Components (Python)

| Component | File | What Changes | Why |
|-----------|------|-------------|-----|
| `src/perception/detector.py` | — | **Gut.** Keep only: the COCO `INDOOR_CLASSES` dict (moved to `yolov11_backend.py`). `ObjectDetector` class is replaced by `DetectorWorker` + `YOLOv11Backend`. The existing inline 2D→3D math moves into `MedianDepthLifter`. | Backwards-compat path: file becomes a shim that re-exports `Detection` (now `OrientedBox3D`) for one release cycle, then deletes. |
| `src/perception/detection_3d.py` | — | Becomes `src/perception/lifters/median_depth.py`. The `project_detections_to_3d` function is repackaged as `MedianDepthLifter.lift()`. | Same logic, correct location. |
| `Coordinator.__init__` | `src/coordination/coordinator.py` | Replace the `self._detector = ObjectDetector(...)` block (lines 139-148) with `self._worker_pool = DetectorWorkerPool.create_from_app_state(robots.keys(), app_state)`. | Per-robot isolation + registry-driven construction. |
| `Coordinator._send_viz_update` | `src/coordination/coordinator.py` | Replace the `self._detector.submit_frame(...)` call (line 637-641) with `self._worker_pool.submit(rid, frame, pose, slam_cloud=cloud_pts if self._worker_pool.needs_slam_cloud(rid) else None)`. Replace the detections dict-building (line 646-654) with `self._worker_pool.get_latest(rid).to_payload()`. | Worker pool replaces inline threading. |
| `Coordinator.reset_for_restart` | `src/coordination/coordinator.py` | Tear down old `DetectorWorkerPool`, construct a new one from `app.state.pending_detector_backend` + `pending_lifter` + `pending_detector_params`. | Mirrors how SLAM backend swap already works on restart. |
| `RobotVizData` | `src/coordination/coordinator.py` | Add `detections_3d: Detections3D \| None` (keeps legacy `detections: list[dict]` for one release). | Typed payload. |
| `streaming_viz.py` | `backend/web/streaming_viz.py` | New message emitter in `_update_robots`: if `data.get("detections_3d")`, emit `{"type":"detections_3d", "robot_id":rid, "payload": {...serialized OrientedBox3D list..., "metrics": {...}}}`. Keep existing "detections" emitter gated on a compat flag for one release. | New wire format for oriented boxes + per-frame metrics. |
| `message_types.py` | `backend/web/message_types.py` | Add `DETECTIONS_3D = "detections_3d"` constant. | Consistency with existing constants. |
| `server.py` | `backend/web/server.py` | Add `app.state.active_detector_backend = "yolo11n"`, `pending_detector_backend`, `pending_detector_params`, `active_lifter`, `pending_lifter`. Include `detector_routes` router. Add `detector_param_update` WS dispatch mirroring `slam_param_update` (lines 124-151). | State scaffolding + router. |
| `main.py` (startup) | `src/main.py` | After `import src.slam.backends.*`, add `import src.perception.backends.yolov11_backend` (always), then `try-importlib` dance for `boxer_backend`, `grounding_dino_backend`, `omnibox3d_lifter`. Same graceful-degradation pattern the SLAM layer uses. | Registry self-registration. |
| `useWebSocket.ts` | `frontend/src/hooks/useWebSocket.ts` | Add case for `detections_3d` → route to `robotStore.updateDetections3D(rid, payload)`. Handle `detector_param_ack`, `detector_restart_complete`. Handle `crash_fallback` with `subsystem:"detector"` → `detectorStore.setCrashMessage`. | Mirror of SLAM WS handling. |
| `robotStore.ts` | `frontend/src/stores/robotStore.ts` | Add `detections3D: OrientedBox3D[]` per robot + `updateDetections3D` action. | New payload. |
| `metricsStore.ts` | `frontend/src/stores/metricsStore.ts` | Add `detectionMetrics: {fps, count, meanConf}` per robot. | Metrics surface. |
| `SceneViewer.tsx` + `DetectionBoxManager` | `frontend/src/components/DetectionBoxes.ts` + `SceneViewer.tsx` | `updateDetections` signature changes to accept `OrientedBox3D[]`: render wireframe + fill from `(center, half_extents, quaternion)` with `THREE.Quaternion` rotation. **Remove** FOV + pixel-bbox-to-world size derivation. | Real oriented boxes, no hidden intrinsic coupling. |
| `Sidebar.tsx` | `frontend/src/components/Sidebar.tsx` | Add `<DetectorSection />`. | Picker surface. |
| `MetricsPanel.tsx` | `frontend/src/components/MetricsPanel.tsx` | Add `<DetectionMetricsCard />` per robot. | Live FPS/#det/conf display. |
| `nodeDefinitions.ts` | `frontend/src/utils/nodeDefinitions.ts` | Add `detector_generic`, `detection_3d_generic`, `tracker_generic`; add `'perception'` to `NodeCategory`; add `'Detections2D'`, `'Detections3D'` to `PortDataType`. | Pipeline editor support. |
| `pipelineTypes.ts` | `frontend/src/utils/pipelineTypes.ts` | Extend `PortDataType` union with `'Detections2D' \| 'Detections3D'`; extend `NodeCategory` union with `'perception'`. | Type system. |
| `PipelineNode.tsx` | `frontend/src/components/pipeline/PipelineNode.tsx` | Add `perception: '\u{1F441}'` (eye) to `CATEGORY_ICONS`. | Visual. |
| `PORT_COLORS`, `PORT_SHAPES`, `CATEGORY_COLORS` | `frontend/src/utils/nodeDefinitions.ts` | Add colors for Detections2D (pink), Detections3D (magenta), and `perception` category header (purple-ish, distinct from filter). | Visual. |

### Unchanged Components

| Component | Why Unchanged |
|-----------|--------------|
| `SLAMProtocol` / `SLAMRegistry` / all SLAM backends | Orthogonal subsystem. Perception consumes their `SLAMResult.points` via `slam_cloud`, nothing flows back. |
| `SubprocessSLAMBridge` | Kept as-is; `SubprocessDetectorBridge` is a *separate class* that follows the same shape. Sharing the bridge would couple two subsystems sharing one ZMQ endpoint — bad blast radius. |
| `MuJoCoBridge` / `MultiRobotBridge` / `SensorFrame` | SLAM-agnostic and detector-agnostic. |
| `OctoMapBuilder`, `VoronoiPartitioner`, `PoseGraphMerger`, `MergeRegistry` | Do not consume detections. |
| `pLCMTransport`, `RobotInstance.publisher`, `RobotMapMessage` | Detection is not currently published via pLCM (direct call from Coordinator). v3.0 keeps this. |
| `pipeline_routes.py` | Stays; receives additional node types but keeps its structure. |
| `CameraIntrinsics` | Used by lifters — but its shape is stable. |

## DetectorProtocol Definition (Answer to Q1)

```python
# src/perception/protocol.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable
import numpy as np

from src.bridge.sensor_types import SensorFrame


class DetectorInput(Enum):
    RGB_ONLY = "rgb_only"
    RGBD = "rgbd"
    RGB_STEREO = "rgb_stereo"
    RGB_TEXT_PROMPT = "rgb_text_prompt"  # open-vocabulary (GroundingDINO)


@dataclass(frozen=True)
class Detection2D:
    class_id: int
    class_name: str
    score: float
    bbox_xyxy: tuple[float, float, float, float]
    mask: np.ndarray | None = None           # (H, W) uint8, optional
    features: np.ndarray | None = None       # backend-specific embedding, optional
    instance_id: int | None = None           # set by tracker, not detector


@dataclass(frozen=True)
class Detections2D:
    items: list[Detection2D]
    inference_ms: float
    image_hw: tuple[int, int]                # so lifters know coord space


@dataclass(frozen=True)
class OrientedBox3D:
    class_id: int
    class_name: str
    score: float
    center: np.ndarray          # (3,) world frame
    half_extents: np.ndarray    # (3,)  -- half-widths along local axes
    quaternion: np.ndarray      # (4,)  xyzw, identity = axis-aligned
    track_id: int | None = None
    source_2d_idx: int | None = None   # index into originating Detections2D
    # For debug / pipeline inspection:
    probabilities: dict[str, float] | None = None  # top-k class distribution


@dataclass(frozen=True)
class Detections3D:
    items: list[OrientedBox3D]
    lifter_ms: float
    detector_ms: float          # forwarded from Detections2D.inference_ms
    n_raw: int                  # pre-filter
    n_final: int                # post-filter
    image_hw: tuple[int, int]


@runtime_checkable
class DetectorProtocol(Protocol):
    """Produces 2D detections from a SensorFrame. Mirrors SLAMProtocol."""

    CAPABILITIES: dict         # {"supports_masks": bool, "supports_features": bool,
                               #  "open_vocabulary": bool, "runs_in_process": bool}
    PARAMETER_SCHEMA: dict     # JSON-schema-ish; identical shape to SLAM
    INPUT_TYPE: DetectorInput
    CLASS_NAMES: list[str] | None   # None = open-vocab

    def process_frame(
        self,
        frame: SensorFrame,
        text_prompt: str | None = None,
    ) -> Detections2D: ...

    def reset(self) -> None: ...

    def get_params(self) -> dict: ...

    def apply_params(self, params: dict) -> dict:
        """Returns per-key {status: "applied"|"requires_restart"|"unknown_parameter"}."""
        ...

    def get_metrics(self) -> dict:
        """Rolling averages over last N frames."""
        ...


@runtime_checkable
class Detection3DProtocol(Protocol):
    """Lifts 2D detections to oriented 3D boxes."""

    CAPABILITIES: dict         # {"requires_depth": bool, "requires_point_cloud": bool,
                               #  "outputs_oriented": bool, "uses_learned_model": bool}
    PARAMETER_SCHEMA: dict

    def lift(
        self,
        detections: Detections2D,
        frame: SensorFrame,
        pose_cam_to_world: np.ndarray,
        slam_cloud: np.ndarray | None,
    ) -> Detections3D: ...

    def reset(self) -> None: ...
    def get_params(self) -> dict: ...
    def apply_params(self, params: dict) -> dict: ...
```

**Design rationale:**

1. **Two protocols, not one.** A unified `DetectorProtocol` that returns 3D boxes would force every 2D model (YOLO, BoxeR, GDINO) to embed 2D→3D logic. Splitting matches the scientific reality: 2D detection and 3D lifting are orthogonal research areas.
2. **`process_frame` mirrors `SLAMProtocol.process_frame`** — same verb, same `SensorFrame` input. Drastically lowers cognitive cost for the v2.0 team.
3. **No `submit_frame` in the protocol.** Queuing / threading is a concern of `DetectorWorker`, not the backend. Backends are stateful *inference engines*, not frame dispatchers. (This deliberately differs from today's `ObjectDetector.submit_frame` which conflates the two.)
4. **`apply_params` returns per-key status.** Matches the `slam_param_ack` pattern — some params are live-tunable (confidence threshold), others need restart (model weights).
5. **`probabilities` optional on `OrientedBox3D`.** BoxeR / GDINO give richer distributions than YOLO's top-1. Frontend can ignore or surface.
6. **`text_prompt` is a method arg, not a constructor arg.** Lets an open-vocab backend change vocabulary between frames without reinit.
7. **`runtime_checkable` Protocol, not ABC.** Matches `SLAMProtocol` exactly — enables duck-typed backends and per-method `isinstance` checks.

## DetectorRegistry Design (Answer to Q2)

**Byte-for-byte clone of `SLAMRegistry`**, distinct class with its own `_backends` dict. Two separate registries (`DetectorRegistry` and `Detection3DRegistry`) live in the same file `src/perception/registry.py`, each with its own decorator. `class_path` strings for lazy import, `available: bool` + `reason: str` in list output, `_load_class` with try/except ImportError — all identical.

```python
# src/perception/registry.py

from src.perception.protocol import DetectorInput

class DetectorRegistry:
    _backends: dict[str, dict] = {}
    _default: str = "yolo11n"

    @classmethod
    def register(
        cls,
        name: str,
        display: str,
        class_path: str,
        input_type: DetectorInput,
        install_hint: str | None = None,
    ) -> None:
        cls._backends[name] = {
            "class_path": class_path,
            "display": display,
            "input_type": input_type.value,
            "install_hint": install_hint,
        }

    # list_backends / create / get_default / _load_class: byte-identical to SLAMRegistry

def detector(
    name: str,
    display: str,
    input: DetectorInput,
    install_hint: str | None = None,
):
    def decorator(klass):
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        DetectorRegistry.register(name, display, class_path, input, install_hint)
        return klass
    return decorator


class Detection3DRegistry:
    _backends: dict[str, dict] = {}
    _default: str = "median_depth"
    # same shape as above

def detection_3d(name, display, install_hint=None):
    ...
```

**`install_hint`** mirrors the SLAM pattern's `INSTALL_HINT` but is stored on the *registry entry*, not the class — so unavailable backends (for which the class never loaded) still surface their install hint in `list_backends()`:

```python
@detector(
    name="boxer",
    display="BoxeR (transformer)",
    input=DetectorInput.RGB_ONLY,
    install_hint="pip install transformers torch && hf download facebook/BoxeR",
)
class BoxeRBackend: ...
```

`list_backends()` returns:
```json
{"name":"boxer","display":"BoxeR (transformer)","available":true,
 "capabilities":{...}, "parameter_schema":{...}, "input_type":"rgb_only"}
```
or when unavailable:
```json
{"name":"boxer","available":false,
 "reason":"Cannot load src.perception.backends.boxer_backend.BoxeRBackend",
 "install_hint":"pip install transformers torch && hf download facebook/BoxeR",
 "input_type":"rgb_only"}
```

**Input requirement declaration:** Done three ways, each with a different role:
- `input_type` at **register time** (registry metadata) — for UI filtering ("which backends can run on a monocular camera?")
- `INPUT_TYPE` **class attribute** — programmatic check inside worker pool; redundant with registry but lets backends assert it at instantiation
- `CAPABILITIES` dict — fine-grained optional flags (`supports_masks`, `open_vocabulary`) that don't fit the enum

## Heavy-Backend Execution Model (Answer to Q3)

**Decision: reuse the subprocess-bridge *concept* as `SubprocessDetectorBridge`, a separate class with the same structural contract.**

Do NOT reuse the SLAM bridge instance. Two subsystems sharing one ZMQ endpoint would couple their failure domains: a SLAM hang would look like a detector hang, the 5s timeout would fire on the wrong subsystem, msgpack headers would need a discriminator field. Keep them sibling classes.

### Why subprocess for transformers (BoxeR, GroundingDINO, OmniBox3D)

1. **Crash isolation.** A torch OOM or CUDA stack trace inside BoxeR kills the subprocess, not the FastAPI event loop, not the sim. The existing `SubprocessSLAMBridge` crash detection (process `poll()`) + WS `crash_fallback` path is already proven — we mirror it.
2. **Memory isolation.** torch + transformers keeps ~1–4 GB resident. Running in-process means every `reset_for_restart()` re-allocates that in the main process. Subprocess = reset = re-exec, clean slate.
3. **Python version / dep conflicts.** Future backends may pin torch versions incompatible with Open3D's. Subprocess decouples.
4. **CPU throttling.** The sim loop spins at ~200 FPS. A 150ms BoxeR forward pass cannot block it. Subprocess + PAIR socket with `zmq.DONTWAIT` on send side + backpressure drop on worker queue is the clean solution.

### In-process alternative (YOLOv11)

Lightweight models (YOLOv11n ~6 MB weights, ~30ms CPU) stay in-process under `torch.no_grad()` + `torch.set_num_threads(2)` (already how it works). The `DetectorWorker` thread model (below) handles it.

### Subprocess Protocol

Same shape as `SubprocessSLAMBridge.send_frame`:

```
Python side:
  header = msgpack.packb({
    "ts": frame.sim_time,
    "rgb_shape": [H, W, 3], "rgb_dtype": "uint8",
    "depth_shape": [H, W] | null, "depth_dtype": "float32" | null,
    "text_prompt": "chair. person. backpack." | "",   # for GDINO-style
    "params": {conf_thresh: 0.3, ...},                 # live-tunable params
  })
  send_multipart([header, rgb.tobytes(), depth.tobytes_or_empty(), prompt_bytes])

C++/Python child side:
  reply_header = msgpack.packb({
    "ts": ..., "inference_ms": ...,
    "n_det": N,
    "classes": [N] int,
    "scores":  [N] float32,
    "bboxes":  [N,4] float32 (xyxy),
    "class_names": ["chair", ...],  // for open-vocab
  })
  reply_parts = [reply_header, det_arrays_bytes, optional_masks_bytes]
```

Same 5s `HANG_TIMEOUT_MS`, same `zmq.Again` -> `_kill_process` -> fallback flow. The only protocol difference from SLAM: reply contains detections, not a pose.

### Threading Model (Answer to Q7)

**One `DetectorWorker` thread per robot**, not one shared thread. This differs from the current v2.x `ObjectDetector._run_loop` which is a single shared thread draining `_pending_frames` for ALL robots. Per-robot threads are necessary for v3.0 because:

1. A slow backend on robot A must not block detections on robot B.
2. Different robots can use different backends (stretch; see below).
3. Backpressure should be per-robot queue (drop A's stale frame without dropping B's).

```python
class DetectorWorker:
    def __init__(self, rid, detector_2d, lifter_3d, cam_intrinsics):
        self._rid = rid
        self._detector = detector_2d
        self._lifter = lifter_3d
        self._intrinsics = cam_intrinsics
        self._pending: tuple | None = None  # single-slot queue = backpressure
        self._latest: Detections3D | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def submit(self, frame, pose, slam_cloud):
        # Drops older pending frame -- newest wins. Backpressure.
        with self._lock:
            self._pending = (frame, pose, slam_cloud)

    def _loop(self):
        while not self._stop.is_set():
            with self._lock:
                job, self._pending = self._pending, None
            if job is None:
                time.sleep(0.01)
                continue
            frame, pose, cloud = job
            t0 = time.perf_counter()
            dets_2d = self._detector.process_frame(frame)
            t1 = time.perf_counter()
            dets_3d = self._lifter.lift(dets_2d, frame, pose, cloud)
            t2 = time.perf_counter()
            # fold measured times into dets_3d.metrics
            with self._lock:
                self._latest = dets_3d
```

**Backpressure discipline:** The Coordinator's sim loop runs at ~200 FPS. `_send_viz_update` runs every 10 sim steps, so submissions happen at ~20 Hz. A BoxeR backend at 5 FPS will see 4 out of 5 submissions dropped — this is correct. The frontend always sees the *latest* detection, no queue buildup, no "ghost" boxes from stale frames.

**Per-robot backends (stretch):** The pool reads `app.state.pending_detector_backend_per_robot: dict[rid, str]` with fallback to the global `pending_detector_backend`. MVP ships the global-only path.

## 2D→3D Lifting: Where It Lives (Answer to Q4)

**Decision: Separate pluggable `Detection3DProtocol` registry, not inside each detector.**

Reasons a separate stage wins:

1. **Orthogonality matrix.** Today's media-depth median lifter should work behind *any* 2D detector (YOLO, BoxeR, GDINO). If lifting lives inside a detector, we duplicate that logic N times. Separation gives us 1+M lifters and 1+N detectors composing into NxM pipelines for free.
2. **Research momentum is split.** 2D detection SOTA (DETR-family, open-vocab) evolves separately from 3D lifting SOTA (depth-anything + geometry, OmniBox3D, BEV methods). Coupling them means every detector backend must track 3D research.
3. **Pipeline editor clarity.** The editor already treats SLAM as a node and merger as a separate node; detection + lifting mirrors that.

**Lifter taxonomy** (for FEATURES.md to expand):

| Lifter | Method | Requires | Outputs oriented? | Latency |
|--------|--------|----------|-------------------|---------|
| `MedianDepthLifter` | median depth in bbox → unproject center, AABB size from bbox px × depth / focal | depth, intrinsics, pose | No | ~0.5 ms |
| `PointClusterLifter` | carve depth points in bbox → PCA for axes → bbox extents from percentile along axes | depth, intrinsics, pose | **Yes** | ~5 ms |
| `SlamCloudLifter` | find SLAM cloud points whose 2D projection lands in bbox → PCA | `slam_cloud`, pose, intrinsics | **Yes** | ~10 ms |
| `OmniBox3DLifter` | learned RGBD → oriented box network | depth, intrinsics, RGB, subprocess | **Yes** | ~50 ms |

**Edge case — detectors that output 3D natively.** Some future backends (e.g. CubeRCNN) produce 3D directly. Model this as:
- Detector has `CAPABILITIES["outputs_3d_natively"] = True`
- `DetectorWorker` checks this flag; if true, it calls a parallel `process_frame_3d()` method that returns `Detections3D` directly and bypasses the lifter
- The frontend `LifterDropdown` hides when `activeDetector.outputs_3d_natively`

This keeps the 2D+3D pipeline the default path while allowing end-to-end models without forcing the abstraction.

**SLAM cloud feeding.** The existing `ObjectDetector.submit_frame` already accepts `slam_cloud`. v3.0 keeps that plumbing: Coordinator passes `cloud_pts` from `robot.get_cloud_data()` when the lifter's `CAPABILITIES["requires_point_cloud"]` is true. `DetectorWorkerPool.needs_slam_cloud(rid)` is the query helper.

## FastAPI Routes + WebSocket Messages (Answer to Q5)

### New REST Routes

File: `backend/web/detector_routes.py` — exact clone of `slam_routes.py` with substituted names.

```
GET    /api/detectors/backends          -> {"backends": [...]}
POST   /api/detectors/select            body: {"backend": "boxer", "params": {...}?}
                                        triggers restart; stores pending on app.state
GET    /api/detectors/active            -> {"backend":..., "display":..., "parameters": {...}}
PATCH  /api/detectors/params            body: {"params": {...}}
                                        per-key: applied | requires_restart | unknown_parameter

GET    /api/detectors/lifters           -> {"lifters": [...]}
POST   /api/detectors/lifter-select     body: {"lifter": "point_cluster"}
GET    /api/detectors/active-lifter     -> {"lifter":..., "display":..., "parameters": {...}}
PATCH  /api/detectors/lifter-params     body: {"params": {...}}
```

### New WebSocket Message Types

Server → Client:
- `{"type":"detections_3d", "robot_id": rid, "payload": {
     items: [{class_id, class_name, score, center, half_extents, quaternion, track_id?, ...}],
     metrics: {detector_ms, lifter_ms, n_raw, n_final}, image_hw
  }}` — replaces legacy `"detections"`.
- `{"type":"detector_param_ack", "payload":{"param":..., "status":"applied"|"requires_restart"|"unknown_parameter", "value":...}}`
- `{"type":"detector_restart_complete", "payload":{"backend":..., "lifter":...}}`
- `{"type":"crash_fallback", "payload":{"subsystem":"detector", "from":"boxer", "to":"yolo11n", "reason":"subprocess timeout"}}` — extends existing crash_fallback with a `subsystem` discriminator.

Client → Server:
- `{"type":"detector_param_update", "param":..., "value":...}` — live-tunable params (conf threshold, NMS IoU).

All of the above structurally mirror the existing SLAM messages (`slam_param_update`, `slam_param_ack`, `slam_restart_complete`). The `crash_fallback` message already exists for SLAM — v3.0 promotes its schema to include a `subsystem` field so the frontend router can direct the toast.

### WS dispatch in `server.py`

Add one elif branch mirroring lines 124-151:
```python
elif msg_type == "detector_param_update":
    # identical shape to slam_param_update, but reads active_detector_backend
    ...
```

## Pipeline Editor Integration (Answer to Q6)

### New port data types

In `pipelineTypes.ts`, extend `PortDataType`:
```typescript
export type PortDataType =
  | 'Image' | 'PointCloud' | 'Pose' | 'IMU' | 'Scalar' | 'Boolean' | 'Config'
  | 'Detections2D' | 'Detections3D';
```

In `nodeDefinitions.ts`:
```typescript
export const PORT_COLORS: Record<PortDataType, string> = {
  ...
  Detections2D: '#ec407a',   // pink
  Detections3D: '#ab47bc',   // magenta
};
export const PORT_SHAPES: Record<PortDataType, string> = {
  ...
  Detections2D: 'hexagon',
  Detections3D: 'hexagon',
};
```

### New node category

Extend `NodeCategory`:
```typescript
export type NodeCategory =
  | 'sensor' | 'slam' | 'merger' | 'filter' | 'splitter'
  | 'parameter' | 'output' | 'perception';   // NEW
```

Header color (purple, distinct from filter's #7b1fa2): `perception: '#6a1b9a'`. Icon: `\u{1F441}` (eye).

### Three new node definitions

```typescript
detector_generic: {
  type: 'detector_generic',
  label: 'Object Detector',
  category: 'perception',
  inputs: [
    { id: 'image_in', label: 'RGB', dataType: 'Image', required: true },
    { id: 'text_in',  label: 'Prompt', dataType: 'Config', required: false },
  ],
  outputs: [
    { id: 'dets_2d_out', label: 'Detections2D', dataType: 'Detections2D', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,   // populated from DetectorRegistry at runtime
},

detection_3d_generic: {
  type: 'detection_3d_generic',
  label: '3D Box Lifter',
  category: 'perception',
  inputs: [
    { id: 'dets_in',  label: 'Detections2D', dataType: 'Detections2D', required: true },
    { id: 'depth_in', label: 'Depth', dataType: 'Image', required: false },
    { id: 'pose_in',  label: 'Pose', dataType: 'Pose', required: true },
    { id: 'cloud_in', label: 'PointCloud', dataType: 'PointCloud', required: false },
  ],
  outputs: [
    { id: 'dets_3d_out', label: 'Detections3D', dataType: 'Detections3D', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,   // populated from Detection3DRegistry at runtime
},

tracker_generic: {
  type: 'tracker_generic',
  label: 'Tracker',
  category: 'perception',
  inputs: [
    { id: 'dets_in',  label: 'Detections3D', dataType: 'Detections3D', required: true },
    { id: 'pose_in',  label: 'Pose', dataType: 'Pose', required: false },
  ],
  outputs: [
    { id: 'tracks_out', label: 'Tracked', dataType: 'Detections3D', required: false },
  ],
  defaultParams: {},
  parameterSchema: null,
},
```

`tracker_generic` is defined now even though tracker backends ship in a later phase — defining it early locks the port shape and means the pipeline registry returns a stable schema.

### Validation (Kahn's algorithm) — no changes needed

`validateGraph` in `pipelineValidation.ts` is data-type agnostic: it walks `nodes` and `edges` regardless of `PortDataType`. Adding `Detections2D`/`Detections3D` ports does NOT require touching the validator. Cycle detection + required-port detection + missing-output detection all keep working.

**What IS needed** — a per-edge type check: today's `onConnect` in `pipelineStore.ts` hardcodes `dataType: 'PointCloud' as const` (line 101). v3.0 upgrades it to read the source port's `dataType` and reject connections whose source/target types mismatch. This was always a pipeline editor bug; v3.0 fixes it cleanly. Add to `pipelineValidation.ts`:

```typescript
export function findTypeMismatches(nodes, edges): ValidationError[] {
  // edge type must match sourcePort.dataType AND targetPort.dataType
}
```

Call in `validateGraph`.

### New preset

Add a built-in `perception_rgbd` preset to the pipeline editor:
```
RGBDSensor -> Detector -> Detection3DLifter -> VizOutput
                   ^             ^
                   Pose-----------
                       (from SLAM)
```
This is the v3.0 shipped default pipeline, mirrors how `slam_icp_pipeline` is the v2.0 default.

### Registry-driven schema

The editor already supports `registryName` + `registrySchema` on node data (see `buildNodeData` in `nodeDefinitions.ts`). On node creation, the frontend fetches `/api/detectors/backends` and populates `parameterSchema` from the selected backend's `parameter_schema` — identical to how `slam_generic` pulls from `SLAMRegistry`.

### `pipeline_routes.py` extension

The existing pipeline apply route receives a `PipelineConfig` containing nodes with `type: "detector_generic"`. The backend side needs to map node `type` + `registryName` to a concrete `DetectorWorkerPool` configuration. Extend `pipeline_routes.py` to:
1. Recognize `detector_generic` / `detection_3d_generic` / `tracker_generic` node types.
2. Resolve `registryName` via `DetectorRegistry.create(name=...)` / `Detection3DRegistry.create(...)`.
3. Push configuration into `app.state.pending_detector_backend` + `pending_lifter` + `pending_detector_params` so the coordinator restart picks it up — same mechanism the SLAM picker uses.

## Coordinator Orchestration Details (Answer to Q7)

### Per-robot detection path (new)

```python
# src/coordination/coordinator.py  (changes in __init__ and _send_viz_update)

class Coordinator:
    def __init__(self, bridge, robots, config, partitioner=None, merger=None, viz=None,
                 app_state=None):
        ...
        # v3.0: replaces lines 139-148 (YOLO ObjectDetector block)
        self._worker_pool: DetectorWorkerPool | None = None
        self._app_state = app_state
        try:
            self._worker_pool = DetectorWorkerPool.create(
                robot_ids=list(robots.keys()),
                detector_name=getattr(app_state, "active_detector_backend", None),
                lifter_name=getattr(app_state, "active_lifter", None),
                detector_params=getattr(app_state, "pending_detector_params", {}),
                intrinsics=config.camera_intrinsics,
            )
            self._worker_pool.start()
        except (ImportError, ValueError) as e:
            logger.warning("Detector pool unavailable: %s", e)
            self._worker_pool = None
```

In `_send_viz_update`:
```python
# Submit (non-blocking; drops old frame if pool busy)
if self._worker_pool is not None:
    needs_cloud = self._worker_pool.needs_slam_cloud(rid)
    self._worker_pool.submit(
        rid,
        frames[rid],
        pose,
        slam_cloud=(cloud_pts if needs_cloud else None),
    )
    dets_3d = self._worker_pool.get_latest(rid)  # Detections3D | None
else:
    dets_3d = None

robot_data[rid] = RobotVizData(..., detections_3d=dets_3d, ...)
```

### Backpressure summary

- **Coordinator thread** (sim loop): never blocks. `submit` is lock+assign, O(1).
- **DetectorWorker thread**: drains when ready. If it's slow, stale frames are overwritten, only the newest is processed.
- **Crash path**: `DetectorWorker._loop` catches subprocess bridge returning None, calls `self._fallback_to_default()` which creates a YOLOv11Backend in-process and emits a `crash_fallback` event via a callback registered by `DetectorWorkerPool`.

### Restart semantics (per-robot hot-swap NOT supported)

Matches v2.0 SLAM: detector swap happens on restart via `reset_for_restart`. The pipeline editor's `ApplyBar` already triggers a restart for SLAM changes; detector changes reuse the same mechanism.

## Build Order (Answer to Q8)

Dependency-ordered phases respecting `DetectorProtocol/Registry → YOLO wrap → 3D strategy API → BoxeR subprocess → frontend → metrics → pipeline nodes`.

### Phase 1: Protocol + Registry + YOLOv11 Refactor (foundation)
**Creates:** `src/perception/protocol.py`, `src/perception/registry.py`, `src/perception/backends/yolov11_backend.py`, `src/perception/detector_worker.py`
**Modifies:** `src/perception/detector.py` (shim/delete), `src/coordination/coordinator.py` (worker pool)
**Test:** All existing 2D detection tests pass; `Coordinator` emits detections identical to v2.x with new plumbing.
**Rationale:** Cannot add a second backend without the abstraction. YOLO wrap is a pure refactor — zero behavioural regression. Establishes worker-per-robot threading.

### Phase 2: Detection3DProtocol + MedianDepthLifter + PointClusterLifter
**Creates:** `src/perception/lifters/median_depth.py`, `src/perception/lifters/point_cluster.py`
**Modifies:** Protocol / registry entries; `OrientedBox3D` payload shape in `streaming_viz.py`; wire `detections_3d` WS message.
**Test:** `median_depth` lifter reproduces v2.x AABB positions to within ε. `point_cluster` lifter outputs oriented boxes with non-identity quaternions for non-axis-aligned objects.
**Rationale:** Once 2D refactor is stable, orthogonal 3D stage unlocks. Two lifters prove the pluggability.

### Phase 3: SubprocessDetectorBridge + BoxeR Backend
**Creates:** `src/perception/subprocess_bridge.py`, `src/perception/backends/boxer_backend.py`, install/download scripts.
**Modifies:** Graceful-degradation import dance in `main.py`.
**Test:** BoxeR subprocess spawns, single-frame forward produces Detections2D; crash injection (kill subprocess) triggers fallback to YOLO + `crash_fallback` WS message.
**Rationale:** First heavy backend using the v2.0-tested subprocess+ZMQ pattern. BoxeR before GroundingDINO because BoxeR is closed-vocab (simpler contract) and already mentioned in PROJECT.md as a specific v3.0 goal.

### Phase 4: FastAPI `/api/detectors/*` Routes + Frontend Picker + Parameter Panel
**Creates:** `backend/web/detector_routes.py`, `frontend/src/stores/detectorStore.ts`, `DetectorDropdown`, `LifterDropdown`, `DetectorSection`.
**Modifies:** `server.py` (router + WS dispatch), `Sidebar.tsx`, `useWebSocket.ts`.
**Test:** Frontend lists backends + lifters, selecting BoxeR triggers restart, live conf-threshold slider sends `detector_param_update`, UI shows `slam_param_ack`-style ACK.
**Rationale:** End-to-end UX comes *after* backends work. Without real BoxeR, the picker would be single-item.

### Phase 5: Frontend 3D OrientedBox Rendering + DetectionBoxManager Rewrite
**Modifies:** `DetectionBoxes.ts` (consume quaternion + half_extents, drop intrinsic derivation), `SceneViewer.tsx`.
**Test:** Chair detection renders as an oriented box aligned with its principal axis, not an AABB; rotating the robot around a chair keeps the box's orientation stable (world-frame, not view-frame).
**Rationale:** Now that `point_cluster` and BoxeR produce oriented boxes end-to-end, the frontend must stop faking them. Critical visible win of v3.0.

### Phase 6: Detection Metrics Pipeline (FPS, #det, conf histogram)
**Creates:** `DetectionMetricsCard`.
**Modifies:** `metricsStore.ts`, `MetricsPanel.tsx`, `MetricsTracker` (backend) to consume `Detections3D.metrics`.
**Test:** MetricsPanel shows per-robot per-backend FPS and detection counts with baseline capture on restart (mirror SLAM metrics comparison).
**Rationale:** Metrics need real data from two comparable backends (YOLO vs BoxeR) to be meaningful.

### Phase 7: Pipeline Editor Nodes (DetectorNode, Detection3DNode, TrackerNode)
**Modifies:** `pipelineTypes.ts`, `nodeDefinitions.ts`, `pipelineValidation.ts` (type-mismatch check), `pipeline_routes.py`.
**Creates:** `perception_rgbd` preset.
**Test:** User drags DetectorNode onto canvas, wires to existing SensorNode + SLAMNode, hits Apply, pipeline restarts with the selected detector wired from the editor.
**Rationale:** Comes last because it exposes the full perception stack once everything below works. Also the highest risk of scope creep — locking port schemas after real runtime integration prevents rework.

### (Optional Phase 8, discovered by research) GroundingDINO + Tracker
**Creates:** `grounding_dino_backend.py`, `bytetrack_tracker.py`.
**Modifies:** Text-prompt param wiring in `DetectorNode`.
**Rationale:** Open-vocab + tracking are additive. Scope-locked after ecosystem research in FEATURES.md.

## NEW vs MODIFIED Summary (Answer to Q9)

### NEW — Python (12 files)
```
src/perception/protocol.py                          NEW
src/perception/registry.py                          NEW
src/perception/detector_worker.py                   NEW
src/perception/subprocess_bridge.py                 NEW
src/perception/backends/__init__.py                 NEW
src/perception/backends/yolov11_backend.py          NEW
src/perception/backends/boxer_backend.py            NEW
src/perception/backends/grounding_dino_backend.py   NEW (Phase 8)
src/perception/lifters/__init__.py                  NEW
src/perception/lifters/median_depth.py              NEW
src/perception/lifters/point_cluster.py             NEW
src/perception/lifters/omnibox3d.py                 NEW (research-gated)
backend/web/detector_routes.py                      NEW
```

### NEW — Frontend (4+ files)
```
frontend/src/stores/detectorStore.ts                NEW
frontend/src/components/DetectorDropdown.tsx        NEW
frontend/src/components/LifterDropdown.tsx          NEW
frontend/src/components/DetectorSection.tsx         NEW
frontend/src/components/DetectionMetricsCard.tsx    NEW
```

### MODIFIED — Python (6 files)
```
src/perception/detector.py               -> shim then deleted (DEPRECATED)
src/perception/detection_3d.py           -> moved to lifters/median_depth.py (DEPRECATED)
src/coordination/coordinator.py          -> DetectorWorkerPool instead of ObjectDetector (~30 lines diff)
src/main.py                              -> importlib dance for detector backends (~10 lines)
backend/web/server.py                    -> app.state scaffolding + detector_routes include + detector_param_update WS (~30 lines)
backend/web/streaming_viz.py             -> detections_3d message emitter (~15 lines)
backend/web/message_types.py             -> DETECTIONS_3D constant (1 line)
backend/web/pipeline_routes.py           -> detector/lifter node type handlers (~30 lines, Phase 7)
```

### MODIFIED — Frontend (8 files)
```
frontend/src/hooks/useWebSocket.ts                       -> detections_3d case, detector_param_ack, detector_restart_complete, subsystem-aware crash_fallback
frontend/src/stores/robotStore.ts                        -> detections3D field + updateDetections3D
frontend/src/stores/metricsStore.ts                      -> detectionMetrics per robot
frontend/src/components/DetectionBoxes.ts                -> consume OrientedBox3D[], drop FOV/intrinsic math
frontend/src/components/SceneViewer.tsx                  -> pass OrientedBox3D[] to manager
frontend/src/components/Sidebar.tsx                      -> <DetectorSection />
frontend/src/components/MetricsPanel.tsx                 -> <DetectionMetricsCard />
frontend/src/components/CrashToast.tsx                   -> subsystem-aware message ("Detector crashed..." vs "SLAM crashed...")
frontend/src/utils/pipelineTypes.ts                      -> Detections2D | Detections3D in PortDataType, 'perception' in NodeCategory
frontend/src/utils/nodeDefinitions.ts                    -> detector_generic, detection_3d_generic, tracker_generic + colors/shapes
frontend/src/utils/pipelineValidation.ts                 -> findTypeMismatches for typed edges
frontend/src/stores/pipelineStore.ts                     -> onConnect reads real port dataType (bugfix)
frontend/src/components/pipeline/PipelineNode.tsx        -> perception icon
```

## Scalability Considerations

| Concern | 2 robots (default) | 4 robots | 8+ robots |
|---------|--------------------|----------|-----------|
| Detector worker threads | 2 threads, ~60 MB each for YOLO | 4 threads, ~240 MB total | Move all but default backend to subprocess; CPU contention > memory |
| Subprocess count (BoxeR) | 2 subprocesses × ~2 GB each = 4 GB RAM | 4 × 2 GB = 8 GB | Share one BoxeR subprocess with batched requests (per-robot queues on Python side, one ZMQ PAIR socket with round-robin) |
| Detection FPS (BoxeR CPU) | ~3-5 FPS per robot | Same per-robot | Frames will drop more aggressively; no additional mechanism needed because backpressure is per-worker |
| WS bandwidth (detections_3d) | ~5 KB × 10 Hz × 2 = 100 KB/s | 200 KB/s | Negligible vs cloud delta; no action |
| Pipeline graph nodes | Small (4-6 nodes) | Same | Same (graph is per-pipeline, not per-robot) |

**Shared-subprocess pattern for N>4:** Post-v3.0 optimization. Build a `BatchedDetectorBridge` that accepts `List[SensorFrame]` instead of single frame; each robot's worker multiplexes through one subprocess. Defer until 4+ robot profiling shows the need.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Sharing `SubprocessSLAMBridge` with detection traffic
**What:** Reusing the SLAM bridge to avoid a second ZMQ endpoint.
**Why bad:** Couples two independent failure domains; header needs a discriminator field; crash fallback ambiguous.
**Instead:** `SubprocessDetectorBridge` is structurally identical but its own class with its own endpoint pattern (`ipc:///tmp/detector_bridge_<pid>_<id>`).

### Anti-Pattern 2: Unified `DetectorProtocol` producing 3D boxes directly
**What:** Fold 2D+3D into one protocol method `detect_3d(frame) -> Detections3D`.
**Why bad:** Every new 2D backend re-implements median-depth or PCA; decouples us from open research on lifters.
**Instead:** Two protocols; detectors expose an optional `outputs_3d_natively` capability for end-to-end models.

### Anti-Pattern 3: One shared detector thread for all robots (status quo)
**What:** Keep the current `ObjectDetector._run_loop` pattern.
**Why bad:** Slow model on robot A blocks robot B; per-robot backpressure impossible; breaks per-robot backend selection.
**Instead:** One `DetectorWorker` thread per robot, single-slot pending queue.

### Anti-Pattern 4: Frontend re-deriving box size from pixel bbox + depth + FOV
**What:** Keep current `DetectionBoxes.ts` logic (lines 81-90) that computes `worldW = bbox_px_w * depth / focal`.
**Why bad:** Hardcoded 70° FOV, hardcoded imgH=480, breaks when intrinsics change, impossible to express true oriented boxes.
**Instead:** Backend computes `(center, half_extents, quaternion)` server-side and ships world-frame geometry. Frontend renders verbatim.

### Anti-Pattern 5: Hot-swap detector mid-run
**What:** Change backend without restart so exploration doesn't pause.
**Why bad:** Same issues as SLAM hot-swap (documented in v2.0 ARCHITECTURE.md): accumulated state, tracking continuity, detector-specific warmup frames.
**Instead:** Apply on restart. The `/api/detectors/select` endpoint triggers restart via `app.state.command_callback({"action":"restart"})` — identical to SLAM.

### Anti-Pattern 6: Pipeline editor with untyped edges ('PointCloud' as const)
**What:** Keep `pipelineStore.ts` `onConnect` line 101 hardcoded to PointCloud.
**Why bad:** Perception edges look "connected" but carry the wrong type label, downstream type checks become impossible.
**Instead:** Phase 7 bugfix: read `sourcePort.dataType` from source node. Add `findTypeMismatches` validator.

## Sources

- Direct codebase analysis (v2.0 shipped): `src/slam/protocol.py` (80 LOC), `src/slam/registry.py` (128 LOC), `src/slam/backends/subprocess_bridge.py` (200 LOC), `src/slam/backends/orbslam3_backend.py` (368 LOC) — HIGH confidence on the patterns being mirrored.
- Direct codebase analysis (current perception): `src/perception/detector.py` (241 LOC), `src/perception/detection_3d.py` (83 LOC), `src/coordination/coordinator.py` (737 LOC) — HIGH confidence on integration points.
- Direct codebase analysis (web layer): `backend/web/slam_routes.py` (175 LOC), `backend/web/server.py` (228 LOC), `backend/web/streaming_viz.py` (391 LOC) — HIGH confidence.
- Direct codebase analysis (frontend): `frontend/src/stores/slamStore.ts` (89 LOC), `frontend/src/stores/pipelineStore.ts` (218 LOC), `frontend/src/utils/pipelineTypes.ts` (73 LOC), `frontend/src/utils/nodeDefinitions.ts` (280 LOC), `frontend/src/utils/pipelineValidation.ts` (112 LOC), `frontend/src/components/DetectionBoxes.ts` (170 LOC), `frontend/src/components/pipeline/PipelineNode.tsx` (240 LOC) — HIGH confidence.
- v2.0 research archive: `.planning/milestones/v2.0-research/ARCHITECTURE.md` — the decisional template this document mirrors; HIGH confidence that following its structure yields a compatible v3.0.
- Existing `.planning/codebase/ARCHITECTURE.md` — broader DimOS context; MEDIUM relevance (DimOS layer is replaced by in-process transport per v1.0 decision).
