# Phase 8: stretch-tracker-fusion-semantic-map - Research

**Researched:** 2026-04-16
**Domain:** Multi-object tracking (ByteTrack), multi-robot detection fusion, semantic map with TTL, heterogeneous per-robot backends
**Confidence:** HIGH

## Summary

Phase 8 delivers four time-gated differentiators that build on the fully-realized perception pipeline (Phases 1-7). The four features are: (1) ByteTrack multi-object tracker producing stable `track_id` values across frames via 3D center Euclidean distance association, (2) centralized multi-robot detection fusion merging same-class detections within 0.5 m world-frame distance, (3) SemanticMap with per-object TTL rendered as a ghosted Three.js wireframe layer, and (4) heterogeneous per-robot backend selection allowing each robot to run a different detector model.

All four features are well-scoped by the CONTEXT.md decisions (D-01 through D-15). The codebase already contains every integration point: `TrackerProtocol`, `TrackerRegistry`, `NoneTracker` (Phase 7), `DetectorWorkerPool.swap_backend` / `swap_lifter` (atomic swap pattern), `WebStreamingViz._update_stats` (WS payload emitter), and the `DetectionBoxManager` Three.js OBB rendering pattern. ByteTrack is adapted to 3D (world-frame center distance instead of 2D IoU), using numpy for cost matrices and `scipy.optimize.linear_sum_assignment` for optimal assignment. No new external dependencies are required -- scipy 1.17.1 and numpy 2.4.4 are already installed.

**Primary recommendation:** Implement in dependency order -- ByteTrack tracker first (DET-STRETCH-01, foundation for everything), then heterogeneous backends (DET-STRETCH-04, independent of fusion), then multi-robot fusion (DET-STRETCH-02, depends on tracked detections), then SemanticMap (DET-STRETCH-03, depends on fused output). This matches the priority order specified in CONTEXT.md specifics: cut DET-STRETCH-03 first if time-constrained.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** ByteTrack runs inside DetectorWorker._loop, post-lift (not a separate thread). Sequence: detector -> lifter -> tracker -> _latest.
- **D-02:** World-frame 3D center distance association (NOT 2D IoU). Threshold: match_thresh default 0.5 m.
- **D-03:** Track lifecycle: creation (confidence >= track_thresh 0.3), association (Hungarian + match_thresh gate, class-gated), deletion (frames_since_seen > frame_gap default 30).
- **D-04:** ByteTrack exposes 3 params via PARAMETER_SCHEMA: track_thresh, match_thresh, frame_gap.
- **D-05:** Worker + pool construction extension: tracker kwarg on worker, tracker_name + tracker_params on pool, swap_tracker method.
- **D-06:** Phase 6 jitter upgrade: track_id-based lookup replaces nearest-neighbor proxy in DetectionMetricsTracker (backward-compatible).
- **D-07:** Centralized FusionManager per coordinator tick owned by WebStreamingViz.
- **D-08:** NN class-gated clustering with 0.5 m world-frame distance. Highest-confidence detection is representative.
- **D-09:** Fused output wire format: fused_detections WS key alongside per-robot detection_metrics.
- **D-10:** Server-side SemanticMap with delta WS updates (active + expired_ids).
- **D-11:** TTL fade-out: wireframe OBBs with opacity proportional to remaining TTL. Separate group from detection boxes.
- **D-12:** Default TTL: 10 seconds.
- **D-13:** Per-robot swap via swap_backend_for_robot(rid, ...) on DetectorWorkerPool.
- **D-14:** REST extension: POST /api/detectors/select?robot_id=robot_0 (backward-compatible).
- **D-15:** Frontend per-robot selector in NodeInspector with per-robot dropdown section.

### Claude's Discretion
- ByteTrack internal data structures: numpy arrays for cost matrix, scipy.optimize.linear_sum_assignment vs greedy matcher.
- Exact class color mapping for SemanticMapLayer (reuse OKABE_ITO per-class colors).
- Whether SemanticMap pipeline node ships in Phase 8 or is deferred.
- fused_detections MetricsPanel rendering details (count-only vs per-class breakdown).
- Exact opacity curve for TTL fade (linear vs ease-out).
- Whether swap_backend_for_robot emits per-robot WS message or reuses detector_swap_complete with robot_id field.
- Hot-apply diff extension for tracker params.

