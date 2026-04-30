"""Env wiring tests for locomotion metrics payloads and summaries."""

import math
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from src.locomotion.controllers import ControllerResult
from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.metrics import LocomotionMetricsConfig


class _FakeCtrl:
    def __init__(self, size: int = 12) -> None:
        self.values = np.zeros(size, dtype=np.float64)

    @property
    def shape(self) -> tuple[int, ...]:
        return self.values.shape

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value) -> None:
        if key == slice(None, None, None):
            self.values[:] = value
        else:
            self.values[key] = value

    def copy(self) -> np.ndarray:
        return self.values.copy()


class _FakeContact:
    def __init__(self, geom1: int, geom2: int) -> None:
        self.geom1 = geom1
        self.geom2 = geom2


class _FakeData:
    def __init__(self) -> None:
        self.qpos = np.zeros(19, dtype=np.float64)
        self.qpos[2] = 0.30
        self.qpos[3] = 1.0
        self.qvel = np.zeros(18, dtype=np.float64)
        self.ctrl = _FakeCtrl(12)
        self.xfrc_applied = np.zeros((1, 6), dtype=np.float64)
        self.geom_xpos = np.array(
            [
                [0.20, 0.10, 0.03],
                [0.20, -0.10, 0.03],
                [-0.20, 0.10, 0.03],
                [-0.20, -0.10, 0.03],
            ],
            dtype=np.float64,
        )
        self.ncon = 0
        self.contact: list[_FakeContact] = []
        self.time = 0.0


class _FakeModel:
    nq = 19
    nv = 18
    nu = 12
    nbody = 1
    opt = SimpleNamespace(timestep=0.002)


def _set_yaw(data: _FakeData, yaw: float) -> None:
    data.qpos[3:7] = [math.cos(yaw / 2.0), 0.0, 0.0, math.sin(yaw / 2.0)]


def _make_env(config: ArgusGo2EnvConfig | None = None) -> tuple[ArgusGo2Env, _FakeData]:
    env = ArgusGo2Env(config or ArgusGo2EnvConfig(sim_steps_per_frame=1))
    data = _FakeData()
    env._model = _FakeModel()
    env._data = data
    env._scenario_sample = None
    env._dt = 0.002 * env.config.sim_steps_per_frame
    return env, data


def _step_once(env: ArgusGo2Env, action: np.ndarray, mj_step):
    with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
        return env.step(action)


def test_step_info_contains_nested_locomotion_metrics():
    """D-01 D-02 D-04: compact nested per-step info exposes defined metric records."""
    env, data = _make_env()

    def mj_step(_model, fake_data):
        fake_data.qpos[0] += 0.01
        fake_data.time += 0.002

    try:
        _obs, _reward, _terminated, _truncated, info = _step_once(
            env,
            np.array([0.1, 0.0, 0.0], dtype=np.float32),
            mj_step,
        )
    finally:
        env.close()

    assert set(info["locomotion_metrics"]) == {
        "command_tracking",
        "stability",
        "action_quality",
        "contact_terrain",
    }
    assert {"vx_error", "fall_rate", "action_delta_norm", "duty_factor"}.isdisjoint(info)
    assert all(not isinstance(value, np.ndarray) for value in info["locomotion_metrics"].values())
    assert "qpos" not in str(info["locomotion_metrics"])
    assert "qvel" not in str(info["locomotion_metrics"])
    assert "tracking_error_norm" in info["locomotion_metrics"]["command_tracking"]
    assert "action_delta_norm" in info["locomotion_metrics"]["action_quality"]


