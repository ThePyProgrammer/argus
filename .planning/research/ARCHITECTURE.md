# Architecture Patterns

**Domain:** Multi-Robot Autonomous Exploration & 3D Reconstruction (Simulation)
**Researched:** 2026-03-17

## Recommended Architecture

**Two-instance DimOS blueprint** architecture: each robot runs as a separate DimOS blueprint instance in its own process tree. A coordination layer uses LCM inter-process messaging to exchange map data and exploration state. This avoids the stream-naming conflicts and broadcast-only limitations of DimOS fleet mode.

```
+----- Process 1: Robot A Blueprint -----+   +----- Process 2: Robot B Blueprint -----+
|                                         |   |                                         |
| SimWorldGymBridge(robot_id="a")         |   | SimWorldGymBridge(robot_id="b")         |
|   |                                     |   |   |                                     |
|   v                                     |   |   v                                     |
| DepthToPointCloud                       |   | DepthToPointCloud                       |
|   |                                     |   |   |                                     |
|   v                                     |   |   v                                     |
| SLAMNode (RTAB-Map instance A)          |   | SLAMNode (RTAB-Map instance B)          |
|   |                                     |   |   |                                     |
|   v                                     |   |   v                                     |
| LocalMapBuilder                         |   | LocalMapBuilder                         |
|   |          |                          |   |   |          |                          |
|   v          v                          |   |   v          v                          |
| OccGrid_A  PointCloud_A                 |   | OccGrid_B  PointCloud_B                 |
|   |          |                          |   |   |          |                          |
|   v          v                          |   |   v          v                          |
| FrontierExplorer_A                      |   | FrontierExplorer_B                      |
|   |                                     |   |   |                                     |
|   v                                     |   |   v                                     |
| LocalNavigator_A                        |   | LocalNavigator_B                        |
|   |                                     |   |   |                                     |
|   +--[LCM: /robot_a/local_map]---------+   |   +--[LCM: /robot_b/local_map]---------+
|   +--[LCM: /robot_a/pose]------+       |   |   +--[LCM: /robot_b/pose]------+       |
+-----------------------------+---+-------+   +-----------------------------+---+-------+
                              |   |                                         |   |
                              v   v                                         v   v
                    +--------- Process 3: Coordination Layer ---------------------+
                    |                                                              |
                    | MapMergeServer                                               |
                    |   - Subscribes to /robot_a/local_map, /robot_b/local_map    |
                    |   - Aligns using known spawn transforms                     |
                    |   - Publishes /merged/point_cloud, /merged/occupancy_grid   |
                    |                                                              |
                    | RegionAllocator                                              |
                    |   - Subscribes to /robot_a/pose, /robot_b/pose              |
                    |   - Subscribes to /merged/occupancy_grid                    |
                    |   - Publishes /robot_a/assigned_region, /robot_b/assigned_region |
                    |                                                              |
                    | RerunBridge                                                  |
                    |   - Subscribes to all map + pose topics                     |
                    |   - Visualizes in Rerun web viewer                          |
                    |                                                              |
                    | DimOS Agent (optional)                                       |
                    |   - LangGraph + GPT-4o                                      |
                    |   - @skill methods for start_exploration, reassign_regions   |
                    +--------------------------------------------------------------+
```

### Component Boundaries