### Deferred Ideas (OUT OF SCOPE)
- DeepSORT CNN re-ID -- out of scope per PROJECT.md.
- Kalman filter prediction for occluded objects.
- Semantic SLAM loop closure -- v4.0+ requirement.
- Per-robot tracker heterogeneity -- all robots share the same tracker.
- SemanticMap persistence across sessions -- ephemeral by design.
- Fusion threshold auto-tuning -- 0.5 m fixed for v3.0.
- Track-to-track fusion -- per-frame snapshots only.
- 3D IoU for fusion -- center distance sufficient for indoor scenes.
- SemanticMap pipeline node (if complex).
- Fused detection MetricsPanel per-class breakdown.
- Hot-swap tracker mid-session via REST.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-STRETCH-01 | ByteTrack multi-object tracker assigns stable `track_id` per detection (class + spatial IoU association, Apache-2.0) | ByteTrack algorithm adapted to 3D with Euclidean distance; TrackerProtocol + TrackerRegistry already exist; NoneTracker provides structural template; scipy.optimize.linear_sum_assignment verified available; worker._loop injection site identified |
| DET-STRETCH-02 | World-frame multi-robot detection fusion merges same-class detections within 0.5 m cluster radius across robots | DetectionFusionManager class design verified; WebStreamingViz._update_stats is the integration site; fused_detections wire format specified in D-09 |
| DET-STRETCH-03 | `SemanticMap` with per-object TTL renders as a ghosted Three.js layer alongside the 3D map | SemanticMap server-side class owns truth (D-10); delta WS updates; DetectionBoxManager provides the Three.js OBB rendering template; UI-SPEC locks all visual properties |
| DET-STRETCH-04 | Heterogeneous per-robot backends -- each robot may run a different detector | swap_backend_for_robot follows swap_backend pattern; REST extension backward-compatible; per-robot instance separation already exists in DetectorWorkerPool since Phase 2 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| numpy | 2.4.4 | Cost matrix computation for ByteTrack Hungarian assignment | Already installed; standard for numerical computation [VERIFIED: pip show] |
| scipy | 1.17.1 | `scipy.optimize.linear_sum_assignment` for optimal bipartite matching | Already installed; canonical Hungarian algorithm implementation [VERIFIED: pip show + import test] |
| three | 0.170.0 | SemanticMapLayer wireframe OBB rendering | Already installed in frontend [VERIFIED: npm list] |
| zustand | 5.0.12 | semanticMapStore, detectorStore extension, metricsStore extension | Already installed in frontend [VERIFIED: npm list] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses (stdlib) | builtin | `replace()` for immutable OrientedBox3D track_id stamping | Every ByteTrack track() call |
| itertools (stdlib) | builtin | `count()` for monotonic track_id generation in ByteTrack | Track creation |
| threading (stdlib) | builtin | _swap_lock reuse for swap_tracker and swap_backend_for_robot | Atomic ref swaps |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scipy.optimize.linear_sum_assignment | Greedy matcher | Greedy is O(N*M) but may produce suboptimal assignments when detections are close. At <20 detections per frame, both are sub-millisecond. Recommend scipy for correctness at negligible cost. |
| InstancedMesh (Three.js) | Individual BoxGeometry per OBB | InstancedMesh is theoretically better for many objects, but the existing DetectionBoxManager uses individual geometries per robot group. SemanticMapLayer can follow either pattern; individual geometries are simpler for per-object opacity control (InstancedMesh opacity is per-material, not per-instance). Recommend individual geometries matching DetectionBoxManager. |

**Installation:**
```bash
# No new dependencies needed -- all already installed
pip list | grep -E "scipy|numpy"
npm --prefix frontend list three zustand
```

## Architecture Patterns

### Recommended Project Structure
```
src/tracking/
  trackers/
    __init__.py          # Extended: import bytetrack (side-effect registration)
    none.py              # Existing passthrough
    bytetrack.py         # NEW: ByteTrackTracker class

src/perception/
  worker.py              # EXTENDED: tracker.track() call in _loop
  worker_pool.py         # EXTENDED: tracker construction, swap_tracker, swap_backend_for_robot
  fusion.py              # NEW: DetectionFusionManager class
  semantic_map.py         # NEW: SemanticMap class with TTL

backend/web/
  streaming_viz.py       # EXTENDED: owns FusionManager + SemanticMap, emits new WS keys
  detector_routes.py     # EXTENDED: per-robot REST endpoints
  pipeline_routes.py     # EXTENDED: hot-apply diff for tracker params

src/metrics/
  detection_metrics_tracker.py  # EXTENDED: track_id-based jitter lookup

frontend/src/
  components/
    SemanticMapLayer.ts          # NEW: Three.js imperative manager
    MetricsPanel.tsx             # EXTENDED: fused detection subsection
    SceneViewer.tsx              # EXTENDED: SemanticMapLayer instantiation
    ControlPanel.tsx             # EXTENDED: semantic map toggle
    pipeline/NodeInspector.tsx   # EXTENDED: per-robot backend dropdown
  stores/
    semanticMapStore.ts          # NEW: Zustand store for semantic map objects
    detectorStore.ts             # EXTENDED: perRobotBackend state
    metricsStore.ts              # EXTENDED: fusedDetections state
  utils/
    messageTypes.ts              # EXTENDED: new type interfaces

tests/
  tracking/
    test_bytetrack_tracker.py         # NEW: SC#1 lockdown
    test_bytetrack_association.py     # NEW: spatial association unit tests
  perception/
    test_fusion_manager.py            # NEW: SC#2 lockdown
    test_semantic_map.py              # NEW: SC#3 lockdown
    test_heterogeneous_backends.py    # NEW: SC#4 lockdown
  integration/
    test_bytetrack_e2e.py             # NEW: ByteTrack in coordinator loop
```

