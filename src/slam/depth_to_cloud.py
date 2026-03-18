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
    # Pinhole unprojection in camera frame (OpenGL: X-right, Y-up, Z-back)
    cam_x = (u[valid] - intrinsics.cx) * z_depth / intrinsics.fx
    cam_y = (v[valid] - intrinsics.cy) * z_depth / intrinsics.fy

    # Camera frame: looking along -Z, X-right, Y-down (image convention)
    # MuJoCo camera: X-right, Y-up, Z-back (OpenGL convention)
    # The front_cam has xyaxes="0 -1 0 0 0 1" meaning:
    #   cam_X = body (0, -1, 0)   (right)
    #   cam_Y = body (0,  0, 1)   (up)
    #   cam_Z = body (-1, 0, 0)   (back, so looking along body +X)
    #
    # Points in camera frame (x_c, y_c, z_c) where z_c = -depth (behind camera = in front):
    #   body_x = -z_c = depth (forward)
    #   body_y = -x_c          (left)
    #   body_z = -y_c + offset (up, flipped from image Y-down)
    #
    # This places the ground plane at body_z ≈ -camera_height ≈ -0.25m (correct)
    points = np.stack([z_depth, -cam_x, -cam_y], axis=-1)
    colors = rgb[valid].astype(np.float64) / 255.0

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd
