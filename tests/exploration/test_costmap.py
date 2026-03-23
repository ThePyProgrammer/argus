"""Tests for src/exploration/costmap.py -- Voronoi-gradient costmap builder."""

import numpy as np
import pytest

from src.exploration.costmap import build_costmap


# ------------------------------------------------------------------ #
# Constants matching costmap.py
# ------------------------------------------------------------------ #

CELL_FREE = 0
CELL_OCCUPIED = 100
CELL_UNKNOWN = -1
IMPASSABLE = 1e6


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestBuildCostmap:
    """build_costmap inflates obstacles and produces a navigable costmap."""

    def test_inflation_radius_covers_obstacle_neighbors(self):
        """Cells within robot_half_width of an obstacle are marked impassable."""
        resolution = 0.1
        robot_half_width = 0.15  # should inflate by 1 cell (ceil(0.15/0.1)=1, but max(1,...))

        # 10x10 grid, all free except one occupied cell at center
        grid = np.full((10, 10), CELL_FREE, dtype=np.int8)
        grid[5, 5] = CELL_OCCUPIED

        costmap = build_costmap(grid, resolution, robot_half_width=robot_half_width)

        # The occupied cell itself should be impassable
        assert costmap[5, 5] == IMPASSABLE

        # Immediate neighbors (within inflate_cells=1) should also be impassable
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                r, c = 5 + dr, 5 + dc
                assert costmap[r, c] == IMPASSABLE, (
                    f"Cell ({r},{c}) should be inflated to impassable"
                )

    def test_free_cells_far_from_obstacles_remain_navigable(self):
        """Cells far from any obstacle have zero or near-zero cost."""
        resolution = 0.1
        robot_half_width = 0.15

        # 20x20 grid with one obstacle at corner
        grid = np.full((20, 20), CELL_FREE, dtype=np.int8)
        grid[0, 0] = CELL_OCCUPIED

        costmap = build_costmap(
            grid, resolution,
            robot_half_width=robot_half_width,
            gradient_distance=0.5,
        )

        # Far corner should be free (no inflation, no gradient)
        assert costmap[19, 19] == 0.0, "Far cell should have zero cost"
        assert costmap[15, 15] == 0.0, "Distant cell should have zero cost"

    def test_larger_inflation_radius(self):
        """Increasing robot_half_width inflates a larger region."""
        resolution = 0.1
        grid = np.full((20, 20), CELL_FREE, dtype=np.int8)
        grid[10, 10] = CELL_OCCUPIED

        small_costmap = build_costmap(grid, resolution, robot_half_width=0.1)
        large_costmap = build_costmap(grid, resolution, robot_half_width=0.3)

        small_impassable = np.sum(small_costmap >= IMPASSABLE)
        large_impassable = np.sum(large_costmap >= IMPASSABLE)

        assert large_impassable > small_impassable, (
            "Larger robot_half_width should inflate more cells"
        )

    def test_edge_cells_at_grid_boundary(self):
        """Obstacle at grid edge inflates correctly without index errors."""
        resolution = 0.1
        robot_half_width = 0.15

        # Obstacle at corner (0, 0)
        grid = np.full((10, 10), CELL_FREE, dtype=np.int8)
        grid[0, 0] = CELL_OCCUPIED

        costmap = build_costmap(grid, resolution, robot_half_width=robot_half_width)

        # Should not crash, and corner should be impassable
        assert costmap[0, 0] == IMPASSABLE
        # Output shape should match input
        assert costmap.shape == grid.shape

    def test_obstacle_at_last_row_col(self):
        """Obstacle at the far edge (last row, last col) inflates without error."""
        resolution = 0.1
        grid = np.full((10, 10), CELL_FREE, dtype=np.int8)
        grid[9, 9] = CELL_OCCUPIED

        costmap = build_costmap(grid, resolution, robot_half_width=0.15)

        assert costmap[9, 9] == IMPASSABLE
        assert costmap.shape == (10, 10)

    def test_all_free_grid_produces_zero_costmap(self):
        """Grid with no obstacles produces all-zero costmap."""
        resolution = 0.1
        grid = np.full((10, 10), CELL_FREE, dtype=np.int8)

        costmap = build_costmap(grid, resolution, robot_half_width=0.15)

        np.testing.assert_array_equal(costmap, 0.0)

    def test_output_dtype_is_float32(self):
        """Costmap output is float32."""
        grid = np.full((5, 5), CELL_FREE, dtype=np.int8)
        grid[2, 2] = CELL_OCCUPIED

        costmap = build_costmap(grid, resolution=0.1)

        assert costmap.dtype == np.float32

    def test_unknown_cells_treated_as_free(self):
        """Unknown cells (-1) are not treated as obstacles."""
        resolution = 0.1
        grid = np.full((10, 10), CELL_UNKNOWN, dtype=np.int8)

        costmap = build_costmap(grid, resolution, robot_half_width=0.15)

        # No occupied cells, so nothing should be impassable
        assert np.all(costmap < IMPASSABLE)
