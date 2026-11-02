"""2D occupancy grid projected from 3D voxels for navigation.

Projects 3D occupied voxels onto a 2D XY grid within a configurable height
range. Cells are marked as FREE (near observed obstacles), OCCUPIED (voxel
present), or UNKNOWN (never observed). The resulting grid is used by the
A* PathPlanner for ground-plane navigation.
"""

from dataclasses import dataclass

import numpy as np

# Cell value constants
CELL_UNKNOWN: int = -1
CELL_FREE: int = 0
CELL_OCCUPIED: int = 100


@dataclass
class OccupancyGrid2D:
    """2D occupancy grid for navigation.

    Attributes:
        grid: (H, W) int8 array with values CELL_FREE, CELL_OCCUPIED, CELL_UNKNOWN.
        resolution: Meters per cell.
        origin: (2,) world coordinates of grid[0, 0] corner.
        width: Grid columns.
        height: Grid rows.
    """

    grid: np.ndarray  # (H, W) int8
    resolution: float
    origin: np.ndarray  # (2,) world XY of grid[0,0]
    width: int
    height: int

    def world_to_grid(self, xy: np.ndarray) -> tuple[int, int]:
        """Convert (2,) world XY to grid (row, col), clamped to bounds."""
        col = int(np.floor((xy[0] - self.origin[0]) / self.resolution + 1e-9))
        row = int(np.floor((xy[1] - self.origin[1]) / self.resolution + 1e-9))
        # Clamp to grid bounds
        row = max(0, min(row, self.height - 1))
        col = max(0, min(col, self.width - 1))
        return row, col

    def grid_to_world(self, row: int, col: int) -> np.ndarray:
        """Convert grid (row, col) to (2,) world XY cell center."""
        x = self.origin[0] + (col + 0.5) * self.resolution
        y = self.origin[1] + (row + 0.5) * self.resolution
        return np.array([x, y], dtype=np.float64)

    def is_free(self, row: int, col: int) -> bool:
        """True if cell is CELL_FREE and within bounds."""
        if row < 0 or row >= self.height or col < 0 or col >= self.width:
            return False
        return int(self.grid[row, col]) == CELL_FREE


