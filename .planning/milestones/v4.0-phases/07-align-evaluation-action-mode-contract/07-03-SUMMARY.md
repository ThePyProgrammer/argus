---
phase: 07-align-evaluation-action-mode-contract
plan: 03
subsystem: locomotion evaluation CLI matrix-config contract
tags:
  - locomotion
  - evaluation
  - cli
  - matrix-config
  - documentation
dependency_graph:
  requires:
    - 07-01
    - 07-02
  provides:
    - explicit-only eval-locomotion scalar override semantics
    - CLI regression coverage for matrix-config action-mode fail-fast behavior
    - clean benchmark guide action-mode inline-code contract
  affects:
    - src/main.py
    - tests/test_main_args.py
    - docs/locomotion-benchmark.md
tech_stack:
  added: []
  patterns:
    - argparse None defaults distinguish absent scalar flags from explicit overrides
    - loaded EvaluationMatrix remains the base object for matrix-config scalar merge
    - subprocess CLI tests use sys.executable for active-interpreter portability
key_files:
  created:
    - .planning/phases/07-align-evaluation-action-mode-contract/07-03-SUMMARY.md
  modified:
    - src/main.py
    - tests/test_main_args.py
    - docs/locomotion-benchmark.md
decisions:
  - Matrix-config scalar values are authoritative unless the user supplies an explicit scalar CLI override.
  - Direct CLI defaults continue to come from EvaluationMatrix defaults while parser scalar defaults stay None for override detection.
metrics:
  duration: 6min 36s
  completed_date: 2026-05-02T07:19:26Z
  tasks_completed: 3
  files_changed: 4
requirements_completed:
  - LOC-ENV-04
  - LOC-EVAL-03
---

# Phase 07 Plan 03: Matrix-Config Scalar Merge Contract Summary

## One-liner

`eval-locomotion --matrix-config` now preserves JSON scalar values unless scalar CLI flags are explicitly supplied, so unsupported matrix-config action modes reach evaluation validation and fail before artifacts.

## Performance

- **Started:** 2026-05-02T07:12:50Z
- **Completed:** 2026-05-02T07:19:26Z
- **Duration:** 6min 36s
- **Tasks:** 3
- **Files changed:** 4 including this summary

## Accomplishments

- Added CLI regressions proving parser scalar override defaults are `None`, matrix-config `joint_position` fails fast before output-root creation, matrix-config scalar values are preserved when CLI scalar flags are absent, and explicit scalar CLI flags override JSON values.
- Replaced hardcoded developer `.venv/bin/python` subprocess paths in CLI tests with `sys.executable`.
- Changed `eval-locomotion` parser scalar defaults for `--action-mode`, `--max-episode-steps`, `--sim-steps-per-frame`, and `--heightfield-size` to `None` while preserving output-root default behavior.
- Updated `run_eval_locomotion_mode()` to rebuild `EvaluationMatrix` from the loaded matrix and only replace scalar fields when the corresponding parsed CLI argument is non-`None`.
- Fixed malformed inline-code markup in the benchmark guide action-mode contract sentence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add CLI matrix-config scalar merge regressions | d12d514 | tests/test_main_args.py |
| 2 | Fix eval-locomotion argparse defaults and explicit-only scalar merging | 2eaf0e9 | src/main.py |
| 3 | Clean action-mode docs markup and run phase gap gate | 28c4426 | docs/locomotion-benchmark.md |

## Verification

- `uv run python -m pytest tests/test_main_args.py -q` after RED tests -> expected failure: 3 failed, 8 passed. Failures proved parser scalar defaults and matrix-config merge behavior were still broken.
- `uv run python -m pytest tests/test_main_args.py -q` after implementation -> 11 passed.
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` -> 77 passed.
- Final repeat gates:
  - `uv run python -m pytest tests/test_main_args.py -q` -> 11 passed.
  - `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` -> 77 passed.

## Decisions Made

- Matrix-config scalar fields are the base configuration for `eval-locomotion`; CLI scalar flags are treated as overrides only when explicitly present.
- The direct no-config CLI path relies on `EvaluationMatrix()` defaults for `velocity_command`, `500`, `10`, and `16`, plus the argparse default output root `outputs/locomotion-evals`.
- CLI subprocess tests use `sys.executable` so the tested command runs in the same interpreter environment as pytest.

## Deviations from Plan

None - plan executed as written.

## Auth Gates

None.

## Known Stubs

The stub scan found only intentional deferred-controller documentation in `docs/locomotion-benchmark.md` lines 119-122 and legitimate test/parser sentinel values in `tests/test_main_args.py` and `src/main.py` (`None` marks absent CLI overrides; empty `episode_rows` is fake-result test data). These do not block the plan goal.

## Threat Flags

None. The plan modified existing CLI merge behavior, tests, and documentation at trust boundaries already listed in the plan threat model; it introduced no new network endpoints, auth paths, schema changes, or additional filesystem write surfaces.

## Deferred Issues

None.

## Self-Check: PASSED

Verified created/modified files exist and task commits are present in git history:

- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a54003d2dc22a82b0/src/main.py`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a54003d2dc22a82b0/tests/test_main_args.py`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a54003d2dc22a82b0/docs/locomotion-benchmark.md`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a54003d2dc22a82b0/.planning/phases/07-align-evaluation-action-mode-contract/07-03-SUMMARY.md`
- FOUND commits: `d12d514`, `2eaf0e9`, `28c4426`
