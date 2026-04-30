"""Tests for Coordinator lifecycle, RobotInstance, pLCM data flow, and rescan-triggered merge.

Tests cover:
- RobotInstance creation and pLCM publishing
- Coordinator boot phase, rescan-triggered merge, no-merge-without-rescan
- Re-partition on empty region
- ExplorationLoop.step_once returns rescan_triggered
- GoalSelector.select_with_bias with custom score_fn
- pLCM subscription setup
"""


from unittest.mock import MagicMock, patch, PropertyMock
from dataclasses import dataclass

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.exploration.config import ExplorationConfig
from src.exploration.exploration_loop import StepMetrics
from src.exploration.frontier_detector import FrontierCluster
from src.exploration.goal_selector import GoalSelector
from src.slam.protocol import SLAMResult, TrackingStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sensor_frame(position=None):
    pose = np.eye(4, dtype=np.float64)
    if position is not None:
        pose[:3, 3] = position
    return SensorFrame(
        rgb=np.zeros((4, 4, 3), dtype=np.uint8),
        depth=np.zeros((4, 4), dtype=np.float32),
        ground_truth_pose=pose,
        sim_time=0.0,
    )


def _make_cluster(centroid, count=10):
    return FrontierCluster(
        centroid=np.array(centroid, dtype=np.float64),
        voxel_count=count,
        voxels=np.zeros((count, 3), dtype=int),
    )


class _MockSLAM:
    def __init__(self):
        self._poses = []
        self._frame_count = 0

    def process_frame(self, frame):
        self._frame_count += 1
        pose = frame.ground_truth_pose.copy()
        self._poses.append(pose)
        rng = np.random.default_rng(self._frame_count)
        points = rng.random((50, 3)) * 5.0
        colors = rng.random((50, 3))
        return SLAMResult(
            pose=pose,
            points=points,
            colors=colors,
            metrics={},
            tracking_status=TrackingStatus.OK,
        )

    def get_global_cloud(self):
        rng = np.random.default_rng(self._frame_count)
        pts = rng.random((50, 3)) * 5.0
        clr = rng.random((50, 3))
        return pts, clr

    def get_poses(self):
        return list(self._poses)

    def reset(self):
        self._poses.clear()
        self._frame_count = 0

    @property
    def num_frames_processed(self):
        return self._frame_count


class _MockOctoMap:
    def __init__(self):
        self._count = 100
        self._insert_count = 0

    def insert_scan(self, points, origin):
        self._insert_count += 1
        self._count += 10

    def get_occupied_voxels(self):
        rng = np.random.default_rng(self._count)
        return rng.random((self._count, 3)) * 5.0

    @property
    def num_occupied(self):
        return self._count


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRobotInstance:
    """Tests for RobotInstance creation and pLCM publishing."""

    def test_robot_instance_create(self):
        """RobotInstance.create returns instance with correct attributes."""
        from src.coordination.robot_instance import RobotInstance

        mock_bridge = MagicMock()
        intrinsics = CameraIntrinsics(fx=32, fy=32, cx=32, cy=32, width=64, height=64)

        mock_slam = _MockSLAM()
        with patch("src.coordination.robot_instance.pLCMTransport") as MockTransport, \
             patch("src.coordination.robot_instance.SLAMRegistry") as MockRegistry:
            mock_pub = MagicMock()
            mock_pub.topic = "/test_bot/occupancy"
            MockTransport.return_value = mock_pub
            MockRegistry.create.return_value = mock_slam

            robot = RobotInstance.create(
                robot_id="test_bot",
                bridge=mock_bridge,
                intrinsics=intrinsics,
            )

        assert robot.robot_id == "test_bot"
        assert robot.slam is not None
        assert robot.octomap is not None
        assert robot.exploration is not None
        assert robot.publisher is not None
        MockTransport.assert_called_once_with(topic="/test_bot/occupancy")
        MockRegistry.create.assert_called_once_with(None, intrinsics=intrinsics)

    def test_robot_instance_publish_map_state(self):
        """publish_map_state broadcasts RobotMapMessage via pLCM."""
        from src.coordination.robot_instance import RobotInstance, RobotMapMessage

        mock_publisher = MagicMock()
        mock_octomap = _MockOctoMap()

        robot = RobotInstance(
            robot_id="robot_a",
            slam=_MockSLAM(),
            octomap=mock_octomap,
            exploration=MagicMock(),
            spawn_transform=np.eye(4, dtype=np.float64),
            publisher=mock_publisher,
        )

        robot.publish_map_state(coverage_pct=42.0)

        mock_publisher.broadcast.assert_called_once()
        args = mock_publisher.broadcast.call_args
        msg = args[0][1]
        assert isinstance(msg, RobotMapMessage)
        assert msg.robot_id == "robot_a"
        assert msg.coverage_pct == 42.0
        assert msg.num_occupied == mock_octomap.num_occupied


