---
phase: 07-align-evaluation-action-mode-contract
plan: 02
subsystem: locomotion evaluation CLI and documentation
tags:
  - locomotion
  - evaluation
  - cli
  - documentation
dependency_graph:
  requires:
    - 07-VALIDATION.md
    - 07-PATTERNS.md
  provides:
    - eval-locomotion action-mode help contract
    - benchmark guide action-mode contract guard
  affects:
    - src/main.py
    - docs/locomotion-benchmark.md
    - tests/test_main_args.py
    - tests/test_locomotion_benchmark_docs.py
tech_stack:
  added: []
  patterns:
    - argparse RawTextHelpFormatter for exact public contract wording
    - pytest content guards for CLI help and Markdown drift
key_files:
  created:
    - .planning/phases/07-align-evaluation-action-mode-contract/07-02-SUMMARY.md
  modified:
    - src/main.py
    - docs/locomotion-benchmark.md
    - tests/test_main_args.py
    - tests/test_locomotion_benchmark_docs.py
decisions:
  - Keep velocity_command as the only evaluator-runnable action mode in user-facing help and docs.
  - Keep joint_position and residual_baseline visible as environment seams while labeling them fail-fast for evaluation until explicit action sources exist.
metrics:
  duration: not recorded
  completed_date: 2026-05-02T06:01:11Z
  tasks_completed: 3
  files_changed: 5
---

# Phase 07 Plan 02: Align Evaluation Action-Mode Contract Summary

## One-liner

CLI help and benchmark docs now explicitly state that `velocity_command` is the current evaluator-runnable mode while `joint_position` and `residual_baseline` remain fail-fast environment seams until action sources exist.

## What Changed

- Added regression guards for `argus eval-locomotion --help` so the action-mode contract cannot silently drift.
- Added Markdown content guards for the benchmark guide's evaluator action-mode wording.
- Updated `eval-locomotion --action-mode` help with the exact runnable/deferred contract and preserved the `velocity_command` default.
- Kept CLI startup import-safe by lazily importing MCP web dependencies inside `run_web_mode()` instead of at `src.main` import time.
- Updated the benchmark guide action-mode section to separate environment-supported seams from currently evaluator-runnable support.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add Wave 0 CLI and docs wording guards | 38c9938 | tests/test_main_args.py, tests/test_locomotion_benchmark_docs.py |
| 2 | Update eval-locomotion help text | c29cfa9 | src/main.py, tests/test_main_args.py |
| 3 | Update benchmark guide action-mode contract | 5780184 | docs/locomotion-benchmark.md |

## Verification

- `uv run python -m pytest tests/test_main_args.py -q` -> 7 passed.
- `uv run python -m pytest tests/test_locomotion_benchmark_docs.py -q` -> 7 passed.
- `uv run python -m pytest tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` -> 14 passed.
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` -> 59 passed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Kept `src.main` importable without web extras**
- **Found during:** Task 2 verification
- **Issue:** Running `uv run python -m pytest tests/test_main_args.py -q` in the worktree-created environment failed before parser assertions because `src.main` imported `src.mcp.server`, which imports optional `fastapi` web dependencies not installed by the default/dev dependency set.
- **Fix:** Moved `from src.mcp.server import configure as configure_mcp, mcp_endpoint` into `run_web_mode()` and updated web-mode tests to stub `src.mcp.server` through `sys.modules`.
- **Files modified:** `src/main.py`, `tests/test_main_args.py`
- **Commit:** c29cfa9

**2. [Rule 1 - Bug] Prevented argparse help wrapping from breaking exact public wording**
- **Found during:** Task 2 verification
- **Issue:** The new help string existed in `src/main.py`, but argparse line wrapping split `velocity_command is the evaluator-runnable mode`, causing the exact help contract guard to fail.
- **Fix:** Set the `eval-locomotion` subparser formatter to `argparse.RawTextHelpFormatter` so exact public wording remains contiguous in help output.
- **Files modified:** `src/main.py`
- **Commit:** c29cfa9

## Auth Gates

None.

## Known Stubs

The stub scan found existing documentation of intentionally unavailable controller placeholders in `docs/locomotion-benchmark.md` and its guard in `tests/test_locomotion_benchmark_docs.py`. These are not implementation stubs; they are the explicit v4.0 scope boundary for deferred residual/direct RL, MPC, and WBC controller families.

## Threat Flags

None. This plan modified CLI help, documentation, and tests only; it did not add network endpoints, auth paths, file access patterns, schema changes, or new trust boundaries beyond the planned CLI/docs information-integrity surface.

## Decisions Made

- `velocity_command` remains the default and only documented evaluator-runnable mode for `argus eval-locomotion`.
- `joint_position` and `residual_baseline` remain documented as environment-supported seams, not current evaluator modes.
- CLI help uses raw text formatting for this subcommand because exact wording is a tested public contract.

## Deferred Issues

None.

## Self-Check: PASSED

- Found modified source, docs, and test files.
- Found summary file at `.planning/phases/07-align-evaluation-action-mode-contract/07-02-SUMMARY.md`.
- Found task commits: `38c9938`, `c29cfa9`, `5780184`.
