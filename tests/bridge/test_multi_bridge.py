"""Tests for multi-robot configuration, scene builder, and multi-robot bridge.

Tests use MockMultiRobotBridge for fast, MuJoCo-free unit testing.
Scene builder XML output is tested with the actual go2.xml model file.
"""

from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.go2 import Go2Platform
import src.bridge.scene_builder as scene_builder
from src.bridge.scene_builder import (
    build_multi_robot_scene,
    build_two_robot_office_scene,
    build_two_robot_scene,
)
from src.bridge.sensor_types import SensorFrame


# ---------- MultiRobotConfig tests ----------


def test_multi_robot_config_defaults():
    """MultiRobotConfig has correct default robot_ids, spawn_positions, and boot_phase_steps."""
    config = MultiRobotConfig()
    assert config.robot_ids == ("robot_a", "robot_b")
    assert "robot_a" in config.spawn_positions
    assert "robot_b" in config.spawn_positions
    assert config.spawn_positions["robot_a"] == (0.0, 0.0, 0.3)
    assert config.spawn_positions["robot_b"] == (5.0, 0.0, 0.3)
    assert config.resolution == (320, 240)
    assert config.boot_phase_steps == 200
    assert config.sim_steps_per_frame == 5
    assert config.model_dir == "models/unitree_go2"


def test_multi_robot_config_accepts_platform_name_and_config():
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": "models/agibot_x2"},
    )

    assert config.platform == "agibot_x2"
    assert config.platform_config == {"model_dir": "models/agibot_x2"}


# ---------- Scene builder tests ----------


_MODEL_DIR = Path("models/unitree_go2")
_HAS_MODEL = (_MODEL_DIR / "go2.xml").exists()


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_two_robot_scene_valid_xml():
    """build_two_robot_scene returns XML string with robot_a_ and robot_b_ prefixed names."""
    config = MultiRobotConfig()
    xml_str = build_two_robot_scene(config.model_dir, config.spawn_positions)
    assert isinstance(xml_str, str)
    assert "robot_a_" in xml_str
    assert "robot_b_" in xml_str
    # Should have two robot base bodies
    assert "robot_a_base" in xml_str
    assert "robot_b_base" in xml_str
    # Should have prefixed actuators
    assert "robot_a_FL_hip" in xml_str
    assert "robot_b_FR_hip" in xml_str
    # Should have cameras
    assert "robot_a_cam" in xml_str
    assert "robot_b_cam" in xml_str


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_multi_robot_scene_uses_platform_camera_and_prefixes():
    platform = Go2Platform()
    xml_str, assets = build_multi_robot_scene(
        platform=platform,
        spawn_positions={"robot_a": (0.0, 0.0, 0.3), "robot_b": (5.0, 0.0, 0.3)},
    )

    assert isinstance(xml_str, str)
    assert isinstance(assets, dict)
    assert "robot_a_base" in xml_str
    assert "robot_b_base" in xml_str
    assert "robot_a_FL_hip" in xml_str
    assert "robot_b_FR_hip" in xml_str
    assert "robot_a_cam" in xml_str
    assert "robot_b_cam" in xml_str


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_two_robot_scene_spawn_positions():
    """build_two_robot_scene places robots at specified spawn positions."""
    spawn = {
        "robot_a": (1.0, 2.0, 0.3),
        "robot_b": (5.0, 6.0, 0.3),
    }
    xml_str = build_two_robot_scene("models/unitree_go2", spawn)
    # robot_a base body should have pos containing "1 2 0.3" (approx)
    assert "1 2" in xml_str or "1.0 2.0" in xml_str
    assert "5 6" in xml_str or "5.0 6.0" in xml_str


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_two_robot_scene_patches_go2_actuators_to_position_controls():
    xml_str = build_two_robot_scene("models/unitree_go2", {
        "robot_a": (0.0, 0.0, 0.3),
        "robot_b": (5.0, 0.0, 0.3),
    })
    root = ET.fromstring(xml_str)
    generated_actuators = [
        actuator
        for actuator in root.findall("./actuator/*")
        if actuator.attrib.get("name", "").startswith(("robot_a_", "robot_b_"))
    ]

    assert generated_actuators
    assert all(actuator.tag == "position" for actuator in generated_actuators)
    assert all("kp" in actuator.attrib for actuator in generated_actuators)
    assert all("kv" in actuator.attrib for actuator in generated_actuators)
    assert not root.findall("./actuator/motor")


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_multi_robot_scene_returns_assets_without_compiler_asset_dirs():
    xml_str, assets = build_multi_robot_scene(
        Go2Platform(),
        {"robot_a": (0.0, 0.0, 0.3), "robot_b": (5.0, 0.0, 0.3)},
    )
    root = ET.fromstring(xml_str)
    compiler = root.find("compiler")

    assert compiler is not None
    assert "meshdir" not in compiler.attrib
    assert "texturedir" not in compiler.attrib
    assert "base_0.obj" in assets


