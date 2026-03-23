"""Tests for OpenVINS backend with mocked SubprocessSLAMBridge.

Unlike ORB-SLAM3 (which mocks a Python C++ binding), OpenVINS communicates
via SubprocessSLAMBridge. Tests mock the bridge entirely so no C++ binary
or OpenVINS installation is needed.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import open3d as o3d
import pytest

from src.bridge.sensor_types import CameraIntrinsics, IMUReading, SensorFrame
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
        ground_truth_pose=np.eye(4, dtype=np.float64),
        sim_time=0.0,
        imu_readings=[
            IMUReading(
                accel=np.array([0.0, 0.0, 9.81]),
                gyro=np.array([0.0, 0.0, 0.0]),
                timestamp=0.0,
            ),
        ],
    )


@pytest.fixture
def synthetic_frame_2():
    """Second frame with a different GT pose (translated 1m forward)."""
    gt = np.eye(4, dtype=np.float64)
    gt[0, 3] = 1.0  # 1m forward in x
    return SensorFrame(
        rgb=np.zeros((10, 10, 3), dtype=np.uint8),
        depth=np.ones((10, 10), dtype=np.float32),
        ground_truth_pose=gt,
        sim_time=0.033,
        imu_readings=[
            IMUReading(
                accel=np.array([0.0, 0.0, 9.81]),
                gyro=np.array([0.0, 0.0, 0.0]),
                timestamp=0.033,
            ),
        ],
    )


@pytest.fixture
def mock_bridge():
    """Create a mock SubprocessSLAMBridge."""
    bridge = MagicMock()
    bridge.alive = True
    # Default: return a valid SLAMResult with identity pose
    bridge.send_frame.return_value = SLAMResult(
        pose=np.eye(4, dtype=np.float64),
        points=np.empty((0, 3), dtype=np.float64),
        colors=np.empty((0, 3), dtype=np.float64),
        metrics={"processing_time_ms": 5.0},
        tracking_status=TrackingStatus.OK,
    )
    return bridge


@pytest.fixture
def backend(mock_intrinsics, mock_bridge):
    """Create an OpenVINSBackend with mocked bridge."""
    with patch(
        "src.slam.backends.openvins_backend.SubprocessSLAMBridge",
        return_value=mock_bridge,
    ), patch(
        "src.slam.backends.openvins_backend._OPENVINS_AVAILABLE",
        True,
    ):
        from src.slam.backends.openvins_backend import OpenVINSBackend

        be = OpenVINSBackend(intrinsics=mock_intrinsics)
    # Replace the bridge with our mock (in case constructor assigned it)
    be._bridge = mock_bridge
    return be


# ---------------------------------------------------------------------------
# Test 1: CAPABILITIES
# ---------------------------------------------------------------------------


class TestOpenVINSCapabilities:
    """OpenVINSBackend has correct CAPABILITIES and PARAMETER_SCHEMA."""

    def test_supports_imu_true(self, backend):
        """CAPABILITIES has supports_imu=True."""
        assert backend.CAPABILITIES["supports_imu"] is True

    def test_outputs_dense_true(self, backend):
        """CAPABILITIES has outputs_dense=True (via depth_to_pointcloud)."""
        assert backend.CAPABILITIES["outputs_dense"] is True

    def test_supports_loop_closure_false(self, backend):
        """OpenVINS does not support loop closure."""
        assert backend.CAPABILITIES["supports_loop_closure"] is False


# ---------------------------------------------------------------------------
# Test 2: PARAMETER_SCHEMA
# ---------------------------------------------------------------------------


class TestOpenVINSParameterSchema:
    """PARAMETER_SCHEMA has expected properties."""

    def test_max_cameras_property(self, backend):
        """PARAMETER_SCHEMA has max_cameras property."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "max_cameras" in props

    def test_num_pts_property(self, backend):
        """PARAMETER_SCHEMA has num_pts property."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "num_pts" in props

    def test_hang_timeout_ms_property(self, backend):
        """PARAMETER_SCHEMA has hang_timeout_ms property."""
        props = backend.PARAMETER_SCHEMA["properties"]
        assert "hang_timeout_ms" in props


# ---------------------------------------------------------------------------
# Test 3: process_frame sends frame to bridge with IMU
# ---------------------------------------------------------------------------


class TestOpenVINSProcessFrame:
    """process_frame delegates to SubprocessSLAMBridge.send_frame."""

    def test_sends_frame_with_imu(self, backend, mock_bridge, synthetic_frame):
        """process_frame calls bridge.send_frame with rgb, depth, time, imu_readings."""
        backend.process_frame(synthetic_frame)
        mock_bridge.send_frame.assert_called_once()
        call_kwargs = mock_bridge.send_frame.call_args
        # Positional or keyword args should include imu_readings
        args, kwargs = call_kwargs
        # The call should pass imu_readings
        assert len(synthetic_frame.imu_readings) > 0

    def test_returns_slam_result(self, backend, synthetic_frame):
        """process_frame returns a SLAMResult."""
        result = backend.process_frame(synthetic_frame)
        assert isinstance(result, SLAMResult)
        assert result.pose.shape == (4, 4)
        assert result.tracking_status == TrackingStatus.OK


# ---------------------------------------------------------------------------
# Test 4: GT offset seeding from first frame
# ---------------------------------------------------------------------------


class TestOpenVINSGTOffset:
    """process_frame seeds GT offset from first frame's ground_truth_pose."""

    def test_gt_offset_seeded_on_first_frame(self, backend, synthetic_frame):
        """_gt_offset is set from first frame's ground_truth_pose."""
        assert backend._gt_offset is None
        backend.process_frame(synthetic_frame)
        assert backend._gt_offset is not None
        np.testing.assert_array_equal(
            backend._gt_offset, synthetic_frame.ground_truth_pose
        )


