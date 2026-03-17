"""Shared test fixtures for the dimensional-applications test suite.

Provides mock sensor data, camera intrinsics, point clouds, and pose
sequences for use across all test modules.
"""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame


@pytest.fixture
def mock_sensor_frame() -> SensorFrame:
    """Return a SensorFrame with random 64x64 RGB, 64x64 depth, identity pose."""
    rng = np.random.default_rng(42)
    return SensorFrame(
        rgb=rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8),
        depth=rng.random((64, 64), dtype=np.float32) * 5.0,  # 0-5 meters
        ground_truth_pose=np.eye(4, dtype=np.float64),
        sim_time=0.0,
    )


@pytest.fixture
def mock_camera_intrinsics() -> CameraIntrinsics:
    """Return CameraIntrinsics for a 64x64 image with simple focal lengths."""
    return CameraIntrinsics(
        fx=32.0, fy=32.0, cx=32.0, cy=32.0, width=64, height=64
    )


@pytest.fixture
def sample_point_cloud() -> np.ndarray:
    """Return a (100, 3) random float64 point cloud."""
    rng = np.random.default_rng(42)
    return rng.random((100, 3), dtype=np.float64)


@pytest.fixture
def sample_poses() -> list[np.ndarray]:
    """Return a list of 10 random valid (4, 4) homogeneous transforms.

    Each transform has a valid rotation matrix (via scipy Rotation.random)
    and a random translation vector.
    """
    rng = np.random.default_rng(42)
    poses = []
    for _ in range(10):
        pose = np.eye(4, dtype=np.float64)
        pose[:3, :3] = Rotation.random(random_state=rng).as_matrix()
        pose[:3, 3] = rng.random(3) * 10.0  # random position 0-10m
        poses.append(pose)
    return poses
