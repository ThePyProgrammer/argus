# Architecture Patterns

**Domain:** Generic SLAM API abstraction layer for multi-robot 3D reconstruction
**Researched:** 2026-03-23
**Confidence:** HIGH -- based on direct codebase analysis of 7,609 LOC Python + 2,486 LOC TypeScript and existing SLAM literature review (.research/)

## Recommended Architecture

### Design Principle: Strategy Pattern with Registry

The SLAM API abstraction is a **Strategy pattern** with a runtime-selectable backend, mediated by a **Registry** that maps string keys to backend factory functions. The abstraction layer sits between `ExplorationLoop` (consumer) and the concrete SLAM implementation (provider), replacing the current hard-wired `SLAMPipeline` class.

### Current Data Flow (v1.0)

```
MuJoCoBridge.step()
  -> SensorFrame (rgb, depth, ground_truth_pose, sim_time)
    -> SLAMPipeline.process_frame(frame) -> 4x4 pose
      -> OctoMapBuilder.insert_scan(last_frame_cloud, current_pos)
        -> MapMerger.merge_from_voxels() [on rescan event]
```

Key observations from codebase:
- `SLAMPipeline` is instantiated in `RobotInstance.create()` with only `intrinsics` arg
- `ExplorationLoop.__init__()` takes `slam: "SLAMPipeline"` (string type hint, not protocol)
- `Coordinator` accesses `robot.slam.slam_poses`, `robot.slam.last_frame_cloud`, `robot.slam.num_frames_processed`, `robot.slam.get_cloud_points()`, `robot.slam.get_cloud_colors()`
- `RobotInstance.get_cloud_data()` delegates to `self.slam.get_cloud_points()` and `self.slam.get_cloud_colors()`
- `ExplorationLoop._update_slam()` calls `self._slam.process_frame(frame)` and `self._slam.last_frame_cloud`

### Proposed Data Flow (v2.0)

```
MuJoCoBridge.step()
  -> SensorFrame (rgb, depth, ground_truth_pose, sim_time)
    -> SLAMBackend.process_frame(frame) -> SLAMResult(pose, cloud_points, cloud_colors, metrics)
      -> OctoMapBuilder.insert_scan(result.cloud_points, current_pos)
        -> PoseGraphMerger.add_pose(robot_id, result) [replaces MapMerger on rescan]
          -> PoseGraphMerger.optimize() -> corrected poses + merged map
```

## Component Boundaries

### New Components

| Component | File | Responsibility | Communicates With |
|-----------|------|---------------|-------------------|
| `SLAMProtocol` | `src/slam/protocol.py` | ABC defining the backend contract | All backends implement it |
| `SLAMResult` | `src/slam/protocol.py` | Immutable dataclass returned by every backend | ExplorationLoop, Coordinator, OctoMapBuilder, viz |
| `SLAMMetrics` | `src/slam/protocol.py` | Per-frame timing, fitness, inlier ratio | Stats streaming, frontend metrics panel |
| `SLAMRegistry` | `src/slam/registry.py` | Maps string keys to backend factories; validates config | RobotInstance.create(), Coordinator, WebSocket handler |
| `ICPBackend` | `src/slam/backends/icp_backend.py` | Wraps existing SLAMPipeline logic, implements SLAMProtocol | SLAMRegistry |
| `ORBBackend` | `src/slam/backends/orb_backend.py` | ORB-SLAM3 wrapper via subprocess/pybind | SLAMRegistry |
| `OpenVINSBackend` | `src/slam/backends/openvins_backend.py` | OpenVINS wrapper | SLAMRegistry |
| `SVOBackend` | `src/slam/backends/svo_backend.py` | SVO Pro wrapper | SLAMRegistry |
| `PoseGraphMerger` | `src/coordination/pose_graph_merger.py` | Replaces MapMerger; Open3D-based pose graph optimization | Coordinator |

### Modified Components

