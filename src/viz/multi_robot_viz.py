"""Multi-robot Rerun dashboard with split-panel layout.

Renders merged 3D map, per-robot camera panels, fading trajectory
trails, coverage heatmap, Voronoi boundary plane, and stats HUD
using Rerun's Blueprint API for programmatic layout control.
"""

import time

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

# Robot color scheme: blue for A, orange for B (colorblind-friendly)
ROBOT_COLORS: dict[str, tuple[int, int, int]] = {
    "robot_a": (66, 133, 244),   # Blue
    "robot_b": (255, 152, 0),    # Orange
}

MAX_TRAIL_SEGMENTS = 50
VORONOI_PLANE_HEIGHT = 5.0
VORONOI_PLANE_HALF_WIDTH = 20.0
VORONOI_PLANE_ALPHA = 80
HEATMAP_RESOLUTION = 0.1


class MultiRobotVisualizer:
    """Multi-robot dashboard with split-panel Rerun layout.

    Creates a Rerun viewer with:
    - Top row: Merged 3D map view + stats HUD
    - Bottom row: Per-robot camera and local cloud panels

    Usage::

        viz = MultiRobotVisualizer()
        viz.update(
            merged_voxels=merged_pts,
            robot_data={"robot_a": {...}, "robot_b": {...}},
            total_coverage=65.0,
            merge_count=3,
        )
    """

    def __init__(self, app_name: str = "multi_robot_viz") -> None:
        """Initialize Rerun recording, send blueprint, start timer.

        Args:
            app_name: Application name shown in the Rerun viewer title bar.
        """
        rr.init(app_name, spawn=True)
        # MuJoCo uses Z-up coordinate system
        rr.log("/", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
        blueprint = self._create_blueprint()
        rr.send_blueprint(blueprint)
        self._start_time = time.monotonic()

    def _create_blueprint(self) -> rrb.Blueprint:
        """Create split-panel blueprint layout.

        Returns:
            Blueprint with top row (merged 3D + stats) and bottom row
            (robot_a + robot_b panels).
        """
        return rrb.Blueprint(
            rrb.Vertical(
                rrb.Horizontal(
                    rrb.Spatial3DView(
                        name="Merged 3D Map",
                        origin="/merged",
                    ),
                    rrb.TextDocumentView(
                        name="Stats",
                        origin="/stats",
                    ),
                    column_shares=[4, 1],
                ),
                rrb.Horizontal(
                    rrb.Spatial3DView(
                        name="Robot A",
                        origin="/robot_a",
                    ),
                    rrb.Spatial3DView(
                        name="Robot B",
                        origin="/robot_b",
                    ),
                    column_shares=[1, 1],
                ),
                row_shares=[3, 1],
            ),
            collapse_panels=True,
        )

    def update(
        self,
        merged_voxels: np.ndarray,
        robot_data: dict,
        frontier_cells: np.ndarray | None = None,
        voronoi_midpoint: np.ndarray | None = None,
        voronoi_direction: np.ndarray | None = None,
        total_coverage: float = 0.0,
        merge_count: int = 0,
    ) -> None:
        """Update all dashboard panels in one call.

        Args:
            merged_voxels: (N, 3) float array of merged map voxel positions.
            robot_data: Dict keyed by robot_id, each containing:
                - frame: object with .rgb (H, W, 3) uint8
                - local_voxels: (M, 3) float array
                - pose: (4, 4) homogeneous transform
                - trajectory: list of (4, 4) transforms
                - coverage_pct: float 0-100
            frontier_cells: Optional (K, 3) float array of frontier cell positions.
            voronoi_midpoint: Optional (2,) midpoint of Voronoi bisector.
            voronoi_direction: Optional (2,) direction vector A->B.
            total_coverage: Combined coverage percentage.
            merge_count: Number of map merges performed.
        """
        self._log_merged_map(merged_voxels, robot_data)
        for rid, data in robot_data.items():
            self._log_robot_panel(rid, data)
            self._log_robot_overlay(rid, data)
        self._log_coverage_heatmap(merged_voxels, frontier_cells)
        if voronoi_midpoint is not None:
            self._log_voronoi_plane(voronoi_midpoint, voronoi_direction)
        self._log_stats_hud(total_coverage, robot_data, merge_count)

    def _log_merged_map(
        self, merged_voxels: np.ndarray, robot_data: dict
    ) -> None:
        """Log combined point cloud with per-robot color tinting.

        Each robot's local_voxels are tinted with its assigned color
        and concatenated into a single Points3D log call.
        """
        all_points = []
        all_colors = []
        for rid, data in robot_data.items():
            voxels = data["local_voxels"]
            if len(voxels) == 0:
                continue
            color_rgb = ROBOT_COLORS.get(rid, (128, 128, 128))
            colors = np.tile(list(color_rgb), (len(voxels), 1)).astype(np.uint8)
            all_points.append(voxels)
            all_colors.append(colors)

        if not all_points:
            return
        points = np.concatenate(all_points, axis=0)
        colors = np.concatenate(all_colors, axis=0)
        rr.log("/merged/point_cloud", rr.Points3D(points, colors=colors))

    def _log_robot_overlay(self, rid: str, data: dict) -> None:
        """Log robot pose and fading trajectory trail on the merged view.

        Args:
            rid: Robot identifier (e.g. "robot_a").
            data: Robot data dict with pose and trajectory.
        """
        pose = data["pose"]
        pos = pose[:3, 3]
        rot = pose[:3, :3]
        rr.log(
            f"/merged/{rid}/pose",
            rr.Transform3D(
                translation=pos,
                mat3x3=rot,
            ),
        )
        # Axis triad: RGB arrows for X/Y/Z axes at robot position
        axis_len = 0.4
        origins = np.tile(pos, (3, 1))
        vectors = rot * axis_len  # columns are X, Y, Z axes
        rr.log(
            f"/merged/{rid}/axes",
            rr.Arrows3D(
                origins=origins,
                vectors=vectors.T,
                colors=[[255, 0, 0], [0, 255, 0], [0, 0, 255]],
                radii=0.02,
            ),
        )
        color_rgb = ROBOT_COLORS.get(rid, (128, 128, 128))
        self._log_fading_trail(
            f"/merged/{rid}/trajectory",
            data["trajectory"],
            color_rgb,
        )

    def _log_fading_trail(
        self,
        entity: str,
        poses: list[np.ndarray],
        color_rgb: tuple[int, int, int],
        max_segments: int = MAX_TRAIL_SEGMENTS,
    ) -> None:
        """Log trajectory as line segments with fading alpha.

        Older segments have lower alpha; most recent segment is fully
        opaque. Capped at max_segments to prevent memory growth.

        Args:
            entity: Rerun entity path for the trail.
            poses: List of (4, 4) homogeneous transforms.
            color_rgb: Base RGB color tuple.
            max_segments: Maximum number of trail segments to render.
        """
        positions = [p[:3, 3] for p in poses]
        if len(positions) < 2:
            return

        recent = positions[-max_segments:]
        n = len(recent) - 1
        strips = []
        colors = []
        for i in range(n):
            strips.append([recent[i], recent[i + 1]])
            alpha = int(255 * (i + 1) / n)
            colors.append([*color_rgb, alpha])
        rr.log(entity, rr.LineStrips3D(strips, colors=colors))

    def _log_robot_panel(self, rid: str, data: dict) -> None:
        """Log camera RGB and tinted local cloud to per-robot panel.

        Args:
            rid: Robot identifier.
            data: Robot data dict with frame and local_voxels.
        """
        rr.log(f"/{rid}/camera/rgb", rr.Image(data["frame"].rgb))

        voxels = data["local_voxels"]
        if len(voxels) > 0:
            color_rgb = ROBOT_COLORS.get(rid, (128, 128, 128))
            colors = np.tile(list(color_rgb), (len(voxels), 1)).astype(np.uint8)
            rr.log(f"/{rid}/local_cloud", rr.Points3D(voxels, colors=colors))

    def _log_coverage_heatmap(
        self,
        occupied_voxels: np.ndarray,
        frontier_cells: np.ndarray | None = None,
    ) -> None:
        """Log coverage heatmap as colored floor grid at z=0.

        Colors: green = explored, red = unexplored, yellow = frontier.
        Grid resolution is HEATMAP_RESOLUTION (0.1m).

        Args:
            occupied_voxels: (N, 3) occupied voxel positions.
            frontier_cells: Optional (K, 3) frontier cell positions.
        """
        if len(occupied_voxels) == 0:
            return

        res = HEATMAP_RESOLUTION

        # Project occupied voxels to 2D XY grid
        xy_occupied = occupied_voxels[:, :2]
        grid_occupied = np.round(xy_occupied / res).astype(int)

        # Compute bounding box with 1-cell margin
        grid_min = grid_occupied.min(axis=0) - 1
        grid_max = grid_occupied.max(axis=0) + 1

        # Create set of occupied grid indices for fast lookup
        occupied_set = set(map(tuple, grid_occupied))

        # Create frontier set if provided
        frontier_set = set()
        if frontier_cells is not None and len(frontier_cells) > 0:
            xy_frontier = frontier_cells[:, :2]
            grid_frontier = np.round(xy_frontier / res).astype(int)
            frontier_set = set(map(tuple, grid_frontier))

        # Generate all grid cells within bounding box
        xs = np.arange(grid_min[0], grid_max[0] + 1)
        ys = np.arange(grid_min[1], grid_max[1] + 1)
        grid_xx, grid_yy = np.meshgrid(xs, ys)
        grid_indices = np.column_stack([grid_xx.ravel(), grid_yy.ravel()])

        # Classify each cell
        positions = []
        cell_colors = []
        for gx, gy in grid_indices:
            key = (gx, gy)
            center_x = gx * res
            center_y = gy * res

            if key in frontier_set:
                # Yellow for frontier
                cell_colors.append([200, 200, 0, 180])
            elif key in occupied_set:
                # Green for explored
                cell_colors.append([0, 200, 0, 180])
            else:
                # Red for unexplored
                cell_colors.append([200, 0, 0, 100])

            positions.append([center_x, center_y, 0.0])

        if positions:
            positions = np.array(positions)
            cell_colors = np.array(cell_colors, dtype=np.uint8)
            rr.log(
                "/merged/heatmap",
                rr.Points3D(
                    positions=positions,
                    colors=cell_colors,
                    radii=res / 2,
                ),
            )

    def _log_voronoi_plane(
        self, midpoint_2d: np.ndarray, direction_2d: np.ndarray
    ) -> None:
        """Log Voronoi partition boundary as a translucent vertical plane.

        The plane is perpendicular to the A->B direction and passes
        through the midpoint between both robots.

        Args:
            midpoint_2d: (2,) XY midpoint between robots.
            direction_2d: (2,) direction vector from robot A to robot B.
        """
        # Perpendicular to direction (bisector runs perpendicular to A->B)
        perp = np.array([-direction_2d[1], direction_2d[0]])
        norm = np.linalg.norm(perp)
        if norm > 1e-8:
            perp = perp / norm

        p0 = midpoint_2d + perp * VORONOI_PLANE_HALF_WIDTH
        p1 = midpoint_2d - perp * VORONOI_PLANE_HALF_WIDTH

        vertices = np.array([
            [p0[0], p0[1], 0.0],
            [p1[0], p1[1], 0.0],
            [p1[0], p1[1], VORONOI_PLANE_HEIGHT],
            [p0[0], p0[1], VORONOI_PLANE_HEIGHT],
        ])

        color = [200, 200, 200, VORONOI_PLANE_ALPHA]
        rr.log(
            "/merged/voronoi_plane",
            rr.Mesh3D(
                vertex_positions=vertices,
                triangle_indices=[[0, 1, 2], [0, 2, 3]],
                vertex_colors=[color] * 4,
            ),
        )

    def _log_stats_hud(
        self, total_coverage: float, robot_data: dict, merge_count: int
    ) -> None:
        """Log markdown stats HUD to the /stats panel.

        Args:
            total_coverage: Combined coverage percentage.
            robot_data: Dict keyed by robot_id with coverage_pct.
            merge_count: Number of map merges performed.
        """
        elapsed = time.monotonic() - self._start_time

        coverage_a = robot_data.get("robot_a", {}).get("coverage_pct", 0.0)
        coverage_b = robot_data.get("robot_b", {}).get("coverage_pct", 0.0)

        md = (
            f"# Exploration Stats\n\n"
            f"**Total Coverage:** {total_coverage:.1f}%\n\n"
            f"**Robot A:** {coverage_a:.1f}%\n\n"
            f"**Robot B:** {coverage_b:.1f}%\n\n"
            f"**Elapsed:** {elapsed:.0f}s\n\n"
            f"**Merges:** {merge_count}\n"
        )
        rr.log("/stats", rr.TextDocument(md, media_type=rr.MediaType.MARKDOWN))