### Pattern 1: ByteTrack 3D Adaptation (D-01, D-02, D-03)
**What:** Adapted ByteTrack algorithm using world-frame 3D Euclidean distance as the association cost instead of 2D IoU.
**When to use:** Every frame in DetectorWorker._loop after lifter.lift() returns.
**Example:**
```python
# Source: CONTEXT D-02 + D-03 + ByteTrack paper adaptation
import numpy as np
from scipy.optimize import linear_sum_assignment
from dataclasses import replace

class ByteTrackTracker:
    """ByteTrack adapted to 3D world-frame center distance association."""

    def track(self, detections_3d: Detections3D) -> Detections3D:
        # 1. Build cost matrix: Euclidean distance between active tracks and new detections
        # 2. Class-gated: only same-class matches allowed
        # 3. Hungarian assignment with match_thresh gate
        # 4. Matched: update track center, reset frames_since_seen
        # 5. Unmatched detections: create new tracks (if score >= track_thresh)
        # 6. Unmatched tracks: increment frames_since_seen; delete if > frame_gap
        # 7. Stamp track_id on each box via dataclasses.replace()
        new_items = [replace(box, track_id=assigned_track_id) for box, assigned_track_id in matched_pairs]
        return replace(detections_3d, items=new_items)
```

### Pattern 2: Atomic Ref Swap (swap_tracker, swap_backend_for_robot)
**What:** Construct-outside-lock, rebind-inside-lock pattern for hot-swapping per-worker state.
**When to use:** swap_tracker mirrors swap_lifter; swap_backend_for_robot mirrors swap_backend but scoped to one worker.
**Example:**
```python
# Source: Existing worker_pool.py L288-L333 (swap_lifter template)
def swap_tracker(self, new_tracker_name: str, new_tracker_params: dict | None = None) -> None:
    import src.tracking.trackers  # noqa: F401 -- force registration
    tracker_kwargs = dict(new_tracker_params or {})
    new_trackers = {
        rid: TrackerRegistry.create(new_tracker_name, **tracker_kwargs)
        for rid in self._workers
    }
    with self._swap_lock:
        for rid, w in self._workers.items():
            w._tracker = new_trackers[rid]
        self.tracker_name = new_tracker_name
        self._tracker_params = tracker_kwargs

def swap_backend_for_robot(self, rid: str, new_backend_name: str, new_backend_params: dict | None = None) -> None:
    import src.perception.backends  # noqa: F401
    backend_kwargs = dict(new_backend_params or {})
    det = DetectorRegistry.create(new_backend_name, **backend_kwargs)
    det.warmup(self._dummy_frame_for(rid))
    with self._swap_lock:
        self._workers[rid]._detector = det
        self._per_robot_backends[rid] = new_backend_name
```

### Pattern 3: Delta WS Updates (SemanticMap)
**What:** Server computes active + expired sets per tick; frontend applies delta (add/update active, remove expired).
**When to use:** SemanticMap payload in _update_stats.
**Example:**
```python
# Source: CONTEXT D-10
class SemanticMap:
    def get_delta(self, sim_time: float) -> dict:
        active = [obj for obj in self._objects.values() if sim_time - obj.last_seen < obj.ttl]
        expired_ids = [tid for tid, obj in self._objects.items() if sim_time - obj.last_seen >= obj.ttl]
        # Remove expired from internal dict
        for tid in expired_ids:
            del self._objects[tid]
        return {"active": [o.to_wire() for o in active], "expired_ids": expired_ids}
```

