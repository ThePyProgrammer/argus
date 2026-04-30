"""Tests for LOC-ENV-04 action mode spaces and decoding."""

import numpy as np
import pytest

from src.locomotion.actions import (
    ACTION_MODE_JOINT_POSITION,
    ACTION_MODE_RESIDUAL_BASELINE,
    ACTION_MODE_VELOCITY,
    build_action_space,
    decode_action,
)
from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.gait_controller import TrotGaitController


DT = 0.02
PREVIOUS_COMMAND = np.array([0.2, 0.0, 0.0], dtype=np.float32)
VALID_ENV_ACTIONS = {
    ACTION_MODE_VELOCITY: np.array([0.1, 0.0, 0.0], dtype=np.float32),
    ACTION_MODE_JOINT_POSITION: np.tile(np.array([0.0, 0.9, -1.8], dtype=np.float32), 4),
    ACTION_MODE_RESIDUAL_BASELINE: np.zeros(12, dtype=np.float32),
}
REPRODUCIBILITY_INFO_KEYS = {
    "seed",
    "scenario_id",
    "sampled_parameters",
    "action_mode",
    "command_schedule",
    "disturbance_schedule",
}


@pytest.mark.parametrize(
    ("mode", "expected_shape"),
    [
        (ACTION_MODE_VELOCITY, (3,)),
        (ACTION_MODE_JOINT_POSITION, (12,)),
        (ACTION_MODE_RESIDUAL_BASELINE, (12,)),
    ],
)
def test_env_action_space_shape_follows_configured_action_mode(mode, expected_shape):
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode=mode))
    try:
        assert env.action_space.shape == expected_shape
    finally:
        env.close()


@pytest.mark.parametrize("mode", [ACTION_MODE_VELOCITY, ACTION_MODE_JOINT_POSITION, ACTION_MODE_RESIDUAL_BASELINE])
def test_env_step_uses_one_public_api_and_reports_reproducibility_info(mode):
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode=mode))
    try:
        _obs, reset_info = env.reset(seed=123)
        result = env.step(VALID_ENV_ACTIONS[mode])
    finally:
        env.close()

    assert len(result) == 5
    _obs, _reward, _terminated, _truncated, step_info = result
    assert REPRODUCIBILITY_INFO_KEYS <= reset_info.keys()
    assert REPRODUCIBILITY_INFO_KEYS <= step_info.keys()
    assert step_info["seed"] == 123
    assert step_info["action_mode"] == mode


def test_env_rejects_nan_action_before_step_count_advances():
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode=ACTION_MODE_VELOCITY))
    try:
        env.reset(seed=123)
        with pytest.raises(ValueError, match="finite"):
            env.step(np.array([np.nan, 0.0, 0.0], dtype=np.float32))
        assert env.step_count == 0
    finally:
        env.close()


def test_velocity_command_action_space_shape_and_bounds():
    """velocity_command exposes a three-value command action space."""
    space = build_action_space(ACTION_MODE_VELOCITY)

    assert space.shape == (3,)
    np.testing.assert_allclose(space.low, [-1.0, -1.0, -3.0])
    np.testing.assert_allclose(space.high, [1.0, 1.0, 3.0])


def test_joint_position_action_space_shape_and_bounds():
    """joint_position exposes twelve Go2 joint target values."""
    space = build_action_space(ACTION_MODE_JOINT_POSITION)

    assert space.shape == (12,)
    expected_low = np.array([-1.0472, -1.5708, -2.7227] * 4, dtype=np.float32)
    expected_high = np.array([1.0472, 4.5379, -0.83776] * 4, dtype=np.float32)
    np.testing.assert_allclose(space.low, expected_low)
    np.testing.assert_allclose(space.high, expected_high)


def test_residual_baseline_action_space_shape_and_bounds():
    """residual_baseline exposes twelve clipped residual values."""
    space = build_action_space(ACTION_MODE_RESIDUAL_BASELINE)

    assert space.shape == (12,)
    np.testing.assert_allclose(space.low, np.full(12, -0.25, dtype=np.float32))
    np.testing.assert_allclose(space.high, np.full(12, 0.25, dtype=np.float32))


