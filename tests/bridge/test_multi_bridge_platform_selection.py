import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import RobotCommand


def test_bridge_exposes_platform_metadata_without_starting():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    metadata = bridge.platform_metadata

    assert metadata.name == "go2"
    assert metadata.actuator_count == 12


def test_bridge_buffers_generic_robot_command():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_command("robot_a", RobotCommand.velocity([0.4, 0.0], 0.2))

    assert bridge.get_runtime_status("robot_a").last_command.to_wire() == {
        "mode": "velocity",
        "linear": [0.4, 0.0],
        "yaw_rate": 0.2,
        "waypoint": None,
    }


def test_set_velocity_preserves_existing_api():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_velocity("robot_a", np.array([0.1, 0.0]), 0.0)

    assert bridge.get_runtime_status("robot_a").last_command.to_wire()["linear"] == [0.1, 0.0]
