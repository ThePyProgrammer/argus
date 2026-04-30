"""Voronoi-gradient costmap for safe path planning.

Two-layer approach (adapted from DimOS):
1. Binary inflation: dilate obstacles by robot half-width (hard impassable)
2. Voronoi gradient: push paths toward corridor centers (soft repulsion)

The result is a costmap where A* naturally produces paths that stay
centered in corridors and maintain clearance from all obstacles.
"""


import numpy as np
from scipy.ndimage import distance_transform_edt, label


def build_costmap(
    grid: np.ndarray,
    resolution: float,
    robot_half_width: float = 0.15,
    gradient_distance: float = 1.5,
) -> np.ndarray:
    """Build a Voronoi-gradient costmap from an occupancy grid.

    Args:
        grid: (H, W) int8 grid with CELL_OCCUPIED=100, CELL_FREE=0, CELL_UNKNOWN=-1.
        resolution: Meters per cell.
        robot_half_width: Hard lethal zone radius in meters.
        gradient_distance: Soft repulsion distance in meters.

    Returns:
        (H, W) float32 costmap. 0 = free, >0 = cost, 1e6 = impassable.
    """
    occupied = grid == 100  # CELL_OCCUPIED
    if not np.any(occupied):
        return np.zeros(grid.shape, dtype=np.float32)

    # Step 1: Binary inflation (hard lethal zone)
    dist_to_occupied = distance_transform_edt(~occupied) * resolution
    inflated = occupied | (dist_to_occupied <= robot_half_width)

    costmap = np.zeros(grid.shape, dtype=np.float32)
    costmap[inflated] = 1e6  # impassable

    # Step 2: Voronoi gradient (soft repulsion toward corridor centers)
    # Distance from each free cell to nearest obstacle
    dist_to_obstacle = distance_transform_edt(~inflated) * resolution

    # Voronoi edges: where the nearest obstacle label changes
    # Label connected obstacle regions
    labeled, n_labels = label(inflated)

    if n_labels >= 2:
        # For each cell, find which obstacle cluster is nearest
        # Cells on the Voronoi boundary are equidistant from 2+ clusters
        # = corridor centers
        dist_to_voronoi = _voronoi_distance(labeled, inflated, resolution)

        # Cost: high near obstacles, low on Voronoi skeleton
        # Formula from DimOS: cost = max_cost * d_voronoi / (d_obstacle + d_voronoi)
        max_grad_cells = int(gradient_distance / resolution)
        grad_mask = (dist_to_obstacle > 0) & (dist_to_obstacle < gradient_distance) & (~inflated)

        if np.any(grad_mask):
            d_obs = dist_to_obstacle[grad_mask]
            d_vor = dist_to_voronoi[grad_mask]
            # Avoid division by zero
            total = d_obs + d_vor + 1e-6
            costmap[grad_mask] = np.clip(50.0 * d_vor / total, 0, 50).astype(np.float32)
    else:
        # Fallback: simple distance-based gradient if only one obstacle cluster
        grad_mask = (dist_to_obstacle > 0) & (dist_to_obstacle < gradient_distance) & (~inflated)
        if np.any(grad_mask):
            normalized = 1.0 - dist_to_obstacle[grad_mask] / gradient_distance
            costmap[grad_mask] = (50.0 * normalized).astype(np.float32)

    return costmap


def _voronoi_distance(
    labeled: np.ndarray,
    inflated: np.ndarray,
    resolution: float,
) -> np.ndarray:
    """Compute distance from each cell to the nearest Voronoi edge.

    Voronoi edges are where the nearest-obstacle-label changes between
    adjacent cells. Cells on these edges are equidistant from two
    different obstacle clusters = corridor/doorway centers.

    Args:
        labeled: (H, W) int array of obstacle cluster labels.
        inflated: (H, W) bool array of inflated obstacles.
        resolution: Meters per cell.

    Returns:
        (H, W) float64 distance to nearest Voronoi edge in meters.
    """
    h, w = labeled.shape

    # Find nearest obstacle label for each free cell using EDT trick:
    # For each label, compute distance to that label's obstacles
    # Then find which label is nearest for each cell
    free_mask = ~inflated
    nearest_label = np.zeros((h, w), dtype=int)

    if np.any(free_mask):
        # Propagate labels from obstacles to free space
        # Use the labeled array directly -- each obstacle cell has its label
        # For free cells, find the nearest labeled obstacle cell
        from scipy.ndimage import maximum_filter, minimum_filter

        # Expand labels into free space using iterative dilation
        expanded = labeled.copy()
        for _ in range(max(h, w)):
            new = maximum_filter(expanded, size=3)
            # Only fill cells that are still unlabeled (0) and free
            fill_mask = (expanded == 0) & free_mask
            if not np.any(fill_mask):
                break
            expanded[fill_mask] = new[fill_mask]

        nearest_label = expanded

    # Voronoi edges: cells where at least one neighbor has a different label
    voronoi_edge = np.zeros((h, w), dtype=bool)
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.roll(np.roll(nearest_label, dr, axis=0), dc, axis=1)
        voronoi_edge |= (nearest_label != shifted) & (nearest_label > 0) & (shifted > 0)

    # Distance from each cell to nearest Voronoi edge
    if np.any(voronoi_edge):
        dist = distance_transform_edt(~voronoi_edge) * resolution
    else:
        # No Voronoi edges (single obstacle cluster) -- return large distance
        dist = np.full((h, w), 100.0)

    return dist
