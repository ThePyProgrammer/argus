"""Tests for MuJoCo bridge (SIM-01 through SIM-04).

Integration tests require MuJoCo and the Go2 model. Unit-level tests
use mocks and can run anywhere.
"""

import inspect
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame
from src.bridge.sim_bridge import MuJoCoBridge


# ---------------------------------------------------------------------------
# Unit tests (mock MuJoCo)
# ---------------------------------------------------------------------------

class TestMuJoCoBridgeUnit:
    """Unit tests using mocked MuJoCo."""

    def test_import(self):
        """MuJoCoBridge can be imported."""
        assert MuJoCoBridge is not None

    def test_init_default_config(self):
        """Bridge initialises with default MuJoCoEnvConfig."""
        bridge = MuJoCoBridge()
        assert not bridge.is_running
        assert bridge.step_count == 0

    def test_step_signature_preserves_public_contract(self):
        """MuJoCoBridge.step keeps the public action and SensorFrame contract."""
        signature = inspect.signature(MuJoCoBridge.step)
        assert str(signature) == "(self, action: numpy.ndarray | None = None) -> src.bridge.sensor_types.SensorFrame"
        assert signature.return_annotation is SensorFrame

    def test_init_creates_registered_analytical_trot_controller(self):
        """Bridge owns one registered analytical_trot controller instance."""
        bridge = MuJoCoBridge()
        metadata = bridge._controller.compute({}, bridge._velocity_command(), 0.02).metadata
        assert metadata["controller_id"] == "analytical_trot"
        assert bridge._controller.__class__.__name__ == "AnalyticalTrotController"

    def test_init_custom_config(self):
        """Bridge accepts a custom config."""
        config = MuJoCoEnvConfig(model_path="custom/path.xml", target_step_hz=5.0)
        bridge = MuJoCoBridge(config)
        assert not bridge.is_running

    def test_step_without_start_raises(self):
        """Calling step() before start() raises RuntimeError."""
        bridge = MuJoCoBridge()
        with pytest.raises(RuntimeError, match="not started"):
            bridge.step()

    def test_set_velocity_buffers(self):
        """set_velocity stores the velocity command for next step."""
        bridge = MuJoCoBridge()
        bridge.set_velocity(np.array([1.0, 0.5]), 0.3)
        assert np.allclose(bridge._linear_vel, [1.0, 0.5])
        assert bridge._angular_vel == pytest.approx(0.3)

    def test_quat_to_rotation_identity(self):
        """Identity quaternion gives identity rotation matrix."""
        from src.bridge.sensor_types import quat_to_rotation_matrix
        R = quat_to_rotation_matrix(np.array([1, 0, 0, 0]))
        assert np.allclose(R, np.eye(3))

    def test_quat_to_rotation_orthonormal(self):
        """Rotation matrix from arbitrary quaternion is orthonormal."""
        from src.bridge.sensor_types import quat_to_rotation_matrix
        q = np.array([0.5, 0.5, 0.5, 0.5])  # 120 deg rotation
        R = quat_to_rotation_matrix(q)
        assert abs(np.linalg.det(R) - 1.0) < 1e-10
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-10)

    def test_direct_action_step_validates_and_returns_sensor_frame(self, monkeypatch):
        """Fake-started bridge writes direct actions via validation before stepping."""
        bridge = MuJoCoBridge()
        bridge._model = SimpleNamespace(opt=SimpleNamespace(timestep=0.002))
        bridge._data = SimpleNamespace(ctrl=np.zeros(12), sensordata=np.zeros(6))
        bridge._dt = 0.02
        expected_frame = SensorFrame(
            rgb=np.zeros((1, 1, 3), dtype=np.uint8),
            depth=None,
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )
        bridge._capture_frame = MagicMock(return_value=expected_frame)
        mj_step = MagicMock()
        monkeypatch.setitem(sys.modules, "mujoco", SimpleNamespace(mj_step=mj_step))

        action = np.array([0.0, 0.9, -1.8] * 4, dtype=np.float64)
        frame = bridge.step(action=action)

        assert frame is expected_frame
        assert isinstance(frame, SensorFrame)
        assert np.allclose(bridge._data.ctrl, action)
        mj_step.assert_called()

    def test_velocity_step_uses_controller_dispatch_and_returns_sensor_frame(self, monkeypatch):
        """Fake-started bridge with action=None writes registered controller target."""
        bridge = MuJoCoBridge()
        bridge._model = SimpleNamespace(opt=SimpleNamespace(timestep=0.002))
        bridge._data = SimpleNamespace(ctrl=np.zeros(12), sensordata=np.zeros(6))
        bridge._dt = 0.02
        bridge.set_velocity(np.array([0.4, -0.1]), 0.2)
        expected_frame = SensorFrame(
            rgb=np.zeros((1, 1, 3), dtype=np.uint8),
            depth=None,
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )
        bridge._capture_frame = MagicMock(return_value=expected_frame)
        mj_step = MagicMock()
        monkeypatch.setitem(sys.modules, "mujoco", SimpleNamespace(mj_step=mj_step))

        frame = bridge.step(action=None)

        assert frame is expected_frame
        assert isinstance(frame, SensorFrame)
        assert bridge._data.ctrl.shape == (12,)
        assert np.all(np.isfinite(bridge._data.ctrl))
        assert not np.allclose(bridge._data.ctrl, np.zeros(12))
        mj_step.assert_called()

    def test_single_bridge_phase2_contract_covers_d10_d11_d12_and_t204(self):
        """Single bridge keeps SensorFrame return contract while using analytical_trot seam."""
        bridge = MuJoCoBridge()
        signature = inspect.signature(MuJoCoBridge.step)

        assert signature.return_annotation is SensorFrame
        assert "SensorFrame" in str(signature)
        assert bridge._controller.compute({}, bridge._velocity_command(), 0.02).metadata["controller_id"] == "analytical_trot"

    def test_start_rejects_unknown_camera_name_before_capture(self, monkeypatch, tmp_path):
        """Invalid camera config must fail before Python negative indexing can select a pose."""
        bridge = self._fake_started_bridge_for_camera(monkeypatch, tmp_path, camera_name="missing_cam")

        with pytest.raises(ValueError, match="Camera 'missing_cam' not found"):
            bridge.start()

        bridge._capture_frame.assert_not_called()
        assert not bridge.is_running
        assert bridge._renderer is None

    def test_start_rejects_free_camera_id_before_capture(self, monkeypatch, tmp_path):
        """Free-camera rendering has no matching SensorFrame pose extraction contract."""
        bridge = self._fake_started_bridge_for_camera(monkeypatch, tmp_path, camera_name=-1)

        with pytest.raises(ValueError, match="Camera id -1 is out of range"):
            bridge.start()

        bridge._capture_frame.assert_not_called()
        assert not bridge.is_running
        assert bridge._renderer is None

    def _fake_started_bridge_for_camera(self, monkeypatch, tmp_path, camera_name):
        model_path = tmp_path / "scene.xml"
        go2_path = tmp_path / "go2.xml"
        model_path.write_text("<mujoco/>")
        go2_path.write_text("<mujoco/>")
        config = MuJoCoEnvConfig(model_path=str(model_path), camera_name=camera_name)
        bridge = MuJoCoBridge(config)

        class FakeModel:
            nq = 0
            ncam = 1
            opt = SimpleNamespace(timestep=0.002)

        class FakeData:
            qpos = np.zeros(0)
            ctrl = np.zeros(12)
            sensordata = np.zeros(0)

        fake_mujoco = SimpleNamespace(
            MjModel=SimpleNamespace(from_xml_string=MagicMock(return_value=FakeModel())),
            MjData=MagicMock(return_value=FakeData()),
            Renderer=MagicMock(),
            mj_name2id=MagicMock(return_value=-1),
            mj_step=MagicMock(),
            mjtObj=SimpleNamespace(mjOBJ_SENSOR=0, mjOBJ_CAMERA=1),
        )
        monkeypatch.setitem(sys.modules, "mujoco", fake_mujoco)
        monkeypatch.setattr(
            "src.bridge.sim_bridge.patch_actuators_to_position_with_floor",
            lambda _: "<mujoco/>",
        )
        bridge._capture_frame = MagicMock()
        return bridge