| Component | File | What Changes | Why |
|-----------|------|-------------|-----|
| `RobotInstance` | `src/coordination/robot_instance.py` | `slam: SLAMPipeline` -> `slam: SLAMProtocol`; factory takes `algorithm` param | Backend-agnostic robot pipeline |
| `ExplorationLoop` | `src/exploration/exploration_loop.py` | Type hint `SLAMPipeline` -> `SLAMProtocol`; use `SLAMResult` instead of direct property access | Decouples from ICP implementation |
| `Coordinator` | `src/coordination/coordinator.py` | Use `PoseGraphMerger` instead of `MapMerger`; forward algorithm-change commands; include metrics in viz data | Pose-graph merging + algorithm control |
| `WebStreamingViz` | `backend/web/streaming_viz.py` | Add `slam_metrics` message type; include algorithm name in stats | Frontend needs to display per-algorithm metrics |
| `server.py` | `backend/web/server.py` | Handle `set_algorithm` WS message type; forward to Coordinator | Frontend algorithm picker communication path |
| `main.py` | `src/main.py` | Use `SLAMRegistry` to resolve backend by name; pass to `RobotInstance.create()` | Entry point wiring |
| `robotStore.ts` | `frontend/src/stores/robotStore.ts` | Add `algorithm`, `slamMetrics` fields to `RobotInfo` | Display current algorithm and metrics |
| `controlStore.ts` | `frontend/src/stores/controlStore.ts` | Add `availableAlgorithms`, `activeAlgorithm`, `setAlgorithm` | Algorithm picker state |
| `useWebSocket.ts` | `frontend/src/hooks/useWebSocket.ts` | Handle `slam_algorithms` and `slam_metrics` message types | Route new messages to stores |
| `ControlPanel.tsx` | `frontend/src/components/ControlPanel.tsx` | Add algorithm picker dropdown (pre-session) | User-facing algorithm selection |

### Unchanged Components

| Component | Why Unchanged |
|-----------|--------------|
| `MuJoCoBridge` / `MultiRobotBridge` | Produces SensorFrames -- SLAM-agnostic |
| `OctoMapBuilder` | Consumes (N,3) point arrays -- format unchanged |
| `VoronoiPartitioner` | Uses poses from Coordinator -- source of pose is irrelevant |
| `pLCMTransport` (InProcessTransport) | Message transport -- payload-agnostic |
| `depth_to_cloud.py` | Only used by ICP backend internally |
| `CoverageTracker`, `FrontierDetector`, `GoalSelector`, `PathPlanner` | Consume OctoMap voxels, not SLAM output directly |

## SLAMProtocol Definition

The protocol is the single most important design decision. It must capture the union of what all four backends can produce while remaining minimal.

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import numpy as np
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame


@dataclass(frozen=True)
class SLAMMetrics:
    """Per-frame performance and quality metrics."""
    processing_time_ms: float = 0.0
    tracking_quality: float = 1.0     # 0.0=lost, 1.0=excellent
    num_features: int = 0             # tracked features this frame
    num_inliers: int = 0              # inliers after RANSAC/matching
    memory_mb: float = 0.0            # current memory usage


@dataclass(frozen=True)
class SLAMResult:
    """Immutable output from a single process_frame() call."""
    pose: np.ndarray                   # (4,4) float64 estimated pose
    cloud_points: np.ndarray           # (N,3) float64 points in world frame
    cloud_colors: np.ndarray           # (N,3) float64 RGB [0,1] or empty
    metrics: SLAMMetrics = field(default_factory=SLAMMetrics)
    keyframe: bool = False             # True if backend considers this a keyframe


@dataclass
class SLAMConfig:
    """Backend-specific configuration (base class)."""
    voxel_size: float = 0.03
    max_depth: float = 10.0


class SLAMProtocol(ABC):
    """Abstract base class for all SLAM backends."""

    @abstractmethod
    def initialize(self, intrinsics: CameraIntrinsics, config: SLAMConfig | None = None) -> None:
        """Set up the backend with camera parameters."""
        ...

    @abstractmethod
    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one RGB-D frame. Returns pose + cloud + metrics."""
        ...

    @abstractmethod
    def reset(self) -> None:
        """Clear all accumulated state."""
        ...

    @abstractmethod
    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (points, colors) of the accumulated global map."""
        ...

    @property
    @abstractmethod
    def poses(self) -> list[np.ndarray]:
        """All estimated poses so far."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend name (e.g. 'ICP', 'ORB-SLAM3')."""
        ...

    @property
    @abstractmethod
    def num_frames_processed(self) -> int:
        ...
