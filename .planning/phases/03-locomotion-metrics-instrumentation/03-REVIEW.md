---
phase: 03-locomotion-metrics-instrumentation
reviewed: 2026-04-30T16:22:29Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/locomotion/metrics.py
  - tests/locomotion/test_locomotion_metrics_collector.py
  - tests/locomotion/test_argus_go2_env_metrics.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-30T16:22:29Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the Phase 03 Plan 05 gap-closure changes for progress-stall gating in the metrics collector and the added collector/environment regression tests. The zero-command and yaw-only cases are now gated out by translational command magnitude, but the stall detector still reuses distance history collected during prior zero/yaw-only commands. That creates a command-transition false termination not covered by the new tests.

## Critical Issues

### CR-01: Progress-stall uses zero-command history after command transitions

**File:** `src/locomotion/metrics.py:300-309`

**Issue:** `_progress_stalled` gates on only the current `desired_command[:2]`, but computes progress against the previous `progress_window_steps` distances regardless of what commands were active during that window. After an agent stands still for at least `progress_window_steps` under zero or yaw-only commands, the first nonzero translational command can immediately compare against the stationary zero-command window and return `progress_stalled` before the robot has had a full commanded-progress window to move. This violates the intended zero-command/yaw-only exemption in command schedules that transition from standing/yawing to walking, and can still false-terminate valid `ArgusGo2Env` episodes immediately after repeated zero commands.

**Fix:** Track whether each retained step was subject to progress-stall enforcement and require the whole evaluated window to have a translational command above `min_progress_command_speed_m_per_s` before declaring a stall. For example, store command speed (or a boolean) in the step stability payload and ignore windows containing below-threshold commands:

```python
# In _stability_payload, include command-gating evidence in the payload.
desired_translational_speed = float(np.linalg.norm(desired_command[:2]))
progress_check_active = desired_translational_speed >= self.config.min_progress_command_speed_m_per_s
elif self._progress_stalled(progress_check_active, distance, dt):
    failure_reason = "progress_stalled"

return {
    ...,
    "progress_check_active": progress_check_active,
    "distance_xy_m": distance,
    "failure_reason": failure_reason,
}, failure_reason

# In _progress_stalled, require a fully active prior window.
def _progress_stalled(self, progress_check_active: bool, current_distance: float, dt: float) -> bool:
    if not progress_check_active or len(self._steps) < self.config.progress_window_steps:
        return False
    window = list(self._steps)[-self.config.progress_window_steps:]
    if not all(bool(step.stability.get("progress_check_active")) for step in window):
        return False
    start_distance = float(window[0].stability["distance_xy_m"])
    elapsed = max(float(len(window)) * dt, dt)
    return (current_distance - start_distance) / elapsed < self.config.min_progress_m_per_s
```

Also add a regression test that records `progress_window_steps + 1` stationary zero-command steps, then switches to a nonzero translational command and asserts no stall until a full nonzero-command window has elapsed.

---

_Reviewed: 2026-04-30T16:22:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
