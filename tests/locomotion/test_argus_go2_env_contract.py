"""Contract tests for the Gymnasium-style Argus Go2 locomotion environment."""

import sys

import numpy as np
import pytest

from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig


def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("Project requires Python >=3.10,<3.13 for MuJoCo integration")


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