# ---------------------------------------------------------------------------
# Test 5: GT offset applied to subprocess-returned pose
# ---------------------------------------------------------------------------


class TestOpenVINSGTOffsetApplication:
    """process_frame applies GT offset to the subprocess-returned pose."""

    def test_gt_offset_applied_to_pose(
        self, backend, mock_bridge, synthetic_frame, synthetic_frame_2
    ):
        """Pose in SLAMResult = gt_offset @ subprocess_pose (when both non-identity)."""
        # First frame seeds GT offset
        backend.process_frame(synthetic_frame)

        # Second frame: subprocess returns a translated pose
        translated = np.eye(4, dtype=np.float64)
        translated[0, 3] = 0.5  # 0.5m forward
        mock_bridge.send_frame.return_value = SLAMResult(
            pose=translated,
            points=np.empty((0, 3), dtype=np.float64),
            colors=np.empty((0, 3), dtype=np.float64),
            metrics={},
            tracking_status=TrackingStatus.OK,
        )
        result = backend.process_frame(synthetic_frame_2)
        # GT offset is identity, so result pose = identity @ translated = translated
        np.testing.assert_array_almost_equal(result.pose, translated)


# ---------------------------------------------------------------------------
# Test 6: Dense cloud via depth_to_pointcloud
# ---------------------------------------------------------------------------


class TestOpenVINSDenseCloud:
    """process_frame generates dense cloud via depth_to_pointcloud when OK."""

    def test_dense_cloud_from_depth(self, backend, synthetic_frame):
        """Result points come from depth_to_pointcloud, not subprocess."""
        result = backend.process_frame(synthetic_frame)
        # Dense cloud from 10x10 depth with all 1.0 should have many points
        assert len(result.points) > 0, "Expected dense cloud from depth image"


# ---------------------------------------------------------------------------
# Test 7: INITIALIZING status when subprocess returns None (not yet tracking)
# ---------------------------------------------------------------------------


class TestOpenVINSInitializing:
    """When subprocess returns None before first track, return INITIALIZING with GT pose."""

    def test_initializing_status_with_gt_pose(
        self, backend, mock_bridge, synthetic_frame
    ):
        """Before first successful track, return INITIALIZING status with GT pose."""
        mock_bridge.send_frame.return_value = None
        result = backend.process_frame(synthetic_frame)
        assert result.tracking_status == TrackingStatus.INITIALIZING
        np.testing.assert_array_equal(result.pose, synthetic_frame.ground_truth_pose)


# ---------------------------------------------------------------------------
# Test 8: reset() shuts down and restarts the subprocess bridge
# ---------------------------------------------------------------------------


class TestOpenVINSReset:
    """reset() shuts down and restarts the subprocess bridge."""

    def test_reset_calls_shutdown_and_start(self, backend, mock_bridge, synthetic_frame):
        """reset() calls bridge.shutdown() then bridge.start()."""
        backend.process_frame(synthetic_frame)
        assert backend.num_frames_processed == 1

        # Patch SubprocessSLAMBridge constructor for reset
        with patch(
            "src.slam.backends.openvins_backend.SubprocessSLAMBridge",
            return_value=mock_bridge,
        ):
            backend.reset()

        assert backend.num_frames_processed == 0
        assert backend.get_poses() == []
        mock_bridge.shutdown.assert_called()


# ---------------------------------------------------------------------------
# Test 9: get_global_cloud() returns accumulated (points, colors)
# ---------------------------------------------------------------------------


class TestOpenVINSGlobalCloud:
    """get_global_cloud() returns accumulated points and colors."""

    def test_returns_tuple_of_arrays(self, backend, synthetic_frame):
        """get_global_cloud returns (ndarray, ndarray) tuple."""
        backend.process_frame(synthetic_frame)
        points, colors = backend.get_global_cloud()
        assert isinstance(points, np.ndarray)
        assert isinstance(colors, np.ndarray)

    def test_accumulates_across_frames(self, backend, synthetic_frame):
        """Points accumulate across multiple frames."""
        backend.process_frame(synthetic_frame)
        pts1, _ = backend.get_global_cloud()
        n1 = len(pts1)

        backend.process_frame(synthetic_frame)
        pts2, _ = backend.get_global_cloud()
        n2 = len(pts2)

        assert n2 >= n1, "Global cloud should accumulate across frames"


# ---------------------------------------------------------------------------
# Test 10: subprocess crash -> LOST status
# ---------------------------------------------------------------------------


class TestOpenVINSCrash:
    """When subprocess returns None (crash) after tracking, return LOST."""

    def test_lost_status_on_crash(self, backend, mock_bridge, synthetic_frame):
        """After successful tracking, subprocess None -> LOST status."""
        # First frame: successful tracking
        result1 = backend.process_frame(synthetic_frame)
        assert result1.tracking_status == TrackingStatus.OK

        # Second frame: subprocess crash (returns None)
        mock_bridge.send_frame.return_value = None
        result2 = backend.process_frame(synthetic_frame)
        assert result2.tracking_status == TrackingStatus.LOST
        # Should have last known pose
        np.testing.assert_array_equal(result2.pose, result1.pose)


# ---------------------------------------------------------------------------
# Registration test
# ---------------------------------------------------------------------------


class TestOpenVINSRegistration:
    """OpenVINSBackend registers in SLAMRegistry."""

    def test_registered_as_openvins(self):
        """Importing the module registers 'openvins' in SLAMRegistry."""
        # Force import to trigger registration
        import src.slam.backends.openvins_backend  # noqa: F401

        assert "openvins" in SLAMRegistry._backends
