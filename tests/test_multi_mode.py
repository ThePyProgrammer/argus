"""Integration tests for multi-mode visualization wiring.

Verifies that Coordinator correctly calls MultiRobotVisualizer.update()
every 10 frames with properly structured data when viz is provided,
and runs without error when viz is None.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tests.conftest import MockMultiRobotBridge
from src.coordination.multi_robot_config import MultiRobotConfig
from src.coordination.robot_instance import RobotInstance
from src.coordination.coordinator import Coordinator
from src.coordination.map_merger import MapMerger
from src.coordination.voronoi_partitioner import VoronoiPartitioner
from src.bridge.sensor_types import CameraIntrinsics
from src.exploration.config import ExplorationConfig


def _make_mock_transport_cls():
    """Create a mock pLCMTransport class that returns usable mock instances."""
    mock_cls = MagicMock()
    mock_cls.return_value = MagicMock()
    return mock_cls


@pytest.fixture
def viz_setup():
    """Create a full multi-robot setup with mock bridge, mock pLCM, and mock viz.

    Returns (coordinator, mock_viz, robots).
    """
    config = MultiRobotConfig(boot_phase_steps=5)
    bridge = MockMultiRobotBridge(robot_ids=config.robot_ids)
    intrinsics = CameraIntrinsics(fx=32.0, fy=32.0, cx=32.0, cy=32.0, width=64, height=64)
    explore_config = ExplorationConfig(max_steps=100, voxel_resolution=0.1)

    mock_transport_cls = _make_mock_transport_cls()

    with patch("src.coordination.robot_instance.pLCMTransport", mock_transport_cls), \
         patch("src.coordination.coordinator.pLCMTransport", mock_transport_cls):

        robots = {}
        for rid in config.robot_ids:
            robots[rid] = RobotInstance.create(
                robot_id=rid, bridge=bridge, intrinsics=intrinsics,
                config=explore_config, spawn_position=config.spawn_positions[rid],
            )

        merger = MapMerger(resolution=0.1, spawn_transforms={
            rid: robots[rid].spawn_transform for rid in robots
        })
        partitioner = VoronoiPartitioner()
        mock_viz = MagicMock()

        coordinator = Coordinator(
            bridge=bridge, robots=robots, config=config,
            partitioner=partitioner, merger=merger, viz=mock_viz,
        )

        yield coordinator, mock_viz, robots


@pytest.fixture
def no_viz_setup():
    """Create a multi-robot setup without viz (viz=None)."""
    config = MultiRobotConfig(boot_phase_steps=5)
    bridge = MockMultiRobotBridge(robot_ids=config.robot_ids)
    intrinsics = CameraIntrinsics(fx=32.0, fy=32.0, cx=32.0, cy=32.0, width=64, height=64)
    explore_config = ExplorationConfig(max_steps=100, voxel_resolution=0.1)

    mock_transport_cls = _make_mock_transport_cls()

    with patch("src.coordination.robot_instance.pLCMTransport", mock_transport_cls), \
         patch("src.coordination.coordinator.pLCMTransport", mock_transport_cls):

        robots = {}
        for rid in config.robot_ids:
            robots[rid] = RobotInstance.create(
                robot_id=rid, bridge=bridge, intrinsics=intrinsics,
                config=explore_config, spawn_position=config.spawn_positions[rid],
            )

        merger = MapMerger(resolution=0.1, spawn_transforms={
            rid: robots[rid].spawn_transform for rid in robots
        })
        partitioner = VoronoiPartitioner()

        coordinator = Coordinator(
            bridge=bridge, robots=robots, config=config,
            partitioner=partitioner, merger=merger,
        )

        yield coordinator


def test_coordinator_calls_viz_update(viz_setup):
    """Coordinator with viz calls viz.update at least once during a 20-step run."""
    coordinator, mock_viz, robots = viz_setup
    coordinator.run(max_steps=20)
    assert mock_viz.update.call_count >= 1, (
        f"Expected viz.update to be called at least once, got {mock_viz.update.call_count}"
    )


def test_viz_update_receives_correct_keys(viz_setup):
    """viz.update is called with all required keyword arguments."""
    coordinator, mock_viz, robots = viz_setup
    coordinator.run(max_steps=10)

    assert mock_viz.update.called, "viz.update was never called"
    kwargs = mock_viz.update.call_args.kwargs
    assert "merged_voxels" in kwargs
    assert "robot_data" in kwargs
    assert "frontier_cells" in kwargs
    assert "total_coverage" in kwargs
    assert "merge_count" in kwargs
    assert "voronoi_midpoint" in kwargs
    assert "voronoi_direction" in kwargs


def test_robot_data_has_required_fields(viz_setup):
    """robot_data dict passed to viz.update has correct per-robot structure."""
    coordinator, mock_viz, robots = viz_setup
    coordinator.run(max_steps=10)

    assert mock_viz.update.called, "viz.update was never called"
    kwargs = mock_viz.update.call_args.kwargs
    robot_data = kwargs["robot_data"]

    assert "robot_a" in robot_data, "robot_data missing robot_a"
    assert "robot_b" in robot_data, "robot_data missing robot_b"

    for rid in ("robot_a", "robot_b"):
        data = robot_data[rid]
        assert "frame" in data, f"{rid} missing 'frame'"
        assert "local_voxels" in data, f"{rid} missing 'local_voxels'"
        assert "pose" in data, f"{rid} missing 'pose'"
        assert "trajectory" in data, f"{rid} missing 'trajectory'"
        assert "coverage_pct" in data, f"{rid} missing 'coverage_pct'"


def test_coordinator_without_viz(no_viz_setup):
    """Coordinator without viz runs without error (viz is None)."""
    coordinator = no_viz_setup
    result = coordinator.run(max_steps=10)
    assert "total_steps" in result
    assert result["total_steps"] > 0


def test_viz_update_interval(viz_setup):
    """viz.update is called exactly 3 times for a 25-step run (steps 0, 10, 20).

    Patches step_once to never terminate, ensuring the full 25 steps execute
    so the update interval can be verified.
    """
    coordinator, mock_viz, robots = viz_setup

    # Patch step_once to prevent early termination (mock data causes quick exit)
    non_terminating = (np.zeros(2), 0.0, {"terminated": False, "rescan_triggered": False, "coverage": 50.0})
    for rid in robots:
        robots[rid].exploration.step_once = MagicMock(return_value=non_terminating)

    coordinator.run(max_steps=25)
    assert mock_viz.update.call_count == 3, (
        f"Expected 3 calls (steps 0, 10, 20), got {mock_viz.update.call_count}"
    )
