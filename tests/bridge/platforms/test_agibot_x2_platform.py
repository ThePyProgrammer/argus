from pathlib import Path

import numpy as np

from src.bridge.platforms import create_platform, list_platforms
from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.types import FallReason, RobotCommand, RobotRuntimeState


X2_FIXTURE_XML = """
<mujoco model="x2_fixture">
  <worldbody>
    <body name="pelvis" pos="0 0 0.85">
      <freejoint/>
      <body name="torso"/>
    </body>
  </worldbody>
  <actuator>
    <position name="left_hip_pitch" joint="left_hip_pitch"/>
    <position name="right_hip_pitch" joint="right_hip_pitch"/>
    <position name="left_knee" joint="left_knee"/>
  </actuator>
  <keyframe>
    <key name="home" qpos="0 0 0.85 1 0 0 0 0.1 0.2 0.3"/>
  </keyframe>
</mujoco>
"""


def _write_fixture_model(tmp_path: Path) -> Path:
    model_dir = tmp_path / "agibot_x2"
    model_dir.mkdir()
    (model_dir / "x2_ultra.xml").write_text(X2_FIXTURE_XML)
    return model_dir


def test_x2_registered_by_package_import():
    assert "agibot_x2" in list_platforms()
    assert create_platform("agibot_x2").metadata.name == "agibot_x2"


def test_x2_metadata_matches_design_contract():
    platform = AgibotX2Platform()

    assert platform.metadata.display_name == "AGIBOT X2 Ultra"
    assert platform.metadata.actuator_count == 31
    assert platform.metadata.command_modes == ("velocity", "stand", "stop", "recover", "waypoint")
    assert platform.metadata.max_linear_speed == 0.8
    assert platform.metadata.spawn_height == 0.85


def test_x2_parses_actuator_names_from_xml(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)

    assert platform.actuator_names() == ("left_hip_pitch", "right_hip_pitch", "left_knee")
    np.testing.assert_allclose(platform.initial_joint_qpos(), [0.1, 0.2, 0.3])
    assert platform.root_body_name() == "pelvis"


def test_x2_missing_asset_fails_with_clear_path(tmp_path):
    platform = AgibotX2Platform(model_dir=str(tmp_path / "missing"))

    try:
        platform.read_model_xml()
    except FileNotFoundError as exc:
        assert "x2_ultra.xml" in str(exc)
        assert "models/agibot_x2" not in str(exc)
    else:
        raise AssertionError("missing X2 asset did not raise FileNotFoundError")


def test_x2_runtime_status_detects_base_height_fall(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)
    pose = np.eye(4)
    pose[:3, 3] = [0.0, 0.0, 0.2]
    state = platform._state_from_arrays(
        base_pose=pose,
        base_velocity=np.zeros(3),
        joint_positions=np.zeros(3),
        joint_velocities=np.zeros(3),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        sim_time=0.0,
    )
    controller = platform.make_controller("robot_a")

    status = platform.runtime_status(
        "robot_a",
        state,
        RobotCommand.velocity([0.2, 0.0], 0.0),
        controller.health(),
    )

    assert status.state == RobotRuntimeState.FALLEN
    assert status.fall_reason == FallReason.BASE_HEIGHT
    assert status.disabled is True
