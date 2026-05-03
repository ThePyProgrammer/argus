---
phase: 06-repair-evaluation-runner-semantics
plan: 01
subsystem: locomotion evaluation
tags: [python, pytest, locomotion, evaluation-runner, command-schedule]

requires:
  - phase: 04-evaluation-runner-and-regression
    provides: evaluation runner, matrix execution, and artifact exports
  - phase: 01-locomotion-env-contract
    provides: ArgusGo2Env reset/step/info contract and scenario command schedules
provides:
  - Env-owned current_command info payload at reset and every step
  - Evaluation action generation that prefers active current_command over static schedule fallback
  - Regression coverage for zero-to-nonzero schedule transitions
affects: [evaluation-runner, locomotion-env, baseline-regression, phase-06-plan-02]

tech-stack:
  added: []
  patterns:
    - Env-owned active command lookup via _current_sim_time() and _command_at_time()
    - Evaluator current_command-first action generation with command_schedule retained as metadata

key-files:
  created:
    - .planning/phases/06-repair-evaluation-runner-semantics/deferred-items.md
  modified:
    - src/locomotion/env.py
    - src/locomotion/evaluation.py
    - tests/locomotion/test_argus_go2_env_contract.py
    - tests/locomotion/test_locomotion_evaluation_runner.py

key-decisions:
  - "Kept schedule-time semantics in ArgusGo2Env and exposed current_command instead of duplicating schedule iteration in the evaluator."
  - "Kept command_schedule in evaluator command_context as provenance metadata while using current_command as the action source."

patterns-established:
  - "current_command payload: {time, vx, vy, omega, source} emitted from env._info()."
  - "Evaluation action path checks info['current_command'] before command_schedule fallback."

requirements-completed: [LOC-EVAL-01, LOC-EVAL-04]

duration: 3min 10sec
completed: 2026-05-01
---

# Phase 06 Plan 01: Active Command Evaluation Semantics Summary

**Env-provided active locomotion commands now drive evaluator actions and exported step command fields after schedule transitions.**

## Performance

- **Duration:** 3min 10sec
- **Started:** 2026-05-01T10:03:47Z
- **Completed:** 2026-05-01T10:06:57Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added failing-first regression coverage for the audit gap where a zero reset command was reused forever after a schedule transition.
- Added `current_command` to `ArgusGo2Env._info()` using the env-owned current simulation time and `_command_at_time()` schedule lookup.
- Changed evaluator action generation to prefer `current_command` before static `command_schedule` fallback while preserving schedule provenance in command context.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 active-command regression tests** - `cab6a06` (test)
2. **Task 2: Emit and consume current_command as the active runtime command** - `f31e412` (feat)

**Plan metadata:** pending final docs commit

_Note: TDD RED/GREEN gates were followed with separate test and implementation commits._

## Files Created/Modified

- `src/locomotion/env.py` - Emits `current_command` from `_info()` at reset and step time.
- `src/locomotion/evaluation.py` - Uses `current_command` first for evaluation actions and retains schedule metadata in context.
- `tests/locomotion/test_argus_go2_env_contract.py` - Adds env contract regression for post-transition active command exposure.
- `tests/locomotion/test_locomotion_evaluation_runner.py` - Adds fake-env regression proving the second step receives the nonzero active command and exports matching command fields.
- `.planning/phases/06-repair-evaluation-runner-semantics/deferred-items.md` - Records the out-of-scope shared quick gate failure owned by later Phase 06 work.

## Decisions Made

- Kept `ArgusGo2Env` as the source of truth for active command timing because it owns simulation time and already has `_command_at_time()`.
- Kept `command_schedule` fallback in the evaluator for non-Argus/fake env compatibility, but only after checking `current_command`.
- Did not alter non-default action-mode behavior; Phase 7 owns that contract per the plan boundary.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The default `python` interpreter was Python 3.14 and lacked `gymnasium`, causing collection errors. Verification was rerun with `uv run --project /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2`, which created a supported Python 3.12 environment and ran the targeted gates.
- The shared quick gate failed in `test_analytical_trot_flat_ground_fixed_seed_regression` because `distance_xy_m` remains exported as `0.0` despite nonzero commanded velocity. This is the separately planned Phase 06 Plan 02 distance export repair, so it was documented in `deferred-items.md` and not fixed in this plan.

## Verification

- `uv run --project /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2 python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2/tests/locomotion/test_locomotion_evaluation_runner.py -q` -> 11 passed.
- `uv run --project /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2 python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a886e2eb5f61fe7c2/tests/locomotion/test_argus_go2_env_contract.py -k current_command -q` -> 1 passed, 20 deselected.
- `grep -R "claude_agent_sdk\|anthropic\|ClaudeSDKClient\|query(" src pyproject.toml tests 2>/dev/null` -> no runtime AI SDK usage found.

## Known Stubs

None. The stub-pattern scan only found pre-existing placeholder-controller test wording and file-open newline parameters; no new UI/data stubs were introduced.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema trust boundaries were introduced beyond the planned env-info to evaluator command boundary.

## User Setup Required

None - no external service configuration required.

## Deferred Issues

- Phase 06 Plan 02 must fix `distance_xy_m` flattening from `stability` rather than `command_tracking`; the shared quick gate currently fails until that planned repair lands.

## Next Phase Readiness

Plan 02 can build on `current_command` provenance now present in step rows and focus on the remaining distance-export audit gap without reworking active-command semantics.

## Self-Check: PASSED

- Found all key modified files and `06-01-SUMMARY.md`.
- Found task commits `cab6a06` and `f31e412` in git history.

---
*Phase: 06-repair-evaluation-runner-semantics*
*Completed: 2026-05-01*
