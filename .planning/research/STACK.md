# Technology Stack

**Project:** Multi-Robot 3D Reconstruction (SimWorld)
**Researched:** 2026-03-17

## Recommended Stack

### Core Framework & Orchestration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| DimOS | 0.0.11 | Robot orchestration, module composition, agent skills | Project constraint. Already supports Go2 fleet mode, spatial perception, SLAM, and LangGraph agents. Blueprint system enables clean module composition. | HIGH |
| Python | 3.12 | Primary language | DimOS ecosystem is Python-native. Nix flake already provisions 3.12. | HIGH |
| Nix | flake | Reproducible dev environment | Already configured in repo. Handles system deps (LCM, graphics, audio) cleanly. | HIGH |

### Simulation Environment

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| SimWorld-Robotics | latest | UE5 simulation with OpenAI gym interface | Project constraint. JHU research platform with procedural urban scenes, multi-robot support (MRS benchmark), and quadruped robot models. Provides sensor simulation (RGB, depth, LiDAR) through gym observations. | MEDIUM |
| gymnasium | 1.0+ | Gym interface wrapper | SimWorld exposes an OpenAI gym-compatible interface. Use gymnasium (successor to gym) for step/reset/observation API. | MEDIUM |

**SimWorld-Robotics notes:** This is a relatively new academic platform (NUS-ARSL / JHU). Documentation may be sparse. The gym interface provides observation dictionaries with sensor data (RGB images, depth maps, potentially LiDAR point clouds) and accepts action vectors for robot control. The `world_buffer.py` multi-agent environment supports spawning multiple robots. Expect to write a DimOS Module that wraps the gym interface to bridge SimWorld observations into DimOS streams.

### SLAM (Simultaneous Localization and Mapping)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| RTAB-Map | 0.23.1 | Per-robot visual SLAM + 3D reconstruction | Best choice for this project. Supports RGB-D and stereo input, produces 3D point clouds and occupancy grids simultaneously, has built-in multi-session and multi-robot map merging via inter-session loop closure, works with ROS 2 Humble/Jazzy, and is actively maintained (35 releases, 3600+ commits). Most battle-tested visual SLAM for 3D reconstruction. | HIGH |
| rtabmap_ros | 0.23.x | ROS 2 wrapper for RTAB-Map | Required for ROS 2 integration. Provides launch files, topic interfaces, and service calls for map management. Available via apt on ROS 2 Humble/Jazzy. | HIGH |

**Why RTAB-Map over alternatives:**

- **ORB-SLAM3 (rejected):** Excellent for localization but produces sparse feature maps, not dense 3D reconstruction. No native occupancy grid output. No built-in multi-robot merging. Research-grade code with GPL license and poor ROS 2 integration.
- **Kimera (rejected):** Impressive metric-semantic SLAM from MIT-SPARK, but the main index repo last updated Feb 2021. Sub-repositories (Kimera-VIO, Kimera-RPGO, Kimera-Semantics) are more active but integration is complex. Primarily stereo+IMU focused. Overkill for this project since we do not need semantic mesh annotation. ROS 2 support exists but is not as mature as RTAB-Map's.
- **Swarm-SLAM (considered, defer):** Decentralized multi-robot SLAM supporting multiple front-ends (ORB-SLAM3, RTAB-Map, LiDAR). Interesting for the multi-robot aspect but adds significant complexity. It is a research system from Lajoie et al. (2023-2024) built on ROS 2 Humble. Consider if RTAB-Map's built-in multi-session merging proves insufficient, but start simpler.
- **FAST-LIO2 (complementary, optional):** DimOS already has `mid360-fastlio` blueprints. If SimWorld provides LiDAR data, FAST-LIO2 could complement visual SLAM. However, since SimWorld simulates depth cameras more naturally than LiDAR, prioritize RGB-D SLAM.

### Multi-Robot Map Merging

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| RTAB-Map multi-session | 0.23.x | Map merging via inter-session loop closure | RTAB-Map natively supports loading multiple map databases and finding loop closures between them. This is the simplest path to map merging for two robots. Each robot builds its own RTAB-Map database; a central node merges them by detecting visual loop closures. | HIGH |
| map_merge_3d (fallback) | ROS 2 | Point cloud map merging | If RTAB-Map's inter-session approach is insufficient, use ICP-based point cloud registration to align maps. Available as ROS 2 package. Only needed as fallback. | LOW |

