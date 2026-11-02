"""Exploration configuration with all tunable parameters.

Centralizes thresholds, speeds, and limits for the autonomous exploration
loop. All values have sensible defaults suitable for MuJoCo at 0.1m
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
    forward_heading_tolerance_rad: float = 0.25  # turn in place before forward travel
    path_simplify_interval: float = 0.5       # waypoints ~0.5m apart for smoother paths
    footprint_radius_m: float = 0.35     # Go2 platform's circular body/leg envelope
    camera_standoff_m: float = 0.15      # space beyond the fixed camera mount
    clearance_margin_m: float = 0.05     # additional planning allowance, not an error bound

    # Termination and mobility recovery
    max_steps: int = 10000                # safety net step limit
    stuck_timeout_s: float = 2.0          # simulation time without commanded progress
    stuck_distance_m: float = 0.05        # net planar displacement resets the timeout
    stuck_angle_rad: float = 0.1         # yaw progress for pure rotation commands
    recovery_reverse_duration_s: float = 0.25

    # Frontier detection
    voxel_resolution: float = 0.05        # must match OctoMapBuilder
    min_cluster_size: int = 5
    goal_strategy: str = "nearest"        # "nearest" or "largest"

    # Skill learning gate (disabled by default)
    skill_learning_enabled: bool = False
    skill_learning_shadow_mode: bool = False
    skill_learning_min_confidence: float = 0.6
    skill_learning_min_dwell_steps: int = 3
    skill_learning_max_failures_before_baseline: int = 3

    # Coverage and logging
    log_interval_steps: int = 50          # log every N steps
    z_min: float = -100.0                  # auto-adapt: ground plane filtered dynamically
    z_max: float = 100.0
    ground_filter: bool = True             # separate observed floor before accumulating scans
    floor_camera_height_m: float = 0.32    # upright Go2 camera calibration; no scene height oracle
    floor_height_tolerance_m: float = 0.04
    floor_distance_tolerance_m: float = 0.015

    def planning_radius(self, camera_offset_m: float, resolution_m: float) -> float:
        """All-heading footprint, camera stand-off, and cell raster allowance."""
        import math
        values = (self.footprint_radius_m, self.camera_standoff_m,
                  self.clearance_margin_m, camera_offset_m, resolution_m)
        if any(not math.isfinite(v) or v < 0 for v in values) or resolution_m == 0:
            raise ValueError("Clearance dimensions must be finite and nonnegative; resolution must be positive")
        # One half-diagonal for each of the occupied and traversed cells.
        return (max(self.footprint_radius_m, camera_offset_m + self.camera_standoff_m)
                + self.clearance_margin_m + math.sqrt(2) * resolution_m)