def project_voxels_to_2d(
    occupied_voxels: np.ndarray,
    resolution: float,
    z_min: float = 0.0,
    z_max: float = 2.0,
    padding: int = 30,
    robot_positions: np.ndarray | None = None,
    observed_free_xy: np.ndarray | None = None,
) -> OccupancyGrid2D:
    """Project 3D occupied voxels to a 2D occupancy grid for navigation.

    Filters voxels by height range, projects to XY plane, marks cells as
    OCCUPIED where voxels exist, and dilates FREE space around obstacles.
    Robot trajectory positions are also stamped as FREE to ensure the
    robot's known-navigable path is always connected.

    Args:
        occupied_voxels: (N, 3) float64 voxel centers.
        resolution: Grid cell size in meters.
        z_min: Minimum height to include.
        z_max: Maximum height to include.
        padding: Extra cells on each side of bounding box.
        robot_positions: (M, 3) float64 positions the robot has visited.
            These are stamped as FREE cells with a small dilation radius,
            ensuring the robot's path is always navigable.
        observed_free_xy: XY samples classified as floor before scan accumulation.
            Occupied columns take precedence over these free observations.

    Returns:
        OccupancyGrid2D with FREE/OCCUPIED/UNKNOWN cells.
    """
    def _empty_grid() -> OccupancyGrid2D:
        return OccupancyGrid2D(
            grid=np.full((1, 1), CELL_UNKNOWN, dtype=np.int8),
            resolution=resolution,
            origin=np.array([0.0, 0.0]),
            width=1,
            height=1,
        )

    # Floor separation belongs to individual observations before accumulation.
    # Never erase the most populated voxel layer: it may be a low obstacle.
    free_xy = np.empty((0, 2)) if observed_free_xy is None else np.asarray(observed_free_xy)[:, :2]
    mask = (occupied_voxels[:, 2] >= z_min) & (occupied_voxels[:, 2] <= z_max)
    xy = occupied_voxels[mask, :2]
    support = np.concatenate((xy, free_xy))
    if not len(support):
        return _empty_grid()
    xy_min = np.floor(support.min(axis=0) / resolution) * resolution - padding * resolution
    xy_max = np.ceil(support.max(axis=0) / resolution) * resolution + padding * resolution

    cols = int(np.ceil((xy_max[0] - xy_min[0]) / resolution)) + 1
    rows = int(np.ceil((xy_max[1] - xy_min[1]) / resolution)) + 1

    origin = xy_min.copy()

    # Initialize grid as UNKNOWN
    grid = np.full((rows, cols), CELL_UNKNOWN, dtype=np.int8)

    # Observed floor is free only where no obstacle occupies the same column.
    free_cells = np.floor((free_xy - origin) / resolution + 1e-9).astype(int)
    if len(free_cells):
        grid[free_cells[:, 1], free_cells[:, 0]] = CELL_FREE

    # Mark occupied cells
    grid_cols = np.floor((xy[:, 0] - origin[0]) / resolution + 1e-9).astype(int)
    grid_rows = np.floor((xy[:, 1] - origin[1]) / resolution + 1e-9).astype(int)

    # Clamp to grid bounds
    grid_cols = np.clip(grid_cols, 0, cols - 1)
    grid_rows = np.clip(grid_rows, 0, rows - 1)

    for r, c in zip(grid_rows, grid_cols):
        grid[r, c] = CELL_OCCUPIED

    # Stamp robot trajectory as FREE -- the robot was physically there
    # Use a small dilation (robot width ~0.3m = 3 cells at 0.1m) to create
    # a navigable corridor along the robot's path
    if robot_positions is not None and len(robot_positions) > 0:
        rob_xy = robot_positions[:, :2]
        rob_cols = np.floor((rob_xy[:, 0] - origin[0]) / resolution + 1e-9).astype(int)
        rob_rows = np.floor((rob_xy[:, 1] - origin[1]) / resolution + 1e-9).astype(int)
        rob_cols = np.clip(rob_cols, 0, cols - 1)
        rob_rows = np.clip(rob_rows, 0, rows - 1)

        robot_radius = max(1, int(0.3 / resolution))  # ~robot half-width
        for r, c in zip(rob_rows, rob_cols):
            for dr in range(-robot_radius, robot_radius + 1):
                for dc in range(-robot_radius, robot_radius + 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if grid[nr, nc] != CELL_OCCUPIED:
                            grid[nr, nc] = CELL_FREE

    # Dilate FREE space around obstacles
    # For each occupied cell, mark nearby UNKNOWN cells as FREE
    dilation_rounds = max(3, int(0.5 / resolution))  # ~0.5m free space around obstacles
    occupied_mask = grid == CELL_OCCUPIED

    for _ in range(dilation_rounds):
        # Find cells that are neighbors of FREE or OCCUPIED cells
        new_free = np.zeros_like(grid, dtype=bool)

        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                # Shift the occupied/free mask
                r_start = max(0, dr)
                r_end = rows + min(0, dr)
                c_start = max(0, dc)
                c_end = cols + min(0, dc)

                src_r_start = max(0, -dr)
                src_r_end = rows + min(0, -dr)
                src_c_start = max(0, -dc)
                src_c_end = cols + min(0, -dc)

                # Cells adjacent to occupied or free cells
                source = (occupied_mask[src_r_start:src_r_end, src_c_start:src_c_end] |
                          (grid[src_r_start:src_r_end, src_c_start:src_c_end] == CELL_FREE))
                new_free[r_start:r_end, c_start:c_end] |= source

        # Only mark UNKNOWN cells as FREE (don't overwrite OCCUPIED)
        free_mask = new_free & (grid == CELL_UNKNOWN)
        grid[free_mask] = CELL_FREE

    return OccupancyGrid2D(
        grid=grid,
        resolution=resolution,
        origin=origin,
        width=cols,
        height=rows,
    )
