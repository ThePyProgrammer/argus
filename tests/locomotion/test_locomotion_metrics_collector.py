"""Unit tests for core locomotion metrics collector behavior."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
import pytest

from src.locomotion.metrics import LocomotionMetricsCollector, LocomotionMetricsConfig


ZERO12 = np.zeros(12, dtype=np.float64)
_THIS_FILE = __file__
_OUT_OF_SCOPE_TEST_FILES = (
    "tests/locomotion/test_locomotion_metrics_collector.py",  # out-of-scope guard scans jsonl/csv/evaluation_runner/rl_policy/mpc/wbc/ros2/frontend
    "tests/locomotion/test_locomotion_metrics_foot_mapping.py",
    "tests/locomotion/test_argus_go2_env_metrics.py",
)
_FORBIDDEN_PHASE3_SCOPE_TERMS = (
    "json" + "l",
    "c" + "sv",
    "evaluation" + "_runner",
    "rl" + "_policy",
    "m" + "pc",
    "w" + "bc",
    "ros" + "2",
    "front" + "end",
)


def _record_step(
    collector: LocomotionMetricsCollector,
    *,
    desired_command: Sequence[float] = (0.0, 0.0, 0.0),
    measured_base_velocity: Sequence[float] = (0.0, 0.0, 0.0),
    roll_rad: float = 0.0,
    pitch_rad: float = 0.0,
    base_height_m: float = 0.30,
    base_xy_position: Sequence[float] = (0.0, 0.0),
    action_target: Sequence[float] | np.ndarray = ZERO12,
    previous_action_target: Sequence[float] | np.ndarray = ZERO12,
    previous_previous_action_target: Sequence[float] | np.ndarray = ZERO12,
    joint_qpos: Sequence[float] | np.ndarray = ZERO12,
    joint_qvel: Sequence[float] | np.ndarray = ZERO12,
    dt: float = 0.02,
    contact_terrain_payload: Mapping[str, object] | None = None,
):
    return collector.record_step(
        desired_command=desired_command,
        measured_base_velocity=measured_base_velocity,
        roll_rad=roll_rad,
        pitch_rad=pitch_rad,
        base_height_m=base_height_m,
        base_xy_position=base_xy_position,
        action_target=action_target,
        previous_action_target=previous_action_target,
        previous_previous_action_target=previous_previous_action_target,
        joint_qpos=joint_qpos,
        joint_qvel=joint_qvel,
        dt=dt,
        contact_terrain_payload=contact_terrain_payload,
    )


def _assert_finite_payload(value: object) -> None:
    if isinstance(value, Mapping):
        for child in value.values():
            _assert_finite_payload(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _assert_finite_payload(child)
        return
    if value is None or isinstance(value, str) or isinstance(value, bool):
        return
    assert math.isfinite(float(value)), f"payload value is not finite: {value!r}"


def test_records_command_tracking_errors():
    """LOC-METRICS-01: command tracking records desired/measured/error fields."""
    collector = LocomotionMetricsCollector()

    step = _record_step(
        collector,
        desired_command=(0.5, -0.2, 0.3),
        measured_base_velocity=(0.2, -0.1, -0.1),
    )

    tracking = step.command_tracking
    assert tracking["desired"] == {"vx": 0.5, "vy": -0.2, "yaw_rate": 0.3}
    assert tracking["measured"] == {"vx": 0.2, "vy": -0.1, "yaw_rate": -0.1}
    assert tracking["signed_error"] == pytest.approx({"vx": -0.3, "vy": 0.1, "yaw_rate": -0.4})
    assert tracking["absolute_error"] == pytest.approx({"vx": 0.3, "vy": 0.1, "yaw_rate": 0.4})

    summary = collector.episode_summary().command_tracking
    assert set(summary) >= {"vx_rmse", "vy_rmse", "yaw_rate_rmse", "tracking_error_rmse"}
    assert summary["vx_rmse"] == pytest.approx(0.3)
    assert summary["vy_rmse"] == pytest.approx(0.1)
    assert summary["yaw_rate_rmse"] == pytest.approx(0.4)


def test_records_stability_failure_and_distance_before_failure():
    """LOC-METRICS-02: D-05 stability failure keeps fall and distance evidence."""
    config = LocomotionMetricsConfig(max_abs_roll_rad=0.8)
    collector = LocomotionMetricsCollector(config)

    step = _record_step(
        collector,
        roll_rad=0.81,
        base_xy_position=(1.2, 0.5),
    )

    assert step.stability["failure_reason"] == "roll_limit"
    assert step.failure_reason == "roll_limit"
    summary = collector.episode_summary()
    assert summary.success is False
    assert summary.failure_reason == "roll_limit"
    assert summary.stability["fall_count"] == 1
    assert summary.stability["fall_rate"] == 1.0
    assert summary.stability["distance_before_failure_m"] == pytest.approx(math.hypot(1.2, 0.5))
    assert "fall_rate" not in collector.latest_info_payload()

    no_failure = LocomotionMetricsCollector(config)
    _record_step(no_failure, base_xy_position=(0.1, 0.0))
    no_failure_summary = no_failure.episode_summary()
    assert no_failure_summary.success is True
    assert no_failure_summary.stability["fall_rate"] == 0.0


def test_records_action_quality_metrics():
    """LOC-METRICS-03: D-13 D-14 D-15 D-16 action-quality proxy metrics."""
    collector = LocomotionMetricsCollector()
    action_target = np.array(
        [
            1.0472,
            3.4907,
            -0.83776,
            1.0472,
            3.4907,
            -0.83776,
            1.0472,
            4.5379,
            -0.83776,
            1.0472,
            4.5379,
            -0.83776,
        ],
        dtype=np.float64,
    )
    previous = np.array([0.0, 0.9, -1.8] * 4, dtype=np.float64)
    previous_previous = previous - 0.05
    joint_qpos = action_target + 0.01
    joint_qvel = np.linspace(0.1, 1.2, 12, dtype=np.float64)

    step = _record_step(
        collector,
        action_target=action_target,
        previous_action_target=previous,
        previous_previous_action_target=previous_previous,
        joint_qpos=joint_qpos,
        joint_qvel=joint_qvel,
        dt=0.02,
    )

    action_quality = step.action_quality
    # D-13 smoothness uses first-difference and second-difference/jerk proxy names.
    assert action_quality["action_delta_norm"] > 0.0
    assert action_quality["action_jerk_proxy_norm"] > 0.0
    # D-14/D-16 threat mitigation: labels stay explicit position-servo/target proxies.
    assert "position_servo_effort_proxy" in action_quality
    assert "position_target_saturation_proxy" in action_quality
    assert "energy" not in " ".join(action_quality)
    assert action_quality["position_servo_effort_proxy"] > 0.0
    assert action_quality["position_target_saturation_proxy"] > 0
    assert action_quality["clipped_target_count"] == 0
    assert action_quality["near_joint_limit_count"] == 12
    # D-15 distinguishes commanded target violations from observed joint-state violations.
    assert action_quality["commanded_joint_limit_violation_count"] == 0
    assert action_quality["observed_joint_limit_violation_count"] == 12
    assert len(action_quality["commanded_joint_limit_violations_by_joint"]) == 12
    assert len(action_quality["observed_joint_limit_violations_by_joint"]) == 12
    assert all(count == 1 for count in action_quality["observed_joint_limit_violations_by_joint"].values())

    summary = collector.episode_summary().action_quality
    assert summary["position_servo_effort_proxy_mean"] == pytest.approx(
        action_quality["position_servo_effort_proxy"]
    )
    assert summary["position_target_saturation_proxy_total"] == 12


def test_reset_episode_preserves_baseline_snapshot():
    collector = LocomotionMetricsCollector()
    _record_step(collector, desired_command=(0.1, 0.0, 0.0))

    collector.capture_baseline()
    assert collector.baseline is not None

    collector.reset_episode()

    assert collector.baseline is not None
    assert collector.history_length == 0


def test_history_is_bounded_and_payload_is_finite():
    """D-02/T-03-03: bounded history emits compact finite nested payloads."""
    collector = LocomotionMetricsCollector(LocomotionMetricsConfig(history_size=3))

    for idx in range(5):
        _record_step(
            collector,
            desired_command=(float(idx), 0.0, 0.0),
            measured_base_velocity=(float(idx) - 0.1, 0.0, 0.0),
            base_xy_position=(float(idx), 0.0),
            contact_terrain_payload={"contact_count": idx},
        )

    assert collector.history_length == 3
    payload = collector.latest_info_payload()
    assert set(payload) == {"command_tracking", "stability", "action_quality", "contact_terrain"}
    assert "fall_rate" not in payload
    _assert_finite_payload(payload)


def test_rejects_malformed_metric_inputs_and_config():
    """T-03-01: malformed finite, shape, and config inputs are rejected."""
    with pytest.raises(ValueError, match="history_size"):
        LocomotionMetricsConfig(history_size=0)
    with pytest.raises(ValueError, match="max_abs_roll_rad"):
        LocomotionMetricsConfig(max_abs_roll_rad=float("nan"))
    with pytest.raises(ValueError, match="saturation_margin_fraction"):
        LocomotionMetricsConfig(saturation_margin_fraction=0.75)

    collector = LocomotionMetricsCollector()
    with pytest.raises(ValueError, match="desired_command must have shape"):
        _record_step(collector, desired_command=(0.0, 0.0))
    with pytest.raises(ValueError, match="action_target must contain only finite"):
        _record_step(collector, action_target=np.full(12, np.inf))
    with pytest.raises(ValueError, match="dt must be positive"):
        _record_step(collector, dt=0.0)


def test_phase3_metrics_tests_do_not_encode_deferred_scope_terms():
    """The out-of-scope guard forbids Phase 4 exports, controller families, ROS, and UI strings."""
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    for rel_path in _OUT_OF_SCOPE_TEST_FILES:
        text = (root / rel_path).read_text(encoding="utf-8")
        for term in _FORBIDDEN_PHASE3_SCOPE_TERMS:
            searchable = "\n".join(line for line in text.lower().splitlines() if "out-of-scope" not in line)
            assert term not in searchable, (rel_path, term)
