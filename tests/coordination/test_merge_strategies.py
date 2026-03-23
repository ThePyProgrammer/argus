"""Tests for merge strategy implementations and output compatibility."""

import importlib

import numpy as np
import open3d as o3d
import pytest

from src.coordination.merge_protocol import MergeResult, RobotMapData
from src.coordination.merge_registry import MergeRegistry


def _make_robot_data(
    robot_id: str, n_voxels: int = 50, n_poses: int = 3
) -> RobotMapData:
    """Create RobotMapData with random voxels and identity poses."""
    rng = np.random.default_rng(hash(robot_id) % 2**31)
    voxels = rng.random((n_voxels, 3)) * 10.0
    poses = [np.eye(4) for _ in range(n_poses)]
    clouds = [rng.random((20, 3)) for _ in range(n_poses)]
    return RobotMapData(
        robot_id=robot_id,
        poses=poses,
        frame_clouds=clouds,
        current_voxels=voxels,
    )


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Clear and re-register strategies before each test."""
    MergeRegistry._clear()
    import src.coordination.merge_strategies  # noqa: F401

    # Force re-import to trigger decorator registration
    importlib.reload(src.coordination.merge_strategies.icp_union)
    yield
    MergeRegistry._clear()


class TestICPUnionStrategy:
    """ICP Union strategy behavior tests."""

    def test_registered_in_registry(self) -> None:
        strategies = MergeRegistry.list_strategies()
        names = [s["name"] for s in strategies]
        assert "icp_union" in names

    def test_merge_two_robots_produces_non_empty_voxels(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": _make_robot_data("robot_a"),
            "robot_b": _make_robot_data("robot_b"),
        }
        result = strategy.merge(robot_data)
        assert isinstance(result, MergeResult)
        assert result.merged_voxels.shape[0] > 0
        assert result.merged_voxels.shape[1] == 3

    def test_merge_empty_voxels_produces_empty_result(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": RobotMapData(
                robot_id="robot_a",
                poses=[np.eye(4)],
                frame_clouds=[np.empty((0, 3))],
                current_voxels=np.empty((0, 3)),
            ),
            "robot_b": RobotMapData(
                robot_id="robot_b",
                poses=[np.eye(4)],
                frame_clouds=[np.empty((0, 3))],
                current_voxels=np.empty((0, 3)),
            ),
        }
        result = strategy.merge(robot_data)
        assert result.merged_voxels.shape == (0, 3)

    def test_merge_returns_input_poses_unchanged(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        data_a = _make_robot_data("robot_a", n_poses=2)
        data_b = _make_robot_data("robot_b", n_poses=3)
        robot_data = {"robot_a": data_a, "robot_b": data_b}
        result = strategy.merge(robot_data)
        assert len(result.optimized_poses["robot_a"]) == 2
        assert len(result.optimized_poses["robot_b"]) == 3
        for orig, opt in zip(data_a.poses, result.optimized_poses["robot_a"]):
            np.testing.assert_array_equal(orig, opt)

    def test_reset_clears_merged_voxels(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": _make_robot_data("robot_a"),
            "robot_b": _make_robot_data("robot_b"),
        }
        strategy.merge(robot_data)
        assert strategy.last_merged_voxels.shape[0] > 0
        strategy.reset()
        assert strategy.last_merged_voxels.shape == (0, 3)


class TestMergeOutputCompat:
    """Output compatibility tests for merge strategies."""

    def test_last_merged_voxels_is_ndarray(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": _make_robot_data("robot_a"),
            "robot_b": _make_robot_data("robot_b"),
        }
        strategy.merge(robot_data)
        assert isinstance(strategy.last_merged_voxels, np.ndarray)

    def test_last_merged_cloud_is_pointcloud(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": _make_robot_data("robot_a"),
            "robot_b": _make_robot_data("robot_b"),
        }
        strategy.merge(robot_data)
        assert isinstance(strategy.last_merged_cloud, o3d.geometry.PointCloud)

    def test_metrics_contains_strategy_name(self) -> None:
        strategy = MergeRegistry.create("icp_union")
        robot_data = {
            "robot_a": _make_robot_data("robot_a"),
            "robot_b": _make_robot_data("robot_b"),
        }
        result = strategy.merge(robot_data)
        assert result.metrics["strategy"] == "icp_union"
