---
phase: 13-live-metrics-dashboard-output-toggle
plan: 01
subsystem: metrics, api, ui
tags: [zustand, websocket, ring-buffer, drift-metrics, slam, typescript]

# Dependency graph
requires:
  - phase: 08-backend-abstraction-icp-wrap
    provides: SLAMProtocol, SLAMResult with metrics dict, streaming_viz stats pipeline
  - phase: 09-frontend-slam-selection
    provides: slamStore pattern, useWebSocket dispatch pattern, messageTypes.ts
  - phase: 11-orbslam3-backend
    provides: tracking_status propagation, last_tracking_status on ExplorationLoop
provides:
  - MetricsTracker class with ring buffer accumulation and ICP baseline capture
  - Coordinator wiring that feeds per-robot SLAM metrics into tracker every viz update
  - Extended StatsPayload with slam_metrics/baseline/metric_history
  - metricsStore Zustand store for frontend metrics state
  - useWebSocket metrics dispatch from stats messages to metricsStore
affects: [13-02-PLAN, 13-03-PLAN, MetricsPanel, Sparkline, output-toggle]

# Tech tracking
tech-stack:
  added: []
  patterns: [ring-buffer-deque-metrics, batched-zustand-update, coordinator-metrics-feed]

key-files:
  created:
    - src/metrics/metrics_tracker.py
    - frontend/src/stores/metricsStore.ts
    - tests/web/test_metrics_tracker.py
  modified:
    - backend/web/streaming_viz.py
    - src/coordination/coordinator.py
    - src/exploration/exploration_loop.py
    - frontend/src/utils/messageTypes.ts
    - frontend/src/hooks/useWebSocket.ts
    - tests/web/test_streaming_viz.py

key-decisions:
  - "MetricsTracker uses deque(maxlen=60) ring buffers -- bounded memory, O(1) append"
  - "Drift computed every 100 sim steps (10 viz updates) with rolling 50-pose window"
  - "Baseline persists across MetricsTracker.reset() for cross-session comparison"
  - "updateAllMetrics uses single set() call to avoid 3 re-renders per stats message"
  - "ExplorationLoop stores last_slam_metrics for coordinator access (Rule 2 deviation)"

patterns-established:
  - "Ring buffer metrics: deque(maxlen=N) for bounded accumulation"
  - "Batched Zustand update: updateAllMetrics sets 3 fields in single set() call"
  - "Coordinator metrics feed: hasattr guard for backward compat with non-streaming viz"

requirements-completed: [CTRL-05, CTRL-06]

# Metrics
duration: 5min
completed: 2026-03-23
---

# Phase 13 Plan 01: Metrics Data Pipeline Summary

**MetricsTracker with per-robot ATE/RPE/ms_per_frame ring buffers, coordinator wiring feeding SLAM data into tracker, extended stats WebSocket with slam_metrics/baseline/metric_history, and metricsStore Zustand store with useWebSocket dispatch**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-23T11:13:11Z
- **Completed:** 2026-03-23T11:18:54Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- MetricsTracker accumulates per-robot ATE, RPE, ms_per_frame, and tracking_status in deque ring buffers (maxlen=60)
- Coordinator feeds record_frame on every viz update (10 sim steps), compute_drift_metrics every 100 sim steps (rolling 50-frame window)
- Stats WebSocket message now carries slam_metrics, baseline, and metric_history alongside existing coverage/merge/elapsed data
- metricsStore Zustand store follows flat state + setter pattern matching slamStore/controlStore
- useWebSocket dispatches all 3 metrics fields from stats message in a single batched update to avoid re-renders

## Task Commits

Each task was committed atomically:

1. **Task 1: MetricsTracker backend + tests + streaming_viz integration** - TDD task
   - RED: `ddb5b0f` (test) -- 10 failing tests
   - GREEN: `a9b304b` (feat) -- MetricsTracker implementation + streaming_viz wiring
2. **Task 2: Coordinator wiring + metricsStore + messageTypes + useWebSocket** - `3477213` (feat)

## Files Created/Modified
- `src/metrics/metrics_tracker.py` - MetricsTracker class with ring buffer deques, baseline capture, stats payload serialization
- `tests/web/test_metrics_tracker.py` - 9 unit tests covering record_frame, record_drift, ring buffer eviction, histories, baseline, payload
- `backend/web/streaming_viz.py` - MetricsTracker instantiation, metrics_tracker property, slam_metrics/baseline/metric_history in stats payload
- `tests/web/test_streaming_viz.py` - Added test_stats_includes_slam_metrics verifying payload structure
- `src/coordination/coordinator.py` - metrics_tracker.record_frame/record_drift wiring, compute_drift_metrics, capture_baseline on restart
- `src/exploration/exploration_loop.py` - Added last_slam_metrics attribute storing SLAMResult.metrics per frame
- `frontend/src/utils/messageTypes.ts` - SlamMetrics, MetricHistory interfaces; StatsPayload extended with 3 optional fields
- `frontend/src/stores/metricsStore.ts` - Zustand store with perRobot, baseline, viewMode, outputMode, history, meshData state + setters
- `frontend/src/hooks/useWebSocket.ts` - Import metricsStore, dispatch slam_metrics/baseline/metric_history in stats handler

## Decisions Made
- MetricsTracker uses deque(maxlen=60) ring buffers for bounded memory and O(1) append
- Drift computed every 100 sim steps (not every viz update) to keep expensive evo computation from running too frequently
- Baseline persists across MetricsTracker.reset() so cross-session comparison remains available
- updateAllMetrics does a single set() call with all 3 fields to avoid 3 re-renders per stats message
- Coordinator uses hasattr guard on self._viz for backward compatibility with non-streaming visualizers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added last_slam_metrics to ExplorationLoop**
- **Found during:** Task 2 (Coordinator wiring)
- **Issue:** Coordinator needs per-frame SLAM metrics (processing_time_ms) to feed into MetricsTracker, but SLAMResult.metrics was not stored anywhere accessible
- **Fix:** Added `self.last_slam_metrics = result.metrics` in ExplorationLoop._update_slam() (same pattern as existing last_tracking_status)
- **Files modified:** src/exploration/exploration_loop.py
- **Verification:** Coordinator reads getattr(robot.exploration, 'last_slam_metrics', {}) safely; all tests pass
- **Committed in:** 3477213 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Essential for metrics pipeline to access per-frame processing time. No scope creep.

## Issues Encountered
- Pre-existing TypeScript compilation errors in DetectionBoxes.ts, SceneViewer.tsx, and useWebSocket.ts (crash_fallback type not in WSMessage union) -- these predate phase 13 and are unrelated to metrics changes. Logged to deferred-items.md.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full metrics data pipeline operational: backend accumulation -> WebSocket transport -> frontend store
- metricsStore ready for MetricsPanel component (plan 13-02) to consume perRobot, baseline, history, viewMode
- outputMode state in metricsStore ready for output toggle component (plan 13-03)
- All 60 web tests pass; TypeScript compiles (pre-existing errors only)

## Self-Check: PASSED

All created files verified to exist on disk. All 3 commit hashes (ddb5b0f, a9b304b, 3477213) verified in git log.

---
*Phase: 13-live-metrics-dashboard-output-toggle*
*Completed: 2026-03-23*