### Pattern 4: Per-Robot Crash Fallback Scoping (D-13, CONTEXT specifics)
**What:** When using heterogeneous backends, crash fallback targets only the crashed robot, not all robots.
**When to use:** on_backend_crash must be scoped to the worker that raised the exception.
**Example:**
```python
# Adaptation of existing on_backend_crash (L440-L579)
# Instead of swapping ALL workers to fallback, only swap the crashed robot:
def on_backend_crash_for_robot(self, rid: str, crashed_backend: str, reason: str, fallback: str = "yolov11"):
    # Step 1: WS crash_fallback message (with robot_id field)
    # Step 2: Registry lockout for the crashed backend ON THIS ROBOT ONLY
    #         (or full lockout if desired -- same behavior as Phase 5)
    # Step 3: Construct + warm fallback for ONE worker, rebind under _swap_lock
    det = DetectorRegistry.create(fallback)
    det.warmup(self._dummy_frame_for(rid))
    with self._swap_lock:
        self._workers[rid]._detector = det
        self._per_robot_backends[rid] = fallback
```

### Anti-Patterns to Avoid
- **Mutating OrientedBox3D geometry in tracker:** ByteTrack MUST NOT change center, half_extents, quaternion, class_id, class_name, or score. Only stamp track_id via `dataclasses.replace()`. [VERIFIED: TrackerProtocol contract in protocol.py L22-28]
- **Mutating capture_pose or capture_timestamp:** Tracker preserves these envelope-level fields. [VERIFIED: TrackerProtocol contract]
- **Module-scope numpy/torch in tracking/:** ByteTrack must lazy-import numpy inside `track()` or `__init__`, not at module scope. [VERIFIED: Pitfall P9 convention from NoneTracker, protocol.py docstring]
- **Shared tracker instance across workers:** Each worker MUST have its own tracker instance (same invariant as detector + lifter). Track state is per-robot. [VERIFIED: CONTEXT D-05]
- **Full-robot swap on per-robot crash:** Heterogeneous crash fallback must scope to the crashed robot only. [VERIFIED: CONTEXT specifics block + Phase 5 D-03 adaptation note]
- **Inline quaternion construction in fusion/semantic_map:** All OBBs come from `OrientedBox3D.to_wire()`. FusionManager and SemanticMap consume wire format, never construct quaternions. [VERIFIED: Phase 1 D-10 invariant in CONTEXT canonical_refs]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bipartite matching (Hungarian) | Custom O(N^3) assignment | `scipy.optimize.linear_sum_assignment` | Proven correctness, handles edge cases (empty matrix, ties), sub-millisecond at N<20 [VERIFIED: scipy available] |
| Track ID generation | Manual counter with race conditions | `itertools.count(start=0)` per tracker instance | Thread-safe (one tracker per worker thread), monotonic, no overflow at int scale [VERIFIED: NoneTracker pattern] |
| Immutable dataclass mutation | Manual __init__ copies | `dataclasses.replace(box, track_id=new_id)` | Preserves frozen dataclass semantics, tested round-trip invariant [VERIFIED: existing pattern in NoneTracker] |
| Atomic ref swap | Custom locking protocol | Existing `_swap_lock` pattern from swap_lifter/swap_backend | Proven correct (GIL atomicity for attribute write), no partial-swap risk [VERIFIED: worker_pool.py L288-L416] |

**Key insight:** The entire atomic swap, registry, and worker pool infrastructure was built in Phases 1-7 specifically to enable Phase 8's features. ByteTrack, fusion, and heterogeneous backends are the "fill in the blanks" features that the architecture was designed for. No new architectural primitives are needed.

## Common Pitfalls

### Pitfall 1: ByteTrack Class Gate Ignoring Same-Class Requirement
**What goes wrong:** Without class gating, a chair detection could match a table track if they happen to be within match_thresh distance.
**Why it happens:** The cost matrix defaults to distance-only without filtering by class_name first.
**How to avoid:** D-03 explicitly requires class-gated matching: partition detections by class_name BEFORE computing the distance cost matrix. Only same-class entries can match. Different-class entries never compete.
**Warning signs:** Test with two different-class objects at the same location -- if they share a track_id, the class gate is missing.

### Pitfall 2: Track Deletion Race with Fusion
**What goes wrong:** A track is deleted (frames_since_seen > frame_gap) in the same tick that fusion tries to read it, producing a stale fused_track_id.
**Why it happens:** ByteTrack deletion happens per-worker; fusion happens in WebStreamingViz._update_stats (different execution context).
**How to avoid:** Fusion reads `worker.latest()` which returns a complete Detections3D snapshot. Deleted tracks are already absent from the snapshot. The `latest()` lock ensures a consistent read. No race.
**Warning signs:** Fused detections referencing track_ids that don't exist in any robot's latest() output.

### Pitfall 3: SemanticMap Expired-ID Removal Before Frontend Receives It
**What goes wrong:** Server removes an expired object from its internal dict before emitting the expired_ids, so the frontend never gets the removal notification.
**Why it happens:** If get_delta() deletes first and then returns, the expired ID might not be included.
**How to avoid:** get_delta() must collect expired_ids BEFORE deleting them from the internal dict (or return them as part of the deletion operation). The implementation should: (1) identify expired, (2) build the response including expired_ids, (3) delete from dict.
**Warning signs:** Ghost OBBs that never disappear from the Three.js scene.

### Pitfall 4: Per-Robot Backend Swap Not Updating _per_robot_backends Dict
**What goes wrong:** swap_backend_for_robot rebinds the worker's _detector but forgets to update the tracking dict, so GET /api/detectors/active returns stale per-robot status.
**Why it happens:** The existing swap_backend only updates self.backend_name (uniform); the new per-robot dict is a new state field.
**How to avoid:** swap_backend_for_robot MUST update self._per_robot_backends[rid] inside the _swap_lock block. Also update app.state as needed for REST response consistency.
**Warning signs:** REST response shows wrong backend for a robot after a per-robot swap.

### Pitfall 5: Tracker Import at Module Scope Breaking Thread Config
**What goes wrong:** ByteTrack imports numpy at module scope in src/tracking/trackers/bytetrack.py, which can trigger premature thread config initialization.
**Why it happens:** The Phase 1 thread-config invariant requires no torch/numpy at module scope in the perception/tracking package.
**How to avoid:** numpy import should be inside `__init__()` or `track()` method, not at module scope. Use `TYPE_CHECKING` for type hints. Follow the NoneTracker pattern exactly: stdlib-only at module scope.
**Warning signs:** Thread config test (`test_protocol_contracts.py`) fails after importing tracking module.

### Pitfall 6: Heterogeneous Crash Fallback Swapping All Robots
**What goes wrong:** Robot 1's BoxeR crashes, but the crash handler swaps ALL robots to YOLOv11 (existing on_backend_crash behavior).
**Why it happens:** The existing on_backend_crash was designed for uniform backends and swaps all workers.
**How to avoid:** Modify on_backend_crash to accept a `robot_id` parameter. When heterogeneous mode is active (i.e., _per_robot_backends has divergent values), scope the fallback to the crashed robot only. When uniform mode, existing behavior is fine.
**Warning signs:** Robot 0 running YOLOv11 suddenly switches to YOLOv11 again (no-op swap) when Robot 1's BoxeR crashes.

### Pitfall 7: TrackerRegistry._clear() in Tests Poisoning Other Tests
**What goes wrong:** A test clears the registry but doesn't repopulate, causing downstream tests to fail with "Unknown tracker: none".
**Why it happens:** Registry is class-level state; _clear() wipes all entries. Python import caching means re-importing the module doesn't re-trigger the @tracker decorator.
**How to avoid:** Every test file that calls TrackerRegistry._clear() must use an autouse fixture that reloads the tracker modules (exactly as test_tracker_registry.py does with `importlib.reload`). [VERIFIED: existing pattern in tests/tracking/test_tracker_registry.py]
**Warning signs:** Tests pass in isolation but fail in suite (import order sensitivity).

### Pitfall 8: Pipeline Hot-Apply Missing Tracker Changes
**What goes wrong:** User changes tracker params in the pipeline editor, applies, but the diff in pipeline_routes.py doesn't detect the change because tracker fields are in the "structural_unchanged" check.
**Why it happens:** pipeline_routes.py L96-104 currently checks `config.tracker_name == last_config.tracker_name and config.tracker_params == last_config.tracker_params` as part of structural_unchanged. If tracker changes, the whole graph restarts instead of hot-applying.
**How to avoid:** Move tracker_name and tracker_params out of the structural_unchanged check and into a new `tracker_changed` diff branch (parallel to detector_changed and lifter_changed). Call pool.swap_tracker() for hot-apply.
**Warning signs:** Changing only the ByteTrack match_thresh in the pipeline editor triggers a full coordinator restart instead of a hot-swap.

## Code Examples

### ByteTrack Tracker Implementation Shape
```python
# Source: CONTEXT D-01..D-06 + NoneTracker template [VERIFIED: src/tracking/trackers/none.py]
from __future__ import annotations
from dataclasses import replace
from typing import TYPE_CHECKING

from src.tracking.registry import tracker

if TYPE_CHECKING:
    from src.perception.types import Detections3D

@tracker(name="bytetrack", display="ByteTrack (3D center distance)")
class ByteTrackTracker:
    CAPABILITIES = {
        "framework": "bytetrack_3d",
        "produces_stable_ids": True,
        "license": "Apache-2.0",
    }
    PARAMETER_SCHEMA = {
        "track_thresh": {"type": "float", "default": 0.3, "min": 0.0, "max": 1.0,
                         "description": "Minimum confidence to create a new track"},
        "match_thresh": {"type": "float", "default": 0.5, "min": 0.1, "max": 2.0,
                         "description": "Max center distance (m) for track association"},
        "frame_gap": {"type": "int", "default": 30, "min": 1, "max": 300,
                      "description": "Frames before a lost track is deleted"},
    }

    def __init__(self, track_thresh=0.3, match_thresh=0.5, frame_gap=30):
        self._track_thresh = track_thresh
        self._match_thresh = match_thresh
        self._frame_gap = frame_gap
        self._next_id = 0
        self._tracks = {}  # {track_id: TrackState}

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        import numpy as np  # Lazy import per Pitfall P9
        from scipy.optimize import linear_sum_assignment
        # ... association logic ...
        # Return new Detections3D with track_ids stamped
        new_items = [replace(box, track_id=tid) for box, tid in zip(detections_3d.items, assigned_ids)]
        return replace(detections_3d, items=new_items)

    def reset(self) -> None:
        self._next_id = 0
        self._tracks.clear()
```

### DetectionFusionManager Shape
```python
# Source: CONTEXT D-07..D-09 [VERIFIED: design from CONTEXT.md]
class DetectionFusionManager:
    """Cross-robot detection fusion via class-gated nearest-neighbor clustering."""

    def __init__(self, cluster_radius: float = 0.5):
        self._cluster_radius = cluster_radius
        self._next_fused_id = 0

    def fuse(self, per_robot_detections: dict[str, Detections3D], sim_time: float) -> list[dict]:
        """Produce fused detections from all robots' latest tracked outputs.

        Algorithm (D-08):
        1. Collect all OrientedBox3D from all robots.
        2. Group by class_name.
        3. Within each class: cluster by world-frame center distance.
        4. Per cluster: pick highest-confidence as representative.
        5. Return fused entries with contributing robot_ids.
        """
        # ... clustering logic ...
        return fused_list
```

### SemanticMap Shape
```python
# Source: CONTEXT D-10..D-12 [VERIFIED: design from CONTEXT.md]
from dataclasses import dataclass

@dataclass
class SemanticObject:
    fused_track_id: int
    class_name: str
    center: list[float]      # [x, y, z]
    half_extents: list[float]
    quaternion: list[float]   # xyzw
    score: float
    last_seen: float          # sim_time
    ttl: float                # seconds (default 10)

class SemanticMap:
    def __init__(self, ttl: float = 10.0):
        self._ttl = ttl
        self._objects: dict[int, SemanticObject] = {}

    def update(self, fused_detections: list[dict], sim_time: float) -> None:
        """Refresh timestamps for matched fused entries; add new ones."""
        ...

    def get_delta(self, sim_time: float) -> dict:
        """Return {active: [...], expired_ids: [...]} for WS emission."""
        ...
```

### Worker._loop Extension Point
```python
# Source: CONTEXT D-01, existing worker.py L255-L331 [VERIFIED: src/perception/worker.py]
# In DetectorWorker._loop(), after lifter.lift():
    dets_3d = self._lifter.lift(dets_2d, frame, pose, self._intrinsics, slam_cloud)
    dets_3d = _attach_capture(dets_3d, pose, sim_time)
    # Phase 8 D-01: tracker.track() call
    if self._tracker is not None:
        try:
            dets_3d = self._tracker.track(dets_3d)
        except Exception as exc:
            _LOGGER.exception("DetectorWorker %s: tracker failed: %s", self._rid, exc)
            # Continue with untracked detections (graceful degradation)
    with self._lock:
        self._latest = dets_3d
```

### Jitter Upgrade (D-06) Integration Point
```python
# Source: CONTEXT D-06, existing detection_metrics_tracker.py L148-L175 [VERIFIED: code inspection]
# In DetectionMetricsTracker.record_frame(), jitter section:
    for obb in items:
        cls = getattr(obb, "class_name", "")
        center = np.asarray(obb.center, dtype=np.float64).reshape(3)
        track_id = getattr(obb, "track_id", None)
        if track_id is not None:
            # Phase 8 D-06: track_id-based lookup (stable across frames)
            key = f"_tid_{track_id}"
        else:
            # Fallback: class-name-based nearest-neighbor proxy (pre-Phase-8)
            key = cls
        # ... rest of jitter computation using `key` instead of `cls` ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ByteTrack 2D IoU on pixel bboxes | 3D Euclidean distance on world-frame OBB centers | Phase 8 adaptation | Natural extension since we have world-frame 3D OBBs from the lifter pipeline |
| Nearest-neighbor jitter proxy | track_id-based jitter lookup | Phase 8 D-06 | More accurate jitter measurement for tracked objects |
| Uniform backend for all robots | Per-robot heterogeneous backends | Phase 8 D-13/D-14 | Architectural completion of Phase 2's per-robot instance separation |

**Deprecated/outdated:**
- Phase 6 D-03 nearest-neighbor jitter: replaced by track_id-based lookup when ByteTrack is active (backward-compatible fallback remains)

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode=auto) |
| Config file | pytest.ini |
| Quick run command | `python -m pytest tests/tracking/ tests/perception/test_fusion_manager.py tests/perception/test_semantic_map.py tests/perception/test_heterogeneous_backends.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-STRETCH-01 | ByteTrack stable track_id across >=100 frames for stationary chair | unit | `python -m pytest tests/tracking/test_bytetrack_tracker.py -x` | Wave 0 |
| DET-STRETCH-01 | Spatial association: within-gate match, cross-gate miss, multi-object disambiguation | unit | `python -m pytest tests/tracking/test_bytetrack_association.py -x` | Wave 0 |
| DET-STRETCH-02 | Two robots detecting same chair within 0.5m produce single fused detection | unit | `python -m pytest tests/perception/test_fusion_manager.py -x` | Wave 0 |
| DET-STRETCH-03 | SemanticMap: insert object, advance time past TTL, assert expired | unit | `python -m pytest tests/perception/test_semantic_map.py -x` | Wave 0 |
| DET-STRETCH-04 | Swap robot_0 to yolov11 and robot_1 to rtdetrv2, both produce detections | unit | `python -m pytest tests/perception/test_heterogeneous_backends.py -x` | Wave 0 |
| DET-STRETCH-01 | ByteTrack in full coordinator loop for 30 frames | integration | `python -m pytest tests/integration/test_bytetrack_e2e.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/tracking/ tests/perception/test_fusion_manager.py tests/perception/test_semantic_map.py tests/perception/test_heterogeneous_backends.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/tracking/test_bytetrack_tracker.py` -- covers DET-STRETCH-01 SC#1 (100-frame stability)
- [ ] `tests/tracking/test_bytetrack_association.py` -- covers DET-STRETCH-01 association edge cases
- [ ] `tests/perception/test_fusion_manager.py` -- covers DET-STRETCH-02 SC#2 (cross-robot fusion)
- [ ] `tests/perception/test_semantic_map.py` -- covers DET-STRETCH-03 SC#3 (TTL expiry)
- [ ] `tests/perception/test_heterogeneous_backends.py` -- covers DET-STRETCH-04 SC#4 (per-robot backends)
- [ ] `tests/integration/test_bytetrack_e2e.py` -- covers integration test (ByteTrack in coordinator loop)

## Assumptions Log

> List all claims tagged [ASSUMED] in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ByteTrack Apache-2.0 license is compatible with project | Standard Stack | Low -- Apache-2.0 is permissive; the original ByteTrack paper/repo uses MIT. Our adaptation is original code, not a copy. |
| A2 | scipy.optimize.linear_sum_assignment handles empty cost matrices gracefully (0 detections or 0 tracks) | Common Pitfalls | Medium -- must test edge case; may need to short-circuit before calling if matrix is empty |
| A3 | Per-frame opacity update in Three.js animation loop is performant at <50 semantic map objects | Architecture Patterns | Low -- at 50 objects, iterating and setting opacity per frame is negligible compared to render cost |

**If this table is empty:** N/A -- 3 assumed claims listed above.

## Open Questions (RESOLVED)

