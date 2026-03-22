"""Tests for MapMerger voxel fusion, point cloud merge, and frame alignment.

Covers union (OR) merge logic, deduplication, empty-set edge cases,
point cloud downsampling, and spawn transform application.
"""

import numpy as np
import open3d as o3d
import pytest

from src.coordination.map_merger import MapMerger
from src.slam.octomap_builder import OctoMapBuilder


class TestMergeVoxels:
    """Tests for MapMerger.merge_voxels()."""

    def test_non_overlapping_union(self):
        """Two non-overlapping voxel sets return union of both (count = A + B)."""
        merger = MapMerger(resolution=0.1)
        voxels_a = np.array([[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.2, 0.0, 0.0]])
        voxels_b = np.array([[5.0, 0.0, 0.0], [5.1, 0.0, 0.0]])
        merged = merger.merge_voxels(voxels_a, voxels_b)
        assert len(merged) == 5

    def test_overlapping_deduplication(self):
        """Overlapping voxels are deduplicated: 50 + 50 with 10 shared -> 90."""
        merger = MapMerger(resolution=0.1)
        rng = np.random.default_rng(42)
        # 50 unique to A
        unique_a = rng.random((40, 3)) * 10.0
        # 50 unique to B
        unique_b = rng.random((40, 3)) * 10.0 + 20.0
        # 10 shared (snapped to grid so they deduplicate exactly)
        shared = np.round(rng.random((10, 3)) * 10.0 / 0.1) * 0.1

        voxels_a = np.vstack([unique_a, shared])
        voxels_b = np.vstack([unique_b, shared])
        merged = merger.merge_voxels(voxels_a, voxels_b)
        # Should be 40 + 40 + 10 = 90, not 100
        assert len(merged) == 90

    def test_one_empty_returns_other(self):
        """Merging with one empty set returns the other unchanged."""
        merger = MapMerger(resolution=0.1)
        voxels = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        empty = np.empty((0, 3), dtype=np.float64)

        merged_a = merger.merge_voxels(voxels, empty)
        assert len(merged_a) == 2
        np.testing.assert_array_equal(merged_a, voxels)

        merged_b = merger.merge_voxels(empty, voxels)
        assert len(merged_b) == 2
        np.testing.assert_array_equal(merged_b, voxels)

    def test_both_empty(self):
        """Merging two empty sets returns empty (0, 3) array."""
        merger = MapMerger(resolution=0.1)
        empty_a = np.empty((0, 3), dtype=np.float64)
        empty_b = np.empty((0, 3), dtype=np.float64)
        merged = merger.merge_voxels(empty_a, empty_b)
        assert merged.shape == (0, 3)


class TestMergePointClouds:
    """Tests for MapMerger.merge_point_clouds()."""

    def test_merged_cloud_downsampled(self):
        """Merged point cloud is voxel-downsampled; count <= sum of inputs."""
        merger = MapMerger(resolution=0.1)
        rng = np.random.default_rng(42)

        cloud_a = o3d.geometry.PointCloud()
        cloud_a.points = o3d.utility.Vector3dVector(rng.random((200, 3)))

        cloud_b = o3d.geometry.PointCloud()
        cloud_b.points = o3d.utility.Vector3dVector(rng.random((200, 3)))

        merged = merger.merge_point_clouds(cloud_a, cloud_b)
        assert len(merged.points) <= 400
        assert len(merged.points) > 0


class TestFrameAlignment:
    """Tests for spawn transform application."""

    def test_spawn_offset_transforms_voxels(self):
        """Robot_b spawn offset (10, 0, 0) transforms robot_b voxels by +10 in X."""
        transform_b = np.eye(4, dtype=np.float64)
        transform_b[:3, 3] = np.array([10.0, 0.0, 0.0])

        merger = MapMerger(
            resolution=0.1,
            spawn_transforms={"robot_b": transform_b},
        )

        voxels_a = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        voxels_b = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])

        # Apply transform to robot_b
        transformed_b = merger._apply_transform(voxels_b, "robot_b")
        np.testing.assert_allclose(transformed_b[0], [10.0, 0.0, 0.0])
        np.testing.assert_allclose(transformed_b[1], [11.0, 0.0, 0.0])

        # robot_a (no transform) should be unchanged
        transformed_a = merger._apply_transform(voxels_a, "robot_a")
        np.testing.assert_array_equal(transformed_a, voxels_a)


class TestMergeIntegration:
    """Integration test: merge two OctoMapBuilder instances."""

    def test_merge_two_octomaps(self):
        """merge() on two OctoMapBuilders returns (unified_voxels, merged_cloud)."""
        octo_a = OctoMapBuilder(resolution=0.1)
        octo_b = OctoMapBuilder(resolution=0.1)

        # Insert non-overlapping scans
        rng = np.random.default_rng(42)
        points_a = rng.random((50, 3)) * 2.0  # 0-2 meter cube
        points_b = rng.random((50, 3)) * 2.0 + np.array([10.0, 0.0, 0.0])

        octo_a.insert_scan(points_a, np.zeros(3))
        octo_b.insert_scan(points_b, np.array([10.0, 0.0, 0.0]))

        merger = MapMerger(resolution=0.1)
        unified_voxels, merged_cloud = merger.merge(octo_a, octo_b)

        # Should have voxels from both maps
        voxels_a_count = octo_a.num_occupied
        voxels_b_count = octo_b.num_occupied
        assert len(unified_voxels) > 0
        # Union should be <= sum (possible dedup at boundaries, but mostly non-overlapping)
        assert len(unified_voxels) <= voxels_a_count + voxels_b_count
        # merged_cloud should be an Open3D PointCloud
        assert isinstance(merged_cloud, o3d.geometry.PointCloud)
        assert len(merged_cloud.points) > 0