# ---------------------------------------------------------------------------
# Integration tests (require MuJoCo + Go2 model)
# ---------------------------------------------------------------------------

@pytest.fixture
def bridge():
    """Create and yield a MuJoCo bridge, ensuring cleanup."""
    config = MuJoCoEnvConfig()
    b = MuJoCoBridge(config)
    yield b
    if b.is_running:
        b.stop()


@pytest.mark.integration
def test_lifecycle(bridge):
    """SIM-01: Bridge starts, steps, and stops correctly."""
    frame = bridge.start()
    assert bridge.is_running
    assert isinstance(frame, SensorFrame)

    frame2 = bridge.step()
    assert isinstance(frame2, SensorFrame)
    assert bridge.step_count == 1

    bridge.stop()
    assert not bridge.is_running
    assert bridge.step_count == 0


@pytest.mark.integration
def test_sensor_extraction(bridge):
    """SIM-02: Step returns RGB and depth with correct shapes."""
    bridge.start()
    frame = bridge.step()

    # RGB
    assert frame.rgb.shape == (240, 320, 3)
    assert frame.rgb.dtype == np.uint8

    # Depth — MuJoCo provides metric float32
    assert frame.depth is not None
    assert frame.depth.shape == (240, 320)
    assert frame.depth.dtype == np.float32

    # Pose
    assert frame.ground_truth_pose.shape == (4, 4)
    assert frame.ground_truth_pose.dtype == np.float64

    # Sim time
    assert isinstance(frame.sim_time, float)