def test_build_two_robot_office_scene_patches_go2_actuators_to_position(tmp_path, monkeypatch):
    """Office scene builder keeps Go2 actuators runtime-ready as position controls."""
    scene_data_dir = tmp_path / "scenes"
    scene_data_dir.mkdir()
    (scene_data_dir / "scene_office1.xml").write_text(
        """
        <mujoco model="office">
          <compiler meshdir="scene_office1/office_split" texturedir="scene_office1/textures"/>
          <worldbody/>
          <asset/>
        </mujoco>
        """,
        encoding="utf-8",
    )
    model_dir = tmp_path / "go2"
    model_dir.mkdir()
    (model_dir / "go2.xml").write_text(
        """
        <mujoco model="go2">
          <worldbody>
            <body name="base">
              <freejoint/>
              <joint name="FL_hip_joint"/>
            </body>
          </worldbody>
          <actuator>
            <motor class="hip" name="FL_hip" joint="FL_hip_joint" ctrlrange="-1 1"/>
          </actuator>
        </mujoco>
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(scene_builder, "_find_dimos_scene_data", lambda: scene_data_dir)

    xml_str, _assets = build_two_robot_office_scene(
        str(model_dir), {"robot_a": (0.0, 0.0, 0.3)}
    )

    root = ET.fromstring(xml_str)
    actuator = root.find("./actuator/position[@name='robot_a_FL_hip']")
    assert actuator is not None
    assert actuator.attrib["joint"] == "robot_a_FL_hip_joint"
    assert actuator.attrib["kp"] == "80"
    assert actuator.attrib["kv"] == "4"
    assert "ctrlrange" not in actuator.attrib


# ---------- MultiRobotBridge tests ----------


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_multi_robot_bridge_flat_scene_loads_generated_assets(monkeypatch):
    """Flat bridge runtime passes generated mesh assets into MuJoCo XML loading."""
    captured = {}

    class FakeModel:
        njnt = 0
        opt = types.SimpleNamespace(timestep=0.002)

        @staticmethod
        def from_xml_string(xml_str, assets=None):
            captured["xml_str"] = xml_str
            captured["assets"] = assets
            raise RuntimeError("stop after XML load")

    fake_mujoco = types.SimpleNamespace(MjModel=FakeModel)
    monkeypatch.setitem(sys.modules, "mujoco", fake_mujoco)

    bridge = MultiRobotBridge(MultiRobotConfig(scene="flat"))
    with pytest.raises(RuntimeError, match="stop after XML load"):
        bridge.start()

    assert captured["xml_str"]
    assert captured["assets"]
    assert "base_0.obj" in captured["assets"]


def test_multi_bridge_stop_before_start_is_safe():
    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    bridge.stop()

    assert not bridge.is_running
    assert bridge.step_count == 0


# ---------- MockMultiRobotBridge tests ----------


def test_mock_multi_bridge_start_returns_both_frames(mock_multi_bridge):
    """MockMultiRobotBridge.start() returns dict with both robot keys as SensorFrames."""
    frames = mock_multi_bridge.start()
    assert isinstance(frames, dict)
    assert "robot_a" in frames
    assert "robot_b" in frames
    assert isinstance(frames["robot_a"], SensorFrame)
    assert isinstance(frames["robot_b"], SensorFrame)


def test_mock_multi_bridge_independent_velocity(mock_multi_bridge):
    """Setting velocity only for robot_a moves it while robot_b stays put."""
    mock_multi_bridge.start()
    initial_b_pos = mock_multi_bridge._positions["robot_b"].copy()

    mock_multi_bridge.set_velocity("robot_a", np.array([1.0, 0.0]), 0.0)
    frames = mock_multi_bridge.step()

    # robot_a should have moved in x
    assert frames["robot_a"].ground_truth_pose[0, 3] > 0.0
    # robot_b should NOT have moved
    np.testing.assert_array_almost_equal(
        frames["robot_b"].ground_truth_pose[:3, 3], initial_b_pos
    )


def test_mock_multi_bridge_different_poses(mock_multi_bridge):
    """After start, robot_a at (0,0,0.3) and robot_b at (10,0,0.3)."""
    frames = mock_multi_bridge.start()
    pos_a = frames["robot_a"].ground_truth_pose[:3, 3]
    pos_b = frames["robot_b"].ground_truth_pose[:3, 3]

    np.testing.assert_array_almost_equal(pos_a, [0.0, 0.0, 0.3])
    np.testing.assert_array_almost_equal(pos_b, [10.0, 0.0, 0.3])


def test_mock_multi_bridge_step_count(mock_multi_bridge):
    """Step count increments correctly."""
    mock_multi_bridge.start()
    assert mock_multi_bridge.step_count == 0
    mock_multi_bridge.step()
    assert mock_multi_bridge.step_count == 1
    mock_multi_bridge.step()
    assert mock_multi_bridge.step_count == 2


def test_mock_multi_bridge_properties(mock_multi_bridge):
    """robot_ids and is_running properties work correctly."""
    assert mock_multi_bridge.robot_ids == ("robot_a", "robot_b")
    assert mock_multi_bridge.is_running is True
