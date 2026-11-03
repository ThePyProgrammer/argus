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


import logging
import time
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.slam.protocol import SLAMProtocol
    from src.slam.octomap_builder import OctoMapBuilder

from src.bridge.sensor_types import BridgeProtocol, SensorFrame


@dataclass
class StepMetrics:
    """Metrics returned from ExplorationLoop.step_once()."""

    frontiers: int
    coverage: float
    terminated: bool
    voxels: int
    rescan_triggered: bool
    error: str | None = None
from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import CoverageTracker, ExplorationResult
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.floor_filter import FloorFilter, FloorTracker
from src.exploration.goal_selector import GoalSelector
from src.exploration.occupancy_grid import project_voxels_to_2d
from src.exploration.path_planner import PathPlanner
from src.exploration.progress_monitor import ProgressMonitor
from src.exploration.skills.executor import SkillExecutionResult, SkillExecutor
from src.exploration.skills.library import create_default_skill_registry
from src.exploration.skills.recorder import SkillOutcomeRecorder
from src.exploration.skills.selector import GatedSkillSelector, SkillSelectorConfig
from src.exploration.skills.state import SkillStateEncoder
from src.exploration.skills.types import SkillOutcomeVector, SkillTermination
from src.control.waypoint_runner import WaypointRunner

logger = logging.getLogger(__name__)


