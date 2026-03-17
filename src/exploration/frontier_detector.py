"""3D voxel frontier detection with 26-connected neighbor scanning and BFS clustering.

A frontier voxel is an occupied voxel that has at least one 26-connected
neighbor position that is NOT occupied (i.e., on the boundary of the known
region). Frontier voxels are clustered via BFS and filtered by minimum
cluster size to remove noise.

This module reads occupied voxel centers from OctoMapBuilder.get_occupied_voxels()
and produces ranked FrontierCluster objects for goal selection.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class FrontierCluster:
    """A cluster of frontier voxels on the boundary of explored space.

    Attributes:
        centroid: (3,) float64 world coordinates of cluster center.
        voxel_count: Number of voxels in this cluster.
        voxels: (K, 3) int grid indices of cluster voxels.
    """

    centroid: np.ndarray  # (3,) float64 world coordinates
    voxel_count: int  # number of voxels in this cluster
    voxels: np.ndarray  # (K, 3) int grid indices of cluster voxels


# Pre-computed 26-connected neighbor offsets (excludes (0,0,0))
_OFFSETS_26: list[tuple[int, int, int]] = []
for _dx in (-1, 0, 1):
    for _dy in (-1, 0, 1):
        for _dz in (-1, 0, 1):
            if _dx == 0 and _dy == 0 and _dz == 0:
                continue
            _OFFSETS_26.append((_dx, _dy, _dz))


class FrontierDetector:
    """Detect frontier voxels in 3D voxel space using 26-connectivity.

    A frontier voxel is an occupied voxel with at least one empty
    26-connected neighbor. Frontiers are clustered via BFS and
    filtered by minimum cluster size.
    """

    def __init__(self, resolution: float = 0.1, min_cluster_size: int = 5):
        self._resolution = resolution
        self._min_cluster_size = min_cluster_size

    @staticmethod
    def _get_26_offsets() -> list[tuple[int, int, int]]:
        """Return pre-computed 26-connected neighbor offsets."""
        return _OFFSETS_26

    def detect(
        self, occupied_voxels: np.ndarray, robot_positions: np.ndarray
    ) -> list[FrontierCluster]:
        """Detect frontier clusters from occupied voxel centers.

        Args:
            occupied_voxels: (N, 3) float64 voxel centers from
                OctoMapBuilder.get_occupied_voxels().
            robot_positions: (M, 3) float64 positions the robot has visited
                (defines the observed region -- reserved for future use).

        Returns:
            List of FrontierCluster objects sorted by voxel_count descending.
            Empty list if no frontiers found or input too small.
        """
        if occupied_voxels.size == 0 or len(occupied_voxels) < self._min_cluster_size:
            return []

        # Convert world coords to grid indices
        grid_min = occupied_voxels.min(axis=0) - self._resolution * 5
        indices = np.round((occupied_voxels - grid_min) / self._resolution).astype(int)

        # Build O(1) lookup set
        occupied_set: set[tuple[int, int, int]] = set(map(tuple, indices))

        # Find frontier voxels: occupied voxels with at least one empty neighbor
        offsets = self._get_26_offsets()
        frontier_set: set[tuple[int, int, int]] = set()

        for idx in occupied_set:
            ix, iy, iz = idx
            for dx, dy, dz in offsets:
                neighbor = (ix + dx, iy + dy, iz + dz)
                if neighbor not in occupied_set:
                    frontier_set.add(idx)
                    break

        if not frontier_set:
            return []

        # Cluster frontier voxels using BFS on 26-connectivity
        clusters = self._cluster_bfs(frontier_set, offsets)

        # Filter by min cluster size and build FrontierCluster objects
        result: list[FrontierCluster] = []
        for cluster_indices in clusters:
            if len(cluster_indices) < self._min_cluster_size:
                continue

            voxels_arr = np.array(cluster_indices, dtype=int)
            centroid_world = grid_min + np.mean(voxels_arr, axis=0) * self._resolution
            centroid_world = centroid_world.astype(np.float64)

            result.append(
                FrontierCluster(
                    centroid=centroid_world,
                    voxel_count=len(cluster_indices),
                    voxels=voxels_arr,
                )
            )

        # Sort by voxel_count descending
        result.sort(key=lambda c: c.voxel_count, reverse=True)
        return result

    @staticmethod
    def _cluster_bfs(
        frontier_set: set[tuple[int, int, int]],
        offsets: list[tuple[int, int, int]],
    ) -> list[list[tuple[int, int, int]]]:
        """Cluster frontier voxels using BFS on 26-connectivity.

        Args:
            frontier_set: Set of frontier voxel grid indices.
            offsets: 26-connected neighbor offsets.

        Returns:
            List of clusters, each a list of (ix, iy, iz) tuples.
        """
        visited: set[tuple[int, int, int]] = set()
        clusters: list[list[tuple[int, int, int]]] = []

        for idx in frontier_set:
            if idx in visited:
                continue

            # BFS from this seed
            cluster: list[tuple[int, int, int]] = []
            queue = deque([idx])

            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(current)

                cx, cy, cz = current
                for dx, dy, dz in offsets:
                    neighbor = (cx + dx, cy + dy, cz + dz)
                    if neighbor in frontier_set and neighbor not in visited:
                        queue.append(neighbor)

            if cluster:
                clusters.append(cluster)

        return clusters
