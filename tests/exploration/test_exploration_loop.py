"""Integration tests for ExplorationLoop.

Uses mock bridge, SLAM, and OctoMap objects to test the full
detect-select-plan-navigate cycle with various termination conditions.
"""


import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame
from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import ExplorationResult
from src.exploration.exploration_loop import ExplorationLoop, StuckRecovery
from src.exploration.frontier_detector import FrontierCluster
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.slam.protocol import SLAMResult, TrackingStatus


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_sensor_frame(position: np.ndarray | None = None) -> SensorFrame:
    """Create a minimal SensorFrame with a given position."""
    pose = np.eye(4, dtype=np.float64)
    if position is not None:
        pose[:3, 3] = position
    return SensorFrame(
        rgb=np.zeros((4, 4, 3), dtype=np.uint8),
        depth=np.zeros((4, 4), dtype=np.float32),
        ground_truth_pose=pose,
        sim_time=0.0,
    )


class MockBridge:
    """Simulates MuJoCoBridge for testing."""

    def __init__(self, move_per_step: float = 0.1) -> None:
        self._step_count = 0
        self._move_per_step = move_per_step
        self._position = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        self._velocity_commands: list[tuple[np.ndarray, float]] = []

    def start(self) -> SensorFrame:
        self._step_count = 0
        frame = _make_sensor_frame(self._position.copy())
        frame.sim_time = self._step_count * .1
        return frame

    def step(self, action=None) -> SensorFrame:
        self._step_count += 1
        self._position[0] += self._move_per_step
        frame = _make_sensor_frame(self._position.copy())
        frame.sim_time = self._step_count * .1
        return frame

    def set_velocity(self, linear: np.ndarray, angular: float) -> None:
        self._velocity_commands.append((linear, angular))

    def stop(self) -> None:
        pass

    @property
    def step_count(self) -> int:
        return self._step_count


class MockSLAM:
    """Simulates SLAMProtocol for testing."""

    def __init__(self) -> None:
        self._frame_count = 0
        self._cloud_size = 100

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        self._frame_count += 1
        rng = np.random.default_rng(self._frame_count)
        points = rng.random((self._cloud_size, 3)) * 5.0
        colors = rng.random((self._cloud_size, 3))
        return SLAMResult(
            pose=frame.ground_truth_pose.copy(),
            points=points,
            colors=colors,
            metrics={},
            tracking_status=TrackingStatus.OK,
        )

    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(self._frame_count)
        pts = rng.random((self._cloud_size, 3)) * 5.0
        clr = rng.random((self._cloud_size, 3))
        return pts, clr

    def get_poses(self) -> list[np.ndarray]:
        return [np.eye(4, dtype=np.float64)] * self._frame_count

    @property
    def num_frames_processed(self) -> int:
        return self._frame_count


class MockOctoMap:
    """Simulates OctoMapBuilder for testing."""

    def __init__(self, initial_voxels: int = 200) -> None:
        self._voxel_count = initial_voxels
        self._insert_count = 0

    def insert_scan(self, points: np.ndarray, sensor_origin: np.ndarray) -> None:
        self._insert_count += 1
        self._voxel_count += 10

    def get_occupied_voxels(self) -> np.ndarray:
        rng = np.random.default_rng(self._voxel_count)
        return rng.random((self._voxel_count, 3)) * 5.0

    @property
    def num_occupied(self) -> int:
        return self._voxel_count


def _make_cluster(centroid: list[float], count: int = 10) -> FrontierCluster:
    """Create a FrontierCluster with given centroid."""
    return FrontierCluster(
        centroid=np.array(centroid, dtype=np.float64),
        voxel_count=count,
        voxels=np.tile([round(centroid[1] / .1), round(centroid[0] / .1)], (count, 1)),
    )


@pytest.fixture(autouse=True)
def policy_test_grid(monkeypatch):
    # These tests mock frontier detection and A*. Give their synthetic clusters
    # valid free cells; projection/clearance are tested independently.
    monkeypatch.setattr("src.exploration.exploration_loop.project_voxels_to_2d",
                        lambda *a, **kw: OccupancyGrid2D(np.zeros((128, 128), np.int8),
                                                       .1, np.array([-.05, -.05]), 128, 128))


