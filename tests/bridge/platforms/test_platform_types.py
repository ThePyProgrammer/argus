import json

import numpy as np
import pytest

from src.bridge.platforms.types import (
    CommandTracking,
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)


def _metadata(**overrides):
    values = {
        "name": "agibot_x2",
        "display_name": "AGIBOT X2 Ultra",
        "model_dir": "models/agibot_x2",
        "model_xml": "x2_ultra.xml",
        "actuator_count": 31,
        "command_modes": ("velocity", "stand", "stop", "recover", "waypoint"),
        "footprint_radius": 0.33,
        "dimensions": (0.46, 0.21, 1.31),
        "max_linear_speed": 0.8,
        "max_yaw_rate": 1.0,
        "marker_asset": None,
        "spawn_height": 0.85,
    }
    values.update(overrides)
    return RobotPlatformMetadata(**values)


def test_robot_command_wire_shape_is_json_safe():
    cmd = RobotCommand.velocity([0.3, -0.1], yaw_rate=0.2)

    payload = cmd.to_wire()

    assert payload == {
        "mode": "velocity",
        "linear": [0.3, -0.1],
        "yaw_rate": 0.2,
        "waypoint": None,
    }
    json.dumps(payload)


def test_robot_command_defensively_copies_and_freezes_linear_array():
    source = np.array([0.3, -0.1])
    cmd = RobotCommand.velocity(source, yaw_rate=0.2)

    source[0] = 9.0

    assert cmd.to_wire()["linear"] == [0.3, -0.1]
    with pytest.raises(ValueError):
        cmd.linear[0] = 1.0


def test_robot_command_rejects_wrong_linear_shape():
    with pytest.raises(ValueError, match="linear command must have shape"):
        RobotCommand.velocity(np.array([1.0, 2.0, 3.0]), yaw_rate=0.0)


def test_robot_waypoint_command_serializes_2d_and_3d_targets():
    cmd_2d = RobotCommand.waypoint_command([1.0, 2.0])
    cmd_3d = RobotCommand.waypoint_command([1.0, 2.0, 3.0])

    payload_2d = cmd_2d.to_wire()
    payload_3d = cmd_3d.to_wire()

    assert payload_2d["mode"] == "waypoint"
    assert payload_2d["linear"] == [0.0, 0.0]
    assert payload_2d["waypoint"] == [1.0, 2.0, 0.0]
    assert payload_3d["waypoint"] == [1.0, 2.0, 3.0]
    json.dumps(payload_2d)
    json.dumps(payload_3d)


def test_robot_waypoint_command_rejects_invalid_shape():
    with pytest.raises(ValueError, match="waypoint command must have shape"):
        RobotCommand.waypoint_command([1.0, 2.0, 3.0, 4.0])


def test_runtime_status_wire_contains_failure_and_controller_health():
    status = RobotRuntimeStatus(
        state=RobotRuntimeState.FALLEN,
        fall_reason=FallReason.ROLL_PITCH_THRESHOLD,
        last_command=RobotCommand.stop(),
        command_tracking=CommandTracking(linear_error=0.2, yaw_error=0.1),
        controller_health=ControllerHealth(
            policy_loaded=True,
            action_shape_valid=True,
            nan_guard_ok=False,
            actuator_clamp_count=3,
            message="invalid policy output",
        ),
        collision_count=1,
        near_miss_count=2,
    )

    payload = status.to_wire()

    assert payload["state"] == "fallen"
    assert payload["fall_reason"] == "roll_pitch_threshold"
    assert payload["last_command"]["mode"] == "stop"
    assert payload["command_tracking"]["linear_error"] == 0.2
    assert payload["controller_health"]["nan_guard_ok"] is False
    assert payload["collision_count"] == 1
    assert payload["near_miss_count"] == 2
    assert payload["disabled"] is True
    json.dumps(payload)


def test_platform_metadata_wire_contains_footprint_and_command_modes():
    metadata = _metadata()

    payload = metadata.to_wire()

    assert payload == {
        "name": "agibot_x2",
        "display_name": "AGIBOT X2 Ultra",
        "model_dir": "models/agibot_x2",
        "model_xml": "x2_ultra.xml",
        "actuator_count": 31,
        "command_modes": ["velocity", "stand", "stop", "recover", "waypoint"],
        "footprint_radius": 0.33,
        "dimensions": [0.46, 0.21, 1.31],
        "max_linear_speed": 0.8,
        "max_yaw_rate": 1.0,
        "marker_asset": None,
        "spawn_height": 0.85,
    }
    json.dumps(payload)


def test_platform_metadata_rejects_invalid_dimensions():
    with pytest.raises(ValueError, match="dimensions must contain three floats"):
        _metadata(dimensions=(0.46, 0.21))


def test_platform_metadata_rejects_invalid_command_mode():
    with pytest.raises(ValueError, match="command mode must be one of"):
        _metadata(command_modes=("velocity", "fly"))


def test_robot_state_validates_copies_and_freezes_arrays():
    base_pose = np.eye(4)
    state = RobotState(
        base_pose=base_pose,
        base_velocity=[0.1, 0.2, 0.3],
        joint_positions=np.array([1.0, 2.0]),
        joint_velocities=np.array([0.1, 0.2]),
        orientation_quat=[1.0, 0.0, 0.0, 0.0],
        contacts=["left_foot", "right_foot"],
        sim_time=1,
    )

    base_pose[0, 0] = 9.0

    assert state.base_pose[0, 0] == 1.0
    assert state.base_pose.dtype == np.float64
    assert state.base_velocity.shape == (3,)
    assert state.joint_positions.shape == (2,)
    assert state.joint_velocities.shape == (2,)
    assert state.orientation_quat.shape == (4,)
    assert state.contacts == ("left_foot", "right_foot")
    assert state.sim_time == 1.0
    with pytest.raises(ValueError):
        state.base_pose[0, 0] = 2.0
    with pytest.raises(ValueError, match="joint_positions and joint_velocities must have equal length"):
        RobotState(
            base_pose=np.eye(4),
            base_velocity=[0.0, 0.0, 0.0],
            joint_positions=[1.0, 2.0],
            joint_velocities=[0.1],
            orientation_quat=[1.0, 0.0, 0.0, 0.0],
            contacts=[],
            sim_time=0.0,
        )
