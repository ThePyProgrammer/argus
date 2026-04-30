import os
from pathlib import Path

import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.types import RobotCommand


X2_MODEL_DIR = Path("models/agibot_x2")
X2_XML = X2_MODEL_DIR / "x2_ultra.xml"
ENABLE_SMOKE = os.environ.get("ARGUS_X2_ENABLE_ASSET_SMOKE") == "1"

pytestmark = pytest.mark.x2_asset


def _require_x2_assets() -> None:
    if not ENABLE_SMOKE:
        pytest.skip("set ARGUS_X2_ENABLE_ASSET_SMOKE=1 to run X2 asset smoke tests")
    if not X2_XML.exists():
        pytest.skip(f"AGIBOT X2 MuJoCo asset missing: {X2_XML}")


def test_x2_asset_actuator_map_matches_controller_io():
    _require_x2_assets()
    platform = AgibotX2Platform(model_dir=str(X2_MODEL_DIR))

    actuator_names = platform.actuator_names()
    assert len(actuator_names) == 31

    pose = np.eye(4, dtype=np.float64)
    pose[:3, 3] = [0.0, 0.0, 0.85]
    state = platform._state_from_arrays(
        base_pose=pose,
        base_velocity=np.zeros(3, dtype=np.float64),
        joint_positions=platform.initial_joint_qpos(),
        joint_velocities=np.zeros(len(actuator_names), dtype=np.float64),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
        sim_time=0.0,
    )
    controller = platform.make_controller("robot_a")

    action = controller.compute(RobotCommand.stand(), state, dt=0.02)

    assert action.shape == (31,)
    assert np.isfinite(action).all()


def test_two_x2_robots_start_step_and_keep_independent_status():
    _require_x2_assets()
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": str(X2_MODEL_DIR)},
        robot_ids=("robot_a", "robot_b"),
        spawn_positions={
            "robot_a": (0.0, 0.0, 0.85),
            "robot_b": (2.0, 0.0, 0.85),
        },
        sim_steps_per_frame=1,
        boot_phase_steps=1,
    )
    bridge = MultiRobotBridge(config)
    try:
        frames = bridge.start()
        assert set(frames) == {"robot_a", "robot_b"}

        bridge.set_velocity("robot_a", np.array([0.1, 0.0], dtype=np.float64), 0.0)
        frames = bridge.step()
        assert set(frames) == {"robot_a", "robot_b"}

        robot_a_status = bridge.get_runtime_status("robot_a").to_wire()
        robot_b_status = bridge.get_runtime_status("robot_b").to_wire()
        allowed_states = {"standing", "walking", "fallen", "disabled"}
        assert robot_a_status["state"] in allowed_states
        assert robot_b_status["state"] in allowed_states
        assert robot_a_status["last_command"]["mode"] == "velocity"
        assert robot_a_status["last_command"]["linear"] == [0.1, 0.0]
        assert robot_b_status["last_command"]["mode"] == "stand"
    finally:
        bridge.stop()


def test_five_x2_robots_build_unique_command_channels():
    _require_x2_assets()
    robot_ids = ("robot_a", "robot_b", "robot_c", "robot_d", "robot_e")
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": str(X2_MODEL_DIR)},
        robot_ids=robot_ids,
        spawn_positions={
            robot_id: (1.5 * index, 0.0, 0.85)
            for index, robot_id in enumerate(robot_ids)
        },
        sim_steps_per_frame=1,
        boot_phase_steps=1,
    )
    bridge = MultiRobotBridge(config)

    commands = {
        "robot_a": ([0.1, 0.0], 0.1),
        "robot_b": ([0.2, -0.1], -0.2),
        "robot_c": ([-0.1, 0.3], 0.3),
        "robot_d": ([0.0, -0.2], -0.4),
    }

    assert bridge.robot_ids == robot_ids
    for robot_id, (linear, yaw_rate) in commands.items():
        bridge.set_velocity(robot_id, np.array(linear, dtype=np.float64), yaw_rate)

    for robot_id, (linear, yaw_rate) in commands.items():
        command_wire = bridge.get_runtime_status(robot_id).last_command.to_wire()
        assert command_wire["mode"] == "velocity"
        assert command_wire["linear"] == linear
        assert command_wire["yaw_rate"] == yaw_rate

    robot_e_command = bridge.get_runtime_status("robot_e").last_command.to_wire()
    assert robot_e_command["mode"] == "stand"
