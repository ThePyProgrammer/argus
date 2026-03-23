"""Tests for MergeProtocol data types and MergeRegistry."""

import numpy as np
import open3d as o3d
import pytest

from src.coordination.merge_protocol import MergeProtocol, MergeResult, RobotMapData
from src.coordination.merge_registry import MergeRegistry, merge_strategy


class TestRobotMapData:
    """RobotMapData dataclass construction."""

    def test_construct_with_required_fields(self) -> None:
        poses = [np.eye(4) for _ in range(3)]
        clouds = [np.random.rand(10, 3) for _ in range(3)]
        voxels = np.random.rand(20, 3)
        data = RobotMapData(
            robot_id="robot_a",
            poses=poses,
            frame_clouds=clouds,
            current_voxels=voxels,
        )
        assert data.robot_id == "robot_a"
        assert len(data.poses) == 3
        assert data.poses[0].shape == (4, 4)
        assert len(data.frame_clouds) == 3
        assert data.current_voxels.shape == (20, 3)


class TestMergeResult:
    """MergeResult dataclass construction."""

    def test_construct_with_required_fields(self) -> None:
        voxels = np.random.rand(15, 3)
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(voxels)
        poses = {"robot_a": [np.eye(4)], "robot_b": [np.eye(4)]}
        result = MergeResult(
            merged_voxels=voxels,
            merged_cloud=cloud,
            optimized_poses=poses,
            metrics={"strategy": "test"},
        )
        assert result.merged_voxels.shape == (15, 3)
        assert isinstance(result.merged_cloud, o3d.geometry.PointCloud)
        assert "robot_a" in result.optimized_poses
        assert result.metrics["strategy"] == "test"

    def test_metrics_defaults_to_empty_dict(self) -> None:
        result = MergeResult(
            merged_voxels=np.empty((0, 3)),
            merged_cloud=o3d.geometry.PointCloud(),
            optimized_poses={},
        )
        assert result.metrics == {}


class TestMergeProtocol:
    """MergeProtocol is runtime_checkable."""

    def test_runtime_checkable(self) -> None:
        """A class implementing the protocol should pass isinstance check."""

        class FakeStrategy:
            CAPABILITIES: dict = {}
            PARAMETER_SCHEMA: dict = {}

            def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
                ...

            def reset(self) -> None:
                ...

            @property
            def last_merged_voxels(self) -> np.ndarray:
                return np.empty((0, 3))

            @property
            def last_merged_cloud(self) -> o3d.geometry.PointCloud:
                return o3d.geometry.PointCloud()

        assert isinstance(FakeStrategy(), MergeProtocol)

    def test_non_conforming_class_fails(self) -> None:
        """A class missing required methods should fail isinstance check."""

        class BadStrategy:
            pass

        assert not isinstance(BadStrategy(), MergeProtocol)


class TestMergeRegistry:
    """MergeRegistry discovery, registration, and factory."""

    @pytest.fixture(autouse=True)
    def _clear_registry(self) -> None:
        MergeRegistry._clear()

    def test_register_stores_strategy(self) -> None:
        MergeRegistry.register(
            "test_strat", "Test Strategy", "tests.fake_module.FakeClass"
        )
        strategies = MergeRegistry.list_strategies()
        assert len(strategies) == 1
        assert strategies[0]["name"] == "test_strat"
        assert strategies[0]["display"] == "Test Strategy"

    def test_list_strategies_returns_metadata(self) -> None:
        @merge_strategy("stub", "Stub Strategy")
        class StubStrategy:
            CAPABILITIES = {"supports_loop_closure": False}
            PARAMETER_SCHEMA = {"type": "object"}

        strategies = MergeRegistry.list_strategies()
        assert len(strategies) == 1
        entry = strategies[0]
        assert entry["name"] == "stub"
        assert entry["display"] == "Stub Strategy"
        assert entry["available"] is True
        assert entry["capabilities"] == {"supports_loop_closure": False}
        assert entry["parameter_schema"] == {"type": "object"}

    def test_create_instantiates_registered_strategy(self) -> None:
        @merge_strategy("dummy", "Dummy")
        class DummyStrategy:
            CAPABILITIES = {}
            PARAMETER_SCHEMA = {}

            def __init__(self, resolution: float = 0.1):
                self.resolution = resolution

        instance = MergeRegistry.create("dummy", resolution=0.2)
        assert instance.resolution == 0.2

    def test_create_raises_for_unknown_name(self) -> None:
        with pytest.raises(ValueError, match="Unknown merge strategy"):
            MergeRegistry.create("nonexistent")

    def test_get_default_returns_icp_union(self) -> None:
        assert MergeRegistry.get_default() == "icp_union"

    def test_clear_empties_registry(self) -> None:
        MergeRegistry.register("x", "X", "some.path.X")
        assert len(MergeRegistry.list_strategies()) == 1
        MergeRegistry._clear()
        assert len(MergeRegistry.list_strategies()) == 0

    def test_decorator_registers_class(self) -> None:
        @merge_strategy("deco_test", "Decorator Test")
        class DecoClass:
            CAPABILITIES = {}
            PARAMETER_SCHEMA = {}

        strategies = MergeRegistry.list_strategies()
        names = [s["name"] for s in strategies]
        assert "deco_test" in names
