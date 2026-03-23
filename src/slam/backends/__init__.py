"""Built-in SLAM backends. Importing this package registers all built-in backends."""

from src.slam.backends import icp_backend  # noqa: F401 -- triggers @slam_backend registration