```

**Design rationale:**

1. **`SLAMResult` instead of properties.** The current `SLAMPipeline` exposes `slam_poses`, `last_frame_cloud`, `get_cloud_points()` as separate properties. This couples consumers to ICP's internal state. `SLAMResult` bundles everything a consumer needs from one frame into a single immutable object.

2. **`cloud_points` in world frame.** The current ICP pipeline transforms points to world frame before returning (line 102 of slam_pipeline.py: `cloud.transform(self._current_pose)`). All backends must do the same -- consumers (OctoMapBuilder, viz) expect world-frame points.

3. **`metrics` on every result.** Enables live comparison dashboard without polling. Each backend populates what it can; defaults are zero.

4. **`keyframe` flag.** ORB-SLAM3 and SVO Pro have explicit keyframe concepts. The pose-graph merger needs keyframes for graph construction. For ICP, every Nth frame is synthetically marked as a keyframe.

5. **`initialize()` separate from `__init__`.** Backends like ORB-SLAM3 need a subprocess or shared library loaded -- this may fail. Separating init from construction allows the registry to construct, then initialize only the selected backend.

## SLAMRegistry Design

```python
_BACKEND_REGISTRY: dict[str, Callable[[], SLAMProtocol]] = {}

def register_backend(name: str, factory: Callable[[], SLAMProtocol]) -> None:
    _BACKEND_REGISTRY[name] = factory

def get_backend(name: str) -> SLAMProtocol:
    if name not in _BACKEND_REGISTRY:
        raise KeyError(f"Unknown SLAM backend: {name}. Available: {list(_BACKEND_REGISTRY.keys())}")
    return _BACKEND_REGISTRY[name]()

def available_backends() -> list[str]:
    return list(_BACKEND_REGISTRY.keys())
```

Each backend module self-registers on import:

```python
# src/slam/backends/icp_backend.py
from src.slam.registry import register_backend

class ICPBackend(SLAMProtocol):
    ...

register_backend("icp", ICPBackend)
```

Backend discovery at startup (`main.py`):

```python
import src.slam.backends.icp_backend  # always available

for backend_module in ["orb_backend", "openvins_backend", "svo_backend"]:
    try:
        importlib.import_module(f"src.slam.backends.{backend_module}")
        logger.info("Loaded SLAM backend: %s", backend_module)
    except ImportError as e:
        logger.info("SLAM backend %s not available: %s", backend_module, e)
```

## Frontend-Backend Communication for Algorithm Changes

### Pre-Session Algorithm Selection (Primary)

The algorithm is selected before the simulation starts or on restart. This avoids mid-run backend swapping complexity.

**Flow:**

```
1. Client connects to /ws
2. Server sends: {"type": "slam_algorithms", "payload": {"available": ["icp", "orb_slam3", "openvins", "svo_pro"], "active": "icp"}}
3. User selects algorithm in ControlPanel dropdown
4. Client sends: {"type": "set_algorithm", "algorithm": "orb_slam3"}
5. Server validates algorithm name against registry
6. Server stores selection on Coordinator._pending_algorithm
7. On next restart (existing restart mechanism in main.py _run_simulation_loop), Coordinator uses new algorithm
8. Server sends: {"type": "algorithm_ack", "payload": {"algorithm": "orb_slam3", "apply_on": "next_restart"}}
```

**Why pre-session, not hot-swap:** Each backend accumulates internal state (global map, pose chain, feature database). Swapping mid-run means the new backend starts with no history (pose chain breaks), the global cloud from the old backend is orphaned, and the OctoMap has mixed-quality data. Hot-swap as stretch goal would require: snapshot old backend state, reset OctoMap + merger, reinitialize new backend from ground-truth pose.

### WebSocket Message Types (New)

```typescript
// Server -> Client (on connect, alongside existing robot_list)
type SLAMAlgorithmsMessage = {
  type: "slam_algorithms";
  payload: {
    available: string[];
    active: string;
    params: Record<string, ParamDef[]>;  // per-algorithm tunable params
  };
};

// Server -> Client (piggybacks on existing 10-frame viz update cycle)
type SLAMMetricsMessage = {
  type: "slam_metrics";
  robot_id: string;
  payload: {
    processing_time_ms: number;
    tracking_quality: number;
    num_features: number;
    memory_mb: number;
    algorithm: string;
  };
};

