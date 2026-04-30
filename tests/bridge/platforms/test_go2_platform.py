import numpy as np
import pytest

from src.bridge.platforms import create_platform, list_platforms, register_platform
from src.bridge.platforms.go2 import GO2_ACTUATOR_NAMES, Go2Platform
from src.bridge.platforms.types import RobotCommand, RobotRuntimeState


@pytest.fixture(autouse=True)
def registered_go2_platform():
    if "go2" not in list_platforms():
        register_platform("go2", Go2Platform)


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
