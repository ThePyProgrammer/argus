"""Map merger for fusing multiple robots' local maps into a unified global map.

Uses union (OR) logic for voxel fusion: a voxel is occupied if EITHER
robot observed it as occupied. No probabilistic merging (v2).

Frame alignment uses known spawn transforms from config -- no ICP.
Since MuJoCo ground-truth poses are already in world frame, the spawn
transform is applied as a coordinate offset to each robot's local map.

Per CONTEXT.md decision: voxel-downsampled point clouds, union (OR) voxels.

This class can accept data either directly (OctoMapBuilder instances) or
via raw voxel arrays (for pLCM-based data flow where Coordinator passes
deserialized voxels received from subscriptions).
"""


import numpy as np
import open3d as o3d

from src.slam.octomap_builder import OctoMapBuilder


class MapMerger:
    """Fuses multiple robots' local maps via union-OR voxel merging.

    Accepts either OctoMapBuilder instances or raw voxel arrays.
    """

    def __init__(
        self,
        resolution: float = 0.1,
        spawn_transforms: dict[str, np.ndarray] | None = None,
    ):
        """
        Args:
            resolution: Voxel size in meters for deduplication.
            spawn_transforms: Dict mapping robot_id -> (4, 4) float64 transform.
                Applied to each robot's local voxels before merging.
                Default: identity (no offset) for both robots.
        """
        self._resolution = resolution
        self._transforms = spawn_transforms or {}
        self._last_merged_voxels: np.ndarray = np.empty((0, 3))
        self._last_merged_cloud: o3d.geometry.PointCloud = o3d.geometry.PointCloud()

    def merge(
        self,
        octomap_a: OctoMapBuilder,
        octomap_b: OctoMapBuilder,
        robot_a_id: str = "robot_a",
        robot_b_id: str = "robot_b",
    ) -> tuple[np.ndarray, o3d.geometry.PointCloud]:
        """Merge two OctoMap occupancy grids and point clouds.

        Returns:
            (unified_voxels, merged_cloud):
                unified_voxels: (N, 3) float64 deduplicated voxel centers
                merged_cloud: Open3D PointCloud, voxel-downsampled
        """
        # No transform needed: SLAM pipeline already outputs world-frame voxels
        # (camera pose includes robot position, so OctoMap data is in world frame)
        voxels_a = octomap_a.get_occupied_voxels()
        voxels_b = octomap_b.get_occupied_voxels()
        return self.merge_from_voxels(voxels_a, voxels_b)

    def merge_from_voxels(
        self,
        voxels_a: np.ndarray,
        voxels_b: np.ndarray,
    ) -> tuple[np.ndarray, o3d.geometry.PointCloud]:
        """Merge two pre-transformed voxel arrays (used by pLCM data flow).

        This is the primary merge path when Coordinator receives voxel data
        via pLCM subscriptions (already transformed by the publishing robot).

        Args:
            voxels_a: (N, 3) float64 voxel centers (already in world frame).
            voxels_b: (M, 3) float64 voxel centers (already in world frame).

        Returns:
            (unified_voxels, merged_cloud) tuple.
        """
        unified = self.merge_voxels(voxels_a, voxels_b)
        self._last_merged_voxels = unified

        cloud = self._merge_clouds_from_voxels(unified)
        self._last_merged_cloud = cloud
        return unified, cloud

    def merge_voxels(self, voxels_a: np.ndarray, voxels_b: np.ndarray) -> np.ndarray:
        """Union-merge two voxel arrays with deduplication.

        Args:
            voxels_a: (N, 3) float64 voxel centers.
            voxels_b: (M, 3) float64 voxel centers.

        Returns:
            (K, 3) float64 deduplicated voxel centers where K <= N + M.
        """
        if voxels_a.size == 0 and voxels_b.size == 0:
            return np.empty((0, 3), dtype=np.float64)
        if voxels_a.size == 0:
            return voxels_b.copy()
        if voxels_b.size == 0:
            return voxels_a.copy()

        combined = np.vstack([voxels_a, voxels_b])
        grid_indices = np.round(combined / self._resolution).astype(np.int64)
        _, unique_idx = np.unique(grid_indices, axis=0, return_index=True)
        return combined[unique_idx]

    def merge_point_clouds(
        self,
        cloud_a: o3d.geometry.PointCloud,
        cloud_b: o3d.geometry.PointCloud,
    ) -> o3d.geometry.PointCloud:
        """Merge and voxel-downsample two point clouds."""
        merged = cloud_a + cloud_b
        if len(merged.points) == 0:
            return merged
        return merged.voxel_down_sample(self._resolution)

    def _apply_transform(self, voxels: np.ndarray, robot_id: str) -> np.ndarray:
        """Apply spawn transform to voxel coordinates."""
        if robot_id not in self._transforms or voxels.size == 0:
            return voxels
        transform = self._transforms[robot_id]
        # Apply rotation and translation: p' = R @ p + t
        rotation = transform[:3, :3]
        translation = transform[:3, 3]
        return (voxels @ rotation.T) + translation

    def _merge_clouds_from_voxels(self, voxels: np.ndarray) -> o3d.geometry.PointCloud:
        """Create an Open3D PointCloud from merged voxel centers."""
        cloud = o3d.geometry.PointCloud()
        if voxels.size > 0:
            cloud.points = o3d.utility.Vector3dVector(voxels)
        return cloud

    @property
    def last_merged_voxels(self) -> np.ndarray:
        return self._last_merged_voxels

    @last_merged_voxels.setter
    def last_merged_voxels(self, voxels: np.ndarray) -> None:
        self._last_merged_voxels = voxels

    @property
    def last_merged_cloud(self) -> o3d.geometry.PointCloud:
        return self._last_merged_cloud