// Client -> Server
type SetAlgorithmMessage = {
  type: "set_algorithm";
  algorithm: string;
};

type SetAlgorithmParamsMessage = {
  type: "set_algorithm_params";
  algorithm: string;
  params: Record<string, number | string | boolean>;
};
```

### Server-Side Handling

In `server.py._dispatch_ws_message()`, add alongside existing `set_cloud_config` handler:

```python
elif msg_type == "set_algorithm":
    algorithm = data.get("algorithm", "icp")
    if algorithm in available_backends():
        # Coordinator stores this; applied on next restart
        coordinator.set_pending_algorithm(algorithm)
        await websocket.send_json({
            "type": "algorithm_ack",
            "payload": {"algorithm": algorithm, "apply_on": "next_restart"},
        })
```

In `Coordinator`, the pending algorithm is consumed during the existing `reset_for_restart()` method, which is already called from `main.py._run_simulation_loop()` during restart:

```python
def reset_for_restart(self, bridge, robots):
    # ... existing reset logic (lines 237-252 of coordinator.py) ...
    # Apply pending algorithm to all robots
    if self._pending_algorithm:
        for rid, robot in robots.items():
            backend = get_backend(self._pending_algorithm)
            backend.initialize(intrinsics)
            robot.slam = backend
```

## Pose-Graph Optimization Replacing ICP Merging

### Current Merge Strategy (v1.0)

`MapMerger.merge_from_voxels()` does union-OR voxel fusion: stacks all robots' occupied voxels, deduplicates by grid index (line 109 of map_merger.py: `np.round(combined / self._resolution).astype(np.int64)`). No geometric alignment -- relies on all robots using ground-truth-seeded ICP poses in a shared world frame.

**Problem:** As the project's own research report documents: "ICP is wrong for sparse point clouds. Standard ICP struggles with the sparse outputs from feature-based SLAM." As drift accumulates without loop closure, two robots observing the same area will have misaligned overlapping regions that simple voxel union cannot correct.

### Proposed Merge Strategy (v2.0)

Replace `MapMerger` with `PoseGraphMerger` that:

1. **Builds a pose graph** from all robots' keyframe poses (nodes) and odometry transforms (edges)
2. **Detects inter-robot loop closures** when robots observe overlapping areas (FPFH descriptors for coarse matching, ICP for refinement)
3. **Optimizes the graph** using Open3D's `GlobalOptimization` to produce globally consistent poses
4. **Re-projects point clouds** using corrected poses, then voxel-deduplicates

```python
class PoseGraphMerger:
    """Replaces MapMerger with Open3D pose graph optimization."""

    def __init__(self, resolution: float = 0.1):
        self._resolution = resolution
        self._pose_graph = o3d.pipelines.registration.PoseGraph()
        self._keyframes: list[KeyframeData] = []
        self._last_merged_voxels: np.ndarray = np.empty((0, 3))

    def add_keyframe(self, robot_id: str, result: SLAMResult,
                     cloud_camera_frame: np.ndarray) -> None:
        """Add a keyframe node + odometry edge to the pose graph."""
        ...

    def detect_loop_closures(self) -> int:
        """Detect inter-robot loop closures via FPFH + ICP.
        Returns number of new loop closure edges."""
        ...

    def optimize(self) -> None:
        """Run Open3D GlobalOptimization (Levenberg-Marquardt)."""
        o3d.pipelines.registration.global_optimization(
            self._pose_graph,
            o3d.pipelines.registration.GlobalOptimizationLevenbergMarquardt(),
            o3d.pipelines.registration.GlobalOptimizationConvergenceCriteria(),
            option,
        )

    def get_merged_map(self) -> np.ndarray:
        """Re-project all keyframe clouds using optimized poses, voxel-deduplicate."""
        ...

    @property
    def last_merged_voxels(self) -> np.ndarray:
        """API-compatible with MapMerger for viz pipeline."""
        return self._last_merged_voxels
```

**Why Open3D's built-in PGO over external g2o:** The project already depends on Open3D. `open3d.pipelines.registration.GlobalOptimization` provides Levenberg-Marquardt pose graph optimization without adding a C++ dependency (g2o requires CMake build). If Open3D PGO proves insufficient for large graphs, `g2opy` is the fallback.

### Integration with Coordinator

The merge trigger point in `Coordinator.run()` (line 466 of coordinator.py) changes:

```python
# v1.0 (current):
if any_rescan_triggered:
    self._merge_occupancy_maps(robot_ids)

