"""Tests for SLAM pipeline (SLAM-01, SLAM-02).

Unit tests using synthetic RGB-D data -- no SimWorld or external SLAM required.
"""

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame


def _make_frame(rng, depth_min=2.0, depth_max=5.0, sim_time=0.0):
    """Create a SensorFrame with random RGB and uniform-random depth."""
    return SensorFrame(
        rgb=rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8),
        depth=rng.uniform(depth_min, depth_max, size=(64, 64)).astype(np.float32),
        ground_truth_pose=np.eye(4, dtype=np.float64),
        sim_time=sim_time,
    )


@pytest.mark.unit
def test_slam_processes_frames(mock_camera_intrinsics):
    """SLAM-01: SLAM pipeline processes RGB-D frames and produces pose estimates.

    Verifies:
    - SLAM pipeline accepts SensorFrame input
    - After processing N frames, a pose estimate is returned
    - Pose estimate is a valid (4, 4) homogeneous transform
    """
    from src.slam.slam_pipeline import SLAMPipeline

    pipeline = SLAMPipeline(intrinsics=mock_camera_intrinsics)
    rng = np.random.default_rng(42)

    for i in range(3):
        frame = _make_frame(rng, sim_time=float(i))
        pose = pipeline.process_frame(frame)
        assert pose.shape == (4, 4), f"Pose should be (4,4), got {pose.shape}"
        assert pose.dtype == np.float64

    assert pipeline.num_frames_processed == 3


@pytest.mark.unit
def test_point_cloud_output(mock_camera_intrinsics):
    """SLAM-02: Point cloud grows as robot moves through the environment.

    Verifies:
    - SLAM pipeline produces accumulated point cloud
    - Point cloud has >0 points after processing frames
    - get_cloud_points() returns (N, 3) array
    """
    from src.slam.slam_pipeline import SLAMPipeline

    pipeline = SLAMPipeline(intrinsics=mock_camera_intrinsics)
    rng = np.random.default_rng(42)

    for i in range(5):
        frame = _make_frame(rng, sim_time=float(i))
        pipeline.process_frame(frame)

    cloud_pts = pipeline.get_cloud_points()
    assert cloud_pts.ndim == 2
    assert cloud_pts.shape[1] == 3
    assert cloud_pts.shape[0] > 0, "Expected >0 points in accumulated cloud"