def test_failed_cell_does_not_discard_other_cells_of_the_same_cluster():
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    cluster = FrontierCluster(np.array([2., 0., 0.]), 2, np.array([[0, 20], [0, 21]]))
    loop.frontier_detector.detect = lambda *a, **kw: [cluster]
    attempts = []
    def plan(start, goal, grid):
        attempts.append(goal.copy())
        return None if len(attempts) == 1 else [start, goal]
    loop._path_planner.plan = plan
    _, _, metrics = loop.step_once(_make_sensor_frame(), 30)
    assert len(attempts) == 2
    assert not metrics.terminated
    assert loop.measurement_state["planning_attempts"] == (("1", False), ("2", True))


@pytest.mark.parametrize("failure", ["no_frontiers", "no_candidates", "astar_failure"])
def test_failed_rescan_discards_route_and_stays_idle_until_success(failure, monkeypatch):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    cluster = _make_cluster([3., 0., 0.])
    detector = MagicMock(return_value=[cluster])
    planner = MagicMock(side_effect=lambda start, goal, grid: [start, goal])
    monkeypatch.setattr(loop.frontier_detector, "detect", detector)
    monkeypatch.setattr(loop._path_planner, "plan", planner)
    scan = MagicMock(return_value=True)
    monkeypatch.setattr(loop, "_should_rescan", scan)

    def advance(step):
        frame = _make_sensor_frame()
        frame.sim_time = step * .1
        return loop.step_once(frame, step)

    linear, _, metrics = advance(30)
    assert linear[0] > 0 and not metrics.terminated
    old_runner = loop._current_waypoint_runner
    if failure == "no_frontiers":
        detector.return_value = []
    elif failure == "no_candidates":
        detector.return_value = [_make_cluster([100., 100., 0.])]
    else:
        planner.side_effect = None
        planner.return_value = None

    linear, angular, metrics = advance(31)
    np.testing.assert_array_equal(linear, [0., 0.])
    assert angular == 0 and metrics.terminated
    assert loop._current_waypoint_runner is None
    assert loop.measurement_state["goal_id"] is None

    # Even if rescans are delayed, idle must persist beyond the recovery timeout.
    scan.return_value = False
    for step in range(32, 57):
        linear, angular, metrics = advance(step)
        np.testing.assert_array_equal(linear, [0., 0.])
        assert angular == 0 and metrics.terminated
        assert not loop.measurement_state["recovering"]

    scan.return_value = True
    detector.return_value = [_make_cluster([0., 3., 0.])]
    planner.side_effect = lambda start, goal, grid: [start, goal]
    linear, angular, metrics = advance(57)
    assert linear[0] > 0 and angular > 0 and not metrics.terminated
    assert loop._current_waypoint_runner is not old_runner
    assert loop.measurement_state["goal_id"] is not None


def test_initial_scan_failure_stops_bootstrap_and_explicit_target_can_resume(monkeypatch):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    monkeypatch.setattr(loop.frontier_detector, "detect", lambda *a, **kw: [])
    frame = _make_sensor_frame()
    linear, _, _ = loop.step_once(frame, 29)
    assert linear[0] > 0  # Initial map acquisition remains supported.
    frame.sim_time = .1
    linear, angular, metrics = loop.step_once(frame, 30)
    np.testing.assert_array_equal(linear, [0., 0.])
    assert angular == 0 and metrics.terminated
    loop.set_waypoint_target([np.array([3., 0., 0.])])
    frame.sim_time = .2
    linear, _, metrics = loop.step_once(frame, 31)
    assert linear[0] > 0 and not metrics.terminated


def test_scan_exception_cannot_leave_an_executable_route(monkeypatch):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    loop.set_waypoint_target([np.array([3., 0., 0.])])
    monkeypatch.setattr(loop, "_should_rescan", lambda *a: False)
    frame = _make_sensor_frame()
    loop.step_once(frame, 28)
    frame.sim_time = .1
    loop.step_once(frame, 29)
    monkeypatch.setattr(loop.frontier_detector, "detect", MagicMock(side_effect=ValueError("bad map")))
    monkeypatch.setattr(loop, "_should_rescan", lambda *a: True)
    frame.sim_time = 1.
    with pytest.raises(ValueError, match="bad map"):
        loop.step_once(frame, 30)
    assert loop._current_waypoint_runner is None
    monkeypatch.setattr(loop, "_should_rescan", lambda *a: False)
    frame.sim_time = 3.1  # The old motion command must not trigger recovery.
    linear, angular, metrics = loop.step_once(frame, 31)
    np.testing.assert_array_equal(linear, [0., 0.])
    assert angular == 0 and metrics.terminated
    assert loop.measurement_state["goal_id"] is None
    assert not loop.measurement_state["recovering"]