class StuckRecovery:
    """Reverse-then-turn recovery when robot is physically stuck.

    When triggered: first reverses for a simulated-time interval to back away
    from the obstacle, then turns through a fixed angle with randomized direction.
    This gets the robot clear of furniture/walls before choosing a new heading.
    """

    def __init__(
        self,
        turn_angle: float = np.pi * 0.75,  # 135 degrees -- bigger turn to escape corners
        angular_speed: float = 1.5,
        reverse_speed: float = 1.0,  # faster reverse
        reverse_duration_s: float = 0.25,
        rng: np.random.Generator | None = None,
    ) -> None:
        self._turn_angle = turn_angle
        self._angular_speed = angular_speed
        self._reverse_speed = reverse_speed
        if any(not np.isfinite(v) or v <= 0 for v in
               (turn_angle, angular_speed, reverse_speed, reverse_duration_s)):
            raise ValueError("Recovery parameters must be finite and positive")
        self._reverse_duration_s = reverse_duration_s
        self._rng = rng
        self._remaining_turn: float = 0.0
        self._remaining_reverse: float = 0.0
        self._active: bool = False
        self._phase: str = "idle"  # "reverse" or "turn"

    def trigger(self) -> None:
        """Start a reverse-then-turn recovery."""
        self._remaining_reverse = self._reverse_duration_s
        direction = 1.0 if (self._rng.random() if self._rng is not None else np.random.random()) > 0.5 else -1.0
        self._remaining_turn = self._turn_angle * direction
        self._active = True
        self._phase = "reverse"

    def step(self, dt: float) -> tuple[float, float, float] | None:
        """Get recovery velocity command (vx, vy, omega), or None if complete.

        Returns:
            (vx, vy, omega) while recovery is active, None when done.
        """
        if not np.isfinite(dt) or dt <= 0:
            raise ValueError("Recovery interval must be finite and positive")
        if not self._active:
            return None

        if self._phase == "reverse":
            duration = min(dt, self._remaining_reverse)
            self._remaining_reverse = max(0.0, self._remaining_reverse - dt)
            if self._remaining_reverse <= 1e-12:
                self._phase = "turn"
            return (-self._reverse_speed * duration / dt, 0.0, 0.0)

        if abs(self._remaining_turn) <= 1e-12:
            self._active = False
            self._phase = "idle"
            return None
        # Scale the last command to the remaining angle, avoiding overshoot
        # and sign oscillation for coarse or irregular sensor intervals.
        turn = float(np.clip(self._remaining_turn / dt,
                             -self._angular_speed, self._angular_speed))
        self._remaining_turn -= turn * dt
        return (0.0, 0.0, turn)

    @property
    def is_active(self) -> bool:
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

    def __init__(
        self,
        bridge: BridgeProtocol,
        slam: "SLAMProtocol",
        octomap: "OctoMapBuilder",
        config: ExplorationConfig | None = None,
        streaming_viz: object | None = None,
        intrinsics: object | None = None,
        recovery_rng: np.random.Generator | None = None,
        frame_dt: float | None = None,
    ):
        self._bridge = bridge
        self._slam = slam
        self._octomap = octomap
        self._config = config or ExplorationConfig()
        self._streaming_viz = streaming_viz
        self._intrinsics = intrinsics
        self._floor_filter = FloorTracker(FloorFilter(
            camera_height_m=self._config.floor_camera_height_m,
            height_tolerance_m=self._config.floor_height_tolerance_m,
            distance_tolerance_m=self._config.floor_distance_tolerance_m,
        ))
        self._observed_floor_cells: set[tuple[int, int]] = set()

        self._frontier_detector = FrontierDetector(
            resolution=self._config.voxel_resolution,
            min_cluster_size=self._config.min_cluster_size,
        )
        self._goal_selector = GoalSelector(strategy=self._config.goal_strategy)
        self._path_planner = PathPlanner(clearance_radius=self._config.planning_radius(
            0., self._config.voxel_resolution))
        self._coverage_tracker = CoverageTracker(
            voxel_resolution=self._config.voxel_resolution,
        )

        # Per-step state (shared between run() and step_once())
        self._robot_positions: list[np.ndarray] = []
        self._current_waypoint_runner: WaypointRunner | None = None
        self._bootstrap_complete = False
        self._navigation_exhausted = False
        self._last_rescan_pos = np.zeros(3, dtype=np.float64)
        self._last_voxel_count = 0
        self._progress = ProgressMonitor(self._config.stuck_timeout_s,
                                         self._config.stuck_distance_m,
                                         self._config.stuck_angle_rad)
        self._last_command = (np.zeros(2), 0.0)
        self._stuck_recovery = StuckRecovery(
            rng=recovery_rng, reverse_duration_s=self._config.recovery_reverse_duration_s)
        if frame_dt is not None and (not np.isfinite(frame_dt) or frame_dt <= 0):
            raise ValueError("Frame interval must be finite and positive")
        self._frame_dt = frame_dt
        self._previous_sim_time: float | None = None
        self._planning_attempts: list[tuple[str, bool]] = []
        self._selection_latency_ms: list[float] = []
        self._planning_sequence = 0
        self._goal_id: str | None = None
        self._last_coverage = 0.0
        self._last_bbox_coverage = 0.0
        self._last_frontier_count = 0
        self.last_tracking_status: str = "ok"

        self._skill_registry = create_default_skill_registry() if self._config.skill_learning_enabled else None
        self._skill_selector = (
            GatedSkillSelector(
                SkillSelectorConfig(
                    min_confidence=self._config.skill_learning_min_confidence,
                    min_dwell_steps=self._config.skill_learning_min_dwell_steps,
                    max_failures_before_baseline=self._config.skill_learning_max_failures_before_baseline,
                )
            )
            if self._config.skill_learning_enabled
            else None
        )
        self._skill_executor = SkillExecutor() if self._config.skill_learning_enabled else None
        self._skill_state_encoder = SkillStateEncoder() if self._config.skill_learning_enabled else None
        self._skill_recorder = (
            SkillOutcomeRecorder(run_id="local", selector_version="gated-v1", skill_library_version="default-v1")
            if self._config.skill_learning_enabled
            else None
        )
        self._last_skill_trace_id: str | None = None

    @property
    def frontier_detector(self) -> FrontierDetector:
        return self._frontier_detector

    @property
    def measurement_state(self) -> dict:
        """Detached decision diagnostics; no evaluator state enters navigation."""
        return {"recovering": self._stuck_recovery.is_active,
                "navigation_exhausted": self._navigation_exhausted,
                "goal_id": self._goal_id if self._current_waypoint_runner is not None
                and not self._current_waypoint_runner.is_complete else None,
                "planning_attempts": tuple(self._planning_attempts),
                "selection_latency_ms": tuple(self._selection_latency_ms),
                "tracking_status": self.last_tracking_status}

    @property
    def slam_backend_type(self) -> type:
        return type(self._slam)

    @property
    def observed_floor_xy(self) -> np.ndarray:
        """Observed floor supports planning free space, never evaluation coverage."""
        cells = np.asarray(sorted(self._observed_floor_cells), dtype=float).reshape(-1, 2)
        return (cells + .5) * self._config.voxel_resolution

    def planning_grid(self, occupied=None):
        """Use the same observed obstacle/floor map for navigation and coordination."""
        return project_voxels_to_2d(
            self._octomap.get_occupied_voxels() if occupied is None else occupied,
            self._config.voxel_resolution, self._config.z_min, self._config.z_max,
            robot_positions=np.array(self._robot_positions), observed_free_xy=self.observed_floor_xy,
        )

    @property
    def frontier_resolution(self) -> float:
        return self._frontier_detector._resolution

    @property
    def last_coverage(self) -> float:
        return self._coverage_tracker._last_coverage

    @property
    def config(self) -> ExplorationConfig:
        return self._config

    def set_waypoint_target(self, waypoints: list[np.ndarray]) -> None:
        """Set a new waypoint sequence for the robot to follow."""
        self._current_waypoint_runner = WaypointRunner(
            waypoints,
            linear_speed=self._config.linear_speed,
            angular_speed=self._config.angular_speed,
            heading_tolerance_rad=self._config.forward_heading_tolerance_rad,
        )
        self._bootstrap_complete = True
        self._navigation_exhausted = False
        self._goal_id = ",".join(format(float(v), ".9g") for v in waypoints[-1])

    def skill_trace_jsonl(self) -> str:
        """Return skill-learning decision/outcome traces as JSONL when enabled."""
        if self._skill_recorder is None:
            return ""
        return self._skill_recorder.to_jsonl()

    # ------------------------------------------------------------------
    # Extracted helpers (called only from step_once)
    # ------------------------------------------------------------------

    def _update_slam(self, frame: SensorFrame) -> tuple[np.ndarray, np.ndarray]:
        """Process frame through SLAM and OctoMap.

        Returns:
            (pose, current_pos) -- 4x4 pose matrix and (3,) position vector.
        """
        result = self._slam.process_frame(frame)
        self.last_tracking_status: str = result.tracking_status.value
        self.last_slam_metrics: dict = result.metrics

        # Emit crash_fallback WS message when a subprocess backend returns LOST
        if (result.tracking_status.value == "lost"
                and hasattr(self._slam, '_bridge')
                and self._streaming_viz is not None
                and hasattr(self._streaming_viz, '_message_queue')):
            backend_name = type(self._slam).__name__
            self._streaming_viz._message_queue.append({
                "type": "crash_fallback",
                "payload": {
                    # Phase 2 (DET-MODELS-05): backward-compat default.
                    # Phase 5 (DET-MODELS-06) adds a "detector" emission path.
                    "subsystem": "slam",
                    "crashed_backend": backend_name,
                    "fallback_backend": "icp",
                },
            })

            # Actually swap to ICP backend so exploration continues
            try:
                from src.slam.registry import SLAMRegistry
                import src.slam.backends  # noqa: F401
                fallback_kwargs = {}
                if self._intrinsics is not None:
                    fallback_kwargs["intrinsics"] = self._intrinsics
                self._slam = SLAMRegistry.create("icp", **fallback_kwargs)
                logger.info("Swapped crashed %s to ICP fallback", backend_name)
            except Exception as exc:
                logger.error("Failed to create ICP fallback: %s", exc)

        pose = result.pose
        current_pos = pose[:3, 3].copy()

        # Insert this frame's cloud directly into OctoMap (not the global accumulator)
        if len(result.points) > 0:
            points = result.points
            if self._config.ground_filter:
                acquiring_floor = self._floor_filter.plane is None
                floor = self._floor_filter.mask(points, current_pos)
                if acquiring_floor and self._floor_filter.plane is not None:
                    normal, offset = self._floor_filter.plane
                    self._octomap.remove_plane_inliers(
                        normal, offset, self._config.floor_distance_tolerance_m)
                cells = np.unique(np.floor(points[floor, :2] / self._config.voxel_resolution).astype(int), axis=0)
                self._observed_floor_cells.update(map(tuple, cells))
                points = points[~floor]
            if len(points):
                self._octomap.insert_scan(points, current_pos)

        return pose, current_pos

    def _check_stuck(
        self, step: int, pose: np.ndarray, sim_time: float,
    ) -> tuple[bool, tuple[np.ndarray, float, StepMetrics] | None]:
        """Check commanded progress; recovery gets its own fresh time window."""
        if self._navigation_exhausted:
            # Includes scans that raised before step_once could record a stop
            # command. An invalid route must not trigger motion via recovery.
            self._progress.reset()
            self._last_command = (np.zeros(2), 0.0)
            return False, None
        if not self._stuck_recovery.is_active:
            if self._progress.update(pose, sim_time, *self._last_command):
                logger.warning("[Step %d] No commanded progress for %.2f s. Recovering.",
                               step, self._config.stuck_timeout_s)
                self._stuck_recovery.trigger()
                self._progress.reset()
                self._current_waypoint_runner = None
                self._goal_id = None

        if self._stuck_recovery.is_active:
            # A recovery cannot trigger on the first observation, so the actual
            # sensor interval is known before issuing its first command.
            recovery_cmd = self._stuck_recovery.step(self._frame_dt)
            if recovery_cmd is not None:
                vx, vy, omega = recovery_cmd
                linear = np.array([vx, vy], dtype=np.float64)
                self._last_command = (linear.copy(), omega)
                return False, (linear, omega, StepMetrics(
                    frontiers=self._last_frontier_count,
                    coverage=self._last_coverage,
                    terminated=False,
                    voxels=self._octomap.num_occupied,
                    rescan_triggered=False,
                ))
            logger.info("[Step %d] Recovery complete. Forcing frontier rescan.", step)
            self._progress.reset()
            self._last_command = (np.zeros(2), 0.0)
            self._current_waypoint_runner = None
            return True, None
        return False, None

    def _should_rescan(
        self, step: int, current_pos: np.ndarray, force_rescan: bool,
    ) -> bool:
        """Evaluate whether a frontier rescan should be triggered."""
        config = self._config

        # Don't rescan in first 30 steps -- drive forward to build initial
        # map data before frontier detection has enough to work with
        min_scan_step = 30
        should_rescan = force_rescan and step >= min_scan_step
        if not should_rescan and step >= min_scan_step:
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

        return should_rescan

    def _evaluate_frontiers(
        self,
        current_pos: np.ndarray,
        pose: np.ndarray,
        score_fn: Callable[[np.ndarray], float] | None,
    ) -> tuple[int, bool]:
        """Detect frontiers, select a goal, and plan a path.

        Returns:
            (frontier_count, terminated) -- number of frontiers found and
            whether exploration should terminate.
        """
        # A scan replaces the route. Invalidate it before any operation that
        # might fail, and stay idle unless this scan installs a valid new path.
        self._bootstrap_complete = True
        self._navigation_exhausted = True
        self._current_waypoint_runner = None
        self._goal_id = None
        config = self._config
        occupied = self._octomap.get_occupied_voxels()

        grid_2d = self.planning_grid(occupied)

        frontiers = self._frontier_detector.detect(
            occupied,
            grid_2d=grid_2d,
        )

        frontier_count = len(frontiers)
        terminated = False
        effective_score_fn = score_fn
        skill_execution: SkillExecutionResult | None = None
        selected_skill_id: str | None = None
        path: list[np.ndarray] | None = None

        if (self._skill_registry is not None
                and self._skill_selector is not None
                and self._skill_executor is not None
                and self._skill_state_encoder is not None
                and self._skill_recorder is not None):
            state = self._skill_state_encoder.encode(
                coverage_pct=self._last_coverage,
                previous_coverage_pct=self._last_coverage,
                robot_position=current_pos,
                frontiers=frontiers,
                is_stuck=self._stuck_recovery.is_active,
                no_progress_steps=self._progress.no_progress_steps,
                blocked_path_count=0,
                recent_skill_ids=(),
                recent_termination_reasons=(),
            )
            proposals, gates = self._skill_registry.proposals_for(state)
            decision = self._skill_selector.select(state, proposals=proposals, gates=gates)
            selected_skill_id = decision.selected_skill_id
            self._last_skill_trace_id = self._skill_recorder.record_decision(
                scenario="local",
                seed=0,
                robot_ids=(state.robot_id,),
                state=state,
                gates=gates,
                decision=decision,
            )
            skill_execution = self._skill_executor.apply(decision)
            if not self._config.skill_learning_shadow_mode:
                effective_score_fn = skill_execution.score_fn if skill_execution.score_fn is not None else score_fn

        if not frontiers:
            terminated = True
        else:
            # Cluster centroids rank regions; actual frontier cells are targets.
            goal = None
            selection_start = time.perf_counter()
            reachable = self._path_planner.reachable_mask(current_pos, grid_2d)
            candidates = [candidate for candidate in self._goal_selector.navigation_candidates(
                frontiers, pose, grid_2d, reachable, effective_score_fn)
                if np.linalg.norm(candidate[:2] - current_pos[:2]) >= config.waypoint_arrival_threshold]
            self._selection_latency_ms.append((time.perf_counter() - selection_start) * 1000)
            for candidate in candidates:
                planned_path = self._path_planner.plan(current_pos, candidate, grid_2d)
                self._planning_sequence += 1
                self._planning_attempts.append((str(self._planning_sequence), planned_path is not None))
                if planned_path is not None:
                    goal, path = candidate, planned_path
                    break

            if goal is None or path is None:
                terminated = True
            else:
                self._goal_id = ",".join(format(float(v), ".9g") for v in goal)
                self._current_waypoint_runner = WaypointRunner(
                    path,
                    linear_speed=config.linear_speed,
                    angular_speed=config.angular_speed,
                    heading_tolerance_rad=config.forward_heading_tolerance_rad,
                    arrival_threshold=config.waypoint_arrival_threshold,
                )

        self._last_rescan_pos = current_pos.copy()
        self._last_voxel_count = self._octomap.num_occupied

        # Update coverage
        previous_coverage = self._last_coverage
        cov, bbox_cov = self._coverage_tracker.update(
            self._octomap.get_occupied_voxels(), frontier_count,
        )

        if self._skill_recorder is not None and self._last_skill_trace_id:
            path_succeeded = path is not None
            fallback_used = bool(skill_execution.fallback_used) if skill_execution is not None else True
            if fallback_used:
                termination = SkillTermination.BASELINE_FALLBACK
            elif path_succeeded:
                termination = SkillTermination.SUCCESS
            else:
                termination = SkillTermination.FAILURE

            outcome = SkillOutcomeVector(
                coverage_gain=max(0.0, cov - previous_coverage),
                frontier_delta=0.0,
                path_length=float(len(path)) if path is not None else 0.0,
                command_effort=0.0,
                safety_events=0,
                recovery_events=0,
                duplicate_coverage_delta=0.0,
                connectivity_delta=0.0,
                map_quality_delta=0.0,
                future_affordance_gain=0.0,
                termination=termination,
                fallback_used=fallback_used,
            )
            self._skill_recorder.record_outcome(self._last_skill_trace_id, outcome)
            if (self._skill_selector is not None
                    and selected_skill_id is not None
                    and selected_skill_id != "baseline"):
                self._skill_selector.record_termination(selected_skill_id, termination)

        self._last_coverage = cov
        self._last_bbox_coverage = bbox_cov
        self._last_frontier_count = frontier_count
        self._navigation_exhausted = terminated

        return frontier_count, terminated

    # ------------------------------------------------------------------
    # Main per-step entry point
    # ------------------------------------------------------------------

    def step_once(
        self,
        frame: SensorFrame,
        step: int,
        score_fn: Callable[[np.ndarray], float] | None = None,
    ) -> tuple[np.ndarray, float, StepMetrics]:
        """Process one exploration step without owning the bridge lifecycle.

        Multi-robot entry point: Coordinator calls this per-robot per-step.
        Does NOT call bridge.start/step/set_velocity (caller manages those).

        Returns:
            (linear_vel, angular_vel, metrics) -- velocity commands and
            StepMetrics. Coordinator uses metrics.rescan_triggered for merges.
        """
        config = self._config

        # a. Update SLAM and OctoMap
        self._planning_attempts = []
        self._selection_latency_ms = []
        if not np.isfinite(frame.sim_time):
            raise ValueError("Exploration sensor time must be finite")
        if self._previous_sim_time is not None:
            elapsed = frame.sim_time - self._previous_sim_time
            if elapsed <= 0:
                raise ValueError("Exploration sensor times must increase")
            self._frame_dt = elapsed
        self._previous_sim_time = frame.sim_time
        camera_pose, _ = self._update_slam(frame)
        # Mapping and floor filtering use the camera origin. Navigation uses
        # the body origin and forward axis, derived only from fixed calibration.
        pose = frame.body_pose_from_camera(camera_pose)
        current_pos = pose[:3, 3].copy()
        self._robot_positions.append(current_pos)
        # Enclose the fixed camera mount at every heading. Its 3D offset norm
        # also bounds horizontal reach when the body pitches or rolls.
        camera_offset = 0. if frame.body_from_camera is None else float(
            np.linalg.norm(frame.body_from_camera[:3, 3]))
        self._path_planner.set_clearance_radius(config.planning_radius(
            camera_offset, config.voxel_resolution))

        # b. Stuck detection and recovery
        force_rescan, early_return = self._check_stuck(step, pose, frame.sim_time)
        if early_return is not None:
            return early_return

        # c. Check re-evaluation trigger
        should_rescan = self._should_rescan(step, current_pos, force_rescan)

        # d. Frontier re-evaluation
        linear_vel = np.zeros(2, dtype=np.float64)
        angular_vel = 0.0
        terminated = self._navigation_exhausted
        frontier_count = self._last_frontier_count

        if should_rescan:
            frontier_count, terminated = self._evaluate_frontiers(
                current_pos, pose, score_fn,
            )

        # e. Execute navigation
        if (not terminated and self._current_waypoint_runner is not None
                and not self._current_waypoint_runner.is_complete):
            # A rescan already replaces the path above. Do not discard the
            # newly planned route on that same frame (including the first scan).
            linear_vel, angular_vel = self._current_waypoint_runner.get_velocity(pose)
        elif not terminated and not self._bootstrap_complete and self._current_waypoint_runner is None:
            # Drive forward only for initial map acquisition, never as a
            # fallback after an unsuccessful scan or an invalidated route.
            linear_vel = np.array([config.linear_speed * 0.5, 0.0], dtype=np.float64)
            angular_vel = 0.0

        # f. Periodic logging
        if step % config.log_interval_steps == 0:
            self._coverage_tracker.log(
                step, self._last_coverage, self._last_bbox_coverage,
                self._last_frontier_count,
            )

        # g. Attribute the next pose interval to this command.
        self._last_command = (linear_vel.copy(), float(angular_vel))

        metrics = StepMetrics(
            frontiers=frontier_count,
            coverage=self._last_coverage,
            terminated=terminated,
            voxels=self._octomap.num_occupied,
            rescan_triggered=should_rescan,
        )

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

            if metrics.terminated and step >= 50:
                # Determine specific termination reason from frontier state
                if metrics.frontiers == 0:
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
