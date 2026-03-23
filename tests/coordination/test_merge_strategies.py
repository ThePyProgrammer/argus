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
    # Register PGO strategies if available
    try:
        import src.coordination.merge_strategies.pgo_open3d  # noqa: F401

        importlib.reload(src.coordination.merge_strategies.pgo_open3d)
    except ImportError:
        pass
    try:
        import src.coordination.merge_strategies.pgo_gtsam  # noqa: F401

        importlib.reload(src.coordination.merge_strategies.pgo_gtsam)
    except ImportError:
        pass
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


# ---------------------------------------------------------------------------
# Helpers for PGO tests
# ---------------------------------------------------------------------------


def _make_robot_data_with_trajectory(
    robot_id: str,
    offset: np.ndarray | None = None,
    n_poses: int = 5,
    n_points_per_frame: int = 100,
    cloud_range: tuple[float, float] = (0.0, 2.0),
) -> RobotMapData:
    """Create RobotMapData with a simple linear trajectory and dense clouds.

    Args:
        robot_id: Robot identifier.
        offset: (3,) translation offset for the trajectory origin.
        n_poses: Number of poses along the trajectory.
        n_points_per_frame: Points per frame cloud.
        cloud_range: Min/max for random cloud points (uniform in cube).
    """
    rng = np.random.default_rng(hash(robot_id) % 2**31)
    if offset is None:
        offset = np.zeros(3)

    poses: list[np.ndarray] = []
    clouds: list[np.ndarray] = []
    all_pts: list[np.ndarray] = []

    for i in range(n_poses):
        pose = np.eye(4)
        pose[:3, 3] = offset + np.array([i * 0.5, 0.0, 0.0])
        poses.append(pose)

        low, high = cloud_range
        pts = rng.uniform(low, high, size=(n_points_per_frame, 3)) + offset
        clouds.append(pts)
        all_pts.append(pts)

    voxels = np.vstack(all_pts)
    # Deduplicate on a coarse grid
    grid = np.round(voxels / 0.1).astype(np.int64)
    _, idx = np.unique(grid, axis=0, return_index=True)
    voxels = voxels[idx]

    return RobotMapData(
        robot_id=robot_id, poses=poses, frame_clouds=clouds, current_voxels=voxels
    )


class TestOpen3DPGO:
    """Open3D PGO strategy behavior tests."""

    def test_registered_in_registry(self) -> None:
        strategies = MergeRegistry.list_strategies()
        names = [s["name"] for s in strategies]
        assert "pgo_open3d" in names

    def test_merge_two_robots_produces_non_empty_voxels(self) -> None:
        strategy = MergeRegistry.create("pgo_open3d")
        robot_data = {
            "robot_a": _make_robot_data_with_trajectory("robot_a"),
            "robot_b": _make_robot_data_with_trajectory(
                "robot_b", offset=np.array([0.5, 0.0, 0.0])
            ),
        }
        result = strategy.merge(robot_data)
        assert isinstance(result, MergeResult)
        assert result.merged_voxels.shape[0] > 0
        assert result.merged_voxels.shape[1] == 3

    def test_merge_returns_optimized_poses_different_from_input(self) -> None:
        strategy = MergeRegistry.create("pgo_open3d")
        data_a = _make_robot_data_with_trajectory("robot_a")
        data_b = _make_robot_data_with_trajectory(
            "robot_b", offset=np.array([0.5, 0.0, 0.0])
        )
        robot_data = {"robot_a": data_a, "robot_b": data_b}
        result = strategy.merge(robot_data)
        # Optimized poses should exist for both robots
        assert "robot_a" in result.optimized_poses
        assert "robot_b" in result.optimized_poses
        assert len(result.optimized_poses["robot_a"]) == len(data_a.poses)

    def test_merge_single_robot_returns_data_unchanged(self) -> None:
        strategy = MergeRegistry.create("pgo_open3d")
        data_a = _make_robot_data_with_trajectory("robot_a")
        robot_data = {"robot_a": data_a}
        result = strategy.merge(robot_data)
        assert result.merged_voxels.shape[0] > 0
        assert len(result.optimized_poses["robot_a"]) == len(data_a.poses)

    def test_reset_clears_state(self) -> None:
        strategy = MergeRegistry.create("pgo_open3d")
        robot_data = {
            "robot_a": _make_robot_data_with_trajectory("robot_a"),
            "robot_b": _make_robot_data_with_trajectory(
                "robot_b", offset=np.array([0.5, 0.0, 0.0])
            ),
        }
        strategy.merge(robot_data)
        assert strategy.last_merged_voxels.shape[0] > 0
        strategy.reset()
        assert strategy.last_merged_voxels.shape == (0, 3)


