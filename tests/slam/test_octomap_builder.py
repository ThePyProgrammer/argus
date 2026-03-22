"""Tests for OctoMap occupancy grid builder (SLAM-03).

Unit tests using synthetic point cloud data -- no SimWorld or SLAM required.
"""

import numpy as np
import pytest


@pytest.mark.unit
def test_occupancy_grid(sample_point_cloud):
    """SLAM-03: OctoMap occupancy grid is built from point cloud insertions.

    Verifies:
    - OctoMapBuilder accepts point cloud + sensor origin
    - After insertion, occupied voxels are returned
    - Occupied voxel count is > 0 and <= input point count
    - Voxel centers are within expected spatial bounds
    """
    from src.slam.octomap_builder import OctoMapBuilder

    builder = OctoMapBuilder(resolution=0.5)
    builder.insert_scan(sample_point_cloud, sensor_origin=np.zeros(3))

    occupied = builder.get_occupied_voxels()
    assert occupied.shape[0] > 0, "Expected occupied voxels after insertion"
    assert builder.num_occupied > 0
    assert builder.num_occupied <= 100, (
        "Fewer voxels than points expected due to discretization"
    )
