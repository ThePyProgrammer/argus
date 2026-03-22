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

    def get_occupied_voxels(self) -> np.ndarray:
        """Get centers of all occupied voxels.

        Returns:
            (M, 3) float64 array of voxel centers, or empty (0, 3) if no data.
        """
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
        return len(self.get_occupied_voxels())
