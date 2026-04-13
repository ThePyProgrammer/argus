"""Built-in Detection3D lifters.

Importing this package triggers @detection_3d side-effect registration on
every built-in lifter. Pattern mirrors src/slam/backends/__init__.py per
CONTEXT.md D-07: `main.py` (via Plan 05) imports this package to populate
Detection3DRegistry before the coordinator queries list_backends().

Phase 1 ships only the MedianDepthLifter; Phase 4 adds point_cluster.
"""

from src.perception.lifters import median_depth  # noqa: F401 -- triggers @detection_3d registration
