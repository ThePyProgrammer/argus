# Feature Landscape: v3.0 Pluggable Perception & 3D Object Detection

**Domain:** Multi-robot SLAM + perception stack with pluggable object-detection backends and real 3D oriented bounding box regression
**Researched:** 2026-04-13
**Confidence:** MEDIUM-HIGH (v2.0 SLAM-picker pattern verified in-tree; detector/tracker/3D-lift ecosystem well-documented in Isaac ROS, Autoware, Nav2, Hugging Face; BoxeR and RT-DETR verified via arXiv/HF)

## Context & Anchoring

The v2.0 milestone already established the mechanical pattern this milestone must mirror:

- `SLAMProtocol` (runtime-checkable) + `SLAMResult` dataclass + `SLAMRegistry` (class-path lazy import + `@slam_backend` decorator)
- Frontend picker → REST `/api/slam/backends` → parameter panel from `PARAMETER_SCHEMA` → restart overlay → live metrics
- Subprocess+ZMQ isolation for C++/crashy backends (`SubprocessSLAMBridge`, 5s hang detection, ICP fallback)
- Pipeline-editor: 11 typed node definitions, Kahn's-algorithm validation, preset library, React Flow canvas

The existing YOLO path (`src/perception/detector.py`, `src/perception/detection_3d.py`, `frontend/src/components/DetectionBoxes.ts`) is an **isolated, hardcoded module**: `ObjectDetector` wires YOLOv11n + a fixed `INDOOR_CLASSES` whitelist + single-class hyperparams; `project_detections_to_3d` takes median-depth-in-bbox and outputs an axis-aligned *point* (no orientation, no real box dimensions); the frontend reconstructs a wireframe box client-side from `(bbox, depth)` and calls it 3D. Every one of those is a v3.0 obligation to replace.

All features in this document are scoped **specifically to the detector → 3D-box → frontend → pipeline-editor → metrics loop**. The SLAM pluggability, merge strategy pluggability, and the frontend architecture itself are OUT OF SCOPE: they already exist and are being mirrored, not redesigned.

Category tags (for downstream REQ-ID grouping): **DET-API** (protocol/registry/lifecycle), **DET-MODELS** (backend implementations), **DET-3D** (2D→3D projection and oriented box regression), **DET-UI** (frontend picker, param panel, overlays), **DET-METRICS** (FPS, counts, confidence, mAP), **DET-PIPELINE** (React Flow node additions). Some features span two; the primary category is listed first.

---

## Table Stakes

Features that MUST ship or the milestone fails on its own terms (the abstraction provides no value over the hardcoded YOLO call).

