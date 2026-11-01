"""A cluster's geometric centroid does not certify its cells' reachability."""

import json
import xml.etree.ElementTree as ET

import numpy as np

from scripts.diagnose_exploration_planning import inspect_attempt
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.exploration.path_planner import PathPlanner


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
