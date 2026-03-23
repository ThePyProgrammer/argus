---
phase: 10-pose-graph-map-merger
plan: 02
subsystem: coordination
tags: [open3d, gtsam, pgo, icp, loop-closure, pose-graph, isam2]

requires:
  - phase: 10-01
    provides: MergeProtocol, MergeRegistry, @merge_strategy decorator, ICPUnionStrategy baseline
provides:
  - Open3D PGO merge strategy with global optimization and loop closure
  - GTSAM iSAM2 incremental PGO merge strategy (optional dependency)
  - Loop closure detection via ICP with spawn transform fallback
  - AVAILABLE class attribute pattern for optional dependency strategies
affects: [10-03, coordinator-integration, merge-api-routes]

tech-stack:
  added: [gtsam (optional)]
  patterns: [optional-dependency-strategy, spawn-transform-fallback, icp-loop-closure]

key-files:
  created:
    - src/coordination/merge_strategies/pgo_open3d.py
    - src/coordination/merge_strategies/pgo_gtsam.py
  modified:
    - src/coordination/merge_strategies/__init__.py
    - src/coordination/merge_registry.py
    - tests/coordination/test_merge_strategies.py

key-decisions:
  - "PointToPlane ICP with automatic normal estimation for loop closure detection"
  - "AVAILABLE class attribute + INSTALL_HINT pattern for optional dependency checking in MergeRegistry"
  - "Reuse _detect_loop_closure and _voxel_downsample_points from pgo_open3d in pgo_gtsam"

patterns-established:
  - "Optional dependency strategy: AVAILABLE class attr + INSTALL_HINT + try-import pattern"
  - "Spawn transform fallback: inv(spawn_a) @ spawn_b when ICP fails, identity when no spawns"

requirements-completed: [MERG-01, MERG-03]

duration: 7min
completed: 2026-03-23
---

# Phase 10 Plan 02: PGO Merge Strategies Summary

**Open3D PGO and GTSAM iSAM2 merge strategies with ICP loop closure detection and spawn transform fallback on ICP failure**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-23T07:20:46Z
- **Completed:** 2026-03-23T07:28:11Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Open3D PGO strategy builds pose graphs with odometry and loop closure edges, runs Levenberg-Marquardt global optimization, re-projects frame clouds with optimized poses
- GTSAM iSAM2 strategy provides incremental PGO with BetweenFactorPose3 factors (optional dependency, gracefully unavailable when gtsam not installed)
- Loop closure detection uses ICP on overlapping point cloud regions, falls back to spawn transforms from MuJoCo config on ICP failure
- MergeRegistry enhanced with AVAILABLE class attribute checking for optional dependency strategies

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: Open3D PGO merge strategy** - `868a801` (test), `578082b` (feat)
2. **Task 2: GTSAM iSAM2 merge strategy** - `b368786` (test), `3465f42` (feat), `50ee7a2` (fix: registry + init), `cd5a0be` (fix: test params)

## Files Created/Modified

- `src/coordination/merge_strategies/pgo_open3d.py` - Open3D PGO strategy with loop closure and spawn fallback
- `src/coordination/merge_strategies/pgo_gtsam.py` - GTSAM iSAM2 incremental PGO with optional dependency handling
- `src/coordination/merge_strategies/__init__.py` - Imports pgo_open3d and pgo_gtsam for registration
- `src/coordination/merge_registry.py` - AVAILABLE/INSTALL_HINT checking in list_strategies and create
- `tests/coordination/test_merge_strategies.py` - TestOpen3DPGO, TestPGOLoopClosure, TestLoopClosureFallback, TestGTSAMPGO

## Decisions Made

- Used PointToPlane ICP with automatic normal estimation for loop closure detection (PointToPoint would work but PointToPlane is more robust)
- GTSAM strategy reuses `_detect_loop_closure` and `_voxel_downsample_points` from pgo_open3d to avoid code duplication
- Added AVAILABLE class attribute pattern to MergeRegistry for optional dependency checking (mirrors approach used in other registries)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ICP PointToPlane requires normals**
- **Found during:** Task 1 (Open3D PGO implementation)
- **Issue:** PointToPlane ICP requires target point cloud to have normals estimated
- **Fix:** Added automatic normal estimation in `_detect_loop_closure` before ICP
- **Files modified:** src/coordination/merge_strategies/pgo_open3d.py
- **Committed in:** 578082b (Task 1 feat commit)

**2. [Rule 1 - Bug] Loop closure test ICP max_correspondence_distance too tight**
- **Found during:** Task 2 verification
- **Issue:** Default 0.15m max correspondence distance insufficient for random test clouds
- **Fix:** Test uses 0.5m correspondence distance for overlapping cloud test
- **Files modified:** tests/coordination/test_merge_strategies.py
- **Committed in:** cd5a0be

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Linter reverted `__init__.py` and `merge_registry.py` changes during Task 2 commit, requiring a separate fix commit (50ee7a2)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Three merge strategies now registered: icp_union, pgo_open3d, pgo_gtsam
- Plan 10-03 (Coordinator integration) can proceed - MergeProtocol implementations are complete
- GTSAM tests skip gracefully when gtsam is not installed (4 skipped)

---
*Phase: 10-pose-graph-map-merger*
*Completed: 2026-03-23*
