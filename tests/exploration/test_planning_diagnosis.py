"""A cluster's geometric centroid does not certify its cells' reachability."""

import json
import xml.etree.ElementTree as ET

import numpy as np

from scripts.diagnose_exploration_planning import inspect_attempt, inspect_frontier_state
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.exploration.path_planner import PathPlanner


def test_terminal_diagnosis_distinguishes_trapped_start_from_missing_frontiers(tmp_path):
    cells = np.full((21, 21), -1, dtype=np.int8)
    cells[4:17, 4:17] = 0
    cells[9:12, 9:12] = 100
    grid = OccupancyGrid2D(cells, .1, np.zeros(2), 21, 21)
    before = cells.copy()
    blocked = inspect_frontier_state(grid, np.array([1.05, 1.05, 0.]), tmp_path / "blocked")
    assert blocked["retained_frontier_cells"] > 0
    assert blocked["reason"] == "start_without_passable_neighbors"
    assert blocked["reachable_cells"] == 0
    available = inspect_frontier_state(grid, np.array([.55, .55, 0.]), tmp_path / "available")
    assert available["reason"] == "reachable_frontier_cells_available"
    assert available["reachable_frontier_cells"] > 0
    np.testing.assert_array_equal(cells, before)
    with np.load(tmp_path / "blocked" / "frontiers.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["grid"], cells)


def test_terminal_diagnosis_reports_cluster_filter_and_no_frontiers(tmp_path):
    cells = np.full((9, 9), -1, dtype=np.int8)
    cells[4, 4] = 0
    grid = OccupancyGrid2D(cells, .1, np.zeros(2), 9, 9)
    small = inspect_frontier_state(grid, np.array([.45, .45, 0.]), tmp_path / "small")
    assert small["reason"] == "clusters_below_minimum_size"
    assert small["raw_cluster_sizes"] == [1]
    cells[:] = 0
    empty = inspect_frontier_state(grid, np.array([.45, .45, 0.]), tmp_path / "empty")
    assert empty["reason"] == "no_frontier_cells"


def test_ring_frontier_has_reachable_cells_despite_occupied_centroid(tmp_path):
    cells = np.full((15, 15), -1, dtype=np.int8)
    cells[3:12, 3:12] = 0
    cells[6:9, 6:9] = 100
    grid = OccupancyGrid2D(cells, .1, np.zeros(2), 15, 15)
    clusters = FrontierDetector(min_cluster_size=3).detect(np.empty((0, 3)), grid_2d=grid)
    assert len(clusters) == 1
    start, goal = np.array([.35, .75, 0.]), clusters[0].centroid
    assert PathPlanner().plan(start, goal, grid) is None
    before = cells.copy()
    report = inspect_attempt({"grid": grid, "start": start, "goal": goal, "path_found": False,
                              "body": start, "camera": start, "robot_id": "probe",
                              "sim_time": .29, "min_cluster_size": 3}, tmp_path)
    assert report["goal_occupancy"] == 100
    assert not report["goal_is_frontier_cell"]
    assert report["selected_cluster_cells"] == report["reachable_selected_cluster_cells"] == 32
    assert report["alternative_path_waypoints"] > 0
    assert PathPlanner().plan(start, np.array(report["alternative_goal_world"]), grid) is not None
    np.testing.assert_array_equal(cells, before)
    assert json.loads((tmp_path / "diagnosis.json").read_text()) == report
    with np.load(tmp_path / "planning.npz", allow_pickle=False) as saved:
        np.testing.assert_array_equal(saved["grid"], before)
    assert ET.parse(tmp_path / "planning.svg").getroot().tag.endswith("svg")