def test_velocity_command_decode_uses_trot_gait_controller():
    """Velocity action decodes through TrotGaitController into finite joint targets."""
    gait = TrotGaitController()
    action = np.array([0.3, 0.1, 0.2], dtype=np.float32)

    decoded = decode_action(action, ACTION_MODE_VELOCITY, gait, DT, PREVIOUS_COMMAND)

    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))


def test_joint_position_decode_passes_through_caller_values():
    """Joint-position actions are validated and returned unchanged."""
    gait = TrotGaitController()
    action = np.array([0.0, 0.9, -1.8] * 4, dtype=np.float32)

    decoded = decode_action(action, ACTION_MODE_JOINT_POSITION, gait, DT, PREVIOUS_COMMAND)

    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))
    np.testing.assert_allclose(decoded, action)


def test_residual_baseline_decode_adds_clipped_residual_to_baseline():
    """Residual actions are clipped then added to the analytical baseline."""
    gait = TrotGaitController()
    residual = np.full(12, 0.1, dtype=np.float32)

    decoded = decode_action(
        residual,
        ACTION_MODE_RESIDUAL_BASELINE,
        gait,
        DT,
        PREVIOUS_COMMAND,
    )

    baseline = TrotGaitController().compute(
        float(PREVIOUS_COMMAND[0]),
        float(PREVIOUS_COMMAND[1]),
        float(PREVIOUS_COMMAND[2]),
        DT,
    )
    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))
    np.testing.assert_allclose(decoded, baseline + residual)


def test_residual_baseline_decode_clips_residual_before_adding_baseline():
    """Residual action values cannot exceed the residual action contract."""
    baseline_gait = TrotGaitController()
    baseline = baseline_gait.compute(
        float(PREVIOUS_COMMAND[0]),
        float(PREVIOUS_COMMAND[1]),
        float(PREVIOUS_COMMAND[2]),
        DT,
    )
    gait = TrotGaitController()
    residual = np.full(12, 1.0, dtype=np.float32)

    decoded = decode_action(
        residual,
        ACTION_MODE_RESIDUAL_BASELINE,
        gait,
        DT,
        PREVIOUS_COMMAND,
    )

    np.testing.assert_allclose(decoded, baseline + 0.25)


@pytest.mark.parametrize(
    ("mode", "action"),
    [
        (ACTION_MODE_VELOCITY, np.zeros(12, dtype=np.float32)),
        (ACTION_MODE_JOINT_POSITION, np.zeros(3, dtype=np.float32)),
        (ACTION_MODE_RESIDUAL_BASELINE, np.zeros(3, dtype=np.float32)),
    ],
)
def test_decode_rejects_wrong_action_shape(mode, action):
    """Every mode rejects malformed action shapes before controls are applied."""
    gait = TrotGaitController()

    with pytest.raises(ValueError, match="shape"):
        decode_action(action, mode, gait, DT, PREVIOUS_COMMAND)


@pytest.mark.parametrize("mode", [ACTION_MODE_VELOCITY, ACTION_MODE_JOINT_POSITION, ACTION_MODE_RESIDUAL_BASELINE])
def test_decode_rejects_nan_action_values(mode):
    """Every mode rejects np.nan action values before controls are applied."""
    gait = TrotGaitController()
    action = np.zeros(build_action_space(mode).shape, dtype=np.float32)
    action[0] = np.nan

    with pytest.raises(ValueError, match="finite"):
        decode_action(action, mode, gait, DT, PREVIOUS_COMMAND)


@pytest.mark.parametrize(
    ("mode", "action"),
    [
        (ACTION_MODE_VELOCITY, np.array([999.0, 0.0, 0.0], dtype=np.float32)),
        (ACTION_MODE_JOINT_POSITION, np.array([2.0, 0.9, -1.8] * 4, dtype=np.float32)),
    ],
)
def test_decode_rejects_out_of_bounds_action_values(mode, action):
    gait = TrotGaitController()

    with pytest.raises(ValueError, match="bounds"):
        decode_action(action, mode, gait, DT, PREVIOUS_COMMAND)


def test_unknown_action_mode_lists_available_modes():
    """Unknown action mode errors include available mode choices."""
    gait = TrotGaitController()

    with pytest.raises(ValueError, match="Available:"):
        decode_action(np.zeros(3, dtype=np.float32), "unknown_mode", gait, DT, PREVIOUS_COMMAND)
