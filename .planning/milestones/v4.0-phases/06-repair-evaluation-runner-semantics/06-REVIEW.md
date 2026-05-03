---
phase: 06-repair-evaluation-runner-semantics
reviewed: 2026-05-01T13:51:27Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/locomotion/env.py
  - src/locomotion/evaluation.py
  - tests/locomotion/test_argus_go2_env_contract.py
  - tests/locomotion/test_locomotion_baseline_regression.py
  - tests/locomotion/test_locomotion_evaluation_exports.py
  - tests/locomotion/test_locomotion_evaluation_runner.py
findings:
  critical: 2
  warning: 1
  info: 0
  total: 3
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-01T13:51:27Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the locomotion environment, evaluation runner, and associated regression/export tests at standard depth. The current implementation still has correctness defects in command execution and failure reporting: velocity-command steps dispatch the caller action rather than the scenario schedule, the runner treats synthetic max-step truncation as successful even when no terminal episode summary exists, and the environment can continue reporting a later schedule command after velocity actions override the active command.

## Critical Issues

### CR-01: Evaluation runner executes the previous step's command instead of the active schedule command

**File:** `src/locomotion/evaluation.py:244-251`

**Issue:** The runner derives `action` from `latest_info` before calling `env.step()`. After `reset()`, `latest_info` is reset metadata that usually lacks `current_command`, so `_action_from_command_context()` falls back to `command_schedule[0]`. On a schedule with a nonzero transition at time 0.2-0.6s, the runner repeatedly sends the prior command one step late: the step that advances past the transition still executes `[0,0,0]`, and only the following step sees the transitioned `current_command`. If an environment terminates or is capped on the transition step, the commanded velocity recorded in artifacts is the old command, while the environment's `info["current_command"]` reports the new active command. This invalidates LOC-EVAL baseline semantics and can mask a stationary controller as having been tested under the intended nonzero command.

**Fix:** Derive the command to execute from the environment's current schedule and simulation time before stepping, not from the previous step's `current_command`. A concrete fix is to prefer the active item in `command_schedule` using `latest_info["sim_time"]`, and record the executed action while also storing post-step info separately.

```python
def _action_from_command_context(info: dict[str, Any]) -> tuple[list[float], str, dict[str, Any]]:
    command_schedule = _serializable_sequence(info.get("command_schedule", ()))
    if command_schedule:
        sim_time = float(info.get("sim_time") or 0.0)
        active = command_schedule[0]
        for command in command_schedule:
            if float(command.get("time", 0.0)) <= sim_time + 1e-12:
                active = command
            else:
                break
        return _command_vector(active), "scenario_schedule", {
            "current_command": dict(active) | {"source": "scenario_schedule"},
            "command_schedule": command_schedule,
        }
    current_command = info.get("current_command")
    if isinstance(current_command, dict):
        return _command_vector(current_command), str(current_command.get("source", "current_command")), {
            "current_command": dict(current_command),
            "command_schedule": command_schedule,
        }
    return [0.0, 0.0, 0.0], "default_zero", {"command_schedule": []}
```

### CR-02: Matrix step cap can convert an incomplete non-terminating episode into a successful row

**File:** `src/locomotion/evaluation.py:253-279`

**Issue:** The runner enforces `max_episode_steps` by setting only the local `truncated = True` after `env.step()`. It does not ask the environment for a final summary after that synthetic truncation, and if the environment did not include `locomotion_metrics_summary` on the uncapped non-terminal step, the runner falls back to `{}`. `_episode_csv_row()` then emits `success=False`, `failure_reason=""`, and `step_count=0`, while `had_locomotion_failure` remains `False` because `success is False` is not true for a missing summary. With `fail_on_locomotion_failure=True`, this produces exit code 0 for an evaluation row that is marked unsuccessful and has no terminal summary. Downstream gates can therefore miss non-terminating or improperly summarized environments.

**Fix:** When the runner truncates due to the matrix cap, synthesize or require a terminal summary before writing artifacts, and treat missing/false success as a locomotion failure. At minimum, preserve the observed step count and mark the row as a cap failure.

```python
if runner_step_count >= int(cell["max_episode_steps"]):
    truncated = True
    latest_info.setdefault("locomotion_metrics_summary", {
        "command_tracking": {},
        "stability": {},
        "action_quality": {},
        "contact_terrain": {},
        "success": False,
        "failure_reason": "max_episode_steps_exceeded",
        "step_count": runner_step_count,
    })

summary = latest_info.get("locomotion_metrics_summary")
if not isinstance(summary, dict) or summary.get("success") is not True:
    had_locomotion_failure = True
```

## Warnings

### WR-01: Step info can report a scenario command that was not executed in velocity-command mode

**File:** `src/locomotion/env.py:140-149,454-474`

**Issue:** In velocity-command mode `step()` sets `self._command` to the validated action, but `_info()` always recomputes `current_command` from the scenario schedule using `_command_at_time(sim_time)`. When a caller intentionally sends a velocity action different from the schedule, `obs["command"]` and metrics use the executed action while `info["current_command"]` claims the schedule command was active. The evaluation runner relies on `info["current_command"]` as command attribution, so artifacts can describe a command that the controller did not actually execute.

**Fix:** Make `_info()` report the executed command for velocity-command mode, or add separate fields for scheduled versus executed command and have the runner consume the executed field.

```python
if self.config.action_mode == ACTION_MODE_VELOCITY:
    active_command = self._command
    command_source = "velocity_action"
else:
    active_command = self._command_at_time(sim_time)
    command_source = "scenario_schedule"

info["current_command"] = {
    "time": float(sim_time),
    "vx": float(active_command[0]),
    "vy": float(active_command[1]),
    "omega": float(active_command[2]),
    "source": command_source,
}
```

---

_Reviewed: 2026-05-01T13:51:27Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
