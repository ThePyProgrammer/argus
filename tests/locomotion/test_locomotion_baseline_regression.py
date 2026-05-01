"""Analytical trot flat-ground regression thresholds.

LOC-EVAL-04 / D-13 / D-14 / D-15: keep the current analytical
baseline guarded by robust thresholds, not golden snapshots. T-04-03 keeps
calibration context explicit when thresholds change.
"""

from __future__ import annotations

import json

import pytest

TRACKING_RMSE_MAX = 1.50
DISTANCE_XY_MIN_M = 0.01
BASE_HEIGHT_MIN_M = 0.15
ROLL_ABS_MAX_RAD = 0.90
PITCH_ABS_MAX_RAD = 0.90


def assert_analytical_flat_ground_thresholds(rows):
    """Assert robust threshold bounds for analytical_trot flat_ground episodes."""

    materialized = list(rows)
    assert materialized, "expected at least one analytical flat-ground episode row"
    for index, row in enumerate(materialized):
        label = row.get("run_id", f"row[{index}]")
        assert row.get("success") is True, f"{label}: locomotion success must be true"
        assert not row.get("failure_reason"), f"{label}: failure_reason must be empty"
        assert "commanded_velocity" in row, f"{label}: commanded_velocity is required"
        assert "command_source" in row, f"{label}: command_source is required"
        assert row["command_source"], f"{label}: command_source must be non-empty"

        commanded_velocity = _coerce_commanded_velocity(row["commanded_velocity"])
        translational_speed = (commanded_velocity[0] ** 2 + commanded_velocity[1] ** 2) ** 0.5
        tracking_rmse = _coerce_float(row, "tracking_rmse")
        distance_xy_m = _coerce_float(row, "distance_xy_m")
        base_height_min_m = _coerce_float(row, "base_height_min_m")
        roll_abs_max_rad = _coerce_float(row, "roll_abs_max_rad")
        pitch_abs_max_rad = _coerce_float(row, "pitch_abs_max_rad")

        assert tracking_rmse <= TRACKING_RMSE_MAX, f"{label}: tracking_rmse {tracking_rmse} > {TRACKING_RMSE_MAX}"
        if translational_speed > 0.0:
            assert distance_xy_m >= DISTANCE_XY_MIN_M, (
                f"{label}: distance_xy_m {distance_xy_m} < {DISTANCE_XY_MIN_M} "
                f"for commanded_velocity={commanded_velocity}"
            )
        assert base_height_min_m >= BASE_HEIGHT_MIN_M, (
            f"{label}: base_height_min_m {base_height_min_m} < {BASE_HEIGHT_MIN_M}"
        )
        assert roll_abs_max_rad <= ROLL_ABS_MAX_RAD, (
            f"{label}: roll_abs_max_rad {roll_abs_max_rad} > {ROLL_ABS_MAX_RAD}"
        )
        assert pitch_abs_max_rad <= PITCH_ABS_MAX_RAD, (
            f"{label}: pitch_abs_max_rad {pitch_abs_max_rad} > {PITCH_ABS_MAX_RAD}"
        )


def _coerce_commanded_velocity(value):
    if isinstance(value, str):
        value = json.loads(value)
    assert isinstance(value, (list, tuple)), "commanded_velocity must be a sequence"
    assert len(value) >= 3, "commanded_velocity must include vx, vy, and yaw rate"
    return [float(value[0]), float(value[1]), float(value[2])]


def _coerce_float(row, key):
    assert key in row, f"{key} is required"
    return float(row[key])


def _good_row(**overrides):
    row = {
        "run_id": "r0001",
        "controller_id": "analytical_trot",
        "scenario_id": "flat_ground",
        "seed": 101,
        "action_mode": "velocity_command",
        "success": True,
        "failure_reason": "",
        "commanded_velocity": [0.4, 0.0, 0.0],
        "command_source": "scenario_schedule",
        "tracking_rmse": 0.20,
        "distance_xy_m": 0.05,
        "base_height_min_m": 0.24,
        "roll_abs_max_rad": 0.20,
        "pitch_abs_max_rad": 0.25,
    }
    row.update(overrides)
    return row


def test_threshold_helper_accepts_bounded_successful_rows():
    rows = (
        _good_row(run_id="r0001", seed=101),
        _good_row(run_id="r0002", seed=202, tracking_rmse=0.30, distance_xy_m=0.04),
    )

    assert_analytical_flat_ground_thresholds(rows)


@pytest.mark.parametrize(
    "overrides",
    [
        {"success": False},
        {"failure_reason": "base_height_below_threshold"},
    ],
)
def test_threshold_helper_rejects_locomotion_failure(overrides):
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([_good_row(**overrides)])


def test_threshold_helper_rejects_tracking_degradation():
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([_good_row(tracking_rmse=TRACKING_RMSE_MAX + 0.01)])


def test_threshold_helper_rejects_zero_distance_for_translational_command():
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([
            _good_row(commanded_velocity=[0.4, 0.0, 0.0], distance_xy_m=DISTANCE_XY_MIN_M - 0.001)
        ])


@pytest.mark.parametrize("missing_key", ["commanded_velocity", "command_source"])
def test_threshold_helper_rejects_missing_command_context(missing_key):
    row = _good_row()
    row.pop(missing_key)

    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([row])


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_height_min_m", BASE_HEIGHT_MIN_M - 0.01),
        ("roll_abs_max_rad", ROLL_ABS_MAX_RAD + 0.01),
        ("pitch_abs_max_rad", PITCH_ABS_MAX_RAD + 0.01),
    ],
)
def test_threshold_helper_rejects_stability_degradation(field, value):
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([_good_row(**{field: value})])
