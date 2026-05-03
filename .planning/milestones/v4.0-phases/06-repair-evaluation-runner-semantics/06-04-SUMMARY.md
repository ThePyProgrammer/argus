---
phase: 06-repair-evaluation-runner-semantics
plan: 04
subsystem: locomotion-evaluation
tags: [python, pytest, locomotion, evaluation-runner, max-episode-steps]

requires:
  - phase: 06-repair-evaluation-runner-semantics
    provides: active-command runner semantics, stability distance exports, and baseline regression fixtures from plans 06-01 through 06-03
provides:
  - runner-owned max_episode_steps enforcement for every evaluation matrix cell
  - non-terminating fake-env regression proving bounded execution and complete artifacts
affects: [locomotion-evaluation, phase-06-verification, LOC-EVAL-01]

tech-stack:
  added: []
  patterns:
    - runner-owned step counter independent of env termination behavior
    - fail-fast fake env for non-terminating runner regression tests

key-files:
  created:
    - .planning/phases/06-repair-evaluation-runner-semantics/06-04-SUMMARY.md
  modified:
    - src/locomotion/evaluation.py
    - tests/locomotion/test_locomotion_evaluation_runner.py

key-decisions:
  - "Keep max_episode_steps validation in validate_evaluation_matrix and enforce the already-validated per-cell cap inside run_evaluation_matrix."
  - "Use a deterministic fake env that raises after the fourth step as the TDD red guard, avoiding sleeps, signals, threads, or wall-clock timeouts."

patterns-established:
  - "Evaluation runner loops must maintain runner_step_count and force truncation when it reaches cell['max_episode_steps']."
  - "Non-terminating env regressions should prove artifact writing after forced truncation, not merely exception behavior."

requirements-completed: [LOC-METRICS-05, LOC-EVAL-01, LOC-EVAL-02, LOC-EVAL-04]

duration: 2min
completed: 2026-05-01
---

# Phase 06 Plan 04: Runner-Owned Matrix Step Cap Summary

**Evaluation matrix cells now terminate at the validated max_episode_steps cap even when a custom env never reports terminated or truncated.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-01T11:56:13Z
- **Completed:** 2026-05-01T11:58:11Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `test_runner_enforces_matrix_max_episode_steps_when_env_never_terminates`, a fake-env regression that never returns termination/truncation and fails fast if the runner calls `env.step()` more than three times.
- Updated `run_evaluation_matrix` with a runner-owned `runner_step_count` initialized after reset and checked against `int(cell["max_episode_steps"])` inside the loop.
- Verified forced-cap execution writes `manifest.json`, `steps.jsonl`, `episodes.csv`, `summary.json`, and `comparison.md` while preserving existing CSV formula safety and output-root containment code.
- Ran the targeted regression, full runner module gate, Phase 6 quick gate, and full Phase 6 wave gate successfully under `uv run`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add non-terminating fake-env regression for runner-owned cap enforcement** - `313871c` (test)
2. **Task 2: Enforce cell max_episode_steps inside run_evaluation_matrix** - `7a90624` (fix)

**Plan metadata:** pending final docs commit

_Note: TDD RED/GREEN gates were followed with separate test and implementation commits._

## Files Created/Modified

- `tests/locomotion/test_locomotion_evaluation_runner.py` - Adds the non-terminating fake env regression and artifact assertions for forced-cap completion.
- `src/locomotion/evaluation.py` - Adds `runner_step_count` and forces truncation once the validated per-cell step cap is reached.
- `.planning/phases/06-repair-evaluation-runner-semantics/06-04-SUMMARY.md` - Execution summary and verification record.

## Decisions Made

- Used the validated `cell["max_episode_steps"]` value rather than changing matrix validation semantics or adding a second configuration path.
- Preserved the capped final step row before truncation, so episode rows, manifest rows, and comparison artifacts remain auditable after forced truncation.
- Kept runtime and tests deterministic/offline; no Claude/Anthropic runtime dependency, network client, or SDK query call was introduced.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The red test failed fast with `AssertionError: runner exceeded max_episode_steps`, then passed after the runner-owned cap was implemented.

## Verification

- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py::test_runner_enforces_matrix_max_episode_steps_when_env_never_terminates -q` — red phase failed fast before implementation; green phase passed (`1 passed`).
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py -q` — passed (`12 passed`).
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_locomotion_baseline_regression.py -q` — passed (`30 passed`).
- `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` — passed (`245 passed`).
- `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" src pyproject.toml tests 2>/dev/null` — no output.

## Known Stubs

None. Stub-pattern scan only found pre-existing placeholder-controller test wording and file-open newline parameters; no UI/data stubs were introduced.

## Threat Flags

None. The plan mitigated the existing untrusted/broken env_factory denial-of-service boundary and introduced no new network endpoint, auth path, schema trust boundary, or file access surface beyond existing evaluation artifact writes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 6 verification gap for LOC-EVAL-01 is closed: scenario/seed matrix execution is bounded by runner-owned max-step enforcement even if a custom environment ignores termination and truncation.

## Self-Check: PASSED

- Found implementation file: `src/locomotion/evaluation.py`
- Found regression test file: `tests/locomotion/test_locomotion_evaluation_runner.py`
- Found summary file: `.planning/phases/06-repair-evaluation-runner-semantics/06-04-SUMMARY.md`
- Found Task 1 commit: `313871c`
- Found Task 2 commit: `7a90624`

---
*Phase: 06-repair-evaluation-runner-semantics*
*Completed: 2026-05-01*
