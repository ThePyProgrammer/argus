"""Depth image to Open3D point cloud conversion.

Uses Open3D's create_from_depth_image for correct intrinsics math,
then applies configurable Y/Z sign flips and pose transforms.
Switchable at runtime from the Argus frontend.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics
from src.bridge.cloud_config import (
    CLOUD_CONFIGS,
    get_active_config,
    set_active_config,
)


def depth_to_pointcloud(
    depth: np.ndarray,
    rgb: np.ndarray,
    intrinsics: CameraIntrinsics,
    max_depth: float = 10.0,
) -> o3d.geometry.PointCloud:
    """Convert depth + RGB to Open3D PointCloud using active config.

    Uses Open3D create_from_depth_image (proven correct intrinsics math),
    then applies the active config's Y/Z sign flips.

    Args:
        depth: (H, W) float32 depth in meters. 0 = invalid.
        rgb: (H, W, 3) uint8 color image.
        intrinsics: Camera intrinsic parameters.
        max_depth: Maximum depth to include (meters).

    Returns:
        Open3D PointCloud with points and colors.
    """
    h, w = depth.shape
    cfg = CLOUD_CONFIGS[get_active_config()]

    o3d_intrinsics = o3d.camera.PinholeCameraIntrinsic(
        w, h, intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy,
    )

    depth_clean = depth.copy()
    depth_clean[depth_clean > max_depth] = 0.0

    o3d_depth = o3d.geometry.Image(depth_clean.astype(np.float32))
    pcd = o3d.geometry.PointCloud.create_from_depth_image(o3d_depth, o3d_intrinsics)

    points = np.asarray(pcd.points)
    if len(points) == 0:
        return pcd

    # Apply Y/Z flips per active config
    points[:, 1] *= cfg["fy"]
    points[:, 2] *= cfg["fz"]
    pcd.points = o3d.utility.Vector3dVector(points)

    # Map RGB colors to points using the valid depth mask
    # create_from_depth_image iterates pixels row-by-row, skipping invalid (0) depths
    valid_mask = depth_clean > 0
    valid_pixels = np.argwhere(valid_mask)  # (N, 2) array of [row, col]
    if len(valid_pixels) == len(points) and rgb is not None:
        rows = valid_pixels[:, 0]
        cols = valid_pixels[:, 1]
        colors = rgb[rows, cols].astype(np.float64) / 255.0
        pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd
