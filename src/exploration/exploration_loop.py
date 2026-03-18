"""Main autonomous exploration orchestrator.

Wires together frontier detection, goal selection, path planning, waypoint
navigation, SLAM, and OctoMap to drive a robot through an unknown
environment without human input.

The loop repeats: sense -> detect frontiers -> select goal -> plan path
-> navigate -> until no reachable frontiers remain or max steps reached.

Supports two modes:
- run(): Full autonomous loop for single-robot exploration.
- step_once(): Single-step mode for multi-robot coordination (Coordinator calls).
"""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np

from src.bridge.sensor_types import SensorFrame
from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import CoverageTracker, ExplorationResult
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.goal_selector import GoalSelector
from src.exploration.occupancy_grid import project_voxels_to_2d
from src.exploration.path_planner import PathPlanner
from src.control.waypoint_runner import WaypointRunner

logger = logging.getLogger(__name__)


class StuckRecovery:
    """Turn-in-place recovery when robot is physically stuck.

    When triggered, commands a 90-degree turn with randomized direction
    (left or right). The recovery runs for the required angular displacement,
    then completes and signals the caller to rescan frontiers.
    """

    def __init__(
        self, turn_angle: float = np.pi / 2, angular_speed: float = 1.0,
    ) -> None:
        self._turn_angle = turn_angle
        self._angular_speed = angular_speed
        self._remaining: float = 0.0
        self._active: bool = False

    def trigger(self) -> None:
        """Start a turn recovery. Randomizes direction (left/right)."""
        direction = 1.0 if np.random.random() > 0.5 else -1.0
        self._remaining = self._turn_angle * direction
        self._active = True

    def step(self, dt: float) -> tuple[float, float, float] | None:
        """Get recovery velocity command (vx, vy, omega), or None if complete.

        Returns:
            (vx, vy, omega) while recovery is active, None when done.
        """
        if not self._active:
            return None

        turn = np.sign(self._remaining) * self._angular_speed
        self._remaining -= turn * dt

        if abs(self._remaining) < 0.1:
            self._active = False
            return None

        return (0.0, 0.0, turn)  # zero linear, only angular

    @property
    def is_active(self) -> bool:
        """True while a recovery turn is in progress."""
        return self._active


