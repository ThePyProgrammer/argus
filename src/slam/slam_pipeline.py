"""SLAM pipeline using Open3D ICP odometry.

Processes RGB-D frames to estimate camera poses via frame-to-frame ICP
alignment and accumulates a global point cloud. This "lite" pipeline
replaces RTAB-Map standalone (whose Python bindings are limited) and is
sufficient for Phase 1 single-robot mapping.

Can be replaced with RTAB-Map ROS 2 integration in later phases if
loop closure and pose graph optimization are needed.
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

    def __init__(self, intrinsics: CameraIntrinsics, voxel_size: float = 0.05):
        self._intrinsics = intrinsics
        self._voxel_size = voxel_size
        self._global_cloud = o3d.geometry.PointCloud()
        self._slam_poses: list[np.ndarray] = []
        self._prev_cloud: o3d.geometry.PointCloud | None = None
        self._current_pose: np.ndarray = np.eye(4)  # cumulative pose

    def process_frame(self, frame: SensorFrame) -> np.ndarray:
        """Process one RGB-D frame. Returns estimated (4,4) pose.

        If depth is None (monocular fallback), uses ground-truth pose directly.

        Args:
            frame: SensorFrame with rgb, depth, ground_truth_pose, sim_time.

        Returns:
            (4, 4) float64 homogeneous transform (estimated camera pose).
        """
        if frame.depth is None:
            # Monocular fallback: use ground-truth pose, no SLAM
            self._slam_poses.append(frame.ground_truth_pose.copy())
            return frame.ground_truth_pose

        # Convert depth to point cloud
        cloud = depth_to_pointcloud(
            frame.depth, frame.rgb, self._intrinsics, max_depth=10.0
        )
        cloud = cloud.voxel_down_sample(self._voxel_size)

        if self._prev_cloud is not None and len(cloud.points) > 100:
            # ICP odometry: align current to previous
            result = o3d.pipelines.registration.registration_icp(
                cloud,
                self._prev_cloud,
                max_correspondence_distance=self._voxel_size * 3,
                init=np.eye(4),
                estimation_method=o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            )
            if result.fitness > 0.3:  # reasonable alignment
                self._current_pose = self._current_pose @ result.transformation

        # Transform cloud to global frame and accumulate
        cloud.transform(self._current_pose)
        self._global_cloud += cloud
        # Downsample accumulated cloud periodically (every 10 frames)
        if len(self._slam_poses) % 10 == 0:
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
        """Accumulated global point cloud in world frame."""
        return self._global_cloud

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