| # | Feature | Category | Why Expected | Complexity | Dependencies | Notes |
|---|---------|----------|--------------|------------|--------------|-------|
| T1 | **`DetectorProtocol` runtime-checkable interface** | DET-API | Without a Protocol there is no "pluggable detection." Mirror of `SLAMProtocol`. | S | None (new code) | `process_frame(rgb, depth, intrinsics, pose) -> DetectionResult`; `reset()`; `CAPABILITIES: dict`; `PARAMETER_SCHEMA: dict`; `@property last_inference_ms`. `DetectionResult` dataclass carries `detections: list[Detection3D]`, `timestamp`, `inference_ms`, `model_name`. Isaac ROS and Autoware both expose detection as a graph of nodes around a typed bbox-array message — the Protocol is the Python-native equivalent. |
| T2 | **`DetectorRegistry` with lazy class-path loading + `@detector_backend` decorator** | DET-API | Mirror of `SLAMRegistry`. Lazy import so missing HuggingFace/transformers does not break import. | S | T1 | Methods: `register(name, display, class_path)`, `list_backends()` (returns `available`, `capabilities`, `parameter_schema`, `reason` if unavailable), `create(name, **kwargs)`, `get_default()`. Default backend: `"yolo"`. This is load-bearing for the frontend picker: the UI lists what the registry returns. |
| T3 | **YOLO backend refactored behind Protocol — zero behavioral regression** | DET-MODELS | The existing detector must still work. This is the proof the abstraction is correct. | S | T1, T2 | Wrap existing `ObjectDetector._detect()`. Preserve `INDOOR_CLASSES` whitelist and 20-px tiny-box filter as `PARAMETER_SCHEMA` fields, not hardcoded constants. Regression test: submit N fixture frames through old and new paths → identical detections. |
| T4 | **Confidence threshold + class filter + min-bbox-size as live-tunable parameters** | DET-API, DET-UI | Every perception stack exposes these (Isaac ROS, Nav2 `vision_msgs`, Hello Robot Stretch, ROS `object_recognition_msgs`). Hardcoding them in 2026 is indefensible. | S | T1 | In `PARAMETER_SCHEMA`: `confidence: {type: "float", min: 0.0, max: 1.0, default: 0.5}`, `iou_nms: {type: "float", default: 0.5}`, `min_bbox_px: {type: "int", default: 20}`, `classes: {type: "multiselect", options: [...]}`. Wire through WebSocket `detector_param_update` (mirror `slam_param_update`). |
| T5 | **Pre-session detector selection via REST + restart overlay** | DET-API, DET-UI | The v2.0 SLAM picker is pre-session; users expect the detector to behave the same way. Hot-swap is explicitly deferred (see anti-features). | S | T2, existing restart plumbing | Endpoints: `GET /api/detector/backends`, `GET /api/detector/active`, `POST /api/detector/select`, `GET|POST /api/detector/params`. Exact shape of `/api/slam/*` — the frontend fetcher can be cloned. |
| T6 | **Graceful fallback when backend dependencies are missing** | DET-API | User's machine is CPU-only; HuggingFace/transformers may not always be installed. The v2.0 pattern flags `available: false, reason: "..."` in the registry listing. | S | T2 | YOLO backend: `YOLO_AVAILABLE` flag already exists; keep it and surface via `CAPABILITIES`. HF backends: try-import in module body, `available = False` if missing. UI grays out unavailable options with reason tooltip — already implemented for SLAM. |
| T7 | **facebook/BoxeR (or closest workable HF detector) as second backend** | DET-MODELS | Explicit v3.0 goal in PROJECT.md. Proves the abstraction supports fundamentally different architectures (CNN YOLO vs. transformer DETR-family). | M-L | T1, T2, transformers ≥ 4.40 | **Verified caveat:** the literal `facebook/BoxeR` is a 2022 CVPR paper with code but is NOT a first-class HF Transformers model — the closest HF-Transformers-native DETR-family detectors are `facebook/detr-resnet-50`, `PekingU/rtdetr_r18vd`, `IDEA-Research/grounding-dino-tiny`. Recommend: land BoxeR via its GitHub repo if feasible; **if not, fall back to `facebook/detr-resnet-50` or `RT-DETR-R18` as the "transformer backend"** and document the substitution. Either way, this is the regression test for the pluggability claim. CPU inference: DETR-R50 is ~2-3s/frame on CPU; RT-DETR-R18 is ~0.5-1s/frame on modern CPU. Both slower than YOLOv11n. |
| T8 | **Real 3D oriented bounding box output (world frame)** | DET-3D | PROJECT.md: "Real 3D oriented bounding box regression (replace depth-median 2D→3D projection)." Current pipeline ships a *point*, not a box. | M | T1 (typed result), depth + intrinsics already available | `Detection3D` carries: `center_world: (3,) float64`, `size_world: (3,) float64` (dx, dy, dz), `yaw_world: float` (or full quaternion), `class_id`, `class_name`, `confidence`, `bbox_2d` (kept for UI overlay), `track_id: int \| None`. CPU-realistic method: lift 2D bbox → depth-segmented frustum → PCA on the in-bbox depth points to fit an oriented box in the gravity-aligned plane. Not SOTA, but correct, CPU-friendly, class-agnostic, and a real oriented box. SOTA (BoxeR-3D, WildDet3D, 3D-MOOD) requires GPU and is out of scope — mention in differentiators. |
| T9 | **Deterministic 3D box dimensions (not reconstructed client-side)** | DET-3D, DET-UI | Current frontend `DetectionBoxes.ts` reconstructs `worldW/worldH/worldD` from `(bbox, depth, fov=70°)` — this is wrong the moment the backend changes image size, intrinsics, or returns a real oriented box. The server must own geometry. | S | T8 | Server sends `{center_world, size_world, yaw_world, class, confidence, track_id}`. Frontend becomes dumb: place box at center, orient by yaw, size from size_world. Delete the client-side focal-length math. |
| T10 | **Per-camera / per-robot detector configuration** | DET-API | Multi-robot systems where robots have different camera configs (intrinsics, mounting pose, resolution) need per-camera inference. Nav2 / Isaac ROS both expose per-camera configs. Go2s are homogeneous in this project but the Protocol must not preclude it. | S | T1 | Registry `create(name, robot_id=..., intrinsics=..., **kwargs)`. Detector holds per-robot state the same way `ObjectDetector` already does (`_pending_frames: dict[robot_id, ...]`). Doesn't add phase work but constrains T1 API shape. |
| T11 | **Async background inference loop + latest-frame-only queue** | DET-API | YOLO at 0.5 FPS, transformer backends at 0.3-0.5 FPS; blocking the main loop is unacceptable. Existing detector already does this — the Protocol must codify it. | S | T1 | Contract: `submit_frame(robot_id, rgb, depth, pose)` returns immediately; a single per-backend worker thread/process consumes the latest pending frame per robot. Drop stale frames. Guaranteed by `_pending_frames: dict` semantics. |
| T12 | **Live detection metrics in MetricsPanel** | DET-METRICS, DET-UI | v2.0 established ATE/RPE/ms-per-frame sparklines; users will expect detection to contribute. | S | T1 (DetectionResult carries timing), existing MetricsTracker | Per-robot, per-backend metrics: `inference_ms` (p50, p95), `detections_per_frame`, `mean_confidence`, `fps`. Stream via existing `stats` WebSocket as `detection_metrics` key. Extend `metricsStore` Zustand slice. |
| T13 | **Frontend detector picker with capability badges + parameter panel** | DET-UI | Exact mirror of SLAM picker. Not having it = inconsistent UX. | S | T2, existing UI components (`CapabilityBadge`, `ConfirmModal`, `RestartOverlay`) | New `detectorStore` Zustand slice. Reuse `CapabilityBadge` for "transformer", "bbox2d-only", "oriented-3d", "real-time", "gpu-required". Parameter panel renders from `PARAMETER_SCHEMA` via the same schema-driven renderer. Pre-session selection → restart overlay flow already built. |
| T14 | **Detector + 3D-projection nodes in React Flow pipeline editor** | DET-PIPELINE | PROJECT.md lists "Pipeline-editor nodes for detector + 3D-projection stages." v2.0 pipeline-editor has 11 node types; perception is a gap. | M | T1, existing `NodeCatalog`, `PipelineBuilder`, 7 port types | New node definitions: (a) `DetectorNode` — inputs RGB+depth+pose, outputs `Detection2D[]`; (b) `BoxLiftNode` — inputs `Detection2D[]` + depth + intrinsics, outputs `Detection3D[]`. New port data types: `detection2d`, `detection3d`. Dropdown on `DetectorNode` selects registered backend; parameters flow through the inspector panel. Add 1-2 presets (e.g., "SLAM + YOLO + 3D Lift", "SLAM + DETR + 3D Lift"). |

