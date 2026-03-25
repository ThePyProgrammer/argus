---
phase: 15-close-v2-0-audit-gaps-restart-signal-crash-fallback
plan: 02
subsystem: slam
tags: [icp, fallback, crash-recovery, subprocess, exploration]

# Dependency graph
requires:
  - phase: 12-subprocess-slam-backends
    provides: "SubprocessSLAMBridge crash detection and crash_fallback WS emission"
provides:
  - "Live ICP backend swap on subprocess SLAM crash in ExplorationLoop"
  - "Intrinsics passthrough from RobotInstance to ExplorationLoop for fallback creation"
affects: [exploration, coordination, slam]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import of SLAMRegistry inside crash handler to avoid circular imports"

key-files:
  created: []
  modified:
    - src/exploration/exploration_loop.py
    - src/coordination/robot_instance.py

key-decisions:
  - "ICP fallback swap placed inside same if-guard as crash_fallback WS emission for consistent triggering"
  - "intrinsics parameter typed as object | None to avoid importing CameraIntrinsics in exploration module"

patterns-established:
  - "Crash recovery pattern: detect -> notify frontend -> swap backend -> continue loop"

requirements-completed: [BACK-06]

# Metrics
duration: 1min
completed: 2026-03-25
---

# Phase 15 Plan 02: Crash Fallback ICP Swap Summary

**Live ICP backend swap in ExplorationLoop when subprocess SLAM crashes, closing the gap where crash notification fired but exploration stalled on dead subprocess**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-25T07:23:18Z
- **Completed:** 2026-03-25T07:24:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- ExplorationLoop now swaps self._slam to a fresh ICP backend when subprocess crash is detected
- Intrinsics parameter added to ExplorationLoop and passed from RobotInstance.create for proper ICP instantiation
- Crash notification WS message preserved alongside the actual backend swap

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ICP fallback swap in ExplorationLoop crash detection** - `4e52b93` (feat)

## Files Created/Modified
- `src/exploration/exploration_loop.py` - Added intrinsics param, ICP fallback swap via SLAMRegistry.create("icp") on crash detection
- `src/coordination/robot_instance.py` - Pass intrinsics to ExplorationLoop constructor

## Decisions Made
- ICP fallback swap placed inside the same if-guard as the crash_fallback WS emission, ensuring both fire under identical conditions (tracking_status lost + has _bridge subprocess attribute)
- Used `object | None` type for intrinsics parameter to avoid importing CameraIntrinsics into exploration module
- Wrapped fallback creation in try/except to prevent fallback failure from crashing the exploration loop

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- MISSING-02 gap (crash_fallback emits notification but does not swap to ICP backend) is now closed
- v2.0 audit gaps fully addressed with this plan

---
*Phase: 15-close-v2-0-audit-gaps-restart-signal-crash-fallback*
*Completed: 2026-03-25*

## Self-Check: PASSED
