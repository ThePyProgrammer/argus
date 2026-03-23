"""Tests for ORB-SLAM3 backend with mocked orbslam3 module.

All tests mock the orbslam3 C++ binding since it may not be installable
on all platforms (especially Python 3.14). The mock creates a fake
orbslam3 module with System, Sensor.RGBD, and Sensor.MONOCULAR.
"""

import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import open3d as o3d
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.protocol import SLAMProtocol, SLAMResult, TrackingStatus
from src.slam.registry import SLAMRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_intrinsics():
    return CameraIntrinsics(fx=100.0, fy=100.0, cx=5.0, cy=5.0, width=10, height=10)


@pytest.fixture
def synthetic_frame():
    return SensorFrame(
        rgb=np.zeros((10, 10, 3), dtype=np.uint8),
        depth=np.ones((10, 10), dtype=np.float32),
        ground_truth_pose=np.eye(4),
        sim_time=0.0,
    )


@pytest.fixture
def mock_orbslam3_module():
    """Create a fake orbslam3 module with System and Sensor classes."""
    mod = types.ModuleType("orbslam3")

    # Sensor enum-like namespace
    sensor = types.SimpleNamespace()
    sensor.RGBD = "RGBD"
    sensor.MONOCULAR = "MONOCULAR"
    mod.Sensor = sensor

    # System class mock
    mock_system_cls = MagicMock()
    mock_system_instance = MagicMock()
    mock_system_instance.get_frame_pose.return_value = np.eye(4, dtype=np.float64)
    mock_system_instance.get_current_points.return_value = [
        ((0.1, 0.2, 0.3), (10, 20)),
        ((0.4, 0.5, 0.6), (30, 40)),
        ((0.7, 0.8, 0.9), (50, 60)),
    ]
    mock_system_instance.process_image_rgbd.return_value = None
    mock_system_instance.process_image_mono.return_value = None
    mock_system_cls.return_value = mock_system_instance
    mod.System = mock_system_cls

    return mod


@pytest.fixture
def _orbslam3_patched(mock_orbslam3_module, tmp_path):
    """Patch sys.modules with mock orbslam3 and reload the backend module.

    Also creates a fake vocab file so __init__ does not raise FileNotFoundError.
    """
    # Create fake vocab file
    vocab_dir = tmp_path / "models" / "orbslam3"
    vocab_dir.mkdir(parents=True)
    vocab_file = vocab_dir / "ORBvoc.txt"
    vocab_file.write_text("fake vocab")

    # Patch orbslam3 into sys.modules
    old = sys.modules.get("orbslam3")
    sys.modules["orbslam3"] = mock_orbslam3_module

    # Clear registry so we get a clean state
    SLAMRegistry._clear()

    # (Re)load the backend module so it picks up the mock
    if "src.slam.backends.orbslam3_backend" in sys.modules:
        mod = importlib.reload(sys.modules["src.slam.backends.orbslam3_backend"])
    else:
        import src.slam.backends.orbslam3_backend as mod
        mod = importlib.reload(mod)

    yield {"module": mod, "vocab_path": str(vocab_file)}

    # Restore
    SLAMRegistry._clear()
    if old is None:
        sys.modules.pop("orbslam3", None)
    else:
        sys.modules["orbslam3"] = old


