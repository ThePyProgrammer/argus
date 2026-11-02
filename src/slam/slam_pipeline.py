"""SLAM pipeline using constrained point-to-plane depth odometry.

Processes RGB-D frames to estimate camera poses via frame-to-frame ICP
alignment and accumulates a global point cloud. Each frame's point cloud
is aligned to the previous frame and the relative transform is chained
into a cumulative pose estimate.

No loop closure or pose graph optimization: drift will accumulate over
long trajectories. Can be replaced with a more sophisticated backend
(e.g., RTAB-Map, ORB-SLAM3) via the same interface.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.depth_to_cloud import depth_to_pointcloud
from src.slam.surface_odometry import MIN_CORRESPONDENCES, align_surfaces, registration_cloud


MAX_CLOUD_POINTS = 500_000


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

    def __init__(self, intrinsics: CameraIntrinsics, voxel_size: float = 0.03, *, cloud_config_key: str | None = None):
        self._intrinsics = intrinsics
        self._voxel_size = voxel_size
        self._cloud_config_key = cloud_config_key
        self._global_cloud = o3d.geometry.PointCloud()
        self._slam_poses: list[np.ndarray] = []
        self._prev_cloud: o3d.geometry.PointCloud | None = None
        self._current_pose: np.ndarray = np.eye(4)  # cumulative pose
        self._last_frame_cloud: np.ndarray = np.empty((0, 3))
        self._last_frame_colors: np.ndarray = np.empty((0, 3))
        self.registration_metrics: dict = {}
        self.tracking_ok = True

    def reset(self) -> None:
        """Clear all accumulated state for a fresh start."""
        self._global_cloud = o3d.geometry.PointCloud()
        self._slam_poses.clear()
        self._prev_cloud = None
        self._current_pose = np.eye(4)
        self._last_frame_cloud = np.empty((0, 3))
        self._last_frame_colors = np.empty((0, 3))
        self.registration_metrics = {}
        self.tracking_ok = True

    def process_frame(self, frame: SensorFrame) -> np.ndarray:
        """Process one RGB-D frame. Returns ICP-estimated (4,4) pose.

        Aligns each frame's point cloud to the previous via ICP and chains
        the relative transforms to produce a cumulative pose estimate.
        Seeds from ground truth on the first frame only. Rejected alignments
        retain the previous estimate; they do not read a live simulator pose.

        Args:
            frame: SensorFrame with rgb, depth, ground_truth_pose, sim_time.

        Returns:
            (4, 4) float64 homogeneous transform (ICP-estimated pose).
        """
        # Seed initial pose from ground truth so ICP chains from the
        # correct world-frame position and orientation.
        if not self._slam_poses:
            self._current_pose = frame.ground_truth_pose.copy()

        self._last_frame_cloud = np.empty((0, 3))
        self._last_frame_colors = np.empty((0, 3))
        self.registration_metrics = {"fitness": 0., "inlier_rmse": None,
                                     "observable_rank": 0, "accepted": False,
                                     "correspondences": 0, "source_points": 0,
                                     "target_points": len(self._prev_cloud.points) if self._prev_cloud is not None else 0,
                                     "registration_voxel_m": None, "rejection_reason": "missing_depth"}
        self.tracking_ok = False
        if frame.depth is None:
            self._slam_poses.append(self._current_pose.copy())
            return self._current_pose.copy()

        # Convert depth to point cloud in camera frame
        observation = depth_to_pointcloud(
            frame.depth, frame.rgb, self._intrinsics, max_depth=10.0,
            **({"cloud_config_key": self._cloud_config_key} if self._cloud_config_key is not None else {}),
        )
        cloud = observation.voxel_down_sample(self._voxel_size)

        # Apply the same preparation to both sides of every alignment.
        if len(cloud.points) > 50:
            cloud, _ = cloud.remove_statistical_outlier(
                nb_neighbors=10, std_ratio=2.0,
            )
        surfaces, registration_voxel = registration_cloud(observation, cloud, self._voxel_size)
        self.registration_metrics.update(source_points=len(surfaces.points),
                                         registration_voxel_m=registration_voxel)

        # Align against the last accepted camera frame.
        if self._prev_cloud is not None:
            mount = frame.body_from_camera
            # Calibration is fixed, so the body origin has these coordinates
            # in both camera frames. No live body/world pose is consulted.
            motion_origin = None if mount is None else -mount[:3, :3].T @ mount[:3, 3]
            result = align_surfaces(surfaces, self._prev_cloud, self._voxel_size * 3,
                                    motion_origin=motion_origin)
            reason = None
            if result.correspondences < MIN_CORRESPONDENCES:
                reason = "insufficient_correspondences"
            elif not (result.fitness > .3):
                reason = "low_overlap"
            elif result.observable_rank < 3:
                reason = "insufficient_rank"
            elif not np.isfinite(result.transformation).all():
                reason = "nonfinite_transform"
            self.tracking_ok = reason is None
            self.registration_metrics.update(fitness=result.fitness, inlier_rmse=result.inlier_rmse,
                                             observable_rank=result.observable_rank,
                                             correspondences=result.correspondences,
                                             accepted=self.tracking_ok, rejection_reason=reason)
            if self.tracking_ok:
                self._current_pose = self._current_pose @ result.transformation
        else:
            # The initial pose is supplied explicitly, so its map can be
            # seeded even if that view cannot support subsequent odometry.
            self.tracking_ok = not self._slam_poses and len(cloud.points) > 0
            self.registration_metrics["accepted"] = self.tracking_ok
            self.registration_metrics["rejection_reason"] = None if self.tracking_ok else "missing_initial_reference"

        if not self.tracking_ok:
            # The previous reference still belongs to the held pose. Do not
            # advance it or insert an unlocalized cloud after a rejected frame.
            self._slam_poses.append(self._current_pose.copy())
            return self._current_pose.copy()

        # Keep exactly the prepared cloud in camera coordinates. Reprojecting
        # it here previously used the mutable global axis configuration and
        # discarded filtering, even when this pipeline had a pinned config.
        self._prev_cloud = surfaces

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
            # Hard cap: progressively downsample with 2x voxel size until
            # the cloud fits under MAX_CLOUD_POINTS to prevent OOM.
            cap_voxel = self._voxel_size * 2
            while len(self._global_cloud.points) > MAX_CLOUD_POINTS:
                self._global_cloud = self._global_cloud.voxel_down_sample(
                    cap_voxel
                )
                cap_voxel *= 2

        self._slam_poses.append(self._current_pose.copy())
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
