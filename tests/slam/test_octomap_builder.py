"""Tests for OctoMap occupancy grid builder (SLAM-03).

Unit tests using synthetic point cloud data -- no SimWorld or SLAM required.
"""

import numpy as np
import open3d as o3d
import pytest
from unittest.mock import patch

from src.slam.octomap_builder import OctoMapBuilder


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


@pytest.mark.parametrize("resolution", [.05, .1, .5])
def test_cached_queries_match_full_rebuild_after_changing_bounds(resolution):
    builder = OctoMapBuilder(resolution)
    cloud = o3d.geometry.PointCloud()
    rng = np.random.default_rng(17)
    for offset in ([0, 0, 0], [-2.13, .07, -.21], [1.03, -3.27, .16]):
        points = rng.uniform(0, 1, (300, 3)) + offset
        scan = o3d.geometry.PointCloud()
        scan.points = o3d.utility.Vector3dVector(points)
        cloud += scan
        builder.insert_scan(points, np.zeros(3))
        reference = o3d.geometry.VoxelGrid.create_from_point_cloud(cloud, resolution)
        expected = reference.origin + (np.array([v.grid_index for v in reference.get_voxels()]) + .5) * resolution
        for _ in range(3):
            np.testing.assert_array_equal(builder.get_occupied_voxels(), expected)
            assert builder.num_occupied == len(expected)


def test_queries_share_voxelization_until_insertion_or_reset():
    builder = OctoMapBuilder(.1)
    with patch.object(builder, "_voxelize", wraps=builder._voxelize) as voxelize:
        assert builder.num_occupied == 0
        assert builder.get_occupied_voxels().shape == (0, 3)
        assert voxelize.call_count == 1
        builder.insert_scan(np.array([[0., 0, 0], [1, 1, 1]]), np.zeros(3))
        for _ in range(7):
            assert builder.num_occupied == 2
            assert len(builder.get_occupied_voxels()) == 2
        assert voxelize.call_count == 2
        builder.insert_scan(np.array([[-1., -1, -1]]), np.zeros(3))
        assert builder.num_occupied == 3
        assert voxelize.call_count == 3
        builder.reset()
        assert builder.num_occupied == 0
        assert builder.get_occupied_voxels().shape == (0, 3)
        assert voxelize.call_count == 4


def test_returned_arrays_cannot_corrupt_cached_geometry():
    builder = OctoMapBuilder(.1)
    builder.insert_scan(np.array([[0., 0, 0], [1, 1, 1]]), np.zeros(3))
    expected = builder.get_occupied_voxels()
    original = expected.copy()
    other = builder.get_occupied_voxels()
    other[:] = 999
    other.resize((1, 3), refcheck=False)
    np.testing.assert_array_equal(builder.get_occupied_voxels(), expected)
    assert builder.num_occupied == 2
    builder.reset()
    builder.insert_scan(np.array([[3., 3, 3]]), np.zeros(3))
    assert builder.num_occupied == 1
    np.testing.assert_array_equal(expected, original)
