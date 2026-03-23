"""Cloud configuration for depth-to-pointcloud axis flips and pose modes.

Extracted from src/slam/depth_to_cloud.py to break the bridge<->slam
dependency cycle.  Bridge, SLAM, perception, and main all import from
here instead of depth_to_cloud.
"""

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
