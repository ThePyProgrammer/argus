from dataclasses import dataclass

import numpy as np
import pytest

from src.bridge.platforms import create_platform, list_platforms, register_platform
from src.bridge.platforms.go2 import GO2_ACTUATOR_NAMES, Go2Platform
from src.bridge.platforms.types import FallReason, RobotCommand, RobotRuntimeState
from src.bridge.sensor_types import STANDING_QPOS


@pytest.fixture(autouse=True)
def registered_go2_platform():
    if "go2" not in list_platforms():
        register_platform("go2", Go2Platform)


@dataclass
class _FakeModel:
    jnt_qposadr: np.ndarray
    jnt_dofadr: np.ndarray


@dataclass
class _FakeData:
    qpos: np.ndarray
    qvel: np.ndarray


def test_go2_registered_by_package_import():
    assert "go2" in list_platforms()
    assert create_platform("go2").metadata.name == "go2"


def test_go2_metadata_preserves_current_defaults():
    platform = Go2Platform()

    assert platform.metadata.model_dir == "models/unitree_go2"
    assert platform.metadata.model_xml == "go2.xml"
    assert platform.metadata.actuator_count == 12
    assert platform.metadata.spawn_height == 0.3
    assert platform.metadata.marker_asset == "/go2.glb"
    assert platform.actuator_names() == GO2_ACTUATOR_NAMES


def test_go2_initial_joint_qpos_returns_standing_pose_copy():
    platform = Go2Platform()

    qpos = platform.initial_joint_qpos()
    qpos[0] = 123.0

    np.testing.assert_allclose(platform.initial_joint_qpos(), STANDING_QPOS)
    assert not np.shares_memory(platform.initial_joint_qpos(), STANDING_QPOS)


def test_go2_camera_spec_preserves_current_fields():
    platform = Go2Platform()

    assert platform.camera_spec("robot_a") == {
        "name": "robot_a_cam",
        "pos": "0.4 0 0.05",
        "xyaxes": "0 -1 0 0 0 1",
        "fovy": "70",
    }


def test_go2_stand_stop_and_recover_return_standing_pose():
    platform = Go2Platform()
    controller = platform.make_controller("robot_a")
    state = platform.extract_state(None, None, 0, 0.0)

    for command in (RobotCommand.stand(), RobotCommand.stop(), RobotCommand.recover()):
        np.testing.assert_allclose(controller.compute(command, state, dt=0.02), STANDING_QPOS)


def test_go2_velocity_controller_returns_twelve_targets():
    platform = Go2Platform()
    controller = platform.make_controller("robot_a")
    state = platform.extract_state(
        model=None,
        data=None,
        qpos_start=0,
        sim_time=0.0,
    )

    ctrl = controller.compute(RobotCommand.velocity([0.1, 0.0], 0.0), state, dt=0.02)

    assert ctrl.shape == (12,)
    assert np.isfinite(ctrl).all()
    assert controller.health().policy_loaded is True


def test_go2_runtime_status_maps_moving_command_to_walking():
    platform = Go2Platform()
    controller = platform.make_controller("robot_a")
    state = platform.extract_state(None, None, 0, 0.0)
    command = RobotCommand.velocity([0.2, 0.0], 0.1)

    status = platform.runtime_status("robot_a", state, command, controller.health())

    assert status.state == RobotRuntimeState.WALKING
    assert status.disabled is False
    assert status.to_wire()["last_command"]["mode"] == "velocity"


def test_go2_extract_state_maps_data_fields():
    platform = Go2Platform()
    qpos = np.zeros(19, dtype=np.float64)
    qpos[0:3] = [1.0, 2.0, 0.15]
    qpos[3:7] = [1.0, 0.0, 0.0, 0.0]
    qpos[7:19] = np.arange(12, dtype=np.float64) + 10.0
    qvel = np.zeros(18, dtype=np.float64)
    qvel[0:3] = [0.1, 0.2, 0.3]
    qvel[6:18] = np.arange(12, dtype=np.float64) + 20.0

    state = platform.extract_state(None, _FakeData(qpos=qpos, qvel=qvel), qpos_start=0, sim_time=1.25)

    np.testing.assert_allclose(state.base_pose[:3, 3], [1.0, 2.0, 0.15])
    np.testing.assert_allclose(state.orientation_quat, [1.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(state.joint_positions, np.arange(12, dtype=np.float64) + 10.0)
    np.testing.assert_allclose(state.base_velocity, [0.1, 0.2, 0.3])
    np.testing.assert_allclose(state.joint_velocities, np.arange(12, dtype=np.float64) + 20.0)
    assert state.fallen is True
    assert state.fall_reason == FallReason.BASE_HEIGHT
    assert state.sim_time == 1.25


def test_go2_extract_state_uses_model_dof_address_for_nonzero_qpos_start():
    platform = Go2Platform()
    qpos = np.zeros(38, dtype=np.float64)
    qpos[19:22] = [4.0, 5.0, 0.3]
    qpos[22:26] = [1.0, 0.0, 0.0, 0.0]
    qpos[26:38] = np.arange(12, dtype=np.float64) + 30.0
    qvel = np.zeros(36, dtype=np.float64)
    qvel[18:21] = [0.4, 0.5, 0.6]
    qvel[24:36] = np.arange(12, dtype=np.float64) + 40.0
    model = _FakeModel(
        jnt_qposadr=np.array([0, 19], dtype=np.int32),
        jnt_dofadr=np.array([0, 18], dtype=np.int32),
    )

    state = platform.extract_state(model, _FakeData(qpos=qpos, qvel=qvel), qpos_start=19, sim_time=2.5)

    np.testing.assert_allclose(state.base_pose[:3, 3], [4.0, 5.0, 0.3])
    np.testing.assert_allclose(state.base_velocity, [0.4, 0.5, 0.6])
    np.testing.assert_allclose(state.joint_positions, np.arange(12, dtype=np.float64) + 30.0)
    np.testing.assert_allclose(state.joint_velocities, np.arange(12, dtype=np.float64) + 40.0)
    assert state.fallen is False
    assert state.fall_reason == FallReason.NONE
