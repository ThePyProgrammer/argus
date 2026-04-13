# Phase 4: Visualization and Integration - Research

**Researched:** 2026-03-17
**Domain:** Rerun SDK visualization, multi-robot dashboard, real-time 3D rendering
**Confidence:** HIGH

## Summary

Phase 4 creates a `MultiRobotVisualizer` class that renders a split-panel Rerun dashboard showing the merged 3D map, per-robot camera feeds, robot trajectories with fading trails, and a coverage heatmap. The existing `RerunVisualizer` provides a solid reference implementation for single-robot patterns; the new class extends the approach to a multi-robot entity hierarchy with Rerun's Blueprint API for programmatic layout control.

The project already specifies `rerun-sdk>=0.30.0` in `pyproject.toml`. The Blueprint API (stable since Rerun 0.15) provides `Vertical`, `Horizontal`, `Grid` containers with `row_shares`/`column_shares` for proportional sizing. `TextDocument` with `media_type=MARKDOWN` enables a live-updating stats HUD. `Mesh3D` with RGBA vertex colors supports the translucent Voronoi boundary plane. All required Rerun features are well-established and documented.

**Primary recommendation:** Use Rerun Blueprint API for declarative layout, `TextDocument` for stats HUD, `Mesh3D` for Voronoi plane, and segment-based fading trails with decreasing alpha in RGBA colors on `LineStrips3D`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Split-panel Rerun layout: merged 3D scene as main view on top, per-robot panels side-by-side below
- Per-robot panels show: RGB camera feed + local (pre-merge) point cloud tinted in the robot's color
- Voronoi partition boundary shown as a translucent vertical plane in the merged 3D view
- Text stats HUD in the merged view: total coverage %, per-robot coverage, elapsed time (Rerun 2D text annotations)
- Color scheme: Robot A = blue, Robot B = orange (colorblind-friendly, high contrast)
- Current position shown as axis triad (RGB XYZ axes) at each robot's pose
- Trajectories rendered as fading trails -- recent positions bright, older positions fade out
- Local point clouds in per-robot panels tinted in the robot's color (blue/orange)
- In merged view, each robot's point cloud contribution also tinted in its color
- Coverage heatmap: colored 2D floor grid -- green = explored, red = unexplored, yellow = frontier
- Grid resolution matches occupancy grid (0.1m)
- No per-robot attribution on the heatmap
- Direct method calls from coordination loop -- no pLCM subscription for viz
- Same update rate for all views -- every 10 frames
- Always-on visualization in --control multi mode
- New MultiRobotVisualizer class (not extending existing RerunVisualizer)
- Existing RerunVisualizer remains untouched for single-robot modes

### Claude's Discretion
- Rerun entity path naming scheme for multi-robot hierarchy
- Exact fading trail implementation (alpha gradient vs separate line segments)
- Stats HUD positioning and formatting within Rerun 2D annotations
- Translucent plane rendering approach for Voronoi boundary
- How to handle Rerun panel layout configuration (blueprint API vs manual)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VIZ-01 | System displays the merged 3D map in real-time via Rerun | Blueprint API for layout, Spatial3DView for merged map, entity path hierarchy for multi-robot data, direct method call from Coordinator loop |
| VIZ-02 | System overlays both robots' current positions and trajectories on the merged map | Transform3D for axis triads, LineStrips3D with RGBA fading for trails, entity paths per robot under merged view |
| VIZ-03 | System displays a coverage heatmap showing explored vs unexplored regions | Boxes3D or Points3D colored grid on ground plane, FrontierDetector provides frontier cells, CoverageTracker provides coverage % |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rerun-sdk | >=0.30.0 | Real-time 3D visualization dashboard | Already in pyproject.toml; Blueprint API stable since 0.15; rich archetype library |
| numpy | >=1.26.0 | Array manipulation for colors, trajectories, grids | Already used throughout project |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| rerun.blueprint (rrb) | Part of rerun-sdk | Programmatic panel layout | Blueprint creation at init time |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Rerun TextDocument for HUD | rr.TextLog | TextDocument supports markdown formatting, better for stats display |
| Boxes3D for heatmap | Points3D with large radii | Boxes3D gives precise grid cells; Points3D simpler but overlaps at boundaries |
| Mesh3D for Voronoi plane | Boxes3D thin slab | Mesh3D has proper RGBA alpha transparency; Boxes3D has no alpha channel control |

**Installation:**
```bash
pip install "rerun-sdk>=0.30.0"
```
Already specified in pyproject.toml -- no new dependencies needed.

## Architecture Patterns

