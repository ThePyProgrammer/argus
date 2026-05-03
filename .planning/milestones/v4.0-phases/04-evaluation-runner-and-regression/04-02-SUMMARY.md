---
phase: 04-evaluation-runner-and-regression
plan: 02
subsystem: locomotion evaluation artifacts
tags:
  - locomotion
  - evaluation-runner
  - artifacts
  - regression
requires:
  - 04-01
provides:
  - LOC-METRICS-05
  - LOC-EVAL-02
  - LOC-EVAL-03
affects:
  - src/locomotion/evaluation.py
  - tests/locomotion/test_locomotion_evaluation_exports.py
tech_stack:
  added: []
  patterns:
    - dataclass runner config
    - fixed-file artifact writer
    - offline CSV-backed summary regeneration
key_files:
  created:
    - tests/locomotion/test_locomotion_evaluation_exports.py
  modified:
    - src/locomotion/evaluation.py
decisions:
  - Preserve matrix validation before creating run directories or constructing environments.
  - Generate comparison outputs from saved episode CSV and manifest data without constructing ArgusGo2Env.
  - Apply CSV formula-prefix defense to all string cells before spreadsheet-facing export.
metrics:
  duration: unknown
  completed: 2026-05-01T03:21:13Z
  tasks_completed: 2
  files_changed: 2
---

# Phase 04 Plan 02: Evaluation Artifact Export Summary

## One-liner

Locomotion evaluation runs now write reproducible JSONL/CSV/manifest/summary/Markdown artifacts with offline comparison regeneration and CSV formula-injection defense.

## Completed Tasks

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add artifact/export/reload tests before implementation | 19cef73 | `tests/locomotion/test_locomotion_evaluation_exports.py` |
| 2 | Implement artifact exports, aggregation, and offline regeneration | 676d278 | `src/locomotion/evaluation.py` |

## What Changed

- Added fast fake-env export tests for the exact artifact set: `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md`.
- Extended `run_evaluation_matrix` to create a timestamped run directory under the configured output root after validation succeeds.
- Persisted compact per-step JSONL rows with controller/scenario/seed ids, command context, and nested `locomotion_metrics` payloads.
- Persisted flattened episode CSV rows with command metadata, success/failure state, tracking, stability, action-quality, and contact/terrain metrics.
- Added top-level manifest reproducibility metadata including git commit, invocation args, matrix, environment config, fixed file list, and per-run reset/command metadata.
- Implemented `aggregate_episode_rows`, `write_comparison_artifacts`, and `regenerate_comparison` so saved artifacts can recreate summary and Markdown comparisons without simulation.
- Added metric direction labels in `summary.json` and Markdown tables without inventing a composite controller score.
- Added CSV formula defense for string cells beginning with `=`, `+`, `-`, or `@`.

## Verification

Command run:

```bash
/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a6beba3405a69b5a7/tests/locomotion/test_locomotion_evaluation_runner.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a6beba3405a69b5a7/tests/locomotion/test_locomotion_evaluation_exports.py -q
```

Result: `14 passed in 2.88s`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserved Plan 01 result row compatibility**
- **Found during:** Task 2 verification.
- **Issue:** Existing runner tests expected `result.step_rows[*]["command_context"]` and `result.episode_rows[*]["summary"]`; the first implementation focused on artifact row shapes and dropped those in-memory compatibility fields.
- **Fix:** Restored `command_context` on in-memory step rows and retained the nested terminal `summary` on in-memory episode rows while keeping CSV output flattened via fixed fieldnames.
- **Files modified:** `src/locomotion/evaluation.py`
- **Commit:** 676d278

## Auth Gates

None.

## Known Stubs

None. The stub-pattern scan only matched `newline=""` arguments for CSV file I/O, not placeholder data paths.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: filesystem-artifacts | `src/locomotion/evaluation.py` | Implements the planned runner-memory-to-filesystem artifact boundary with fixed filenames and output-root containment checks. |
| threat_flag: saved-artifact-reload | `src/locomotion/evaluation.py` | Implements the planned saved-artifacts-to-offline-comparison boundary by reading manifest and episode CSV only. |
| threat_flag: csv-spreadsheet | `src/locomotion/evaluation.py` | Implements the planned CSV spreadsheet boundary with formula-prefix escaping for string cells. |

## TDD Gate Compliance

- RED gate commit: 19cef73 `test(04-02): add locomotion evaluation artifact export tests`
- GREEN gate commit: 676d278 `feat(04-02): implement locomotion evaluation artifact exports`

## Self-Check: PASSED

Verified files exist:

- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a6beba3405a69b5a7/src/locomotion/evaluation.py`
- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a6beba3405a69b5a7/tests/locomotion/test_locomotion_evaluation_exports.py`
- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a6beba3405a69b5a7/.planning/phases/04-evaluation-runner-and-regression/04-02-SUMMARY.md`

Verified commits exist: `19cef73`, `676d278`.
