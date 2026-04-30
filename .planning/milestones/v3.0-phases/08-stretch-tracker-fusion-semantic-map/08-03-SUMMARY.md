---
phase: 08-stretch-tracker-fusion-semantic-map
plan: 03
subsystem: perception
tags: [per-robot-backend, hot-swap, heterogeneous-detectors, worker-pool, rest-api]

# Dependency graph
requires:
  - phase: 08-01
    provides: "DetectorWorkerPool with swap_backend + on_backend_crash"
provides:
  - "swap_backend_for_robot() for single-robot atomic detector hot-swap"
  - "_per_robot_backends dict tracking per-robot backend assignments"
  - "per_robot_backends property returning lock-safe snapshot"
  - "Scoped crash fallback (single robot via robot_id param)"
  - "POST /select?robot_id=X per-robot REST endpoint"
  - "GET /active per_robot breakdown in response"
affects: [08-04, 08-05, 08-06, 08-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-robot heterogeneous backend pattern: _per_robot_backends dict + swap_backend_for_robot"
    - "Scoped crash fallback: on_backend_crash(robot_id=X) only swaps that robot"

key-files:
  created: []
  modified:
    - src/perception/worker_pool.py
    - src/perception/worker.py
    - backend/web/detector_routes.py
    - tests/perception/test_heterogeneous_backends.py

key-decisions:
  - "per_robot_backends property returns a copy under _swap_lock for thread safety"
  - "swap_backend_for_robot constructs+warms single detector OUTSIDE lock, rebinds INSIDE lock (mirror of swap_backend pattern)"
  - "on_backend_crash robot_id=None preserves all-robots fallback behavior (backward compat)"
  - "app_state.last_applied_pipeline_config only updated on all-robots crash fallback (not scoped)"

patterns-established:
  - "Per-robot heterogeneous backend: _per_robot_backends dict updated inside _swap_lock in ALL mutation paths (swap_backend, swap_backend_for_robot, on_backend_crash)"
  - "REST per-robot targeting: optional Query param robot_id; omit for all-robots behavior"

requirements-completed: [DET-STRETCH-04]

# Metrics
duration: 7min
completed: 2026-04-16
---

# Phase 08 Plan 03: Heterogeneous Per-Robot Backend Summary

**Per-robot detector hot-swap via swap_backend_for_robot() + scoped crash fallback + REST /select?robot_id extension**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-16T05:04:48Z
- **Completed:** 2026-04-16T05:11:56Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added swap_backend_for_robot() for atomic single-robot detector hot-swap with construct-warmup-rebind pattern
- Added _per_robot_backends dict tracking each robot's backend assignment, synchronized via _swap_lock in all mutation paths
- Scoped on_backend_crash fallback to single robot when robot_id is provided (worker.py passes self._rid)
- Extended POST /select with optional robot_id query param for per-robot REST hot-swap (no restart needed)
- Extended GET /active to return per_robot breakdown dict
- Replaced 4 test skip-stubs with 7 comprehensive tests covering all behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add swap_backend_for_robot + _per_robot_backends + scoped crash fallback** - `569fd14` (feat, TDD)
2. **Task 2: Extend REST endpoints for per-robot backend selection** - `4cc037d` (feat)

## Files Created/Modified
- `src/perception/worker_pool.py` - Added _per_robot_backends dict, per_robot_backends property, swap_backend_for_robot(), updated swap_backend() and on_backend_crash() with per-robot scoping
- `src/perception/worker.py` - Updated _loop crash escalation to pass robot_id=self._rid to on_backend_crash
- `backend/web/detector_routes.py` - POST /select accepts optional robot_id query param; GET /active returns per_robot breakdown
- `tests/perception/test_heterogeneous_backends.py` - Replaced 4 skip-stubs with 7 real tests using _MockDetector/_MockDetectorAlt/_MockLifter

## Decisions Made
- per_robot_backends property returns a dict copy under _swap_lock for thread safety (not a live reference)
- swap_backend_for_robot mirrors swap_backend pattern: construct+warm OUTSIDE lock, rebind INSIDE lock
- on_backend_crash with robot_id=None preserves original all-robots fallback (backward compatibility)
- app_state.last_applied_pipeline_config only updated on all-robots crash fallback (scoped fallback doesn't touch the pipeline baseline)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- test_detector_routes.py cannot run in this environment due to pre-existing mujoco dependency missing from import chain (server.py -> streaming_viz.py -> mujoco_gt.py). This is a pre-existing environment issue unrelated to plan 08-03 changes. All heterogeneous backend tests (7/7) and related swap/crash tests (10/10) pass.

## Threat Flags

None - all threat mitigations from the plan's threat model are implemented:
- T-08-03: robot_id validated by swap_backend_for_robot against pool._workers.keys() -> ValueError -> HTTP 404
- T-08-04: Backend name validated via DetectorRegistry.list_backends() before create() (existing T-02-19 pattern)
- T-08-05: _per_robot_backends updated inside _swap_lock in on_backend_crash (both scoped and all-robots paths)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Per-robot heterogeneous backend infrastructure complete
- pool.per_robot_backends property ready for frontend consumption
- Scoped crash fallback ready for production use via worker.py's robot_id escalation

## Self-Check: PASSED

All files exist, all commits verified.

---
*Phase: 08-stretch-tracker-fusion-semantic-map*
*Completed: 2026-04-16*
