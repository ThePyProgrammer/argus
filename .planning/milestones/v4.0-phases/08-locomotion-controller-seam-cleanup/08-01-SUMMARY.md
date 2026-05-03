---
phase: 08-locomotion-controller-seam-cleanup
plan: 01
subsystem: locomotion-controller-seam-cleanup
tags:
  - locomotion
  - multi-robot-bridge
  - controller-validation
dependency_graph:
  requires:
    - src/bridge/multi_bridge.py
    - src/locomotion/controller_dispatch.py
  provides:
    - LOC-CTRL-04 explicit multi-robot platform controller boundary
    - all-or-nothing platform controller target validation before data.ctrl mutation
  affects:
    - tests/bridge/test_multi_bridge.py
    - tests/bridge/test_multi_bridge_platform_selection.py
tech_stack:
  added: []
  patterns:
    - fake-runtime pytest bridge regressions
    - NumPy finite/shape/index validation before mutation
    - platform-local controller construction via platform.make_controller(robot_id)
key_files:
  created:
    - .planning/phases/08-locomotion-controller-seam-cleanup/08-01-SUMMARY.md
  modified:
    - src/bridge/multi_bridge.py
    - tests/bridge/test_multi_bridge.py
    - tests/bridge/test_multi_bridge_platform_selection.py
decisions:
  - Preserved MultiRobotBridge as the platform-runtime controller boundary instead of forcing platform controllers through the Go2-only ControllerRegistry path.
  - Added bridge-local generic actuator-count validation modeled on apply_controller_target because non-Go2 platforms can have fewer than twelve actuators.
metrics:
  duration: ~8 minutes
  completed_date: 2026-05-02T16:33:24Z
  tasks_completed: 2
  files_changed: 4
requirements:
  - LOC-CTRL-04
---

# Phase 08 Plan 01: Multi-Robot Controller Seam Validation Summary

## One-liner

MultiRobotBridge now preserves platform-local controller construction while applying platform-sized all-or-nothing validation before any indexed `data.ctrl` mutation.

## Completed Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add fake-runtime regressions for the explicit multi-robot platform boundary and generic no-mutation validation | 314ffac | `tests/bridge/test_multi_bridge.py`, `tests/bridge/test_multi_bridge_platform_selection.py` |
| 2 | Replace MultiRobotBridge direct indexed writes with generic platform target validation | e2846ea | `src/bridge/multi_bridge.py` |

## What Changed

- Added fake-runtime bridge tests proving invalid non-finite controller output raises before mutating `bridge._data.ctrl`.
- Added duplicate and out-of-range `ctrl_indices` regressions that assert no partial control writes occur.
- Added a one-actuator non-Go2 success path to prove generic platform actuator counts still step through the multi-robot bridge.
- Added an explicit platform-boundary test proving `MultiRobotBridge` obtains controllers from `platform.make_controller(robot_id)`.
- Added `_apply_platform_controller_target(self, robot_id: str, ctrl: np.ndarray) -> None` to validate one-dimensional float targets, target length, finite values, duplicate indices, and bounds before the single indexed assignment `self._data.ctrl[ctrl_indices] = target`.
- Replaced direct shape-only loop writes in `step()` with `_apply_platform_controller_target(robot_id, ctrl)`.
- Also routed startup standing-pose controller output through the same helper using keyword arguments, closing the same validation seam during initial control application.

## Verification

- `uv run python -m pytest tests/bridge/test_multi_bridge.py::test_multi_bridge_rejects_invalid_controller_output_without_mutating_ctrl tests/bridge/test_multi_bridge.py::test_multi_bridge_rejects_bad_ctrl_indices_without_mutating_ctrl tests/bridge/test_multi_bridge.py::test_multi_bridge_applies_fake_non_go2_one_actuator_target tests/bridge/test_multi_bridge_platform_selection.py::test_multi_bridge_platform_controller_boundary_is_explicit -q`
  - RED before implementation: 3 failed, 2 passed, as expected.
- `uv run python -m pytest tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py tests/locomotion/test_controller_dispatch.py -q`
  - PASS: 41 passed.
- `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/test_locomotion_benchmark_docs.py -q`
  - PASS: 54 passed.

## Acceptance Criteria

- `src/bridge/multi_bridge.py` defines `_apply_platform_controller_target(self, robot_id: str, ctrl: np.ndarray) -> None`.
- `src/bridge/multi_bridge.py` contains exactly one positional step-loop call to `self._apply_platform_controller_target(robot_id, ctrl)`.
- `src/bridge/multi_bridge.py` contains the post-validation indexed assignment `self._data.ctrl[ctrl_indices] = target`.
- The old direct write loop pattern `self._data.ctrl[act_id] = ctrl[i]` is removed.
- `self._platform.make_controller(rid)` remains the controller construction boundary.
- Bridge tests cover non-finite output no-mutation, bad-index no-mutation, one-actuator non-Go2 success, and explicit platform-local controller construction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Routed startup controller target application through the same validation helper**
- **Found during:** Task 2
- **Issue:** The plan focused on the `step()` control loop, but `start()` also applied per-robot controller outputs to `data.ctrl` through a direct indexed loop.
- **Fix:** Replaced the startup loop with `_apply_platform_controller_target(robot_id=robot_id, ctrl=ctrl)` so boot-time standing targets receive the same shape, finite-value, duplicate-index, and bounds validation before mutation.
- **Files modified:** `src/bridge/multi_bridge.py`
- **Commit:** e2846ea

## Threat Flags

None. This plan reduced the existing platform-controller-to-physics mutation threat surface and introduced no new network endpoints, auth paths, file access patterns, or schema trust boundaries.

## Known Stubs

None found in created or modified files during the stub scan.

## Auth Gates

None.

## Deferred Issues

None.

## Self-Check: PASSED

- FOUND: `.planning/phases/08-locomotion-controller-seam-cleanup/08-01-SUMMARY.md`
- FOUND: `src/bridge/multi_bridge.py`
- FOUND: `tests/bridge/test_multi_bridge.py`
- FOUND: `tests/bridge/test_multi_bridge_platform_selection.py`
- FOUND: commit `314ffac`
- FOUND: commit `e2846ea`
