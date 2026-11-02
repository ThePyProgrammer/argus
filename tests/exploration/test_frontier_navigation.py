"""Navigate to cluster members, including when a cluster center is blocked."""

import numpy as np

from src.exploration.frontier_detector import FrontierCluster, FrontierDetector
from src.exploration.goal_selector import GoalSelector
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.exploration.path_planner import PathPlanner


def ring():
    cells = np.full((25, 25), -1, np.int8)
    cells[3:22, 3:22] = 0
    cells[9:16, 9:16] = 100
    grid = OccupancyGrid2D(cells, .1, np.zeros(2), 25, 25)
    pose = np.eye(4)
    pose[:3, 3] = [.55, 1.25, 0]
    clusters = FrontierDetector().detect(np.empty((0, 3)), grid)
    return grid, pose, clusters


def test_occupied_centroid_does_not_discard_reachable_ring():
    grid, pose, clusters = ring()
    planner, selector = PathPlanner(), GoalSelector()
    assert planner.plan(pose[:3, 3], clusters[0].centroid, grid) is None
    targets = list(selector.navigation_candidates(clusters, pose, grid, planner.reachable_mask(pose[:3, 3], grid)))
    assert len(targets) == clusters[0].voxel_count
    member_cells = {tuple(cell) for cell in clusters[0].voxels}
    assert all(grid.world_to_grid(target[:2]) in member_cells for target in targets)
    assert planner.plan(pose[:3, 3], targets[0], grid) is not None


def test_inflated_and_disconnected_members_are_not_targets():
    cells = np.zeros((12, 12), np.int8)
    cells[:, 6] = 100
    grid = OccupancyGrid2D(cells, .1, np.zeros(2), 12, 12)
    pose = np.eye(4)
    pose[:3, 3] = [.25, .55, 0]
    members = np.array([[5, 5], [5, 8], [8, 2]])  # Inflated, disconnected, reachable.
    cluster = FrontierCluster(np.array([.6, .6, 0]), 3, members)
    planner = PathPlanner()
    targets = list(GoalSelector().navigation_candidates([cluster], pose, grid, planner.reachable_mask(pose[:3, 3], grid)))
    assert len(targets) == 1
    np.testing.assert_allclose(targets[0], [.25, .85, 0])
    assert planner.plan(pose[:3, 3], targets[0], grid) is not None


def test_candidate_order_is_stable_when_cluster_members_are_reordered():
    grid, pose, clusters = ring()
    reachable = PathPlanner().reachable_mask(pose[:3, 3], grid)
    first = list(GoalSelector().navigation_candidates(clusters, pose, grid, reachable))
    clusters[0].voxels = clusters[0].voxels[::-1]
    second = list(GoalSelector().navigation_candidates(clusters, pose, grid, reachable))
    np.testing.assert_array_equal(first, second)


def test_updated_grid_invalidates_cached_clearance():
    grid, pose, _ = ring()
    planner = PathPlanner()
    before = planner.reachable_mask(pose[:3, 3], grid)
    assert before[5, 5]
    grid.grid[5, 5] = 100
    assert not planner.reachable_mask(pose[:3, 3], grid)[5, 5]
