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
    missing_dir = tmp_path / "missing"
    platform = AgibotX2Platform(model_dir=str(missing_dir))

    try:
        platform.read_model_xml()
    except FileNotFoundError as exc:
        assert str(exc) == f"AGIBOT X2 MuJoCo model not found: {missing_dir / 'x2_ultra.xml'}"
        assert "models/agibot_x2" not in str(exc)
    else:
        raise AssertionError("missing X2 asset did not raise FileNotFoundError")


def test_x2_extract_state_uses_model_dof_address_for_nonzero_qpos_start(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)
    qpos_start = 10
    model = type(
        "FakeModel",
        (),
        {
            "jnt_qposadr": np.array([0, qpos_start]),
            "jnt_dofadr": np.array([0, 9]),
        },
    )()
    qpos = np.zeros(20, dtype=np.float64)
    qpos[qpos_start:qpos_start + 7] = [0.0, 0.0, 0.85, 1.0, 0.0, 0.0, 0.0]
    qpos[qpos_start + 7:qpos_start + 10] = [0.1, 0.2, 0.3]
    qvel = np.arange(30, dtype=np.float64)
    data = type("FakeData", (), {"qpos": qpos, "qvel": qvel})()

    state = platform.extract_state(model, data, qpos_start=qpos_start, sim_time=1.25)

    np.testing.assert_allclose(state.base_velocity, [9.0, 10.0, 11.0])
    np.testing.assert_allclose(state.joint_velocities, [15.0, 16.0, 17.0])


def test_x2_extract_state_uses_cached_actuator_count_without_rereading_xml(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)
    assert platform.actuator_names() == ("left_hip_pitch", "right_hip_pitch", "left_knee")
    (model_dir / "x2_ultra.xml").unlink()
    qpos = np.array([0.0, 0.0, 0.85, 1.0, 0.0, 0.0, 0.0, 0.1, 0.2, 0.3], dtype=np.float64)
    qvel = np.array([0.4, 0.5, 0.6, 0.0, 0.0, 0.0, 1.1, 1.2, 1.3], dtype=np.float64)
    data = type("FakeData", (), {"qpos": qpos, "qvel": qvel})()

    state = platform.extract_state(model=None, data=data, qpos_start=0, sim_time=2.0)

    np.testing.assert_allclose(state.base_velocity, [0.4, 0.5, 0.6])
    np.testing.assert_allclose(state.joint_velocities, [1.1, 1.2, 1.3])


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
