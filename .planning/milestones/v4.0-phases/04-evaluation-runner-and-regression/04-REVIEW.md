---
phase: 04-evaluation-runner-and-regression
reviewed: 2026-05-01T05:37:31Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - src/locomotion/evaluation.py
  - src/main.py
  - tests/locomotion/test_locomotion_evaluation_runner.py
  - tests/locomotion/test_locomotion_evaluation_exports.py
  - tests/locomotion/test_locomotion_baseline_regression.py
  - tests/test_main_args.py
findings:
  critical: 2
  warning: 0
  info: 0
  total: 2
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-01T05:37:31Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the locomotion evaluation runner, CLI integration, and listed regression/export tests at standard depth. The runner currently flattens production metric summaries using key names that do not match the actual `LocomotionMetricsCollector` summary schema, causing exported CSV/summary artifacts and baseline gates to silently report zero for several core metrics. There is also an unbounded simulation-loop edge case: fake/test environments or malformed environments that never terminate can hang evaluation indefinitely despite `max_episode_steps` being part of the validated run contract.

## Critical Issues

### CR-01: Episode export drops real stability/action/contact metrics due to schema mismatch

**File:** `src/locomotion/evaluation.py:489-498`
**Issue:** `_episode_csv_row()` reads `base_height_min_m`, `base_height_max_deviation_m`, `roll_abs_max_rad`, `pitch_abs_max_rad`, `action_smoothness_mean`, `position_servo_effort_mean`, `joint_limit_violation_count`, `actuator_saturation_count`, `foot_slip_mean`, `foot_clearance_mean`, and `duty_factor_mean`. The production metrics summary emitted by `src/locomotion/metrics.py` uses different keys such as `min_base_height_m`, `max_base_height_deviation_m`, `max_abs_roll_rad`, `max_abs_pitch_rad`, `action_delta_norm_mean`, `position_servo_effort_proxy_mean`, and nested contact dictionaries (`slip_mean_m_per_s`, `clearance_min_m`, `duty_factor`). As a result, real evaluation artifacts default these fields to `0.0`, hiding falls/instability and corrupting `episodes.csv`, `summary.json`, and `comparison.md`. This is not just a naming nit: the regression thresholds consume these flattened values and can pass with impossible zero roll/pitch and zero base height if their fallback is also mis-keyed.

**Fix:** Map exported scorecard fields to the actual summary schema, with compatibility aliases if the new flat names must be retained. For example:

```python
def _metric_alias(mapping: dict[str, Any], *keys: str, default: float = 0.0) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return _jsonable(mapping[key])
    return default

row.update(
    {
        "base_height_min_m": _metric_alias(stability, "base_height_min_m", "min_base_height_m"),
        "base_height_max_deviation_m": _metric_alias(
            stability, "base_height_max_deviation_m", "max_base_height_deviation_m"
        ),
        "roll_abs_max_rad": _metric_alias(stability, "roll_abs_max_rad", "max_abs_roll_rad"),
        "pitch_abs_max_rad": _metric_alias(stability, "pitch_abs_max_rad", "max_abs_pitch_rad"),
        "action_smoothness_mean": _metric_alias(
            action_quality, "action_smoothness_mean", "action_delta_norm_mean"
        ),
        "position_servo_effort_mean": _metric_alias(
            action_quality, "position_servo_effort_mean", "position_servo_effort_proxy_mean"
        ),
        "joint_limit_violation_count": _metric_alias(
            action_quality,
            "joint_limit_violation_count",
            "commanded_joint_limit_violation_count_total",
        ),
        "actuator_saturation_count": _metric_alias(
            action_quality, "actuator_saturation_count", "position_target_saturation_proxy_total"
        ),
        "foot_slip_mean": _aggregate_contact_metric(contact_terrain, "foot_slip_mean", "slip_mean_m_per_s"),
        "foot_clearance_mean": _aggregate_contact_metric(contact_terrain, "foot_clearance_mean", "clearance_min_m"),
        "duty_factor_mean": _aggregate_contact_metric(contact_terrain, "duty_factor_mean", "duty_factor"),
    }
)
```

Add a test that runs against a summary shaped like `LocomotionMetricsCollector.episode_summary()` rather than only the already-flattened fake summary currently used in export tests.

### CR-02: Regression threshold fallback uses obsolete stability summary keys

**File:** `tests/locomotion/test_locomotion_baseline_regression.py:52-54`
**Issue:** The baseline regression helper falls back from CSV row values to summary keys named `min_base_height_m`, `max_abs_roll_rad`, and `max_abs_pitch_rad`, but the helper passes row labels `base_height_min_m`, `roll_abs_max_rad`, and `pitch_abs_max_rad`. This fallback happens only after `_is_missing_metric_value()` treats a `0.0` CSV value as missing. Combined with the export bug above, production rows can contain `0.0` for these flattened fields while the fallback then looks under keys that are inconsistent with the fake export tests and with the flattened fields. The practical result is fragile regression coverage: the helper can either raise on valid rows shaped with the new flattened names or mask the exporter writing zeros by relying on a different summary schema. The test should assert one canonical schema instead of allowing the exporter and regression gate to drift apart.

**Fix:** Align the regression helper with the actual artifact contract after fixing the exporter. If `episodes.csv` is the contract under test, require non-zero/non-missing flattened CSV fields and remove the summary fallback. If summary fallback remains for in-memory rows, use explicit aliases and do not treat legitimate zero-valued metrics as universally missing:

```python
base_height_min_m = _coerce_metric(
    row, summary, "base_height_min_m", "stability", "min_base_height_m", "base_height_min_m"
)
roll_abs_max_rad = _coerce_metric(
    row, summary, "roll_abs_max_rad", "stability", "max_abs_roll_rad", "roll_abs_max_rad"
)
pitch_abs_max_rad = _coerce_metric(
    row, summary, "pitch_abs_max_rad", "stability", "max_abs_pitch_rad", "pitch_abs_max_rad"
)
```

Then add a regression test that fails when `episodes.csv` contains `0.0` for `base_height_min_m` while the summary contains the real `min_base_height_m` value, so the export bug cannot reappear silently.

---

_Reviewed: 2026-05-01T05:37:31Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
