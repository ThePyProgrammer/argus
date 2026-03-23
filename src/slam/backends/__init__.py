"""Built-in SLAM backends. Importing this package registers all built-in backends."""

from src.slam.backends import icp_backend  # noqa: F401 -- triggers @slam_backend registration

try:
    from src.slam.backends import orbslam3_backend  # noqa: F401
except Exception:
    pass  # orbslam3-python not installed; backend stays unregistered
