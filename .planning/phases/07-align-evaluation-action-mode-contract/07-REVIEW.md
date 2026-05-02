---
phase: 07-align-evaluation-action-mode-contract
reviewed: 2026-05-02T06:08:58Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - src/locomotion/evaluation.py
  - src/main.py
  - docs/locomotion-benchmark.md
  - tests/locomotion/test_locomotion_evaluation_runner.py
  - tests/locomotion/test_locomotion_evaluation_exports.py
  - tests/test_main_args.py
  - tests/test_locomotion_benchmark_docs.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-02T06:08:58Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the locomotion evaluation runner, CLI wiring, benchmark documentation contract, and related regression tests. The main correctness defect is in the `eval-locomotion` CLI merge logic: matrix-config scalar values are silently overwritten by argparse defaults, so JSON configs cannot actually define action mode or episode/runtime settings unless they happen to match CLI defaults. There are also documentation rendering and test portability defects that should be fixed before relying on this contract gate.

## Critical Issues

### CR-01: Matrix config action/runtime fields are silently ignored by the CLI

**File:** `src/main.py:300-307`
**Issue:** `run_eval_locomotion_mode()` always rebuilds `EvaluationMatrix` with `args.action_mode`, `args.max_episode_steps`, `args.sim_steps_per_frame`, and `args.heightfield_size`. Those parser arguments have concrete defaults at `src/main.py:134-139`, so a JSON matrix config's scalar fields are overwritten even when the user did not pass the corresponding CLI flags. This breaks the documented matrix-config workflow and the new action-mode contract: a config containing `"action_mode": "joint_position"` should fail fast as unsupported, but the CLI replaces it with `velocity_command` and runs instead. Likewise `max_episode_steps`, `sim_steps_per_frame`, and `heightfield_size` from saved configs are ignored.
**Fix:** Make eval-locomotion scalar CLI defaults `None`, then preserve matrix-config values unless the flag was explicitly supplied. For example:

```python
# parse_args(): use None so absence can be distinguished from an explicit CLI override.
eval_parser.add_argument("--max-episode-steps", type=int, default=None)
eval_parser.add_argument("--sim-steps-per-frame", type=int, default=None)
eval_parser.add_argument("--heightfield-size", type=int, default=None)
eval_parser.add_argument(
    "--action-mode",
    default=None,
    help=(
        "Action mode for evaluation. velocity_command is the evaluator-runnable mode; "
        "joint_position and residual_baseline are env-supported seams that fail fast "
        "in eval-locomotion until explicit action sources exist."
    ),
)

# run_eval_locomotion_mode(): preserve loaded matrix values unless overridden.
matrix = EvaluationMatrix(
    controllers=_defaulted_eval_sequence(args.controller, matrix.controllers),
    scenarios=_defaulted_eval_sequence(args.scenario, matrix.scenarios),
    seeds=_defaulted_eval_sequence(args.seed, matrix.seeds),
    action_mode=matrix.action_mode if args.action_mode is None else args.action_mode,
    max_episode_steps=matrix.max_episode_steps if args.max_episode_steps is None else args.max_episode_steps,
    sim_steps_per_frame=matrix.sim_steps_per_frame if args.sim_steps_per_frame is None else args.sim_steps_per_frame,
    heightfield_size=matrix.heightfield_size if args.heightfield_size is None else args.heightfield_size,
)
```

Add a CLI-level regression test that invokes `eval-locomotion --matrix-config config.json` with non-default scalar values, including an unsupported action mode, and asserts the config values are honored before env construction/artifact creation.

## Warnings

### WR-01: Benchmark guide has broken inline-code markup for the action-mode contract

**File:** `docs/locomotion-benchmark.md:37`
**Issue:** The sentence starts an inline-code span before `argus` and then nests another backtick pair around `velocity_command`: `` `argus eval-locomotion currently runs `velocity_command`; ...``. Markdown renderers will terminate the code span before `velocity_command`, leaving the contract sentence malformed and harder to read. This is a documentation contract file, so broken markup undermines the phase's user-facing contract.
**Fix:** Do not wrap the whole sentence in one inline-code span. Wrap only command/token names:

```markdown
The environment-supported action modes are listed below. `argus eval-locomotion` currently runs `velocity_command`; `joint_position` and `residual_baseline` are env-supported seams that fail fast in evaluation until explicit action sources exist.
```

### WR-02: Help-output subprocess tests are hardcoded to one developer's venv path

**File:** `tests/test_main_args.py:241-244` and `tests/test_main_args.py:270-273`
**Issue:** The help tests invoke `/home/prannayag/pragnition/robotics/argus/.venv/bin/python` directly. That makes the test suite non-portable and flaky in CI, worktrees, containers, or any clone not located at that exact absolute path. Test files are in scope here because this directly affects test reliability.
**Fix:** Use the interpreter running the test process, as the existing labeled-eval-set subprocess test already does:

```python
proc = subprocess.run(
    [sys.executable, "-m", "src.main", "eval-locomotion", "--help"],
    capture_output=True,
    text=True,
    timeout=60,
)
```

---

_Reviewed: 2026-05-02T06:08:58Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
