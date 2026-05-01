---
phase: 06-repair-evaluation-runner-semantics
reviewed: 2026-05-01T12:07:13Z
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
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-01T12:07:13Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the locomotion environment, evaluation runner, and listed regression/export tests at standard depth. The runner-side max-step guard has been added, but production code still contains one blocking correctness defect in the real velocity-command environment and one robustness defect in metric export aggregation.

## Critical Issues

### CR-01: Velocity-command mode ignores the scenario command schedule in the real environment

**File:** `src/locomotion/env.py:125-140`

**Issue:** In `ACTION_MODE_VELOCITY`, `step()` validates the caller action and dispatches the controller with that action directly, then stores it in `self._command`. The active scenario schedule is only used by `_info()`, not by the controller. `run_evaluation_matrix()` chooses the next action from the previous step/reset info, so when a schedule transition occurs at the step boundary the runner sends the old command for the entire just-completed step. After the step, `_info()` reports the new `current_command`, causing exported rows to claim the run used `[0.4, 0.0, 0.0]` while the controller was actually driven with the previous `[0.0, 0.0, 0.0]` command for that step. This silently invalidates tracking metrics and the regression gate for scheduled command transitions in real `ArgusGo2Env` runs; the fake-env tests only assert runner behavior and do not exercise the real environment/controller path.

**Fix:** Make the environment authoritative for scheduled velocity commands, or make the export label raw policy actions honestly. If scenario schedules are the intended source of truth, compute the active command inside `step()` at the simulation time being applied and dispatch/record that command consistently:

```python
if self.config.action_mode == ACTION_MODE_VELOCITY:
    velocity_action = self._validate_velocity_action(action)
    scheduled_command = self._command_at_time(self._current_sim_time())
    command_obj = command_from_velocity(
        scheduled_command[:2],
        float(scheduled_command[2]),
        metadata={"controller_id": self.config.controller_id},
    )
    result = dispatch_controller(
        self._controller,
        extract_observation(self._data, scheduled_command, self._previous_action),
        command_obj,
        self._dt,
        data=self._data,
    )
    ctrl = result.action
    self._command = scheduled_command.copy()
```

Then record metrics and observations against the same command that actually drove the controller. Alternatively, if actions are supposed to override the schedule, change `_info()`/evaluation export so `current_command.source` and `commanded_velocity` reflect the action actually applied, not `scenario_schedule`.

## Warnings

### WR-01: Contact terrain metric export can crash on non-numeric per-foot values

**File:** `src/locomotion/evaluation.py:543-547`

**Issue:** `_contact_metric_mean()` assumes that every non-`None` value inside a dict metric can be converted with `float(item)`. Saved or fake environment summaries are accepted as plain dictionaries at the artifact boundary, so a malformed or partially serialized contact metric such as `{"FL": "n/a"}` raises `ValueError` while building the episode row. That aborts the whole evaluation after simulation has run and before artifacts are written. Other numeric aggregation paths in this file use tolerant coercion (`_to_float`), but this branch does not.

**Fix:** Reuse tolerant numeric coercion or explicitly skip non-numeric values when averaging contact metrics:

```python
def _contact_metric_mean(mapping: dict[str, Any], *keys: str, default: float = 0.0) -> Any:
    value = _metric_alias(mapping, *keys, default=default)
    if isinstance(value, dict):
        numeric_values = []
        for item in value.values():
            if item is None:
                continue
            try:
                numeric_values.append(float(item))
            except (TypeError, ValueError):
                continue
        return sum(numeric_values) / len(numeric_values) if numeric_values else default
    return value
```

Add a regression test that passes a dict-valued contact metric with one malformed per-foot value and verifies evaluation still writes artifacts using the valid numeric values or the default.

---

_Reviewed: 2026-05-01T12:07:13Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
