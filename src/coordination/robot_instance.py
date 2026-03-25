"""Per-robot pipeline container with pLCM publisher.

Each RobotInstance bundles SLAM, OctoMap, and ExplorationLoop for one robot,
plus a pLCMTransport publisher for broadcasting occupancy grid and coverage
status to the Coordinator via DimOS pLCM typed pub/sub.

Per CONTEXT.md locked decision: each robot publishes its occupancy grid +
coverage status via pLCM. The Coordinator subscribes to these channels.
"""


from dataclasses import dataclass

import numpy as np

from src.slam.protocol import SLAMProtocol
from src.slam.registry import SLAMRegistry
from src.slam.octomap_builder import OctoMapBuilder
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.config import ExplorationConfig
from src.bridge.sensor_types import BridgeProtocol, CameraIntrinsics

from src.coordination.transport import pLCMTransport


@dataclass
class RobotMapMessage:
    """Message published via pLCM containing a robot's current map state.

    Serialized via PickleLCM (pLCM handles complex Python objects natively).
    """

    robot_id: str
    occupied_voxels: np.ndarray  # (M, 3) float64 world-frame voxel centers
    num_occupied: int
    coverage_pct: float  # 0.0 to 100.0


@dataclass
class RobotInstance:
    """Per-robot pipeline container bundling SLAM, OctoMap, Exploration, and pLCM publisher.

    Per CONTEXT.md locked decision: each robot publishes its occupancy grid +
    coverage status via pLCM. The publisher broadcasts a RobotMapMessage on
    each rescan event (when step_once returns rescan_triggered=True).
    """

    robot_id: str
    slam: SLAMProtocol
    octomap: OctoMapBuilder
    exploration: ExplorationLoop
    spawn_transform: np.ndarray  # (4, 4) world-frame offset (identity if at origin)
    publisher: pLCMTransport  # publishes RobotMapMessage to /{robot_id}/occupancy

    def get_pose(self) -> np.ndarray:
        """Return the latest SLAM pose, or identity if no poses yet."""
        poses = self.slam.get_poses()
        if poses:
            return poses[-1]
        return np.eye(4, dtype=np.float64)

    def get_occupied_voxels(self) -> np.ndarray:
        """Return occupied voxel centers from this robot's OctoMap."""
        return self.octomap.get_occupied_voxels()

    def get_cloud_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (points, colors) from this robot's SLAM global cloud."""
        return self.slam.get_global_cloud()

    def publish_map_state(self, coverage_pct: float = 0.0) -> None:
        """Publish current occupancy grid and coverage via pLCM.

        Called by Coordinator when step_once returns rescan_triggered=True.
        Voxels are already in world frame (SLAM pipeline transforms them
        using the camera's world pose), so no additional transform needed.
        """
        world_voxels = self.octomap.get_occupied_voxels()

        msg = RobotMapMessage(
            robot_id=self.robot_id,
            occupied_voxels=world_voxels,
            num_occupied=self.octomap.num_occupied,
            coverage_pct=coverage_pct,
        )
        self.publisher.broadcast(None, msg)

    @classmethod
    def create(
        cls,
        robot_id: str,
        bridge: BridgeProtocol,
        intrinsics: CameraIntrinsics,
        config: ExplorationConfig | None = None,
        spawn_position: tuple[float, float, float] = (0.0, 0.0, 0.3),
        backend_name: str | None = None,
    ) -> "RobotInstance":
        """Factory method to create a fully wired robot instance with pLCM publisher.

        Creates a pLCMTransport publishing to /{robot_id}/occupancy channel.

        Args:
            backend_name: SLAM backend name, or None for registry default ('icp').
        """
        slam = SLAMRegistry.create(backend_name, intrinsics=intrinsics)
        octomap = OctoMapBuilder(
            resolution=(config or ExplorationConfig()).voxel_resolution,
        )
        exploration = ExplorationLoop(
            bridge=bridge, slam=slam, octomap=octomap, config=config,
            intrinsics=intrinsics,
        )

        spawn_transform = np.eye(4, dtype=np.float64)
        spawn_transform[:3, 3] = np.array(spawn_position)

        # pLCM publisher for this robot's occupancy data
        publisher = pLCMTransport(topic=f"/{robot_id}/occupancy")

        return cls(
            robot_id=robot_id,
            slam=slam,
            octomap=octomap,
            exploration=exploration,
            spawn_transform=spawn_transform,
            publisher=publisher,
        )