# v2.0 (proposed):
if any_rescan_triggered:
    for rid in robot_ids:
        robot = self._robots[rid]
        result = robot.last_slam_result
        if result and result.keyframe:
            self._pose_graph_merger.add_keyframe(rid, result, ...)
    closures = self._pose_graph_merger.detect_loop_closures()
    if closures > 0:
        self._pose_graph_merger.optimize()
    self._pose_graph_merger.update_merged_map()
```

The `last_merged_voxels` property on `PoseGraphMerger` is API-compatible with `MapMerger`, so `_send_viz_update()` (line 617 of coordinator.py: `merged_voxels=self._merger.last_merged_voxels`) works unchanged.

## Patterns to Follow

### Pattern 1: Backend Wrapper with Subprocess Isolation

ORB-SLAM3, OpenVINS, and SVO Pro are C++ codebases. Use subprocess communication for initial integration because:
- No CMake/build system coupling with the Python project
- Crash in C++ SLAM does not crash the Python process
- Easier to develop and test independently
- Each backend can be installed independently (nix, apt, or manual build)

```python
class ORBBackend(SLAMProtocol):
    """ORB-SLAM3 backend via subprocess communication."""

    def initialize(self, intrinsics, config=None):
        self._write_config_yaml(intrinsics, config)
        self._process = subprocess.Popen(
            ["orb_slam3_rgbd", str(vocab_path), str(config_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )

    def process_frame(self, frame):
        # Write depth + rgb to shared memory or named pipe
        # Read pose (4x4) + sparse points from stdout
        ...
```

**Upgrade path:** Replace subprocess with pybind11 wrapper once the interface is stable and performance needs to be optimized.

### Pattern 2: Graceful Degradation on Missing Backends

Not all backends will be installed on every machine. The system must work with only the ICP backend.

```python
# In main.py startup
import src.slam.backends.icp_backend  # always available (pure Python + Open3D)

for name in ["orb_backend", "openvins_backend", "svo_backend"]:
    try:
        importlib.import_module(f"src.slam.backends.{name}")
    except ImportError as e:
        logger.info("SLAM backend %s not available: %s", name, e)
```

The frontend algorithm picker only shows backends from `available_backends()`, so missing C++ backends do not cause UI errors.

### Pattern 3: Consistent Coordinate Frames

All backends MUST output poses and points in the **MuJoCo world frame** (Z-up, right-handed). The existing ICP backend seeds from `frame.ground_truth_pose` which is already in world frame (line 71 of slam_pipeline.py). External backends use their own coordinate conventions and need a transform in the wrapper:

```python
def _to_world_frame(self, slam_pose: np.ndarray) -> np.ndarray:
    return self._world_from_slam @ slam_pose
```

### Pattern 4: SLAMResult Caching on RobotInstance

Store the latest `SLAMResult` on the robot instance so Coordinator and viz can access metrics without re-querying the backend:

```python
# In ExplorationLoop._update_slam():
result = self._slam.process_frame(frame)
self._last_slam_result = result  # cached for external access

# In RobotInstance:
@property
def last_slam_result(self) -> SLAMResult | None:
    return self.exploration._last_slam_result
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Leaking Backend State Through the Protocol

**What:** Adding backend-specific properties to `SLAMProtocol` (e.g., `orb_features`, `vins_imu_state`).
**Why bad:** Every consumer needs backend-aware code paths. Defeats the abstraction.
**Instead:** Put everything in `SLAMResult.metrics` and `SLAMResult.cloud_points/cloud_colors`. Backend-specific debug info goes in logging.

### Anti-Pattern 2: Hot-Swapping Without State Reset

**What:** Changing algorithm mid-run and feeding frames to new backend without clearing accumulated state.
**Why bad:** New backend has no pose history. First frame produces identity/ground-truth pose, creating a discontinuity. OctoMap has mixed-quality data.
**Instead:** Algorithm changes take effect on restart. The existing `Coordinator.reset_for_restart()` already clears all state (line 237 of coordinator.py).

### Anti-Pattern 3: Blocking the Simulation Loop with Heavy Backends

**What:** Calling a slow backend's `process_frame()` synchronously in the coordinator loop.
**Why bad:** ORB-SLAM3 can take 30-50ms per frame. The current loop runs as fast as possible (~200fps for ICP).
**Instead:** For slow backends, consider async processing: queue frames, return last known pose immediately, update when result arrives. Start synchronous, measure, optimize if needed. The existing `step_delay` in MultiRobotConfig provides a natural throttle point.

### Anti-Pattern 4: Dual Merge Paths

**What:** Running both `MapMerger` (voxel union) and `PoseGraphMerger` simultaneously.
**Why bad:** Confusing code, unclear which merged map is authoritative, double memory.
**Instead:** `PoseGraphMerger` replaces `MapMerger`. For the ICP backend (no native keyframes), treat every Nth frame as a synthetic keyframe.

## Integration Point Details (Exact Lines)

### 1. RobotInstance.create() (line 86-119 of robot_instance.py)

Current:
```python
slam = SLAMPipeline(intrinsics)
```

Proposed:
```python
slam = get_backend(algorithm)  # algorithm: str param, default "icp"
slam.initialize(intrinsics, config)
```

The `algorithm` parameter flows from: CLI `--algorithm` arg -> `MultiRobotConfig` -> `RobotInstance.create()`. On restart, from `Coordinator._pending_algorithm`.

### 2. ExplorationLoop._update_slam() (line 192-207 of exploration_loop.py)

Current:
```python
pose = self._slam.process_frame(frame)
current_pos = pose[:3, 3].copy()
frame_cloud = self._slam.last_frame_cloud
```

Proposed:
```python
result = self._slam.process_frame(frame)
pose = result.pose
current_pos = pose[:3, 3].copy()
frame_cloud = result.cloud_points
self._last_slam_result = result  # cached for Coordinator
```

### 3. Coordinator._send_viz_update() (line 559-624 of coordinator.py)

Add `slam_metrics` and `algorithm` to `RobotVizData`:
```python
robot_data[rid] = RobotVizData(
    ...,
    slam_metrics=robot.last_slam_result.metrics if robot.last_slam_result else None,
    algorithm=robot.slam.name,
)
```

### 4. server.py websocket_endpoint (line 112-158 of server.py)

On connect, send available algorithms alongside existing `robot_list` and `cloud_configs`:
```python
await websocket.send_json({
    "type": "slam_algorithms",
    "payload": {
        "available": available_backends(),
        "active": coordinator.current_algorithm,
    },
})
```

### 5. useWebSocket.ts handleTextMessage (line 64-143 of useWebSocket.ts)

Add cases for new message types:
```typescript
case 'slam_algorithms': {
    const payload = msg.payload as { available: string[]; active: string };
    useControlStore.getState().setAlgorithms(payload.available, payload.active);
    break;
}
case 'slam_metrics': {
    const payload = msg.payload as SLAMMetricsPayload;
    if (msg.robot_id) {
        useRobotStore.getState().updateSLAMMetrics(msg.robot_id, payload);
    }
    break;
}
```

## Build Order (Dependency-Aware)

### Phase 1: Protocol + Registry + ICP Backend Refactor
**Creates:** `protocol.py`, `registry.py`, `backends/icp_backend.py`
**Modifies:** `RobotInstance`, `ExplorationLoop` (type hints + SLAMResult usage)
**Test:** All existing tests pass with ICP backend resolved via registry
**Rationale:** Foundation. Everything depends on the protocol being right. The ICP backend is a pure refactor of existing `SLAMPipeline` -- no new functionality, no risk.

### Phase 2: Frontend Algorithm Picker + WS Messages
**Creates:** New WS message types, `AlgorithmPicker` component in ControlPanel
**Modifies:** `server.py`, `useWebSocket.ts`, `controlStore.ts`, `ControlPanel.tsx`
**Test:** Frontend shows algorithm dropdown, sends `set_algorithm`, receives ack. Only ICP available but plumbing works.
**Rationale:** Establishes end-to-end communication path. Can test with only ICP.

### Phase 3: Pose-Graph Merger
**Creates:** `pose_graph_merger.py`
**Modifies:** `Coordinator` (swap merger reference)
**Test:** Two-robot run produces optimized merged map; compare quality vs v1.0 voxel union
**Rationale:** Merge strategy is orthogonal to new backends. Doing it before adding backends means every backend benefits from day one.

### Phase 4: ORB-SLAM3 Backend
**Creates:** `backends/orb_backend.py`, build script, config YAML templates
**Modifies:** Nothing (self-registers via import)
**Test:** Single robot ORB-SLAM3 run; compare ATE vs ICP baseline
**Rationale:** Most mature C++ backend; best first candidate for subprocess wrapper pattern.

### Phase 5: OpenVINS + SVO Pro Backends
**Creates:** `backends/openvins_backend.py`, `backends/svo_backend.py`
**Test:** Each backend runs single-robot; metrics comparison across all backends
**Rationale:** Same wrapper pattern as ORB-SLAM3. These two can be developed in parallel.

### Phase 6: Live Metrics Dashboard + Comparison Panel
**Creates:** `MetricsPanel.tsx`, metrics comparison view
**Modifies:** `robotStore.ts`, `Sidebar.tsx`
**Test:** Side-by-side metrics (processing time, tracking quality, features, memory) visible
**Rationale:** Last because it needs real metrics data from multiple backends to be meaningful.

## Scalability Considerations

| Concern | 2 robots (current) | 4 robots | 8+ robots |
|---------|-------------------|----------|-----------|
| Backend memory | 2x backend memory (~200MB for ICP) | 4x -- may need lighter backends (SVO Pro) | Memory-constrained; must profile |
| Pose graph size | ~100 nodes/run | ~200 nodes | Sliding window, prune old nodes |
| Loop closure detection | O(N^2) pairwise keyframe comparison | Becomes bottleneck at ~500 keyframes | Use DBoW2 visual vocabulary for O(1) lookup |
| Merge frequency | On rescan (~every 50 steps) | Same trigger, more data per merge | Incremental merge; avoid full re-merge |
| WebSocket bandwidth | ~50KB/s cloud delta + metrics | ~100KB/s | Subsample or paginate cloud updates |

## Directory Structure After v2.0

```
src/slam/
  __init__.py
  protocol.py          # SLAMProtocol, SLAMResult, SLAMMetrics, SLAMConfig
  registry.py          # register_backend(), get_backend(), available_backends()
  depth_to_cloud.py    # unchanged, used internally by ICP backend
  octomap_builder.py   # unchanged
  slam_pipeline.py     # DEPRECATED -- kept for reference, replaced by icp_backend
  backends/
    __init__.py
    icp_backend.py     # wraps existing SLAMPipeline logic
    orb_backend.py     # ORB-SLAM3 subprocess wrapper
    openvins_backend.py
    svo_backend.py

src/coordination/
  pose_graph_merger.py  # NEW -- replaces map_merger.py
  map_merger.py         # DEPRECATED -- kept as fallback reference
  ... existing files unchanged ...

backend/web/
  server.py            # +set_algorithm handler, +slam_algorithms on connect
  streaming_viz.py     # +slam_metrics message type
  message_types.py     # +SLAM_ALGORITHMS, SLAM_METRICS constants

frontend/src/
  stores/
    controlStore.ts    # +algorithms state
    robotStore.ts      # +slamMetrics per robot
  hooks/
    useWebSocket.ts    # +slam_algorithms, slam_metrics handlers
  components/
    ControlPanel.tsx   # +AlgorithmPicker dropdown
    MetricsPanel.tsx   # NEW -- live SLAM metrics comparison
```

## Sources

- Direct codebase analysis: `src/slam/slam_pipeline.py` (157 lines), `src/coordination/coordinator.py` (625 lines), `src/coordination/robot_instance.py` (119 lines), `src/coordination/map_merger.py` (152 lines), `src/exploration/exploration_loop.py` (491 lines), `backend/web/server.py` (187 lines), `backend/web/streaming_viz.py` (372 lines), `frontend/src/stores/robotStore.ts` (219 lines), `frontend/src/hooks/useWebSocket.ts` (180 lines)
- Project SLAM literature review: `.research/report.md` -- 40+ methods evaluated, HIGH confidence
- ICP merge compatibility analysis: `.research/findings/axis-4-icp-merge-compatibility.md` -- HIGH confidence
- Open3D pose graph optimization: `open3d.pipelines.registration.GlobalOptimization` (available in project's existing Open3D dependency)
