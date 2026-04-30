---
phase: 08-stretch-tracker-fusion-semantic-map
plan: 06
subsystem: perception
tags: [fusion, semantic-map, streaming-viz, pipeline-routes, hot-apply, tracker, websocket]

# Dependency graph
requires:
  - phase: 08-04
    provides: "tracker.track() wired in DetectorWorker + swap_tracker() on pool"
  - phase: 08-05
    provides: "DetectionFusionManager + SemanticMap data structures"
provides:
  - "fused_detections and semantic_map WS keys emitted per stats tick"
  - "set_detector_pool() reverse ref wiring from viz to pool"
  - "tracker hot-apply via pipeline_routes.py (swap_tracker call on diff)"
  - "active_tracker in hot-apply response payload"
affects: [08-07, frontend-semantic-map-layer, frontend-metrics-panel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reverse ref pattern: streaming_viz.set_detector_pool(pool) mirrors pool.set_streaming_viz(viz)"
    - "Graceful degradation: _detector_pool=None => empty fused_detections/semantic_map"
    - "tracker_changed parallel to detector_changed/lifter_changed in hot-apply diff"

key-files:
  created: []
  modified:
    - backend/web/streaming_viz.py
    - backend/web/pipeline_routes.py
    - src/main.py
    - tests/integration/test_bytetrack_e2e.py

key-decisions:
  - "Reverse ref pattern for pool->viz wiring rather than pool passing data through method args"
  - "Graceful None degradation on _detector_pool means no crash before pool is wired"
  - "tracker_changed removed from structural_unchanged per Pitfall 8 (tracker is hot-swappable)"

patterns-established:
  - "set_detector_pool / set_streaming_viz bidirectional wiring in main.py restart block"
  - "Hot-apply diff: detector_changed || lifter_changed || tracker_changed (all three hot-swappable)"

requirements-completed: [DET-STRETCH-01, DET-STRETCH-02, DET-STRETCH-03]

# Metrics
duration: 4min
completed: 2026-04-16
---

# Phase 08 Plan 06: WS Transport Wiring Summary

**FusionManager + SemanticMap wired into WebStreamingViz._update_stats emitting fused_detections and semantic_map WS keys, pipeline hot-apply extended with tracker swap_tracker diff**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-16T05:29:10Z
- **Completed:** 2026-04-16T05:33:30Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- WebStreamingViz._update_stats now collects per-robot tracked detections via pool.latest(), runs cross-robot fusion, updates the semantic map, and emits fused_detections + semantic_map WS keys per stats tick
- pipeline_routes.py hot-apply diff extended: tracker_name/tracker_params removed from structural_unchanged check and handled via dedicated tracker_changed branch calling pool.swap_tracker()
- Integration tests replace skip-stub with real FastAPI TestClient tests verifying tracker hot-apply path + error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire FusionManager + SemanticMap into WebStreamingViz._update_stats** - `3f5d5bd` (feat)
2. **Task 2: Extend pipeline_routes.py hot-apply diff for tracker changes** - `93dca56` (feat)

## Files Created/Modified
- `backend/web/streaming_viz.py` - Added FusionManager + SemanticMap imports, instances in __init__, fusion computation in _update_stats, fused_detections/semantic_map payload keys, set_detector_pool() method
- `backend/web/pipeline_routes.py` - Removed tracker from structural_unchanged, added tracker_changed diff, swap_tracker hot-apply branch, active_tracker in response
- `src/main.py` - Added streaming_viz.set_detector_pool(detector_pool) call after pool.set_streaming_viz(streaming_viz)
- `tests/integration/test_bytetrack_e2e.py` - Replaced pytest.mark.skip stub with 2 real integration tests (tracker hot-apply + swap failure 400)

## Decisions Made
- Reverse ref pattern (viz stores pool ref) chosen over passing pool data through method arguments -- consistent with existing pool.set_streaming_viz pattern and avoids changing _update_stats signature
- Graceful None degradation when _detector_pool not yet wired -- fused_detections and semantic_map emit empty defaults without error
- tracker_name/tracker_params removed from structural_unchanged per Pitfall 8 -- trackers are lightweight state machines suitable for hot-swap like detectors/lifters

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- fused_detections and semantic_map WS keys now flow to connected frontend clients every stats tick
- Frontend semantic map layer (Plan 07) can consume the {active: [...], expired_ids: [...]} delta format
- Pipeline editor tracker node changes hot-apply without coordinator restart
- All 49 relevant tests passing (fusion, semantic map, tracking, pipeline hot-apply, bytetrack e2e)

## Self-Check: PASSED
