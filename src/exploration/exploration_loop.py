"""Main autonomous exploration orchestrator.

Wires together frontier detection, goal selection, path planning, waypoint
navigation, SLAM, and OctoMap to drive a robot through an unknown
environment without human input.

The loop repeats: sense -> detect frontiers -> select goal -> plan path
-> navigate -> until no reachable frontiers remain or max steps reached.
"""

from __future__ import annotations

import logging

import numpy as np

from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import CoverageTracker, ExplorationResult
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.goal_selector import GoalSelector
from src.exploration.occupancy_grid import project_voxels_to_2d
from src.exploration.path_planner import PathPlanner
from src.control.waypoint_runner import WaypointRunner

logger = logging.getLogger(__name__)


class ExplorationLoop:
    """Autonomous exploration loop orchestrator.

    Manages the full exploration cycle: sense the environment via bridge/SLAM,
    detect frontiers, select goals, plan paths, and navigate until termination.

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

    def run(self) -> ExplorationResult:
        """Run the full autonomous exploration loop.

        Returns:
            ExplorationResult with final coverage metrics, step count,
            termination reason, and coverage history.
        """
        config = self._config
        frame = self._bridge.start()

        robot_positions: list[np.ndarray] = []
        current_waypoint_runner: WaypointRunner | None = None
        last_rescan_pos = np.zeros(3, dtype=np.float64)
        last_voxel_count = 0
        stuck_counter = 0
        last_position = np.zeros(3, dtype=np.float64)
        terminated_reason = "max_steps"

        # Coverage state for logging
        last_coverage = 0.0
        last_bbox_coverage = 0.0
        last_frontier_count = 0

        for step in range(config.max_steps):
            # ----------------------------------------------------------
            # a. Update SLAM and OctoMap
            # ----------------------------------------------------------
            pose = self._slam.process_frame(frame)
            current_pos = pose[:3, 3].copy()

            cloud_points = self._slam.get_cloud_points()
            if len(cloud_points) > 0:
                # Insert recent points (last batch)
                recent = cloud_points[-min(len(cloud_points), 500):]
                self._octomap.insert_scan(recent, current_pos)

            robot_positions.append(current_pos)

            # ----------------------------------------------------------
            # b. Stuck detection
            # ----------------------------------------------------------
            if step > 0:
                dist_moved = float(np.linalg.norm(current_pos - last_position))
                if dist_moved < config.stuck_distance_m:
                    stuck_counter += 1
                else:
                    stuck_counter = 0

            force_rescan = False
            if stuck_counter >= config.stuck_threshold_steps:
                logger.warning(
                    "[Step %d] Stuck detected (%d steps without movement). Forcing re-scan.",
                    step, stuck_counter,
                )
                force_rescan = True
                stuck_counter = 0
                current_waypoint_runner = None

            # ----------------------------------------------------------
            # c. Check re-evaluation trigger
            # ----------------------------------------------------------
            should_rescan = force_rescan
            if not should_rescan:
                dist_from_last_scan = float(np.linalg.norm(current_pos - last_rescan_pos))
                voxel_delta = self._octomap.num_occupied - last_voxel_count
                waypoint_done = (
                    current_waypoint_runner is None
                    or current_waypoint_runner.is_complete
                )

                if (dist_from_last_scan > config.rescan_distance_m
                        or voxel_delta > config.rescan_voxel_delta
                        or waypoint_done):
                    should_rescan = True

            # ----------------------------------------------------------
            # d. Frontier re-evaluation
            # ----------------------------------------------------------
            if should_rescan:
                occupied = self._octomap.get_occupied_voxels()
                frontiers = self._frontier_detector.detect(
                    occupied, np.array(robot_positions),
                )

                # Build 2D grid for path planning
                grid_2d = project_voxels_to_2d(
                    occupied,
                    config.voxel_resolution,
                    config.z_min,
                    config.z_max,
                )

                if not frontiers:
                    terminated_reason = "no_frontiers"
                    logger.info("[Step %d] No frontiers remaining. Exploration complete.", step)
                    break

                # Try to find a reachable frontier
                remaining = list(frontiers)
                goal = None
                path = None

                while remaining:
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

                    # Remove unreachable frontier and try next
                    remaining = [
                        f for f in remaining
                        if not np.allclose(f.centroid, candidate)
                    ]

                if goal is None or path is None:
                    terminated_reason = "all_unreachable"
                    logger.info(
                        "[Step %d] All frontiers unreachable. Exploration complete.", step,
                    )
                    break

                # Create waypoint runner for the planned path
                current_waypoint_runner = WaypointRunner(
                    path,
                    linear_speed=config.linear_speed,
                    angular_speed=config.angular_speed,
                    arrival_threshold=config.waypoint_arrival_threshold,
                )

                last_rescan_pos = current_pos.copy()
                last_voxel_count = self._octomap.num_occupied

                # Update coverage
                cov, bbox_cov = self._coverage_tracker.update(
                    occupied, len(frontiers),
                )
                last_coverage = cov
                last_bbox_coverage = bbox_cov
                last_frontier_count = len(frontiers)

            # ----------------------------------------------------------
            # e. Execute navigation
            # ----------------------------------------------------------
            if current_waypoint_runner is not None and not current_waypoint_runner.is_complete:
                linear, angular = current_waypoint_runner.get_velocity(pose)
                self._bridge.set_velocity(linear, angular)

            # ----------------------------------------------------------
            # f. Step simulation
            # ----------------------------------------------------------
            frame = self._bridge.step()

            # ----------------------------------------------------------
            # g. Periodic logging
            # ----------------------------------------------------------
            if step % config.log_interval_steps == 0:
                self._coverage_tracker.log(
                    step, last_coverage, last_bbox_coverage, last_frontier_count,
                )

            # ----------------------------------------------------------
            # h. Update last_position for stuck detection
            # ----------------------------------------------------------
            last_position = current_pos.copy()

        else:
            # Loop completed without break -- max_steps reached
            terminated_reason = "max_steps"
            logger.info("Max steps (%d) reached. Exploration terminated.", config.max_steps)

        return self._coverage_tracker.result(step + 1, terminated_reason)
