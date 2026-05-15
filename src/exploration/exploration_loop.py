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
from src.exploration.goal_selector import GoalSelector
from src.exploration.occupancy_grid import project_voxels_to_2d
from src.exploration.path_planner import PathPlanner
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

    When triggered: first reverses for a set number of steps to back away
    from the obstacle, then turns 90 degrees with randomized direction.
    This gets the robot clear of furniture/walls before choosing a new heading.
    """

    def __init__(
        self,
        turn_angle: float = np.pi * 0.75,  # 135 degrees -- bigger turn to escape corners
        angular_speed: float = 1.5,
        reverse_speed: float = 1.0,  # faster reverse
        reverse_steps: int = 25,     # longer reverse to clear obstacles
    ) -> None:
        self._turn_angle = turn_angle
        self._angular_speed = angular_speed
        self._reverse_speed = reverse_speed
        self._reverse_steps = reverse_steps
        self._remaining_turn: float = 0.0
        self._remaining_reverse: int = 0
        self._active: bool = False
        self._phase: str = "idle"  # "reverse" or "turn"

    def trigger(self) -> None:
        """Start a reverse-then-turn recovery."""
        self._remaining_reverse = self._reverse_steps
        direction = 1.0 if np.random.random() > 0.5 else -1.0
        self._remaining_turn = self._turn_angle * direction
        self._active = True
        self._phase = "reverse"

    def step(self, dt: float) -> tuple[float, float, float] | None:
        """Get recovery velocity command (vx, vy, omega), or None if complete.

        Returns:
            (vx, vy, omega) while recovery is active, None when done.
        """
        if not self._active:
            return None

        if self._phase == "reverse":
            self._remaining_reverse -= 1
            if self._remaining_reverse <= 0:
                self._phase = "turn"
            return (-self._reverse_speed, 0.0, 0.0)  # reverse

        # Turn phase
        turn = np.sign(self._remaining_turn) * self._angular_speed
        self._remaining_turn -= turn * dt

        if abs(self._remaining_turn) < 0.1:
            self._active = False
            self._phase = "idle"
            return None

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
    ):
        self._bridge = bridge
        self._slam = slam
        self._octomap = octomap
        self._config = config or ExplorationConfig()
        self._streaming_viz = streaming_viz
        self._intrinsics = intrinsics

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
        )

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
            self._octomap.insert_scan(result.points, current_pos)

        self._robot_positions.append(current_pos)
        return pose, current_pos

    def _check_stuck(
        self, step: int, current_pos: np.ndarray,
    ) -> tuple[bool, tuple[np.ndarray, float, StepMetrics] | None]:
        """Run stuck detection and recovery logic.

        Returns:
            (force_rescan, early_return) where early_return is a full
            step_once return tuple when recovery is mid-execution, else None.
        """
        config = self._config

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
                early = (
                    np.array([vx, vy], dtype=np.float64),
                    omega,
                    StepMetrics(
                        frontiers=self._last_frontier_count,
                        coverage=self._last_coverage,
                        terminated=False,
                        voxels=self._octomap.num_occupied,
                        rescan_triggered=False,
                    ),
                )
                return False, early
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

        return force_rescan, None

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
        config = self._config
        occupied = self._octomap.get_occupied_voxels()

        grid_2d = project_voxels_to_2d(
            occupied,
            config.voxel_resolution,
            config.z_min,
            config.z_max,
            robot_positions=np.array(self._robot_positions),
        )

        frontiers = self._frontier_detector.detect(
            occupied,
            grid_2d=grid_2d,
        )

        frontier_count = len(frontiers)
        terminated = False
        effective_score_fn = score_fn
        skill_execution: SkillExecutionResult | None = None

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
                no_progress_steps=self._stuck_counter,
                blocked_path_count=0,
                recent_skill_ids=(),
                recent_termination_reasons=(),
            )
            proposals, gates = self._skill_registry.proposals_for(state)
            decision = self._skill_selector.select(state, proposals=proposals, gates=gates)
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
            # Try to find a reachable frontier
            remaining = list(frontiers)
            goal = None
            path = None

            while remaining:
                if effective_score_fn is not None:
                    candidate = self._goal_selector.select_with_bias(
                        remaining, pose, effective_score_fn,
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
        previous_coverage = self._last_coverage
        cov, bbox_cov = self._coverage_tracker.update(
            self._octomap.get_occupied_voxels(), frontier_count,
        )

        if self._skill_recorder is not None and self._last_skill_trace_id:
            path_succeeded = path is not None if frontiers else False
            fallback_used = bool(skill_execution.fallback_used) if skill_execution is not None else not path_succeeded
            self._skill_recorder.record_outcome(
                self._last_skill_trace_id,
                SkillOutcomeVector(
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
                    termination=SkillTermination.SUCCESS if path_succeeded else SkillTermination.BASELINE_FALLBACK,
                    fallback_used=fallback_used,
                ),
            )

        self._last_coverage = cov
        self._last_bbox_coverage = bbox_cov
        self._last_frontier_count = frontier_count

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
        pose, current_pos = self._update_slam(frame)

        # b. Stuck detection and recovery
        force_rescan, early_return = self._check_stuck(step, current_pos)
        if early_return is not None:
            return early_return

        # c. Check re-evaluation trigger
        should_rescan = self._should_rescan(step, current_pos, force_rescan)

        # d. Frontier re-evaluation
        linear_vel = np.zeros(2, dtype=np.float64)
        angular_vel = 0.0
        terminated = False
        frontier_count = self._last_frontier_count

        if should_rescan:
            frontier_count, terminated = self._evaluate_frontiers(
                current_pos, pose, score_fn,
            )

        # e. Execute navigation
        if (self._current_waypoint_runner is not None
                and not self._current_waypoint_runner.is_complete):
            # Mid-path replanning: check if upcoming path is still clear
            # every 10 steps using the occupancy grid (not depth camera)
            if step % 10 == 0 and should_rescan:
                # Path may be blocked by newly discovered obstacles
                # Force a rescan which will replan if needed
                self._current_waypoint_runner = None

            if self._current_waypoint_runner is not None:
                linear_vel, angular_vel = self._current_waypoint_runner.get_velocity(pose)
        elif self._current_waypoint_runner is None:
            # No waypoints yet -- just drive forward
            linear_vel = np.array([config.linear_speed * 0.5, 0.0], dtype=np.float64)
            angular_vel = 0.0

        # f. Periodic logging
        if step % config.log_interval_steps == 0:
            self._coverage_tracker.log(
                step, self._last_coverage, self._last_bbox_coverage,
                self._last_frontier_count,
            )

        # g. Update last_position for stuck detection
        self._last_position = current_pos.copy()

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
