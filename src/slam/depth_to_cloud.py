"""Depth image to Open3D point cloud conversion.

Unprojects a depth image into 3D points using pinhole camera intrinsics,
optionally coloring each point from the corresponding RGB pixel.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics


def depth_to_pointcloud(
    depth: np.ndarray,
    rgb: np.ndarray,
    intrinsics: CameraIntrinsics,
    max_depth: float = 10.0,
) -> o3d.geometry.PointCloud:
    """Convert a depth image + RGB image to an Open3D PointCloud.

    Args:
        depth: (H, W) float32 depth in meters.
        rgb: (H, W, 3) uint8 color image.
        intrinsics: Camera intrinsic parameters.
        max_depth: Maximum depth to include (meters). Points beyond this are excluded.

    Returns:
        Open3D PointCloud with points and colors.
    """
    h, w = depth.shape
    u, v = np.meshgrid(np.arange(w), np.arange(h))

    valid = (depth > 0) & (depth < max_depth)
    z_depth = depth[valid]
    # Pinhole unprojection: image (u,v) + depth → camera frame point
    cam_x = (u[valid] - intrinsics.cx) * z_depth / intrinsics.fx
    cam_y = (v[valid] - intrinsics.cy) * z_depth / intrinsics.fy

    # Config G: [-cx, -cy, -z] with cam_xmat.T transform
    # Empirically verified to place cloud in front of robot at ground level.
    points = np.stack([-cam_x, -cam_y, -z_depth], axis=-1)
    colors = rgb[valid].astype(np.float64) / 255.0

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd
