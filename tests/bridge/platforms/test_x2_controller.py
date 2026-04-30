import numpy as np
import pytest

from src.bridge.platforms.types import RobotCommand, RobotState
from src.locomotion.x2_controller import X2PolicyController


def _state(actuator_count: int) -> RobotState:
    pose = np.eye(4)
    pose[:3, 3] = [0.0, 0.0, 0.85]
    return RobotState(
        base_pose=pose,
        base_velocity=np.array([0.1, 0.0, 0.0]),
        joint_positions=np.zeros(actuator_count),
        joint_velocities=np.zeros(actuator_count),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        contacts=("left_foot", "right_foot"),
        sim_time=0.0,
    )


def test_stand_command_returns_default_pose_without_policy():
    controller = X2PolicyController(
        actuator_count=4,
        default_qpos=np.array([0.1, 0.2, 0.3, 0.4]),
    )

    action = controller.compute(RobotCommand.stand(), _state(4), dt=0.02)

    np.testing.assert_allclose(action, [0.1, 0.2, 0.3, 0.4])
    assert controller.health().policy_loaded is False
    assert controller.health().action_shape_valid is True


def test_policy_output_shape_and_clamp_count(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.ones((obs_dim, 4), dtype=np.float64),
        bias=np.array([0.0, 0.0, 0.0, 3.0], dtype=np.float64),
        lower=np.array([-1.0, -1.0, -1.0, -1.0], dtype=np.float64),
        upper=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64),
        default_qpos=np.zeros(4, dtype=np.float64),
    )
    controller = X2PolicyController(actuator_count=4, policy_path=policy_path)

    action = controller.compute(RobotCommand.velocity([0.2, 0.1], 0.3), _state(4), dt=0.02)

    assert action.shape == (4,)
    assert np.isfinite(action).all()
    assert action[-1] == 1.0
    assert controller.health().policy_loaded is True
    assert controller.health().actuator_clamp_count == 1


def test_invalid_policy_output_uses_safe_default(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.full((obs_dim, 4), np.nan, dtype=np.float64),
        bias=np.zeros(4, dtype=np.float64),
        lower=np.full(4, -1.0, dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64),
    )
    controller = X2PolicyController(actuator_count=4, policy_path=policy_path)

    action = controller.compute(RobotCommand.velocity([0.2, 0.0], 0.0), _state(4), dt=0.02)

    np.testing.assert_allclose(action, [0.4, 0.3, 0.2, 0.1])
    assert controller.health().nan_guard_ok is False
    assert controller.health().message == "controller_invalid_output"


def test_policy_rejects_non_finite_lower_bounds(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.ones((obs_dim, 4), dtype=np.float64),
        bias=np.zeros(4, dtype=np.float64),
        lower=np.array([np.nan, -1.0, -1.0, -1.0], dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.zeros(4, dtype=np.float64),
    )

    with pytest.raises(ValueError, match="lower must contain only finite values"):
        X2PolicyController(actuator_count=4, policy_path=policy_path)


def test_policy_rejects_lower_bounds_greater_than_upper_bounds(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.ones((obs_dim, 4), dtype=np.float64),
        bias=np.zeros(4, dtype=np.float64),
        lower=np.array([-1.0, 2.0, -1.0, -1.0], dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.zeros(4, dtype=np.float64),
    )

    with pytest.raises(ValueError, match="lower bounds must be less than or equal to upper bounds"):
        X2PolicyController(actuator_count=4, policy_path=policy_path)


def test_policy_rejects_non_finite_default_qpos(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.ones((obs_dim, 4), dtype=np.float64),
        bias=np.zeros(4, dtype=np.float64),
        lower=np.full(4, -1.0, dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.array([0.0, np.inf, 0.0, 0.0], dtype=np.float64),
    )

    with pytest.raises(ValueError, match="default_qpos must contain only finite values"):
        X2PolicyController(actuator_count=4, policy_path=policy_path)


def test_non_finite_clipped_action_uses_safe_default(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.zeros((obs_dim, 4), dtype=np.float64),
        bias=np.array([0.5, 0.0, 0.0, 0.0], dtype=np.float64),
        lower=np.full(4, -1.0, dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64),
    )
    controller = X2PolicyController(actuator_count=4, policy_path=policy_path)
    controller.lower[0] = np.nan

    action = controller.compute(RobotCommand.velocity([0.2, 0.0], 0.0), _state(4), dt=0.02)

    np.testing.assert_allclose(action, [0.4, 0.3, 0.2, 0.1])
    assert controller.health().policy_loaded is True
    assert controller.health().action_shape_valid is True
    assert controller.health().nan_guard_ok is False
    assert controller.health().message == "controller_invalid_output"