| Component | Responsibility | DimOS Abstraction | Communicates With | Transport |
|-----------|---------------|-------------------|-------------------|-----------|
| **SimWorldGymBridge** | Bridge SimWorld gym env to DimOS streams. Steps env, publishes observations (RGB, depth, pose), receives velocity commands. | Module (1 per robot) | DepthToPointCloud, SLAMNode, LocalNavigator | SHM (large images) |
| **DepthToPointCloud** | Convert depth images to 3D point clouds using camera intrinsics. Filter invalid points. | Module (1 per robot) | SimWorldGymBridge (In), SLAMNode (Out) | SHM |
| **SLAMNode** | Run RTAB-Map. Consume point clouds + odometry, produce corrected pose + registered cloud. Detect loop closures. | Module (1 per robot) | DepthToPointCloud (In), LocalMapBuilder (Out) | SHM |
| **LocalMapBuilder** | Accumulate registered clouds into local map. Maintain voxelized point cloud + occupancy grid (OctoMap). Publish incremental updates. | Module (1 per robot) | SLAMNode (In), MapMergeServer (Out via LCM), FrontierExplorer (Out) | SHM (local), LCM (cross-process) |
| **FrontierExplorer** | Detect frontier cells in local occupancy grid (or merged grid). Filter by assigned region. Select best frontier as navigation goal. | Module (1 per robot) | LocalMapBuilder (In), RegionAllocator (In), LocalNavigator (Out) | LCM |
| **LocalNavigator** | Plan path to frontier goal. Execute velocity commands. Handle obstacle avoidance. | Module (1 per robot) | FrontierExplorer (In), SimWorldGymBridge (Out: velocity commands) | LCM/SHM |
| **MapMergeServer** | Receive local maps from both robots. Transform to global frame using known spawn poses. Fuse into unified map. Publish merged point cloud + occupancy grid. | Module (singleton) | LocalMapBuilder x2 (In via LCM), RegionAllocator (Out), RerunBridge (Out) | LCM (input), SHM (output) |
| **RegionAllocator** | Compute Voronoi partitioning of environment. Assign exploration regions to robots. Re-partition when regions are exhausted. | Module (singleton) | MapMergeServer (In), robot poses (In via LCM), FrontierExplorer x2 (Out via LCM) | LCM |
| **RerunBridge** | Visualize all data: merged map, robot poses, frontiers, exploration progress, per-robot local maps. | Module (singleton) | All other modules (various In streams) | LCM (subscribes to all topics) |

### Data Flow

**Sensor Path (per robot, 10-30 Hz):**
```
SimWorld gym.step(action)
  -> obs["depth"] -> SimWorldGymBridge -> depth_image: Out[DepthImage]
  -> obs["rgb"]   -> SimWorldGymBridge -> rgb_image: Out[Image]
  -> obs["pose"]  -> SimWorldGymBridge -> gt_pose: Out[Pose]

DepthToPointCloud:
  depth_image: In[DepthImage] -> unproject using intrinsics -> point_cloud: Out[PointCloud]

SLAMNode (RTAB-Map):
  point_cloud: In[PointCloud] + gt_pose: In[Pose] -> corrected_pose: Out[Pose] + registered_cloud: Out[PointCloud]
```

**Map Building Path (per robot, 1-5 Hz):**
```
LocalMapBuilder:
  registered_cloud: In[PointCloud] -> voxel downsample (Open3D) -> accumulate
  -> local_point_cloud: Out[PointCloud] (incremental delta)
  -> local_occupancy_grid: Out[OccupancyGrid] (OctoMap update)
```

**Map Merge Path (1-2 Hz):**
```
MapMergeServer:
  /robot_a/local_map: In (via LCM) + /robot_b/local_map: In (via LCM)
  -> transform to global frame using T_global_from_a, T_global_from_b
  -> fuse (voxel merge with conflict resolution)
  -> /merged/point_cloud: Out[PointCloud]
  -> /merged/occupancy_grid: Out[OccupancyGrid]
```

**Exploration Loop (per robot, ~1 Hz):**
```
FrontierExplorer:
  local_occupancy_grid: In[OccupancyGrid] (or merged grid)
  + assigned_region: In[Region] (from RegionAllocator)
  -> detect frontier cells within assigned region
  -> score frontiers (distance, size, information gain)
  -> select best frontier
  -> nav_goal: Out[Pose]

LocalNavigator:
  nav_goal: In[Pose]
  + local_occupancy_grid: In[OccupancyGrid]
  -> A* path planning on grid
  -> DWA local avoidance
  -> velocity_cmd: Out[Twist] -> SimWorldGymBridge
```

## Patterns to Follow

### Pattern 1: Separate Processes per Robot (NOT Fleet Mode)

**What:** Run each robot as a separate DimOS blueprint instance with its own process tree. Use LCM topics for cross-process communication between robots and the coordination layer.

**When:** Always for this project. DimOS fleet mode (`Go2FleetConnection`) broadcasts commands to all robots simultaneously and only streams sensors from the primary robot. It cannot support independent navigation or per-robot SLAM.

**Why:** Each robot needs its own SLAM instance, its own occupancy grid, its own frontier explorer, and its own navigator. Stream name isolation is natural with separate processes. Debugging is easier (crash one robot, the other continues).

