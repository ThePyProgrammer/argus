"""A* path planning on 2D occupancy grid.

Finds shortest paths on OccupancyGrid2D using A* with 8-connected neighbors
and octile distance heuristic. Returns world-coordinate waypoints suitable
for the WaypointRunner. Adapted from the DimOS min_cost_astar() pattern.
"""

import heapq
import math

import numpy as np

from src.exploration.occupancy_grid import CELL_FREE, CELL_OCCUPIED, CELL_UNKNOWN, OccupancyGrid2D

# Diagonal movement cost
_SQRT2 = math.sqrt(2)

# 8-connected neighbor offsets: (dr, dc, cost)
_NEIGHBORS_8: list[tuple[int, int, float]] = [
    (-1, 0, 1.0),   # up
    (1, 0, 1.0),    # down
    (0, -1, 1.0),   # left
    (0, 1, 1.0),    # right
    (-1, -1, _SQRT2),  # up-left
    (-1, 1, _SQRT2),   # up-right
    (1, -1, _SQRT2),   # down-left
    (1, 1, _SQRT2),    # down-right
]


def _octile_heuristic(r1: int, c1: int, r2: int, c2: int) -> float:
    """Octile distance heuristic for A* on 8-connected grid.

    h = max(|dr|, |dc|) + (sqrt(2) - 1) * min(|dr|, |dc|)
    """
    dr = abs(r1 - r2)
    dc = abs(c1 - c2)
    return max(dr, dc) + (_SQRT2 - 1.0) * min(dr, dc)


class PathPlanner:
    """A* path planner on 2D occupancy grid.

    Plans paths avoiding OCCUPIED cells, penalizing UNKNOWN cells,
    and returning world-coordinate waypoints.
    """

    def __init__(self, unknown_cost: float = 5.0):
        """Initialize planner.

        Args:
            unknown_cost: Cost multiplier for traversing UNKNOWN cells.
                Higher values discourage exploration through unknown space.
        """
        self._unknown_cost = unknown_cost

    def plan(
        self,
        start_world: np.ndarray,
        goal_world: np.ndarray,
        grid: OccupancyGrid2D,
    ) -> list[np.ndarray] | None:
        """Plan a path from start to goal on the occupancy grid.

        Args:
            start_world: (3,) or (2,) world coordinates of start position.
            goal_world: (3,) or (2,) world coordinates of goal position.
            grid: OccupancyGrid2D to plan on.

        Returns:
            List of (3,) float64 waypoints in world coordinates (Z=0.0),
            or None if no path found. Single-element list if start == goal.
        """
        start_xy = start_world[:2]
        goal_xy = goal_world[:2]

        start_row, start_col = grid.world_to_grid(start_xy)
        goal_row, goal_col = grid.world_to_grid(goal_xy)

        # The robot's current position is always navigable (it's physically there),
        # even if the grid marks it as OCCUPIED due to ground voxels.
        # Only reject if the GOAL is occupied (can't drive into a wall).
        if grid.grid[goal_row, goal_col] == CELL_OCCUPIED:
            return None

        # Start == goal: return single waypoint
        if start_row == goal_row and start_col == goal_col:
            xy = grid.grid_to_world(start_row, start_col)
            return [np.array([xy[0], xy[1], 0.0], dtype=np.float64)]

        # A* search
        # Priority queue: (f_cost, counter, row, col)
        counter = 0
        open_set: list[tuple[float, int, int, int]] = []
        h = _octile_heuristic(start_row, start_col, goal_row, goal_col)
        heapq.heappush(open_set, (h, counter, start_row, start_col))
        counter += 1

        g_cost: dict[tuple[int, int], float] = {(start_row, start_col): 0.0}
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        closed: set[tuple[int, int]] = set()

        while open_set:
            _, _, cr, cc = heapq.heappop(open_set)
            current = (cr, cc)

            if current in closed:
                continue
            closed.add(current)

            # Goal reached
            if cr == goal_row and cc == goal_col:
                return self._reconstruct_path(came_from, current, grid)

            for dr, dc, move_cost in _NEIGHBORS_8:
                nr, nc = cr + dr, cc + dc

                # Bounds check
                if nr < 0 or nr >= grid.height or nc < 0 or nc >= grid.width:
                    continue

                neighbor = (nr, nc)
                if neighbor in closed:
                    continue

                cell_val = int(grid.grid[nr, nc])

                # OCCUPIED cells are impassable
                if cell_val == CELL_OCCUPIED:
                    continue

                # Compute cost for this cell
                if cell_val == CELL_UNKNOWN:
                    step_cost = move_cost * self._unknown_cost
                else:
                    step_cost = move_cost

                tentative_g = g_cost[current] + step_cost

                if tentative_g < g_cost.get(neighbor, float("inf")):
                    g_cost[neighbor] = tentative_g
                    came_from[neighbor] = current
                    h = _octile_heuristic(nr, nc, goal_row, goal_col)
                    f = tentative_g + h
                    heapq.heappush(open_set, (f, counter, nr, nc))
                    counter += 1

        # No path found
        return None

    def _reconstruct_path(
        self,
        came_from: dict[tuple[int, int], tuple[int, int]],
        goal: tuple[int, int],
        grid: OccupancyGrid2D,
    ) -> list[np.ndarray]:
        """Reconstruct and simplify path from A* result.

        Converts grid path to world coordinates, simplifies by keeping
        every Nth waypoint to produce coarse waypoints ~1m apart.
        """
        # Reconstruct full grid path
        path_grid: list[tuple[int, int]] = [goal]
        current = goal
        while current in came_from:
            current = came_from[current]
            path_grid.append(current)
        path_grid.reverse()

        # Convert to world coordinates
        path_world: list[np.ndarray] = []
        for row, col in path_grid:
            xy = grid.grid_to_world(row, col)
            path_world.append(np.array([xy[0], xy[1], 0.0], dtype=np.float64))

        # Simplify: keep every Nth waypoint (~1m apart)
        step = max(1, int(1.0 / grid.resolution))
        simplified: list[np.ndarray] = []
        for i in range(0, len(path_world), step):
            simplified.append(path_world[i])

        # Always include the goal
        if len(path_world) > 0 and (len(simplified) == 0 or
                not np.array_equal(simplified[-1], path_world[-1])):
            simplified.append(path_world[-1])

        return simplified
