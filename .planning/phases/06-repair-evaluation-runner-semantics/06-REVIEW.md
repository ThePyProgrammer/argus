---
phase: 06-repair-evaluation-runner-semantics
reviewed: 2026-05-01T10:28:02Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/locomotion/env.py
  - src/locomotion/evaluation.py
  - tests/locomotion/test_argus_go2_env_contract.py
  - tests/locomotion/test_locomotion_evaluation_runner.py
  - tests/locomotion/test_locomotion_evaluation_exports.py
  - tests/locomotion/test_locomotion_baseline_regression.py
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-01T10:28:02Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 06 locomotion environment, evaluation runner, and associated tests. The implementation has two correctness defects in production code: the runner can hang forever when an environment never reports termination, and velocity-command mode misattributes tracking metrics by recording the raw action instead of the active scenario command used to drive the controller.

## Critical Issues

### CR-01: Evaluation loop can run forever if env ignores or exceeds the matrix step cap

**File:** `src/locomotion/evaluation.py:243`

**Issue:** `run_evaluation_matrix` loops only on `terminated`/`truncated` from the environment:

```python
while not (terminated or truncated):
```

The matrix validates and passes `max_episode_steps`, but the runner never enforces it. A custom `env_factory` or a broken environment that keeps returning `(terminated=False, truncated=False)` will hang the evaluation process indefinitely, never writing artifacts or returning an exit code. This is especially bad because `env_factory` is an exposed extension seam and the phase specifically repairs evaluation-runner semantics.

**Fix:** Enforce the validated per-cell step cap in the runner, independent of environment behavior, and treat hitting the cap as truncation:

```python
step_count = 0
while not (terminated or truncated):
    if step_count >= cell["max_episode_steps"]:
        truncated = True
        break
    action, source, initial_context = _action_from_command_context(latest_info)
    _observation, _reward, terminated, truncated, info = env.step(np.asarray(action, dtype=np.float32))
    step_count += 1
    ...
```

Also add a regression test with a fake environment that never terminates and assert the runner returns after exactly `max_episode_steps` steps with artifacts written.

## Warnings

### WR-01: Velocity-command metrics are recorded against the wrong desired command

**File:** `src/locomotion/env.py:140`

**Issue:** In `velocity_command` mode, the controller command is built from `velocity_action`, but `self._command` is overwritten with that raw action before metrics are recorded. This makes `desired_command` in `_record_locomotion_metrics` equal to the caller action, not necessarily the active scenario command from `current_command`/`command_schedule`. In the evaluation runner this is masked by tests whose fake env echoes the schedule, but the real `ArgusGo2Env` will report command tracking against the action selected before stepping, not the scenario command context after stepping. When schedules transition during a step, tracking RMSE and progress/failure checks can be attributed to the wrong command.

**Fix:** Keep separate variables for the controller input command and the command that should be reported/measured for the completed step. For example, compute the active scenario command at the same time used for `current_command`, pass that to metrics, and only store the raw action as previous policy input if needed:

```python
if self.config.action_mode == ACTION_MODE_VELOCITY:
    velocity_action = self._validate_velocity_action(action)
    active_command = self._command_at_time(self._current_sim_time())
    command_obj = command_from_velocity(active_command[:2], float(active_command[2]), metadata={"controller_id": self.config.controller_id})
    result = dispatch_controller(..., command_obj, ...)
    ctrl = result.action
    self._command = active_command.copy()
...
metrics_step = self._record_locomotion_metrics(
    desired_command=self._command,
    ...
)
```

If the intended contract is instead that velocity-command action overrides the scenario schedule, then `_info()`/evaluation export should stop labeling it as `scenario_schedule`; otherwise the command context and metrics are inconsistent.

---

_Reviewed: 2026-05-01T10:28:02Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
