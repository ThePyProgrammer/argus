---
phase: 06-repair-evaluation-runner-semantics
plan: 02
subsystem: locomotion-evaluation
tags: [python, pytest, locomotion, evaluation, csv, metrics]
requires:
  - phase: 06-repair-evaluation-runner-semantics
    provides: active command propagation from plan 06-01
provides:
  - stability-sourced distance_xy_m flattening for evaluation episode artifacts
  - artifact regression covering result rows, episodes.csv, summary.json, and comparison.md
affects: [locomotion-evaluation, metric-exports, baseline-regression]
tech-stack:
  added: []
  patterns:
    - pytest fake-env artifact regression
    - stability metrics as distance source of truth
key-files:
  created:
    - .planning/phases/06-repair-evaluation-runner-semantics/06-02-SUMMARY.md
  modified:
    - tests/locomotion/test_locomotion_evaluation_exports.py
    - src/locomotion/evaluation.py
key-decisions:
  - "Keep distance_xy_m owned by summary['stability']; evaluator flattening adapts to the production metrics schema."
  - "Preserve existing CSV formula safety and output-root containment while changing only the distance source."
patterns-established:
  - "Artifact tests must assert metric consistency across result.episode_rows, episodes.csv, summary.json, and comparison.md."
requirements-completed: [LOC-METRICS-05, LOC-EVAL-02]
duration: 2min
completed: 2026-05-01
---

# Phase 06 Plan 02: Stability Distance Export Summary

**Evaluation artifacts now preserve locomotion distance from stability metrics instead of the stale command-tracking family.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-01T10:12:38Z
- **Completed:** 2026-05-01T10:14:15Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added a regression test where `command_tracking.distance_xy_m` is zero while `stability.distance_xy_m` is `0.42`.
- Verified the regression asserts the same distance through `result.episode_rows`, `episodes.csv`, `summary.json`, and `comparison.md`.
- Updated `_episode_csv_row()` to flatten `distance_xy_m` from the `stability` metrics family without touching CSV hardening or output path containment.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 stability-distance artifact regression test** - `1057051` (test)
2. **Task 2: Flatten distance from stability and preserve export hardening** - `2bad864` (fix)

**Plan metadata:** pending final metadata commit

_Note: TDD RED/GREEN commits were created as separate task commits._

## Files Created/Modified

- `tests/locomotion/test_locomotion_evaluation_exports.py` - Adds `test_episode_export_reads_distance_xy_m_from_stability_summary` and artifact-layer assertions for nonzero stability distance.
- `src/locomotion/evaluation.py` - Changes episode row distance flattening to `_metric_alias(stability, "distance_xy_m", default=0.0)`.
- `.planning/phases/06-repair-evaluation-runner-semantics/06-02-SUMMARY.md` - Execution summary and verification record.

## Decisions Made

- Kept `distance_xy_m` in `summary["stability"]` as the source of truth because `src/locomotion/metrics.py` already owns locomotion distance in the stability family.
- Made the smallest evaluator change possible: only the distance source changed; `_prepare_run_dir()` containment and `_csv_safe()` CSV writer behavior remain unchanged.

## Deviations from Plan

None - plan scope was executed as written.

## Issues Encountered

- Automated pytest verification could not collect in this worktree because the default interpreter is Python 3.14 and lacks project dependencies, specifically `gymnasium`; this matches the Phase 6 research environment note. Static acceptance checks confirmed the intended code paths, but full pytest must be run in a supported project environment with dependencies installed.

## Verification

Attempted:

```bash
python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q
```

Result: collection failed with `ModuleNotFoundError: No module named 'gymnasium'` before test execution.

Attempted shared quick gate:

```bash
python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q
```

Result: collection failed with the same missing `gymnasium` dependency.

Static acceptance checks passed:

- `_episode_csv_row()` maps `"distance_xy_m"` from `stability`.
- CSV writing still uses `writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})`.
- `_prepare_run_dir()` still contains the `Run directory escapes output root` containment guard.

## Self-Check: PASSED

- Found modified test file: `tests/locomotion/test_locomotion_evaluation_exports.py`
- Found modified implementation file: `src/locomotion/evaluation.py`
- Found summary file: `.planning/phases/06-repair-evaluation-runner-semantics/06-02-SUMMARY.md`
- Found task commit: `1057051`
- Found task commit: `2bad864`

## Known Stubs

None.

## Threat Flags

None - no new network endpoints, auth paths, file access patterns, schema changes, or trust boundaries were introduced. Existing filesystem and CSV defenses were preserved.

## User Setup Required

None - no external service configuration required. For automated test execution, use a supported Python `>=3.10,<3.13` environment with project dependencies installed.

## Next Phase Readiness

Plan 06-02 closes the distance export gap for LOC-METRICS-05 and LOC-EVAL-02. Remaining Phase 6/7 work can rely on episode rows and aggregate comparison artifacts reading locomotion distance from the production stability summary.

---
*Phase: 06-repair-evaluation-runner-semantics*
*Completed: 2026-05-01*