### Recommended Project Structure
```
src/
  viz/
    rerun_viz.py              # Existing single-robot (UNTOUCHED)
    multi_robot_viz.py        # NEW: MultiRobotVisualizer class
```

### Entity Path Naming Scheme (Claude's Discretion)

```
/merged/                      # Main merged 3D view root
  point_cloud                 # Merged point cloud (colored per-robot)
  occupancy                   # Merged occupancy voxels
  robot_a/
    pose                      # Transform3D axis triad
    trajectory                # LineStrips3D fading trail
  robot_b/
    pose                      # Transform3D axis triad
    trajectory                # LineStrips3D fading trail
  voronoi_plane               # Mesh3D translucent partition boundary
  heatmap                     # Boxes3D or Points3D coverage grid

/robot_a/                     # Per-robot panel root
  camera/rgb                  # rr.Image
  local_cloud                 # Points3D tinted blue

/robot_b/                     # Per-robot panel root
  camera/rgb                  # rr.Image
  local_cloud                 # Points3D tinted orange

/stats                        # TextDocument markdown HUD
```

**Rationale:** Prefixing with `/merged/`, `/robot_a/`, `/robot_b/`, `/stats` gives each blueprint view a clean `origin` path. Rerun views filter by entity path origin, so this hierarchy maps directly to the split-panel layout.

### Pattern 1: Blueprint Layout Configuration

**What:** Programmatic split-panel layout using Rerun Blueprint API
**When to use:** At MultiRobotVisualizer initialization, after `rr.init()`

```python
import rerun as rr
import rerun.blueprint as rrb

def _create_blueprint() -> rrb.Blueprint:
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
                column_shares=[4, 1],  # 80% map, 20% stats
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
                column_shares=[1, 1],  # Equal width
            ),
            row_shares=[3, 1],  # 75% main view, 25% per-robot panels
        ),
        collapse_panels=True,
    )
```

### Pattern 2: Fading Trajectory Trails (Claude's Discretion)

**What:** Segment-based fading trails with decreasing alpha for older positions
**When to use:** Each visualization update cycle

**Recommendation:** Use multiple `LineStrips3D` segments with decreasing alpha rather than a single line strip (Rerun does not support per-vertex alpha on line strips). Log the N most recent segments with alpha gradient:

```python
def _log_fading_trail(
    entity: str,
    positions: list[np.ndarray],
    color_rgb: tuple[int, int, int],
    max_segments: int = 50,
) -> None:
    """Log trajectory as segments with fading alpha."""
    if len(positions) < 2:
        return
    recent = positions[-max_segments:]
    n = len(recent) - 1
    strips = []
    colors = []
    for i in range(n):
        strips.append([recent[i], recent[i + 1]])
        alpha = int(255 * (i + 1) / n)  # 0=old -> 255=recent
        colors.append([*color_rgb, alpha])
    rr.log(entity, rr.LineStrips3D(strips, colors=colors))
```

### Pattern 3: Coverage Heatmap as Floor Grid

**What:** 2D grid of colored boxes projected on the ground plane (z=0)
**When to use:** Each visualization update cycle

```python
def _log_coverage_heatmap(
    occupied_voxels: np.ndarray,
    frontier_cells: np.ndarray,
    resolution: float = 0.1,
) -> None:
    """Log explored/unexplored/frontier as colored floor grid."""
    # Project to 2D (XY), compute bounding box
    # Green = explored, Red = unexplored, Yellow = frontier
    # Use rr.Boxes3D with flat (z-thin) boxes at ground level
    # OR rr.Points3D with radii=resolution/2 at z=0
```

### Pattern 4: Stats HUD via TextDocument Markdown

**What:** Live-updating markdown stats panel
**When to use:** Each visualization update cycle

```python
def _log_stats_hud(
    total_coverage: float,
    coverage_a: float,
    coverage_b: float,
    elapsed_s: float,
    merge_count: int,
) -> None:
    md = (
        f"# Exploration Stats\n\n"
        f"**Total Coverage:** {total_coverage:.1f}%\n\n"
        f"**Robot A:** {coverage_a:.1f}%\n\n"
        f"**Robot B:** {coverage_b:.1f}%\n\n"
        f"**Elapsed:** {elapsed_s:.0f}s\n\n"
        f"**Merges:** {merge_count}\n"
    )
    rr.log("/stats", rr.TextDocument(md, media_type=rr.MediaType.MARKDOWN))
```

### Pattern 5: Voronoi Boundary as Translucent Plane (Claude's Discretion)

