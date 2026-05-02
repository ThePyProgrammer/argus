---
phase: 08-locomotion-controller-seam-cleanup
plan: 02
subsystem: locomotion-controller-registry
tags:
  - locomotion
  - controller-registry
  - documentation
  - tests
requirements:
  - LOC-CTRL-03
  - LOC-REPORT-02
dependency_graph:
  requires:
    - src/locomotion/actions.py
    - src/locomotion/controllers.py
    - docs/locomotion-benchmark.md
  provides:
    - explicit WBC unavailable/deferred action-contract metadata
    - registry/docs drift guards for WBC placeholder vocabulary
  affects:
    - ControllerRegistry.list_controllers()
    - docs/locomotion-benchmark.md controller-family matrix
tech_stack:
  added: []
  patterns:
    - pytest registry contract guards
    - Markdown documentation drift guards
    - unavailable placeholder metadata under existing capability fields
key_files:
  created:
    - .planning/phases/08-locomotion-controller-seam-cleanup/08-02-SUMMARY.md
  modified:
    - src/locomotion/controllers.py
    - docs/locomotion-benchmark.md
    - tests/locomotion/test_locomotion_controller_registry.py
    - tests/test_locomotion_benchmark_docs.py
decisions:
  - WBC remains registered and unavailable, but its future action contract is named undefined_deferred and is not a v4.0 env action mode.
  - The v4.0 env action-mode catalog remains limited to velocity_command, joint_position, and residual_baseline.
metrics:
  duration_seconds: 138
  completed_at: 2026-05-02T16:33:24Z
  tasks_completed: 2
  files_modified: 4
commits:
  - ad2659e
  - 7b5fd37
---

# Phase 08 Plan 02: WBC Placeholder Metadata Cleanup Summary

## One-liner

WBC placeholder metadata now advertises an explicit unavailable future action contract, `undefined_deferred`, with registry and documentation guards proving it is not a runnable v4.0 environment action mode.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add WBC placeholder vocabulary and evaluator-preservation regressions | ad2659e | `tests/locomotion/test_locomotion_controller_registry.py`, `tests/test_locomotion_benchmark_docs.py` |
| 2 | Update WBC registry metadata and controller-family docs to explicit deferred vocabulary | 7b5fd37 | `src/locomotion/controllers.py`, `docs/locomotion-benchmark.md` |

## What Changed

- Added `test_wbc_placeholder_advertises_deferred_action_contract` to assert that the `wbc` registry entry is unavailable, uses `capabilities["action_mode"] == "undefined_deferred"`, does not appear in `available_action_modes()`, and stores `model_requirements["action_contract"] == "undefined_deferred"` plus `env_action_mode is None`.
- Added `test_wbc_documentation_matches_registry_deferred_action_contract` to keep the benchmark guide aligned with WBC registry metadata and to prevent reintroducing `torque_or_joint_position` documentation drift.
- Updated `WBCController.CAPABILITIES` to build from `_placeholder_capabilities("wbc", "undefined_deferred")` and annotate WBC-only model requirements with the deferred action contract and `env_action_mode = None`.
- Updated the controller-family matrix row for WBC to state: `Controller id `wbc`; future action contract `undefined_deferred` (not a v4.0 env action mode)`.

## Verification

- RED gate for Task 1 failed as expected before implementation:
  - `uv run python -m pytest tests/locomotion/test_locomotion_controller_registry.py::test_wbc_placeholder_advertises_deferred_action_contract tests/test_locomotion_benchmark_docs.py::test_wbc_documentation_matches_registry_deferred_action_contract tests/locomotion/test_locomotion_evaluation_runner.py::test_unknown_action_mode_fails_before_env_construction tests/locomotion/test_locomotion_evaluation_runner.py::test_unsupported_action_modes_fail_before_env_construction -q`
  - Result: 2 failed, 3 passed because registry/docs still used `torque_or_joint_position`.
- Task 2 verification:
  - `uv run python -m pytest tests/locomotion/test_locomotion_controller_registry.py tests/test_locomotion_benchmark_docs.py tests/locomotion/test_locomotion_evaluation_runner.py::test_unknown_action_mode_fails_before_env_construction tests/locomotion/test_locomotion_evaluation_runner.py::test_unsupported_action_modes_fail_before_env_construction -q`
  - Result: 24 passed.
- Phase quick verification:
  - `uv run python -m pytest tests/locomotion/test_controller_dispatch.py tests/locomotion/test_locomotion_controller_registry.py tests/bridge/test_multi_bridge.py tests/test_locomotion_benchmark_docs.py -q`
  - Result: 52 passed.

## TDD Gate Compliance

- RED commit present: `ad2659e test(08-02): add WBC deferred contract regressions`.
- GREEN commit present after RED: `7b5fd37 fix(08-02): clarify WBC deferred action contract`.
- No refactor commit was needed.

## Deviations from Plan

None - plan executed exactly as written.

## Auth Gates

None.

## Known Stubs

None introduced. Existing placeholder terminology remains intentional for unavailable future controller families and is part of the v4.0 controller seam contract.

## Threat Flags

None. This plan changed registry metadata, documentation, and tests only; it did not introduce new endpoints, auth paths, file access patterns, or schema trust boundaries.

## Self-Check: PASSED

- Found summary file at `.planning/phases/08-locomotion-controller-seam-cleanup/08-02-SUMMARY.md`.
- Found modified implementation/docs files on disk.
- Found task commits `ad2659e` and `7b5fd37` in git history.