class ExplorationLoop:
    """Autonomous exploration loop orchestrator.

    Manages the full exploration cycle: sense the environment via bridge/SLAM,
    detect frontiers, select goals, plan paths, and navigate until termination.

    Supports two operating modes:
    - run(): Full lifecycle -- calls bridge.start/step/set_velocity.
    - step_once(): Per-frame processing -- caller manages bridge lifecycle.

    Args:
        bridge: Simulation bridge providing start/step/set_velocity/stop.
        slam: SLAM pipeline for pose estimation and cloud accumulation.
        octomap: OctoMap builder for voxel occupancy tracking.
        config: Exploration configuration (uses defaults if None).
    """

    def __init__(self, bridge, slam, octomap, config: ExplorationConfig | None = None):
        self._bridge = bridge
        self._slam = slam
        self._octomap = octomap
        self._config = config or ExplorationConfig()

        self._frontier_detector = FrontierDetector(
            resolution=self._config.voxel_resolution,
            min_cluster_size=self._config.min_cluster_size,
        )
        self._goal_selector = GoalSelector(strategy=self._config.goal_strategy)
        self._path_planner = PathPlanner()
        self._coverage_tracker = CoverageTracker(
            voxel_resolution=self._config.voxel_resolution,
        )

        # Per-step state (shared between run() and step_once())
        self._robot_positions: list[np.ndarray] = []
        self._current_waypoint_runner: WaypointRunner | None = None
        self._last_rescan_pos = np.zeros(3, dtype=np.float64)
        self._last_voxel_count = 0
        self._stuck_counter = 0
        self._stuck_recovery = StuckRecovery()
        self._last_position = np.zeros(3, dtype=np.float64)
        self._last_coverage = 0.0
        self._last_bbox_coverage = 0.0
        self._last_frontier_count = 0

    def step_once(
        self,
        frame: SensorFrame,
        step: int,
        score_fn: Callable[[np.ndarray], float] | None = None,
    ) -> tuple[np.ndarray, float, dict]:
        """Process one exploration step without owning the bridge lifecycle.

        This is the multi-robot entry point. The Coordinator calls this per-robot
        per-step, providing the SensorFrame from the shared MultiRobotBridge.

        Does NOT call bridge.start(), bridge.step(), or bridge.set_velocity().
        The caller (Coordinator) manages those.

        Args:
            frame: Current sensor frame (from bridge.step()[robot_id]).
            step: Current global step count (for logging and stuck detection).
            score_fn: Optional frontier scoring function for Voronoi bias.

        Returns:
            (linear_vel, angular_vel, metrics) where:
                linear_vel: (2,) float64 velocity command
                angular_vel: float
                metrics: dict with keys:
                    "frontiers": int (number of frontier clusters detected)
                    "coverage": float (coverage percentage)
                    "terminated": bool (True if no frontiers remain)
                    "voxels": int (number of occupied voxels)
                    "rescan_triggered": bool -- True if this step triggered a
                        frontier rescan (distance or voxel-delta threshold met).
                        CRITICAL: Coordinator uses this to trigger map merge
                        per user decision (merge on same event as frontier rescan).
        """
        config = self._config

        # ----------------------------------------------------------
        # a. Update SLAM and OctoMap
        # ----------------------------------------------------------
        pose = self._slam.process_frame(frame)
        current_pos = pose[:3, 3].copy()

        cloud_points = self._slam.get_cloud_points()
        if len(cloud_points) > 0:
            recent = cloud_points[-min(len(cloud_points), 500):]
            self._octomap.insert_scan(recent, current_pos)

        self._robot_positions.append(current_pos)

        # ----------------------------------------------------------
        # b. Stuck detection
        # ----------------------------------------------------------
        if step > 0:
            dist_moved = float(np.linalg.norm(current_pos - self._last_position))
            if dist_moved < config.stuck_distance_m:
                self._stuck_counter += 1
            else:
                self._stuck_counter = 0

        force_rescan = False

        # If stuck recovery is active, execute recovery turn instead of normal logic
        if self._stuck_recovery.is_active:
            dt = 0.2  # approximate frame dt
            recovery_cmd = self._stuck_recovery.step(dt)
            if recovery_cmd is not None:
                vx, vy, omega = recovery_cmd
                return (
                    np.array([vx, vy], dtype=np.float64),
                    omega,
                    {
                        "frontiers": self._last_frontier_count,
                        "coverage": self._last_coverage,
                        "terminated": False,
                        "voxels": self._octomap.num_occupied,
                        "rescan_triggered": False,
                    },
                )
            else:
                # Recovery just completed -- force rescan for new frontier
                logger.info(
                    "[Step %d] Stuck recovery complete. Forcing frontier rescan.",
                    step,
                )
                self._current_waypoint_runner = None
                force_rescan = True

        if self._stuck_counter >= config.stuck_threshold_steps:
            logger.warning(
                "[Step %d] Stuck detected (%d steps). Triggering turn recovery.",
                step, self._stuck_counter,
            )
            self._stuck_recovery.trigger()
            self._stuck_counter = 0

        # ----------------------------------------------------------
        # c. Check re-evaluation trigger
        # ----------------------------------------------------------
        should_rescan = force_rescan
        if not should_rescan:
            dist_from_last_scan = float(np.linalg.norm(current_pos - self._last_rescan_pos))
            voxel_delta = self._octomap.num_occupied - self._last_voxel_count
            waypoint_done = (
                self._current_waypoint_runner is None
                or self._current_waypoint_runner.is_complete
            )

            if (dist_from_last_scan > config.rescan_distance_m
                    or voxel_delta > config.rescan_voxel_delta
                    or waypoint_done):
                should_rescan = True

        # ----------------------------------------------------------
        # d. Frontier re-evaluation
        # ----------------------------------------------------------
        linear_vel = np.zeros(2, dtype=np.float64)
        angular_vel = 0.0
        terminated = False
        frontier_count = self._last_frontier_count

        if should_rescan:
            occupied = self._octomap.get_occupied_voxels()

            grid_2d = project_voxels_to_2d(
                occupied,
                config.voxel_resolution,
                config.z_min,
                config.z_max,
                robot_positions=np.array(self._robot_positions),
            )

            frontiers = self._frontier_detector.detect(
                occupied, np.array(self._robot_positions),
                grid_2d=grid_2d,
            )

            frontier_count = len(frontiers)

            if not frontiers:
                terminated = True
            else:
                # Try to find a reachable frontier
                remaining = list(frontiers)
                goal = None
                path = None

                while remaining:
                    if score_fn is not None:
                        candidate = self._goal_selector.select_with_bias(
                            remaining, pose, score_fn,
                        )
                    else:
                        candidate = self._goal_selector.select(remaining, pose)
                    if candidate is None:
                        break

                    planned_path = self._path_planner.plan(
                        current_pos, candidate, grid_2d,
                    )
                    if planned_path is not None:
                        goal = candidate
                        path = planned_path
                        break

                    remaining = [
                        f for f in remaining
                        if not np.allclose(f.centroid, candidate)
                    ]

                if goal is None or path is None:
                    terminated = True
                else:
                    self._current_waypoint_runner = WaypointRunner(
                        path,
                        linear_speed=config.linear_speed,
                        angular_speed=config.angular_speed,
                        arrival_threshold=config.waypoint_arrival_threshold,
                    )

            self._last_rescan_pos = current_pos.copy()
            self._last_voxel_count = self._octomap.num_occupied

            # Update coverage
            cov, bbox_cov = self._coverage_tracker.update(
                self._octomap.get_occupied_voxels(), frontier_count,
            )
            self._last_coverage = cov
            self._last_bbox_coverage = bbox_cov
            self._last_frontier_count = frontier_count

        # ----------------------------------------------------------
        # e. Execute navigation
        # ----------------------------------------------------------
        if (self._current_waypoint_runner is not None
                and not self._current_waypoint_runner.is_complete):
            linear_vel, angular_vel = self._current_waypoint_runner.get_velocity(pose)
        elif self._current_waypoint_runner is None:
            # No waypoints yet (e.g., empty map during boot phase, or all
            # frontiers unreachable) -- drive forward to build initial map
            # instead of standing still. The coordinator decides when to
            # truly terminate; this just ensures the robot keeps moving.
            linear_vel = np.array([config.linear_speed * 0.5, 0.0], dtype=np.float64)
            angular_vel = 0.0

        # ----------------------------------------------------------
        # f. Periodic logging
        # ----------------------------------------------------------
        if step % config.log_interval_steps == 0:
            self._coverage_tracker.log(
                step, self._last_coverage, self._last_bbox_coverage,
                self._last_frontier_count,
            )

        # ----------------------------------------------------------
        # g. Update last_position for stuck detection
        # ----------------------------------------------------------
        self._last_position = current_pos.copy()

        metrics = {
            "frontiers": frontier_count,
            "coverage": self._last_coverage,
            "terminated": terminated,
            "voxels": self._octomap.num_occupied,
            "rescan_triggered": should_rescan,
        }

        return linear_vel, angular_vel, metrics

    def run(self) -> ExplorationResult:
        """Run the full autonomous exploration loop.

        Returns:
            ExplorationResult with final coverage metrics, step count,
            termination reason, and coverage history.
        """
        config = self._config
        frame = self._bridge.start()

        terminated_reason = "max_steps"

        for step in range(config.max_steps):
            linear_vel, angular_vel, metrics = self.step_once(frame, step)

            self._bridge.set_velocity(linear_vel, angular_vel)

            if metrics["terminated"]:
                # Determine specific termination reason from frontier state
                if metrics["frontiers"] == 0:
                    terminated_reason = "no_frontiers"
                else:
                    terminated_reason = "all_unreachable"
                break

            # Step simulation
            frame = self._bridge.step()

        else:
            # Loop completed without break -- max_steps reached
            terminated_reason = "max_steps"
            logger.info("Max steps (%d) reached. Exploration terminated.", config.max_steps)
            step = config.max_steps - 1

        return self._coverage_tracker.result(step + 1, terminated_reason)