**Example:**
```python
# robot_a.py -- Process 1
from dimos.core.blueprints import autoconnect

blueprint_a = autoconnect(
    simworld_gym_bridge(robot_id="a", spawn_pose=POSE_A),
    depth_to_pointcloud(),
    slam_node(config=RTABMAP_CONFIG),
    local_map_builder(voxel_size=0.05),
    frontier_explorer(),
    local_navigator(),
)
blueprint_a.build().loop()

# robot_b.py -- Process 2 (identical structure, different config)
blueprint_b = autoconnect(
    simworld_gym_bridge(robot_id="b", spawn_pose=POSE_B),
    depth_to_pointcloud(),
    slam_node(config=RTABMAP_CONFIG),
    local_map_builder(voxel_size=0.05),
    frontier_explorer(),
    local_navigator(),
)
blueprint_b.build().loop()

# coordinator.py -- Process 3
blueprint_coord = autoconnect(
    map_merge_server(spawn_transforms={
        "a": POSE_A, "b": POSE_B
    }),
    region_allocator(),
    rerun_bridge(),
)
blueprint_coord.build().loop()
```

### Pattern 2: SHM Transport for High-Bandwidth, LCM for Cross-Process

**What:** Use `pSHMTransport` for large data within a process tree (depth images, point clouds). Use `LCMTransport` for cross-process communication (map updates, poses, goals).

**When:** Always. Point clouds are 1-10 MB per message. LCM multicast is adequate for small messages (<1 KB) but wastes bandwidth on large ones.

**Example:**
```python
# Within robot blueprint (SHM for large data)
blueprint_a = blueprint_a.transports({
    "depth_image": pSHMTransport,
    "point_cloud": pSHMTransport,
    "registered_cloud": pSHMTransport,
    "local_point_cloud": pSHMTransport,
})

# Cross-process messages use LCM (default) -- no override needed
# /robot_a/local_map, /robot_a/pose, /robot_a/nav_goal all use LCM
```

### Pattern 3: Gym-to-Stream Bridge Module

**What:** A DimOS Module that owns the SimWorld gym environment handle, steps it in a timed loop, and publishes observations as typed streams. This bridges the synchronous gym step paradigm to DimOS's async pub/sub.

**When:** Required -- this is the foundational bridge between SimWorld and the DimOS pipeline.

**Key design decisions:**
- The gym step loop runs at a fixed rate (e.g., 30 Hz) in the module's dedicated process
- Velocity commands from the navigator are buffered and applied at the next step
- Observations are published immediately after each step
- Use simulation timestamps from the gym (not wall clock) for all downstream messages

```python
class SimWorldGymBridge(Module):
    # Outputs (published each step)
    rgb_image: Out[Image]
    depth_image: Out[DepthImage]
    ground_truth_pose: Out[Pose]

    # Input (from navigator)
    velocity_cmd: In[VelocityCmd]

    def __init__(self, robot_id: str, env_config: dict, step_hz: float = 30.0):
        self._robot_id = robot_id
        self._env_config = env_config
        self._step_hz = step_hz
        self._current_action = np.zeros(ACTION_DIM)

    @rpc
    def start(self) -> None:
        super().start()
        self._env = gym.make("SimWorldRobotics-v0", **self._env_config)
        obs, info = self._env.reset()
        self._publish_observations(obs, sim_time=0.0)
        self.velocity_cmd.subscribe(self._on_velocity)
        # Fixed-rate step loop
        self._timer = self.create_timer(1.0 / self._step_hz, self._step_loop)

    def _on_velocity(self, cmd: VelocityCmd):
        self._current_action = cmd.to_action_array()

    def _step_loop(self):
        obs, reward, done, truncated, info = self._env.step(self._current_action)
        sim_time = info.get("sim_time", time.monotonic())
        self._publish_observations(obs, sim_time)

    def _publish_observations(self, obs, sim_time):
        self.rgb_image.publish(Image(data=obs["rgb"], ts=sim_time))
        self.depth_image.publish(DepthImage(data=obs["depth"], ts=sim_time))
        self.ground_truth_pose.publish(Pose(data=obs["pose"], ts=sim_time))
```

### Pattern 4: Known-Transform Map Alignment (Simulation Advantage)

**What:** Since robots spawn at known positions in SimWorld, use the known spawn transforms to place each robot's local SLAM map in a shared global frame. No ICP registration or feature matching needed.

**When:** Always in simulation with known spawn poses.

**How:**
```python
class MapMergeServer(Module):
    def __init__(self, spawn_transforms: dict[str, np.ndarray]):
        # T_global_from_local for each robot
        self._transforms = spawn_transforms

    def _merge_maps(self, local_map_a, local_map_b):
        # Transform local maps to global frame
        global_cloud_a = local_map_a.point_cloud.transform(self._transforms["a"])
        global_cloud_b = local_map_b.point_cloud.transform(self._transforms["b"])

        # Fuse (not concatenate) -- voxel grid merge
        merged = open3d.geometry.PointCloud()
        merged += global_cloud_a
        merged += global_cloud_b
        merged = merged.voxel_down_sample(voxel_size=0.05)

        return merged
```

