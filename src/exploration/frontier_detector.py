"""Frontier detection on 2D occupancy grid.

A frontier cell is a FREE cell adjacent to at least one UNKNOWN cell --
the boundary between explored navigable space and unexplored territory.
This correctly handles enclosed environments (offices, rooms) where walls
are OCCUPIED and should NOT be frontiers.

Previous approach (3D voxel boundary) treated wall edges as frontiers,
causing the robot to immediately declare "all explored" in office scenes.

Frontier cells are clustered via BFS and filtered by minimum cluster size.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from src.exploration.occupancy_grid import OccupancyGrid2D, CELL_FREE, CELL_UNKNOWN, CELL_OCCUPIED


@dataclass
class FrontierCluster:
    """A cluster of frontier cells on the boundary of explored space.

    Attributes:
        centroid: (3,) float64 world coordinates of cluster center (z=0).
        voxel_count: Number of cells in this cluster.
        voxels: (K, 2) int grid indices (row, col) of cluster cells.
    """

    centroid: np.ndarray  # (3,) float64 world coordinates
    voxel_count: int
    voxels: np.ndarray  # (K, 2) int grid indices


# 8-connected neighbor offsets for 2D grid
_OFFSETS_8: list[tuple[int, int]] = [
    (-1, -1), (-1, 0), (-1, 1),
    (0, -1),           (0, 1),
    (1, -1),  (1, 0),  (1, 1),
]


class FrontierDetector:
    """Detect frontier cells on a 2D occupancy grid.

    A frontier is a FREE cell with at least one UNKNOWN 8-connected
    neighbor. Frontiers are clustered via BFS and filtered by minimum
    cluster size.
    """

    def __init__(self, resolution: float = 0.1, min_cluster_size: int = 3):
        self._resolution = resolution
        self._min_cluster_size = min_cluster_size

    def detect(
        self, occupied_voxels: np.ndarray,
        grid_2d: OccupancyGrid2D | None = None,
    ) -> list[FrontierCluster]:
        """Detect frontier clusters.

        Args:
            occupied_voxels: (N, 3) float64 voxel centers (used to build
                grid if grid_2d not provided).
            grid_2d: Pre-built 2D occupancy grid. If None, one is built
                from occupied_voxels using default parameters.

        Returns:
            List of FrontierCluster sorted by voxel_count descending.
        """
        if grid_2d is None:
            from src.exploration.occupancy_grid import project_voxels_to_2d
            grid_2d = project_voxels_to_2d(
                occupied_voxels, self._resolution,
            )

        grid = grid_2d.grid
        rows, cols = grid.shape

        # Find frontier cells: FREE cells with at least one UNKNOWN neighbor
        frontier_cells: set[tuple[int, int]] = set()

        # Vectorized: find all FREE cells
        free_mask = grid == CELL_FREE
        free_rows, free_cols = np.where(free_mask)

        for r, c in zip(free_rows, free_cols):
            for dr, dc in _OFFSETS_8:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    if grid[nr, nc] == CELL_UNKNOWN:
                        frontier_cells.add((int(r), int(c)))
                        break

        if not frontier_cells:
            return []

        # Cluster via BFS
        clusters = self._cluster_bfs(frontier_cells)

        # Build FrontierCluster objects
        result: list[FrontierCluster] = []
        for cluster_cells in clusters:
            if len(cluster_cells) < self._min_cluster_size:
                continue

            cells_arr = np.array(cluster_cells, dtype=int)
            # Compute centroid in world coordinates
            mean_row = np.mean(cells_arr[:, 0])
            mean_col = np.mean(cells_arr[:, 1])
            cx = grid_2d.origin[0] + (mean_col + 0.5) * grid_2d.resolution
            cy = grid_2d.origin[1] + (mean_row + 0.5) * grid_2d.resolution

            result.append(
                FrontierCluster(
                    centroid=np.array([cx, cy, 0.0], dtype=np.float64),
                    voxel_count=len(cluster_cells),
                    voxels=cells_arr,
                )
            )

        result.sort(key=lambda c: c.voxel_count, reverse=True)
        return result

    @staticmethod
    def _cluster_bfs(
        frontier_cells: set[tuple[int, int]],
    ) -> list[list[tuple[int, int]]]:
        """Cluster frontier cells using BFS on 8-connectivity."""
        visited: set[tuple[int, int]] = set()
        clusters: list[list[tuple[int, int]]] = []

        for cell in frontier_cells:
            if cell in visited:
                continue

            cluster: list[tuple[int, int]] = []
            queue = deque([cell])

            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(current)

                r, c = current
                for dr, dc in _OFFSETS_8:
                    neighbor = (r + dr, c + dc)
                    if neighbor in frontier_cells and neighbor not in visited:
                        queue.append(neighbor)

            if cluster:
                clusters.append(cluster)

        return clusters
