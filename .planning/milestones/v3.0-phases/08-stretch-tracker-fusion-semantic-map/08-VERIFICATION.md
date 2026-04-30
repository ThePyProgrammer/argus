---
phase: 08-stretch-tracker-fusion-semantic-map
verified: 2026-04-16T13:50:00Z
status: human_needed
score: 3/4 must-haves verified (SC#3 and SC#4 partial — human visual confirmation required)
overrides_applied: 0
human_verification:
  - test: "Start simulator (uv run python main.py), open http://localhost:8765, load perception_rgbd preset in pipeline editor, change tracker node from none to bytetrack and Apply. Observe detection boxes in the 3D scene."
    expected: "Detection boxes have stable track_ids that persist across frames for stationary objects. MetricsPanel shows track count."
    why_human: "100-frame stability test passes programmatically but live render stability can only be confirmed with running simulator."
  - test: "With SemanticMapLayer in SceneViewer: click Semantic Map toggle in ControlPanel. Observe 3D scene."
    expected: "Wireframe OBBs appear as a ghosted layer alongside the 3D reconstruction map. When robots move away from objects, the wireframe OBBs fade over ~10 seconds (TTL) and disappear."
    why_human: "Three.js TTL opacity fade (0.7 * clamp((ttl - age)/ttl, 0, 1)) applied per-frame in animation loop — visual fade behavior cannot be asserted programmatically without running the render engine."
  - test: "With 2 robots active: open NodeInspector for detector node in pipeline editor. Set Robot 0 to yolov11 and Robot 1 to rtdetrv2 via the per-robot override dropdowns. Check MetricsPanel."
    expected: "Both robots' detections appear in MetricsPanel under their own backend labels. Coordinator boots appropriate worker per robot without crashes."
    why_human: "Requires real multi-robot session. swap_backend_for_robot REST path is verified by unit tests but full coordinator/robot lifecycle needs human confirmation."
---

# Phase 8: stretch-tracker-fusion-semantic-map Verification Report

**Phase Goal:** Time-gated differentiators — ByteTrack per-detection `track_id`, world-frame multi-robot detection fusion, SemanticMap with TTL rendered as a ghosted Three.js layer, and heterogeneous per-robot backends.
**Verified:** 2026-04-16T13:50:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Running a session with ByteTrack enabled produces stable `track_id` values across frames for the same physical object — verified by a persistent chair keeping a single `track_id` across >=100 consecutive frames | ✓ VERIFIED | `src/tracking/trackers/bytetrack.py` implements 3D center distance Hungarian association; `test_stationary_chair_keeps_single_track_id_100_frames` passes (15 tracker tests pass). Wired in `DetectorWorker._loop` (worker.py:342). TrackerRegistry lists bytetrack with `produces_stable_ids: True`. |
| 2 | Two robots detecting the same chair within a 0.5 m cluster radius in world frame produce a single fused detection with a shared `track_id` in the merged metrics view, not two separate entries | ✓ VERIFIED | `src/perception/fusion.py` DetectionFusionManager with `cluster_radius=0.5`; 21 fusion+semantic tests pass. Spot-check confirmed: two robots at distance 0.1 m fused to single entry with `robot_ids=['robot_0','robot_1']` and score=0.92. Wired in `streaming_viz._update_stats` emitting `fused_detections` WS key. `MetricsPanel.tsx` shows `fusedDetections.length`. |
| 3 | SemanticMap renders as a ghosted Three.js layer alongside the 3D reconstruction map; objects disappear from the layer after their per-object TTL expires (user observes a fade-out within TTL seconds of leaving FOV) | ? HUMAN NEEDED | Backend: `SemanticMap` TTL expiry verified (spot-check confirmed expiry at sim_time=11 with ttl=10). Frontend: `SemanticMapLayer.ts` exists (129 lines), uses `wireframe: true, transparent: true, depthWrite: false, renderOrder: -1`, per-class Okabe-Ito colors, opacity formula `0.7 * clamp((ttl - age)/ttl, 0, 1)` in per-frame update. Wired in `SceneViewer.tsx` with `useSemanticMapStore` subscription and per-frame opacity update. ControlPanel has Semantic Map toggle. Visual fade behavior requires human to observe in running browser session. |
| 4 | Per-robot detector selection works end-to-end — user sets Robot 0 to `yolov11` and Robot 1 to `rtdetrv2` via UI, both robots' detections appear in MetricsPanel under their own backend labels, and the coordinator boots the appropriate worker per robot without crashes | ? HUMAN NEEDED | Architecture complete: `swap_backend_for_robot()` in worker_pool.py (7 tests pass), `_per_robot_backends` dict synchronized under `_swap_lock`, `POST /api/detectors/select?robot_id=X` in detector_routes.py, per-robot override section in NodeInspector.tsx with robot-color border indicator and inline error handling, `detectorStore.perRobotBackend` Zustand state. `rtdetrv2` available in DetectorRegistry. Full 2-robot coordinator startup + MetricsPanel per-backend display requires human to confirm. |

**Score:** 2/4 truths fully verified + 2/4 requiring human visual/runtime confirmation (infrastructure verified, render and live coordinator not testable programmatically)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/tracking/trackers/bytetrack.py` | ByteTrackTracker with 3D center distance association | ✓ VERIFIED | 198 lines; `@tracker(name="bytetrack"`, `PARAMETER_SCHEMA` with track_thresh/match_thresh/frame_gap, `produces_stable_ids: True`, scipy inside method (lazy per P9), no module-scope numpy |
| `src/tracking/trackers/__init__.py` | Side-effect import for bytetrack registration | ✓ VERIFIED | `from . import bytetrack # noqa: F401` present |
| `src/perception/worker.py` | tracker.track() call in _loop | ✓ VERIFIED | Line 342: `dets_3d = self._tracker.track(dets_3d)` with try/except graceful degradation |
| `src/perception/worker_pool.py` | swap_backend_for_robot + _per_robot_backends + swap_tracker | ✓ VERIFIED | All three present; TrackerRegistry.create called per-robot in __init__ |
| `src/perception/fusion.py` | DetectionFusionManager class | ✓ VERIFIED | 134 lines; `class DetectionFusionManager`, `def fuse(`, `self._cluster_radius = 0.5` |
| `src/perception/semantic_map.py` | SemanticMap class with TTL | ✓ VERIFIED | 98 lines; `class SemanticMap`, `def get_delta(`, `expired_ids` collected before `del self._objects[fid]` (Pitfall 3 safe) |
| `backend/web/detector_routes.py` | per-robot REST extension | ✓ VERIFIED | `robot_id: str | None = Query(None`, `swap_backend_for_robot` call, `per_robot` in GET /active response |
| `backend/web/streaming_viz.py` | FusionManager + SemanticMap integration | ✓ VERIFIED | Imports DetectionFusionManager + SemanticMap; instances in __init__; `fused_detections` and `semantic_map` in _update_stats payload; `def set_detector_pool` |
| `backend/web/pipeline_routes.py` | tracker hot-apply diff | ✓ VERIFIED | `tracker_changed =` (lines 114-118); `pool.swap_tracker(` (line 175); `active_tracker` in response |
| `src/main.py` | set_detector_pool wiring | ✓ VERIFIED | Line 588: `streaming_viz.set_detector_pool(detector_pool)` |
| `frontend/src/utils/messageTypes.ts` | FusedDetection, SemanticMapObject, SemanticMapDelta types | ✓ VERIFIED | All three interfaces present (lines 160, 172, 184) |
| `frontend/src/stores/semanticMapStore.ts` | Zustand store for semantic map objects | ✓ VERIFIED | 38 lines; `useSemanticMapStore`, `addOrUpdate`, `remove`, `clear`, `setVisible`, `setCurrentSimTime` |
| `frontend/src/components/SemanticMapLayer.ts` | Three.js wireframe OBB manager with TTL fade | ✓ VERIFIED | 129 lines; `class SemanticMapLayer`, `wireframe: true`, `depthWrite: false`, opacity formula present |
| `frontend/src/components/SceneViewer.tsx` | SemanticMapLayer instantiation + subscription | ✓ VERIFIED | `SemanticMapLayer` imported and instantiated; `useSemanticMapStore.subscribe` wired |
| `frontend/src/components/ControlPanel.tsx` | Semantic Map toggle | ✓ VERIFIED | `semanticMapVisible` selector; toggle button with `Semantic Map` label |
| `frontend/src/components/MetricsPanel.tsx` | FUSION subsection with fused detection count | ✓ VERIFIED | `fusedDetections` from metricsStore; `fusion` header; `{fusedDetections.length}` rendered |
| `frontend/src/components/pipeline/NodeInspector.tsx` | per-robot backend dropdown | ✓ VERIFIED | `per-robot override` section; `perRobotBackend` selector; `robot_id` in POST URL |
| `frontend/src/stores/detectorStore.ts` | perRobotBackend state | ✓ VERIFIED | `perRobotBackend`, `setPerRobotBackend`, `setAllPerRobotBackends`; populated from GET /active `per_robot` field |
| `frontend/src/stores/metricsStore.ts` | fusedDetections field | ✓ VERIFIED | `fusedDetections: FusedDetection[]` field; `setFusedDetections` setter |
| `frontend/src/hooks/useWebSocket.ts` | fused_detections and semantic_map dispatch | ✓ VERIFIED | Lines 136-147: dispatches `fused_detections` to metricsStore and `semantic_map` deltas to semanticMapStore with `addOrUpdate`/`remove`/`setCurrentSimTime` |
| `src/metrics/detection_metrics_tracker.py` | track_id-based jitter lookup | ✓ VERIFIED | `track_id = getattr(obb, "track_id", None)`; `key = f"_tid_{track_id}"`; fallback `key = cls` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/tracking/trackers/bytetrack.py` | `src/tracking/registry.py` | `@tracker` decorator | ✓ WIRED | `@tracker(name="bytetrack"` present; TrackerRegistry.list_backends() confirms registration |
| `src/tracking/trackers/bytetrack.py` | `src/perception/types.py` | `OrientedBox3D` consumption | ✓ WIRED | `from src.perception.types import` present; `replace(box, track_id=tid)` uses frozen dataclass |
| `src/perception/worker.py` | `src/tracking/protocol.py` | `TrackerProtocol.track()` | ✓ WIRED | `self._tracker.track(dets_3d)` at line 342 |
| `src/perception/worker_pool.py` | `src/tracking/registry.py` | `TrackerRegistry.create()` | ✓ WIRED | `TrackerRegistry.create(tracker_name, **tracker_kwargs)` at line 209 |
| `backend/web/detector_routes.py` | `src/perception/worker_pool.py` | `pool.swap_backend_for_robot()` | ✓ WIRED | `pool.swap_backend_for_robot(robot_id, req.backend, req.params)` at line 84 |
| `backend/web/streaming_viz.py` | `src/perception/fusion.py` | `DetectionFusionManager.fuse()` | ✓ WIRED | `fused_detections = self._fusion_manager.fuse(per_robot_dets, elapsed)` at line 525 |
| `backend/web/streaming_viz.py` | `src/perception/semantic_map.py` | `SemanticMap.update() + get_delta()` | ✓ WIRED | `self._semantic_map.update(fused_detections, elapsed)` + `get_delta(elapsed)` at lines 527-528 |
| `backend/web/pipeline_routes.py` | `src/perception/worker_pool.py` | `pool.swap_tracker()` | ✓ WIRED | `pool.swap_tracker(config.tracker_name, dict(config.tracker_params))` at line 175 |
| `src/main.py` | `backend/web/streaming_viz.py` | `set_detector_pool()` | ✓ WIRED | `streaming_viz.set_detector_pool(detector_pool)` at line 588 |
| `frontend/src/hooks/useWebSocket.ts` | `frontend/src/stores/semanticMapStore.ts` | `semantic_map` WS key dispatch | ✓ WIRED | `useSemanticMapStore.getState().addOrUpdate(semanticMap.active)` at line 143 |
| `frontend/src/components/SceneViewer.tsx` | `frontend/src/components/SemanticMapLayer.ts` | `SemanticMapLayer` instantiation | ✓ WIRED | `const semanticMapLayer = new SemanticMapLayer(worldRoot)` at line 105 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `StreamingViz._update_stats` | `fused_detections` | `pool.latest(rid)` per robot via `pool.robot_ids` loop | Yes — real tracked Detections3D from live worker, fused by DetectionFusionManager | ✓ FLOWING |
| `StreamingViz._update_stats` | `semantic_map_delta` | `self._semantic_map.get_delta(elapsed)` after `update(fused_detections, elapsed)` | Yes — real TTL-tracked objects from fused detections | ✓ FLOWING |
| `SemanticMapLayer` | `objects` | `useSemanticMapStore.objects` (populated by useWebSocket from stats `semantic_map` key) | Yes — server-generated delta via WS `stats` messages | ✓ FLOWING |
| `MetricsPanel` | `fusedDetections` | `useMetricsStore.fusedDetections` (set by useWebSocket from stats `fused_detections` key) | Yes — real fused detection list per stats tick | ✓ FLOWING |
| `NodeInspector` | `perRobotBackend` | `useDetectorStore.perRobotBackend` (populated from GET /active `per_robot` response) | Yes — server-sourced per-robot backend map | ✓ FLOWING |
| Note: `_detector_pool` is `None` until `set_detector_pool()` called (graceful degradation: empty lists emitted) | — | — | — | — |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ByteTrackTracker is importable and instantiable | `uv run python -c "from src.tracking.trackers.bytetrack import ByteTrackTracker; t = ByteTrackTracker()"` | ByteTrackTracker: class at `src.tracking.trackers.bytetrack.ByteTrackTracker` | ✓ PASS |
| TrackerRegistry lists bytetrack with produces_stable_ids | `TrackerRegistry.list_backends()` names check | `['bytetrack', 'none']`, bytetrack produces_stable_ids: True | ✓ PASS |
| DetectionFusionManager fuses two robots within 0.5m | Constructed two Detections3D at distance 0.1m, called `fuse()` | `fused count: 1, robot_ids: ['robot_0', 'robot_1'], score: 0.92` | ✓ PASS |
| SemanticMap TTL expiry at sim_time=11 (ttl=10) | `sm.get_delta(11.0)` after `update(fd, 0.0)` | `expired active: 0, expired_ids: [0]` | ✓ PASS |
| 50 pytest tests pass (tracking + fusion + semantic_map + heterogeneous + e2e) | `uv run pytest tests/tracking/ tests/perception/test_fusion*.py tests/perception/test_semantic*.py tests/perception/test_hetero*.py tests/integration/test_bytetrack_e2e.py -q` | 50 passed, 0 failures | ✓ PASS |
| 48 vitest tests pass (full frontend suite) | `cd frontend && npx vitest run --reporter=verbose` | 48 passed, 10 test files | ✓ PASS |
| TypeScript compilation clean | `cd frontend && npx tsc --noEmit` | Exit 0, no output | ✓ PASS |
| rtdetrv2 available for SC#4 | `DetectorRegistry.list_backends()` | rtdetrv2 available: True | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DET-STRETCH-01 | 08-02, 08-04, 08-06 | ByteTrack multi-object tracker assigns stable `track_id` per detection | ✓ SATISFIED | ByteTrackTracker registered, 15 tracker tests pass, wired in worker._loop, jitter upgraded to track_id keying |
| DET-STRETCH-02 | 08-05, 08-06, 08-07 | World-frame multi-robot detection fusion merges same-class detections within 0.5m | ✓ SATISFIED | DetectionFusionManager with class-gated clustering; 10 fusion tests pass; wired in streaming_viz; MetricsPanel shows count |
| DET-STRETCH-03 | 08-05, 08-06, 08-07 | SemanticMap with per-object TTL renders as ghosted Three.js layer | PARTIALLY SATISFIED | Backend SemanticMap verified (11 tests pass, TTL expiry spot-checked). SemanticMapLayer Three.js class verified with correct material settings. Visual render requires human |
| DET-STRETCH-04 | 08-03, 08-07 | Heterogeneous per-robot backends — each robot may run a different detector | PARTIALLY SATISFIED | swap_backend_for_robot + _per_robot_backends + REST + NodeInspector UI all verified. End-to-end with real 2-robot session requires human |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/main.py` | 553-560 | `DetectorWorkerPool` constructed without `tracker_name` param | ℹ️ Info | Defaults to `"none"` (NoneTracker) which is correct zero-config behavior. Tracker changed via pipeline hot-apply. Not a bug. |

No TODO/FIXME/PLACEHOLDER patterns found in any Phase 8 files. No pytest.mark.skip or test.skip stubs remaining in any test files.

### Human Verification Required

#### 1. SemanticMapLayer visual render and TTL fade (SC#3)

**Test:** Start the Argus simulator (`uv run python main.py`), open `http://localhost:8765`, load the `perception_rgbd` preset in the pipeline editor. Click "Semantic Map" toggle in ControlPanel.
**Expected:** Wireframe OBBs appear in the 3D scene as a ghosted layer with per-class colors. Move robots away from objects — wireframes should fade over ~10 seconds (TTL) and vanish. Toggle off removes all wireframes.
**Why human:** Three.js per-frame opacity fade driven by `currentSimTime` in animation loop — visual quality of fade cannot be asserted programmatically.

#### 2. ByteTrack live stable track_ids (SC#1 live validation)

**Test:** Same session. Change tracker node from `none` to `bytetrack` in pipeline editor and Apply. Watch detection boxes on a stationary object.
**Expected:** MetricsPanel shows stable track count. A stationary chair keeps one track_id across frames (no flickering IDs).
**Why human:** 100-frame stability is verified by unit test but live render consistency with real sensor frames can only be observed in running session.

#### 3. Per-robot backend end-to-end (SC#4 live validation)

**Test:** With 2 robots active, open NodeInspector for the detector node. Set Robot 0 to `yolov11` and Robot 1 to `rtdetrv2` via per-robot override dropdowns.
**Expected:** Both robots' detections appear in MetricsPanel. No crashes. Coordinator continues running.
**Why human:** Requires real 2-robot coordinator session. REST path verified by unit tests; live coordinator lifecycle with heterogeneous backends needs runtime confirmation.

### Gaps Summary

No gaps found. All automated verifications pass. Three human verification items remain for SC#3 (visual render) and SC#4 (live runtime). These are inherently visual/runtime behaviors that cannot be confirmed programmatically.

---

_Verified: 2026-04-16T13:50:00Z_
_Verifier: Claude (gsd-verifier)_