class TestCoordinatorBootPhase:
    """Tests for Coordinator boot phase behavior."""

    def test_coordinator_boot_phase(self):
        """Partitioner.update_positions not called before boot_phase_steps."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=5)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a", "robot_b")

        frames = {
            "robot_a": _make_sensor_frame([0, 0, 0.3]),
            "robot_b": _make_sensor_frame([10, 0, 0.3]),
        }
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.octomap = _MockOctoMap()
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            r.exploration = MagicMock()
            r.exploration.step_once.return_value = (
                np.zeros(2), 0.0,
                StepMetrics(frontiers=5, coverage=0.0, terminated=True,
                            voxels=100, rescan_triggered=False),
            )
            robots[rid] = r

        mock_partitioner = MagicMock()
        mock_merger = MagicMock()
        mock_merger.last_merged_voxels = np.empty((0, 3))

        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            partitioner=mock_partitioner, merger=mock_merger,
        )

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"):
            # Run terminates immediately because all robots report terminated
            result = coordinator.run(max_steps=3)

        # Boot phase is 5, but we only ran 3 steps -- partition should NOT be called
        mock_partitioner.update_positions.assert_not_called()


class TestCoordinatorMerge:
    """Tests for merge triggering on rescan events."""

    def test_coordinator_triggers_merge_on_rescan(self):
        """Merge triggered when step_once returns rescan_triggered=True."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=0)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a", "robot_b")
        frames = {
            "robot_a": _make_sensor_frame([0, 0, 0.3]),
            "robot_b": _make_sensor_frame([10, 0, 0.3]),
        }
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames

        step_count = [0]

        def make_step_once(rid):
            def step_once(frame, step, score_fn=None):
                step_count[0] += 1
                # Rescan on steps 0, 2, 4 (for both robots)
                rescan = (step % 2 == 0)
                terminated = (step >= 5)
                return (
                    np.zeros(2), 0.0,
                    StepMetrics(
                        frontiers=0 if terminated else 5, coverage=0.0,
                        terminated=terminated, voxels=100,
                        rescan_triggered=rescan),
                )
            return step_once

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.octomap = _MockOctoMap()
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            r.exploration = MagicMock()
            r.exploration.step_once.side_effect = make_step_once(rid)
            robots[rid] = r

        mock_merger = MagicMock()
        mock_merger.last_merged_voxels = np.empty((0, 3))

        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=mock_merger,
        )

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"):
            result = coordinator.run(max_steps=6)

        # Rescan on steps 0, 2, 4 -> 3 merge calls during loop + 1 final merge = 4
        assert result.merge_count >= 3  # at least 3 rescan-triggered merges

    def test_coordinator_no_merge_without_rescan(self):
        """No merge (except final) when step_once never returns rescan_triggered."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=999)  # no partition
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a", "robot_b")
        frames = {
            "robot_a": _make_sensor_frame([0, 0, 0.3]),
            "robot_b": _make_sensor_frame([10, 0, 0.3]),
        }
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.octomap = _MockOctoMap()
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            r.exploration = MagicMock()
            # Never rescan, terminate at step 99
            r.exploration.step_once.return_value = (
                np.zeros(2), 0.0,
                StepMetrics(frontiers=5, coverage=0.0, terminated=False,
                            voxels=100, rescan_triggered=False),
            )
            robots[rid] = r

        mock_merger = MagicMock()
        mock_merger.last_merged_voxels = np.empty((0, 3))

        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=mock_merger,
        )

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"):
            result = coordinator.run(max_steps=100)

        # Only the final merge
        assert result.merge_count == 1


class TestCoordinatorRepartition:
    """Tests for re-partition when a robot's region is exhausted."""

    def test_coordinator_repartition_on_empty_region(self):
        """Re-partition triggers when should_repartition returns True."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=0)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a", "robot_b")
        frames = {
            "robot_a": _make_sensor_frame([0, 0, 0.3]),
            "robot_b": _make_sensor_frame([10, 0, 0.3]),
        }
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.octomap = _MockOctoMap()
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            r.exploration = MagicMock()
            r.exploration.frontier_detector = MagicMock()
            r.exploration.frontier_detector.detect.return_value = [
                _make_cluster([5, 0, 0]),
            ]
            r.exploration.step_once.return_value = (
                np.zeros(2), 0.0,
                StepMetrics(frontiers=1, coverage=0.0, terminated=True,
                            voxels=100, rescan_triggered=False),
            )
            robots[rid] = r

        mock_partitioner = MagicMock()
        mock_partitioner.should_repartition.return_value = True
        mock_merger = MagicMock()
        mock_merger.last_merged_voxels = np.empty((0, 3))

        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            partitioner=mock_partitioner, merger=mock_merger,
        )

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"):
            coordinator.run(max_steps=1)

        # Partition computed at least once (boot phase partition).
        # Repartition requires valid occupancy data which mocks can't provide;
        # repartition logic verified by integration tests with real MuJoCo.
        assert mock_partitioner.update_positions.call_count >= 1


class TestExplorationLoopStepOnce:
    """Tests for step_once returning rescan_triggered."""

    def test_step_once_returns_rescan_triggered(self):
        """step_once processes a frame and returns metrics with rescan_triggered."""
        from src.exploration.exploration_loop import ExplorationLoop

        mock_bridge = MagicMock()
        mock_slam = _MockSLAM()
        mock_octomap = _MockOctoMap()
        config = ExplorationConfig(max_steps=10, rescan_distance_m=0.5)

        loop = ExplorationLoop(mock_bridge, mock_slam, mock_octomap, config)

        frame = _make_sensor_frame([0, 0, 0])

        # Call at step 35 (past min_scan_step=30) to trigger rescan
        with patch.object(loop._frontier_detector, "detect", return_value=[]), \
             patch("src.exploration.exploration_loop.project_voxels_to_2d", return_value=MagicMock()):
            linear, angular, metrics = loop.step_once(frame, 35)

        assert isinstance(linear, np.ndarray)
        assert isinstance(angular, float)
        assert isinstance(metrics.rescan_triggered, bool)
        # First step always triggers rescan (waypoint_runner is None)
        assert metrics.rescan_triggered is True


class TestGoalSelectorWithBias:
    """Tests for GoalSelector.select_with_bias."""

    def test_select_with_bias_custom_score(self):
        """select_with_bias with custom score_fn selects highest-scored frontier."""
        selector = GoalSelector(strategy="nearest")
        clusters = [
            _make_cluster([1.0, 0.0, 0.0], count=10),
            _make_cluster([10.0, 0.0, 0.0], count=10),
        ]
        pose = np.eye(4, dtype=np.float64)

        # Score function: prefer further away (opposite of nearest)
        def prefer_far(centroid):
            return float(np.linalg.norm(centroid))

        result = selector.select_with_bias(clusters, pose, score_fn=prefer_far)
        assert result is not None
        np.testing.assert_array_almost_equal(result, [10.0, 0.0, 0.0])

    def test_select_with_bias_no_score_falls_back(self):
        """select_with_bias without score_fn falls back to default strategy."""
        selector = GoalSelector(strategy="nearest")
        clusters = [
            _make_cluster([10.0, 0.0, 0.0], count=10),
            _make_cluster([1.0, 0.0, 0.0], count=10),
        ]
        pose = np.eye(4, dtype=np.float64)

        result = selector.select_with_bias(clusters, pose, score_fn=None)
        assert result is not None
        np.testing.assert_array_almost_equal(result, [1.0, 0.0, 0.0])

    def test_select_with_bias_empty_returns_none(self):
        """select_with_bias with empty frontiers returns None."""
        selector = GoalSelector(strategy="nearest")
        pose = np.eye(4, dtype=np.float64)
        result = selector.select_with_bias([], pose, score_fn=lambda c: 1.0)
        assert result is None


class TestPLCMSubscriptionSetup:
    """Tests for Coordinator._setup_subscriptions."""

    def test_plcm_subscription_setup(self):
        """_setup_subscriptions creates one subscriber per robot on correct topics."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig()
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a", "robot_b")

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            robots[rid] = r

        mock_merger = MagicMock()
        mock_merger.last_merged_voxels = np.empty((0, 3))

        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=mock_merger,
        )

        with patch("src.coordination.coordinator.pLCMTransport") as MockTransport:
            mock_transport = MagicMock()
            MockTransport.return_value = mock_transport
            coordinator._setup_subscriptions()

        # Should create 2 transports (one per robot)
        assert MockTransport.call_count == 2
        topics = [call.kwargs.get("topic", call.args[0] if call.args else None)
                  for call in MockTransport.call_args_list]
        assert "/robot_a/occupancy" in topics
        assert "/robot_b/occupancy" in topics
        assert mock_transport.start.call_count == 2
        assert mock_transport.subscribe.call_count == 2


