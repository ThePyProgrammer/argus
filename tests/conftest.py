"""Shared test fixtures for the dimensional-applications test suite.

Provides mock sensor data, camera intrinsics, point clouds, and pose
sequences for use across all test modules.
"""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.exploration.config import ExplorationConfig


def _reload_modules(module_names: tuple[str, ...]) -> None:
    import importlib

    for module_name in module_names:
        module = importlib.import_module(module_name)
        importlib.reload(module)


def _restore_builtin_registries() -> None:
    from src.coordination.merge_registry import MergeRegistry
    from src.perception.registry import Detection3DRegistry, DetectorRegistry
    from src.slam.backends import register_builtin_backends

    register_builtin_backends()

    if not {"icp_union", "pgo_open3d", "pgo_gtsam"} <= MergeRegistry._strategies.keys():
        _reload_modules((
            "src.coordination.merge_strategies.icp_union",
            "src.coordination.merge_strategies.pgo_open3d",
            "src.coordination.merge_strategies.pgo_gtsam",
        ))

    if not {"yolov11", "rtdetrv2", "boxer"} <= DetectorRegistry._backends.keys():
        _reload_modules((
            "src.perception.backends.yolov11_backend",
            "src.perception.backends.rtdetrv2_backend",
            "src.perception.backends.boxer_backend",
        ))

    if not {"median_depth", "point_cluster"} <= Detection3DRegistry._backends.keys():
        _reload_modules((
            "src.perception.lifters.median_depth",
            "src.perception.lifters.point_cluster",
        ))


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item, nextitem):
    yield
    _restore_builtin_registries()


@pytest.fixture
def mock_sensor_frame() -> SensorFrame:
    """Return a SensorFrame with random 64x64 RGB, 64x64 depth, identity pose."""
    rng = np.random.default_rng(42)
    return SensorFrame(
        rgb=rng.integers(0, 256, size=(64, 64, 3), dtype=np.uint8),
        depth=rng.random((64, 64), dtype=np.float32) * 5.0,  # 0-5 meters
        ground_truth_pose=np.eye(4, dtype=np.float64),
        sim_time=0.0,
    )


@pytest.fixture
def mock_camera_intrinsics() -> CameraIntrinsics:
    """Return CameraIntrinsics for a 64x64 image with simple focal lengths."""
    return CameraIntrinsics(
        fx=32.0, fy=32.0, cx=32.0, cy=32.0, width=64, height=64
    )


@pytest.fixture
def sample_point_cloud() -> np.ndarray:
    """Return a (100, 3) random float64 point cloud."""
    rng = np.random.default_rng(42)
    return rng.random((100, 3), dtype=np.float64)


@pytest.fixture
def sample_poses() -> list[np.ndarray]:
    """Return a list of 10 random valid (4, 4) homogeneous transforms.

    Each transform has a valid rotation matrix (via scipy Rotation.random)
    and a random translation vector.
    """
    rng = np.random.default_rng(42)
    poses = []
    for _ in range(10):
        pose = np.eye(4, dtype=np.float64)
        pose[:3, :3] = Rotation.random(random_state=rng).as_matrix()
        pose[:3, 3] = rng.random(3) * 10.0  # random position 0-10m
        poses.append(pose)
    return poses


# ---------- Phase 2: Exploration fixtures ----------


@pytest.fixture
def mock_occupied_cube() -> np.ndarray:
    """Return (1000, 3) float64 voxel centers for a 10x10x10 cube at 0.1m resolution.

    Voxels from (0,0,0) to (0.9, 0.9, 0.9).
    """
    coords = []
    for x in range(10):
        for y in range(10):
            for z in range(10):
                coords.append([x * 0.1, y * 0.1, z * 0.1])
    return np.array(coords, dtype=np.float64)


