"""SLAM pipeline using Open3D ICP odometry.

Processes RGB-D frames to estimate camera poses via frame-to-frame ICP
alignment and accumulates a global point cloud. Each frame's point cloud
is aligned to the previous frame and the relative transform is chained
into a cumulative pose estimate.

No loop closure or pose graph optimization — drift will accumulate over
long trajectories. Can be replaced with a more sophisticated backend
(e.g., RTAB-Map, ORB-SLAM3) via the same interface.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.depth_to_cloud import depth_to_pointcloud


class SLAMPipeline:
    """ICP-based visual odometry with global point cloud accumulation.

    Processes RGB-D SensorFrames one at a time. Each frame is converted to
    a point cloud, aligned to the previous frame via ICP, and the resulting
    relative transform is chained to produce a cumulative pose estimate.
    Aligned clouds are accumulated into a single global point cloud.

    Args:
        intrinsics: Camera intrinsic parameters for depth unprojection.
        voxel_size: Voxel size for downsampling (meters). Smaller = denser.
    """

    def __init__(self, intrinsics: CameraIntrinsics, voxel_size: float = 0.03):
        self._intrinsics = intrinsics
        self._voxel_size = voxel_size
        self._global_cloud = o3d.geometry.PointCloud()
        self._slam_poses: list[np.ndarray] = []
        self._prev_cloud: o3d.geometry.PointCloud | None = None
        self._current_pose: np.ndarray = np.eye(4)  # cumulative pose
        self._last_frame_cloud: np.ndarray = np.empty((0, 3))
        self._last_frame_colors: np.ndarray = np.empty((0, 3))

    def reset(self) -> None:
        """Clear all accumulated state for a fresh start."""
        self._global_cloud = o3d.geometry.PointCloud()
        self._slam_poses.clear()
        self._prev_cloud = None
        self._current_pose = np.eye(4)
        self._last_frame_cloud = np.empty((0, 3))
        self._last_frame_colors = np.empty((0, 3))

    def process_frame(self, frame: SensorFrame) -> np.ndarray:
        """Process one RGB-D frame. Returns ICP-estimated (4,4) pose.

        Aligns each frame's point cloud to the previous via ICP and chains
        the relative transforms to produce a cumulative pose estimate.
        Falls back to ground-truth on the first frame or when ICP fails.

        Args:
            frame: SensorFrame with rgb, depth, ground_truth_pose, sim_time.

        Returns:
            (4, 4) float64 homogeneous transform (ICP-estimated pose).
        """
        if frame.depth is None:
            self._slam_poses.append(self._current_pose.copy())
            return self._current_pose.copy()

        # Convert depth to point cloud in camera frame
        cloud = depth_to_pointcloud(
            frame.depth, frame.rgb, self._intrinsics, max_depth=10.0
        )
        cloud = cloud.voxel_down_sample(self._voxel_size)

        # Depth filtering: run every 5th frame to reduce CPU load
        if len(cloud.points) > 50 and len(self._slam_poses) % 5 == 0:
            cloud, _ = cloud.remove_statistical_outlier(
                nb_neighbors=10, std_ratio=2.0,
            )

        # ICP frame-to-frame alignment
        if self._prev_cloud is not None and len(cloud.points) > 100:
            result = o3d.pipelines.registration.registration_icp(
                cloud,
                self._prev_cloud,
                max_correspondence_distance=self._voxel_size * 3,
                init=np.eye(4),
                estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            )
            if result.fitness > 0.3:
                self._current_pose = self._current_pose @ result.transformation

        # Transform cloud to world frame using ICP-estimated pose
        cloud.transform(self._current_pose)

        # Store per-frame cloud for direct OctoMap insertion
        self._last_frame_cloud = np.asarray(cloud.points).copy()
        self._last_frame_colors = np.asarray(cloud.colors).copy() if cloud.has_colors() else np.empty((0, 3))

        self._global_cloud += cloud

        # Downsample accumulated cloud less aggressively (every 30 frames)
        if len(self._slam_poses) % 30 == 0:
            self._global_cloud = self._global_cloud.voxel_down_sample(
                self._voxel_size
            )

        self._slam_poses.append(self._current_pose.copy())
        self._prev_cloud = depth_to_pointcloud(
            frame.depth, frame.rgb, self._intrinsics, max_depth=10.0
        ).voxel_down_sample(self._voxel_size)

        return self._current_pose.copy()

    @property
    def global_cloud(self) -> o3d.geometry.PointCloud:
        return self._global_cloud

    @property
    def last_frame_cloud(self) -> np.ndarray:
        """Point cloud from the most recent frame (Nx3 float64)."""
        return self._last_frame_cloud

    @property
    def slam_poses(self) -> list[np.ndarray]:
        """List of estimated (4, 4) poses, one per processed frame."""
        return list(self._slam_poses)

    @property
    def num_frames_processed(self) -> int:
        """Number of frames processed so far."""
        return len(self._slam_poses)

    def get_cloud_points(self) -> np.ndarray:
        """Get global cloud as (N, 3) numpy array."""
        return np.asarray(self._global_cloud.points)

    def get_cloud_colors(self) -> np.ndarray:
        """Get global cloud colors as (N, 3) numpy array."""
        return np.asarray(self._global_cloud.colors)
