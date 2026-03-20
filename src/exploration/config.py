"""Exploration configuration with all tunable parameters.

Centralizes thresholds, speeds, and limits for the autonomous exploration
loop. All values have sensible defaults suitable for SimWorld at 0.1m
voxel resolution.
"""

from dataclasses import dataclass


@dataclass
class ExplorationConfig:
    """Configuration for the autonomous exploration loop.

    Attributes are grouped by subsystem: re-evaluation triggers, navigation,
    termination, frontier detection, and coverage logging.
    """

    # Frontier re-evaluation triggers
    rescan_distance_m: float = 2.0       # re-evaluate when robot moves this far
    rescan_voxel_delta: int = 500         # re-evaluate when map grows by this many voxels

    # Navigation
    waypoint_arrival_threshold: float = 0.3   # tighter threshold for continuous gait
    linear_speed: float = 0.8  # office-safe speed (2.0 was too fast for furniture)
    angular_speed: float = 1.0
    path_simplify_interval: float = 0.5       # waypoints ~0.5m apart for smoother paths

    # Termination
    max_steps: int = 10000                # safety net step limit
    stuck_threshold_steps: int = 30       # faster stuck detection
    stuck_distance_m: float = 0.05        # minimum movement over threshold steps

    # Frontier detection
    voxel_resolution: float = 0.05        # must match OctoMapBuilder
    min_cluster_size: int = 5
    goal_strategy: str = "nearest"        # "nearest" or "largest"

    # Coverage and logging
    log_interval_steps: int = 50          # log every N steps
    z_min: float = -100.0                  # auto-adapt: ground plane filtered dynamically
    z_max: float = 100.0
    ground_filter: bool = True             # remove dominant ground plane from occupancy grid
