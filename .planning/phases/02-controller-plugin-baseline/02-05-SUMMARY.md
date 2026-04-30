---
phase: 02-controller-plugin-baseline
plan: 05
subsystem: bridge
tags: [python, pytest, mujoco, multi-robot, controller, locomotion]

requires:
  - phase: 02-controller-plugin-baseline
    provides: Locomotion controller registry from Plan 02-01 and shared dispatch/application helpers from Plan 02-02
provides:
  - MultiRobotBridge controller loop backed by one registered analytical_trot controller per robot id
  - Regression tests for MultiRobotBridge step public contract, per-robot controller isolation, pre-start error behavior, and indexed control writes
affects: [controller-plugin-baseline, bridge-dispatch, multi-robot-control, benchmark-runtime]

tech-stack:
  added: []
  patterns: [Per-robot registered controller instances, validate-before-indexed-control-write, fake-started MuJoCo-free bridge tests]

key-files:
  created: []
  modified:
    - src/bridge/multi_bridge.py
    - tests/bridge/test_multi_bridge.py

key-decisions:
  - "Keep MultiRobotBridge.step as def step(self) -> dict[str, SensorFrame] while changing only internal controller dispatch."
  - "Create one ControllerRegistry.create(\"analytical_trot\") instance per robot id at bridge construction time to preserve state isolation."
  - "Use compute_controller_action and apply_controller_target for standing setup and per-step indexed data.ctrl writes."

patterns-established:
  - "Multi-robot bridge controller state is stored as _controllers keyed by configured robot id, not as a shared singleton."
  - "Multi-robot control writes route through apply_controller_target(..., ctrl_indices=self._ctrl_indices[robot_id]) after controller output validation."
  - "Bridge contract tests use inspect.signature for public API preservation and fake-started bridge state to avoid real MuJoCo."

requirements-completed: [LOC-CTRL-02, LOC-CTRL-04]

duration: 3min 12s
completed: 2026-04-30
---

# Phase 2 Plan 05: Multi-Robot Bridge Controller Seam Summary

**MultiRobotBridge now uses isolated per-robot analytical_trot registry controllers with shared validated indexed control writes and unchanged dict SensorFrame returns.**

## Performance

- **Duration:** 3min 12s
- **Started:** 2026-04-30T12:56:26Z
- **Completed:** 2026-04-30T12:59:38Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added focused MuJoCo-free regression tests asserting the `MultiRobotBridge.step` public no-argument `dict[str, SensorFrame]` contract, pre-start `RuntimeError`, one distinct controller per robot id, and fake-started indexed per-robot actuator writes.
- Replaced `MultiRobotBridge`'s private per-robot `TrotGaitController` objects with per-robot `ControllerRegistry.create("analytical_trot")` instances.
- Routed standing setup and step-time velocity commands through `command_from_velocity`, `compute_controller_action`, and `apply_controller_target(..., ctrl_indices=self._ctrl_indices[robot_id])`, preserving per-robot state isolation and validated `(12,)` target writes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend multi-bridge tests for per-robot controller seam and public contract preservation** - `b8bb033` (test)
2. **Task 2: Refactor MultiRobotBridge internals to per-robot registered analytical controllers** - `1770131` (feat)

**Plan metadata:** pending final docs commit

_Note: This plan followed the TDD gate with RED tests committed before GREEN implementation._

## Files Created/Modified

- `tests/bridge/test_multi_bridge.py` - Added contract, controller-isolation, pre-start lifecycle, and fake-started indexed-write regression coverage.
- `src/bridge/multi_bridge.py` - Replaced `_gaits` with registered per-robot `_controllers` and shared dispatch/application helpers for standing and step controls.

## Decisions Made

- Preserved `MultiRobotBridge.step` exactly as the existing no-argument dict-return bridge API; no C2/frontend selection or public bridge API rewrite was introduced.
- Used registry-created controller instances during bridge initialization so every robot receives independent gait phase/controller state before any start/step lifecycle work.
- Kept MuJoCo-free tests by patching a minimal `mujoco.mj_step` module and fake bridge state instead of requiring real MuJoCo model loading.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Completed fake-started bridge test state for viewer attribute**
- **Found during:** Task 2 (Refactor MultiRobotBridge internals to per-robot registered analytical controllers)
- **Issue:** The fake-started test bypassed `start()`, so `_viewer_handle` was not initialized before `step()` reached the existing viewer-sync guard.
- **Fix:** Set `bridge._viewer_handle = None` in the fake-started regression test setup, matching the non-viewer path initialized by `start()`.
- **Files modified:** `tests/bridge/test_multi_bridge.py`
- **Verification:** `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/bridge/test_multi_bridge.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_controller_dispatch.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_controller_protocol.py -q -x` passed.
- **Committed in:** `1770131` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking test setup issue)
**Impact on plan:** No scope creep. The adjustment made the planned fake-started MuJoCo-free test accurately model the existing started bridge state.

## Issues Encountered

- Task 1 RED verification failed as expected before implementation with `AttributeError: 'MultiRobotBridge' object has no attribute '_controllers'`.
- Pytest emitted existing configuration warnings for `asyncio_default_fixture_loop_scope` and `asyncio_mode`; these warnings are unrelated to this plan and did not affect test results.

## Verification

- RED: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/bridge/test_multi_bridge.py -q -x` failed before implementation with missing `_controllers` on `MultiRobotBridge`.
- Task 1 acceptance criteria passed after test creation: `inspect.signature` count 1, `_controllers` count 6, `is not` count 1, `dict` count 2.
- GREEN/final: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/tests/bridge/test_multi_bridge.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_controller_dispatch.py /home/prannayag/pragnition/robotics/argus/tests/locomotion/test_locomotion_controller_protocol.py -q -x` passed: 30 passed, 2 warnings.
- Task 2 acceptance criteria passed: `_controllers` count 3, `ControllerRegistry.create("analytical_trot")` count 1, `apply_controller_target` count 3, `ctrl_indices=self._ctrl_indices[robot_id]` count 2, exact `step` signature count 1, `_gaits` count 0.

## Known Stubs

None. The new tests use fake MuJoCo data and a fake `mujoco.mj_step` module intentionally to keep regression coverage fast and MuJoCo-free; production multi-bridge code is wired to the registered controller seam.

## Threat Flags

None beyond the plan threat model. The per-robot controller state boundary and controller-to-indexed-`data.ctrl` write boundary were covered by T-2-01, T-2-03, and T-2-04 mitigations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02-06 can rely on both single-robot and multi-robot bridge paths using the registered analytical baseline through the shared controller dispatch/application seam. Multi-robot public dict returns and per-robot controller isolation are pinned by tests.

## TDD Gate Compliance

- RED gate commit exists: `b8bb033` (`test(02-05): add failing multi-bridge controller seam tests`).
- GREEN gate commit exists after RED: `1770131` (`feat(02-05): use per-robot registered multi-bridge controllers`).
- REFACTOR gate not needed.

## Self-Check: PASSED

- Found `src/bridge/multi_bridge.py`.
- Found `tests/bridge/test_multi_bridge.py`.
- Found task commit `b8bb033`.
- Found task commit `1770131`.

---
*Phase: 02-controller-plugin-baseline*
*Completed: 2026-04-30*
