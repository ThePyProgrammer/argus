"""Rerun streaming visualization for SLAM pipeline.

Logs point clouds, occupancy grids, robot trajectory, camera images,
and robot pose to the Rerun viewer for real-time 3D inspection.
"""

import numpy as np
import rerun as rr


class RerunVisualizer:
    """Streams SLAM data to Rerun viewer.

    Logs camera images, accumulated point cloud, OctoMap occupancy voxels,
    SLAM trajectory, and current robot pose to named Rerun entities.

    Usage::

        viz = RerunVisualizer(app_name="slam_viz")
        viz.log_frame(sensor_frame)
        viz.log_point_cloud(points, colors)
        viz.log_occupancy_grid(voxel_centers, resolution)
        viz.log_trajectory(slam_poses)
        viz.log_robot_pose(current_pose)
    """

    def __init__(self, app_name: str = "slam_viz"):
        """Initialize Rerun recording and spawn the viewer.

        Args:
            app_name: Application name shown in the Rerun viewer title bar.
        """
        rr.init(app_name, spawn=True)

    def log_frame(self, frame) -> None:
        """Log RGB and depth images from a SensorFrame.

        Args:
            frame: SensorFrame with ``rgb`` (H,W,3 uint8) and optional
                ``depth`` attributes.
        """
        rr.log("camera/rgb", rr.Image(frame.rgb))
        if frame.depth is not None:
            rr.log("camera/depth", rr.DepthImage(frame.depth))

    def log_point_cloud(
        self, points: np.ndarray, colors: np.ndarray | None = None
    ) -> None:
        """Log accumulated global point cloud.

        Args:
            points: (N, 3) float array of 3D positions.
            colors: Optional (N, 3) float or uint8 array of per-point colors.
        """
        if len(points) == 0:
            return
        if colors is not None and len(colors) == len(points):
            rr.log("map/point_cloud", rr.Points3D(points, colors=colors))
        else:
            rr.log("map/point_cloud", rr.Points3D(points))

    def log_occupancy_grid(
        self, voxel_centers: np.ndarray, resolution: float
    ) -> None:
        """Log occupied voxels from OctoMap as green cubes.

        Args:
            voxel_centers: (M, 3) float array of occupied voxel center positions.
            resolution: Voxel edge length in meters (used for point radii).
        """
        if len(voxel_centers) == 0:
            return
        rr.log(
            "map/occupancy",
            rr.Points3D(
                voxel_centers,
                radii=resolution / 2.0,
                colors=np.tile([0, 200, 0], (len(voxel_centers), 1)),
            ),
        )

    def log_trajectory(
        self, poses: list[np.ndarray], entity: str = "robot/slam_trajectory"
    ) -> None:
        """Log robot trajectory as a 3D line strip.

        Args:
            poses: List of (4, 4) homogeneous transforms.
            entity: Rerun entity path.
        """
        if len(poses) < 2:
            return
        positions = np.array([p[:3, 3] for p in poses])
        rr.log(entity, rr.LineStrips3D([positions]))

    def log_robot_pose(
        self, pose: np.ndarray, entity: str = "robot/current"
    ) -> None:
        """Log current robot transform.

        Args:
            pose: (4, 4) homogeneous transform.
            entity: Rerun entity path.
        """
        rr.log(
            entity,
            rr.Transform3D(
                translation=pose[:3, 3],
                mat3x3=pose[:3, :3],
            ),
        )
