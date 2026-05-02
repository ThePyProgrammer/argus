---
phase: 07-align-evaluation-action-mode-contract
plan: 01
subsystem: locomotion-evaluation
tags: [python, pytest, locomotion, evaluation, action-modes, artifacts]

requires:
  - phase: 06-repair-evaluation-runner-semantics
    provides: same-index executed velocity-command row/export semantics for evaluation artifacts
provides:
  - fail-fast evaluator action-mode validation before env construction or artifact writes
  - velocity_command-only evaluator runnable contract backed by authoritative env action-mode names
  - completed-run action-mode metadata assertions for manifest, validated cells, run rows, step rows, and episode CSV
  - no-artifact regression coverage for rejected joint_position, residual_baseline, and unknown modes
affects: [locomotion-evaluation, CLI-action-mode-contract, LOC-ENV-04, LOC-EVAL-03]

tech-stack:
  added: []
  patterns:
    - validate user-selected action modes during matrix validation before filesystem side effects
    - import action-mode names from src.locomotion.actions instead of duplicating env mode strings
    - record artifact action_mode only for validated completed velocity_command runs

key-files:
  created:
    - .planning/phases/07-align-evaluation-action-mode-contract/07-01-SUMMARY.md
  modified:
    - src/locomotion/evaluation.py
    - tests/locomotion/test_locomotion_evaluation_runner.py
    - tests/locomotion/test_locomotion_evaluation_exports.py

key-decisions:
  - "argus eval-locomotion runs only velocity_command until concrete non-default evaluator action sources exist."
  - "joint_position and residual_baseline remain environment-supported seams but are rejected by evaluation matrix validation before any env or artifact side effects."

patterns-established:
  - "Evaluator action-mode capability is narrower than env action-mode support and is enforced in validate_evaluation_matrix()."
  - "Rejected action-mode requests leave output roots empty because run directories are prepared only after validation."

requirements-completed: [LOC-ENV-04, LOC-EVAL-03]

duration: 4min 6s
completed: 2026-05-02
---

# Phase 07 Plan 01: Action-Mode Evaluation Contract Summary

**Velocity-command-only locomotion evaluator contract with fail-fast rejection for unevaluable env action-mode seams and completed-run action-mode artifact metadata.**

## Performance

- **Duration:** 4min 6s
- **Started:** 2026-05-02T05:56:44Z
- **Completed:** 2026-05-02T06:00:50Z
- **Tasks:** 3
- **Files modified:** 3 source/test files plus this summary

## Accomplishments

- Added runner regressions proving unknown, `joint_position`, and `residual_baseline` action modes fail before env construction and before output artifacts are created.
- Added export regressions proving completed `velocity_command` runs record action mode consistently in manifest top-level metadata, validated cells, manifest run rows, JSONL step rows, and episode CSV rows.
- Implemented evaluator action-mode validation using `ACTION_MODE_VELOCITY` and `available_action_modes()` from `src.locomotion.actions`, preserving Phase 6 same-index command/export semantics.
- Strengthened no-artifact rejection coverage to include `joint_position`, `residual_baseline`, and unknown strings.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Wave 0 runner and export contract tests for action modes** - `8d373e3` (test)
2. **Task 2: Implement fail-fast evaluator action-mode validation** - `2e6e1f2` (feat)
3. **Task 3: Finalize action-mode artifact metadata and quick gate** - `958fd36` (test)

**Plan metadata:** pending final docs commit

_Note: TDD plan executed with RED test commit followed by GREEN implementation and a final metadata/no-artifact coverage tightening commit._

## Files Created/Modified

- `src/locomotion/evaluation.py` - Adds evaluator-runnable action-mode constant and pre-side-effect validation for unknown or unevaluable action modes.
- `tests/locomotion/test_locomotion_evaluation_runner.py` - Adds pre-env-construction rejection regressions while preserving same-index executed command checks.
- `tests/locomotion/test_locomotion_evaluation_exports.py` - Adds completed-run action-mode metadata checks and rejected-mode no-artifact checks.
- `.planning/phases/07-align-evaluation-action-mode-contract/07-01-SUMMARY.md` - Execution summary for this plan.

## Decisions Made

- `argus eval-locomotion` currently runs only `velocity_command`; non-default env modes require explicit future action sources before they can become evaluator-runnable.
- Unknown action modes are distinguished from known-but-unevaluable env seams: unknown strings report the authoritative env action-mode list, while `joint_position` and `residual_baseline` report that they have no evaluator action source.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing web optional dependencies in the local uv environment for the quick gate**
- **Found during:** Task 3 (quick gate)
- **Issue:** `tests/test_main_args.py` imported `src.main`, which imports `fastapi` through the MCP server path; the fresh worktree uv environment lacked the project `web` optional dependencies, causing four unrelated quick-gate failures.
- **Fix:** Installed `fastapi`, `uvicorn`, and `websockets` into the local uv environment using `uv pip install` so the planned quick gate could run.
- **Files modified:** None; environment-only dependency installation.
- **Verification:** `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` passed with 65 tests.
- **Committed in:** Not applicable; environment-only fix.

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Environment setup only. No source scope expansion beyond the planned files and tests.

## Issues Encountered

- Initial RED run failed as expected for the new action-mode rejection tests before production implementation.
- Focused export verification passed immediately after implementation; the broader quick gate required the local web optional dependencies described above.

## Verification

- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` → 24 passed.
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` → 9 passed.
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py -q` → 65 passed.
- `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` → 255 passed.

## Known Stubs

None. Stub scan found only legitimate empty dict/list initialization in runner internals and fake-test capture lists, plus the pre-existing placeholder-controller test name; none are user-visible stubs or incomplete plan behavior.

## Threat Flags

None. The plan modified existing CLI/evaluation validation and artifact behavior at the trust boundaries already listed in the plan threat model; no new endpoint, auth path, file-access pattern, or schema trust boundary was introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 02 can update CLI help and benchmark documentation to describe the same implemented contract: `velocity_command` is evaluator-runnable, while `joint_position` and `residual_baseline` are environment seams rejected until explicit action sources exist.

## Self-Check: PASSED

Verified created/modified files exist and task commits are present in git history:

- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ad2fdeb1a04abe560/src/locomotion/evaluation.py`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ad2fdeb1a04abe560/tests/locomotion/test_locomotion_evaluation_runner.py`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ad2fdeb1a04abe560/tests/locomotion/test_locomotion_evaluation_exports.py`
- FOUND: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-ad2fdeb1a04abe560/.planning/phases/07-align-evaluation-action-mode-contract/07-01-SUMMARY.md`
- FOUND commits: `8d373e3`, `2e6e1f2`, `958fd36`

---
*Phase: 07-align-evaluation-action-mode-contract*
*Completed: 2026-05-02*