**What:** Vertical translucent mesh plane along the perpendicular bisector
**Recommendation:** Use `Mesh3D` with RGBA vertex colors including alpha ~80 (semi-transparent).

```python
def _log_voronoi_plane(
    midpoint_2d: np.ndarray,
    direction_2d: np.ndarray,
    height: float = 5.0,
    half_width: float = 20.0,
) -> None:
    """Log Voronoi partition boundary as a translucent vertical plane."""
    # Perpendicular to direction (bisector is perpendicular to A->B line)
    perp = np.array([-direction_2d[1], direction_2d[0]])
    perp = perp / (np.linalg.norm(perp) + 1e-8)

    p0 = midpoint_2d + perp * half_width
    p1 = midpoint_2d - perp * half_width

    vertices = np.array([
        [p0[0], p0[1], 0.0],
        [p1[0], p1[1], 0.0],
        [p1[0], p1[1], height],
        [p0[0], p0[1], height],
    ])
    # Semi-transparent white
    color = [200, 200, 200, 80]
    rr.log(
        "/merged/voronoi_plane",
        rr.Mesh3D(
            vertex_positions=vertices,
            triangle_indices=[[0, 1, 2], [0, 2, 3]],
            vertex_colors=[color] * 4,
        ),
    )
```

### Anti-Patterns to Avoid
- **Extending RerunVisualizer:** User locked decision -- create a separate class. The single-robot viz must remain untouched.
- **Using pLCM for viz data:** User locked decision -- direct method calls only. Coordinator calls `viz.update()` directly.
- **Logging every frame:** Performance killer. Stick to the established 10-frame interval.
- **Single global entity path:** Without the `/merged/`, `/robot_a/`, `/robot_b/` hierarchy, blueprint view filtering will not work correctly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Panel layout | Manual viewer configuration | `rerun.blueprint` API | Declarative, reproducible, persists across sessions |
| Markdown rendering | Custom text formatting | `rr.TextDocument` with `MediaType.MARKDOWN` | Built-in support for headers, bold, tables |
| Color tinting of point clouds | Manual per-point color assignment loops | NumPy broadcast: `np.tile([r,g,b], (N,1))` | Already established pattern in `rerun_viz.py` |
| 3D transforms for robot pose | Custom rotation matrix visualization | `rr.Transform3D(translation=..., mat3x3=...)` | Built-in axis triad rendering in Rerun |

**Key insight:** Rerun provides all the primitives needed for this phase. The work is wiring existing data sources (MapMerger, CoverageTracker, FrontierDetector, VoronoiPartitioner, SLAMPipeline) into Rerun log calls with proper entity paths.

## Common Pitfalls

### Pitfall 1: Blueprint Not Applied
**What goes wrong:** Blueprint is created but viewer shows default layout
**Why it happens:** `rr.send_blueprint()` must be called after `rr.init()` but before heavy logging begins
**How to avoid:** Call `rr.send_blueprint(blueprint)` immediately after `rr.init(app_name, spawn=True)` in the constructor
**Warning signs:** All entities appear in a single default panel

### Pitfall 2: Entity Path Mismatch with Blueprint Origins
**What goes wrong:** Views appear empty despite data being logged
**Why it happens:** Blueprint view `origin="/robot_a"` only shows entities under that path prefix
**How to avoid:** Verify all `rr.log()` entity paths start with the view's origin prefix
**Warning signs:** Data appears in wrong panel or not at all

### Pitfall 3: Performance Degradation with Large Heatmaps
**What goes wrong:** Visualization frame rate drops significantly
**Why it happens:** Logging thousands of individual boxes/points for the heatmap grid each update
**How to avoid:** Batch all heatmap cells into a single `rr.Points3D` or `rr.Boxes3D` call with arrays, not individual log calls. Consider reducing heatmap resolution (e.g., 0.5m instead of 0.1m for display) or only logging changed cells.
**Warning signs:** >100ms per viz update cycle

### Pitfall 4: Fading Trails Memory Leak
**What goes wrong:** Trail rendering slows down over time as trajectory grows
**Why it happens:** Logging the entire trajectory history as line segments each update
**How to avoid:** Cap trail length to last N positions (e.g., 50-100 segments). Full trajectory can remain as a thin static line.
**Warning signs:** Increasing log payload size over time

### Pitfall 5: Mesh3D Alpha Not Rendering
**What goes wrong:** Voronoi plane appears opaque instead of translucent
**Why it happens:** Rerun historically had limited alpha support for meshes; alpha may be ignored in some rendering paths
**How to avoid:** Use RGBA vertex_colors with alpha in [0,255] range. Ensure counter-clockwise winding order for front faces. If alpha is ignored, fall back to a very sparse wireframe or stippled rendering.
**Warning signs:** Plane obscures the 3D scene behind it

### Pitfall 6: Coordinator Integration Timing
**What goes wrong:** Viz update called but data sources return empty/stale data
**Why it happens:** Viz update runs before the merge or exploration step completes in that cycle
**How to avoid:** Call `viz.update()` at the END of each coordination loop iteration, after merge and exploration steps complete
**Warning signs:** Dashboard shows data from previous cycle

## Code Examples

### MultiRobotVisualizer Class Skeleton

```python
import time
import numpy as np
import rerun as rr
import rerun.blueprint as rrb

# Robot colors: blue for A, orange for B
ROBOT_COLORS = {
    "robot_a": (66, 133, 244),    # Blue
    "robot_b": (255, 152, 0),     # Orange
}

class MultiRobotVisualizer:
    """Multi-robot dashboard with split-panel Rerun layout."""

    def __init__(self, app_name: str = "multi_robot_viz"):
        rr.init(app_name, spawn=True)
        blueprint = self._create_blueprint()
        rr.send_blueprint(blueprint)
        self._start_time = time.monotonic()

    def _create_blueprint(self) -> rrb.Blueprint:
        # ... as shown in Pattern 1 above

    def update(
        self,
        merged_voxels: np.ndarray,
        robot_data: dict,  # {robot_id: {frame, local_voxels, pose, trajectory, coverage_pct}}
        frontier_cells: np.ndarray | None = None,
        voronoi_midpoint: np.ndarray | None = None,
        voronoi_direction: np.ndarray | None = None,
        total_coverage: float = 0.0,
        merge_count: int = 0,
    ) -> None:
        """Update all dashboard panels in one call."""
        self._log_merged_map(merged_voxels, robot_data)
        for rid, data in robot_data.items():
            self._log_robot_panel(rid, data)
            self._log_robot_overlay(rid, data)
        self._log_coverage_heatmap(merged_voxels, frontier_cells)
        if voronoi_midpoint is not None:
            self._log_voronoi_plane(voronoi_midpoint, voronoi_direction)
        self._log_stats_hud(total_coverage, robot_data, merge_count)
```

### Tinting Point Cloud Per-Robot

```python
def _tint_points(points: np.ndarray, color_rgb: tuple[int, int, int]) -> np.ndarray:
    """Create uniform color array for a point cloud."""
    return np.tile(list(color_rgb), (len(points), 1)).astype(np.uint8)
```

### Integration Point: Coordinator.run() Modification