@pytest.mark.parametrize("absorbing", [False, True])
def test_coordinator_keeps_exhausted_robot_idle_while_teammate_moves(absorbing, monkeypatch):
    from src.bridge.multi_robot_config import MultiRobotConfig
    from src.coordination.coordinator import Coordinator
    from src.coordination.robot_instance import RobotInstance

    bridge = MagicMock()
    bridge.robot_ids = ("robot_a", "robot_b")
    bridge.get_runtime_status.return_value.disabled = False
    time = 0.

    def frames():
        result = {rid: _make_sensor_frame() for rid in bridge.robot_ids}
        for frame in result.values():
            frame.sim_time = time
        return result

    def advance_physics():
        nonlocal time
        time += .1
        return frames()

    bridge.start.side_effect = frames
    bridge.step.side_effect = advance_physics
    robots = {}
    for rid in bridge.robot_ids:
        slam, octomap = MockSLAM(), MockOctoMap()
        loop = ExplorationLoop(bridge, slam, octomap)
        monkeypatch.setattr(loop.frontier_detector, "detect", MagicMock(return_value=[_make_cluster([3., 0., 0.])]))
        monkeypatch.setattr(loop._path_planner, "plan", lambda start, goal, grid: [start, goal])
        robots[rid] = RobotInstance(rid, slam, octomap, loop, np.eye(4), MagicMock())
    a, b = (robots[rid].exploration for rid in bridge.robot_ids)
    monkeypatch.setattr(a, "_should_rescan", lambda step, *args: step in (30, 31, 34, 35))
    monkeypatch.setattr(b, "_should_rescan", lambda step, *args: step in (30, 35))
    coordinator = Coordinator(bridge, robots, MultiRobotConfig(boot_phase_steps=999))
    for method in ("_setup_subscriptions", "_teardown_subscriptions", "_merge_occupancy_maps"):
        monkeypatch.setattr(coordinator, method, lambda *a: None)
    try:
        coordinator.start()
        coordinator._step_count = 29
        first = coordinator.advance(stop_on_termination=absorbing)
        assert all(c.to_wire()["linear"][0] > 0 for c in first.commands.values())
        a.frontier_detector.detect.return_value = []
        for _ in range(3):  # Scan failure, then two frames without a rescan.
            tick = coordinator.advance(stop_on_termination=absorbing)
            assert tick.commands["robot_a"].to_wire()["linear"] == [0., 0.]
            assert tick.commands["robot_a"].to_wire()["yaw_rate"] == 0.
            assert tick.commands["robot_b"].to_wire()["linear"][0] > 0
            assert tick.metrics["robot_a"].terminated
            assert tick.termination_reason is None
        a.frontier_detector.detect.return_value = [_make_cluster([0., 3., 0.])]
        resumed = coordinator.advance(stop_on_termination=absorbing)
        assert resumed.commands["robot_a"].to_wire()["linear"][0] > 0
        assert not resumed.metrics["robot_a"].terminated
        a.frontier_detector.detect.return_value = []
        b.frontier_detector.detect.return_value = []
        ended = coordinator.advance(stop_on_termination=absorbing)
        assert all(m.terminated for m in ended.metrics.values())
        assert ended.termination_reason == ("no_frontiers" if absorbing else None)
        assert all(c.to_wire()["linear"] == [0., 0.] for c in ended.commands.values())
    finally:
        coordinator.close()


def test_recovery_does_not_accumulate_another_stuck_timeout():
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap(),
                           ExplorationConfig(stuck_timeout_s=.2, recovery_reverse_duration_s=.1))
    recovering = []
    for step in range(29):
        frame = _make_sensor_frame()
        frame.sim_time = step * .1
        linear, _, _ = loop.step_once(frame, step)
        active = loop.measurement_state["recovering"]
        recovering.append(active)
        if active:
            assert loop._progress.no_progress_steps == 0
        if step == 3:
            assert active
            assert linear[0] < 0  # Recover on the triggering frame.
    completion = next(i for i in range(4, len(recovering)) if not recovering[i])
    assert not any(recovering[completion:completion + 3])
    assert recovering[completion + 3]


