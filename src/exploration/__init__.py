"""Autonomous exploration algorithms: frontier detection, goal selection, path planning.

Public API:
    FrontierDetector, FrontierCluster -- 3D frontier detection and clustering
    GoalSelector -- Frontier ranking and selection
    PathPlanner -- A* path planning on 2D occupancy grid
    OccupancyGrid2D, project_voxels_to_2d -- 2D grid projection from 3D voxels
    CoverageTracker, ExplorationResult -- Coverage metrics and result summary
    ExplorationLoop -- Main autonomous exploration orchestrator
    ExplorationConfig -- Configuration with all tunable parameters
"""

from src.exploration.frontier_detector import FrontierCluster, FrontierDetector
from src.exploration.goal_selector import GoalSelector
from src.exploration.path_planner import PathPlanner
from src.exploration.occupancy_grid import OccupancyGrid2D, project_voxels_to_2d
from src.exploration.coverage_tracker import CoverageTracker, ExplorationResult
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.config import ExplorationConfig

__all__ = [
    "FrontierDetector",
    "FrontierCluster",
    "GoalSelector",
    "PathPlanner",
    "OccupancyGrid2D",
    "project_voxels_to_2d",
    "CoverageTracker",
    "ExplorationResult",
    "ExplorationLoop",
    "ExplorationConfig",
]