```python
# Inside Coordinator.run() loop, after merge step:
if step % 10 == 0 and self._viz is not None:
    robot_data = {}
    for rid in robot_ids:
        robot = self._robots[rid]
        robot_data[rid] = {
            "frame": frames[rid],
            "local_voxels": robot.octomap.get_occupied_voxels(),
            "pose": robot.slam.slam_poses[-1] if robot.slam.slam_poses else np.eye(4),
            "trajectory": [p[:3, 3] for p in robot.slam.slam_poses],
            "coverage_pct": robot.exploration._coverage_tracker._last_coverage,
        }
    self._viz.update(
        merged_voxels=self._merger.last_merged_voxels,
        robot_data=robot_data,
        frontier_cells=...,  # Gather from frontier detectors
        voronoi_midpoint=...,
        voronoi_direction=...,
        total_coverage=...,
        merge_count=self._merge_count,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual Rerun UI layout | Blueprint API programmatic layout | Rerun 0.15+ (2024) | Reproducible layouts via code |
| RViz2 for robotics viz | Rerun SDK | Project decision | Simpler API, no ROS dependency, better for multi-modal data |
| Matplotlib post-hoc plots | Rerun real-time streaming | Project decision (Phase 1) | Live updates during exploration |

**Deprecated/outdated:**
- `rr.log_text_entry()`: Replaced by `rr.TextLog()` archetype in modern Rerun
- `SeriesVisible` component: Removed in Rerun 0.30

## Open Questions

1. **Heatmap performance at 0.1m resolution**
   - What we know: At 0.1m resolution over a large area (e.g., 50mx50m), the heatmap would have 250,000 cells -- potentially too many for smooth rendering
   - What's unclear: Exact performance threshold for Rerun with large `Points3D`/`Boxes3D` batches
   - Recommendation: Start at 0.1m (matches user decision), but add a configurable `heatmap_resolution` parameter that can be increased (e.g., 0.5m) if performance is poor. Only log cells within the current bounding box of explored space, not the entire theoretical grid.

2. **Mesh3D alpha transparency reliability**
   - What we know: Rerun supports RGBA vertex colors on Mesh3D and states "front faces are those with counter clockwise winding"
   - What's unclear: Whether alpha blending works reliably across all Rerun renderer backends at >=0.30.0
   - Recommendation: Implement with Mesh3D RGBA first. If alpha is not rendered, fall back to a thin wireframe grid or dashed line representation of the boundary.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0.0 with pytest-timeout |
| Config file | pyproject.toml (implicit) |
| Quick run command | `python -m pytest tests/ -x --timeout=30` |
| Full suite command | `python -m pytest tests/ --timeout=60` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIZ-01 | MultiRobotVisualizer logs merged map to correct entity paths | unit (mock rr.log) | `python -m pytest tests/test_multi_robot_viz.py::test_log_merged_map -x` | No -- Wave 0 |
| VIZ-01 | Blueprint layout has Spatial3DView with origin /merged | unit | `python -m pytest tests/test_multi_robot_viz.py::test_blueprint_layout -x` | No -- Wave 0 |
| VIZ-02 | Robot pose logged as Transform3D at correct entity path | unit (mock rr.log) | `python -m pytest tests/test_multi_robot_viz.py::test_log_robot_pose -x` | No -- Wave 0 |
| VIZ-02 | Fading trail logged with decreasing alpha segments | unit | `python -m pytest tests/test_multi_robot_viz.py::test_fading_trail -x` | No -- Wave 0 |
| VIZ-03 | Coverage heatmap colors: green=explored, red=unexplored, yellow=frontier | unit | `python -m pytest tests/test_multi_robot_viz.py::test_heatmap_colors -x` | No -- Wave 0 |
| VIZ-03 | Heatmap grid resolution matches 0.1m | unit | `python -m pytest tests/test_multi_robot_viz.py::test_heatmap_resolution -x` | No -- Wave 0 |
| INT | Coordinator calls viz.update() every 10 frames | unit (mock viz) | `python -m pytest tests/test_coordinator.py::test_viz_update_interval -x` | No -- Wave 0 |
| INT | main.py --control multi wires MultiRobotVisualizer | smoke | `python -m pytest tests/test_multi_mode.py::test_multi_mode_wiring -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_multi_robot_viz.py -x --timeout=30`
- **Per wave merge:** `python -m pytest tests/ --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_multi_robot_viz.py` -- covers VIZ-01, VIZ-02, VIZ-03 (unit tests with mocked rr.log)
- [ ] `tests/test_multi_mode.py` -- covers integration wiring of --control multi mode
- [ ] Test approach: mock `rr.log` and `rr.send_blueprint` to verify correct entity paths, colors, and data shapes without launching the Rerun viewer

## Sources

### Primary (HIGH confidence)
- [Rerun Blueprint API docs](https://rerun.io/docs/howto/visualization/build-a-blueprint-programmatically) -- Vertical/Horizontal/Grid containers, row_shares, column_shares, view origins
- [Rerun TextDocument archetype](https://rerun.io/docs/reference/types/archetypes/text_document) -- Markdown media type, live updates via re-logging
- [Rerun Mesh3D archetype](https://rerun.io/docs/reference/types/archetypes/mesh3d) -- RGBA vertex colors, triangle indices, winding order for alpha
- [Rerun Points3D archetype](https://rerun.io/docs/reference/types/archetypes/points3d) -- Colors, radii, labels
- [Rerun PyPI](https://pypi.org/project/rerun-sdk/) -- Latest version 0.28.1 (Jan 2026); project specifies >=0.30.0
- Existing codebase: `src/viz/rerun_viz.py` -- established patterns for entity paths, rr.init(spawn=True), 10-frame update interval

### Secondary (MEDIUM confidence)
- [Rerun Blueprint blog post](https://rerun.io/blog/blueprint-part-one) -- Blueprint API design rationale
- [Rerun GitHub releases](https://github.com/rerun-io/rerun/releases) -- Version history and changelog

### Tertiary (LOW confidence)
- Mesh3D alpha transparency: documented as supported via RGBA vertex_colors, but real-world rendering reliability at >=0.30.0 unverified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- rerun-sdk already in project, Blueprint API well-documented
- Architecture: HIGH -- entity path hierarchy maps cleanly to blueprint views; existing patterns from RerunVisualizer transfer directly
- Pitfalls: MEDIUM -- heatmap performance and mesh alpha transparency are empirical questions
- Validation: HIGH -- straightforward mock-based testing of rr.log calls

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain, Rerun API unlikely to break)
