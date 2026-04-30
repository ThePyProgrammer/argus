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


import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.sensor_types import SensorFrame
from src.bridge.platforms.types import RobotCommand
from src.coordination.robot_instance import RobotInstance, RobotMapMessage
from src.bridge.multi_robot_config import MultiRobotConfig
from src.coordination.voronoi_partitioner import VoronoiPartitioner
from src.coordination.map_merger import MapMerger
from src.coordination.merge_protocol import MergeProtocol, RobotMapData
from src.coordination.merge_registry import MergeRegistry
from src.coordination.transport import pLCMTransport
from src.metrics.drift_metrics import compute_drift_metrics
from src.perception.types import Detections3D
# DetectorWorkerPool is attached by main.py's restart block (see Plan 02-09) —
# kept off module-scope imports to honor P9 (torch-free coordinator module).

if TYPE_CHECKING:
    from src.perception.worker_pool import DetectorWorkerPool
    from src.viz.multi_robot_viz import MultiRobotVisualizer


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
    detections_3d: Detections3D | None
    scene_description: dict | None
    platform: dict | None = None
    runtime_status: dict | None = None
    tracking_status: str = "ok"
    body_yaw: float = 0.0

    # -- dict-style compatibility helpers ----------------------------------

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)


@dataclass
class CoordinationResult:
    """Result of a multi-robot coordination run."""

    total_steps: int
    merge_count: int
    terminated_reason: str
    merged_voxel_count: int
    per_robot_voxels: dict[str, int] = field(default_factory=dict)

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
        merger: "MergeProtocol | MapMerger | None" = None,
        viz: "MultiRobotVisualizer | None" = None,
    ):
        self._bridge = bridge
        self._robots = robots
        self._config = config
        self._partitioner = partitioner or VoronoiPartitioner()
        if merger is not None:
            self._merger: Any = merger
        else:
            try:
                import src.coordination.merge_strategies  # noqa: F401
                self._merger = MergeRegistry.create()
            except (ImportError, ValueError):
                self._merger = MapMerger(
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

        # Detector pool is constructed by main.py's restart block (D-01, D-02):
        # __init__ starts with None; main.py attaches via
        # ``coordinator._detector_pool = ...`` after each reset_for_restart.
        # Coordinator treats it as a black box — it never constructs the pool.
        self._detector_pool: "DetectorWorkerPool | None" = None

        # Scene description disabled by default (heavy on CPU, requires libvips)
        # Enable with: coordinator._describer = SceneDescriber(...)
        self._describer = None

        # Web control flags (set via _command_handler from Argus interface)
        self._should_stop: bool = False
        self._paused: bool = False
        self._freeze_motion: bool = False  # set True to keep robots stationary

        # Restart state
        self._restart_requested: bool = False
        self._restart_positions: dict | None = None
        self._restarting: bool = False

        # Metrics feed counter (drift computed every 10 viz updates = 100 sim steps)
        self._viz_update_count: int = 0

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
        """Return the detector pool (or None) as the single detection surface.

        Phase 2 D-18 cutover: the legacy ``ObjectDetector`` is gone; the pool
        exposes ``submit(rid, frame, pose, ...)`` and ``latest(rid) -> Detections3D | None``.
        Callers must use the pool API, not the legacy ``get_detections``/
        ``submit_frame`` methods from Phase 1.
        """
        return self._detector_pool

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

    def set_viz(self, viz: "MultiRobotVisualizer | None") -> None:
        self._viz = viz
        # Phase 6 BLOCKER 2: best-effort early attach. If the bridge is not
        # yet started (common in run_web_mode: set_viz is called BEFORE
        # coordinator.run() invokes bridge.start()), ``mj_model`` / ``mj_data``
        # are None and this no-ops — run() will call the helper again after
        # bridge.start() so the extractor attaches on the first tick.
        self._attach_gt_extractor_if_possible()

    def _attach_gt_extractor_if_possible(self) -> None:
        """Attach the MuJoCo GT extractor on the streaming viz, if wired.

        Phase 6 BLOCKER 2 fix (revision 2026-04-15). Graceful no-op if:
          - no viz attached, or
          - viz lacks ``attach_gt_extractor`` (pre-Phase-6 visualizers), or
          - bridge has no ``mj_model`` / ``mj_data`` accessors yet (pre-start
            or older MultiBridge without the public properties), or
          - the YAML file does not exist in this checkout.

        ``attach_gt_extractor`` itself swallows ValueError / FileNotFoundError /
        OSError internally (Plan 08 WebStreamingViz) so a bad mapping file
        leaves ``gt_extractor`` as None without crashing coordinator boot —
        the UI GT panel renders N/A while live detection metrics continue.

        Called from two sites:
          - :meth:`set_viz` (early, optimistic — may be pre-bridge.start())
          - :meth:`run` (after ``self._bridge.start()``, guaranteed usable)
        Second call is idempotent when the first succeeded — Plan 08's
        ``attach_gt_extractor`` just reconstructs the extractor, and both
        calls resolve against the same live ``mj_data`` handle.
        """
        viz = self._viz
        if viz is None or not hasattr(viz, "attach_gt_extractor"):
            return
        # Already attached — skip the reconstruction work.
        if getattr(viz, "gt_extractor", None) is not None:
            return
        from pathlib import Path as _GTPath
        gt_yaml = _GTPath("data/scenes/scene_office1_gt.yaml")
        if not gt_yaml.exists():
            return
        if not (hasattr(self._bridge, "mj_model") and hasattr(self._bridge, "mj_data")):
            return
        mj_model = self._bridge.mj_model
        mj_data = self._bridge.mj_data
        if mj_model is None or mj_data is None:
            return

        viz.attach_gt_extractor(gt_yaml, mj_model, mj_data)
        if getattr(viz, "gt_extractor", None) is not None:
            logger.info(
                "GT extractor attached: %s (classes=%s)",
                gt_yaml,
                viz.gt_extractor.all_classes(),
            )
        else:
            logger.warning(
                "GT extractor attach attempted but extractor is None; "
                "GT metrics will render N/A (see attach_gt_extractor logs).",
            )

    def set_freeze_motion(self, freeze: bool) -> None:
        self._freeze_motion = freeze

    def request_stop(self) -> None:
        self._should_stop = True

    def reset_merger(self) -> None:
        """Clear the map merger's accumulated data."""
        if hasattr(self._merger, "reset"):
            self._merger.reset()
        else:
            self._merger.last_merged_voxels = np.empty((0, 3))

    def get_robot_status(self, rid: str) -> dict:
        """Return status data for a single robot (position, voxel count).

        Used by MCP server to avoid reaching through coordinator.robots.
        Returns safe defaults while a restart is in progress.
        """
        if self._restarting:
            return {"position": [0, 0, 0], "voxels": 0, "tracking_status": "ok"}
        robot = self._robots.get(rid)
        if robot is None:
            return {"position": [0, 0, 0], "voxels": 0, "tracking_status": "ok"}
        poses = robot.slam.get_poses()
        if poses:
            pos = poses[-1][:3, 3].tolist()
        else:
            pos = [0, 0, 0]
        tracking_status_str = getattr(robot.exploration, "last_tracking_status", "ok")
        return {
            "position": pos,
            "voxels": robot.octomap.num_occupied,
            "tracking_status": tracking_status_str,
        }

    def get_robot_coverage(self, rid: str) -> dict:
        """Return coverage data for a single robot (voxels, SLAM frames).

        Used by MCP server to avoid reaching through coordinator.robots.
        Returns safe defaults while a restart is in progress.
        """
        if self._restarting:
            return {"voxels": 0, "slam_frames": 0}
        robot = self._robots.get(rid)
        if robot is None:
            return {"voxels": 0, "slam_frames": 0}
        return {
            "voxels": robot.octomap.num_occupied,
            "slam_frames": robot.slam.num_frames_processed,
        }

    def reset_for_restart(self, bridge: MultiRobotBridge, robots: dict[str, RobotInstance]) -> None:
        """Reset coordinator state for a simulation restart.

        Detector-pool lifecycle (D-01, D-02): if a prior pool is attached, it is
        shut down here so its worker threads stop cleanly before main.py attaches
        a freshly constructed pool. Coordinator never constructs the pool itself.
        """
        # Shutdown any prior detector pool so old workers are joined before
        # main.py attaches a new pool (Plan 02-09 contract).
        if self._detector_pool is not None:
            try:
                self._detector_pool.shutdown()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("detector_pool.shutdown failed: %s", exc)
            self._detector_pool = None

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
        self._viz_update_count = 0

        # Capture baseline metrics from the ending session (for comparison display)
        if self._viz is not None and hasattr(self._viz, 'metrics_tracker'):
            self._viz.metrics_tracker.capture_baseline()
            self._viz.reset_metrics()

        # pLCM subscription state: latest received map data per robot
        self._latest_map_data: dict[str, RobotMapMessage] = {}
        self._subscribers: list[pLCMTransport] = []

    def _command_handler(self, command: dict) -> None:
        """Handle control commands from the Argus web interface.

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
        elif action == "velocity":
            robot_id = command.get("robot_id")
            if robot_id and robot_id in self._robots and hasattr(self._bridge, "set_command"):
                linear = command.get("linear", [0.0, 0.0])
                yaw_rate = command.get("yaw_rate", 0.0)
                self._bridge.set_command(robot_id, RobotCommand.velocity(linear, yaw_rate))
                logger.info("Command received: velocity %s linear=%s yaw=%.3f", robot_id, linear, yaw_rate)
        elif action == "stand":
            robot_id = command.get("robot_id")
            if robot_id and robot_id in self._robots and hasattr(self._bridge, "set_command"):
                self._bridge.set_command(robot_id, RobotCommand.stand())
                logger.info("Command received: stand %s", robot_id)
        elif action == "stop_robot":
            robot_id = command.get("robot_id")
            if robot_id and robot_id in self._robots and hasattr(self._bridge, "stop_robot"):
                self._bridge.stop_robot(robot_id)
                logger.info("Command received: stop_robot %s", robot_id)
        elif action == "recover_robot":
            robot_id = command.get("robot_id")
            if robot_id and robot_id in self._robots and hasattr(self._bridge, "recover_robot"):
                self._bridge.recover_robot(robot_id)
                logger.info("Command received: recover_robot %s", robot_id)
        elif action == "send_to":
            robot_id = command.get("robot_id")
            target = command.get("target")
            if robot_id and target and robot_id in self._robots:
                target_pos = np.array(target, dtype=np.float64)
                robot = self._robots[robot_id]
                # Get current pose for path planning
                poses = robot.slam.get_poses()
                if poses:
                    current_pos = poses[-1][:3, 3]
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
            grid_2d = project_voxels_to_2d(occupied, robot.exploration.frontier_resolution)
            frontiers = robot.exploration.frontier_detector.detect(
                occupied, grid_2d=grid_2d,
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
        # Phase 6 BLOCKER 2: bridge is now started → mj_model / mj_data are
        # populated. Retry the GT-extractor attach (no-op if already attached
        # or if the scene YAML is absent).
        self._attach_gt_extractor_if_possible()
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

                if hasattr(self._bridge, "get_runtime_status"):
                    runtime_status = self._bridge.get_runtime_status(rid)
                    if getattr(runtime_status, "disabled", False) is True:
                        if hasattr(self._bridge, "stop_robot"):
                            self._bridge.stop_robot(rid)
                        continue

                try:
                    # Build score function if partitioned
                    score_fn = None
                    if self._partitioned:
                        _poses = robot.slam.get_poses()
                        _current_pose = _poses[-1] if _poses else np.eye(4)
                        score_fn = lambda centroid, _rid=rid, _cp=_current_pose: (
                                self._partitioner.score_frontier_with_bias(
                                    centroid,
                                    _rid,
                                    _cp,
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

                if self._freeze_motion:
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
                    except Exception as e:
                        logger.debug("Viz merge skipped: %s", e)
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
            poses = robot.slam.get_poses()
            if poses:
                positions[rid] = poses[-1][:3, 3]
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
                grid_2d=grid_2d,
            )
            if frontiers:
                centroids = np.array([f.centroid for f in frontiers])
                if self._partitioner.should_repartition(rid, centroids, robot_ids):
                    self._compute_partition(robot_ids)
                    break

    def _merge_occupancy_maps(self, robot_ids: tuple[str, ...]) -> None:
        """Merge maps using data received via pLCM subscriptions.

        If the merger satisfies MergeProtocol, builds RobotMapData per robot
        and calls strategy.merge(). Otherwise falls back to legacy
        merge_from_voxels path for raw MapMerger instances.
        """
        if isinstance(self._merger, MergeProtocol):
            self._merge_via_protocol(robot_ids)
        else:
            self._legacy_merge(robot_ids)
        self._merge_count += 1

    def _merge_via_protocol(self, robot_ids: tuple[str, ...]) -> None:
        """Merge using MergeProtocol strategy with RobotMapData."""
        robot_data: dict[str, RobotMapData] = {}
        for rid in robot_ids:
            robot = self._robots.get(rid)
            if robot is None:
                continue

            poses = robot.slam.get_poses()
            cloud_pts, _ = robot.get_cloud_data()

            if rid in self._latest_map_data:
                current_voxels = self._latest_map_data[rid].occupied_voxels
            else:
                current_voxels = robot.octomap.get_occupied_voxels()

            frame_clouds = [cloud_pts] if len(cloud_pts) > 0 else []

            robot_data[rid] = RobotMapData(
                robot_id=rid,
                poses=poses,
                frame_clouds=frame_clouds,
                current_voxels=current_voxels,
            )

        if len(robot_data) >= 1:
            self._merger.merge(robot_data)

    def _legacy_merge(self, robot_ids: tuple[str, ...]) -> None:
        """Merge using legacy MapMerger.merge_from_voxels path."""
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
            combined = np.vstack(all_voxels)
            self._merger.merge_from_voxels(all_voxels[0], combined[len(all_voxels[0]):])
        elif len(all_voxels) == 1:
            self._merger.last_merged_voxels = all_voxels[0]

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

            # Submit frames for perception (background threads).
            # D-05: pool.submit receives the full SensorFrame (not rgb/depth split)
            # and is a silent no-op for unknown rids. Newest-wins semantics inside
            # the per-robot worker guarantee non-blocking hot-loop submit.
            detections_3d: Detections3D | None = None
            if self._detector_pool is not None:
                self._detector_pool.submit(rid, frames[rid], pose, slam_cloud=None)
                detections_3d = self._detector_pool.latest(rid)
            if self._describer is not None:
                self._describer.submit_frame(rid, frames[rid].rgb)

            scene_desc = None
            if self._describer is not None:
                desc = self._describer.get_description(rid)
                if desc is not None:
                    scene_desc = {
                        "text": desc.description,
                        "objects": desc.objects,
                    }

            # Get body yaw from bridge (actual MuJoCo heading)
            body_yaw = 0.0
            if hasattr(self._bridge, 'get_body_yaw'):
                body_yaw = self._bridge.get_body_yaw(rid)

            platform_payload = None
            if hasattr(self._bridge, "platform_metadata"):
                platform_metadata = self._bridge.platform_metadata
                if hasattr(platform_metadata, "to_wire"):
                    platform_payload = platform_metadata.to_wire()
            runtime_payload = None
            if hasattr(self._bridge, "get_runtime_status"):
                runtime_status = self._bridge.get_runtime_status(rid)
                if hasattr(runtime_status, "to_wire"):
                    runtime_payload = runtime_status.to_wire()

            robot_data[rid] = RobotVizData(
                frame=frames[rid],
                local_voxels=robot.get_occupied_voxels(),
                slam_cloud_pts=cloud_pts,
                slam_cloud_rgb=cloud_rgb,
                pose=pose,
                trajectory=robot.slam.get_poses(),
                coverage_pct=robot.exploration.last_coverage,
                detections_3d=detections_3d,
                scene_description=scene_desc,
                platform=platform_payload,
                runtime_status=runtime_payload,
                tracking_status=getattr(robot.exploration, "last_tracking_status", "ok"),
                body_yaw=body_yaw,
            )

        # --- Feed metrics into tracker ---
        if hasattr(self._viz, 'metrics_tracker'):
            tracker = self._viz.metrics_tracker
            self._viz_update_count += 1

            for rid in robot_ids:
                robot = self._robots[rid]
                # Access per-frame SLAM metrics stored by exploration loop
                slam_metrics_dict = getattr(robot.exploration, 'last_slam_metrics', {})
                tracking_str = robot_data[rid].tracking_status
                tracker.record_frame(rid, slam_metrics_dict, tracking_str)

            # Compute drift every 10 viz updates (= every 100 simulation steps)
            # This keeps the expensive evo computation from running too often
            if self._viz_update_count % 10 == 0:
                for rid in robot_ids:
                    robot = self._robots[rid]
                    slam_poses = robot.slam.get_poses()
                    if len(slam_poses) < 2:
                        continue
                    # Ground truth: use slam poses as both (drift will be 0 without GT)
                    # When GroundTruthCollector is wired to coordinator, use that instead
                    gt_poses = slam_poses  # placeholder -- real GT requires GroundTruthCollector
                    timestamps = list(range(len(slam_poses)))
                    try:
                        drift = compute_drift_metrics(
                            slam_poses=slam_poses[-50:],  # rolling window of last 50
                            gt_poses=gt_poses[-50:],
                            timestamps=timestamps[-50:],
                        )
                        tracker.record_drift(
                            rid,
                            ate_rmse=drift["ate_rmse"],
                            ate_mean=drift["ate_mean"],
                            rpe_rmse=drift["rpe_rmse"],
                            rpe_mean=drift["rpe_mean"],
                        )
                    except Exception:
                        pass  # drift computation can fail with insufficient data

        # ──────────────────────────────────────────────────────────────────
        # Phase 6 (DET-METRICS-01 / DET-METRICS-02): detection-metrics pump.
        # Runs once per robot per tick. Guarded by hasattr so pre-Phase-6 viz
        # objects no-op silently. sim_now uses sim clock per Pitfall 4.
        # ──────────────────────────────────────────────────────────────────
        if hasattr(self._viz, "detection_metrics_tracker") and self._detector_pool is not None:
            det_tracker = self._viz.detection_metrics_tracker
            det_export = self._viz.detection_export
            gt_extractor = self._viz.gt_extractor
            sim_now = float(frames[robot_ids[0]].sim_time)

            workers_map = self._detector_pool.workers_by_robot()
            for rid in robot_ids:
                worker = workers_map.get(rid)
                if worker is None:
                    continue
                latest = worker.latest()
                inspect = worker.inspect()
                backend_metrics = worker.detector.get_metrics()

                det_tracker.record_frame(
                    robot_id=rid,
                    sim_now=sim_now,
                    latest=latest,
                    inspect=inspect,
                    backend_metrics=backend_metrics,
                )

                if latest is not None:
                    items = getattr(latest, "items", None) or getattr(latest, "boxes", [])
                    for obb in items:
                        det_export.append(
                            obb,
                            robot_id=rid,
                            backend_id=backend_metrics.get("backend_id", "unknown"),
                            capture_timestamp=float(latest.capture_timestamp),
                        )
                        if gt_extractor is not None:
                            cls = getattr(obb, "class_name", "")
                            center = np.asarray(obb.center, dtype=np.float64).reshape(3)
                            # Consume match result via tracker.record_gt_match (Plan 04
                            # surface; SC#2 end-to-end delivery). match_detection returns
                            # (gid, err) where err is None if no match within gate_m.
                            _gid, err = gt_extractor.match_detection(cls, center, gate_m=1.0)
                            det_tracker.record_gt_match(
                                robot_id=rid,
                                class_name=cls,
                                center_err_m=err,
                                matched=(err is not None),
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
