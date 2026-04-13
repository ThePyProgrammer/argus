# Phase 3: Multi-Robot Coordination and Map Merging - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Two Go2 robots operate independently with coordinated region assignments and produce a single unified 3D map in real-time. The environment is partitioned via Voronoi splitting, each robot explores its assigned zone, regions are re-partitioned when one finishes, and local maps are fused into a unified occupancy grid and point cloud incrementally during exploration.

Requirements: COORD-01 (separate instances), COORD-02 (Voronoi partitioning), COORD-03 (dynamic re-partitioning), MERGE-01 (frame alignment), MERGE-02 (voxel fusion), MERGE-03 (point cloud merge), MERGE-04 (real-time incremental merging).

</domain>

<decisions>
## Implementation Decisions

### Two-Robot Spawning & Simulation
- Single MuJoCo environment with two Go2 bodies loaded at different spawn positions
- One physics step advances both robots simultaneously
- Configurable spawn positions defined in config (e.g., robot_a at origin, robot_b at [10, 0, 0]) -- known transforms are just config values

### Pipeline Isolation (COORD-01 reinterpretation)
- COORD-01 reinterpreted for MuJoCo: "separate DimOS blueprint instances with namespaced streams" means separate object instances with namespaced data (robot_a.slam, robot_b.slam) in the same Python process
- Two SLAMPipeline objects, two OctoMapBuilder objects, two ExplorationLoop instances -- all in same process but operating on independent data
- The spirit of independence is preserved: each robot's SLAM pipeline sees only its own sensor data

### Voronoi Partitioning (COORD-02)
- Initial partition computed AFTER a brief initial exploration phase (not from scene bounding box) -- both robots explore freely first, then partition based on discovered map extent
- Claude's Discretion: duration/criterion for the initial exploration boot-up phase (fixed step count vs coverage threshold)
- Soft constraint: frontiers in own region are prioritized (higher score), but robot CAN enter the other's region if no local frontiers remain -- prevents deadlocks

### Dynamic Re-partitioning (COORD-03)
- Re-partition triggers when one robot's assigned region has zero remaining frontiers
- The idle robot's partition expands to include unexplored areas from the other robot's zone
- Claude's Discretion: exact re-partition algorithm implementation

### Map Merging Strategy (MERGE-01, MERGE-02, MERGE-03)
- Dedicated MapMerger class -- takes two OctoMapBuilders + spawn transforms, produces unified occupancy grid + merged point cloud
- Frame alignment via configurable spawn transforms (MERGE-01) -- no ICP needed, just coordinate transform using known config values
- Voxel conflict resolution: union (OR) -- occupied if either robot says occupied (MERGE-02). Conservative for navigation. Advanced conflict resolution is v2 (MERGE-05).
- Point cloud merging (MERGE-03): voxel-downsampled to match occupancy resolution before merge. Keeps memory bounded.

### Incremental Real-Time Merging (MERGE-04)
- Merge triggers on the same event as frontier rescan (distance/change trigger from Phase 2)
- Unified map grows continuously during exploration, not as a batch operation

### Inter-Robot Communication
- DimOS pLCM transport (pickled LCM) for robot-to-robot data sharing -- gets typed pub/sub with serialization of complex Python objects
- Data flow: each robot publishes its occupancy grid + coverage status via pLCM; MapMerger subscribes to both
- Coordinator (partition assigner + merge trigger) runs in-process, not on LCM -- reads robot data via LCM but directly assigns partitions and triggers merges
- Hybrid: LCM where it matters (robot data isolation), direct calls where simpler (coordination logic)

### Claude's Discretion
- Initial exploration boot-up phase duration before first Voronoi partition
- Re-partition algorithm implementation details
- MuJoCo scene XML modifications for two-robot loading
- pLCM channel naming and message type design
- Multi-robot MuJoCoBridge extension (how to control two bodies independently)
- Exact integration with ExplorationLoop from Phase 2 (one loop per robot)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase context
- `.planning/phases/01-simulation-bridge-and-single-robot-slam/1-CONTEXT.md` -- Phase 1 decisions (MuJoCo pivot, SLAM validation, control modes)
- `.planning/phases/02-autonomous-exploration/02-CONTEXT.md` -- Phase 2 decisions (3D frontier detection, goal selection, navigation, completion)

### Existing source code
- `src/bridge/sim_bridge.py` -- MuJoCoBridge class (single-robot, needs extension for two bodies)
- `src/bridge/env_config.py` -- MuJoCoEnvConfig (model_path, resolution, sim_steps_per_frame)
- `src/bridge/sensor_types.py` -- SensorFrame, CameraIntrinsics
- `src/slam/slam_pipeline.py` -- SLAMPipeline (ICP odometry)
- `src/slam/octomap_builder.py` -- OctoMapBuilder (Open3D VoxelGrid, 0.1m resolution)
- `src/exploration/exploration_loop.py` -- ExplorationLoop (frontier-based autonomous exploration)
- `src/exploration/frontier_detector.py` -- FrontierDetector (3D voxel frontier detection)
- `src/exploration/goal_selector.py` -- GoalSelector
- `src/exploration/path_planner.py` -- A* path planner
- `src/exploration/coverage_tracker.py` -- CoverageTracker
- `src/exploration/config.py` -- ExplorationConfig
- `src/main.py` -- Current single-robot main loop with --control explore mode
- `models/unitree_go2/scene.xml` -- MuJoCo Go2 scene (single robot, needs duplication)

### Project decisions
- `.planning/PROJECT.md` -- Two separate DimOS instances (reinterpreted as namespaced objects), known spawn transforms eliminate ICP

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MuJoCoBridge` (src/bridge/sim_bridge.py): Needs extension for two-body control but core MuJoCo loading/stepping/rendering reusable
- `ExplorationLoop` (src/exploration/exploration_loop.py): One instance per robot -- the explore-map-navigate cycle is robot-agnostic
- `OctoMapBuilder` (src/slam/octomap_builder.py): Two instances, one per robot. MapMerger reads from both via `get_occupied_voxels()`
- `SLAMPipeline` (src/slam/slam_pipeline.py): Two instances, one per robot. Each processes only its robot's SensorFrames
- `FrontierDetector`, `GoalSelector`, `PathPlanner`: All per-robot, instantiated twice
- `CoverageTracker`: Per-robot coverage, plus a global coverage tracker for the merged map

### Established Patterns
- Standalone Python classes with start/step/stop lifecycle
- Open3D VoxelGrid as spatial backend
- Configurable via dataclasses (MuJoCoEnvConfig, ExplorationConfig)
- Rerun for visualization
- main.py as orchestration entry point with argparse control modes

### Integration Points
- MuJoCoBridge must be extended to load two Go2 XMLs and render/control each independently
- ExplorationLoop.run() needs to accept a Voronoi region as a frontier scoring bias
- MapMerger is a new component that subscribes to both robots' pLCM streams
- Coordinator orchestrates: initial exploration → partition → explore with regions → re-partition → merge → repeat
- main.py gets a new --control multi mode (or separate multi_main.py)

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

- MERGE-05: Conflict resolution for overlapping mapped regions -- v2, currently using simple union (OR)
- MERGE-06: Merged map quality scoring against ground-truth -- v2
- COORD-05: Inter-robot communication protocol for sharing map fragments -- v2 (using pLCM as v1 mechanism)
- EXPL-05: Multi-robot collision avoidance -- v2

</deferred>

---

*Phase: 03-multi-robot-coordination-and-map-merging*
*Context gathered: 2026-03-17*
