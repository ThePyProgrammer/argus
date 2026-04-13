# Phase 2: Autonomous Exploration - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning

<domain>
## Phase Boundary

A single robot autonomously explores the environment using frontier-based navigation, building its map without any human commands. The robot identifies frontier cells, selects goals, navigates to them, and repeats the explore-map-navigate cycle. Coverage completeness is tracked and reported.

Requirements: EXPL-01 (frontier detection), EXPL-02 (autonomous goal selection + navigation), EXPL-03 (coverage tracking).

</domain>

<decisions>
## Implementation Decisions

### Frontier Detection Strategy
- Full 3D frontier detection in voxel space (not projected to 2D)
- Re-detect frontiers on a distance/change trigger (robot moved N meters or map grew by M voxels), not every gym step
- Claude's Discretion: extraction method (voxel boundary scan vs other), minimum cluster size for noise filtering, exact trigger thresholds

### Goal Selection Policy
- Skip unreachable frontiers and try the next candidate; if all unreachable, trigger exploration complete
- No blacklist for failed frontiers -- unreachable ones are skipped this cycle but re-eligible on next scan
- Claude's Discretion: selection strategy (nearest, largest, weighted score), commitment vs re-evaluation behavior

### Navigation & Path Execution
- Use DimOS replanning A* module for pathfinding (adapt to SimWorld if needed)
- Step-by-step action mapping: convert path waypoints to sequences of discrete actions using the existing `set_velocity()` → discrete action pipeline in `sim_bridge.py`
- Replan paths when occupancy grid changes affect the current path (new obstacle or new shortcut), aligned with the distance/change trigger for frontier detection
- Claude's Discretion: stuck detection method (position check vs waypoint timeout)

### Completion & Termination
- Exploration terminates when zero reachable frontier clusters remain
- Configurable maximum step limit as safety net (e.g., 10,000 steps) -- if reached, stop and report achieved coverage
- Periodic log output: coverage %, frontier count, and step count every N steps or on frontier re-evaluation
- Claude's Discretion: coverage % calculation method (frontier exhaustion ratio, bounding box, or ground-truth if accessible)

### Claude's Discretion
- Frontier extraction algorithm and noise filtering thresholds
- Goal selection strategy (nearest/largest/weighted)
- Frontier commitment vs re-evaluation mid-journey
- Stuck detection implementation
- Coverage metric calculation approach
- DimOS replanning A* integration details and any adaptations needed for 3D + discrete actions

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 context and discoveries
- `.planning/phases/01-simulation-bridge-and-single-robot-slam/1-CONTEXT.md` -- Phase 1 decisions (SimWorld fallback strategy, manual driving interface, SLAM validation criteria)
- `docs/simworld_discovery.md` -- SimWorld gym API format, observation keys, action space (Discrete(6)), ground-truth pose format

### Existing source code
- `src/bridge/sim_bridge.py` -- SimWorldGymBridge with set_velocity() discrete action mapping, step/start/stop lifecycle
- `src/bridge/sensor_types.py` -- SensorFrame data type (rgb, depth, ground_truth_pose, sim_time)
- `src/bridge/env_config.py` -- SimWorldEnvConfig
- `src/slam/octomap_builder.py` -- OctoMapBuilder using Open3D VoxelGrid (0.1m resolution), insert_scan(), get_occupied_voxels()
- `src/slam/depth_to_cloud.py` -- Depth image to point cloud conversion
- `src/metrics/drift_metrics.py` -- Drift metrics (ATE/RPE)
- `src/metrics/ground_truth.py` -- Ground-truth pose handling

### DimOS modules (installed package)
- DimOS `replanning_a_star` module -- built-in A* with replanning capability (in `dimos/navigation/replanning_a_star/`)
- DimOS `wavefront_frontier_explorer` module -- built-in frontier exploration (in `dimos/navigation/frontier_exploration/`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OctoMapBuilder` (src/slam/octomap_builder.py): Frontier detection reads from `get_occupied_voxels()` to identify boundaries between explored/unexplored space
- `SimWorldGymBridge.set_velocity()` (src/bridge/sim_bridge.py): Already maps continuous velocity to Discrete(6) actions -- navigation module feeds velocity commands through this
- `SensorFrame` (src/bridge/sensor_types.py): Standard data type carrying RGB, depth, pose, and sim_time per step
- DimOS `replanning_a_star` and `wavefront_frontier_explorer`: Built-in navigation modules that may be usable or adaptable

### Established Patterns
- Module pattern: standalone Python classes (not DimOS Modules yet) with clear lifecycle (start/step/stop)
- Open3D VoxelGrid as spatial backend (not octomap-python)
- Ground-truth pose available every step for evaluation
- Rerun for all 3D visualization

### Integration Points
- Frontier detector reads from OctoMapBuilder's accumulated voxel grid
- Navigator sends velocity commands via SimWorldGymBridge.set_velocity()
- Exploration loop orchestrates: step sim → update SLAM → detect frontiers → select goal → plan path → execute action
- Coverage metrics logged periodically and visualized in Rerun

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 02-autonomous-exploration*
*Context gathered: 2026-03-17*
