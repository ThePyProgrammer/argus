"""Tests for ICPBackend wrapper and backends package auto-registration."""

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.protocol import SLAMProtocol, SLAMResult, TrackingStatus
from src.slam.registry import SLAMRegistry


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
def _fresh_registry():
    """Clear and re-register ICP backend for each test."""
    SLAMRegistry._clear()
    # Re-import to trigger registration
    import importlib
    import src.slam.backends.icp_backend as mod
    importlib.reload(mod)
    yield
    SLAMRegistry._clear()


@pytest.fixture
def backend(mock_intrinsics, _fresh_registry):
    from src.slam.backends.icp_backend import ICPBackend
    return ICPBackend(intrinsics=mock_intrinsics)


class TestICPBackendProtocol:
    def test_icp_backend_isinstance_protocol(self, backend):
        """ICPBackend satisfies isinstance(instance, SLAMProtocol)."""
        assert isinstance(backend, SLAMProtocol)

    def test_icp_capabilities(self, backend):
        """CAPABILITIES dict matches expected values."""
        expected = {
            "supports_imu": False,
            "outputs_dense": True,
            "supports_loop_closure": False,
            "supports_stereo": False,
        }
        assert backend.CAPABILITIES == expected

    def test_icp_parameter_schema(self, backend):
        """PARAMETER_SCHEMA has voxel_size and max_cloud_points properties."""
        schema = backend.PARAMETER_SCHEMA
        assert "properties" in schema
        assert "voxel_size" in schema["properties"]
        assert "max_cloud_points" in schema["properties"]


class TestICPBackendBehavior:
    def test_process_frame_returns_slam_result(self, backend, synthetic_frame):
        """process_frame returns SLAMResult with correct types."""
        result = backend.process_frame(synthetic_frame)
        assert isinstance(result, SLAMResult)
        assert result.pose.shape == (4, 4)
        assert result.tracking_status == TrackingStatus.OK

    def test_reset_clears_state(self, backend, synthetic_frame):
        """After reset, num_frames_processed is 0 and get_poses() empty."""
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

    def test_num_frames_processed(self, backend, synthetic_frame):
        """num_frames_processed increments correctly."""
        assert backend.num_frames_processed == 0
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 1


class TestICPBackendRegistry:
    def test_registry_auto_registration(self, _fresh_registry):
        """Importing src.slam.backends registers 'icp' in SLAMRegistry."""
        assert "icp" in SLAMRegistry._backends

    def test_create_via_registry(self, mock_intrinsics, _fresh_registry):
        """SLAMRegistry.create('icp', ...) returns ICPBackend instance."""
        from src.slam.backends.icp_backend import ICPBackend
        instance = SLAMRegistry.create("icp", intrinsics=mock_intrinsics)
        assert isinstance(instance, ICPBackend)
