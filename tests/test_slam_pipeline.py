"""Tests for SLAM pipeline (SLAM-01, SLAM-02).

These are integration tests that require SLAM infrastructure to be set up.
Currently stubbed as pending implementation.
"""

import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_slam_processes_frames():
    """SLAM-01: RTAB-Map (or ICP odometry) processes RGB-D frames and produces pose.

    Verifies:
    - SLAM pipeline accepts SensorFrame input
    - After processing N frames, a pose estimate is returned
    - Pose estimate is a valid (4, 4) homogeneous transform
    """
    assert False, "pending"


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_point_cloud_output():
    """SLAM-02: Point cloud grows as robot moves through the environment.

    Verifies:
    - SLAM pipeline produces accumulated point cloud
    - Point cloud size increases as more frames are processed
    - Point cloud points are in world frame (transformed by SLAM poses)
    """
    assert False, "pending"
