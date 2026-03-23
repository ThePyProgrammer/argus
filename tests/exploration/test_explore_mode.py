"""End-to-end integration tests for the --control explore CLI mode.

Validates that ExplorationLoop runs through the full exploration pipeline
with a mock MuJoCo bridge (no real MuJoCo required). Tests cover:
- CLI argument parsing for explore mode
- Full exploration loop with max_steps termination
- Voxel production during exploration
- run_explore_mode function existence and callability
"""


import sys
from unittest.mock import patch

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import ExplorationResult
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.frontier_detector import FrontierCluster
from src.slam.octomap_builder import OctoMapBuilder
from src.slam.slam_pipeline import SLAMPipeline


# ---------------------------------------------------------------------------
# MockMuJoCoBridge -- simulates MuJoCoBridge for testing without MuJoCo
# ---------------------------------------------------------------------------

class MockMuJoCoBridge:
    """Simulates MuJoCoBridge for testing without MuJoCo installed.

    Returns synthetic SensorFrames with:
    - RGB: 320x240 black image
    - Depth: 320x240 float32 with uniform 2.0m depth (simulates a room)
    - Ground-truth pose: advances position by 0.05m in X per step
    - sim_time: step_count * 0.02
    """

    def __init__(self) -> None:
        self._step_count = 0
        self._position = np.array([0.0, 0.0, 0.3])
        self._linear_vel = np.zeros(2)
        self._angular_vel = 0.0

    def start(self) -> SensorFrame:
        self._step_count = 0
        return self._make_frame()

    def step(self, action=None) -> SensorFrame:
        # Move robot based on velocity command
        self._position[0] += self._linear_vel[0] * 0.02
        self._position[1] += self._linear_vel[1] * 0.02
        self._step_count += 1
        return self._make_frame()

    def set_velocity(self, linear: np.ndarray, angular: float) -> None:
        self._linear_vel = np.asarray(linear)
        self._angular_vel = angular

    def stop(self) -> None:
        pass

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def is_running(self) -> bool:
        return True

    def _make_frame(self) -> SensorFrame:
        pose = np.eye(4)
        pose[:3, 3] = self._position
        return SensorFrame(
            rgb=np.zeros((240, 320, 3), dtype=np.uint8),
            depth=np.full((240, 320), 2.0, dtype=np.float32),
            ground_truth_pose=pose,
            sim_time=self._step_count * 0.02,
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mujoco_bridge() -> MockMuJoCoBridge:
    """Return a fresh MockMuJoCoBridge instance."""
    return MockMuJoCoBridge()


@pytest.fixture
def mock_intrinsics() -> CameraIntrinsics:
    """Return CameraIntrinsics matching MuJoCo's 45-deg FOV at 320x240."""
    return CameraIntrinsics(
        fx=386.0, fy=386.0, cx=160.0, cy=120.0, width=320, height=240
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExploreModeParsing:
    """Test CLI argument parsing for explore mode."""

    def test_explore_mode_parse_args(self) -> None:
        """parse_args accepts --control explore and --explore-max-steps."""
        from src.main import parse_args

        original_argv = sys.argv
        try:
            sys.argv = ["main", "--control", "explore", "--explore-max-steps", "100"]
            args = parse_args()
            assert args.control == "explore"
            assert args.explore_max_steps == 100
        finally:
            sys.argv = original_argv

    def test_explore_rescan_distance_arg(self) -> None:
        """parse_args accepts --explore-rescan-distance."""
        from src.main import parse_args

        original_argv = sys.argv
        try:
            sys.argv = [
                "main", "--control", "explore",
                "--explore-rescan-distance", "3.5",
            ]
            args = parse_args()
            assert args.explore_rescan_distance == 3.5
        finally:
            sys.argv = original_argv


class TestExplorationLoopIntegration:
    """Integration tests running ExplorationLoop with mock bridge + real SLAM/OctoMap."""

    def test_exploration_loop_max_steps(self, mock_mujoco_bridge, mock_intrinsics) -> None:
        """ExplorationLoop terminates with 'max_steps' and correct step count."""
        slam = SLAMPipeline(mock_intrinsics)
        octomap = OctoMapBuilder(resolution=0.1)

        config = ExplorationConfig(
            max_steps=50,
            log_interval_steps=10,
            rescan_distance_m=0.5,
            rescan_voxel_delta=20,
            stuck_threshold_steps=100,  # disable stuck detection
        )

        loop = ExplorationLoop(
            bridge=mock_mujoco_bridge,
            slam=slam,
            octomap=octomap,
            config=config,
        )

        # Patch path planner to always return a valid path so loop reaches max_steps
        # (real planner may return None for frontiers in synthetic voxel data)
        def fake_plan(start, goal, grid):
            return [start, goal]

        with patch.object(loop._path_planner, "plan", side_effect=fake_plan):
            result = loop.run()

        assert isinstance(result, ExplorationResult)
        assert result.terminated_reason == "max_steps"
        assert abs(result.total_steps - 50) <= 1

    def test_exploration_loop_produces_voxels(self, mock_mujoco_bridge, mock_intrinsics) -> None:
        """Exploration loop produces occupied voxels (map grows)."""
        slam = SLAMPipeline(mock_intrinsics)
        octomap = OctoMapBuilder(resolution=0.1)

        config = ExplorationConfig(
            max_steps=100,
            log_interval_steps=20,
            rescan_distance_m=0.5,
            rescan_voxel_delta=20,
            stuck_threshold_steps=200,  # disable stuck detection
        )

        loop = ExplorationLoop(
            bridge=mock_mujoco_bridge,
            slam=slam,
            octomap=octomap,
            config=config,
        )

        loop.run()

        assert octomap.num_occupied > 0, "Exploration should produce occupied voxels"

    def test_exploration_result_has_valid_fields(self, mock_mujoco_bridge, mock_intrinsics) -> None:
        """ExplorationResult has all required fields populated."""
        slam = SLAMPipeline(mock_intrinsics)
        octomap = OctoMapBuilder(resolution=0.1)

        config = ExplorationConfig(
            max_steps=30,
            log_interval_steps=10,
            rescan_distance_m=0.5,
            rescan_voxel_delta=20,
            stuck_threshold_steps=100,
        )

        loop = ExplorationLoop(
            bridge=mock_mujoco_bridge,
            slam=slam,
            octomap=octomap,
            config=config,
        )

        result = loop.run()

        assert result.total_steps > 0
        assert isinstance(result.final_coverage_pct, float)
        assert isinstance(result.final_bbox_coverage_pct, float)
        assert isinstance(result.final_frontier_count, int)
        assert result.terminated_reason in ("no_frontiers", "max_steps", "all_unreachable")
        assert isinstance(result.history, list)


class TestRunExploreModeFunction:
    """Smoke tests for the run_explore_mode function."""

    def test_run_explore_mode_exists(self) -> None:
        """run_explore_mode is importable and callable."""
        from src.main import run_explore_mode

        assert callable(run_explore_mode)
