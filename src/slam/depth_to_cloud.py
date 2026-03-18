"""Depth image to Open3D point cloud conversion.

Unprojects a depth image into 3D points using pinhole camera intrinsics,
optionally coloring each point from the corresponding RGB pixel.

The point arrangement config is switchable at runtime via CLOUD_CONFIG.
"""

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics

# Runtime-switchable cloud configuration.
# Format: (cx_sign, cy_sign, cz_component) where cz_component is 'z' or '-z'
# Combined with pose_mode in multi_bridge: "body", "cam_noT", "cam_T"
CLOUD_CONFIGS = {
    "A": {"label": "[cx, -cy, -z] | cam (no .T)",  "sx": 1,  "sy": -1, "sz": -1},
    "B": {"label": "[cx, cy, -z] | cam (no .T)",   "sx": 1,  "sy": 1,  "sz": -1},
    "C": {"label": "[z, -cx, -cy] | body",         "sx": None, "sy": None, "sz": None},  # special
    "D": {"label": "[z, cx, -cy] | body",          "sx": None, "sy": None, "sz": None},  # special
    "E": {"label": "[-z, cx, cy] | body",          "sx": None, "sy": None, "sz": None},  # special
    "F": {"label": "[cx, -cy, z] | cam (no .T)",   "sx": 1,  "sy": -1, "sz": 1},
    "G": {"label": "[-cx, -cy, -z] | cam (.T)",    "sx": -1, "sy": -1, "sz": -1},
    "H": {"label": "[z, -cx, cy] | body",          "sx": None, "sy": None, "sz": None},  # special
}

# Active config key -- switched via WebSocket command
_active_config: str = "G"


def get_active_config() -> str:
    return _active_config


def set_active_config(key: str) -> None:
    global _active_config
    if key in CLOUD_CONFIGS:
        _active_config = key


def get_pose_mode() -> str:
    """Return the pose transform mode for the active config."""
    cfg = _active_config
    if cfg in ("A", "B", "F"):
        return "cam_noT"
    elif cfg in ("G",):
        return "cam_T"
    else:
        return "body"


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
    cam_x = (u[valid] - intrinsics.cx) * z_depth / intrinsics.fx
    cam_y = (v[valid] - intrinsics.cy) * z_depth / intrinsics.fy

    cfg = _active_config

    if cfg == "C":
        points = np.stack([z_depth, -cam_x, -cam_y], axis=-1)
    elif cfg == "D":
        points = np.stack([z_depth, cam_x, -cam_y], axis=-1)
    elif cfg == "E":
        points = np.stack([-z_depth, cam_x, cam_y], axis=-1)
    elif cfg == "H":
        points = np.stack([z_depth, -cam_x, cam_y], axis=-1)
    else:
        # Standard configs: [sx*cx, sy*cy, sz*z]
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
