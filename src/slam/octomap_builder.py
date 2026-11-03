"""OctoMap-style occupancy grid builder using Open3D VoxelGrid.

Uses Open3D's VoxelGrid as backend. Provides insert point cloud scans,
query occupied voxels, and control resolution.
"""

import numpy as np
import open3d as o3d


class OctoMapBuilder:
    """Occupancy grid builder using Open3D voxel discretization.

    Accumulates point cloud scans and provides occupied voxel queries.
    Resolution controls the voxel edge length in meters.
    """

    def __init__(self, resolution: float = 0.05):
        self._resolution = resolution
        self._accumulated_cloud = o3d.geometry.PointCloud()
        self._occupied_cache: np.ndarray | None = None

    def reset(self) -> None:
        """Clear all accumulated voxel data for a fresh start."""
        self._accumulated_cloud = o3d.geometry.PointCloud()
        self._occupied_cache = None

    def insert_scan(self, points: np.ndarray, sensor_origin: np.ndarray) -> None:
        """Insert a point cloud scan into the occupancy grid.

        Args:
            points: (N, 3) float64 array of 3D points in global frame.
            sensor_origin: (3,) float64 sensor position (stored for future
                ray-casting support but not used in voxel-only mode).
        """
        scan = o3d.geometry.PointCloud()
        scan.points = o3d.utility.Vector3dVector(points.astype(np.float64))
        self._accumulated_cloud += scan
        self._occupied_cache = None

    def get_occupied_voxels(self) -> np.ndarray:
        """Get centers of all occupied voxels.

        Returns:
            (M, 3) float64 array of voxel centers, or empty (0, 3) if no data.
        """
        # Preserve the caller-owned array contract while sharing voxelization
        # across planning, reporting, and count queries for the same scan set.
        return self._occupied_voxels().copy()

    def remove_plane_inliers(self, normal: np.ndarray, offset: float, tolerance: float) -> int:
        """Reclassify raw observations after an observed floor becomes available.

        Filter before voxelization: a low obstacle and floor can share a voxel,
        so removing a voxel by its center height would erase valid obstacles.
        """
        normal = np.asarray(normal, dtype=float)
        if (normal.shape != (3,) or not np.isfinite(normal).all()
                or not np.isclose(np.linalg.norm(normal), 1.)
                or not np.isfinite(offset) or not np.isfinite(tolerance) or tolerance <= 0):
            raise ValueError("Plane requires a unit normal, finite offset, and positive tolerance")
        points = np.asarray(self._accumulated_cloud.points)
        remove = np.abs(points @ normal - offset) <= tolerance
        count = int(remove.sum())
        if count:
            self._accumulated_cloud = self._accumulated_cloud.select_by_index(np.flatnonzero(~remove).tolist())
            self._occupied_cache = None
        return count

    def _occupied_voxels(self) -> np.ndarray:
        if self._occupied_cache is None:
            self._occupied_cache = self._voxelize()
        return self._occupied_cache

    def _voxelize(self) -> np.ndarray:
        if len(self._accumulated_cloud.points) == 0:
            return np.empty((0, 3))

        voxel_grid = o3d.geometry.VoxelGrid.create_from_point_cloud(
            self._accumulated_cloud, voxel_size=self._resolution
        )
        voxels = voxel_grid.get_voxels()
        if not voxels:
            return np.empty((0, 3))

        # Vectorized: convert voxel indices to world coordinates
        origin = np.asarray(voxel_grid.origin)
        indices = np.array([v.grid_index for v in voxels], dtype=np.float64)
        return origin + (indices + 0.5) * self._resolution

    @property
    def resolution(self) -> float:
        """Voxel edge length in meters."""
        return self._resolution

    @property
    def num_occupied(self) -> int:
        return len(self._occupied_voxels())