@pytest.fixture
def backend(_orbslam3_patched, mock_intrinsics):
    """Create an ORBSlam3Backend instance with mocked orbslam3."""
    mod = _orbslam3_patched["module"]
    vocab_path = _orbslam3_patched["vocab_path"]
    return mod.ORBSlam3Backend(
        intrinsics=mock_intrinsics,
        vocab_path=vocab_path,
    )


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestORBSlam3Protocol:
    """ORBSlam3Backend satisfies SLAMProtocol and has correct metadata."""

    def test_isinstance_protocol(self, backend):
        """ORBSlam3Backend satisfies isinstance(instance, SLAMProtocol)."""
        assert isinstance(backend, SLAMProtocol)

    def test_capabilities(self, backend):
        """CAPABILITIES dict has expected values."""
        expected = {
            "supports_imu": False,
            "outputs_dense": True,
            "supports_loop_closure": True,
            "supports_stereo": False,
        }
        assert backend.CAPABILITIES == expected

    def test_parameter_schema(self, backend):
        """PARAMETER_SCHEMA has nFeatures, scaleFactor, nLevels, mode."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "nFeatures" in props
        assert "scaleFactor" in props
        assert "nLevels" in props
        assert "mode" in props


class TestORBSlam3Behavior:
    """Behavioral tests for process_frame, reset, get_global_cloud."""

    def test_process_frame_returns_slam_result(self, backend, synthetic_frame):
        """process_frame returns SLAMResult with correct types."""
        result = backend.process_frame(synthetic_frame)
        assert isinstance(result, SLAMResult)
        assert result.pose.shape == (4, 4)
        assert result.tracking_status == TrackingStatus.OK

    def test_process_frame_dense_points_from_depth(self, backend, synthetic_frame):
        """SLAMResult.points are dense (from depth_to_pointcloud), NOT sparse ORB features."""
        result = backend.process_frame(synthetic_frame)
        # Dense cloud from 10x10 depth image with all 1.0 should have many points
        # Sparse features mock has only 3 points
        # Dense should have >> 3 points (100 valid depth pixels -> ~100 points)
        assert len(result.points) > 3, (
            f"Expected dense point cloud but got only {len(result.points)} points"
        )

    def test_sparse_feature_count_in_metrics(self, backend, synthetic_frame):
        """SLAMResult.metrics contains 'sparse_feature_count' key."""
        result = backend.process_frame(synthetic_frame)
        assert "sparse_feature_count" in result.metrics
        assert result.metrics["sparse_feature_count"] == 3  # mock returns 3 points

    def test_reset_clears_state(self, backend, synthetic_frame):
        """After reset, num_frames_processed=0 and get_poses() empty."""
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 1
        backend.reset()
        assert backend.num_frames_processed == 0
        assert backend.get_poses() == []

    def test_get_global_cloud_returns_tuple(self, backend, synthetic_frame):
        """get_global_cloud returns (ndarray, ndarray) tuple."""
        backend.process_frame(synthetic_frame)
        points, colors = backend.get_global_cloud()
        assert isinstance(points, np.ndarray)
        assert isinstance(colors, np.ndarray)

    def test_num_frames_processed_increments(self, backend, synthetic_frame):
        """num_frames_processed increments correctly."""
        assert backend.num_frames_processed == 0
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 1
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 2

    def test_tracking_lost_returns_last_pose(self, _orbslam3_patched, mock_intrinsics, synthetic_frame):
        """When tracking is LOST (pose is None), returns last known pose with LOST status."""
        mod = _orbslam3_patched["module"]
        vocab_path = _orbslam3_patched["vocab_path"]
        be = mod.ORBSlam3Backend(intrinsics=mock_intrinsics, vocab_path=vocab_path)

        # First frame: normal tracking
        result1 = be.process_frame(synthetic_frame)
        assert result1.tracking_status == TrackingStatus.OK
        first_pose = result1.pose.copy()

        # Second frame: simulate LOST (get_frame_pose returns None)
        be._slam.get_frame_pose.return_value = None
        result2 = be.process_frame(synthetic_frame)
        assert result2.tracking_status == TrackingStatus.LOST
        np.testing.assert_array_equal(result2.pose, first_pose)

    def test_monocular_mode(self, _orbslam3_patched, mock_intrinsics, mock_orbslam3_module):
        """Monocular mode selects orbslam3.Sensor.MONOCULAR."""
        mod = _orbslam3_patched["module"]
        vocab_path = _orbslam3_patched["vocab_path"]
        be = mod.ORBSlam3Backend(
            intrinsics=mock_intrinsics, mode="monocular", vocab_path=vocab_path,
        )
        # Check that System was called with MONOCULAR sensor enum
        call_args = mock_orbslam3_module.System.call_args
        assert call_args is not None
        # The sensor arg should be MONOCULAR
        # System(vocab_path, config_path, sensor_enum)
        args = call_args[0]
        assert args[2] == "MONOCULAR"


class TestORBSlam3Registry:
    """Registration and factory creation via SLAMRegistry."""

    def test_registry_registration(self, _orbslam3_patched):
        """Importing the module registers 'orbslam3' in SLAMRegistry."""
        assert "orbslam3" in SLAMRegistry._backends

    def test_create_via_registry(self, _orbslam3_patched, mock_intrinsics):
        """SLAMRegistry.create('orbslam3', ...) returns ORBSlam3Backend."""
        mod = _orbslam3_patched["module"]
        vocab_path = _orbslam3_patched["vocab_path"]
        instance = SLAMRegistry.create(
            "orbslam3", intrinsics=mock_intrinsics, vocab_path=vocab_path,
        )
        assert isinstance(instance, mod.ORBSlam3Backend)


class TestORBSlam3CoordinateTransform:
    """_convert_pose applies T_MUJOCO_FROM_OPTICAL correctly."""

    def test_convert_pose_known_rotation(self, backend):
        """_convert_pose applies T_MUJOCO_FROM_OPTICAL @ orbslam_pose."""
        identity = np.eye(4, dtype=np.float64)
        result = backend._convert_pose(identity)
        # T_MUJOCO_FROM_OPTICAL @ I = T_MUJOCO_FROM_OPTICAL
        expected = np.array([
            [0,  0, 1, 0],
            [-1, 0, 0, 0],
            [0, -1, 0, 0],
            [0,  0, 0, 1],
        ], dtype=np.float64)
        np.testing.assert_array_almost_equal(result, expected)


class TestORBSlam3Config:
    """_write_config generates valid YAML with camera params."""

    def test_write_config_content(self, backend):
        """_write_config generates YAML with correct camera params and DepthMapFactor."""
        import os
        config_path = backend._config_path
        assert os.path.isfile(config_path)
        with open(config_path) as f:
            content = f.read()
        assert "Camera.fx: 100.0" in content
        assert "Camera.fy: 100.0" in content
        assert "Camera.cx: 5.0" in content
        assert "Camera.cy: 5.0" in content
        assert "Camera.width: 10" in content
        assert "Camera.height: 10" in content
        assert "DepthMapFactor: 1.0" in content
        assert "ORBextractor.nFeatures: 1000" in content


class TestORBSlam3Unavailable:
    """When orbslam3 is not installed, backend is unavailable."""

    def test_unavailable_raises_import_error(self, mock_intrinsics, tmp_path):
        """When orbslam3 not installed, _ORBSLAM3_AVAILABLE is False and constructor raises."""
        old = sys.modules.pop("orbslam3", None)
        # Insert None sentinel to block re-import during reload
        sys.modules["orbslam3"] = None  # type: ignore[assignment]
        SLAMRegistry._clear()

        try:
            if "src.slam.backends.orbslam3_backend" in sys.modules:
                mod = importlib.reload(sys.modules["src.slam.backends.orbslam3_backend"])
            else:
                import src.slam.backends.orbslam3_backend as mod
                mod = importlib.reload(mod)

            assert mod._ORBSLAM3_AVAILABLE is False
            with pytest.raises(ImportError, match="orbslam3"):
                mod.ORBSlam3Backend(intrinsics=mock_intrinsics)
        finally:
            SLAMRegistry._clear()
            if old is not None:
                sys.modules["orbslam3"] = old
            else:
                sys.modules.pop("orbslam3", None)
