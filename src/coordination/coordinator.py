"""Multi-robot exploration coordinator with pLCM-based data flow.

Orchestrates the full multi-robot exploration lifecycle:
1. Boot phase: Both robots explore freely
2. First partition: Compute Voronoi from current robot positions
3. Biased exploration: Each robot prioritizes frontiers in its Voronoi region
4. Re-partition: When one robot has zero frontiers in its region, recompute
5. Merge: On each frontier rescan event (per user decision -- same trigger
   as frontier rescan from Phase 2, NOT a fixed step interval)
6. Termination: Both robots have zero frontiers globally

Data flow (per user decision -- DimOS pLCM transport):
- Each RobotInstance publishes RobotMapMessage to /{robot_id}/occupancy
- Coordinator subscribes to all robot channels
- On rescan_triggered, robot publishes its map; Coordinator receives via
  pLCM callback and triggers merge using the latest received voxel data
- Partition assignment uses direct calls (allowed per CONTEXT.md hybrid model)
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.coordination.robot_instance import RobotInstance, RobotMapMessage
from src.coordination.multi_robot_config import MultiRobotConfig
from src.coordination.voronoi_partitioner import VoronoiPartitioner
from src.coordination.map_merger import MapMerger

if TYPE_CHECKING:
    from src.viz.multi_robot_viz import MultiRobotVisualizer
try:
    from dimos.core.transport import pLCMTransport
except (ImportError, OSError):
    try:
        # Fallback for local development with dimos as submodule
        from dimos.dimos.core.transport import pLCMTransport  # type: ignore[no-redef]
    except (ImportError, OSError):
        # Stub for testing environments where dimos is not available
        pLCMTransport = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


class Coordinator:
    """Orchestrates multi-robot exploration lifecycle.

    Manages boot phase -> partition -> biased exploration -> merge cycle.
    Map merge triggers on rescan events (per user decision -- same trigger
    as frontier rescan from Phase 2, NOT a fixed step interval).

    Args:
        bridge: MultiRobotBridge providing start/step/set_velocity/stop.
        robots: Dict mapping robot_id -> RobotInstance.
        config: MultiRobotConfig with spawn positions and boot phase length.
        partitioner: VoronoiPartitioner for frontier assignment (optional).
        merger: MapMerger for voxel fusion (optional).
        viz: MultiRobotVisualizer for dashboard display (optional).
    """

    def __init__(
        self,
        bridge: MultiRobotBridge,
        robots: dict[str, RobotInstance],
        config: MultiRobotConfig,
        partitioner: VoronoiPartitioner | None = None,
        merger: MapMerger | None = None,
        viz: Any = None,
    ):
        self._bridge = bridge
        self._robots = robots
        self._config = config
        self._partitioner = partitioner or VoronoiPartitioner()
        self._merger = merger or MapMerger(
            resolution=0.1,
            spawn_transforms={
                rid: robots[rid].spawn_transform for rid in robots
            },
        )
        self._viz = viz
        self._partitioned = False
        self._step_count = 0
        self._merge_count = 0
        self._body_trajectories: dict[str, list[np.ndarray]] = {}

        # Web control flags (set via _command_handler from C2 interface)
        self._should_stop: bool = False
        self._paused: bool = False
        self._static: bool = False  # set True to keep robots stationary

        # pLCM subscription state: latest received map data per robot
        self._latest_map_data: dict[str, RobotMapMessage] = {}
        self._subscribers: list[pLCMTransport] = []

    def _command_handler(self, command: dict) -> None:
        """Handle control commands from the C2 web interface.

        Supports:
            {"action": "stop"} -- terminate exploration
            {"action": "pause"} -- pause the coordination loop
            {"action": "resume"} -- resume after pause
            {"action": "set_speed", "value": N} -- set simulation speed

        Args:
            command: Dict with at least an "action" key.
        """
        action = command.get("action")
        if action == "stop":
            self._should_stop = True
            logger.info("Command received: stop")
        elif action == "pause":
            self._paused = True
            logger.info("Command received: pause")
        elif action == "resume":
            self._paused = False
            logger.info("Command received: resume")
        elif action == "set_speed":
            value = command.get("value", 1.0)
            if value > 0:
                self._config.step_delay = 1.0 / value
                logger.info("Command received: set_speed %.1f (delay=%.3fs)", value, self._config.step_delay)

    def _get_voronoi_geometry(self) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Extract Voronoi midpoint and direction for visualization."""
        positions = self._partitioner._robot_positions
        if len(positions) < 2:
            return None, None
        keys = list(positions.keys())
        pos_a = positions[keys[0]]
        pos_b = positions[keys[1]]
        midpoint = (pos_a + pos_b) / 2.0
        direction = pos_b - pos_a
        return midpoint, direction

    def _gather_frontier_cells(self, robot_ids: tuple[str, ...]) -> np.ndarray | None:
        """Gather frontier cells from all robots for heatmap visualization."""
        from src.exploration.occupancy_grid import project_voxels_to_2d
        all_cells = []
        for rid in robot_ids:
            robot = self._robots[rid]
            occupied = robot.octomap.get_occupied_voxels()
            if len(occupied) == 0:
                continue
            sensor_pos = robot.slam.slam_poses[-1][:3, 3] if robot.slam.slam_poses else np.zeros(3)
            grid_2d = project_voxels_to_2d(occupied, robot.exploration._frontier_detector._resolution)
            frontiers = robot.exploration._frontier_detector.detect(
                occupied, np.array([sensor_pos]), grid_2d=grid_2d,
            )
            for f in frontiers:
                # Convert grid (row, col) to world XY with z=0
                world_coords = np.column_stack([
                    grid_2d.origin[0] + (f.voxels[:, 1] + 0.5) * grid_2d.resolution,
                    grid_2d.origin[1] + (f.voxels[:, 0] + 0.5) * grid_2d.resolution,
                    np.zeros(len(f.voxels)),
                ])
                all_cells.append(world_coords)
        if all_cells:
            return np.concatenate(all_cells, axis=0)
        return None

    def _setup_subscriptions(self) -> None:
        """Subscribe to each robot's pLCM occupancy channel.

        Creates a pLCMTransport subscriber per robot that stores the
        latest RobotMapMessage in self._latest_map_data.
        """
        for rid in self._robots:
            transport = pLCMTransport(topic=f"/{rid}/occupancy")
            transport.start()

            def _on_map_msg(msg: RobotMapMessage, _rid: str = rid) -> None:
                self._latest_map_data[_rid] = msg

            transport.subscribe(_on_map_msg)
            self._subscribers.append(transport)

    def _teardown_subscriptions(self) -> None:
        """Stop all pLCM subscriber transports."""
        for transport in self._subscribers:
            transport.stop()
        self._subscribers.clear()

    def run(self, max_steps: int = 10000) -> dict:
        """Run the multi-robot coordination loop.

        Returns:
            dict with "total_steps", "merge_count", "terminated_reason",
            "merged_voxel_count", "per_robot_voxels"
        """
        # Start pLCM subscriptions for robot data
        self._setup_subscriptions()
        # Start robot pLCM publishers
        for rid, robot in self._robots.items():
            robot.publisher.start()

        frames = self._bridge.start()
        robot_ids = tuple(self._robots.keys())
        terminated_reason = "max_steps"

        for step in range(max_steps):
            self._step_count = step

            # Check web control flags
            if self._should_stop:
                terminated_reason = "user_stopped"
                break
            while self._paused:
                import time
                time.sleep(0.1)
                if self._should_stop:
                    break

            # Per-robot: run one exploration step
            all_terminated = True
            any_rescan_triggered = False

            for rid in robot_ids:
                robot = self._robots[rid]
                frame = frames[rid]

                try:
                    # Build score function if partitioned
                    score_fn = None
                    if self._partitioned:
                        score_fn = lambda centroid, _rid=rid: (
                            self._partitioner.score_frontier_with_bias(
                                centroid,
                                _rid,
                                robot.slam.slam_poses[-1] if robot.slam.slam_poses else np.eye(4),
                                robot_ids,
                            )
                        )

                    linear, angular, metrics = robot.exploration.step_once(
                        frame, step, score_fn=score_fn,
                    )
                except (IndexError, ValueError) as e:
                    logger.warning("[Step %d] %s: step_once error: %s", step, rid, e)
                    linear, angular = np.zeros(2), 0.0
                    metrics = {"terminated": False, "rescan_triggered": False, "coverage": 0.0}

                if self._static:
                    self._bridge.set_velocity(rid, np.zeros(2), 0.0)
                else:
                    self._bridge.set_velocity(rid, linear, angular)

                if not metrics.get("terminated", False):
                    all_terminated = False

                # When rescan triggered: robot publishes map via pLCM
                if metrics.get("rescan_triggered", False):
                    any_rescan_triggered = True
                    robot.publish_map_state(
                        coverage_pct=metrics.get("coverage", 0.0),
                    )

            # Never terminate early in multi-robot mode. The frontier
            # detection on flat/sparse scenes is unreliable for termination.
            # Run for full max_steps; user controls duration via CLI flag.
            all_terminated = False

            # Slow down for visualization
            if self._config.step_delay > 0:
                import time
                time.sleep(self._config.step_delay)

            # Step simulation (advances both robots)
            frames = self._bridge.step()

            # After boot phase: compute first Voronoi partition
            if not self._partitioned and step >= self._config.boot_phase_steps:
                self._compute_partition(robot_ids)

            # Check re-partition (direct call -- allowed per CONTEXT.md)
            if self._partitioned:
                self._check_repartition(robot_ids)

            # Merge maps -- triggered by rescan event (per user decision:
            # "Merge triggers on the same event as frontier rescan")
            # NOT step % 50 or any fixed interval
            if any_rescan_triggered:
                self._do_merge(robot_ids)

            # Visualization update (every 2 frames)
            if step % 2 == 0 and self._viz is not None:
                # Always merge for viz (ensures cloud updates after config switch)
                try:
                    self._do_merge(robot_ids)
                except Exception:
                    pass  # skip merge if OctoMaps are empty

                robot_data = {}
                for rid in robot_ids:
                    robot = self._robots[rid]
                    spawn_offset = robot.spawn_transform[:3, 3].copy()
                    spawn_offset[2] = 0.0  # only subtract X/Y, keep Z as-is

                    # Adjust pose: subtract spawn position
                    pose = robot.slam.slam_poses[-1].copy() if robot.slam.slam_poses else np.eye(4)
                    pose[:3, 3] -= spawn_offset

                    # Adjust trajectory: subtract spawn position from each pose
                    trajectory = []
                    for p in robot.slam.slam_poses:
                        adj = p.copy()
                        adj[:3, 3] -= spawn_offset
                        trajectory.append(adj)

                    # Adjust cloud points
                    cloud_pts = robot.slam.get_cloud_points()
                    if len(cloud_pts) > 0:
                        cloud_pts = cloud_pts - spawn_offset

                    # Adjust local voxels
                    local_voxels = robot.octomap.get_occupied_voxels()
                    if len(local_voxels) > 0:
                        local_voxels = local_voxels - spawn_offset

                    robot_data[rid] = {
                        "frame": frames[rid],
                        "local_voxels": local_voxels,
                        "slam_cloud_pts": cloud_pts,
                        "slam_cloud_rgb": robot.slam.get_cloud_colors(),
                        "pose": pose,
                        "trajectory": trajectory,
                        "coverage_pct": robot.exploration._coverage_tracker._last_coverage,
                    }
                voronoi_mid, voronoi_dir = self._get_voronoi_geometry()
                frontier_cells = self._gather_frontier_cells(robot_ids)
                total_cov = sum(d["coverage_pct"] for d in robot_data.values()) / len(robot_data)
                # Adjust merged voxels: subtract average spawn position
                merged = self._merger.last_merged_voxels
                if len(merged) > 0:
                    avg_spawn = np.mean(
                        [self._robots[rid].spawn_transform[:3, 3] for rid in robot_ids],
                        axis=0,
                    )
                    avg_spawn[2] = 0.0  # only subtract X/Y, keep Z as-is
                    merged = merged - avg_spawn

                self._viz.update(
                    merged_voxels=merged,
                    robot_data=robot_data,
                    frontier_cells=frontier_cells,
                    voronoi_midpoint=voronoi_mid,
                    voronoi_direction=voronoi_dir,
                    total_coverage=total_cov,
                    merge_count=self._merge_count,
                )

            if all_terminated:
                terminated_reason = "all_explored"
                break

        # Final merge
        self._do_merge(robot_ids)

        # Cleanup
        self._teardown_subscriptions()
        for rid, robot in self._robots.items():
            robot.publisher.stop()
        self._bridge.stop()

        return {
            "total_steps": self._step_count + 1,
            "merge_count": self._merge_count,
            "terminated_reason": terminated_reason,
            "merged_voxel_count": len(self._merger.last_merged_voxels),
            "per_robot_voxels": {
                rid: self._robots[rid].octomap.num_occupied for rid in robot_ids
            },
        }

    def _compute_partition(self, robot_ids: tuple[str, ...]) -> None:
        """Compute Voronoi partition from current robot positions (direct call)."""
        positions = {}
        for rid in robot_ids:
            robot = self._robots[rid]
            if robot.slam.slam_poses:
                positions[rid] = robot.slam.slam_poses[-1][:3, 3]
            else:
                positions[rid] = robot.spawn_transform[:3, 3]
        self._partitioner.update_positions(positions)
        self._partitioned = True

    def _check_repartition(self, robot_ids: tuple[str, ...]) -> None:
        """Check if any robot's region is exhausted and needs re-partition."""
        from src.exploration.occupancy_grid import project_voxels_to_2d
        for rid in robot_ids:
            robot = self._robots[rid]
            occupied = robot.octomap.get_occupied_voxels()
            if len(occupied) == 0:
                continue
            try:
                grid_2d = project_voxels_to_2d(occupied, robot.exploration._frontier_detector._resolution)
            except (ValueError, IndexError):
                continue
            frontiers = robot.exploration._frontier_detector.detect(
                occupied,
                np.array([robot.slam.slam_poses[-1][:3, 3]])
                if robot.slam.slam_poses
                else np.zeros((1, 3)),
                grid_2d=grid_2d,
            )
            if frontiers:
                centroids = np.array([f.centroid for f in frontiers])
                if self._partitioner.should_repartition(rid, centroids, robot_ids):
                    self._compute_partition(robot_ids)
                    break

    def _do_merge(self, robot_ids: tuple[str, ...]) -> None:
        """Merge maps using data received via pLCM subscriptions.

        If pLCM data is available (from robot publish events), use the
        pre-transformed voxels from subscriptions. Falls back to direct
        OctoMapBuilder access if no pLCM data received yet (e.g., first merge).
        """
        if len(self._latest_map_data) == len(robot_ids):
            # Use pLCM-received data (voxels already in world frame)
            voxels_a = self._latest_map_data[robot_ids[0]].occupied_voxels
            voxels_b = self._latest_map_data[robot_ids[1]].occupied_voxels
            self._merger.merge_from_voxels(voxels_a, voxels_b)
        else:
            # Fallback: direct access (e.g., final merge or before first publish)
            octo_a = self._robots[robot_ids[0]].octomap
            octo_b = self._robots[robot_ids[1]].octomap
            self._merger.merge(octo_a, octo_b, robot_ids[0], robot_ids[1])
        self._merge_count += 1
