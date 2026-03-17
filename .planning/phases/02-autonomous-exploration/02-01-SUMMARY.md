---
phase: 02-autonomous-exploration
plan: 01
subsystem: exploration
tags: [frontier-detection, a-star, occupancy-grid, bfs-clustering, voxel, numpy]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: OctoMapBuilder.get_occupied_voxels() returning (N,3) float64 voxel centers
provides:
  - FrontierDetector with 26-connected BFS clustering
  - GoalSelector with nearest/largest strategy
  - OccupancyGrid2D with 3D-to-2D projection
  - A* PathPlanner with octile heuristic and world-coordinate waypoints
affects: [02-02-exploration-loop, 03-multi-robot]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD red-green, voxel-to-grid discretization with np.round, heapq A*]

key-files:
  created:
    - src/exploration/__init__.py
    - src/exploration/frontier_detector.py
    - src/exploration/goal_selector.py
    - src/exploration/occupancy_grid.py
    - src/exploration/path_planner.py
    - tests/test_frontier_detector.py
    - tests/test_goal_selector.py
    - tests/test_path_planner.py
  modified:
    - tests/conftest.py

key-decisions:
  - "Used np.round for float-to-int grid index conversion to avoid truncation bugs with 0.1m resolution voxels"
  - "Dilation-based free-space model: UNKNOWN cells near OCCUPIED cells become FREE, repeated max(3, 1/resolution) rounds"
  - "Path simplification keeps every Nth waypoint (~1m apart) for coarse navigation with discrete actions"
  - "UNKNOWN cells traversable in A* but penalized with configurable unknown_cost multiplier (default 5x)"

patterns-established:
  - "Grid discretization: always np.round before astype(int) to prevent float truncation"
  - "Frontier detector accepts robot_positions param reserved for future observed-region modeling"
  - "PathPlanner returns (3,) float64 waypoints with Z=0.0 for ground-plane nav"

requirements-completed: [EXPL-01, EXPL-02]

# Metrics
duration: 7min
completed: 2026-03-17
---

# Phase 2 Plan 1: Exploration Algorithms Summary

**3D voxel frontier detection with BFS clustering, nearest/largest goal selection, 2D occupancy grid projection, and A* path planning with world-coordinate waypoints**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-17T06:56:27Z
- **Completed:** 2026-03-17T07:03:07Z
- **Tasks:** 2 (TDD, 4 commits)
- **Files modified:** 9

## Accomplishments
- FrontierDetector identifies 3D boundary voxels using 26-connected neighbor scanning, clusters via BFS, filters by min_cluster_size
- GoalSelector ranks frontier clusters by nearest (Euclidean distance) or largest (voxel count) strategy
- OccupancyGrid2D projects 3D voxels to 2D navigation grid with dilation-based free-space model
- A* PathPlanner with 8-connected grid, octile heuristic, unknown cell penalty, and path simplification
- 23 unit tests passing across 3 test files

## Task Commits

Each task was committed atomically (TDD: test then feat):

1. **Task 1: FrontierDetector and GoalSelector**
   - `7df6760` (test) - Failing tests for frontier detection and goal selection
   - `ef38469` (feat) - Implementation with np.round fix for grid discretization

2. **Task 2: OccupancyGrid2D and A* PathPlanner**
   - `eed8887` (test) - Failing tests for grid projection and path planning
   - `b57dc2b` (feat) - Implementation with dilation free-space and heapq A*

## Files Created/Modified
- `src/exploration/__init__.py` - Package init for exploration module
- `src/exploration/frontier_detector.py` - FrontierDetector class with 26-connected BFS clustering
- `src/exploration/goal_selector.py` - GoalSelector with nearest/largest strategy
- `src/exploration/occupancy_grid.py` - OccupancyGrid2D with project_voxels_to_2d()
- `src/exploration/path_planner.py` - A* PathPlanner with octile heuristic
- `tests/test_frontier_detector.py` - 6 tests for frontier detection
- `tests/test_goal_selector.py` - 5 tests for goal selection
- `tests/test_path_planner.py` - 12 tests for grid projection and path planning
- `tests/conftest.py` - Added mock_occupied_cube, mock_two_blobs, mock_robot_positions fixtures

## Decisions Made
- Used `np.round` before `astype(int)` for voxel-to-grid conversion to avoid floating-point truncation (0.1*9/0.1 = 8.999... -> 8 without rounding)
- Dilation-based free-space model (not ray-casting) for simplicity; adequate for A* navigation
- UNKNOWN cells are traversable in A* with 5x cost penalty to allow exploration through uncharted areas
- Path simplification at ~1m intervals for compatibility with coarse discrete action space

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed float-to-int truncation in grid index computation**
- **Found during:** Task 1 (FrontierDetector TDD GREEN)
- **Issue:** `((voxels - grid_min) / resolution).astype(int)` truncates 9.999 to 9, collapsing 10x10x10=1000 voxels into 8x8x8=512 unique indices
- **Fix:** Changed to `np.round(...).astype(int)` for correct rounding
- **Files modified:** src/exploration/frontier_detector.py
- **Verification:** 10x10x10 cube now correctly produces 488 frontier (shell) voxels
- **Committed in:** ef38469

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Essential correctness fix for floating-point precision. No scope creep.

## Issues Encountered
- Environment library linking: numpy/Open3D require LD_LIBRARY_PATH set to nix store paths for libstdc++ and libz. Existing Phase 1 Open3D tests fail due to missing libX11 (headless environment). New exploration tests do not depend on Open3D and pass cleanly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All four exploration algorithm modules ready for ExplorationLoop (Plan 02) to orchestrate
- FrontierDetector.detect() takes (N,3) voxels from OctoMapBuilder.get_occupied_voxels()
- GoalSelector.select() takes FrontierCluster list and returns (3,) goal centroid
- PathPlanner.plan() takes start/goal world coords and OccupancyGrid2D, returns waypoint list
- WaypointRunner (Phase 1) converts waypoints to velocity commands for SimWorld

---
*Phase: 02-autonomous-exploration*
*Completed: 2026-03-17*
