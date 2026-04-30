---
phase: 08-stretch-tracker-fusion-semantic-map
plan: 04
subsystem: perception
tags: [bytetrack, tracker, worker, pool, jitter, track_id, detection-metrics]

# Dependency graph
requires:
  - phase: 08-02
    provides: "TrackerRegistry + TrackerProtocol + NoneTracker + ByteTrack tracker backends"
provides:
  - "tracker.track() call wired into DetectorWorker._loop post-lift"
  - "DetectorWorkerPool tracker construction via TrackerRegistry.create()"
  - "swap_tracker() method for atomic all-worker tracker hot-swap"
  - "track_id-based jitter measurement in DetectionMetricsTracker"
affects: [08-05, 08-06, 08-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "tracker.track() called post-lift/pre-store in worker._loop with try/except graceful degradation"
    - "swap_tracker mirrors swap_lifter pattern for atomic ref swap under _swap_lock"
    - "track_id-based keying with class-name fallback for backward-compatible jitter"

key-files:
  created: []
  modified:
    - src/perception/worker.py
    - src/perception/worker_pool.py
    - src/metrics/detection_metrics_tracker.py

key-decisions:
  - "NoneTracker default when no tracker param provided -- zero-config backward compat"
  - "Graceful degradation on tracker failure -- untracked detections still flow to _latest"
  - "track_id key prefix _tid_ avoids collision with class-name keys in jitter tracked dict"

patterns-established:
  - "tracker.track() post-lift pattern: detector -> lifter -> attach_capture -> tracker -> _latest"
  - "swap_tracker mirrors swap_lifter: construct outside lock, rebind inside _swap_lock"

requirements-completed: [DET-STRETCH-01]

# Metrics
duration: 3min
completed: 2026-04-16
---

# Phase 08 Plan 04: Tracker Worker Integration Summary

**ByteTrack wired into DetectorWorker._loop post-lift with per-robot tracker construction, swap_tracker, and track_id-based jitter measurement**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-16T05:14:22Z
- **Completed:** 2026-04-16T05:18:18Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- DetectorWorker._loop now calls tracker.track() after lifter.lift() and _attach_capture, with try/except graceful degradation on tracker failure (T-08-06 mitigated)
- DetectorWorkerPool constructs per-robot trackers via TrackerRegistry.create() and supports atomic swap_tracker() mirroring the swap_lifter pattern
- Jitter metrics upgraded to use track_id as the keying dimension when available, falling back to class-name nearest-neighbor proxy for backward compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire tracker into DetectorWorker._loop and extend DetectorWorkerPool construction + swap** - `56587b1` (feat)
2. **Task 2: Upgrade jitter to track_id-based lookup (D-06)** - `3606dfd` (feat)

## Files Created/Modified
- `src/perception/worker.py` - Added tracker param to __init__ (NoneTracker default), tracker.track() call in _loop, tracker.reset() in reset()
- `src/perception/worker_pool.py` - Added tracker_name/tracker_params to __init__, per-robot TrackerRegistry.create() in construction loop, swap_tracker() method
- `src/metrics/detection_metrics_tracker.py` - Jitter keying upgraded from class-name-only to track_id-based with class-name fallback

## Decisions Made
- NoneTracker used as default when no tracker parameter provided, ensuring zero-config backward compatibility with all existing tests and callers
- Tracker failures wrapped in try/except with graceful degradation (untracked detections still flow through) per threat model T-08-06
- track_id key uses `_tid_{track_id}` prefix to avoid namespace collision with class-name keys in the jitter tracked-centers dict

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- ByteTrack is now live in the per-robot worker pipeline, producing tracked detections visible to all downstream consumers
- swap_tracker() enables hot-swapping trackers at runtime (Phase 8 Plan 05+ can wire this to REST endpoints)
- track_id-based jitter gives meaningful cross-frame stability measurement when ByteTrack is active

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 08-stretch-tracker-fusion-semantic-map*
*Completed: 2026-04-16*