**Map merging strategy:** Run RTAB-Map independently on each robot. A central "map merger" DimOS module subscribes to both robots' map data streams, feeds them to a single RTAB-Map instance in multi-session mode, and publishes the unified map. This approach leverages RTAB-Map's proven loop closure detection rather than requiring custom registration code.

### 3D Reconstruction & Point Cloud Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Open3D | 0.18+ | Point cloud processing, mesh generation, ICP registration | Best Python point cloud library. Faster than PCL Python bindings, cleaner API, GPU-accelerated operations, built-in TSDF volume integration for dense reconstruction. Already used in the DimOS ecosystem (C++ interop). | HIGH |
| OctoMap | 1.10.0 | Octree-based 3D occupancy grid | Industry standard for probabilistic 3D occupancy mapping. Memory-efficient octree structure handles large environments. v1.10.0 (March 2024) is current. Produces navigation-grade occupancy grids from point clouds. | HIGH |
| octomap_server2 | ROS 2 | ROS 2 OctoMap server | Bridges point cloud topics to OctoMap and publishes occupancy grids. Available for ROS 2 Humble. | MEDIUM |

**Why Open3D over PCL:**
- PCL (Point Cloud Library) is the traditional choice but its Python bindings are poor, build system is complex, and the project has slow development cadence.
- Open3D provides equivalent functionality with a clean Python API, pip-installable, GPU acceleration via CUDA/Tensor, and active development from Intel ISL.

### Occupancy & Navigation Grids

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| OctoMap | 1.10.0 | 3D occupancy grid (octree) | See above. Primary 3D occupancy representation. | HIGH |
| nav2_costmap_2d (optional) | ROS 2 Humble | 2D navigation costmap | If DimOS's built-in navigation needs a 2D projection of the 3D map for path planning. DimOS already has its own planner (`--planner-strategy`) so this may not be needed. | LOW |

### ROS 2 Integration Layer

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| ROS 2 Humble | Humble Hawksbill | Middleware for SLAM nodes | RTAB-Map and OctoMap run as ROS 2 nodes. DimOS has `ROSTransport` for bridging DimOS streams to ROS 2 topics. Use ROS 2 as the SLAM backbone, DimOS for orchestration. | HIGH |
| ros2_bridge (DimOS) | built-in | DimOS-to-ROS 2 stream bridge | DimOS `unitree-go2-ros` blueprint and `ROSTransport` provide bidirectional topic translation. Use this to publish SimWorld sensor data as ROS 2 topics for RTAB-Map consumption. | HIGH |

**Architecture decision:** DimOS is the orchestration layer; ROS 2 is the SLAM computation layer. SimWorld gym observations flow into DimOS modules, get published as ROS 2 topics (via ROSTransport), consumed by RTAB-Map nodes, and results flow back into DimOS streams for the agent and visualization.

### Exploration & Coverage Planning

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Custom frontier-based exploration | n/a | Autonomous exploration with split-room strategy | No off-the-shelf multi-robot exploration planner fits this project's split-room constraint. Implement frontier-based exploration as a DimOS Module using the OctoMap occupancy grid. Frontier cells (boundary between known-free and unknown) drive exploration targets. | MEDIUM |
| explore_lite (reference only) | ROS 2 | Reference implementation for frontier detection | Useful as algorithmic reference but do not use directly -- it is a ROS 1 port with limited multi-robot support. Extract the frontier detection algorithm and implement it as a DimOS skill. | LOW |

**Exploration strategy:** Each robot gets assigned a spatial region (split-room). Within its region, the robot uses frontier-based exploration: detect frontiers in the occupancy grid, select the nearest/largest frontier, navigate to it, repeat. The DimOS agent (LangGraph + GPT-4o) orchestrates high-level task allocation; the frontier planner handles low-level waypoint generation.

### Visualization

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Rerun SDK | 0.20.0+ | Real-time 3D visualization | Already integrated in DimOS. Visualize point clouds, occupancy grids, robot trajectories, and exploration frontiers. Supports web viewer for remote monitoring. | HIGH |
| Rerun (web) | 0.20.0+ | Browser-based 3D viewer | `dimos --viewer rerun-web` for remote access to visualization. | HIGH |

