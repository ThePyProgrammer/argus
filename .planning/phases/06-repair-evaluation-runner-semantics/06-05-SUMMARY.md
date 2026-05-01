---
phase: 06-repair-evaluation-runner-semantics
plan: 05
subsystem: locomotion-evaluation
tags: [python, pytest, locomotion, evaluation-runner, command-schedule]

requires:
  - phase: 06-repair-evaluation-runner-semantics
    provides: active-command runner semantics, distance exports, baseline regression, and runner-owned step caps from plans 06-01 through 06-04
provides:
  - step rows labeled from the exact pre-step action/source/context that drove env.step(action)
  - per-step action/export equality regression across a zero-to-nonzero schedule transition
  - fake-MuJoCo ArgusGo2Env velocity-command dispatch regression across a schedule transition
affects: [locomotion-evaluation, phase-06-verification, LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04]

tech-stack:
  added: []
  patterns:
    - preserve executed pre-step command metadata before env.step and use it for that row only
    - fake-MuJoCo dispatch tests for real ArgusGo2Env velocity-command semantics

key-files:
  created:
    - .planning/phases/06-repair-evaluation-runner-semantics/06-05-SUMMARY.md
  modified:
    - src/locomotion/evaluation.py
    - tests/locomotion/test_locomotion_evaluation_runner.py
    - tests/locomotion/test_argus_go2_env_contract.py

key-decisions:
  - "Record normal step rows from the executed pre-step action/source/context rather than post-step current_command metadata."
  - "Keep post-step latest_info as the next-iteration action source, preserving schedule-transition execution while preventing row relabeling."
  - "Cover ArgusGo2Env velocity-command schedule transitions with patched dispatch_controller and fake MuJoCo instead of requiring a real MuJoCo install."

patterns-established:
  - "Evaluation runner row labels must be captured before env.step when post-step info can represent the next command."
  - "Schedule-transition regressions must assert every captured env.step(action) against the same-index exported row, not only the final row."

requirements-completed: [LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04]

duration: 2min
completed: 2026-05-01
---

# Phase 06 Plan 05: Command-Schedule Step Row Semantics Summary

**Evaluation step rows now audit the exact velocity command passed to env.step(action), with fake-MuJoCo coverage proving schedule-transition dispatch through ArgusGo2Env.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-01T13:44:42Z
- **Completed:** 2026-05-01T13:47:09Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `test_runner_records_each_step_commanded_velocity_from_executed_action`, which captures both fake-env step actions and asserts same-index exported `commanded_velocity` rows across a zero-to-nonzero schedule transition.
- Updated `run_evaluation_matrix` so each row uses `executed_commanded_velocity`, `executed_command_source`, and `executed_command_context` captured before `env.step(action)`.
- Added `test_velocity_command_step_dispatch_uses_schedule_current_command_after_transition`, using fake MuJoCo time advancement and patched `dispatch_controller` to verify first-step zero dispatch, post-first-step `current_command` observability, and second-step nonzero dispatch.
- Re-ran targeted gap gates, Phase 6 quick gate, full locomotion/bridge wave gate, and runtime-AI dependency scan successfully.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add per-step action/export equality regression at schedule boundary** - `4828343` (test)
2. **Task 2: Label step rows from the executed pre-step action** - `4f472ca` (fix)
3. **Task 3: Add ArgusGo2Env velocity-command transition dispatch coverage** - `72d7f9c` (test)

**Plan metadata:** pending final docs commit

_Note: TDD RED/GREEN intent was followed with a test commit before the implementation commit; Task 3 was coverage-only and did not require production changes._

## Files Created/Modified

- `tests/locomotion/test_locomotion_evaluation_runner.py` - Adds same-index step action/export equality coverage for the schedule boundary row and post-transition row.
- `src/locomotion/evaluation.py` - Captures executed command metadata before `env.step(action)` and writes that metadata into the just-completed step row.
- `tests/locomotion/test_argus_go2_env_contract.py` - Adds fake-MuJoCo dispatch coverage for velocity-command schedule transitions.
- `.planning/phases/06-repair-evaluation-runner-semantics/06-05-SUMMARY.md` - Execution summary and verification record.

## Decisions Made

- Used pre-step metadata for per-step rows because post-step `current_command` may legitimately represent the next scheduled command.
- Left `_command_fields()` available for fallback/no-step usage and did not alter artifact writing, CSV safety, output-root containment, or runner-owned max-step cap behavior.
- Did not modify `src/locomotion/env.py`; the new dispatch regression confirmed the existing velocity-command path dispatches the caller action and exposes the next scheduled command after time advances.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The planned runner mismatch was corrected by carrying executed command metadata through row construction; the real-env fake-MuJoCo dispatch coverage passed without production env changes.

## Verification

- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_records_each_step_commanded_velocity_from_executed_action tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_uses_active_current_command_after_schedule_transition tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_enforces_matrix_max_episode_steps_when_env_never_terminates -q` — passed (`3 passed`).
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` — passed (`13 passed`).
- `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py::test_velocity_command_step_dispatch_uses_schedule_current_command_after_transition -q` — passed (`1 passed`).
- `uv run python -m pytest tests/locomotion/test_argus_go2_env_contract.py -k "current_command or velocity_command_step_dispatch" -q` — passed (`3 passed, 19 deselected`).
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` — passed (`31 passed`).
- `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` — passed (`247 passed`).
- `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" src pyproject.toml tests 2>/dev/null` — no matches.

## Known Stubs

None introduced. Stub-pattern scan only found pre-existing placeholder-controller test wording and file-open `newline=""` parameters; these are not runtime/UI stubs and do not affect the plan goal.

## Threat Flags

None. The plan mitigated the existing env-info-to-artifact and scenario-schedule-to-dispatch boundaries and introduced no new network endpoint, auth path, schema trust boundary, or new file-access surface beyond existing evaluation artifacts.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 6 gap closure is ready for orchestrator-owned state/roadmap updates. The remaining verification truths around step command fidelity and real-env velocity-command transition coverage are now backed by deterministic pytest gates.

## Self-Check: PASSED

- Found implementation file: `src/locomotion/evaluation.py`
- Found runner regression test file: `tests/locomotion/test_locomotion_evaluation_runner.py`
- Found env contract test file: `tests/locomotion/test_argus_go2_env_contract.py`
- Found summary file: `.planning/phases/06-repair-evaluation-runner-semantics/06-05-SUMMARY.md`
- Found Task 1 commit: `4828343`
- Found Task 2 commit: `4f472ca`
- Found Task 3 commit: `72d7f9c`

---
*Phase: 06-repair-evaluation-runner-semantics*
*Completed: 2026-05-01*