---

## Differentiators

Features that elevate the perception layer beyond "pluggable YOLO" and align with what Autoware/Isaac ROS/Nav2 expose. Not required for milestone success; strong candidates for phase 2/3 of the roadmap.

| # | Feature | Category | Value Proposition | Complexity | Dependencies | Notes |
|---|---------|----------|-------------------|------------|--------------|-------|
| D1 | **Multi-object tracker with persistent track IDs (ByteTrack or SORT)** | DET-3D, DET-METRICS | Single-frame detections flicker; users immediately want "that's the same chair as before." Autoware uses tracker-aware detection; Isaac ROS has `isaac_ros_nvtracker`. ByteTrack is CPU-friendly and does not need a re-ID network. | M | T1, T8 | ByteTrack is Apache-2.0 Python, ~300 LOC, pure Kalman+IoU. Appends `track_id: int` to `Detection3D`. Frontend: stable colors per `track_id` instead of per `robot_id`. DeepSORT explicitly avoided — its CNN re-ID head is a CPU killer on this budget. |
| D2 | **World-frame multi-robot detection fusion** | DET-3D | N robots see the same chair from different angles; without fusion the viewer shows N overlapping boxes. v2.0 merges maps; v3.0 should merge detections. Core value of "multi-robot" is lost otherwise. | M | D1 (stable IDs help), existing pose graph | Cluster `Detection3D` across robots by class + spatial IoU/distance with Dirichlet-process-style association (cited in semantic-SLAM survey). Serve unified `world_detections: list[WorldDetection3D]` WebSocket message. Hard case: cross-robot track ID handoff. Defer full re-ID; cluster per frame is sufficient. |
| D3 | **Oriented bounding box via PCA-on-depth-frustum (gravity-aligned)** | DET-3D | This is the "real oriented 3D box" path for CPU. Axis-aligned boxes look wrong when objects are at an angle; gravity-aligned yaw looks correct in >90% of indoor cases. | M | T8 | Steps: (1) backproject bbox-masked depth to point frustum in world frame, (2) project to ground plane, (3) 2D PCA → yaw + width/length, (4) z-range from min/max depth. O(bbox_pixels) per detection, negligible CPU cost. Class-agnostic. Known limitation: depth-noise-sensitive for small objects; mitigate by requiring ≥50 valid depth pixels. |
| D4 | **Overlay detections on the raw RGB camera feed panel** | DET-UI | The raw camera feed already streams in the C2 UI. Drawing the 2D bbox + class + confidence overlay is trivial and standard (every ROS rqt/Foxglove/Rerun UI does this). | S | T1 (bbox_2d in result) | 2D canvas overlay on the existing `<canvas>`/`<img>` camera feed. No Three.js needed. |
| D5 | **Confidence histogram + per-class count sparklines** | DET-METRICS, DET-UI | Answers "is the detector confused?" at a glance. Autoware and Isaac ROS dashboards ship this; research-grade stacks (FrameNet, Nuscenes devkit) expect it. | S | T12 | Extend metrics message with `confidence_bins: [0.5-0.6: N, 0.6-0.7: N, ...]` and `class_counts: {chair: N, ...}` rolling over a sliding window. Render as two sparkline components in MetricsPanel. |
| D6 | **Ground-truth object positions from MuJoCo + on-line mAP / per-class recall** | DET-METRICS | MuJoCo knows every object's true pose and class — free ground truth. Computing mAP@0.5 live is a 50-line task (matching by IoU), and it's the one quality metric that makes backend comparison meaningful. Research-grade systems expose this; consumer robotics does not, because they lack GT. | M | T1, MuJoCo body introspection | Map MuJoCo `body_id → class` via the scene XML, take `body_xpos + geom_size`, compute 3D IoU (or 2D IoU on projected bbox for a cheaper variant). Emit `mAP_50, mAP_50_95, per_class_recall` on the stats WebSocket. Guarded by a capability flag — disabled in real-world deployments. |
| D7 | **Parameter presets per backend (accurate / balanced / fast)** | DET-API, DET-UI | Same pattern the v2.0 SLAM panel already supports. Low marginal cost. | S | T4, T13 | 2-3 presets per backend. Dropdown in parameter panel. |
| D8 | **Per-robot detector selection (different model per robot)** | DET-API, DET-UI | Genuinely useful asymmetric setup: one robot runs fast YOLO for exploration, another runs DETR for scrutinizing. Nav2 and Isaac ROS natively allow this via per-robot node instances. | M | T5, T10 | API shape: `POST /api/detector/select` accepts `{backend, robot_id?: str}`. UI: picker gains a per-robot tab or a "apply to: [all/robot_a/robot_b]" selector. **Adds UX complexity — recommend deferring unless users ask.** |
| D9 | **Semantic map: world-frame detection log with TTL + persistence** | DET-3D | Every serious perception stack builds a semantic map (Voxblox++, Fusion++, Hydra, Autoware object map). Persisting detections into a world-frame log with class labels transforms ephemeral bboxes into a queryable "scene inventory." | M-L | D1, D2 | Server keeps `SemanticMap: dict[track_id, WorldObject]` with `last_seen_ts`, TTL decay, class probability accumulation. New WebSocket message `semantic_map_update`. New Three.js layer renders persistent boxes distinct from live detections (e.g., ghosted). |
| D10 | **Export detections (JSON / CSV per session)** | DET-METRICS, DET-API | Research users want offline analysis. v2.0 already added metrics export; extending is 10 lines. | S | Existing metrics export plumbing | `/api/detections/export?format=jsonl` endpoint. Streams `{ts, robot_id, track_id, class, confidence, center_world, size_world, yaw_world, bbox_2d}` per line. |
| D11 | **Pipeline-editor: Tracker node + SemanticMap node** | DET-PIPELINE, DET-3D | Makes the pipeline editor express the full perception graph: detector → lift → tracker → semantic map. Mirrors how Autoware's perception is wired. | M | T14, D1, D9 | Two additional node definitions. New port types: `tracked_detection3d`, `semantic_map`. One additional preset. |
| D12 | **False-positive flagging UI (right-click a box → "mark FP")** | DET-METRICS, DET-UI | Builds a labeled dataset for free during normal use. Standard in labeling tools (Label Studio, CVAT) but uncommon in live robot UIs — a real differentiator. | M | T13 (box picking), Detection3D carries track_id | Append `{track_id, fp: true, ts}` to a local JSONL log. Exposed in `/api/detections/export`. No auto-retraining — just collection. |