@pytest.fixture
def mock_two_blobs() -> np.ndarray:
    """Return (250, 3) float64 for two separated 5x5x5 cubes.

    Blob 1: voxels from (0,0,0) to (0.4,0.4,0.4).
    Blob 2: voxels from (5,0,0) to (5.4,0.4,0.4).
    """
    coords = []
    for x in range(5):
        for y in range(5):
            for z in range(5):
                coords.append([x * 0.1, y * 0.1, z * 0.1])
                coords.append([5.0 + x * 0.1, y * 0.1, z * 0.1])
    return np.array(coords, dtype=np.float64)


@pytest.fixture
def mock_robot_positions() -> np.ndarray:
    """Return (5, 3) float64 positions along a line from (0,0,0) to (0.4,0,0)."""
    return np.array([
        [0.0, 0.0, 0.0],
        [0.1, 0.0, 0.0],
        [0.2, 0.0, 0.0],
        [0.3, 0.0, 0.0],
        [0.4, 0.0, 0.0],
    ], dtype=np.float64)


@pytest.fixture
def mock_exploration_config() -> ExplorationConfig:
    """Return a default ExplorationConfig for testing."""
    return ExplorationConfig()


# ---------- Phase 2: MuJoCo mock fixtures ----------


class MockMuJoCoBridge:
    """Simulates MuJoCoBridge for testing without MuJoCo installed.

    Returns synthetic SensorFrames with:
    - RGB: 320x240 black image
    - Depth: 320x240 float32 with uniform 2.0m depth
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


@pytest.fixture
def mock_mujoco_bridge() -> MockMuJoCoBridge:
    """Return a fresh MockMuJoCoBridge instance."""
    return MockMuJoCoBridge()


@pytest.fixture
def mock_mujoco_intrinsics() -> CameraIntrinsics:
    """Return CameraIntrinsics matching MuJoCo's 45-deg FOV at 320x240."""
    return CameraIntrinsics(
        fx=386.0, fy=386.0, cx=160.0, cy=120.0, width=320, height=240
    )


# ---------- Phase 3: Multi-robot fixtures ----------


class MockMultiRobotBridge:
    """Mock MultiRobotBridge for testing without MuJoCo."""

    def __init__(self, robot_ids=("robot_a", "robot_b")):
        self._robot_ids = robot_ids
        self._step_count = 0
        self._positions = {
            "robot_a": np.array([0.0, 0.0, 0.3]),
            "robot_b": np.array([10.0, 0.0, 0.3]),
        }
        self._velocities = {rid: (np.zeros(2), 0.0) for rid in robot_ids}

    def start(self) -> dict[str, SensorFrame]:
        self._step_count = 0
        return {rid: self._make_frame(rid) for rid in self._robot_ids}

    def step(self) -> dict[str, SensorFrame]:
        for rid in self._robot_ids:
            lin, ang = self._velocities[rid]
            self._positions[rid][0] += lin[0] * 0.02
            self._positions[rid][1] += lin[1] * 0.02
        self._step_count += 1
        return {rid: self._make_frame(rid) for rid in self._robot_ids}

    def set_velocity(self, robot_id: str, linear: np.ndarray, angular: float):
        self._velocities[robot_id] = (np.asarray(linear), angular)

    def stop(self):
        pass

    @property
    def step_count(self):
        return self._step_count

    @property
    def robot_ids(self):
        return self._robot_ids

    @property
    def is_running(self):
        return True

    def _make_frame(self, robot_id: str) -> SensorFrame:
        pose = np.eye(4)
        pose[:3, 3] = self._positions[robot_id]
        return SensorFrame(
            rgb=np.zeros((64, 64, 3), dtype=np.uint8),
            depth=np.full((64, 64), 2.0, dtype=np.float32),
            ground_truth_pose=pose,
            sim_time=self._step_count * 0.02,
        )


@pytest.fixture
def mock_multi_bridge():
    """Return a fresh MockMultiRobotBridge instance."""
    return MockMultiRobotBridge()