@pytest.mark.integration
def test_movement_command(bridge):
    """SIM-03: Velocity commands result in position change."""
    bridge.start()
    initial_frame = bridge.step()
    initial_pos = initial_frame.ground_truth_pose[:3, 3].copy()

    bridge.set_velocity(np.array([0.5, 0.0]), 0.0)
    for _ in range(20):
        frame = bridge.step()

    new_pos = frame.ground_truth_pose[:3, 3]
    # Position should have changed (robot moves or at least shifts)
    assert np.linalg.norm(new_pos - initial_pos) > 0.001


@pytest.mark.integration
def test_ground_truth_pose(bridge):
    """SIM-04: Ground-truth pose is a valid 4x4 homogeneous transform."""
    bridge.start()
    frame = bridge.step()

    pose = frame.ground_truth_pose
    assert pose.shape == (4, 4)
    assert pose.dtype == np.float64

    # Rotation part should be orthonormal
    R = pose[:3, :3]
    assert abs(np.linalg.det(R) - 1.0) < 1e-6

    # Bottom row should be [0, 0, 0, 1]
    assert np.allclose(pose[3, :], [0, 0, 0, 1])


@pytest.mark.integration
def test_sim_time_increments(bridge):
    """sim_time advances with each step."""
    frame0 = bridge.start()
    assert frame0.sim_time == 0.0

    frame1 = bridge.step()
    assert frame1.sim_time > 0.0

    frame2 = bridge.step()
    assert frame2.sim_time > frame1.sim_time


@pytest.mark.integration
def test_depth_is_metric(bridge):
    """Depth values are in meters (not normalized or colormapped)."""
    bridge.start()
    frame = bridge.step()

    # Depth should have reasonable metric values (not all 0 or all 1)
    valid_depth = frame.depth[frame.depth > 0]
    if len(valid_depth) > 0:
        assert valid_depth.min() > 0.01   # at least 1cm
        assert valid_depth.max() < 100.0  # less than 100m
