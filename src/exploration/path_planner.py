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
    and inflating obstacle costs so paths maintain clearance from walls
    and furniture (robot body is ~30cm wide).
    """

    def __init__(self, unknown_cost: float = 5.0, inflation_radius: float = 0.8):
        """Initialize planner.

        Args:
            unknown_cost: Cost multiplier for traversing UNKNOWN cells.
                Higher values discourage exploration through unknown space.
            inflation_radius: Distance in meters around obstacles where
                traversal cost is increased. Should be >= robot half-width.
        """
        self._unknown_cost = unknown_cost
        self._inflation_radius = inflation_radius
        self._inflation_cache: np.ndarray | None = None
        self._inflation_grid_id: int | None = None

    def _get_inflation_cost(self, grid: OccupancyGrid2D) -> np.ndarray:
        """Voronoi-gradient costmap: paths stay centered in corridors.

        Two layers:
        1. Binary inflation (robot half-width) -- hard impassable
        2. Voronoi gradient -- soft repulsion toward corridor centers

        Returns:
            (H, W) float array. 0 = free, >0 = cost, 1e6 = impassable.
        """
        grid_id = id(grid.grid)
        if self._inflation_grid_id == grid_id and self._inflation_cache is not None:
            return self._inflation_cache

        from src.exploration.costmap import build_costmap
        cost = build_costmap(
            grid.grid,
            resolution=grid.resolution,
            robot_half_width=0.15,
            gradient_distance=self._inflation_radius,
        )

        self._inflation_cache = cost
        self._inflation_grid_id = grid_id
        return cost

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

        # Compute inflation costmap
        inflation_cost = self._get_inflation_cost(grid)

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
                extra = float(inflation_cost[nr, nc])
                if extra >= 1e5:
                    continue  # Lethal zone — treat as impassable

                if cell_val == CELL_UNKNOWN:
                    step_cost = move_cost * self._unknown_cost + extra
                else:
                    step_cost = move_cost + extra

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

        # Smooth and resample (replaces old Nth-waypoint simplification)
        from src.exploration.path_smoother import smooth_path
        smoothed = smooth_path(path_world, resample_spacing=0.1, smoothing_window=50)

        # Always include the goal
        if len(path_world) > 0 and len(smoothed) > 0:
            if not np.allclose(smoothed[-1], path_world[-1], atol=0.2):
                smoothed.append(path_world[-1])

        return smoothed
