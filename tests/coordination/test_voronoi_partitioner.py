"""Tests for VoronoiPartitioner perpendicular bisector partitioning.

Tests verify frontier assignment, region-biased scoring, and
repartition detection for the two-robot case.
"""

import numpy as np
import pytest

from src.coordination.voronoi_partitioner import VoronoiPartitioner


@pytest.fixture
def partitioner():
    """Return a VoronoiPartitioner with robots at (0,0) and (10,0)."""
    vp = VoronoiPartitioner(in_region_weight=2.0)
    vp.update_positions({
        "robot_a": np.array([0.0, 0.0, 0.3]),
        "robot_b": np.array([10.0, 0.0, 0.3]),
    })
    return vp


def test_assign_frontiers_near_robot_a(partitioner):
    """Frontier at (3,0,0) should be assigned to robot_a (closer to A side)."""
    centroids = np.array([[3.0, 0.0, 0.0]])
    assignments = partitioner.assign_frontiers(centroids)
    assert len(assignments["robot_a"]) == 1
    assert len(assignments["robot_b"]) == 0
    np.testing.assert_array_almost_equal(assignments["robot_a"][0], [3.0, 0.0, 0.0])


def test_assign_frontiers_near_robot_b(partitioner):
    """Frontier at (7,0,0) should be assigned to robot_b (closer to B side)."""
    centroids = np.array([[7.0, 0.0, 0.0]])
    assignments = partitioner.assign_frontiers(centroids)
    assert len(assignments["robot_a"]) == 0
    assert len(assignments["robot_b"]) == 1
    np.testing.assert_array_almost_equal(assignments["robot_b"][0], [7.0, 0.0, 0.0])


def test_assign_frontiers_on_bisector(partitioner):
    """Frontier exactly on bisector (5,0,0) assigned to robot_a (dot=0, not > 0)."""
    centroids = np.array([[5.0, 0.0, 0.0]])
    assignments = partitioner.assign_frontiers(centroids)
    # dot product = 0, mask_b = (0 > 0) = False, so assigned to robot_a
    assert len(assignments["robot_a"]) == 1
    assert len(assignments["robot_b"]) == 0


def test_assign_frontiers_multiple(partitioner):
    """Multiple frontiers distributed correctly across both regions."""
    centroids = np.array([
        [2.0, 1.0, 0.0],   # robot_a region
        [3.0, -1.0, 0.0],  # robot_a region
        [7.0, 2.0, 0.0],   # robot_b region
        [8.0, -1.0, 0.0],  # robot_b region
        [9.0, 0.0, 0.0],   # robot_b region
    ])
    assignments = partitioner.assign_frontiers(centroids)
    assert len(assignments["robot_a"]) == 2
    assert len(assignments["robot_b"]) == 3


def test_score_frontier_with_bias_in_region(partitioner):
    """In-region frontier scores higher than out-of-region at same distance."""
    robot_a_pose = np.eye(4)
    robot_a_pose[:3, 3] = [0.0, 0.0, 0.3]

    # Frontier in robot_a's region (x=3)
    in_region = np.array([3.0, 0.0, 0.0])
    # Frontier in robot_b's region at same distance (x=7 is 7m away, but we want same dist)
    # Put it at (-3, 0, 0) -- still in A's region. Use (7,0,0) for B region.
    out_region = np.array([7.0, 0.0, 0.0])

    score_in = partitioner.score_frontier_with_bias(in_region, "robot_a", robot_a_pose)
    score_out = partitioner.score_frontier_with_bias(out_region, "robot_a", robot_a_pose)

    # in_region frontier is closer AND has 2x bias, so definitely higher
    assert score_in > score_out


def test_score_frontier_with_bias_no_positions():
    """With no positions set, score is distance-only (no bias applied)."""
    vp = VoronoiPartitioner(in_region_weight=2.0)
    # Do NOT call update_positions

    robot_pose = np.eye(4)
    robot_pose[:3, 3] = [0.0, 0.0, 0.0]

    frontier = np.array([3.0, 0.0, 0.0])
    score = vp.score_frontier_with_bias(frontier, "robot_a", robot_pose)

    # Should be 1.0 / (3.0 + 1e-6) -- distance-only, no multiplier
    expected = 1.0 / (3.0 + 1e-6)
    assert abs(score - expected) < 1e-4


def test_should_repartition_no_frontiers_in_region(partitioner):
    """Returns True when robot has zero frontiers in its assigned region."""
    # All frontiers in robot_b's region
    centroids = np.array([
        [7.0, 0.0, 0.0],
        [8.0, 1.0, 0.0],
    ])
    assert partitioner.should_repartition("robot_a", centroids) is True


def test_should_repartition_has_frontiers_in_region(partitioner):
    """Returns False when robot still has frontiers in its region."""
    centroids = np.array([
        [3.0, 0.0, 0.0],  # in robot_a's region
        [7.0, 0.0, 0.0],  # in robot_b's region
    ])
    assert partitioner.should_repartition("robot_a", centroids) is False
    assert partitioner.should_repartition("robot_b", centroids) is False


def test_should_repartition_empty_frontiers(partitioner):
    """Returns True when frontier list is empty."""
    centroids = np.array([]).reshape(0, 3)
    assert partitioner.should_repartition("robot_a", centroids) is True
