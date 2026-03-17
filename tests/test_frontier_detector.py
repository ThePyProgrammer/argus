"""Tests for 3D voxel frontier detection.

Verifies FrontierDetector identifies boundary voxels between explored
and unexplored space, clusters them via BFS, and filters by minimum size.
"""

import numpy as np
import pytest

from src.exploration.frontier_detector import FrontierCluster, FrontierDetector


class TestFrontierDetector:
    """Tests for FrontierDetector.detect()."""

    def test_empty_voxels(self, mock_robot_positions):
        """Empty voxel array returns empty frontier list."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        empty = np.empty((0, 3), dtype=np.float64)
        result = detector.detect(empty, mock_robot_positions)
        assert result == []

    def test_single_voxel_below_min_cluster(self, mock_robot_positions):
        """Single voxel returns empty list (below min_cluster_size=5)."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        single = np.array([[0.5, 0.5, 0.5]], dtype=np.float64)
        result = detector.detect(single, mock_robot_positions)
        assert result == []

    def test_cube_shell_frontiers(self, mock_occupied_cube, mock_robot_positions):
        """10x10x10 cube: frontiers are only the shell voxels (have empty neighbors).

        Interior voxels (8x8x8 = 512) have all 26 neighbors occupied.
        Shell voxels = 1000 - 512 = 488 are frontiers.
        All shell voxels are 26-connected, so they form one cluster.
        """
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        result = detector.detect(mock_occupied_cube, mock_robot_positions)

        # Should get at least one cluster
        assert len(result) >= 1

        # Total frontier voxels across all clusters should be shell count
        total_frontier_voxels = sum(c.voxel_count for c in result)
        interior = 8 * 8 * 8  # 512 interior voxels
        expected_shell = 1000 - interior  # 488 shell voxels
        assert total_frontier_voxels == expected_shell

    def test_two_clusters(self, mock_two_blobs, mock_robot_positions):
        """Two separated voxel blobs produce two distinct clusters."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        result = detector.detect(mock_two_blobs, mock_robot_positions)

        # Two well-separated blobs should produce 2 clusters
        assert len(result) == 2

        # Each cluster should have frontier voxels
        for cluster in result:
            assert cluster.voxel_count >= 5

    def test_min_cluster_filter(self, mock_robot_positions):
        """min_cluster_size filtering removes small clusters.

        Create a small blob of 3 voxels -- should be filtered with min_cluster_size=5.
        """
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        small_blob = np.array([
            [0.0, 0.0, 0.0],
            [0.1, 0.0, 0.0],
            [0.2, 0.0, 0.0],
        ], dtype=np.float64)
        result = detector.detect(small_blob, mock_robot_positions)
        assert result == []

    def test_frontier_cluster_has_correct_types(self, mock_occupied_cube, mock_robot_positions):
        """FrontierCluster fields have correct numpy types."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        result = detector.detect(mock_occupied_cube, mock_robot_positions)
        assert len(result) > 0
        cluster = result[0]
        assert isinstance(cluster, FrontierCluster)
        assert cluster.centroid.shape == (3,)
        assert cluster.centroid.dtype == np.float64
        assert isinstance(cluster.voxel_count, int)
        assert isinstance(cluster.voxels, np.ndarray)