def test_failure_threshold_sets_terminated_true():
    """LOC-METRICS-02: D-05 D-06 D-08 threshold overrides terminate immediately."""
    config = ArgusGo2EnvConfig(
        sim_steps_per_frame=1,
        metrics_config=LocomotionMetricsConfig(min_base_height_m=0.25, min_progress_m_per_s=0.001),
    )
    env, data = _make_env(config)

    def mj_step(_model, fake_data):
        fake_data.qpos[2] = 0.10
        fake_data.time += 0.002

    try:
        _obs, _reward, terminated, truncated, info = _step_once(env, np.zeros(3, dtype=np.float32), mj_step)
    finally:
        env.close()

    assert terminated is True
    assert truncated is False
    assert info["locomotion_metrics_summary"]["stability"]["success"] is False
    assert info["locomotion_metrics_summary"]["stability"]["fall_rate"] == pytest.approx(1.0)


def test_terminal_or_truncated_step_contains_episode_summary():
    """D-04 D-07: survival to truncation is successful episode summary semantics."""
    env, _data = _make_env(ArgusGo2EnvConfig(sim_steps_per_frame=1, max_episode_steps=1))

    def mj_step(_model, fake_data):
        fake_data.qpos[0] += 0.01
        fake_data.time += 0.002

    try:
        _obs, _reward, terminated, truncated, info = _step_once(env, np.zeros(3, dtype=np.float32), mj_step)
    finally:
        env.close()

    assert terminated is False
    assert truncated is True
    assert "locomotion_metrics_summary" in info
    assert set(info["locomotion_metrics_summary"]) >= {
        "command_tracking",
        "stability",
        "action_quality",
        "contact_terrain",
    }
    assert info["locomotion_metrics_summary"]["success"] is True
    assert info["locomotion_metrics_summary"]["failure_reason"] is None


def test_zero_command_standing_does_not_terminate_progress_stalled():
    config = ArgusGo2EnvConfig(
        sim_steps_per_frame=1,
        max_episode_steps=20,
        metrics_config=LocomotionMetricsConfig(
            progress_window_steps=3,
            min_progress_m_per_s=0.001,
            min_progress_command_speed_m_per_s=0.05,
        ),
    )
    env, data = _make_env(config)
    action = np.zeros(3, dtype=np.float32)

    def dispatch_controller(_controller, _observation, _command, _dt, data=None, ctrl_indices=None):
        return ControllerResult(action=np.zeros(12, dtype=np.float64), metadata={"source": "test"})

    def mj_step(_model, fake_data):
        fake_data.time += 0.002

    try:
        with patch("src.locomotion.env.dispatch_controller", side_effect=dispatch_controller):
            for _ in range(config.metrics_config.progress_window_steps + 3):
                _obs, _reward, terminated, truncated, info = _step_once(env, action, mj_step)
                assert terminated is False
                assert truncated is False
                assert info["locomotion_metrics"]["stability"]["failure_reason"] != "progress_stalled"
            np.testing.assert_allclose(data.qpos[0:2], [0.0, 0.0])
            assert data.qpos[2] == pytest.approx(0.30)
            assert env.last_locomotion_metrics_summary is None
    finally:
        env.close()


def test_reset_starts_fresh_episode_metrics_without_clearing_baseline():
    """D-03: reset starts fresh active buffer while preserving captured baseline."""
    env = ArgusGo2Env(ArgusGo2EnvConfig(sim_steps_per_frame=1))
    try:
        env._metrics.record_step(
            desired_command=[0.0, 0.0, 0.0],
            measured_base_velocity=[0.0, 0.0, 0.0],
            roll_rad=0.0,
            pitch_rad=0.0,
            base_height_m=0.30,
            base_xy_position=[0.0, 0.0],
            action_target=np.zeros(12),
            previous_action_target=np.zeros(12),
            previous_previous_action_target=np.zeros(12),
            joint_qpos=np.array([0.0, 0.9, -1.8] * 4),
            joint_qvel=np.zeros(12),
            dt=0.02,
        )
        env._metrics.capture_baseline()
        assert env._metrics.baseline is not None

        _obs, info = env.reset(seed=123)

        assert info["step_count"] == 0
        assert env._metrics.history_length == 0
        assert env._metrics.baseline is not None
    finally:
        env.close()