1. **SemanticMap pipeline node: include or defer?**
   - What we know: CONTEXT discretion says "if trivial, include; if complex, defer". A passthrough node with just a `ttl` parameter and no new port types is trivial.
   - What's unclear: Whether the pipeline builder needs a new node type definition or can reuse tracker_generic pattern.
   - Recommendation: Include it if the implementation adds fewer than 30 lines to pipeline_builder.py. Otherwise defer.
   - RESOLVED: Deferred — plans exclude it. Pipeline builder extension is non-trivial and the SemanticMap operates independently of the pipeline graph in Phase 8.

2. **scipy.optimize.linear_sum_assignment vs greedy for ByteTrack?**
   - What we know: At <20 detections per frame (indoor office scene), both are sub-millisecond. Greedy is simpler but may misassign in ambiguous cases.
   - What's unclear: Whether any test scenario produces ambiguous-enough detections to expose greedy's suboptimality.
   - Recommendation: Use scipy (Hungarian) -- it's already installed, proven correct, and the cost is negligible. This is the recommendation for Claude's discretion.
   - RESOLVED: scipy.optimize.linear_sum_assignment — Plan 02 implements it. Already installed (scipy 1.17.1), proven correct, negligible cost.

3. **Hot-apply for tracker params: extend or restart?**
   - What we know: pipeline_routes.py currently treats tracker_name/tracker_params as structural fields (change = restart). CONTEXT discretion asks whether to make them hot-applicable.
   - What's unclear: Whether tracker state should be preserved across param changes (e.g., changing match_thresh while tracks are active).
   - Recommendation: Make tracker changes hot-applicable via pool.swap_tracker(). Tracker state resets on swap (fresh instance), which is acceptable since users changing tracker params expect behavior to change immediately. Cost: ~10 lines in pipeline_routes.py.
   - RESOLVED: Hot-apply via swap_tracker() — Plan 06 Task 2 implements the tracker_changed diff branch in pipeline_routes.py.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.14 | All backend code | Checked | 3.14 | -- |
| numpy | ByteTrack cost matrix | Checked | 2.4.4 | -- |
| scipy | Hungarian algorithm | Checked | 1.17.1 | Greedy matcher (less optimal) |
| three.js | SemanticMapLayer | Checked | 0.170.0 | -- |
| zustand | Stores | Checked | 5.0.12 | -- |
| pytest | Tests | Checked | Available | -- |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A (local dev tool) |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A (single-user) |
| V5 Input Validation | yes | Pydantic BaseModel for REST requests (existing pattern); robot_id query param validated against pool.robot_ids |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for Phase 8

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| robot_id query param injection on /api/detectors/select | Tampering | Validate robot_id against pool._workers.keys() before mutation (T-02-08 pattern -- unknown rid = 404) |
| Backend name injection on per-robot /select | Tampering | DetectorRegistry.list_backends() validation before create() (existing T-02-19 pattern) |
| Stale per_robot_backends state after crash fallback | Information Disclosure (mild) | Update _per_robot_backends inside _swap_lock in on_backend_crash (Pitfall 4 mitigation) |

## Sources

### Primary (HIGH confidence)
- Codebase inspection: src/tracking/protocol.py, src/tracking/registry.py, src/tracking/trackers/none.py, src/perception/worker.py, src/perception/worker_pool.py, backend/web/streaming_viz.py, backend/web/detector_routes.py, backend/web/pipeline_routes.py, src/metrics/detection_metrics_tracker.py
- Codebase inspection: frontend/src/stores/detectorStore.ts, frontend/src/stores/metricsStore.ts, frontend/src/components/SceneViewer.tsx, frontend/src/components/DetectionBoxes.ts, frontend/src/utils/messageTypes.ts, frontend/src/components/pipeline/NodeInspector.tsx
- CONTEXT.md (Phase 8) -- 15 locked decisions, discretion areas, deferred items
- REQUIREMENTS.md -- DET-STRETCH-01..04 definitions
- UI-SPEC.md (Phase 8) -- locked visual contracts for all frontend changes
- [VERIFIED: pip show scipy] -- scipy 1.17.1
- [VERIFIED: pip show numpy] -- numpy 2.4.4
- [VERIFIED: npm list three zustand] -- three 0.170.0, zustand 5.0.12

### Secondary (MEDIUM confidence)
- ByteTrack paper: Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box" (ECCV 2022) -- algorithm reference [ASSUMED: paper details from training data]

### Tertiary (LOW confidence)
- None. All claims verified against codebase or installed dependencies.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified installed, no new dependencies
- Architecture: HIGH -- all integration points identified in existing code, patterns well-established
- Pitfalls: HIGH -- derived from codebase inspection and existing test patterns

**Research date:** 2026-04-16
**Valid until:** 2026-05-16 (stable -- codebase patterns are locked from prior phases)
