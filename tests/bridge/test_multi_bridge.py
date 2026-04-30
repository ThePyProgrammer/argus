"""Tests for multi-robot configuration, scene builder, and multi-robot bridge.

Tests use MockMultiRobotBridge for fast, MuJoCo-free unit testing.
Scene builder XML output is tested with the actual go2.xml model file.
"""

from pathlib import Path
import inspect
import sys
import types

import numpy as np
import pytest

from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.scene_builder import build_two_robot_scene
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


# ---------- MultiRobotBridge controller seam tests ----------


def _sensor_frame_at(x: float) -> SensorFrame:
    pose = np.eye(4, dtype=np.float64)
    pose[0, 3] = x
    return SensorFrame(
        rgb=np.zeros((1, 1, 3), dtype=np.uint8),
        depth=None,
        ground_truth_pose=pose,
        sim_time=0.0,
    )


class _FakeData:
    def __init__(self, ctrl_size: int = 24) -> None:
        self.ctrl = np.zeros(ctrl_size, dtype=np.float64)
        self.qpos = np.zeros(32, dtype=np.float64)


class _FakeModel:
    pass


def test_multi_bridge_step_public_contract_is_dict_of_sensor_frames():
    """MultiRobotBridge.step remains the no-arg dict-return public contract."""
    from src.bridge.multi_bridge import MultiRobotBridge

    signature = inspect.signature(MultiRobotBridge.step)
    assert list(signature.parameters) == ["self"]
    assert signature.return_annotation == dict[str, SensorFrame]


def test_multi_bridge_stop_before_start_is_safe():
    """Cleanup should be safe around failed or skipped startup."""
    from src.bridge.multi_bridge import MultiRobotBridge

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    bridge.stop()

    assert not bridge.is_running
    assert bridge.step_count == 0


def test_multi_bridge_initializes_one_controller_per_robot_id():
    """Each configured robot owns a distinct registered controller instance."""
    from src.bridge.multi_bridge import MultiRobotBridge
    from src.locomotion.controllers import LocomotionCommand

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    assert set(bridge._controllers) == {"robot_a", "robot_b"}
    assert bridge._controllers["robot_a"] is not bridge._controllers["robot_b"]
    assert bridge._controllers["robot_a"].compute({}, LocomotionCommand(), 0.02).metadata[
        "controller_id"
    ] == "analytical_trot"
    assert bridge._controllers["robot_b"].compute({}, LocomotionCommand(), 0.02).metadata[
        "controller_id"
    ] == "analytical_trot"


def test_multi_bridge_step_before_start_still_raises_not_started():
    """The controller seam must not change pre-start lifecycle errors."""
    from src.bridge.multi_bridge import MultiRobotBridge

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    with pytest.raises(RuntimeError, match="not started"):
        bridge.step()


def test_multi_bridge_set_velocity_rejects_unknown_robot_id():
    """Unknown command targets must fail instead of disappearing at step()."""
    from src.bridge.multi_bridge import MultiRobotBridge

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    with pytest.raises(KeyError, match="Unknown robot_id 'robot_c'"):
        bridge.set_velocity("robot_c", np.array([0.3, 0.0]), 0.0)

    assert set(bridge._velocities) == {"robot_a", "robot_b"}


def test_multi_bridge_set_velocity_validates_command_values():
    """Malformed velocity commands are rejected at the public bridge boundary."""
    from src.bridge.multi_bridge import MultiRobotBridge

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b")))

    with pytest.raises(ValueError, match=r"shape-\(2,\)"):
        bridge.set_velocity("robot_a", np.array([0.3, 0.0, 0.1]), 0.0)
    with pytest.raises(ValueError, match="finite"):
        bridge.set_velocity("robot_a", np.array([np.nan, 0.0]), 0.0)
    with pytest.raises(ValueError, match="finite"):
        bridge.set_velocity("robot_a", np.array([0.0, 0.0]), np.inf)


