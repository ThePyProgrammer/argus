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
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.sensor_types import SensorFrame
from src.coordination.robot_instance import RobotInstance, RobotMapMessage
from src.bridge.multi_robot_config import MultiRobotConfig


@dataclass
class RobotVizData:
    """Typed container for per-robot visualization data.

    Replaces the untyped 9-key dict previously built in _send_viz_update.
    Supports dict-style access (``data["pose"]``, ``data.get("pose")``)
    for backward compatibility with viz consumers.
    """

    frame: SensorFrame
    local_voxels: np.ndarray
    slam_cloud_pts: np.ndarray
    slam_cloud_rgb: np.ndarray
    pose: np.ndarray
    trajectory: list[np.ndarray]
    coverage_pct: float
    detections: list[dict]
    scene_description: dict | None

    # -- dict-style compatibility helpers ----------------------------------

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


@dataclass
class CoordinationResult:
    """Result of a multi-robot coordination run."""

    total_steps: int
    merge_count: int
    terminated_reason: str
    merged_voxel_count: int
    per_robot_voxels: dict[str, int] = field(default_factory=dict)
from src.coordination.voronoi_partitioner import VoronoiPartitioner
from src.coordination.map_merger import MapMerger

if TYPE_CHECKING:
    from src.viz.multi_robot_viz import MultiRobotVisualizer
