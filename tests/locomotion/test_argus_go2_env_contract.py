"""Contract tests for the Gymnasium-style Argus Go2 locomotion environment."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.scenarios import list_scenarios


def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
    try:
        import mujoco  # noqa: F401
    except ImportError:
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")


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


class _FakeData:
    def __init__(self) -> None:
        self.qpos = np.zeros(19, dtype=np.float64)
        self.qvel = np.ones(18, dtype=np.float64)
        self.ctrl = _FakeCtrl(12)
        self.xfrc_applied = np.zeros((1, 6), dtype=np.float64)
        self.time = 0.0


class _FakeModel:
    nq = 19
    nv = 18
    nu = 12
    nbody = 1
    opt = SimpleNamespace(timestep=0.002)


def test_import_argus_go2_env_contract_types():
    """ArgusGo2Env and ArgusGo2EnvConfig can be imported."""
    assert ArgusGo2Env is not None
    assert ArgusGo2EnvConfig is not None


def test_default_config_uses_flat_ground_velocity_command():
    """Default config selects the LOC-ENV-01 baseline scenario and action mode."""
    config = ArgusGo2EnvConfig()

    assert config.scenario_id == "flat_ground"
    assert config.action_mode == "velocity_command"


def test_default_env_exposes_observation_and_action_spaces():
    """Default environment exposes Gymnasium spaces without loading MuJoCo."""
    env = ArgusGo2Env()
    try:
        assert env.observation_space is not None
        assert env.action_space is not None
        assert env.action_space.shape == (3,)
    finally:
        env.close()


def test_reset_returns_observation_and_info():
    """reset(seed=...) returns a Gymnasium two-tuple and reproducibility info."""
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    try:
        obs, info = env.reset(seed=123)
    finally:
        env.close()

    assert isinstance(obs, dict)
    assert info["seed"] == 123
    assert info["scenario_id"] == "flat_ground"
    assert info["action_mode"] == "velocity_command"
    assert "sampled_parameters" in info
    assert "command_schedule" in info
    assert "disturbance_schedule" in info
    assert info["step_count"] == 0
    assert "sim_time" in info


def test_step_returns_gymnasium_five_tuple():
    """step(action) returns observation, reward, terminated, truncated, info."""
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    try:
        env.reset(seed=123)
        result = env.step(np.array([0.0, 0.0, 0.0], dtype=np.float32))
    finally:
        env.close()

    assert len(result) == 5
    obs, reward, terminated, truncated, info = result
    assert isinstance(obs, dict)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert info["seed"] == 123
    assert info["scenario_id"] == "flat_ground"
    assert info["action_mode"] == "velocity_command"
    assert info["step_count"] == 1


def test_same_seed_reset_reproduces_first_nonzero_action():
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    action = np.array([0.2, 0.0, 0.0], dtype=np.float32)
    try:
        env.reset(seed=123)
        first_obs, *_ = env.step(action)
        env.reset(seed=123)
        second_obs, *_ = env.step(action)
    finally:
        env.close()

    np.testing.assert_allclose(first_obs["previous_action"], second_obs["previous_action"])


@pytest.mark.integration
@pytest.mark.parametrize("scenario_id", list_scenarios())
def test_reset_can_initialize_and_close_mujoco_for_each_named_scenario(scenario_id):
    _skip_if_mujoco_python_unsupported()
    if not (Path("models/unitree_go2") / "go2.xml").exists():
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")

    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id=scenario_id))
    try:
        obs, info = env.reset(seed=123)
        assert isinstance(obs, dict)
        assert info["scenario_id"] == scenario_id
        assert env._model is not None
        assert env._data is not None
    finally:
        env.close()

    assert env._model is None
    assert env._data is None


@pytest.mark.integration
def test_step_advances_mujoco_sim_time_when_integration_available():
    _skip_if_mujoco_python_unsupported()
    if not (Path("models/unitree_go2") / "go2.xml").exists():
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")

    env = ArgusGo2Env(ArgusGo2EnvConfig(sim_steps_per_frame=2))
    try:
        _obs, reset_info = env.reset(seed=123)
        _obs, _reward, _terminated, _truncated, info = env.step(
            np.array([0.0, 0.0, 0.0], dtype=np.float32),
        )
        assert info["sim_time"] > reset_info["sim_time"]
    finally:
        env.close()


def test_step_decodes_action_writes_ctrl_and_calls_mj_step_configured_count():
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode="joint_position", sim_steps_per_frame=3))
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    env._scenario_sample = None
    expected_ctrl = np.linspace(-0.1, 0.1, 12, dtype=np.float64)
    mj_step = MagicMock(side_effect=lambda _model, data: setattr(data, "time", data.time + 0.002))

    with patch("src.locomotion.env.decode_action", return_value=expected_ctrl) as decode_action_mock:
        with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
            obs, _reward, _terminated, _truncated, info = env.step(np.array([0.0] * 12, dtype=np.float32))

    decode_action_mock.assert_called_once()
    np.testing.assert_allclose(fake_data.ctrl.copy(), expected_ctrl)
    assert mj_step.call_count == env.config.sim_steps_per_frame
    assert info["sim_time"] == pytest.approx(fake_data.time)
    np.testing.assert_allclose(obs["qpos"], fake_data.qpos.astype(np.float32))


def test_push_disturbance_applies_xfrc_applied_deterministically_then_clears():
    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id="push_disturbance", sim_steps_per_frame=1))
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    env.reset(seed=123)
    env._model = _FakeModel()
    env._data = fake_data
    env._dt = 0.002
    schedule = env._scenario_sample.disturbance_schedule
    active_time = schedule[0]["time"]
    force = np.array([schedule[0]["force_x"], schedule[0]["force_y"], schedule[0]["force_z"]])
    env._step_count = math.ceil(active_time / env._dt)

    with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=lambda _model, data: None)}):
        _obs, _reward, _terminated, _truncated, active_info = env.step(
            np.array([0.0, 0.0, 0.0], dtype=np.float32),
        )
        active_force = fake_data.xfrc_applied[0, :3].copy()
        env._step_count = int((active_time + schedule[0]["duration"] + env._dt) / env._dt)
        _obs, _reward, _terminated, _truncated, clear_info = env.step(
            np.array([0.0, 0.0, 0.0], dtype=np.float32),
        )

    np.testing.assert_allclose(active_force, force)
    assert active_info["active_push"] is not None
    np.testing.assert_allclose(fake_data.xfrc_applied[0], np.zeros(6))
    assert clear_info["active_push"] is None


def test_reset_writes_spawn_position_yaw_quat_qpos_3_7_and_standing_pose():
    env = ArgusGo2Env(ArgusGo2EnvConfig())
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    _obs, info = env.reset(seed=123)
    yaw = info["spawn_pose"][3]
    expected_quat = np.array([math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2)])

    np.testing.assert_allclose(fake_data.qpos[:3], info["spawn_pose"][:3])
    np.testing.assert_allclose(fake_data.qpos[3:7], expected_quat)
    np.testing.assert_allclose(fake_data.qpos[7:19], [0.0, 0.9, -1.8] * 4)
    np.testing.assert_allclose(fake_data.qvel, np.zeros_like(fake_data.qvel))
    np.testing.assert_allclose(fake_data.ctrl.copy(), np.zeros(12))
