---
phase: 05-robot-locomotion-fix
plan: 01
subsystem: locomotion
tags: [mujoco, quadruped, gait-controller, position-actuators, go2, tdd]

# Dependency graph
requires:
  - phase: 03-multi-robot
    provides: "scene_builder.py XML generation, MultiRobotBridge"
provides:
  - "src/locomotion/ module with TrotGaitController, GaitParams, patch_actuators_to_position"
  - "Position-controlled actuator patching for Go2 MJCF"
  - "Analytical trot gait producing 12 joint targets from (vx, vy, omega)"
  - "patch_actuators_to_position_with_floor for standalone physics testing"
affects: [bridge-integration, exploration-loop, multi-robot-coordination]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Runtime XML patching for actuator type conversion (no upstream file modification)"
    - "TDD with MuJoCo physics integration tests (not just unit tests)"
    - "Differential stride turning for analytical quadruped gait"

key-files:
  created:
    - src/locomotion/__init__.py
    - src/locomotion/gait_controller.py
    - src/locomotion/gait_params.py
    - src/locomotion/xml_patcher.py
    - tests/test_locomotion.py
  modified: []

key-decisions:
  - "PD gains kp=80/120 kv=4/6 (2x research recommendation) for reliable servo tracking"
  - "Gait frequency=3.0 Hz for sufficient stride cycles per exploration step"
  - "Differential stride turning instead of hip-abduction-only (produces actual yaw torque)"
  - "Calf tucking (more negative) during swing for ground clearance -- opposite of initial plan"
  - "stride_length=0.4 and swing_height=0.15 (joint-angle scale, not meters)"

patterns-established:
  - "XML patcher returns string, never modifies upstream go2.xml on disk"
  - "Integration tests use patch_actuators_to_position_with_floor for standalone MuJoCo physics"
  - "Assets dict loaded from models/unitree_go2/assets/ for from_xml_string calls"

requirements-completed: [LOCO-01, LOCO-02, LOCO-03]

# Metrics
duration: 17min
completed: 2026-03-18
---

# Phase 5 Plan 1: Locomotion Module Summary

**Analytical trot gait controller with position-actuator XML patching, producing >0.5m forward displacement and >45-degree turning in MuJoCo physics**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-18T04:39:10Z
- **Completed:** 2026-03-18T04:56:47Z
- **Tasks:** 2 (both TDD)
- **Files created:** 5

## Accomplishments
- XML patcher converts all 12 Go2 motor actuators to position-controlled servos with PD gains
- TrotGaitController produces 12 joint targets from (vx, vy, omega) with swing/stance phases
- Robot verified to translate >0.5m forward in 100 steps (MuJoCo physics)
- Robot verified to turn >45 degrees in 100 steps (MuJoCo physics)
- Robot stays within 0.1m drift with zero velocity command
- All 14 tests pass (6 patcher, 1 params, 4 controller, 3 integration)

## Task Commits

Each task was committed atomically:

1. **Task 1: XML patcher and GaitParams dataclass** - `673caa4` (feat -- TDD RED+GREEN)
2. **Task 1.5: Failing tests for TrotGaitController** - `c0c45af` (test -- TDD RED)
3. **Task 2: TrotGaitController with movement verification** - `df86c4a` (feat -- TDD GREEN)

## Files Created/Modified
- `src/locomotion/__init__.py` - Module exports (TrotGaitController, GaitParams, patch_actuators_to_position)
- `src/locomotion/gait_controller.py` - TrotGaitController with diagonal pair trot gait and differential stride turning
- `src/locomotion/gait_params.py` - Frozen dataclass with keyframe-derived standing pose values
- `src/locomotion/xml_patcher.py` - MJCF motor-to-position conversion with PD gains
- `tests/test_locomotion.py` - 14 tests covering patcher, params, controller, and MuJoCo integration

## Decisions Made
- **PD gains doubled from research values:** kp=80/120 kv=4/6 instead of kp=40/60 kv=2/3. The research-recommended values produced insufficient position tracking at the joint level, leading to only 0.47m displacement. Higher gains provide aggressive servo tracking needed for ground reaction forces.
- **Differential stride turning:** Hip abduction alone produces negligible yaw torque (<7 degrees). Differential stride length (right side pushes harder for left turn) generates actual yaw through asymmetric ground forces. Hip abduction retained as secondary assist.
- **Calf direction correction:** The plan specified `calf = standing_calf + lift * 1.5` (less negative = extending lower leg). This moves the foot DOWN, not up. Corrected to `calf = standing_calf - lift * 2.0` (more negative = tucking knee = foot rises for clearance).
- **Gait frequency 3.0 Hz:** Original 2.0 Hz produced only 4 gait cycles in the 100-step test (2s sim time), insufficient for 0.5m displacement. 3.0 Hz gives 6 cycles with better coverage.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Missing ground plane in standalone go2.xml**
- **Found during:** Task 2 (MuJoCo integration tests)
- **Issue:** go2.xml has no floor geom; robot falls through infinity when loaded standalone
- **Fix:** Added `patch_actuators_to_position_with_floor()` variant that injects floor geom + light
- **Files modified:** src/locomotion/xml_patcher.py
- **Verification:** Robot settles at z=0.25 after 500 steps
- **Committed in:** df86c4a (Task 2 commit)

**2. [Rule 1 - Bug] Swing foot dragging backward**
- **Found during:** Task 2 (robot moved backward instead of forward)
- **Issue:** Swing phase calf correction was `+lift*1.5` (extending leg = foot down) instead of `-lift*2.0` (tucking = foot up). Swing feet dragged on ground, canceling stance push.
- **Fix:** Reversed calf direction and increased lift multiplier for clearance
- **Files modified:** src/locomotion/gait_controller.py
- **Verification:** Robot moves forward 0.5+ meters in 100 steps
- **Committed in:** df86c4a (Task 2 commit)

**3. [Rule 1 - Bug] Weak turning via hip abduction only**
- **Found during:** Task 2 (robot turned only 6.8 degrees in 50 steps)
- **Issue:** Hip abduction offset of 0.05*omega produces negligible yaw torque
- **Fix:** Implemented differential stride turning (asymmetric left/right push) as primary mechanism, hip abduction as secondary
- **Files modified:** src/locomotion/gait_controller.py
- **Verification:** Robot turns >45 degrees in 100 steps
- **Committed in:** df86c4a (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All fixes were essential for the robot to actually move. The plan's gait mechanics had incorrect calf direction and insufficient turning mechanism. No scope creep.

## Issues Encountered
- Nix-built Python venv requires `nix develop` wrapper for shared library resolution (libstdc++)
- MuJoCo `from_xml_string` requires explicit assets dict when XML references mesh files via relative paths

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Locomotion module ready for integration into MuJoCoBridge._velocity_to_ctrl() and MultiRobotBridge._velocity_to_ctrl()
- Both bridges need to: (1) patch actuators at model load time, (2) instantiate TrotGaitController, (3) call compute() in _velocity_to_ctrl()
- Stuck recovery (turn-in-place) deferred to bridge integration plan

---
*Phase: 05-robot-locomotion-fix*
*Completed: 2026-03-18*
