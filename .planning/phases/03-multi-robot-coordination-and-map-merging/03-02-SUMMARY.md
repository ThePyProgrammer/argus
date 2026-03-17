---
phase: 03-multi-robot-coordination-and-map-merging
plan: 02
subsystem: coordination
tags: [map-merger, voxel-fusion, plcm, pub-sub, multi-robot, coordinator, exploration]

# Dependency graph
requires:
  - phase: 03-01
    provides: MultiRobotConfig, MultiRobotBridge, VoronoiPartitioner, scene builder
  - phase: 02
    provides: ExplorationLoop, GoalSelector, FrontierDetector, CoverageTracker
  - phase: 01
    provides: SLAMPipeline, OctoMapBuilder, SensorFrame, CameraIntrinsics
provides:
  - MapMerger class for voxel fusion with union (OR) logic and frame alignment
  - RobotInstance per-robot pipeline container with pLCM publisher
  - RobotMapMessage dataclass for occupancy data published via pLCM
  - Coordinator lifecycle orchestrator with pLCM subscriptions
  - ExplorationLoop.step_once() for single-step multi-robot mode
  - GoalSelector.select_with_bias() for Voronoi-biased frontier selection
affects: [03-03-PLAN, visualization, integration-testing]

# Tech tracking
tech-stack:
  added: [pLCMTransport, PickleLCM]
  patterns: [pLCM pub/sub for robot-to-robot data, rescan-triggered merge, step_once pattern]

key-files:
  created:
    - src/coordination/map_merger.py
    - src/coordination/robot_instance.py
    - src/coordination/coordinator.py
    - tests/test_map_merger.py
    - tests/test_coordinator.py
  modified:
    - src/exploration/exploration_loop.py
    - src/exploration/goal_selector.py

key-decisions:
  - "pLCM transport for robot-to-robot data sharing (per locked user decision)"
  - "Merge triggers on rescan events (same trigger as frontier rescan), NOT fixed step intervals"
  - "Graceful dimos import fallback with try/except for testing without full dimos runtime"
  - "ExplorationLoop.run() refactored to delegate to step_once() for backward compatibility"

patterns-established:
  - "pLCM pub/sub pattern: RobotInstance publishes, Coordinator subscribes"
  - "step_once pattern: single-frame processing returning (linear, angular, metrics) tuple"
  - "Rescan-triggered merge: Coordinator.run() checks metrics['rescan_triggered'] per step"

requirements-completed: [COORD-03, MERGE-01, MERGE-02, MERGE-03]

# Metrics
duration: 9min
completed: 2026-03-17
---

# Phase 3 Plan 2: Map Merger, Robot Instance, and Coordinator Summary

**MapMerger with union (OR) voxel fusion, RobotInstance with pLCM publishers, Coordinator with rescan-triggered merge and Voronoi-biased exploration**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-17T08:14:00Z
- **Completed:** 2026-03-17T08:23:54Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- MapMerger fuses two occupancy grids with union (OR) logic, deduplication, and spawn transform alignment
- RobotInstance bundles SLAM + OctoMap + ExplorationLoop per robot, publishes occupancy data via pLCM
- Coordinator orchestrates full multi-robot lifecycle: boot -> partition -> biased exploration -> rescan-triggered merge
- ExplorationLoop.step_once() enables single-step mode for Coordinator control while maintaining backward-compatible run()
- GoalSelector.select_with_bias() supports Voronoi-biased frontier selection via external scoring function

## Task Commits

Each task was committed atomically:

1. **Task 1: MapMerger (TDD RED)** - `3edd0d7` (test: failing tests for voxel fusion)
2. **Task 1: MapMerger (TDD GREEN)** - `a647380` (feat: implement MapMerger)
3. **Task 2: RobotInstance + Coordinator + step_once + GoalSelector bias** - `16b99fc` (feat)

## Files Created/Modified
- `src/coordination/map_merger.py` - MapMerger class: voxel fusion, point cloud merge, frame alignment
- `src/coordination/robot_instance.py` - RobotInstance container + RobotMapMessage + pLCM publisher
- `src/coordination/coordinator.py` - Coordinator: multi-robot lifecycle, pLCM subscriptions, rescan-triggered merge
- `src/exploration/exploration_loop.py` - Added step_once() method, refactored run() to use it
- `src/exploration/goal_selector.py` - Added select_with_bias() for Voronoi-biased selection
- `tests/test_map_merger.py` - 7 tests: union merge, dedup, empty sets, point clouds, transforms, integration
- `tests/test_coordinator.py` - 11 tests: RobotInstance, Coordinator lifecycle, pLCM, rescan-trigger, repartition

## Decisions Made
- pLCM transport for robot-to-robot data sharing (per locked user decision from CONTEXT.md)
- Merge triggers on rescan events (per user decision -- same trigger as frontier rescan from Phase 2)
- Graceful dimos import with try/except fallback (dimos runtime has heavy transitive deps -- cv2, etc.)
- ExplorationLoop.run() refactored to call step_once() internally for code reuse

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Graceful dimos import fallback**
- **Found during:** Task 2 (RobotInstance + Coordinator)
- **Issue:** dimos.core.transport import chain pulls in cv2, numpy, and system libs not available in test environment
- **Fix:** Added try/except with fallback to None stub for testing; tests mock pLCMTransport
- **Files modified:** src/coordination/robot_instance.py, src/coordination/coordinator.py
- **Verification:** All 30 tests pass
- **Committed in:** 16b99fc (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for testability without full dimos runtime. No scope creep.

## Issues Encountered
- MuJoCo renderer test (test_sim_bridge.py::test_lifecycle) fails in headless environment -- pre-existing, unrelated to our changes

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full coordination pipeline ready: MapMerger + RobotInstance + Coordinator
- Plan 03-03 can build end-to-end integration test wiring all components
- Coordinator manages complete lifecycle: boot -> partition -> explore -> merge -> terminate

---
*Phase: 03-multi-robot-coordination-and-map-merging*
*Completed: 2026-03-17*
