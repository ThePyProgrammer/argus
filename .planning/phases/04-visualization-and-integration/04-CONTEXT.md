# Phase 4: Visualization and Integration - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A real-time dashboard displays the merged 3D reconstruction with robot tracking and exploration progress. The dashboard uses Rerun with a split-panel layout: merged 3D scene on top, per-robot panels below. Both robots' positions, trajectories, and a coverage heatmap are visible. This is the final integration phase — visualization is the deliverable.

Requirements: VIZ-01 (merged 3D map in real-time via Rerun), VIZ-02 (robot positions and trajectories overlay), VIZ-03 (coverage heatmap explored vs unexplored).

</domain>

<decisions>
## Implementation Decisions

### Dashboard Layout
- Split-panel Rerun layout: merged 3D scene as main view on top, per-robot panels side-by-side below
- Per-robot panels show: RGB camera feed + local (pre-merge) point cloud tinted in the robot's color
- Voronoi partition boundary shown as a translucent vertical plane in the merged 3D view
- Text stats HUD in the merged view: total coverage %, per-robot coverage, elapsed time (Rerun 2D text annotations)

### Robot Identity Encoding
- Color scheme: Robot A = blue, Robot B = orange (colorblind-friendly, high contrast)
- Current position shown as axis triad (RGB XYZ axes) at each robot's pose — standard robotics convention
- Trajectories rendered as fading trails — recent positions bright, older positions fade out, shows direction and recency
- Local point clouds in per-robot panels tinted in the robot's color (blue/orange)
- In merged view, each robot's point cloud contribution also tinted in its color

### Coverage Heatmap (VIZ-03)
- Colored 2D floor grid projected on the ground plane, rendered below the 3D map data
- Green = explored, red = unexplored, yellow = frontier cells (boundary between explored and unexplored — maps directly to Phase 2 frontier detection)
- Grid resolution matches occupancy grid (0.1m) for accuracy
- No per-robot attribution on the heatmap — just explored/unexplored/frontier. Robot identity is conveyed through trajectories and pose markers

### Update Frequency & Data Flow
- Direct method calls from the coordination loop — no pLCM subscription for viz. Coordinator calls viz.update() each cycle
- Same update rate for all views (merged map, per-robot cameras, heatmap, trajectories) — currently every 10 frames from Phase 1 pattern
- Always-on visualization when running --control multi mode — no separate --viz flag needed. This is the final phase; viz is the deliverable

### Class Architecture
- New `MultiRobotVisualizer` class (not extending existing RerunVisualizer)
- Dedicated to multi-robot entity paths, split panels, heatmap, stats HUD, fading trails
- Existing `RerunVisualizer` remains untouched for single-robot modes

### Claude's Discretion
- Rerun entity path naming scheme for multi-robot hierarchy
- Exact fading trail implementation (alpha gradient vs separate line segments)
- Stats HUD positioning and formatting within Rerun 2D annotations
- Translucent plane rendering approach for Voronoi boundary
- How to handle Rerun panel layout configuration (blueprint API vs manual)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase context
- `.planning/phases/01-simulation-bridge-and-single-robot-slam/1-CONTEXT.md` — Phase 1 decisions (MuJoCo pivot, Rerun viz pattern, 10-frame update interval)
- `.planning/phases/02-autonomous-exploration/02-CONTEXT.md` — Phase 2 decisions (frontier detection, coverage tracking)
- `.planning/phases/03-multi-robot-coordination-and-map-merging/03-CONTEXT.md` — Phase 3 decisions (MapMerger, pLCM transport, Voronoi partitioning, known spawn transforms)

### Existing visualization code
- `src/viz/rerun_viz.py` — Current single-robot RerunVisualizer (log_frame, log_point_cloud, log_occupancy_grid, log_trajectory, log_robot_pose)

### Existing source code (data sources for visualization)
- `src/slam/octomap_builder.py` — OctoMapBuilder (get_occupied_voxels for occupancy data)
- `src/slam/slam_pipeline.py` — SLAMPipeline (pose estimates, trajectory)
- `src/exploration/frontier_detector.py` — FrontierDetector (frontier cells for yellow heatmap regions)
- `src/exploration/coverage_tracker.py` — CoverageTracker (coverage % for stats HUD)
- `src/coordination/voronoi_partitioner.py` — VoronoiPartitioner (partition boundary for translucent plane)
- `src/coordination/multi_robot_config.py` — MultiRobotConfig (spawn positions, robot colors)
- `src/main.py` — Entry point with --control modes (will get --control multi wiring)

### Project decisions
- `.planning/PROJECT.md` — Real-time map requirement, DimOS framework context

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RerunVisualizer` (src/viz/rerun_viz.py): Reference implementation for single-robot viz. log_point_cloud, log_occupancy_grid, log_trajectory, log_robot_pose methods provide patterns to replicate per-robot
- `CoverageTracker` (src/exploration/coverage_tracker.py): Already computes coverage % — feed directly to stats HUD
- `FrontierDetector` (src/exploration/frontier_detector.py): Frontier cell detection reused for yellow heatmap cells
- `VoronoiPartitioner` (src/coordination/voronoi_partitioner.py): Partition geometry needed for translucent plane rendering

### Established Patterns
- Rerun entity paths: currently `camera/rgb`, `camera/depth`, `map/point_cloud`, `map/occupancy`, `robot/slam_trajectory`, `robot/current`
- rr.init() with spawn=True for auto-launching viewer
- Configurable via dataclasses (MuJoCoEnvConfig, ExplorationConfig, MultiRobotConfig)
- 10-frame visualization update interval for performance

### Integration Points
- MultiRobotVisualizer instantiated by Coordinator (or multi-robot main loop)
- Called via direct methods: viz.update(merged_map, robot_a_data, robot_b_data, coverage_stats)
- Needs access to: MapMerger output, per-robot SLAMPipeline poses, per-robot SensorFrames, CoverageTracker stats, VoronoiPartitioner boundary
- main.py --control multi mode wires visualization into the coordination loop

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-visualization-and-integration*
*Context gathered: 2026-03-17*