---

## Anti-Features

Things users may ask for, that look reasonable, but are wrong for this project's constraints (CPU-only, simulation-first, research-grade). Explicit "no" list for scope defense.

| # | Anti-Feature | Why It Looks Appealing | Why It's Wrong Here | What To Do Instead |
|---|--------------|-----------------------|---------------------|-------------------|
| A1 | **Hot-swap detector mid-session** | Symmetry with "pluggable" branding. "Why not? SLAM picker is pre-session but surely detectors are lighter." | Models take 2-5s to load on CPU. Warm tracker state (track IDs, Kalman filter) becomes meaningless across models with different class lists. Semantic map needs rebuild. PROJECT.md already deferred SLAM hot-swap in v2.0 for the same reasons. | Pre-session selection + restart overlay (T5). Reuse v2.0 restart plumbing verbatim. |
| A2 | **Run multiple heavy detectors simultaneously on all robots** | "Ensembling boosts mAP." True in offline benchmarks. | YOLOv11n ≈ 0.5 FPS CPU; DETR-R50 ≈ 0.3 FPS CPU. Two simultaneously on 2 robots = 4 backends competing for ~8 CPU threads, all falling under 0.2 FPS. The metrics panel will just show everything broken. | Side-by-side comparison mode (offered as future stretch): ONE robot runs A, ANOTHER runs B, compare on shared GT. Not ensemble — sampling. |
| A3 | **Per-frame model re-initialization / reloading** | Appears in naive async code when devs forget to cache a model handle. | Adds 2-5s per frame = system becomes unusable. | Load once at backend construction; caller holds reference; registry returns instance. |
| A4 | **DeepSORT with CNN re-ID backbone** | Best per-paper tracking accuracy among classical trackers. | Re-ID CNN adds another forward pass per detection per frame. On CPU this is the straw on the camel's back. ByteTrack (IoU + Kalman only) delivers 95% of the value at 5% of the compute. | ByteTrack or SORT (D1). |
| A5 | **GPU-required backends (BEVFormer, CenterPoint, WildDet3D)** | State-of-the-art 3D detection. All of Autoware's recent advances. | Environment has no NVIDIA GPU (PROJECT.md constraint — explicitly repeated from v2.0 deferral of GPU SLAM backends). | Document in "deferred to v4.0" list. Keep Protocol API shape compatible so they drop in later. |
| A6 | **Detector picker inside the React Flow node (different from top-level picker)** | Feels natural: "each pipeline node should configure its own model." | Two pickers → two sources of truth → state-sync bug guaranteed. v2.0 already has the "pre-session top-level picker" pattern working. | Pipeline-editor node displays the currently-active backend (read-only), with a link "change in Settings". Single picker owns state. |
| A7 | **Running the VLM scene-describer and the detector simultaneously on every robot** | `scene_describer.py` already exists and produces rich descriptions; tempting to "just always run both." | VLM (moondream) takes ~3-5s per image CPU-bound. Combined with a detector, per-robot perception drops under 0.1 FPS. | Keep VLM as opt-in, low-duty-cycle (every 10-30s), separate from detector pipeline. Out of scope for v3.0 — do not mix into detector Protocol. |
| A8 | **Arbitrary-class open-vocabulary detection (Grounding DINO, OWL-ViT)** | Massive expressive power — detect anything by text prompt. | CPU inference is 5-10s per frame per query. OWL-ViT quickly becomes unusable beyond 2-3 prompts. Interesting research path but not v3.0 table stakes. | Defer. Registry is extensible — add a `GroundingDinoBackend` in v4.0 if someone finds a GPU. |
| A9 | **3D bbox directly from the 2D-only detector's logits (e.g., "add a regression head to YOLO")** | Looks like the efficient path: one network, one pass. | Requires retraining the detector with 3D labels. The value of the abstraction is precisely that the 2D detector stays 2D and the 3D lifting is a separate, swappable stage. Mixing them locks the 3D approach to one architecture. | Keep `BoxLiftNode` separate from `DetectorNode` in the pipeline (T14). Compose stages, don't fuse them. |
| A10 | **Client-side 3D geometry reconstruction** | Already in the codebase — the frontend recomputes box dims from bbox+depth+fov. "If it works, why change it?" | Any backend change breaks silently (T9). Violates separation of concerns. Invalidates unit-testing of 3D output. | Server owns geometry. Frontend is a dumb renderer of `(center, size, yaw)`. Delete the focal-length math from `DetectionBoxes.ts`. |
| A11 | **Continuous online model retraining / active learning** | "The robot is already labeling — why not fine-tune?" | Out of scope; requires labeling UX, training pipeline, model versioning, eval harness. | FP flagging (D12) collects data only. Retraining is a separate milestone if ever. |
| A12 | **Detection for classes not in the MuJoCo scene** | COCO has 80 classes; why not expose them all? | The scene contains ~10-20 actual object types. Exposing all 80 creates false positives and clutters the UI. | Keep `INDOOR_CLASSES` whitelist as default; make it schema-tunable (T4). |

