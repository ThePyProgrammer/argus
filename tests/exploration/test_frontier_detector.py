"""Tests for 2D occupancy grid frontier detection.

Verifies FrontierDetector identifies FREE cells adjacent to UNKNOWN cells,
clusters them via BFS, and filters by minimum cluster size.
"""

import numpy as np
import pytest

from src.exploration.frontier_detector import FrontierCluster, FrontierDetector
from src.exploration.occupancy_grid import OccupancyGrid2D, CELL_FREE, CELL_OCCUPIED, CELL_UNKNOWN


def _make_grid(grid_array: np.ndarray, resolution: float = 0.1) -> OccupancyGrid2D:
    """Create an OccupancyGrid2D from a 2D numpy array."""
    h, w = grid_array.shape
    return OccupancyGrid2D(
        grid=grid_array.astype(np.int8),
        resolution=resolution,
        origin=np.array([0.0, 0.0]),
        width=w,
        height=h,
    )


class TestFrontierDetector:
    """Tests for FrontierDetector.detect()."""

    def test_empty_voxels(self):
        """Empty voxel array returns empty frontier list."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        empty = np.empty((0, 3), dtype=np.float64)
        result = detector.detect(empty)
        assert result == []

    def test_all_unknown_no_frontiers(self):
        """Grid with only UNKNOWN cells has no frontiers (need FREE cells)."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        grid = _make_grid(np.full((10, 10), CELL_UNKNOWN))
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert result == []

    def test_all_free_no_frontiers(self):
        """Grid with only FREE cells has no frontiers (need UNKNOWN neighbors)."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        grid = _make_grid(np.full((10, 10), CELL_FREE))
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert result == []

    def test_free_unknown_boundary(self):
        """FREE cells adjacent to UNKNOWN cells are detected as frontiers."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        # Left half FREE, right half UNKNOWN
        g = np.full((10, 20), CELL_UNKNOWN, dtype=np.int8)
        g[:, :10] = CELL_FREE
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)

        assert len(result) >= 1
        # Frontier should be along the column 9 (last FREE column, adjacent to UNKNOWN)
        total_cells = sum(c.voxel_count for c in result)
        assert total_cells >= 5  # at least several cells along the boundary

    def test_occupied_not_frontier(self):
        """OCCUPIED cells adjacent to UNKNOWN are NOT frontiers."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        # Wall of OCCUPIED with UNKNOWN beyond -- no FREE cells at all
        g = np.full((10, 10), CELL_UNKNOWN, dtype=np.int8)
        g[4:6, :] = CELL_OCCUPIED  # wall across the middle
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert result == []

    def test_free_next_to_occupied_not_frontier(self):
        """FREE cells next to OCCUPIED (but not UNKNOWN) are NOT frontiers."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        g = np.full((10, 10), CELL_FREE, dtype=np.int8)
        g[5, 5] = CELL_OCCUPIED  # one obstacle in the middle
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert result == []  # no UNKNOWN cells means no frontiers

    def test_min_cluster_filter(self):
        """Small frontier clusters below min_cluster_size are filtered out."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=5)
        # Create a grid with a tiny FREE->UNKNOWN boundary (2 cells)
        g = np.full((10, 10), CELL_UNKNOWN, dtype=np.int8)
        g[5, 4:6] = CELL_FREE  # only 2 FREE cells adjacent to UNKNOWN
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert result == []  # 2 cells < min_cluster_size of 5

    def test_two_separate_frontiers(self):
        """Two disconnected FREE regions produce two frontier clusters."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        g = np.full((20, 20), CELL_UNKNOWN, dtype=np.int8)
        # Two FREE patches far apart
        g[2:5, 2:5] = CELL_FREE    # top-left patch
        g[15:18, 15:18] = CELL_FREE  # bottom-right patch
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert len(result) == 2

    def test_frontier_cluster_types(self):
        """FrontierCluster fields have correct types."""
        detector = FrontierDetector(resolution=0.1, min_cluster_size=3)
        g = np.full((10, 20), CELL_UNKNOWN, dtype=np.int8)
        g[:, :10] = CELL_FREE
        grid = _make_grid(g)
        result = detector.detect(np.zeros((1, 3)), grid_2d=grid)
        assert len(result) > 0
        cluster = result[0]
        assert isinstance(cluster, FrontierCluster)
        assert cluster.centroid.shape == (3,)
        assert cluster.centroid.dtype == np.float64
        assert isinstance(cluster.voxel_count, int)
        assert isinstance(cluster.voxels, np.ndarray)