def test_metrics_record_validated_control_target_not_raw_velocity_action():
    env, data = _make_env(ArgusGo2EnvConfig(sim_steps_per_frame=1))
    expected_ctrl = np.linspace(-0.2, 0.2, 12, dtype=np.float64)
    action = np.array([0.25, -0.1, 0.35], dtype=np.float32)

    def dispatch_controller(_controller, _observation, _command, _dt, data=None, ctrl_indices=None):
        data.ctrl[:] = expected_ctrl
        return ControllerResult(action=expected_ctrl, metadata={"source": "test"})

    def mj_step(_model, fake_data):
        fake_data.time += 0.002

    try:
        with patch("src.locomotion.env.dispatch_controller", side_effect=dispatch_controller):
            _obs, _reward, _terminated, _truncated, info = _step_once(env, action, mj_step)
    finally:
        env.close()

    recorded_delta = info["locomotion_metrics"]["action_quality"]["action_delta_norm"]
    assert recorded_delta == pytest.approx(float(np.linalg.norm(expected_ctrl)))
    assert recorded_delta != pytest.approx(float(np.linalg.norm(action)))
    np.testing.assert_allclose(data.ctrl.copy(), expected_ctrl)


def test_measured_command_tracking_uses_world_pose_deltas_and_wrapped_yaw():
    """LOC-METRICS-01: command tracking uses world pose deltas and wrapped yaw."""
    env, data = _make_env(ArgusGo2EnvConfig(sim_steps_per_frame=1))
    data.qpos[0:2] = [1.0, -2.0]
    _set_yaw(data, math.pi - 0.05)
    data.time = 4.0
    data.qvel[:3] = [99.0, -99.0, 42.0]

    def mj_step(_model, fake_data):
        fake_data.qpos[0:2] = [1.04, -1.98]
        _set_yaw(fake_data, -math.pi + 0.05)
        fake_data.time = 4.2
        fake_data.qvel[:3] = [99.0, -99.0, 42.0]

    try:
        _obs, _reward, _terminated, _truncated, info = _step_once(env, np.zeros(3, dtype=np.float32), mj_step)
    finally:
        env.close()

    measured = info["locomotion_metrics"]["command_tracking"]["measured"]
    assert measured["vx"] == pytest.approx(0.2)
    assert measured["vy"] == pytest.approx(0.1)
    assert measured["yaw_rate"] == pytest.approx(0.5)
    assert measured["vx"] != pytest.approx(99.0)
    assert measured["vy"] != pytest.approx(-99.0)
    assert measured["yaw_rate"] != pytest.approx(42.0)


def test_last_locomotion_metrics_summary_survives_reset_until_next_completion():
    """D-03 D-04: last_locomotion_metrics_summary persists until next completed episode."""
    env, _data = _make_env(ArgusGo2EnvConfig(sim_steps_per_frame=1, max_episode_steps=1))

    def mj_step_first(_model, fake_data):
        fake_data.qpos[0] = 0.01
        fake_data.time += 0.002

    try:
        _obs, _reward, _terminated, truncated, first_info = _step_once(env, np.zeros(3, dtype=np.float32), mj_step_first)
        assert truncated is True
        first_summary = env.last_locomotion_metrics_summary
        assert first_summary == first_info["locomotion_metrics_summary"]

        _obs, reset_info = env.reset(seed=123)
        assert reset_info["step_count"] == 0
        assert env._metrics.history_length == 0
        assert env.last_locomotion_metrics_summary == first_summary

        env.config.max_episode_steps = 1

        def mj_step_second(_model, fake_data):
            fake_data.qpos[0] = 0.25
            fake_data.time += 0.002

        _obs, _reward, _terminated, _truncated, second_info = _step_once(
            env,
            np.zeros(3, dtype=np.float32),
            mj_step_second,
        )
        assert env.last_locomotion_metrics_summary == second_info["locomotion_metrics_summary"]
        assert env.last_locomotion_metrics_summary != first_summary
    finally:
        env.close()
