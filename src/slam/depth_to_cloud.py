"""Depth image to Open3D point cloud conversion.

Supports multiple unprojection methods switchable at runtime via the
cloud config system. The active config determines both the point
arrangement and the pose transform mode used in multi_bridge.

Config "DIMOS" uses DimOS's proven approach (Open3D create_from_depth_image
+ Y/Z flip + cam_mat @ points). All other configs use manual pinhole math.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics

# Cloud configs: each defines how points are arranged in camera frame
# and which pose transform to use (body, cam_mat, cam_mat.T)
CLOUD_CONFIGS = {
    "DIMOS": {"label": "DimOS (o3d + flip Y/Z) | cam_mat", "pose": "cam_direct"},
    "A":     {"label": "[cx, -cy, -z] | cam (no .T)",       "pose": "cam_noT", "sx": 1,  "sy": -1, "sz": -1},
    "B":     {"label": "[cx, cy, -z] | cam (no .T)",        "pose": "cam_noT", "sx": 1,  "sy": 1,  "sz": -1},
    "C":     {"label": "[z, -cx, -cy] | body",              "pose": "body"},
    "D":     {"label": "[z, cx, -cy] | body",               "pose": "body"},
    "E":     {"label": "[-z, cx, cy] | body",               "pose": "body"},
    "F":     {"label": "[cx, -cy, z] | cam (no .T)",        "pose": "cam_noT", "sx": 1,  "sy": -1, "sz": 1},
    "G":     {"label": "[-cx, -cy, -z] | cam (.T)",         "pose": "cam_T",   "sx": -1, "sy": -1, "sz": -1},
    "H":     {"label": "[z, -cx, cy] | body",               "pose": "body"},
}

_active_config: str = "DIMOS"


def get_active_config() -> str:
    return _active_config


def set_active_config(key: str) -> None:
    global _active_config
    if key in CLOUD_CONFIGS:
        _active_config = key


def get_pose_mode() -> str:
    """Return the pose transform mode for the active config."""
    return CLOUD_CONFIGS.get(_active_config, CLOUD_CONFIGS["DIMOS"])["pose"]


def depth_to_pointcloud(
    depth: np.ndarray,
    rgb: np.ndarray,
    intrinsics: CameraIntrinsics,
    max_depth: float = 10.0,
) -> o3d.geometry.PointCloud:
    """Convert a depth image + RGB image to an Open3D PointCloud.

    The point arrangement depends on the active cloud config.

    Args:
        depth: (H, W) float32 depth in meters.
        rgb: (H, W, 3) uint8 color image.
        intrinsics: Camera intrinsic parameters.
        max_depth: Maximum depth to include (meters).

    Returns:
        Open3D PointCloud with points and colors.
    """
    cfg = _active_config

    if cfg == "DIMOS":
        return _dimos_depth_to_cloud(depth, rgb, intrinsics, max_depth)
    else:
        return _manual_depth_to_cloud(depth, rgb, intrinsics, max_depth, cfg)


def _dimos_depth_to_cloud(
    depth: np.ndarray,
    rgb: np.ndarray,
    intrinsics: CameraIntrinsics,
    max_depth: float,
) -> o3d.geometry.PointCloud:
    """DimOS approach: Open3D create_from_depth_image + Y/Z flip.

    This is the proven method from dimos/simulation/mujoco/depth_camera.py.
    Open3D handles the intrinsics math, then we flip Y and Z to convert
    from OpenCV convention (Y-down, Z-forward) to OpenGL/MuJoCo convention
    (Y-up, Z-back).

    The caller must use cam_mat @ points.T + cam_pos (no transpose)
    for world transform -- see get_pose_mode() returning "cam_direct".
    """
    h, w = depth.shape

    o3d_intrinsics = o3d.camera.PinholeCameraIntrinsic(
        w, h, intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy,
    )

    # Clamp depth: Open3D treats 0 as invalid
    depth_clean = depth.copy()
    depth_clean[depth_clean > max_depth] = 0.0

    o3d_depth = o3d.geometry.Image(depth_clean.astype(np.float32))
    pcd = o3d.geometry.PointCloud.create_from_depth_image(o3d_depth, o3d_intrinsics)

    points = np.asarray(pcd.points)
    if len(points) == 0:
        return pcd

    # Flip Y and Z: OpenCV (Y-down, Z-forward) → OpenGL (Y-up, Z-back)
    points[:, 1] = -points[:, 1]
    points[:, 2] = -points[:, 2]
    pcd.points = o3d.utility.Vector3dVector(points)

    # Add colors from RGB image
    if rgb is not None and len(points) > 0:
        # Re-project points back to pixel coords to sample colors
        # (create_from_depth_image preserves pixel ordering for valid depths)
        valid_mask = (depth_clean > 0).flatten()
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == len(points):
            rows = valid_indices // w
            cols = valid_indices % w
            colors = rgb[rows, cols].astype(np.float64) / 255.0
            pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd


def _manual_depth_to_cloud(
    depth: np.ndarray,
    rgb: np.ndarray,
    intrinsics: CameraIntrinsics,
    max_depth: float,
    cfg: str,
) -> o3d.geometry.PointCloud:
    """Manual pinhole unprojection with configurable point arrangement."""
    h, w = depth.shape
    u, v = np.meshgrid(np.arange(w), np.arange(h))

    valid = (depth > 0) & (depth < max_depth)
    z_depth = depth[valid]
    cam_x = (u[valid] - intrinsics.cx) * z_depth / intrinsics.fx
    cam_y = (v[valid] - intrinsics.cy) * z_depth / intrinsics.fy

    if cfg == "C":
        points = np.stack([z_depth, -cam_x, -cam_y], axis=-1)
    elif cfg == "D":
        points = np.stack([z_depth, cam_x, -cam_y], axis=-1)
    elif cfg == "E":
        points = np.stack([-z_depth, cam_x, cam_y], axis=-1)
    elif cfg == "H":
        points = np.stack([z_depth, -cam_x, cam_y], axis=-1)
    else:
        c = CLOUD_CONFIGS.get(cfg, CLOUD_CONFIGS["G"])
        points = np.stack([
            c["sx"] * cam_x,
            c["sy"] * cam_y,
            c["sz"] * z_depth,
        ], axis=-1)

    colors = rgb[valid].astype(np.float64) / 255.0

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd
