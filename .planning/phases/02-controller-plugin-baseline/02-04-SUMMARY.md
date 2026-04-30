---
phase: 02-controller-plugin-baseline
plan: 04
subsystem: locomotion
tags: [python, pytest, bridge, controller, dispatch, mujoco]

requires:
  - phase: 02-controller-plugin-baseline
    provides: LocomotionCommand, ControllerRegistry, AnalyticalTrotController, and controller_dispatch helpers from Plans 02-01 and 02-02
provides:
  - Single-robot MuJoCoBridge control path backed by registered analytical_trot controller
  - Validated direct-action and velocity-derived data.ctrl writes through apply_controller_target
  - Regression tests preserving MuJoCoBridge step signature, SensorFrame return behavior, pre-start error, and velocity buffering
affects: [controller-plugin-baseline, bridge-dispatch, locomotion-env, c2-runtime]

tech-stack:
  added: []
  patterns: [registered analytical bridge controller, validate-before-mutate control sink, fake-started bridge unit tests]

key-files:
  created: []
  modified:
    - tests/bridge/test_sim_bridge.py
    - src/bridge/sim_bridge.py

key-decisions:
  - "Keep MuJoCoBridge public lifecycle unchanged while replacing bridge-private TrotGaitController ownership with ControllerRegistry.create(\"analytical_trot\")."
  - "Route both direct 12-element actions and velocity-buffered controller output through apply_controller_target before data.ctrl mutation."
  - "Expose a bridge-private _velocity_command helper so tests and future bridge integration can verify typed command construction without changing the public API."

patterns-established:
  - "MuJoCoBridge owns one registered controller instance per bridge object and resets it during start settling."
  - "_velocity_to_ctrl composes command_from_velocity with compute_controller_action and returns an already validated 12-joint action."
  - "Unit bridge tests fake _model, _data.ctrl, _capture_frame, and mujoco.mj_step to verify control writes without real MuJoCo."

requirements-completed: [LOC-CTRL-02, LOC-CTRL-04]

duration: 2min 30s
completed: 2026-04-30
---

# Phase 2 Plan 04: Single-Robot Bridge Controller Seam Summary

**MuJoCoBridge now obtains analytical walking targets through the registered analytical_trot controller seam and validates all direct or computed targets before control-sink writes.**

## Performance

- **Duration:** 2min 30s
- **Started:** 2026-04-30T12:56:20Z
- **Completed:** 2026-04-30T12:58:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added focused `tests/bridge/test_sim_bridge.py` regression coverage for the exact `step(action: np.ndarray | None = None) -> SensorFrame` contract, registered analytical controller ownership, pre-start `not started` behavior, velocity buffering, fake-started direct actions, and fake-started `action=None` controller dispatch.
- Refactored `src/bridge/sim_bridge.py` so each `MuJoCoBridge` creates one `ControllerRegistry.create("analytical_trot")` controller instance instead of owning `TrotGaitController` directly.
- Replaced raw `data.ctrl[:]` writes for direct actions, standing settle targets, and velocity-derived targets with `apply_controller_target`, with velocity conversion flowing through `command_from_velocity` and `compute_controller_action`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend single-bridge tests for controller seam and public contract preservation** - `a0883cb` (test)
2. **Task 2: Refactor MuJoCoBridge internals to registered analytical controller seam** - `c67eef7` (feat)

**Plan metadata:** pending final docs commit

_Note: This plan followed the TDD gate with RED tests committed before GREEN implementation._

## Files Created/Modified

- `tests/bridge/test_sim_bridge.py` - Added public-contract, registered-controller, direct-action validation, and velocity dispatch regression tests using fake bridge state and patched MuJoCo stepping.
- `src/bridge/sim_bridge.py` - Replaced direct gait-controller ownership and raw control writes with the registered controller and shared dispatch/application helpers.

## Decisions Made

- Kept controller selection internal and fixed to `analytical_trot`; user-facing C2 controller selection remains deferred per Phase 2 scope.
- Used `command_from_velocity` inside a private `_velocity_command()` helper to keep existing `set_velocity()` buffering semantics observable without changing the public bridge API.
- Reset the registered controller before the start-settling loop so bridge starts begin from deterministic controller-local gait state.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 1 RED verification failed as expected with `AttributeError: 'MuJoCoBridge' object has no attribute '_controller'` before implementation.
- Pytest emitted existing configuration warnings for `asyncio_default_fixture_loop_scope` and `asyncio_mode`; these warnings are unrelated to this plan and did not affect test results.
- Concurrent Wave 3 changes appeared in `src/bridge/multi_bridge.py` and `tests/bridge/test_multi_bridge.py`; they were left unstaged and untouched because this plan owns only single-robot bridge files.

## Verification

- RED: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/bridge/test_sim_bridge.py -q -x` failed before implementation with missing `_controller` on `MuJoCoBridge`.
- GREEN/final: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/bridge/test_sim_bridge.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_controller_dispatch.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_controller_protocol.py -q -x` passed: 35 passed, 2 warnings.
- Acceptance grep criteria passed for both tasks.

## Known Stubs

None. The stub-pattern scan only matched normal optional/lifecycle initialization (`None` fields), empty local containers, and the required `action: np.ndarray | None = None` signature; no UI-facing or unwired placeholder behavior was introduced.

## Threat Flags

None beyond the plan threat model. The direct-action and velocity-buffer trust boundaries are covered by validation through `apply_controller_target` and `compute_controller_action`, and the public bridge contract is pinned by tests.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The single-robot bridge now uses the same registered analytical controller seam as the locomotion dispatch helpers. Multi-robot bridge and environment metadata plans can integrate the same validation pattern without depending on any public API changes in `MuJoCoBridge`.

## TDD Gate Compliance

- RED gate commit exists: `a0883cb` (`test(02-04): add failing single bridge controller seam tests`).
- GREEN gate commit exists after RED: `c67eef7` (`feat(02-04): route single bridge controls through controller seam`).
- REFACTOR gate not needed.

## Self-Check: PASSED

- Found `tests/bridge/test_sim_bridge.py`.
- Found `src/bridge/sim_bridge.py`.
- Found `.planning/phases/02-controller-plugin-baseline/02-04-SUMMARY.md`.
- Found task commit `a0883cb`.
- Found task commit `c67eef7`.

---
*Phase: 02-controller-plugin-baseline*
*Completed: 2026-04-30*
