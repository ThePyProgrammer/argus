"""Cloud configuration for depth-to-pointcloud axis flips.

Extracted from src/slam/depth_to_cloud.py to break the bridge<->slam
dependency cycle.  Bridge, SLAM, perception, and main all import from
here instead of depth_to_cloud.

cam_xmat from MuJoCo is R_world_from_cam (columns = camera axes in
world coords).  Only the direct matrix is correct for transforming
camera-frame points to world frame.  The transposed variants (cam.T)
were an early debugging artifact and have been removed -- they apply
R_cam_from_world which scatters ~30% of points below ground.
"""

import threading

# Each config: (flip_y, flip_z)
# flip_y/flip_z: whether to negate that axis after Open3D unprojection.
# Open3D camera convention is x-right, y-down, z-forward.
# MuJoCo camera convention is x-right, y-up, z-backward.
# Config "1" (Y- Z-) converts Open3D -> MuJoCo camera frame correctly.
CLOUD_CONFIGS = {
    "1": {"label": "Y- Z-",  "fy": -1, "fz": -1},
    "2": {"label": "Y- Z+",  "fy": -1, "fz":  1},
    "3": {"label": "Y+ Z-",  "fy":  1, "fz": -1},
    "4": {"label": "Y+ Z+",  "fy":  1, "fz":  1},
}

_active_config: str = "1"  # Y-Z- cam (standardized with offset correction)
_config_lock = threading.Lock()


def get_active_config() -> str:
    with _config_lock:
        return _active_config


def set_active_config(key: str) -> None:
    global _active_config
    with _config_lock:
        if key in CLOUD_CONFIGS:
            _active_config = key


def get_pose_mode() -> str:
    """Return the pose transform mode.

    Always returns "cam_noT" (direct cam_xmat, R_world_from_cam).
    The cam.T variants were removed -- they applied the inverse
    rotation which scattered points below ground.
    """
    return "cam_noT"