---

## Feature Dependencies

```
DetectorProtocol (T1) [DET-API]
  |
  +--> DetectorRegistry (T2) [DET-API]
  |     |
  |     +--> YOLO refactor (T3) [DET-MODELS]  --regression test--> v1.0 YOLO behavior preserved
  |     +--> Graceful fallback (T6) [DET-API]
  |     +--> BoxeR/DETR/RT-DETR backend (T7) [DET-MODELS]  <-- HARDEST new dependency (HF transformers on CPU)
  |
  +--> Live-tunable params (T4) [DET-API, DET-UI]
  |     |
  |     +--> Parameter presets (D7) [DET-API]
  |
  +--> Per-camera config (T10) [DET-API]
  |     |
  |     +--> Per-robot detector selection (D8) [DET-API]
  |
  +--> Async frame queue (T11) [DET-API]
  |
  +--> Detection3D result type (T8) [DET-3D]
        |
        +--> Server-owned geometry (T9) [DET-3D, DET-UI]
        +--> PCA-on-frustum oriented box (D3) [DET-3D]
        +--> Tracker with ByteTrack (D1) [DET-3D]
              |
              +--> Multi-robot fusion (D2) [DET-3D]
                    |
                    +--> Semantic map with TTL (D9) [DET-3D]
                          |
                          +--> SemanticMap node in pipeline editor (D11) [DET-PIPELINE]

REST + WS plumbing (mirror v2.0 SLAM):
  T5 (pre-session selection) ---> T13 (frontend picker + param panel) [DET-UI]
                                        |
                                        +--> RGB overlay (D4) [DET-UI]
                                        +--> FP flagging (D12) [DET-METRICS, DET-UI]

Metrics:
  T1 --inference_ms--> T12 (live FPS/count/confidence in MetricsPanel) [DET-METRICS]
                             |
                             +--> Confidence histogram + per-class sparklines (D5)
                             +--> MuJoCo GT -> live mAP (D6)
                             +--> Export JSONL (D10)

Pipeline editor:
  T1, T8 ---> T14 (DetectorNode + BoxLiftNode) [DET-PIPELINE]
                  |
                  +--> D11 (TrackerNode + SemanticMapNode)
```

**Critical ordering constraints (for roadmap phase ordering):**

1. **T1 → T2 → T3 is atomic.** Ship together or the YOLO regression surface breaks.
2. **T8 before T14.** The pipeline-editor nodes need the typed `Detection3D` result to define port data types.
3. **T13 before T12.** The MetricsPanel extension is trivial once the frontend detector store exists; doing it first requires throwaway wiring.
4. **T9 blocks *any* visible win from T8.** Until the frontend stops reconstructing boxes, the server's oriented-box output is invisible. Pair them in the same phase.
5. **D1 before D2 before D9.** Tracking → fusion → persistent semantic map is the only sensible order.
6. **T7 (second backend) is the pluggability regression test** — runs last in the "core" set, because it pressure-tests every API decision made in T1-T6.

---

## Existing-System Dependencies (v2.0 surface area this milestone consumes)

| v2.0 asset | How v3.0 uses it | Risk |
|------------|------------------|------|
| `SLAMProtocol`, `SLAMRegistry`, `@slam_backend` | Copy-paste-rename as `DetectorProtocol`, `DetectorRegistry`, `@detector_backend`. Shape, semantics, lazy-load logic all reusable verbatim. | Low — proven pattern. |
| `SubprocessSLAMBridge` + ZMQ isolation | If a detector backend is crashy or has painful deps (unlikely for pure-Python HF models, possible for C++ detectors like YOLOv8-TensorRT or Detectron2), reuse the bridge. | Low — only needed for non-Python backends, currently none planned. |
| `CapabilityBadge`, `ConfirmModal`, `RestartOverlay` | Reuse directly in the detector picker. | None. |
| `parameter schema → form` frontend renderer | Must generalize over detector schemas (`multiselect` for class filter is new, add it once). | Low — one new widget type. |
| `MetricsTracker` ring buffers | Extend with `detection_metrics` per-robot entry. Same pattern as `slam_metrics`. | Low. |
| `metricsStore` Zustand slice + `useWebSocket` dispatch | Add `detection_metrics` message handler. | Low. |
| `ControlPanel` + `ViewToggle` + `Sidebar` layout | Detector picker lives alongside SLAM picker; no layout changes. | Low. |
| React Flow `NodeCatalog`, `PipelineBuilder`, Kahn's-algorithm validator, 7 port data types | Add 3 new port types (`detection2d`, `detection3d`, `tracked_detection3d`), 2-4 new node definitions, 1-2 presets. Validator is algorithm-generic; no changes. | Medium — port-type schema changes touch serializer tests. |
| `DetectionBoxManager` (frontend) | **Gut client-side geometry reconstruction** (T9) and repurpose as dumb renderer of server-owned `(center, size, yaw)`. | Medium — existing FP rendering needs visual regression test. |
| MuJoCo body/geom introspection | For D6 (ground-truth mAP). Need to map body_id ↔ class via scene XML. | Low-Medium — scene files vary, need a discovery strategy. |

---

## MVP Recommendation (maps onto roadmap phases)

**Phase A — DET-API core (table stakes T1, T2, T3, T4, T6, T10, T11):**
Ship the Protocol, Registry, YOLO refactor behind it, schema-driven params, graceful fallback, per-camera keyword, async queue contract. Zero user-visible change — this is the load-bearing phase.

**Phase B — DET-UI + REST plumbing (T5, T13, D4, D7):**
Backend selection API, frontend picker, parameter panel, restart overlay, RGB overlay, presets. Users can now switch detector, tune params, and *see something* — even if the only backend is still YOLO.

**Phase C — DET-3D real boxes (T8, T9, D3):**
`Detection3D` result type, PCA-on-frustum oriented boxes, server-owned geometry, frontend renderer simplification. Delivers the PROJECT.md "real oriented 3D boxes" promise.

**Phase D — DET-MODELS second backend (T7):**
BoxeR (or DETR/RT-DETR fallback) integration. Pluggability regression test. This is where the abstraction earns its keep.

**Phase E — DET-METRICS (T12, D5, D6, D10):**
Live FPS/count/confidence in MetricsPanel, histograms, MuJoCo ground-truth mAP, export. Makes backend comparison quantitative.

**Phase F — DET-PIPELINE (T14, D11):**
DetectorNode, BoxLiftNode, TrackerNode, SemanticMapNode in React Flow. Adds perception expressiveness to the pipeline editor.

**Phase G — Differentiators (D1, D2, D9, D8, D12):**
ByteTrack, multi-robot fusion, semantic map with TTL, per-robot detector selection, FP flagging. The "feels like a real stack" phase.

**Deferred to v4.0 explicitly:**
- GPU-required SOTA 3D detectors (BEVFormer, WildDet3D, 3D-MOOD)
- Open-vocabulary detection (Grounding DINO, OWL-ViT) at any useful FPS
- Hot-swap mid-session
- Online active learning / retraining

---

## Confidence & Open Questions

