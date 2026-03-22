"""Tests for OccupancyGrid2D projection and A* PathPlanner.

Verifies 2D occupancy grid projection from 3D voxels and A* pathfinding
on the projected grid with world-coordinate waypoint output.
"""

import numpy as np
import pytest

from src.exploration.occupancy_grid import (
    CELL_FREE,
    CELL_OCCUPIED,
    CELL_UNKNOWN,
    OccupancyGrid2D,
    project_voxels_to_2d,
)
from src.exploration.path_planner import PathPlanner


# ---------- OccupancyGrid2D tests ----------


class TestOccupancyGrid2D:
    """Tests for OccupancyGrid2D and project_voxels_to_2d."""

    def test_empty_voxels_produce_small_grid(self):
        """Empty voxels produce a small grid with CELL_UNKNOWN."""
        empty = np.empty((0, 3), dtype=np.float64)
        grid = project_voxels_to_2d(empty, resolution=0.1)
        assert grid.grid.shape == (1, 1)
        assert grid.grid[0, 0] == CELL_UNKNOWN

    def test_single_row_projects_occupied(self):
        """Single row of voxels at z=0.5 projects to occupied cells."""
        # 5 voxels in a row along X axis at z=0.5
        voxels = np.array([
            [0.0, 0.0, 0.5],
            [0.1, 0.0, 0.5],
            [0.2, 0.0, 0.5],
            [0.3, 0.0, 0.5],
            [0.4, 0.0, 0.5],
        ], dtype=np.float64)
        grid = project_voxels_to_2d(voxels, resolution=0.1, z_min=0.0, z_max=2.0)

        # Check that occupied cells exist in the grid
        assert np.any(grid.grid == CELL_OCCUPIED)

    def test_voxels_outside_z_range_excluded(self):
        """Voxels outside z_min/z_max range are excluded."""
        voxels = np.array([
            [0.0, 0.0, 5.0],  # z=5.0, above z_max=2.0
            [0.1, 0.0, 5.0],
            [0.2, 0.0, 5.0],
        ], dtype=np.float64)
        grid = project_voxels_to_2d(voxels, resolution=0.1, z_min=0.0, z_max=2.0)

        # All voxels filtered, should get small UNKNOWN grid
        assert grid.grid.shape == (1, 1)
        assert grid.grid[0, 0] == CELL_UNKNOWN

    def test_grid_has_correct_properties(self):
        """Grid has correct origin, resolution, and dimensions."""
        voxels = np.array([
            [1.0, 2.0, 0.5],
            [1.5, 2.5, 0.5],
            [2.0, 3.0, 0.5],
        ], dtype=np.float64)
        grid = project_voxels_to_2d(voxels, resolution=0.1, z_min=0.0, z_max=2.0, padding=5)

        assert grid.resolution == 0.1
        assert grid.origin.shape == (2,)
        assert grid.width == grid.grid.shape[1]
        assert grid.height == grid.grid.shape[0]
        assert grid.width > 0
        assert grid.height > 0

    def test_world_to_grid_round_trip(self):
        """world_to_grid and grid_to_world are approximate inverses."""
        grid = OccupancyGrid2D(
            grid=np.zeros((20, 20), dtype=np.int8),
            resolution=0.5,
            origin=np.array([0.0, 0.0]),
            width=20,
            height=20,
        )

        # Convert world -> grid -> world
        world_pt = np.array([3.25, 4.75])
        row, col = grid.world_to_grid(world_pt)
        back = grid.grid_to_world(row, col)

        # Should be within half a cell of the original
        assert abs(back[0] - world_pt[0]) < grid.resolution
        assert abs(back[1] - world_pt[1]) < grid.resolution

    def test_is_free(self):
        """is_free returns True for FREE cells and False otherwise."""
        g = np.full((5, 5), CELL_UNKNOWN, dtype=np.int8)
        g[2, 2] = CELL_FREE
        g[3, 3] = CELL_OCCUPIED
        grid = OccupancyGrid2D(
            grid=g, resolution=0.1, origin=np.array([0.0, 0.0]), width=5, height=5
        )
        assert grid.is_free(2, 2) is True
        assert grid.is_free(3, 3) is False
        assert grid.is_free(0, 0) is False  # UNKNOWN
        assert grid.is_free(-1, 0) is False  # out of bounds


