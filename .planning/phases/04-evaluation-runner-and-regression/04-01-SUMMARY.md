---
phase: 04-evaluation-runner-and-regression
plan: 01
subsystem: locomotion-evaluation
tags: [python, pytest, locomotion, evaluation-runner, matrix-validation]

requires:
  - phase: 01-locomotion-env-contract
    provides: Gymnasium-style ArgusGo2Env reset/step API and command schedule info
  - phase: 02-controller-plugin-baseline
    provides: ControllerRegistry and unavailable-controller semantics
  - phase: 03-locomotion-metrics-instrumentation
    provides: per-step locomotion_metrics and terminal locomotion_metrics_summary payloads
provides:
  - EvaluationMatrix and EvaluationRunConfig contracts for controller x scenario x seed matrices
  - Fail-fast validation for controllers, scenario ids, seeds, numeric env config, and max matrix size
  - Fake-env-compatible runner loop that records command schedule context and nonzero locomotion-failure exit status
  - Unit coverage for LOC-EVAL-01, D-02, D-04, D-16, T-04-01, and T-04-05
affects: [phase-04-plan-02-cli-and-exports, phase-04-plan-04-baseline-regression]

tech-stack:
  added: []
  patterns:
    - strict dataclass matrix contracts with stdlib JSON config loading
    - validation-before-side-effects for benchmark execution
    - in-memory runner result rows before Plan 02 artifact writers

key-files:
  created:
    - src/locomotion/evaluation.py
    - tests/locomotion/test_locomotion_evaluation_runner.py
  modified: []

key-decisions:
  - "Plan 01 keeps artifact writing as a private no-op hook so Plan 02 owns final JSONL/CSV/manifest formats."
  - "The runner derives velocity commands from scenario command metadata instead of hardcoding stationary actions."

patterns-established:
  - "Validate the full evaluation matrix before creating output directories or environments."
  - "Return EvaluationResult with collected rows plus exit_code instead of raising immediately on locomotion failure."

requirements-completed: [LOC-EVAL-01]

duration: 18min
completed: 2026-05-01
---

# Phase 04 Plan 01: Evaluation Runner Foundation Summary

**Controller x scenario x seed evaluation matrix contracts with fail-fast validation and command-schedule-aware fake-env runner rows**

## Performance

- **Duration:** 18 min
- **Started:** 2026-05-01T02:54:00Z
- **Completed:** 2026-05-01T03:12:01Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `EvaluationMatrix`, `EvaluationRunConfig`, `EvaluationResult`, `load_matrix_config`, `validate_evaluation_matrix`, and `run_evaluation_matrix` in `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/src/locomotion/evaluation.py`.
- Enforced validation before side effects for unknown controllers, unavailable placeholder controllers, unknown scenarios, invalid/duplicate/non-integer seeds, invalid numeric config, and matrices larger than 1000 cells.
- Added fake-env tests proving runner rows preserve `commanded_velocity`, `command_source`, and command schedule context while locomotion failures return `exit_code == 1` after rows exist.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add matrix validation tests before production runner code** - `952a842` (test)
2. **Task 2: Implement evaluation matrix contracts and fake-env runner loop** - `99ed176` (feat)

**Plan metadata:** committed separately after this summary.

## Files Created/Modified

- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/tests/locomotion/test_locomotion_evaluation_runner.py` - TDD tests for matrix validation, strict JSON config loading, side-effect prevention, command schedule row context, and locomotion-failure status semantics.
- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/src/locomotion/evaluation.py` - Evaluation dataclasses, strict config loader, fail-fast matrix validation, and fake-env-compatible runner loop.

## Decisions Made

- Kept artifact writing as `_write_noop_artifacts(...)` because Plan 01 explicitly establishes the runner foundation while Plan 02 owns final file formats.
- Used scenario `command_schedule` / `current_command` metadata as the runner's command source of truth; zero velocity is only a fallback when no command metadata exists.
- Validation calls `ControllerRegistry.list_controllers()` and `list_scenarios()` before output directory creation or environment construction.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

- `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/src/locomotion/evaluation.py` has private `_write_noop_artifacts(...)`; this is intentional Plan 01 scope because Plan 02 replaces it with JSONL/CSV/manifest/summary writers.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: output-path | `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/src/locomotion/evaluation.py` | `_prepare_run_dir` creates the configured output root after validation. Plan 01 does not write artifacts; Plan 02 must constrain final run directories under `outputs/locomotion-evals/` per T-04-02. |

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/tests/locomotion/test_locomotion_evaluation_runner.py -q` → 10 passed.

## Next Phase Readiness

- Plan 02 can layer CLI parsing and artifact writers on top of `EvaluationMatrix`, `EvaluationRunConfig`, `validate_evaluation_matrix`, and `run_evaluation_matrix`.
- The runner returns in-memory step and episode rows with enough provenance for JSONL/CSV/manifest export work.

## Self-Check: PASSED

- Found `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/src/locomotion/evaluation.py`.
- Found `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/tests/locomotion/test_locomotion_evaluation_runner.py`.
- Found `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a34061bc53acddfe1/.planning/phases/04-evaluation-runner-and-regression/04-01-SUMMARY.md`.
- Found task commits `952a842` and `99ed176`.

---
*Phase: 04-evaluation-runner-and-regression*
*Completed: 2026-05-01*