@pytest.mark.parametrize("timestamp", [0., -.1, float("nan"), float("inf")])
def test_sensor_clock_must_advance_even_without_explicit_frame_dt(timestamp):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    frame = _make_sensor_frame()
    loop.step_once(frame, 0)
    frame.sim_time = timestamp
    with pytest.raises(ValueError, match="sensor time"):
        loop.step_once(frame, 1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExplorationLoop:
    """Integration tests for ExplorationLoop."""

    def _make_config(self, **overrides) -> ExplorationConfig:
        """Create a fast test config."""
        defaults = dict(
            max_steps=100,
            stuck_timeout_s=0.5,
            rescan_distance_m=0.5,
            rescan_voxel_delta=50,
            log_interval_steps=10,
        )
        defaults.update(overrides)
        return ExplorationConfig(**defaults)

    def test_termination_no_frontiers(self) -> None:
        """Loop terminates when frontier detector returns empty list."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=200)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        call_count = 0

        def fake_detect(occupied, grid_2d=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return [_make_cluster([3.0, 0.0, 0.0])]
            return []

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=[
                 np.array([1.0, 0.0, 0.0]),
                 np.array([3.0, 0.0, 0.0]),
             ]):
            result = loop.run()

        assert result.terminated_reason == "no_frontiers"

    def test_skip_unreachable(self) -> None:
        """Loop skips unreachable frontier and tries next candidate."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=50)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        frontiers = [
            _make_cluster([2.0, 0.0, 0.0]),  # unreachable
            _make_cluster([1.0, 0.0, 0.0]),  # reachable
        ]

        detect_calls = [0]

        def fake_detect(occupied, grid_2d=None):
            detect_calls[0] += 1
            if detect_calls[0] <= 2:
                return frontiers
            return []  # terminate

        plan_call_goals = []

        def fake_plan(start, goal, grid):
            plan_call_goals.append(goal.copy())
            # First call unreachable, second reachable
            if len(plan_call_goals) <= 1:
                return None  # unreachable
            return [start, goal]  # reachable

        # GoalSelector uses "nearest" so it picks the closest first.
        # We need to control which is selected, so mock it.
        select_calls = [0]

        def fake_select(frontiers_list, pose):
            select_calls[0] += 1
            if not frontiers_list:
                return None
            return frontiers_list[0].centroid

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._goal_selector, "select", side_effect=fake_select), \
             patch.object(loop._path_planner, "plan", side_effect=fake_plan):
            result = loop.run()

        # Planner was called at least twice (first unreachable, second reachable)
        assert len(plan_call_goals) >= 2

    def test_all_unreachable(self) -> None:
        """Loop terminates when all frontiers are unreachable."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=200)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        def fake_detect(occupied, grid_2d=None):
            return [
                _make_cluster([2.0, 0.0, 0.0]),
                _make_cluster([5.0, 0.0, 0.0]),
            ]

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=None):
            result = loop.run()

        assert result.terminated_reason == "all_unreachable"

    def test_max_steps(self) -> None:
        """Loop terminates when max_steps reached."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=50)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        # Always return frontiers and valid paths so loop never terminates naturally
        def fake_detect(occupied, grid_2d=None):
            return [_make_cluster([10.0, 0.0, 0.0])]

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=[
                 np.array([5.0, 0.0, 0.0]),
                 np.array([10.0, 0.0, 0.0]),
             ]):
            result = loop.run()

        assert result.terminated_reason == "max_steps"
        assert result.total_steps == 50

    def test_stuck_detection(self) -> None:
        """Stuck detection triggers re-scan when position unchanged."""
        bridge = MockBridge(move_per_step=0.0)  # no movement
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=80, stuck_timeout_s=0.5)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        detect_call_count = [0]

        def fake_detect(occupied, grid_2d=None):
            detect_call_count[0] += 1
            # After a few detections, return empty to terminate
            if detect_call_count[0] > 3:
                return []
            return [_make_cluster([5.0, 0.0, 0.0])]

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=[
                 np.array([2.0, 0.0, 0.0]),
                 np.array([5.0, 0.0, 0.0]),
             ]):
            result = loop.run()

        # Detect was called multiple times (initial + stuck re-scans)
        assert detect_call_count[0] >= 2

    def test_coverage_logged(self) -> None:
        """Coverage is logged at log_interval_steps intervals."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=50, log_interval_steps=10)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        def fake_detect(occupied, grid_2d=None):
            return [_make_cluster([10.0, 0.0, 0.0])]

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=[
                 np.array([5.0, 0.0, 0.0]),
                 np.array([10.0, 0.0, 0.0]),
             ]):
            result = loop.run()

        # Should have logged at steps 0, 10, 20, 30, 40 (5 times)
        assert len(result.history) >= 3  # at least a few log entries

    def test_result_type(self) -> None:
        """run() returns ExplorationResult."""
        bridge = MockBridge()
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = self._make_config(max_steps=10)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        def fake_detect(occupied, grid_2d=None):
            return []

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect):
            result = loop.run()

        assert isinstance(result, ExplorationResult)


def test_skill_learning_disabled_preserves_baseline_score_fn() -> None:
    bridge = MockBridge()
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(
            skill_learning_enabled=False,
            rescan_distance_m=0.0,
            rescan_voxel_delta=0,
        ),
    )
    observed = {}

    def score_fn(candidate: np.ndarray) -> float:
        observed["called"] = True
        return -float(np.linalg.norm(candidate[:2]))

    loop.frontier_detector.detect = lambda occupied, grid_2d=None: [_make_cluster([2.0, 0.0, 0.0])]
    loop._path_planner.plan = lambda start, goal, grid: [start, goal]

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=30, score_fn=score_fn)

    assert metrics.frontiers == 1
    assert observed["called"] is True
    assert loop._current_waypoint_runner is not None
    assert loop.measurement_state["goal_id"] is not None


def test_skill_learning_enabled_records_decision_trace() -> None:
    bridge = MockBridge()
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(
            skill_learning_enabled=True,
            rescan_distance_m=0.0,
            rescan_voxel_delta=0,
        ),
    )
    loop.frontier_detector.detect = lambda occupied, grid_2d=None: [_make_cluster([2.0, 0.0, 0.0])]
    loop._path_planner.plan = lambda start, goal, grid: [start, goal]

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=30)

    records = [json.loads(line) for line in loop.skill_trace_jsonl().splitlines()]
    outcome = records[-1]["outcome"]
    assert metrics.frontiers == 1
    assert records[-1]["decision"]["selected_skill_id"] != "baseline"
    assert "frontier_pursuit" in loop.skill_trace_jsonl()
    assert outcome["termination"] == "success"
    assert outcome["fallback_used"] is False


def test_skill_learning_shadow_mode_records_without_changing_baseline_bias() -> None:
    bridge = MockBridge()
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(
            skill_learning_enabled=True,
            skill_learning_shadow_mode=True,
            rescan_distance_m=0.0,
            rescan_voxel_delta=0,
        ),
    )
    loop.frontier_detector.detect = lambda occupied, grid_2d=None: [
        _make_cluster([1.0, 0.0, 0.0]),
        _make_cluster([5.0, 0.0, 0.0]),
    ]
    selected_goals: list[np.ndarray] = []

    def fake_plan(start: np.ndarray, goal: np.ndarray, grid: np.ndarray) -> list[np.ndarray]:
        selected_goals.append(goal)
        return [start, goal]

    loop._path_planner.plan = fake_plan

    def prefer_far(candidate: np.ndarray) -> float:
        return float(candidate[0])

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=30, score_fn=prefer_far)

    trace_lines = loop.skill_trace_jsonl().splitlines()
    assert metrics.frontiers == 2
    assert selected_goals
    assert selected_goals[0][0] == pytest.approx(5.0)
    assert trace_lines


def test_skill_learning_enabled_no_frontiers_records_baseline_outcome() -> None:
    bridge = MockBridge()
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(
            skill_learning_enabled=True,
            rescan_distance_m=0.0,
            rescan_voxel_delta=0,
        ),
    )
    loop.frontier_detector.detect = lambda occupied, grid_2d=None: []

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=30)

    records = [json.loads(line) for line in loop.skill_trace_jsonl().splitlines()]
    outcome = records[-1]["outcome"]
    assert metrics.terminated is True
    assert metrics.frontiers == 0
    assert records[-1]["decision"]["selected_skill_id"] == "baseline"
    assert outcome["termination"] == "baseline_fallback"
    assert outcome["fallback_used"] is True
    assert outcome["path_length"] == 0.0


def test_skill_learning_enabled_unreachable_frontier_records_failure_outcome() -> None:
    bridge = MockBridge()
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(
            skill_learning_enabled=True,
            rescan_distance_m=0.0,
            rescan_voxel_delta=0,
        ),
    )
    loop.frontier_detector.detect = lambda occupied, grid_2d=None: [_make_cluster([2.0, 0.0, 0.0])]
    loop._path_planner.plan = lambda start, goal, grid: None

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=30)

    records = [json.loads(line) for line in loop.skill_trace_jsonl().splitlines()]
    outcome = records[-1]["outcome"]
    assert metrics.terminated is True
    assert metrics.frontiers == 1
    assert records[-1]["decision"]["selected_skill_id"] != "baseline"
    assert outcome["termination"] == "failure"
    assert outcome["fallback_used"] is False
    assert outcome["path_length"] == 0.0


# ---------------------------------------------------------------------------
# StuckRecovery tests
# ---------------------------------------------------------------------------

class TestStuckRecovery:
    """Tests for the StuckRecovery turn-in-place mechanism."""

    def test_stuck_recovery_triggers(self) -> None:
        """Stuck detection triggers StuckRecovery after a simulated-time timeout."""
        bridge = MockBridge(move_per_step=0.0)  # no movement
        slam = MockSLAM()
        octomap = MockOctoMap()
        config = ExplorationConfig(
            max_steps=30,
            stuck_timeout_s=0.5,
            rescan_distance_m=0.5,
            rescan_voxel_delta=50,
            log_interval_steps=100,
        )

        loop = ExplorationLoop(bridge, slam, octomap, config)

        # Mock frontier detection to return frontiers (keep loop alive)
        def fake_detect(occupied, grid_2d=None):
            return [_make_cluster([5.0, 0.0, 0.0])]

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect), \
             patch.object(loop._path_planner, "plan", return_value=[
                 np.array([2.0, 0.0, 0.0]),
                 np.array([5.0, 0.0, 0.0]),
             ]):
            # Run enough simulated time to trigger recovery.
            frame = bridge.start()
            for step in range(30):
                linear_vel, angular_vel, metrics = loop.step_once(frame, step)
                bridge.set_velocity(linear_vel, angular_vel)
                frame = bridge.step()

            # After stuck_timeout_s (0.5 seconds), recovery should have been triggered.
            # Recovery is reverse-then-turn: check for reverse (negative linear)
            # OR angular turn commands as evidence of activation.
            recovery_commands = [
                cmd for cmd in bridge._velocity_commands
                if abs(cmd[1]) > 0.5 or cmd[0][0] < -0.1  # angular turn OR reverse
            ]
            assert len(recovery_commands) > 0, (
                "Expected recovery commands (reverse or turn)"
            )

    def test_stuck_recovery_completes(self) -> None:
        """StuckRecovery.step() returns None after turning the required angle."""
        recovery = StuckRecovery(turn_angle=np.pi / 2, angular_speed=1.0)

        # Not active initially
        assert recovery.is_active is False
        assert recovery.step(0.1) is None

        # Trigger recovery
        np.random.seed(42)
        recovery.trigger()
        assert recovery.is_active is True

        # Step until recovery completes
        step_count = 0
        while recovery.is_active and step_count < 100:
            result = recovery.step(0.1)
            step_count += 1

        assert recovery.is_active is False, "Recovery should complete"
        assert step_count > 5, "Recovery should take multiple steps"
        assert step_count < 50, "Recovery should not take too many steps"

    def test_stuck_recovery_randomizes_direction(self) -> None:
        """StuckRecovery alternates between left and right turns."""
        recovery = StuckRecovery(turn_angle=np.pi / 2, angular_speed=1.0)

        directions = []
        for seed in range(20):
            np.random.seed(seed)
            recovery.trigger()
            # Step through the reverse phase to reach the turn phase
            for _ in range(40):
                result = recovery.step(0.1)
                if result is not None and abs(result[2]) > 0.01:
                    # Found the turn phase -- record direction
                    directions.append(np.sign(result[2]))
                    break
            # Reset for next trial
            recovery._active = False
            recovery._remaining_turn = 0.0
            recovery._remaining_reverse = 0
            recovery._phase = "idle"

        unique_directions = set(directions)
        assert len(unique_directions) >= 2, (
            f"Expected both positive and negative turns, got {unique_directions}"
        )
