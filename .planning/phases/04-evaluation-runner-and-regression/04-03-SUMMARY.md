---
phase: 04-evaluation-runner-and-regression
plan: 03
subsystem: cli
tags: [argparse, locomotion, evaluation, benchmark, pytest]

requires:
  - phase: 04-evaluation-runner-and-regression
    provides: Evaluation matrix runner, artifact exporter, and comparison regeneration APIs from plans 04-01 and 04-02
provides:
  - Dedicated `argus eval-locomotion` subcommand under `src.main:main`
  - Repeatable controller/scenario/seed matrix flags with optional JSON matrix config
  - CLI dispatch to run evaluation matrices or regenerate saved comparison artifacts
  - CLI parser and subprocess smoke coverage for the evaluation command
  - Nonzero evaluation exit-code propagation from `EvaluationResult.exit_code`
affects: [locomotion-evaluation, cli, benchmark-harness, regression]

tech-stack:
  added: []
  patterns: [argparse top-level subcommand, lazy evaluation imports, subprocess CLI help test]

key-files:
  created:
    - .planning/phases/04-evaluation-runner-and-regression/04-03-SUMMARY.md
  modified:
    - src/main.py
    - tests/test_main_args.py

key-decisions:
  - "Kept eval-locomotion as a top-level argparse subcommand rather than a --control choice."
  - "Kept evaluation imports lazy inside run_eval_locomotion_mode so parser/help tests do not construct simulation environments."
  - "Preserved existing no-subcommand behavior by leaving --control defaulted to web."

patterns-established:
  - "Evaluation CLI flags are parsed at the entry point and converted into EvaluationMatrix/EvaluationRunConfig objects immediately before lazy runner dispatch."
  - "Saved comparison regeneration is a no-simulation branch guarded by --from-run-dir."

requirements-completed: [LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-03]

duration: 2min
completed: 2026-05-01T03:27:36Z
---

# Phase 04 Plan 03: Evaluation CLI Subcommand Summary

**Dedicated `argus eval-locomotion` CLI for repeatable locomotion benchmark matrices and saved-artifact comparison regeneration**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-01T03:25:12Z
- **Completed:** 2026-05-01T03:27:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added RED coverage for the dedicated `eval-locomotion` subcommand, repeatable `--controller`, `--scenario`, and `--seed` flags, artifact/help flags, and separation from `--control` runtime modes.
- Added the `eval-locomotion` parser branch with `--matrix-config`, `--from-run-dir`, `--output-root`, run-configuration flags, `--allow-locomotion-failures`, and `--verbose`.
- Wired CLI dispatch through a lazy `run_eval_locomotion_mode()` function that calls `run_evaluation_matrix()` or `regenerate_comparison()` and returns evaluation exit codes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CLI subcommand parser and subprocess tests** - `5002328` (test)
2. **Task 2: Wire `argus eval-locomotion` to evaluation module** - `b96d55f` (feat)

**Plan metadata:** committed separately after this summary.

_Note: TDD tasks used a RED test commit followed by the GREEN implementation commit._

## Files Created/Modified

- `src/main.py` - Adds the `eval-locomotion` argparse subcommand and lazy evaluation dispatch.
- `tests/test_main_args.py` - Adds parser and subprocess smoke coverage for the new evaluation CLI shape.
- `.planning/phases/04-evaluation-runner-and-regression/04-03-SUMMARY.md` - Records execution outcomes for this plan.

## Verification

- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/test_main_args.py -q` failed during RED as expected before implementation.
- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/test_main_args.py -q` passed after implementation: 20 passed.
- Final verification repeated successfully: 20 passed.

## Decisions Made

- Kept `eval-locomotion` as a top-level subcommand and not a `--control` choice, matching D-01.
- Used lazy imports inside `run_eval_locomotion_mode()` so CLI parsing and help remain fast and do not construct `ArgusGo2Env`.
- Made repeated flags override matrix-config dimensions only when explicitly supplied; otherwise matrix-config values are preserved.

## Deviations from Plan

None - plan executed as written.

## Issues Encountered

None.

## Known Stubs

None found in files created or modified by this plan.

## Threat Flags

None. The CLI trust boundaries and mitigations were already described in the plan threat model; this implementation did not add unplanned network, auth, schema, or file-access surfaces beyond the requested CLI artifact paths.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The installed `argus = src.main:main` entry point can now invoke the Phase 4 locomotion evaluation runner.
- Plan 04-04 can build on the CLI surface for baseline regression and harness documentation.

## Self-Check: PASSED

- FOUND: `src/main.py`
- FOUND: `tests/test_main_args.py`
- FOUND: `.planning/phases/04-evaluation-runner-and-regression/04-03-SUMMARY.md`
- FOUND commit: `5002328`
- FOUND commit: `b96d55f`

---
*Phase: 04-evaluation-runner-and-regression*
*Completed: 2026-05-01*
