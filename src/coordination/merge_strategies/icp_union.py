"""ICP Union baseline merge strategy.

Wraps the existing MapMerger as proof that the merge strategy abstraction
works with zero behavioral regression. Uses union (OR) voxel merging
and returns input poses unchanged (no pose graph optimization).
"""

import numpy as np
import open3d as o3d

from src.coordination.map_merger import MapMerger
from src.coordination.merge_protocol import MergeResult, RobotMapData
from src.coordination.merge_registry import merge_strategy


@merge_strategy(name="icp_union", display="ICP Union (Baseline)")
class ICPUnionStrategy:
    """Baseline merge strategy delegating to MapMerger.

    Collects voxels from all robots, merges via union-OR deduplication,
    and passes through poses unchanged. No pose graph optimization.
    """

    CAPABILITIES = {"supports_loop_closure": False, "incremental": False}
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "resolution": {
                "type": "number",
                "default": 0.1,
                "minimum": 0.01,
                "maximum": 0.5,
                "live_tunable": False,
            },
        },
    }

    def __init__(self, resolution: float = 0.1):
        self._merger = MapMerger(resolution=resolution)

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        """Merge maps from multiple robots using union-OR voxel fusion.

        Collects current_voxels from each robot, merges non-empty sets
        via MapMerger, and returns poses unchanged.
        """
        all_voxels = [
            d.current_voxels
            for d in robot_data.values()
            if len(d.current_voxels) > 0
        ]

        if len(all_voxels) >= 2:
            combined = np.vstack(all_voxels)
            self._merger.merge_from_voxels(all_voxels[0], combined[len(all_voxels[0]):])
        elif len(all_voxels) == 1:
            self._merger.last_merged_voxels = all_voxels[0]
            # Build cloud from the single voxel set
            cloud = o3d.geometry.PointCloud()
            if all_voxels[0].size > 0:
                cloud.points = o3d.utility.Vector3dVector(all_voxels[0])
            self._merger._last_merged_cloud = cloud

        return MergeResult(
            merged_voxels=self._merger.last_merged_voxels,
            merged_cloud=self._merger.last_merged_cloud,
            optimized_poses={
                rid: d.poses for rid, d in robot_data.items()
            },
            metrics={"strategy": "icp_union"},
        )

    def reset(self) -> None:
        """Clear accumulated merge state."""
        self._merger.last_merged_voxels = np.empty((0, 3))

    @property
    def last_merged_voxels(self) -> np.ndarray:
        """Most recently merged voxel array."""
        return self._merger.last_merged_voxels

    @property
    def last_merged_cloud(self) -> o3d.geometry.PointCloud:
        """Most recently merged point cloud."""
        return self._merger.last_merged_cloud