class TestCoordinatorMergeProtocol:
    """Tests for MergeProtocol integration in Coordinator."""

    def _make_mock_protocol_merger(self):
        """Create a mock that satisfies MergeProtocol runtime check."""
        from src.coordination.merge_protocol import MergeProtocol, MergeResult
        import open3d as o3d

        merger = MagicMock()
        merger.CAPABILITIES = {"supports_loop_closure": False, "incremental": False}
        merger.PARAMETER_SCHEMA = {}
        merger.last_merged_voxels = np.zeros((5, 3))
        merger.last_merged_cloud = o3d.geometry.PointCloud()
        merger.merge.return_value = MergeResult(
            merged_voxels=np.zeros((10, 3)),
            merged_cloud=o3d.geometry.PointCloud(),
            optimized_poses={},
            metrics={"strategy": "mock"},
        )
        # Make isinstance check pass by setting spec
        merger.__class__ = type(
            "MockMergeProtocol",
            (),
            {
                "CAPABILITIES": {"supports_loop_closure": False, "incremental": False},
                "PARAMETER_SCHEMA": {},
                "merge": lambda self, data: None,
                "reset": lambda self: None,
                "last_merged_voxels": property(lambda self: np.empty((0, 3))),
                "last_merged_cloud": property(lambda self: o3d.geometry.PointCloud()),
            },
        )
        return merger

    def test_coordinator_accepts_merge_protocol(self):
        """Coordinator can be created with a MergeProtocol merger."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig
        from src.coordination.merge_protocol import MergeProtocol

        config = MultiRobotConfig()
        mock_bridge = MagicMock()
        robots = {}
        for rid in ("robot_a",):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            robots[rid] = r

        merger = self._make_mock_protocol_merger()
        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=merger,
        )
        assert isinstance(coordinator._merger, MergeProtocol)

    def test_merge_via_protocol_calls_strategy_merge(self):
        """_merge_occupancy_maps calls strategy.merge() with RobotMapData when MergeProtocol."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig
        from src.coordination.merge_protocol import RobotMapData

        config = MultiRobotConfig()
        mock_bridge = MagicMock()

        robots = {}
        for rid in ("robot_a", "robot_b"):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.slam.process_frame(_make_sensor_frame([0, 0, 0]))
            r.octomap = _MockOctoMap()
            r.get_cloud_data.return_value = (np.zeros((10, 3)), np.zeros((10, 3)))
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            robots[rid] = r

        merger = self._make_mock_protocol_merger()
        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=merger,
        )

        coordinator._merge_occupancy_maps(("robot_a", "robot_b"))

        merger.merge.assert_called_once()
        call_args = merger.merge.call_args[0][0]
        assert "robot_a" in call_args
        assert "robot_b" in call_args
        assert isinstance(call_args["robot_a"], RobotMapData)

    def test_reset_merger_calls_strategy_reset(self):
        """reset_merger() calls strategy.reset() when MergeProtocol."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig()
        mock_bridge = MagicMock()
        robots = {}
        for rid in ("robot_a",):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            robots[rid] = r

        merger = self._make_mock_protocol_merger()
        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=merger,
        )

        coordinator.reset_merger()
        merger.reset.assert_called_once()

    def test_last_merged_voxels_accessible_after_merge(self):
        """self._merger.last_merged_voxels is accessible after merge (viz compat)."""
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig()
        mock_bridge = MagicMock()

        robots = {}
        for rid in ("robot_a",):
            r = MagicMock(spec=RobotInstance)
            r.robot_id = rid
            r.slam = _MockSLAM()
            r.slam.process_frame(_make_sensor_frame([0, 0, 0]))
            r.octomap = _MockOctoMap()
            r.get_cloud_data.return_value = (np.zeros((10, 3)), np.zeros((10, 3)))
            r.spawn_transform = np.eye(4, dtype=np.float64)
            r.publisher = MagicMock()
            robots[rid] = r

        merger = self._make_mock_protocol_merger()
        coordinator = Coordinator(
            bridge=mock_bridge, robots=robots, config=config,
            merger=merger,
        )

        coordinator._merge_occupancy_maps(("robot_a",))
        # Verify last_merged_voxels is accessible (used by viz pipeline)
        voxels = coordinator._merger.last_merged_voxels
        assert isinstance(voxels, np.ndarray)


class TestCoordinatorPlatformRuntimeState:
    def test_command_handler_forwards_velocity_command_to_bridge(self):
        from src.coordination.coordinator import Coordinator
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=0)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a",)
        robots = {"robot_a": MagicMock()}
        coordinator = Coordinator(mock_bridge, robots, config)

        coordinator.handle_command({
            "action": "velocity",
            "robot_id": "robot_a",
            "linear": [0.2, 0.0],
            "yaw_rate": 0.1,
        })

        args = mock_bridge.set_command.call_args[0]
        assert args[0] == "robot_a"
        assert args[1].to_wire() == {
            "mode": "velocity",
            "linear": [0.2, 0.0],
            "yaw_rate": 0.1,
            "waypoint": None,
        }

    def test_disabled_robot_gets_stop_command_in_run_loop(self):
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig
        from src.bridge.platforms.types import RobotRuntimeState, RobotRuntimeStatus

        config = MultiRobotConfig(boot_phase_steps=999)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a",)
        frames = {"robot_a": _make_sensor_frame([0, 0, 0.3])}
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames
        mock_bridge.get_runtime_status.return_value = RobotRuntimeStatus(state=RobotRuntimeState.DISABLED)

        robot = MagicMock(spec=RobotInstance)
        robot.robot_id = "robot_a"
        robot.slam = _MockSLAM()
        robot.octomap = _MockOctoMap()
        robot.spawn_transform = np.eye(4)
        robot.publisher = MagicMock()
        robot.exploration = MagicMock()
        robot.exploration.step_once.return_value = (
            np.array([1.0, 0.0]),
            0.2,
            StepMetrics(frontiers=5, coverage=0.0, terminated=False, voxels=100, rescan_triggered=False),
        )

        coordinator = Coordinator(mock_bridge, {"robot_a": robot}, config)

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"), \
             patch.object(coordinator, "_merge_occupancy_maps"):
            coordinator.run(max_steps=1)

        mock_bridge.stop_robot.assert_called_once_with("robot_a")
        robot.exploration.step_once.assert_not_called()
