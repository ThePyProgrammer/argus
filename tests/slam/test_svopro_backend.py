"""Tests for SVO Pro / DSO backend with mocked SubprocessSLAMBridge.

All tests mock the SubprocessSLAMBridge since the DSO binary is not
available in CI. The mock creates a fake bridge that returns known
poses for testing coordinate transforms, GT offset seeding, and
crash (None return) handling.
"""

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
def mock_bridge():
    """Create a mock SubprocessSLAMBridge."""
    bridge = MagicMock()
    bridge.alive = True
    # Default: return identity pose with OK status
    bridge.send_frame.return_value = SLAMResult(
        pose=np.eye(4, dtype=np.float64),
        points=np.empty((0, 3), dtype=np.float64),
        colors=np.empty((0, 3), dtype=np.float64),
        metrics={"processing_time_ms": 5},
        tracking_status=TrackingStatus.OK,
    )
    return bridge


@pytest.fixture
def backend(mock_intrinsics, mock_bridge):
    """Create an SVOProBackend with mocked SubprocessSLAMBridge."""
    with patch(
        "src.slam.backends.svopro_backend.SubprocessSLAMBridge",
        return_value=mock_bridge,
    ):
        from src.slam.backends.svopro_backend import SVOProBackend
        be = SVOProBackend(intrinsics=mock_intrinsics)
        be._bridge = mock_bridge
        return be


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestSVOProCapabilities:
    """SVOProBackend has correct CAPABILITIES and PARAMETER_SCHEMA."""

    def test_supports_imu_false(self, backend):
        """CAPABILITIES has supports_imu=False (DSO is visual-only)."""
        assert backend.CAPABILITIES["supports_imu"] is False

    def test_outputs_dense_true(self, backend):
        """CAPABILITIES has outputs_dense=True (via depth_to_pointcloud)."""
        assert backend.CAPABILITIES["outputs_dense"] is True

    def test_supports_loop_closure_false(self, backend):
        """CAPABILITIES has supports_loop_closure=False."""
        assert backend.CAPABILITIES["supports_loop_closure"] is False

    def test_supports_stereo_false(self, backend):
        """CAPABILITIES has supports_stereo=False."""
        assert backend.CAPABILITIES["supports_stereo"] is False

    def test_parameter_schema_has_mode(self, backend):
        """PARAMETER_SCHEMA includes mode property."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "mode" in props
        assert props["mode"]["default"] == "mono"

    def test_parameter_schema_has_hang_timeout(self, backend):
        """PARAMETER_SCHEMA includes hang_timeout_ms property."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "hang_timeout_ms" in props


class TestSVOProProcessFrame:
    """process_frame behavior: subprocess calls, GT offset, coord transform, dense cloud."""

    def test_sends_frame_without_imu(self, backend, synthetic_frame, mock_bridge):
        """process_frame sends to bridge WITHOUT imu_readings (DSO is visual-only)."""
        backend.process_frame(synthetic_frame)
        call_args = mock_bridge.send_frame.call_args
        # imu_readings should not be passed or should be None
        if call_args.kwargs:
            assert call_args.kwargs.get("imu_readings") is None
        else:
            # Positional: rgb, depth, timestamp -- no imu_readings arg
            assert len(call_args.args) <= 3 or call_args.args[3] is None

    def test_seeds_gt_offset_from_first_frame(self, backend, synthetic_frame, mock_bridge):
        """First frame seeds _gt_offset from ground_truth_pose."""
        assert backend._gt_offset is None
        backend.process_frame(synthetic_frame)
        assert backend._gt_offset is not None
        np.testing.assert_array_equal(backend._gt_offset, np.eye(4))

    def test_applies_mujoco_from_optical_transform(self, backend, synthetic_frame, mock_bridge):
        """process_frame applies T_MUJOCO_FROM_OPTICAL coordinate transform."""
        from src.slam.backends.svopro_backend import T_MUJOCO_FROM_OPTICAL

        # Bridge returns identity => after transform it should be T_MUJOCO_FROM_OPTICAL
        # But GT offset is also identity, so result = I @ T_MUJOCO_FROM_OPTICAL @ I = T_MUJOCO_FROM_OPTICAL
        result = backend.process_frame(synthetic_frame)
        expected = T_MUJOCO_FROM_OPTICAL.copy()
        np.testing.assert_array_almost_equal(result.pose, expected)

    def test_generates_dense_cloud_from_depth(self, backend, synthetic_frame, mock_bridge):
        """process_frame generates dense cloud via depth_to_pointcloud."""
        result = backend.process_frame(synthetic_frame)
        # 10x10 depth image with all 1.0 should produce many points
        assert len(result.points) > 3, (
            f"Expected dense point cloud but got only {len(result.points)} points"
        )

    def test_crash_returns_lost(self, backend, synthetic_frame, mock_bridge):
        """When subprocess returns None (crash), process_frame returns LOST status."""
        mock_bridge.send_frame.return_value = None
        result = backend.process_frame(synthetic_frame)
        assert result.tracking_status == TrackingStatus.LOST

    def test_returns_slam_result(self, backend, synthetic_frame):
        """process_frame returns SLAMResult instance."""
        result = backend.process_frame(synthetic_frame)
        assert isinstance(result, SLAMResult)
        assert result.pose.shape == (4, 4)


class TestSVOProReset:
    """reset() shuts down and restarts subprocess bridge."""

    def test_reset_restarts_bridge(self, backend, synthetic_frame, mock_bridge):
        """reset() calls bridge.shutdown() and bridge.start()."""
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 1
        backend.reset()
        assert backend.num_frames_processed == 0
        mock_bridge.shutdown.assert_called()
        mock_bridge.start.assert_called()


class TestSVOProRegistry:
    """SVOProBackend is registered via __init__.py."""

    def test_svopro_in_init(self):
        """svopro_backend is imported in __init__.py with try/except."""
        import src.slam.backends.__init__ as init_mod
        import inspect
        source = inspect.getsource(init_mod)
        assert "svopro_backend" in source
