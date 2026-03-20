"""Depth image to Open3D point cloud conversion.

Uses Open3D's create_from_depth_image for correct intrinsics math,
then applies configurable Y/Z sign flips and pose transforms.
Switchable at runtime from the C2 frontend.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics

# Each config: (flip_y, flip_z, pose_mode)
# flip_y/flip_z: whether to negate that axis after Open3D unprojection
# pose_mode: "cam" (cam_mat, no transpose) or "cam_T" (cam_mat.T)
CLOUD_CONFIGS = {
    "1": {"label": "Y- Z- | cam",    "fy": -1, "fz": -1, "pose": "cam_noT"},
    "2": {"label": "Y- Z- | cam.T",  "fy": -1, "fz": -1, "pose": "cam_T"},
    "3": {"label": "Y- Z+ | cam",    "fy": -1, "fz":  1, "pose": "cam_noT"},
    "4": {"label": "Y- Z+ | cam.T",  "fy": -1, "fz":  1, "pose": "cam_T"},
    "5": {"label": "Y+ Z- | cam",    "fy":  1, "fz": -1, "pose": "cam_noT"},
    "6": {"label": "Y+ Z- | cam.T",  "fy":  1, "fz": -1, "pose": "cam_T"},
    "7": {"label": "Y+ Z+ | cam",    "fy":  1, "fz":  1, "pose": "cam_noT"},
    "8": {"label": "Y+ Z+ | cam.T",  "fy":  1, "fz":  1, "pose": "cam_T"},
}

_active_config: str = "1"  # Y-Z- cam (standardized with offset correction)


def get_active_config() -> str:
    return _active_config


def set_active_config(key: str) -> None:
    global _active_config
    if key in CLOUD_CONFIGS:
        _active_config = key


def get_pose_mode() -> str:
    """Return the pose transform mode for the active config."""
    return CLOUD_CONFIGS[_active_config]["pose"]


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
    cfg = CLOUD_CONFIGS[_active_config]

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
