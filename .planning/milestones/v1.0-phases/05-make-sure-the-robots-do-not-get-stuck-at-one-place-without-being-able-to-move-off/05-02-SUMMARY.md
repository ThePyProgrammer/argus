---
phase: 05-robot-locomotion-fix
plan: 02
subsystem: bridge, exploration, locomotion
tags: [mujoco, trot-gait, position-actuators, stuck-recovery, depth-rendering]

# Dependency graph
requires:
  - phase: 05-01
    provides: TrotGaitController, GaitParams, patch_actuators_to_position
provides:
  - Bridge integration with trot gait controller (both single and multi-robot)
  - Scene builder actuator patching for multi-robot scenes
  - Stuck recovery turn-in-place in exploration loop
  - Body-attached camera with correct point cloud transforms
  - Ground plane filtering in occupancy grid
  - Rewritten frontier detector using FREE/UNKNOWN boundaries
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Body-attached front_cam instead of free camera for correct depth transforms"
    - "Dynamic ground plane filter in occupancy grid (z_min threshold)"
    - "Frontier detection via FREE-to-UNKNOWN cell boundaries on 2D grid"
    - "A* allows start from OCCUPIED cells (robot standing position)"

key-files:
  created: []
  modified:
    - src/bridge/sim_bridge.py
    - src/bridge/multi_bridge.py
    - src/coordination/scene_builder.py
    - src/exploration/exploration_loop.py
    - src/exploration/frontier_detector.py
    - src/exploration/occupancy_grid.py
    - src/exploration/path_planner.py
    - src/control/waypoint_runner.py
    - src/main.py
    - tests/test_exploration_loop.py
    - tests/test_multi_bridge.py

key-decisions:
  - "Body-attached front_cam replaces free camera for correct point cloud transforms"
  - "Ground plane filter at z_min=0.15m to exclude floor from occupancy grid"
  - "Frontier detector rewritten to use FREE-to-UNKNOWN boundaries on 2D grid"
  - "A* allows starting from OCCUPIED cells since robot physically stands on ground voxels"
  - "Waypoint runner always drives forward (no turn-in-place stalling)"
  - "Stuck detection thresholds relaxed for continuous gait locomotion"
  - "Multi-robot early termination disabled to run full max_steps"

patterns-established:
  - "Metric vs normalized depth detection: check value range to determine MuJoCo depth format"
  - "Stamp robot trajectory as FREE space in occupancy grid to prevent self-blocking"

requirements-completed: [LOCO-04, LOCO-05, LOCO-06]

# Metrics
duration: ~60min
completed: 2026-03-18
---

# Phase 5 Plan 2: Bridge Integration, Stuck Recovery, and Locomotion Verification Summary

**TrotGaitController wired into both bridges with position-actuator patching, stuck turn-in-place recovery, and extensive depth/navigation bug fixes verified at 200 steps with 149 voxel merges and 33k merged voxels**

## Performance

- **Duration:** ~60 min (including extensive human verification and debugging)
- **Started:** 2026-03-18T05:00:00Z
- **Completed:** 2026-03-18T06:00:00Z
- **Tasks:** 3 (2 auto + 1 human-verify)
- **Files modified:** 19

## Accomplishments
- Both single-robot and multi-robot bridges now use TrotGaitController for real walking locomotion
- Scene builder patches actuators to position type before multi-robot assembly
- Stuck recovery triggers 90-degree randomized turn-in-place when robot is stuck
- Depth rendering fixed with metric vs normalized format detection
- Body-attached front_cam produces correct point cloud transforms
- Frontier detector rewritten for reliable FREE/UNKNOWN boundary detection
- Final verification: 200 steps, 149 merges, 33k merged voxels, both robots producing ~16k voxels each

## Task Commits

Each task was committed atomically:

1. **Task 1: Integrate locomotion into bridges and scene builder** - `cf1628a` (feat)
2. **Task 2: Add stuck recovery to exploration loop** - `4de38b0` (feat)
3. **Task 3: Visual verification of robot locomotion** - human-verified (approved)

Additional bug-fix commits during verification:
- `640f370` fix: double-multiplied dt in velocity_to_ctrl
- `5a8f051` fix: default multi-robot to flat scene
- `889507c` fix: drive forward when no waypoints
- `ba12992` fix: reduce waypoint arrival threshold
- `4ada4cf` fix: don't skip last waypoint
- `308ee90` fix: always drive forward while turning
- `8d89122` fix: relax stuck detection thresholds
- `177930e` fix: remove step delay for full speed
- `ebd0784` fix: increase linear speed, relax stuck detection
- `f192c09` fix: rewrite frontier detector (2D FREE/UNKNOWN boundaries)
- `6a6c462` fix: stamp robot trajectory as FREE space
- `fca1da6` fix: reverse before turning in stuck recovery
- `969e49b` fix: add visual znear/zfar for depth rendering
- `bbc6f96` fix: handle both normalized and metric depth formats
- `254ba87` fix: don't rescan or terminate in first 20 steps
- `087f770` fix: raise z_min to 0.15m for ground plane exclusion
- `34f74d5` fix: add dynamic ground plane filter
- `63444d8` fix: add body-attached front_cam
- `376649d` fix: reduce dilation, increase padding
- `d182f64` fix: allow A* to start from OCCUPIED cells
- `c7cee9b` fix: increase min explore steps before termination
- `88a64f0` fix: disable early termination in multi-robot mode
- `003558d` fix: rescan check inside per-robot loop
- `fc98d2e` chore: remove debug scripts
- `7dbf069` fix: remove accidentally staged dimos submodule

## Files Created/Modified
- `src/bridge/sim_bridge.py` - Single-robot bridge with TrotGaitController integration
- `src/bridge/multi_bridge.py` - Multi-robot bridge with per-robot gait controllers
- `src/coordination/scene_builder.py` - Actuator patching before multi-robot scene assembly
- `src/exploration/exploration_loop.py` - StuckRecovery class and recovery execution
- `src/exploration/frontier_detector.py` - Rewritten to use FREE/UNKNOWN cell boundaries
- `src/exploration/occupancy_grid.py` - Ground plane filter and trajectory stamping
- `src/exploration/path_planner.py` - A* allows starting from OCCUPIED cells
- `src/control/waypoint_runner.py` - Always drives forward, no turn-in-place stalling
- `src/main.py` - Scene flag, updated spawn positions
- `tests/test_exploration_loop.py` - Stuck recovery tests added

## Decisions Made
- Body-attached front_cam replaces free camera -- free camera had incorrect transforms for point cloud generation
- Ground plane filter at z_min=0.15m excludes floor voxels that were clogging the occupancy grid
- Frontier detector rewritten because original used 3D voxel boundaries which missed 2D navigation frontiers
- A* must allow OCCUPIED start cells because the robot's own ground contact creates occupied voxels at its position
- Stuck detection thresholds relaxed because continuous gait produces small position deltas even when moving normally
- Multi-robot early termination disabled because premature termination prevented meaningful exploration

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Depth rendering produced all-zero values**
- **Found during:** Task 3 verification
- **Issue:** MuJoCo depth buffer returned normalized [0,1] values but code expected metric meters
- **Fix:** Added format detection (checks value range) and conversion for both formats; added znear/zfar camera parameters
- **Files modified:** src/bridge/sim_bridge.py, src/bridge/multi_bridge.py
- **Committed in:** bbc6f96, 969e49b

**2. [Rule 1 - Bug] Free camera produced incorrect point cloud transforms**
- **Found during:** Task 3 verification
- **Issue:** Free camera position != robot position, causing point clouds to map to wrong locations
- **Fix:** Added body-attached front_cam to XML, used it instead of free camera
- **Files modified:** src/locomotion/xml_patcher.py, src/bridge/sim_bridge.py
- **Committed in:** 63444d8

**3. [Rule 1 - Bug] Ground plane voxels clogged occupancy grid**
- **Found during:** Task 3 verification
- **Issue:** Floor voxels filled the occupancy grid, blocking all navigation
- **Fix:** Added dynamic ground plane filter with z_min=0.15m threshold
- **Files modified:** src/exploration/occupancy_grid.py
- **Committed in:** 34f74d5, 087f770

**4. [Rule 1 - Bug] Frontier detector found no frontiers**
- **Found during:** Task 3 verification
- **Issue:** Original 3D voxel-based frontier detection missed navigable 2D frontiers
- **Fix:** Rewritten to use FREE-to-UNKNOWN cell boundaries on projected 2D grid
- **Files modified:** src/exploration/frontier_detector.py
- **Committed in:** f192c09

**5. [Rule 1 - Bug] A* pathfinding rejected valid start positions**
- **Found during:** Task 3 verification
- **Issue:** Robot's own ground contact created OCCUPIED cells at its position, A* refused to start
- **Fix:** Allow A* to start from OCCUPIED cells
- **Files modified:** src/exploration/path_planner.py
- **Committed in:** d182f64

**6. [Rule 1 - Bug] Waypoint runner stalled with turn-in-place behavior**
- **Found during:** Task 3 verification
- **Issue:** Robot would stop and turn in place instead of driving forward while turning
- **Fix:** Always drive forward when turning toward waypoints
- **Files modified:** src/control/waypoint_runner.py
- **Committed in:** 308ee90

**7. [Rule 1 - Bug] Stuck detection false positives with continuous gait**
- **Found during:** Task 3 verification
- **Issue:** Continuous gait produces small position deltas triggering false stuck detection
- **Fix:** Relaxed stuck detection thresholds
- **Files modified:** src/exploration/exploration_loop.py, src/exploration/config.py
- **Committed in:** 8d89122, ebd0784

**8. [Rule 1 - Bug] Multi-robot early termination**
- **Found during:** Task 3 verification
- **Issue:** Both robots terminated prematurely before meaningful exploration
- **Fix:** Disabled early termination, run full max_steps
- **Files modified:** src/coordination/coordinator.py
- **Committed in:** 88a64f0

---

**Total deviations:** 8 auto-fixed (all Rule 1 - bugs discovered during human verification)
**Impact on plan:** All fixes were necessary for correct robot locomotion and navigation. The original plan correctly identified the integration points but the runtime behavior exposed multiple interdependent bugs in the sensor-to-navigation pipeline. No scope creep -- all fixes directly support the plan objective of making robots walk.

## Issues Encountered
- Extensive debugging cycle during human verification revealed that locomotion integration exposed latent bugs throughout the sensor-to-navigation pipeline (depth, camera, occupancy, frontiers, pathfinding, waypoints)
- Each fix often revealed the next issue in the pipeline, requiring iterative debugging

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 5 is complete -- robots physically walk and explore
- Phase 4 Plan 2 (visualization wiring) remains incomplete but is independent of locomotion
- The full pipeline works end-to-end: locomotion, depth sensing, SLAM, frontier detection, path planning, and multi-robot voxel merging

## Self-Check: PASSED

All 10 key commits verified present. SUMMARY.md file exists on disk.

---
*Phase: 05-robot-locomotion-fix*
*Completed: 2026-03-18*
