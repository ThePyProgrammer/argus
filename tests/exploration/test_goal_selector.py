"""Tests for frontier goal selection.

Verifies GoalSelector ranks frontier clusters and returns the best
candidate based on strategy (nearest or largest).
"""

import numpy as np
import pytest

from src.exploration.frontier_detector import FrontierCluster
from src.exploration.goal_selector import GoalSelector


def _make_cluster(centroid: list, voxel_count: int) -> FrontierCluster:
    """Helper to create a FrontierCluster with given centroid and count."""
    c = np.array(centroid, dtype=np.float64)
    voxels = np.zeros((voxel_count, 3), dtype=int)
    return FrontierCluster(centroid=c, voxel_count=voxel_count, voxels=voxels)


def _make_pose(position: list) -> np.ndarray:
    """Helper to create a (4,4) homogeneous transform with given translation."""
    pose = np.eye(4, dtype=np.float64)
    pose[:3, 3] = position
    return pose


class TestGoalSelector:
    """Tests for GoalSelector.select()."""

    def test_empty_returns_none(self):
        """Empty frontier list returns None."""
        selector = GoalSelector(strategy="nearest")
        pose = _make_pose([0.0, 0.0, 0.0])
        result = selector.select([], pose)
        assert result is None

    def test_single_cluster(self):
        """Single cluster returns that cluster's centroid."""
        selector = GoalSelector(strategy="nearest")
        cluster = _make_cluster([5.0, 3.0, 1.0], voxel_count=50)
        pose = _make_pose([0.0, 0.0, 0.0])
        result = selector.select([cluster], pose)
        assert result is not None
        np.testing.assert_array_almost_equal(result, [5.0, 3.0, 1.0])

    def test_nearest_strategy(self):
        """Multiple clusters -> nearest-to-robot cluster is selected."""
        selector = GoalSelector(strategy="nearest")
        far_cluster = _make_cluster([10.0, 0.0, 0.0], voxel_count=100)
        near_cluster = _make_cluster([1.0, 0.0, 0.0], voxel_count=10)
        pose = _make_pose([0.0, 0.0, 0.0])

        result = selector.select([far_cluster, near_cluster], pose)
        assert result is not None
        np.testing.assert_array_almost_equal(result, [1.0, 0.0, 0.0])

    def test_largest_strategy(self):
        """Largest strategy picks cluster with most voxels."""
        selector = GoalSelector(strategy="largest")
        small_cluster = _make_cluster([1.0, 0.0, 0.0], voxel_count=10)
        large_cluster = _make_cluster([10.0, 0.0, 0.0], voxel_count=100)
        pose = _make_pose([0.0, 0.0, 0.0])

        result = selector.select([small_cluster, large_cluster], pose)
        assert result is not None
        np.testing.assert_array_almost_equal(result, [10.0, 0.0, 0.0])

    def test_returns_float64_array(self):
        """Selector returns centroid as (3,) float64 array."""
        selector = GoalSelector(strategy="nearest")
        cluster = _make_cluster([2.5, 3.5, 0.5], voxel_count=20)
        pose = _make_pose([0.0, 0.0, 0.0])

        result = selector.select([cluster], pose)
        assert result is not None
        assert result.shape == (3,)
        assert result.dtype == np.float64
