"""Built-in Detection3D lifters.

Importing this package triggers @detection_3d side-effect registration on
every built-in lifter. Pattern mirrors src/slam/backends/__init__.py per
CONTEXT.md D-07: `main.py` (via Plan 05) imports this package to populate
Detection3DRegistry before the coordinator queries list_backends().

Phase 1 shipped MedianDepthLifter; Phase 4 adds PointClusterLifter
(PCA-OBB via Open3D robust fit + sklearn DBSCAN, with MedianDepthLifter
composed as the <50-valid-pixels fallback per D-07).

Invariant (DET-3D-02): BOTH modules must be imported here — removing the
median_depth import would break PointClusterLifter's composition fallback
AND the 'median_depth' backend advertised via Detection3DRegistry.
"""

from src.perception.lifters import median_depth  # noqa: F401 -- registers 'median_depth'
from src.perception.lifters import point_cluster  # noqa: F401 -- registers 'point_cluster'