# ---------- PathPlanner tests ----------


def _make_free_grid(rows: int, cols: int, resolution: float = 0.5) -> OccupancyGrid2D:
    """Create an all-FREE grid."""
    g = np.full((rows, cols), CELL_FREE, dtype=np.int8)
    return OccupancyGrid2D(
        grid=g,
        resolution=resolution,
        origin=np.array([0.0, 0.0]),
        width=cols,
        height=rows,
    )


def _make_walled_grid(
    rows: int, cols: int, wall_row: int, gap_col: int, resolution: float = 0.5
) -> OccupancyGrid2D:
    """Create a FREE grid with a wall at wall_row and a gap at gap_col."""
    g = np.full((rows, cols), CELL_FREE, dtype=np.int8)
    g[wall_row, :] = CELL_OCCUPIED
    g[wall_row, gap_col] = CELL_FREE  # gap
    return OccupancyGrid2D(
        grid=g,
        resolution=resolution,
        origin=np.array([0.0, 0.0]),
        width=cols,
        height=rows,
    )


class TestPathPlanner:
    """Tests for A* PathPlanner."""

    def test_path_free_grid(self):
        """Path from start to goal on empty (all FREE) grid returns waypoint list."""
        grid = _make_free_grid(20, 20, resolution=0.5)
        planner = PathPlanner()

        start = np.array([1.0, 1.0, 0.0])
        goal = np.array([8.0, 8.0, 0.0])
        path = planner.plan(start, goal, grid)

        assert path is not None
        assert len(path) >= 2  # at least start and goal
        # First waypoint near start, last near goal
        assert np.linalg.norm(path[0][:2] - start[:2]) < 1.0
        assert np.linalg.norm(path[-1][:2] - goal[:2]) < 1.0

    def test_path_blocked(self):
        """Path blocked by full OCCUPIED wall returns None."""
        g = np.full((20, 20), CELL_FREE, dtype=np.int8)
        g[10, :] = CELL_OCCUPIED  # solid wall, no gap
        grid = OccupancyGrid2D(
            grid=g, resolution=0.5, origin=np.array([0.0, 0.0]), width=20, height=20
        )
        planner = PathPlanner()

        start = np.array([2.0, 2.0, 0.0])  # above wall
        goal = np.array([2.0, 8.0, 0.0])   # below wall
        path = planner.plan(start, goal, grid)

        assert path is None

    def test_path_through_gap(self):
        """Path through narrow gap in wall succeeds."""
        grid = _make_walled_grid(20, 20, wall_row=10, gap_col=10, resolution=0.5)
        planner = PathPlanner()

        start = np.array([2.0, 2.0, 0.0])
        goal = np.array([2.0, 8.0, 0.0])
        path = planner.plan(start, goal, grid)

        assert path is not None
        assert len(path) >= 2

    def test_start_equals_goal(self):
        """Start == goal returns single-element path."""
        grid = _make_free_grid(20, 20, resolution=0.5)
        planner = PathPlanner()

        point = np.array([5.0, 5.0, 0.0])
        path = planner.plan(point, point, grid)

        assert path is not None
        assert len(path) == 1

    def test_waypoints_are_world_coordinates(self):
        """Waypoints are (3,) float64 arrays in world coordinates."""
        grid = _make_free_grid(20, 20, resolution=0.5)
        planner = PathPlanner()

        start = np.array([1.0, 1.0, 0.0])
        goal = np.array([5.0, 5.0, 0.0])
        path = planner.plan(start, goal, grid)

        assert path is not None
        for wp in path:
            assert wp.shape == (3,)
            assert wp.dtype == np.float64
            # Z should be 0.0 (ground-plane navigation)
            assert wp[2] == 0.0

    def test_start_on_occupied_finds_path(self):
        """Robot can start from OCCUPIED cell (it's physically there)."""
        g = np.full((20, 20), CELL_FREE, dtype=np.int8)
        g[0, 0] = CELL_OCCUPIED
        grid = OccupancyGrid2D(
            grid=g, resolution=0.5, origin=np.array([0.0, 0.0]), width=20, height=20
        )
        planner = PathPlanner()
        start = np.array([0.25, 0.25, 0.0])  # maps to cell (0,0) which is occupied
        goal = np.array([5.0, 5.0, 0.0])
        path = planner.plan(start, goal, grid)
        assert path is not None
