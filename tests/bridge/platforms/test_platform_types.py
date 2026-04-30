import numpy as np

from src.bridge.platforms.types import (
    CommandTracking,
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
)


def test_robot_command_wire_shape_is_json_safe():
    cmd = RobotCommand.velocity([0.3, -0.1], yaw_rate=0.2)

    assert cmd.to_wire() == {
        "mode": "velocity",
        "linear": [0.3, -0.1],
        "yaw_rate": 0.2,
        "waypoint": None,
    }


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


def test_platform_metadata_wire_contains_footprint_and_command_modes():
    metadata = RobotPlatformMetadata(
        name="agibot_x2",
        display_name="AGIBOT X2 Ultra",
        model_dir="models/agibot_x2",
        model_xml="x2_ultra.xml",
        actuator_count=31,
        command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
        footprint_radius=0.33,
        dimensions=(0.46, 0.21, 1.31),
        max_linear_speed=0.8,
        max_yaw_rate=1.0,
        marker_asset=None,
        spawn_height=0.85,
    )

    assert metadata.to_wire() == {
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


def test_robot_command_rejects_wrong_linear_shape():
    try:
        RobotCommand.velocity(np.array([1.0, 2.0, 3.0]), yaw_rate=0.0)
    except ValueError as exc:
        assert "linear command must have shape (2,)" in str(exc)
    else:
        raise AssertionError("RobotCommand.velocity accepted a 3-element linear command")