from src.coordination.transport import pLCMTransport

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

        # Object detection (optional -- graceful if ultralytics not installed)
        self._detector = None
        try:
            from src.perception.detector import ObjectDetector, YOLO_AVAILABLE
            if YOLO_AVAILABLE:
                self._detector = ObjectDetector(device="cpu", max_fps=0.5)
                self._detector.start()
                logger.info("YOLO object detector started (CPU, 0.5 FPS)")
        except ImportError:
            pass

        # Scene description disabled by default (heavy on CPU, requires libvips)
        # Enable with: coordinator._describer = SceneDescriber(...)
        self._describer = None

        # Web control flags (set via _command_handler from C2 interface)
        self._should_stop: bool = False
        self._paused: bool = False
        self._static: bool = False  # set True to keep robots stationary

        # Restart state
        self._restart_requested: bool = False
        self._restart_positions: dict | None = None

        # pLCM subscription state
        self._latest_map_data: dict[str, RobotMapMessage] = {}
        self._subscribers: list = []

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def merge_count(self) -> int:
        return self._merge_count

    @property
    def robots(self) -> dict[str, RobotInstance]:
        return self._robots

    @property
    def detector(self) -> Any:
        return self._detector

    @property
    def describer(self) -> Any:
        return self._describer

    def handle_command(self, command: dict) -> None:
        """Public entry point for control commands."""
        self._command_handler(command)

    @property
    def restart_requested(self) -> bool:
        return self._restart_requested

    @property
    def restart_positions(self) -> dict | None:
        return self._restart_positions

    def set_viz(self, viz) -> None:
        self._viz = viz

    def set_static(self, static: bool) -> None:
        self._static = static

    def request_stop(self) -> None:
        self._should_stop = True

    def reset_merger(self) -> None:
        """Clear the map merger's accumulated data."""
        self._merger.last_merged_voxels = np.empty((0, 3))

    def reset_for_restart(self, bridge, robots: dict[str, RobotInstance]) -> None:
        """Reset coordinator state for a simulation restart."""
        self._bridge = bridge
        self._robots = robots
        self._should_stop = False
        self._paused = False
        self._partitioned = False
        self._step_count = 0
        self._merge_count = 0
        self._body_trajectories = {}
        self._restart_requested = False
        self._restart_positions = None

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
            {"action": "send_to", "robot_id": str, "target": [x, y]} -- navigate robot to target
            {"action": "restart", "positions": {rid: [x, y, z]}} -- restart with optional positions

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
                # Speed 1.0 = no delay, higher = faster (no delay), lower = add delay
                if value >= 1.0:
                    self._config.step_delay = 0.0
                else:
                    self._config.step_delay = (1.0 / value) * 0.01  # small delay for slow-mo
                logger.info("Command received: set_speed %.1f (delay=%.3fs)", value, self._config.step_delay)
        elif action == "send_to":
            robot_id = command.get("robot_id")
            target = command.get("target")
            if robot_id and target and robot_id in self._robots:
                target_pos = np.array(target, dtype=np.float64)
                robot = self._robots[robot_id]
                # Get current pose for path planning
                if robot.slam.slam_poses:
                    current_pos = robot.slam.slam_poses[-1][:3, 3]
                else:
                    current_pos = np.array(robot.spawn_transform[:3, 3])
                robot.exploration.set_waypoint_target([target_pos])
                logger.info("Command received: send %s to (%.1f, %.1f)", robot_id, target[0], target[1])
        elif action == "restart":
            positions = command.get("positions")
            if positions and isinstance(positions, dict):
                self._restart_positions = {
                    rid: tuple(pos) for rid, pos in positions.items()
                }
            else:
                self._restart_positions = None  # use current/default positions
            self._restart_requested = True
            self._should_stop = True
            logger.info("Command received: restart with positions=%s", self._restart_positions)

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
            grid_2d = project_voxels_to_2d(occupied, robot.exploration.frontier_resolution)
            frontiers = robot.exploration.frontier_detector.detect(
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

    def run(self, max_steps: int = 0) -> CoordinationResult:
        """Run the multi-robot coordination loop.

        Args:
            max_steps: Maximum steps. 0 = run forever (until Ctrl+C or stop command).
        """
        # Start pLCM subscriptions for robot data
        self._setup_subscriptions()
        # Start robot pLCM publishers
        for rid, robot in self._robots.items():
            robot.publisher.start()

        frames = self._bridge.start()
        robot_ids = tuple(self._robots.keys())
        terminated_reason = "stopped"

        step = 0
        while max_steps == 0 or step < max_steps:
            self._step_count = step
            step += 1

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
                    logger.warning("[Step %d] %s exploration error: %s", step, rid, e)
                    linear, angular = np.zeros(2), 0.0
                    from src.exploration.exploration_loop import StepMetrics
                    metrics = StepMetrics(
                        frontiers=0, coverage=0.0, terminated=True,
                        voxels=0, rescan_triggered=False,
                        error=str(e),
                    )

                if self._static:
                    self._bridge.set_velocity(rid, np.zeros(2), 0.0)
                else:
                    self._bridge.set_velocity(rid, linear, angular)

                # When rescan triggered: robot publishes map via pLCM
                if metrics.rescan_triggered:
                    any_rescan_triggered = True
                    robot.publish_map_state(
                        coverage_pct=metrics.coverage,
                    )

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
                self._merge_occupancy_maps(robot_ids)

            # Visualization update (every 10 frames)
            if step % 10 == 0 and self._viz is not None:
                if self._merge_count == 0:
                    try:
                        self._merge_occupancy_maps(robot_ids)
                    except Exception:
                        pass
                self._send_viz_update(robot_ids, frames)

        # Final merge
        self._merge_occupancy_maps(robot_ids)

        # Cleanup
        self._teardown_subscriptions()
        for rid, robot in self._robots.items():
            robot.publisher.stop()
        self._bridge.stop()

        return CoordinationResult(
            total_steps=self._step_count + 1,
            merge_count=self._merge_count,
            terminated_reason=terminated_reason,
            merged_voxel_count=len(self._merger.last_merged_voxels),
            per_robot_voxels={
                rid: self._robots[rid].octomap.num_occupied for rid in robot_ids
            },
        )

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
                grid_2d = project_voxels_to_2d(occupied, robot.exploration.frontier_resolution)
            except (ValueError, IndexError):
                continue
            frontiers = robot.exploration.frontier_detector.detect(
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

    def _merge_occupancy_maps(self, robot_ids: tuple[str, ...]) -> None:
        """Merge maps using data received via pLCM subscriptions.

        If pLCM data is available (from robot publish events), use the
        pre-transformed voxels from subscriptions. Falls back to direct
        OctoMapBuilder access if no pLCM data received yet (e.g., first merge).
        """
        # Collect all robot voxels and merge N-way
        all_voxels = []
        for rid in robot_ids:
            if rid in self._latest_map_data:
                v = self._latest_map_data[rid].occupied_voxels
                if len(v) > 0:
                    all_voxels.append(v)
            else:
                robot = self._robots.get(rid)
                if robot:
                    v = robot.octomap.get_occupied_voxels()
                    if len(v) > 0:
                        all_voxels.append(v)

        if len(all_voxels) >= 2:
            import numpy as np
            combined = np.vstack(all_voxels)
            self._merger.merge_from_voxels(all_voxels[0], combined[len(all_voxels[0]):])
        elif len(all_voxels) == 1:
            self._merger.last_merged_voxels = all_voxels[0]
        self._merge_count += 1

    def _send_viz_update(
        self,
        robot_ids: tuple[str, ...],
        frames: dict,
    ) -> None:
        """Assemble per-robot viz data and send to the visualizer."""
        robot_data = {}
        for rid in robot_ids:
            robot = self._robots[rid]
            pose = robot.get_pose()
            cloud_pts, cloud_rgb = robot.get_cloud_data()

            # Submit frames for perception (background threads)
            if self._detector is not None:
                self._detector.submit_frame(
                    rid, frames[rid].rgb, frames[rid].depth, pose,
                    slam_cloud=robot.slam.last_frame_cloud if hasattr(robot.slam, 'last_frame_cloud') else None,
                )
            if self._describer is not None:
                self._describer.submit_frame(rid, frames[rid].rgb)

            # Collect detections
            detections = []
            if self._detector is not None:
                detections = [
                    {"class": d.class_name, "confidence": d.confidence,
                     "bbox": list(d.bbox),
                     "pos_3d": d.center_3d.tolist() if d.center_3d is not None else None,
                     "depth": d.depth_m}
                    for d in self._detector.get_detections(rid)
                ]

            scene_desc = None
            if self._describer is not None:
                desc = self._describer.get_description(rid)
                if desc is not None:
                    scene_desc = {
                        "text": desc.description,
                        "objects": desc.objects,
                    }

            robot_data[rid] = RobotVizData(
                frame=frames[rid],
                local_voxels=robot.get_occupied_voxels(),
                slam_cloud_pts=cloud_pts,
                slam_cloud_rgb=cloud_rgb,
                pose=pose,
                trajectory=list(robot.slam.slam_poses),
                coverage_pct=robot.exploration.last_coverage,
                detections=detections,
                scene_description=scene_desc,
            )

        voronoi_mid, voronoi_dir = self._get_voronoi_geometry()
        frontier_cells = self._gather_frontier_cells(robot_ids)
        total_cov = sum(d.coverage_pct for d in robot_data.values()) / len(robot_data)

        self._viz.update(
            merged_voxels=self._merger.last_merged_voxels,
            robot_data=robot_data,
            frontier_cells=frontier_cells,
            voronoi_midpoint=voronoi_mid,
            voronoi_direction=voronoi_dir,
            total_coverage=total_cov,
            merge_count=self._merge_count,
        )