**HIGH confidence:**
- v2.0 pattern is directly applicable (in-tree verification: `src/slam/protocol.py`, `src/slam/registry.py`).
- ByteTrack, SORT as CPU-viable trackers; DeepSORT CPU-hostile — multiple sources.
- DETR-family CPU inference speeds — widely benchmarked.
- Gravity-aligned oriented box from depth frustum via PCA is a textbook method.

**MEDIUM confidence:**
- `facebook/BoxeR` integration path on CPU. BoxeR has a GitHub repo but is not a stock HF-Transformers model. **Recommend the requirements allow substitution to `facebook/detr-resnet-50` or `PekingU/rtdetr_r18vd` if BoxeR integration is painful.** This must be surfaced in requirements, not discovered mid-phase.
- Frame rate targets. YOLOv11n at 0.5 FPS is documented; DETR/BoxeR on CPU is projected at 0.2-0.5 FPS based on general DETR benchmarks. Real numbers await integration.
- Multi-robot detection fusion spatial threshold — no clean "right answer" exists; class + 0.5m cluster radius is a sane starting default.

**LOW confidence (flag for phase-level research):**
- Whether the current MuJoCo scene files carry stable class-labeled geoms suitable for D6 (ground-truth mAP). Needs a 30-min scene-inventory check at phase-planning time.
- Whether `orbslam3`-style subprocess isolation will be needed for any detector backend, or if all target backends are pure-Python. Current plan: assume pure-Python; add subprocess only if a backend proves unstable in-process.

---

## Sources

- [SLAMProtocol + SLAMRegistry — in-tree code](file:///home/prannayag/pragnition/robotics/argus/src/slam/protocol.py) — HIGH
- [Existing ObjectDetector hardcoded path](file:///home/prannayag/pragnition/robotics/argus/src/perception/detector.py) — HIGH
- [Existing 2D→3D projection (median depth)](file:///home/prannayag/pragnition/robotics/argus/src/perception/detection_3d.py) — HIGH
- [Existing frontend box renderer](file:///home/prannayag/pragnition/robotics/argus/frontend/src/components/DetectionBoxes.ts) — HIGH
- [Isaac ROS Object Detection — graph-of-nodes pattern](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_object_detection/index.html) — HIGH
- [Isaac ROS Object Detection concepts + 3D bbox format](https://nvidia-isaac-ros.github.io/concepts/object_detection/index.html) — HIGH
- [Autoware Universe — detection_by_tracker](https://autowarefoundation.github.io/autoware_universe/main/perception/autoware_detection_by_tracker/) — HIGH
- [Autoware BEV perception roadmap (BEVDet, BEVFormer)](https://autoware.org/from-bevdet-to-bevformer/) — HIGH
- [BoxeR paper (CVPR 2022) — box-attention for 2D/3D transformers](https://arxiv.org/abs/2111.13087) — HIGH
- [facebook/detr-resnet-50 on HuggingFace](https://huggingface.co/facebook/detr-resnet-50) — HIGH
- [RT-DETR on HuggingFace](https://huggingface.co/docs/transformers/model_doc/rt_detr) — HIGH
- [ByteTrack introduction — IoU+Kalman tracker, CPU-friendly](https://datature.io/blog/introduction-to-bytetrack-multi-object-tracking-by-associating-every-detection-box) — HIGH
- [DeepSORT overview — CNN re-ID cost](https://learnopencv.com/understanding-multiple-object-tracking-using-deepsort/) — MEDIUM
- [Semantic SLAM survey — object-level data association, multi-robot fusion](https://www.sciencedirect.com/science/article/pii/S2667305325001176) — HIGH
- [Object SLAM papers list (curated)](https://github.com/520xyxyzq/awesome-object-SLAM) — MEDIUM
- [Hello Robot Stretch — confidence threshold + class filter per-camera pattern](https://docs.hello-robot.com/0.2/stretch-tutorials/ros2/deep_perception/) — MEDIUM
- [WildDet3D — 2D-to-3D lifting from any detector (Allen AI)](https://allenai.org/blog/wilddet3d) — MEDIUM (GPU-only, cited as anti-feature reference)
- [3D-MOOD — monocular open-set 3D from 2D](https://arxiv.org/html/2507.23567) — MEDIUM (GPU-only, cited as anti-feature reference)

---

*Feature research: 2026-04-13 — v3.0 Pluggable Perception & 3D Object Detection milestone*