### Pattern 5: Incremental Map Updates

**What:** LocalMapBuilder publishes only new voxels/points since the last update, not the entire accumulated map.

**When:** Always, once maps exceed a few thousand points. Essential for LCM cross-process transport where bandwidth matters.

**How:** Maintain a "last published" index. Each update message contains only points added since that index. The merge server accumulates on its end.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Single SLAM Instance for Both Robots

**What:** Running one SLAM instance consuming data from both robots.

**Why bad:** Multi-robot data association is fundamentally harder. Viewpoints differ, timing differs, and a single failure affects both robots. Standard multi-robot SLAM runs independent instances and merges at the map level.

**Instead:** One RTAB-Map per robot. Merge at the map level using MapMergeServer.

### Anti-Pattern 2: DimOS Fleet Mode for Independent Robot Control

**What:** Using `Go2FleetConnection` or `unitree-go2-fleet` blueprint for two independently-navigating robots.

**Why bad:** Fleet mode broadcasts the same commands to all robots. Only the primary robot's sensors are published. No per-robot navigation or SLAM is possible.

**Instead:** Separate blueprint instances per robot. Custom coordination via LCM.

### Anti-Pattern 3: Blocking Gym Step on SLAM Processing

**What:** Calling `env.step()` synchronously with SLAM, so simulation waits for SLAM to finish before advancing.

**Why bad:** SLAM takes 50-200ms per frame. Blocking means 5-20 Hz simulation rate, causing unrealistic dynamics and wasted GPU time.

**Instead:** Decouple via DimOS streams. Gym bridge publishes asynchronously. SLAM processes at its own rate, dropping frames if behind. Gym loop runs at full speed.

### Anti-Pattern 4: Full-Resolution Point Cloud Accumulation

**What:** Storing every point from every depth frame without downsampling.

**Why bad:** 640x480 depth at 30 Hz = ~9M points/second. Memory explodes within minutes.

**Instead:** Voxel grid downsampling in LocalMapBuilder. 2-5 cm voxels for navigation, 1 cm for high-quality visualization. Use Open3D `voxel_down_sample()`.

### Anti-Pattern 5: Autoconnect for Multi-Robot Pipelines in Single Process

**What:** Using `autoconnect()` with two identically-named robot pipelines in one blueprint.

**Why bad:** Stream names collide. Robot B's odometry wires to Robot A's navigator. Debugging is extremely difficult.

**Instead:** Separate processes (recommended) or explicit `.remappings()` with robot-specific prefixes.

## Scalability Considerations

| Concern | 2 Robots (target) | 4 Robots | 10+ Robots |
|---------|-------------------|----------|------------|
| SLAM compute | 2 RTAB-Map instances, comfortable | 4 instances, may need GPU sharing | Distributed compute needed |
| Map merge | Pairwise in global frame, trivial | N maps to merge, still O(N) | Hierarchical merge tree |
| Point cloud memory | ~50M points after 10 min (5cm voxels) | ~100M points | Octree required, Open3D struggles |
| Gym stepping | 1 env with 2 agents, fine | May need env partitioning | Multiple SimWorld instances |
| Exploration coord | Voronoi partition, simple | Voronoi still works | Auction-based allocation |
| Inter-process comm | ~100 MB/s LCM, manageable | ~200 MB/s, OK | DDS transport needed |
| Process management | 3 processes, manual start | 6 processes, needs orchestrator | Kubernetes or similar |

## Sources

- DimOS architecture docs (local: `docs/architecture.md`) -- HIGH confidence
- DimOS robots docs (local: `docs/robots.md`) -- HIGH confidence
- DimOS fleet mode behavior (local: `docs/examples.md`, `.planning/codebase/CONCERNS.md`) -- HIGH confidence
- RTAB-Map multi-session capabilities -- HIGH confidence (verified v0.23.1)
- OctoMap octree mapping -- HIGH confidence (verified v1.10.0)
- Multi-robot SLAM architecture patterns -- MEDIUM confidence (training knowledge, well-established in literature)
- SimWorld gym API specifics -- LOW confidence (inferred from PROJECT.md)

---

*Architecture research: 2026-03-17*