def test_multi_bridge_start_resets_per_robot_controllers(monkeypatch):
    """Restarted simulations must begin each controller from its reset gait phase."""
    from src.bridge.multi_bridge import MultiRobotBridge

    reset_calls: list[str] = []

    class FakeController:
        def __init__(self, robot_id: str) -> None:
            self.robot_id = robot_id

        def reset(self, seed: int | None = None) -> None:
            del seed
            reset_calls.append(self.robot_id)

        def compute(self, observation, command, dt):
            del observation, command, dt
            from src.locomotion.controllers import ControllerResult

            return ControllerResult(action=np.zeros(12), metadata={"controller_id": self.robot_id})

    class FakeModel:
        opt = types.SimpleNamespace(timestep=0.002)
        nq = 40
        njnt = 2
        ncam = 2
        jnt_bodyid = np.array([0, 1])
        jnt_type = np.array([0, 0])
        jnt_qposadr = np.array([0, 19])

    class FakeData:
        qpos = np.zeros(40)
        ctrl = np.zeros(24)

    name_ids = {
        "robot_a_base": 0,
        "robot_b_base": 1,
        "robot_a_cam": 0,
        "robot_b_cam": 1,
    }
    for offset, suffix in enumerate(("FL_hip", "FL_thigh", "FL_calf", "FR_hip", "FR_thigh", "FR_calf", "RL_hip", "RL_thigh", "RL_calf", "RR_hip", "RR_thigh", "RR_calf")):
        name_ids[f"robot_a_{suffix}"] = offset
        name_ids[f"robot_b_{suffix}"] = 12 + offset

    fake_mujoco = types.SimpleNamespace(
        MjModel=types.SimpleNamespace(from_xml_string=lambda *args, **kwargs: FakeModel()),
        MjData=lambda model: FakeData(),
        Renderer=lambda *args, **kwargs: types.SimpleNamespace(close=lambda: None),
        mj_name2id=lambda model, obj, name: name_ids.get(name, -1),
        mj_step=lambda model, data: None,
        mjtObj=types.SimpleNamespace(mjOBJ_BODY=0, mjOBJ_ACTUATOR=1, mjOBJ_CAMERA=2),
        viewer=types.SimpleNamespace(launch_passive=lambda model, data: None),
    )
    monkeypatch.setitem(sys.modules, "mujoco", fake_mujoco)
    monkeypatch.setitem(sys.modules, "mujoco.viewer", fake_mujoco.viewer)
    monkeypatch.setattr(
        "src.bridge.multi_bridge.build_two_robot_scene",
        lambda model_dir, spawn_positions: "<mujoco/>",
    )

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a", "robot_b"), boot_phase_steps=0))
    bridge._controllers = {
        "robot_a": FakeController("robot_a"),
        "robot_b": FakeController("robot_b"),
    }
    bridge._capture_frame = lambda robot_id: _sensor_frame_at(1.0 if robot_id == "robot_a" else 2.0)

    bridge.start()

    assert reset_calls == ["robot_a", "robot_b"]


def test_multi_bridge_step_writes_controller_targets_by_robot_ctrl_indices(monkeypatch):
    """Fake-started bridge applies each robot controller output to its own ctrl indices."""
    from src.bridge.multi_bridge import MultiRobotBridge

    step_calls: list[tuple[object, object]] = []
    fake_mujoco = types.SimpleNamespace(
        mj_step=lambda model, data: step_calls.append((model, data))
    )
    monkeypatch.setitem(sys.modules, "mujoco", fake_mujoco)

    bridge = MultiRobotBridge(
        MultiRobotConfig(robot_ids=("robot_a", "robot_b"), sim_steps_per_frame=2)
    )
    bridge._model = _FakeModel()
    bridge._data = _FakeData()
    bridge._dt = 0.02
    bridge._ctrl_indices = {
        "robot_a": list(range(0, 12)),
        "robot_b": list(range(12, 24)),
    }
    bridge._qpos_starts = {"robot_a": 0, "robot_b": 16}
    bridge._viewer_handle = None
    bridge._capture_frame = lambda robot_id: _sensor_frame_at(1.0 if robot_id == "robot_a" else 2.0)

    bridge.set_velocity("robot_a", np.array([0.3, 0.0]), 0.0)
    bridge.set_velocity("robot_b", np.array([0.0, 0.2]), 0.5)

    frames = bridge.step()

    assert isinstance(frames, dict)
    assert set(frames) == {"robot_a", "robot_b"}
    assert all(isinstance(frame, SensorFrame) for frame in frames.values())
    assert bridge.step_count == 1
    assert bridge._last_frames == frames
    assert len(step_calls) == 2

    robot_a_ctrl = bridge._data.ctrl[:12].copy()
    robot_b_ctrl = bridge._data.ctrl[12:24].copy()
    assert robot_a_ctrl.shape == (12,)
    assert robot_b_ctrl.shape == (12,)
    assert np.any(robot_a_ctrl != 0.0)
    assert np.any(robot_b_ctrl != 0.0)
    assert not np.allclose(robot_a_ctrl, robot_b_ctrl)


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