### Agent & Coordination

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| LangGraph (via DimOS Agent) | built-in | Multi-robot task orchestration | DimOS Agent uses LangGraph with tool calling. Define exploration skills (@skill decorated) that the agent invokes for task allocation, region assignment, and coordination. | HIGH |
| DimOS Fleet Mode | built-in | Multi-robot communication | `unitree-go2-fleet` blueprint supports multiple robot IPs. Extend for SimWorld with per-robot gym environment instances. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| NumPy | 1.26.4+ | Array operations | Always -- point cloud data, transformations |
| SciPy | 1.15.1+ | Spatial algorithms (KDTree, transforms) | Frontier detection, nearest-neighbor queries |
| OpenCV (cv2) | 4.x | Image processing | SimWorld RGB/depth image preprocessing |
| transforms3d or scipy.spatial.transform | latest | 3D transformations | Coordinate frame conversions between SimWorld, RTAB-Map, OctoMap |
| FilterPy | 1.4.5+ | Kalman filtering | Robot pose smoothing if SimWorld odometry is noisy |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| SLAM | RTAB-Map | ORB-SLAM3 | Sparse maps, no occupancy grid, GPL, poor ROS 2 support |
| SLAM | RTAB-Map | Kimera | Stale integration repo, complex setup, overkill for non-semantic task |
| SLAM | RTAB-Map | Swarm-SLAM | Research system, adds complexity; RTAB-Map's multi-session is simpler for 2 robots |
| SLAM | RTAB-Map | FAST-LIO2 | LiDAR-only; SimWorld primary sensor is RGB-D |
| Point Cloud | Open3D | PCL | Poor Python bindings, complex build, slower development |
| Occupancy | OctoMap | Voxblox/Voxgraph | More complex, less mature ROS 2 support, overkill for non-TSDF pipeline |
| Exploration | Custom frontier | explore_lite | ROS 1 port, no multi-robot, no split-room support |
| Exploration | Custom frontier | GBPlanner/FUEL | Too complex for this project, designed for UAVs |
| Simulation | SimWorld | Gazebo/Isaac Sim | Project constraint -- SimWorld is required |
| Orchestration | DimOS | Pure ROS 2 | Project constraint -- DimOS is required |

## Installation

```bash
# DimOS with required extras
pip install 'dimos[base,unitree]'

# ROS 2 Humble (Ubuntu 22.04) -- system-level
sudo apt install ros-humble-desktop

# RTAB-Map for ROS 2
sudo apt install ros-humble-rtabmap ros-humble-rtabmap-ros

# OctoMap for ROS 2
sudo apt install ros-humble-octomap ros-humble-octomap-server

# Python libraries
pip install open3d gymnasium numpy scipy opencv-python-headless

# SimWorld-Robotics (install from source -- academic repo)
# git clone <simworld-repo> && pip install -e .
```

**Nix alternative (preferred for this project):**
The existing `flake.nix` should be extended to include ROS 2 packages. Consider using `nix-ros-overlay` for reproducible ROS 2 integration within the Nix environment.

## Version Compatibility Matrix

| Component | Version | ROS 2 Humble | Ubuntu 22.04 | Python 3.12 |
|-----------|---------|-------------|-------------|-------------|
| RTAB-Map | 0.23.1 | Yes | Yes | Yes |
| OctoMap | 1.10.0 | Yes | Yes | Yes |
| Open3D | 0.18+ | n/a | Yes | Yes |
| DimOS | 0.0.11 | Bridge | Yes | Yes |
| Rerun | 0.20+ | n/a | Yes | Yes |

## Sources

- RTAB-Map GitHub: github.com/introlab/rtabmap (v0.23.1, Oct 2025) -- verified via WebFetch
- Kimera GitHub: github.com/MIT-SPARK/Kimera (last index update Feb 2021) -- verified via WebFetch
- OctoMap GitHub: github.com/OctoMap/octomap (v1.10.0, Mar 2024) -- verified via WebFetch
- DimOS documentation: local project docs/ directory -- HIGH confidence
- DimOS codebase analysis: .planning/codebase/ -- HIGH confidence
- ORB-SLAM3, Swarm-SLAM, Open3D, PCL, Nav2, exploration algorithms: training data -- MEDIUM confidence (well-established libraries, unlikely to have changed fundamentally)
- SimWorld-Robotics details: training data + PROJECT.md -- LOW confidence (academic platform, could not verify current API)

---

*Stack research: 2026-03-17*
