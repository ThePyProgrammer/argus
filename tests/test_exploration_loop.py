"""Integration tests for ExplorationLoop.

Uses mock bridge, SLAM, and OctoMap objects to test the full
detect-select-plan-navigate cycle with various termination conditions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame
from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import ExplorationResult
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.frontier_detector import FrontierCluster


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
        return _make_sensor_frame(self._position.copy())

    def step(self, action=None) -> SensorFrame:
        self._step_count += 1
        self._position[0] += self._move_per_step
        return _make_sensor_frame(self._position.copy())

    def set_velocity(self, linear: np.ndarray, angular: float) -> None:
        self._velocity_commands.append((linear, angular))

    def stop(self) -> None:
        pass

    @property
    def step_count(self) -> int:
        return self._step_count


class MockSLAM:
    """Simulates SLAMPipeline for testing."""

    def __init__(self) -> None:
        self._frame_count = 0
        self._cloud_size = 100

    def process_frame(self, frame: SensorFrame) -> np.ndarray:
        self._frame_count += 1
        return frame.ground_truth_pose.copy()

    def get_cloud_points(self) -> np.ndarray:
        rng = np.random.default_rng(self._frame_count)
        return rng.random((self._cloud_size, 3)) * 5.0


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
        voxels=np.zeros((count, 3), dtype=int),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExplorationLoop:
    """Integration tests for ExplorationLoop."""

    def _make_config(self, **overrides) -> ExplorationConfig:
        """Create a fast test config."""
        defaults = dict(
            max_steps=100,
            stuck_threshold_steps=5,
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

        def fake_detect(occupied, robot_positions):
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

        def fake_detect(occupied, robot_positions):
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

        def fake_detect(occupied, robot_positions):
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
        def fake_detect(occupied, robot_positions):
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
        config = self._make_config(max_steps=30, stuck_threshold_steps=5)

        loop = ExplorationLoop(bridge, slam, octomap, config)

        detect_call_count = [0]

        def fake_detect(occupied, robot_positions):
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

        def fake_detect(occupied, robot_positions):
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

        def fake_detect(occupied, robot_positions):
            return []

        with patch.object(loop._frontier_detector, "detect", side_effect=fake_detect):
            result = loop.run()

        assert isinstance(result, ExplorationResult)