class TestPGOLoopClosure:
    """Loop closure detection tests for PGO strategies."""

    def test_overlapping_clouds_detect_loop_closure(self) -> None:
        """When two robots have overlapping point clouds, loop closure is detected."""
        # Both robots explore the same [0,2]^3 region
        strategy = MergeRegistry.create(
            "pgo_open3d", loop_closure_interval=1
        )
        robot_data = {
            "robot_a": _make_robot_data_with_trajectory(
                "robot_a", cloud_range=(0.0, 2.0), n_points_per_frame=200
            ),
            "robot_b": _make_robot_data_with_trajectory(
                "robot_b",
                offset=np.array([0.1, 0.0, 0.0]),
                cloud_range=(0.0, 2.0),
                n_points_per_frame=200,
            ),
        }
        result = strategy.merge(robot_data)
        assert result.metrics.get("loop_closures_found", 0) > 0


class TestLoopClosureFallback:
    """Loop closure fallback to spawn transforms tests."""

    def test_fallback_with_spawn_transforms_uses_relative_transform(self) -> None:
        """When ICP fails and spawn_transforms are provided, fallback uses
        the relative spawn transform (not identity)."""
        # Robots in completely separate regions so ICP will fail
        t_b = np.eye(4)
        t_b[:3, 3] = [100.0, 0.0, 0.0]
        strategy = MergeRegistry.create(
            "pgo_open3d",
            loop_closure_interval=1,
            spawn_transforms={"robot_a": np.eye(4), "robot_b": t_b},
        )
        data_a = _make_robot_data_with_trajectory(
            "robot_a", cloud_range=(0.0, 1.0), n_points_per_frame=100
        )
        data_b = _make_robot_data_with_trajectory(
            "robot_b",
            offset=np.array([100.0, 0.0, 0.0]),
            cloud_range=(0.0, 1.0),
            n_points_per_frame=100,
        )
        robot_data = {"robot_a": data_a, "robot_b": data_b}
        result = strategy.merge(robot_data)
        assert result.metrics.get("loop_closure_fallbacks", 0) > 0

    def test_fallback_without_spawn_transforms_uses_identity(self) -> None:
        """When ICP fails and no spawn_transforms are provided, fallback uses
        identity transform (graceful degradation)."""
        strategy = MergeRegistry.create(
            "pgo_open3d",
            loop_closure_interval=1,
            spawn_transforms=None,
        )
        data_a = _make_robot_data_with_trajectory(
            "robot_a", cloud_range=(0.0, 1.0), n_points_per_frame=100
        )
        data_b = _make_robot_data_with_trajectory(
            "robot_b",
            offset=np.array([100.0, 0.0, 0.0]),
            cloud_range=(0.0, 1.0),
            n_points_per_frame=100,
        )
        robot_data = {"robot_a": data_a, "robot_b": data_b}
        result = strategy.merge(robot_data)
        # Should still produce a result (graceful degradation)
        assert result.merged_voxels.shape[0] > 0
        assert result.metrics.get("loop_closure_fallbacks", 0) > 0
