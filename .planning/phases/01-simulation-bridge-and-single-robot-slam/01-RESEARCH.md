# Phase 1: Simulation Bridge and Single-Robot SLAM - Research

**Researched:** 2026-03-17
**Domain:** SimWorld gym integration, RGB-D SLAM pipeline, 3D visualization
**Confidence:** MEDIUM (SimWorld gym API is LOW; SLAM and visualization stack are HIGH)

## Summary

Phase 1 connects a single Go2 quadruped to SimWorld-Robotics via its gymnasium interface, extracts RGB-D sensor data and ground-truth poses, runs SLAM to produce a 3D point cloud and occupancy grid, and visualizes everything in Rerun. The biggest unknown is the SimWorld gym API -- its observation/action space format, achievable step rate, and sensor availability must be discovered empirically by reading the `simworld_gym` source code.

The recommended approach is: (1) clone SimWorld-Robotics and study the gym environment code to understand observation/action spaces, (2) build a minimal SimWorldGymBridge that steps the environment and publishes sensor data, (3) integrate RTAB-Map for SLAM (standalone C++ library approach preferred over ROS 2 to avoid heavyweight dependency), (4) use Open3D for point cloud processing and octomap-python for occupancy grids, (5) stream everything to Rerun for live visualization, (6) compute ATE/RPE drift metrics using the `evo` library against ground-truth poses.

**Primary recommendation:** Start with SimWorld gym source code investigation (parallel with bridge scaffolding). Use RTAB-Map standalone library if Python bindings are viable; fall back to ROS 2 `rtabmap_ros` if not. Use `evo` library for trajectory evaluation. Use `pynput` for keyboard teleop.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Go/no-go criterion:** SimWorld gym must deliver sensor data at 5+ Hz. Below that, pivot to batch processing (drop real-time requirement).
- **Sensor fallback:** If SimWorld provides RGB only (no depth), switch to monocular SLAM (ORB-SLAM3 monocular mode). Scale ambiguity accepted.
- **Investigation approach:** Work in parallel -- one effort tries the gym API directly, another reads SimWorld source code to understand sensor internals.
- **Scope reduction plan:** If gym step rate is below 5 Hz, reduce scope to batch/offline processing. Pre-recording is NOT the fallback.
- **Control modes:** Build all three -- keyboard teleop (WASD), scripted waypoints, and random walk. Keyboard teleop is primary testing interface.
- **Control longevity:** Reusable across all phases. Build properly, not throwaway.
- **Control architecture:** Claude's call -- DimOS Module with Out stream preferred.
- **SLAM quality bar:** Three criteria must ALL pass: visual inspection (point cloud looks like environment), drift metric (ATE + RPE reported), map completeness (covers visited areas).
- **Drift metrics:** Report both ATE and RPE. No hard numerical threshold -- qualitative judgment.
- **Viewer:** Rerun for all 3D visualization.

### Claude's Discretion
- Control module architecture (DimOS Module with Out stream vs standalone script)

### Deferred Ideas (OUT OF SCOPE)
None captured during discussion.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SIM-01 | Connect to SimWorld gym environment and manage lifecycle (start/stop/reset) | SimWorld gym uses gymnasium API: `gym.make()`, `env.reset()`, `env.step()`, `env.close()`. Asynchronous world_buffer.py for multi-agent. |
| SIM-02 | Extract depth and RGB sensor data per robot per gym step | SimWorld provides RGB, depth, and segmentation per step. Observation dict keys must be discovered from source. Fallback to monocular if no depth. |
| SIM-03 | Dispatch independent movement commands to each of two Go2 robots | SimWorld supports continuous translation (forward/back/left/right) + free-angle rotation. Centralized buffer with per-agent availability flags. Phase 1 only needs single robot. |
| SIM-04 | Extract ground-truth pose (position + orientation) per robot per step | SimWorld provides ground-truth orientation via built-in compass. Full pose extraction needs source verification. |
| SLAM-01 | Run RTAB-Map RGB-D SLAM producing local pose graph and map | RTAB-Map v0.23.1 supports RGB-D mode. C++ library has standalone API (Rtabmap, Odometry, SensorData classes). Python bindings exist but are limited. ROS 2 rtabmap_ros is the proven path. |
| SLAM-02 | Output 3D point cloud of explored area | RTAB-Map produces registered point clouds via `util3d::cloudRGBFromSensorData()`. Open3D for Python-side accumulation and voxel downsampling. |
| SLAM-03 | Output OctoMap 3D occupancy grid for navigation | octomap-python (`pip install octomap-python`) provides Python bindings for octree creation and point cloud insertion. |
| SLAM-04 | Compare SLAM poses to ground-truth and report drift metrics | `evo` library (`pip install evo`) provides ATE (`evo_ape`) and RPE (`evo_rpe`) computation with Python API. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SimWorld-Robotics | latest (Dec 2025) | UE5 simulation with gym interface | Project constraint. Provides RGB, depth, segmentation sensors and multi-robot control. |
| gymnasium | 1.0+ | Gym wrapper for SimWorld | Standard successor to OpenAI gym. SimWorld follows gym API conventions. |
| RTAB-Map | 0.23.1 | RGB-D SLAM (pose graph + map) | Battle-tested visual SLAM. Supports RGB-D input, produces point clouds + occupancy data, has loop closure. 3600+ commits, actively maintained. |
| rtabmap_ros | 0.23.x | ROS 2 wrapper for RTAB-Map | Most reliable way to run RTAB-Map. Provides topic interfaces for RGB-D input and map output. |
| Open3D | 0.18+ | Point cloud processing | Best Python point cloud library. pip-installable, GPU-accelerated, clean API. |
| octomap-python | 1.8.0 | Python OctoMap bindings | Direct Python access to octree creation and point cloud insertion. Avoids ROS dependency for occupancy grids. |
| Rerun SDK | 0.30.2 | Live 3D visualization | Points3D, Image, Transform3D archetypes. Supports streaming updates and web viewer. Python 3.10+. |
| evo | latest | Trajectory evaluation (ATE/RPE) | Standard tool for SLAM evaluation. Python API for programmatic use. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pynput | 1.7.6+ | Keyboard input for teleop | WASD keyboard teleop. Cross-platform, works without terminal focus. |
| NumPy | 1.26+ | Array operations | Always -- point cloud data, transforms, sensor arrays |
| OpenCV (cv2) | 4.x | Image processing | Depth image preprocessing, undistortion |
| scipy.spatial.transform | 1.15+ | 3D rotations/transforms | Coordinate frame conversions (Rotation, Transform) |
| DimOS | 0.0.11 | Module/Stream orchestration | Module architecture for bridge, SLAM pipeline, teleop |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| RTAB-Map (ROS 2) | RTAB-Map standalone C++ library | Avoids ROS 2 dependency but Python bindings are limited/undocumented. Try standalone first, fall back to ROS 2. |
| RTAB-Map | ORB-SLAM3 monocular | Only if SimWorld has no depth sensor. Sparse maps, scale ambiguity. CONTEXT.md fallback. |
| octomap-python | octomap_server2 (ROS 2) | ROS 2 package. Use if already running ROS 2 for RTAB-Map; otherwise octomap-python is simpler. |
| pynput | curses | curses requires terminal focus and doesn't work on Windows. pynput is more flexible. |

**Installation:**
```bash
# Core Python packages
pip install gymnasium open3d octomap-python rerun-sdk evo pynput numpy scipy opencv-python-headless

# SimWorld-Robotics (from source)
git clone https://github.com/SCAI-JHU/SimWorld-Robotics.git
cd SimWorld-Robotics/simworld_gym && pip install -e . && cd ../..

# RTAB-Map via ROS 2 (if using ROS 2 approach)
sudo apt install ros-humble-rtabmap ros-humble-rtabmap-ros

# DimOS
pip install 'dimos[base,unitree]'
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── bridge/                  # SimWorld gym bridge
│   ├── sim_bridge.py        # SimWorldGymBridge module - steps env, publishes observations
│   ├── sensor_types.py      # Data classes for RGB, Depth, Pose observations
│   └── env_config.py        # SimWorld environment configuration
├── slam/                    # SLAM pipeline
│   ├── slam_pipeline.py     # RTAB-Map integration (ROS 2 or standalone)
│   ├── depth_to_cloud.py    # Depth image -> 3D point cloud conversion
│   └── octomap_builder.py   # Point cloud -> OctoMap occupancy grid
├── control/                 # Robot control
│   ├── teleop.py            # Keyboard WASD teleop (pynput)
│   ├── waypoint_runner.py   # Scripted waypoint follower
│   └── random_walk.py       # Random exploration controller
├── metrics/                 # Evaluation
│   ├── drift_metrics.py     # ATE/RPE computation using evo library
│   └── ground_truth.py      # Ground-truth pose collection and formatting
├── viz/                     # Visualization
│   └── rerun_viz.py         # Rerun streaming for point cloud, grid, trajectory
└── main.py                  # Entry point - wires modules together
```

### Pattern 1: SimWorld Gym Bridge (Event-Driven Step Loop)

**What:** A module that owns the SimWorld gym environment handle, steps it at a target rate, and publishes observations as typed data. Bridges synchronous gym `step()` to async downstream consumers.

**When to use:** Always -- this is the foundational interface between SimWorld and everything else.

**Example:**
```python
# Source: SimWorld-Robotics paper + gymnasium API conventions
import gymnasium as gym
import numpy as np
from dataclasses import dataclass

@dataclass
class SensorFrame:
    rgb: np.ndarray          # (H, W, 3) uint8
    depth: np.ndarray        # (H, W) float32, meters
    ground_truth_pose: np.ndarray  # (4, 4) homogeneous transform
    sim_time: float          # simulation timestamp

class SimWorldGymBridge:
    def __init__(self, env_id: str, env_kwargs: dict = None):
        self._env_id = env_id
        self._env_kwargs = env_kwargs or {}
        self._env = None
        self._current_action = None  # velocity command buffer

    def start(self):
        self._env = gym.make(self._env_id, **self._env_kwargs)
        obs, info = self._env.reset()
        return self._parse_observation(obs, info)

    def step(self, action: np.ndarray = None) -> SensorFrame:
        if action is None:
            action = self._current_action or np.zeros(self._action_dim)
        obs, reward, done, truncated, info = self._env.step(action)
        return self._parse_observation(obs, info)

    def _parse_observation(self, obs, info) -> SensorFrame:
        # Keys must be discovered from SimWorld source code
        return SensorFrame(
            rgb=obs.get("rgb", obs.get("image", None)),
            depth=obs.get("depth", None),
            ground_truth_pose=obs.get("pose", info.get("pose", None)),
            sim_time=info.get("sim_time", 0.0),
        )

    def set_velocity(self, linear: np.ndarray, angular: float):
        """Buffer velocity command for next step."""
        self._current_action = np.concatenate([linear, [angular]])

    def stop(self):
        if self._env:
            self._env.close()
            self._env = None
```

### Pattern 2: Depth-to-Point-Cloud Conversion

**What:** Unproject depth image to 3D points using camera intrinsics. This is the bridge between 2D sensor data and 3D SLAM input.

**When to use:** Every frame from SimWorld that has depth data.

**Example:**
```python
# Source: Standard pinhole camera model
import numpy as np
import open3d as o3d

def depth_to_pointcloud(
    depth: np.ndarray,       # (H, W) float32, meters
    rgb: np.ndarray,         # (H, W, 3) uint8
    fx: float, fy: float,    # focal lengths in pixels
    cx: float, cy: float,    # principal point
    max_depth: float = 10.0, # clip far points
) -> o3d.geometry.PointCloud:
    h, w = depth.shape
    u, v = np.meshgrid(np.arange(w), np.arange(h))

    valid = (depth > 0) & (depth < max_depth)
    z = depth[valid]
    x = (u[valid] - cx) * z / fx
    y = (v[valid] - cy) * z / fy

    points = np.stack([x, y, z], axis=-1)
    colors = rgb[valid].astype(np.float64) / 255.0

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    return pcd
```

### Pattern 3: RTAB-Map Integration (Two Paths)

**Path A: ROS 2 rtabmap_ros (recommended if ROS 2 already available):**
- Launch `rtabmap_ros` node with RGB-D configuration
- Publish sensor data as ROS 2 topics (`sensor_msgs/Image`, `sensor_msgs/CameraInfo`)
- Subscribe to output topics (`/rtabmap/mapData`, `/rtabmap/odom`)
- Use DimOS `ROSTransport` for bridging

**Path B: Standalone (attempt first, fall back to Path A):**
- RTAB-Map C++ library has `Rtabmap`, `Odometry`, `SensorData` classes
- Python bindings (`rtabmap_python`) exist but are limited to PyMatcher/PyDetector
- Full standalone SLAM requires C++ wrapper or subprocess approach

**Recommendation:** Start with Path B investigation (check if `rtabmap_python` supports full SLAM pipeline). If not viable within 2 hours, switch to Path A (ROS 2). The ROS 2 path is proven and well-documented.

### Pattern 4: Occupancy Grid from Point Cloud

**What:** Convert accumulated point cloud to octree-based occupancy grid using octomap-python.

**Example:**
```python
# Source: octomap-python API (inferred from examples)
import octomap
import numpy as np

class OctoMapBuilder:
    def __init__(self, resolution: float = 0.1):
        self._tree = octomap.OcTree(resolution)

    def insert_scan(self, points: np.ndarray, sensor_origin: np.ndarray):
        """Insert a point cloud scan into the octree.

        Args:
            points: (N, 3) float64 array of 3D points in global frame
            sensor_origin: (3,) sensor position for ray-casting
        """
        self._tree.insertPointCloud(
            pointcloud=points.astype(np.float64),
            origin=sensor_origin.astype(np.float64),
        )

    def get_occupied_voxels(self) -> np.ndarray:
        """Get centers of all occupied voxels."""
        occupied = []
        for node in self._tree.begin_tree():
            if self._tree.isNodeOccupied(node):
                occupied.append([node.getX(), node.getY(), node.getZ()])
        return np.array(occupied) if occupied else np.empty((0, 3))
```

### Pattern 5: Drift Metrics with evo Library

**What:** Compute ATE and RPE programmatically using evo's Python API.

**Example:**
```python
# Source: evo library API (github.com/MichaelGrupp/evo)
from evo.core.trajectory import PoseTrajectory3D
from evo.core import metrics, sync
import numpy as np

def compute_drift_metrics(
    slam_poses: list[np.ndarray],    # list of (4,4) transforms
    gt_poses: list[np.ndarray],      # list of (4,4) transforms
    timestamps: list[float],
) -> dict:
    """Compute ATE and RPE between SLAM and ground-truth trajectories."""
    slam_traj = PoseTrajectory3D(
        poses_se3=slam_poses,
        timestamps=np.array(timestamps),
    )
    gt_traj = PoseTrajectory3D(
        poses_se3=gt_poses,
        timestamps=np.array(timestamps),
    )

    # Sync trajectories by timestamp
    gt_synced, slam_synced = sync.associate_trajectories(gt_traj, slam_traj)

    # ATE (Absolute Trajectory Error)
    ate_metric = metrics.APE(metrics.PoseRelation.translation_part)
    ate_metric.process_data((gt_synced, slam_synced))

    # RPE (Relative Pose Error)
    rpe_metric = metrics.RPE(metrics.PoseRelation.translation_part)
    rpe_metric.process_data((gt_synced, slam_synced))

    return {
        "ate_rmse": ate_metric.get_statistic(metrics.StatisticsType.rmse),
        "ate_mean": ate_metric.get_statistic(metrics.StatisticsType.mean),
        "rpe_rmse": rpe_metric.get_statistic(metrics.StatisticsType.rmse),
        "rpe_mean": rpe_metric.get_statistic(metrics.StatisticsType.mean),
    }
```

### Pattern 6: Rerun Streaming Visualization

**What:** Stream point cloud, occupancy grid voxels, trajectory, and images to Rerun viewer.

**Example:**
```python
# Source: Rerun SDK docs (rerun.io/docs)
import rerun as rr
import numpy as np

class RerunVisualizer:
    def __init__(self, app_name: str = "slam_viz"):
        rr.init(app_name, spawn=True)

    def log_frame(self, frame, slam_pose=None, gt_pose=None):
        """Log a single frame's data to Rerun."""
        # RGB image
        rr.log("camera/rgb", rr.Image(frame.rgb))

        # Depth image (as grayscale)
        rr.log("camera/depth", rr.DepthImage(frame.depth))

    def log_point_cloud(self, points: np.ndarray, colors: np.ndarray = None):
        """Log accumulated point cloud."""
        if colors is not None:
            rr.log("map/point_cloud", rr.Points3D(points, colors=colors))
        else:
            rr.log("map/point_cloud", rr.Points3D(points))

    def log_occupancy_grid(self, voxel_centers: np.ndarray, resolution: float):
        """Log occupied voxels as colored boxes."""
        rr.log("map/occupancy", rr.Points3D(
            voxel_centers,
            radii=resolution / 2.0,
            colors=[0, 200, 0],  # green for occupied
        ))

    def log_trajectory(self, poses: list[np.ndarray], entity: str = "robot/trajectory"):
        """Log robot trajectory as a line strip."""
        positions = np.array([p[:3, 3] for p in poses])
        rr.log(entity, rr.LineStrips3D([positions]))

    def log_robot_pose(self, pose: np.ndarray, entity: str = "robot/current"):
        """Log current robot position."""
        rr.log(entity, rr.Transform3D(
            translation=pose[:3, 3],
            mat3x3=pose[:3, :3],
        ))
```

### Anti-Patterns to Avoid
- **Blocking gym step on SLAM processing:** SLAM takes 50-200ms per frame. Decouple via async queue or threading. Gym loop runs at its own rate; SLAM processes frames as fast as it can, dropping if behind.
- **Full-resolution point cloud accumulation:** 640x480 at 30Hz = 9M points/sec. Always voxel downsample (0.05-0.1m) before accumulation.
- **Using wall clock time for SLAM:** SimWorld has simulation time. Use sim timestamps exclusively for all SLAM and metric computation.
- **Hardcoding observation dictionary keys:** SimWorld API is LOW confidence. Wrap observation parsing in a single function and log raw keys on first run for discovery.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visual SLAM | Custom visual odometry + loop closure | RTAB-Map | Thousands of engineering hours in loop closure, pose graph optimization, memory management |
| Trajectory evaluation | Custom ATE/RPE computation | `evo` library | Handles timestamp sync, SE3 alignment, multiple metrics, statistical aggregation |
| 3D occupancy mapping | Custom voxel grid with ray-casting | `octomap-python` | Probabilistic updates, memory-efficient octree, proper ray-casting for free-space |
| Point cloud operations | Manual numpy point operations | Open3D | Voxel downsampling, ICP, normal estimation, I/O -- all optimized C++ with Python API |
| Depth unprojection | (fine to hand-roll -- it's 10 lines) | But verify with Open3D's `create_from_depth_image` | Open3D has `create_from_rgbd_image()` that handles intrinsics correctly |
| Keyboard input | Raw terminal/stdin polling | `pynput` | Cross-platform, doesn't require terminal focus, proper key event handling |

**Key insight:** Phase 1 is an integration phase, not an algorithms phase. The value is in correctly wiring SimWorld observations through SLAM to visualization. Every component has a proven library -- the risk is in the glue, not the algorithms.

## Common Pitfalls

### Pitfall 1: SimWorld Gym Observation Keys Unknown
**What goes wrong:** Code assumes specific dictionary keys (`obs["rgb"]`, `obs["depth"]`) but SimWorld uses different keys. Code crashes on first run.
**Why it happens:** SimWorld gym API is not well-documented externally. Observation space format must be discovered from source.
**How to avoid:** First task must be reading `simworld_gym/envs/` source code to discover observation and action space. Log `obs.keys()` and `obs[key].shape` for every key on first successful step. Write a discovery script before building the full bridge.
**Warning signs:** `KeyError` on first env.step() call.

### Pitfall 2: SimWorld Step Rate Below 5 Hz
**What goes wrong:** UE5 rendering is computationally expensive. Each gym step may take 200ms+ (5 Hz) or worse, making real-time SLAM impossible.
**Why it happens:** SimWorld renders photorealistic scenes in UE5. Without GPU acceleration or render quality reduction, step rate is too slow.
**How to avoid:** Measure step rate BEFORE building SLAM pipeline. This is the go/no-go gate per CONTEXT.md. If below 5 Hz, pivot to batch/offline processing.
**Warning signs:** `time.monotonic()` delta between steps exceeding 200ms consistently.

### Pitfall 3: Missing Depth Sensor in SimWorld
**What goes wrong:** SimWorld may provide RGB and segmentation but depth images may not be in the default observation space for the quadruped robot model.
**Why it happens:** Different robot models in SimWorld may have different sensor configurations. The paper confirms depth is available but specific robot configs vary.
**How to avoid:** Per CONTEXT.md fallback: if no depth, switch to ORB-SLAM3 monocular mode. Check observation space during discovery phase.
**Warning signs:** `obs.get("depth")` returns None or key doesn't exist.

### Pitfall 4: Camera Intrinsics Not Provided by SimWorld
**What goes wrong:** Depth-to-pointcloud conversion requires focal length (fx, fy) and principal point (cx, cy). SimWorld may not expose these directly.
**Why it happens:** Gym environments often abstract away camera parameters. UE5 has camera settings but they may not be exposed in the gym observation.
**How to avoid:** Check SimWorld source for camera configuration. If not available: (a) look at UE5 scene config files, (b) assume standard FOV and compute intrinsics from image resolution, (c) use RTAB-Map's auto-calibration.
**Warning signs:** Point cloud has wrong scale or barrel distortion.

### Pitfall 5: Simulation Time vs Wall Clock Desynchronization
**What goes wrong:** SLAM algorithms expect real-time or known-rate data. SimWorld may step faster or slower than real-time. Using wall clock timestamps causes motion estimation errors.
**Why it happens:** Gym environments step at variable rate depending on compute load.
**How to avoid:** Use simulation timestamps from `info` dict (or compute from step count * dt). Never use `time.time()` for SLAM timestamps.
**Warning signs:** SLAM reports impossibly fast or slow motion.

### Pitfall 6: RTAB-Map Python Bindings Are Limited
**What goes wrong:** Attempting to use `rtabmap_python` for full SLAM pipeline and discovering it only supports feature matching (PyMatcher/PyDetector), not the full Rtabmap SLAM engine.
**Why it happens:** RTAB-Map's Python interface is designed for extending C++ feature matching with Python models, not for running SLAM from Python.
**How to avoid:** Time-box standalone investigation to 2 hours. If full SLAM API isn't available in Python, switch to ROS 2 `rtabmap_ros` approach. The ROS 2 path is proven.
**Warning signs:** ImportError for core SLAM classes, only matcher/detector available.

### Pitfall 7: OctoMap Memory Growth
**What goes wrong:** Inserting every frame's point cloud into OctoMap without bounds causes memory growth. OctoMap's octree is memory-efficient but not infinite.
**Why it happens:** Each insertPointCloud call adds ray-cast data. Large environments accumulate fast.
**How to avoid:** Insert every Nth frame (e.g., every 5th). Use coarser resolution (0.1-0.2m) for Phase 1. Monitor tree size periodically.
**Warning signs:** Process RSS growing steadily above 2GB.

## Code Examples

Verified patterns from official sources are included in Architecture Patterns above. Additional key patterns:

### SimWorld Environment Discovery Script
```python
# Run FIRST to discover observation/action space format
import gymnasium as gym

# Adjust env_id based on SimWorld-Robotics actual registration
env = gym.make("SimWorldRobotics-v0")  # or whatever the actual ID is
obs, info = env.reset()

print("=== Observation Space ===")
print(f"Type: {type(obs)}")
if isinstance(obs, dict):
    for key, value in obs.items():
        if hasattr(value, 'shape'):
            print(f"  {key}: shape={value.shape}, dtype={value.dtype}")
        else:
            print(f"  {key}: type={type(value)}, value={value}")

print("\n=== Info ===")
for key, value in info.items():
    print(f"  {key}: {type(value)} = {value}")

print("\n=== Action Space ===")
print(f"Action space: {env.action_space}")
print(f"Sample action: {env.action_space.sample()}")

# Measure step rate
import time
times = []
for i in range(50):
    t0 = time.monotonic()
    obs, reward, done, truncated, info = env.step(env.action_space.sample())
    times.append(time.monotonic() - t0)
    if done:
        obs, info = env.reset()

print(f"\n=== Step Rate ===")
print(f"Mean: {1.0 / np.mean(times):.1f} Hz")
print(f"Min:  {1.0 / max(times):.1f} Hz")
print(f"Max:  {1.0 / min(times):.1f} Hz")

env.close()
```

### Keyboard Teleop with pynput
```python
# Source: pynput documentation (pynput.readthedocs.io)
from pynput import keyboard
import numpy as np
import threading

class TeleopController:
    """WASD keyboard teleop. Thread-safe velocity output."""

    def __init__(self, linear_speed: float = 0.5, angular_speed: float = 1.0):
        self._linear_speed = linear_speed
        self._angular_speed = angular_speed
        self._keys_pressed = set()
        self._lock = threading.Lock()
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def get_velocity(self) -> tuple[np.ndarray, float]:
        """Returns (linear_vel [x, y], angular_vel)."""
        with self._lock:
            keys = set(self._keys_pressed)

        vx, vy, wz = 0.0, 0.0, 0.0
        if keyboard.KeyCode.from_char('w') in keys: vx += self._linear_speed
        if keyboard.KeyCode.from_char('s') in keys: vx -= self._linear_speed
        if keyboard.KeyCode.from_char('a') in keys: wz += self._angular_speed
        if keyboard.KeyCode.from_char('d') in keys: wz -= self._angular_speed

        return np.array([vx, vy]), wz

    def _on_press(self, key):
        with self._lock:
            self._keys_pressed.add(key)

    def _on_release(self, key):
        with self._lock:
            self._keys_pressed.discard(key)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| OpenAI gym | gymnasium (Farama) | 2023 | Use `gymnasium` not `gym`. API changes: `step()` returns 5 values (obs, reward, terminated, truncated, info) |
| RViz2 for visualization | Rerun SDK | 2024-2025 | Rerun is lighter weight, no ROS dependency, better Python API, web viewer |
| Manual ATE/RPE scripts | evo library | 2023+ | Standardized trajectory evaluation with proper SE3 handling |
| PCL for point clouds | Open3D | 2022+ | Python-native, pip-installable, GPU support |
| Custom octree | octomap-python | 2024+ | pip-installable Python bindings for OctoMap C++ |

**Deprecated/outdated:**
- `gym` (OpenAI): Use `gymnasium` (Farama Foundation) instead. API breaking changes in step() return values.
- Manual trajectory error computation: Use `evo` library for correct SE3 alignment and statistics.

## Open Questions

1. **SimWorld observation dictionary keys and shapes**
   - What we know: RGB, depth, segmentation are available per the paper. Quadruped robot is supported.
   - What's unclear: Exact dictionary keys, image resolution, depth units (meters vs mm), whether camera intrinsics are exposed.
   - Recommendation: First task must be a discovery script that prints all observation keys and shapes.

2. **SimWorld gym environment registration ID**
   - What we know: `simworld_gym/envs/` contains `simple_world.py`, `traffic_world.py`, `world_buffer.py`.
   - What's unclear: Exact `gym.make()` ID strings. May need to register manually or import directly.
   - Recommendation: Read `simworld_gym/__init__.py` and `setup.py` for registered env IDs.

3. **RTAB-Map standalone Python viability**
   - What we know: C++ API supports full SLAM (Rtabmap, Odometry, SensorData). Python `rtabmap_python` exists but scope is unclear.
   - What's unclear: Whether Python bindings expose full SLAM pipeline or only feature matching.
   - Recommendation: Time-box to 2 hours. Check `import rtabmap` in Python, inspect available classes. Fall back to ROS 2 rtabmap_ros.

4. **SimWorld asynchronous stepping semantics**
   - What we know: World buffer uses asynchronous control with per-agent availability flags. Buffer updates at 0.01s intervals.
   - What's unclear: Whether single-agent env (`simple_world.py`) has simpler synchronous stepping. Whether step blocks until UE5 renders.
   - Recommendation: Use single-agent env for Phase 1 (simpler). Multi-agent env needed in Phase 3+.

5. **Ground-truth pose format from SimWorld**
   - What we know: Paper mentions "ground-truth orientation via built-in compass" and 3D bounding boxes.
   - What's unclear: Whether full 6-DOF pose (position + orientation as matrix/quaternion) is in observation or info dict.
   - Recommendation: Discovery script will reveal this. If only orientation (no position), may need to compute position from odometry or find it in scene graph data.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (aliased in Nix flake: `python -m pytest`) |
| Config file | None -- Wave 0 must create pytest.ini |
| Quick run command | `python -m pytest tests/ -x --timeout=30` |
| Full suite command | `python -m pytest tests/ -v --timeout=60` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SIM-01 | Gym env connects, resets, steps, closes | integration | `python -m pytest tests/test_sim_bridge.py::test_lifecycle -x` | No -- Wave 0 |
| SIM-02 | Step returns RGB and depth arrays with correct shapes | integration | `python -m pytest tests/test_sim_bridge.py::test_sensor_extraction -x` | No -- Wave 0 |
| SIM-03 | Velocity command changes robot position | integration | `python -m pytest tests/test_sim_bridge.py::test_movement_command -x` | No -- Wave 0 |
| SIM-04 | Ground-truth pose extracted per step | integration | `python -m pytest tests/test_sim_bridge.py::test_ground_truth_pose -x` | No -- Wave 0 |
| SLAM-01 | RTAB-Map processes RGB-D frames and produces pose | integration | `python -m pytest tests/test_slam_pipeline.py::test_slam_processes_frames -x` | No -- Wave 0 |
| SLAM-02 | Point cloud grows as robot moves | integration | `python -m pytest tests/test_slam_pipeline.py::test_point_cloud_output -x` | No -- Wave 0 |
| SLAM-03 | OctoMap occupancy grid built from point cloud | unit | `python -m pytest tests/test_octomap_builder.py::test_occupancy_grid -x` | No -- Wave 0 |
| SLAM-04 | ATE/RPE computed from SLAM vs ground-truth poses | unit | `python -m pytest tests/test_drift_metrics.py::test_ate_rpe -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x --timeout=30`
- **Per wave merge:** `python -m pytest tests/ -v --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest.ini` -- basic pytest configuration with timeout
- [ ] `tests/__init__.py` -- test package init
- [ ] `tests/conftest.py` -- shared fixtures (mock SimWorld env, sample sensor data)
- [ ] `tests/test_sim_bridge.py` -- SIM-01 through SIM-04
- [ ] `tests/test_slam_pipeline.py` -- SLAM-01, SLAM-02
- [ ] `tests/test_octomap_builder.py` -- SLAM-03
- [ ] `tests/test_drift_metrics.py` -- SLAM-04
- [ ] Framework install: `pip install pytest pytest-timeout` (or add to requirements)

**Note:** SIM-01 through SIM-04 tests require SimWorld to be running. These are integration tests that may need to be skipped in CI. SLAM-03 and SLAM-04 can be unit-tested with synthetic data.

## Sources

### Primary (HIGH confidence)
- [RTAB-Map GitHub](https://github.com/introlab/rtabmap) - C++ RGBD Mapping wiki, standalone API classes
- [RTAB-Map C++ RGBD Mapping tutorial](https://github.com/introlab/rtabmap/wiki/Cplusplus-RGBD-Mapping) - Core API (Rtabmap, Odometry, SensorData)
- [Rerun SDK PyPI](https://pypi.org/project/rerun-sdk/) - v0.30.2, Python >= 3.10
- [Rerun Points3D docs](https://rerun.io/docs/reference/types/archetypes/points3d) - API for 3D point logging
- [evo library GitHub](https://github.com/MichaelGrupp/evo) - ATE/RPE metrics, Python API
- [octomap-python GitHub](https://github.com/wkentaro/octomap-python) - Python OctoMap bindings, insertPointCloud API
- [pynput docs](https://pynput.readthedocs.io/en/latest/keyboard.html) - Keyboard listener API

### Secondary (MEDIUM confidence)
- [SimWorld-Robotics paper (arXiv)](https://arxiv.org/html/2512.10046) - Sensors: RGB, depth, segmentation. Actions: continuous translation + rotation. Async centralized buffer for multi-agent.
- [SimWorld-Robotics GitHub](https://github.com/SCAI-JHU/SimWorld-Robotics) - Repository structure, gym envs, installation steps
- [SimWorld-Robotics project page](https://scai.cs.jhu.edu/projects/SimWorldRobotics/) - Multi-robot search benchmark details

### Tertiary (LOW confidence)
- SimWorld gym observation/action space exact format -- must be discovered empirically from source code
- RTAB-Map Python bindings scope -- only PyMatcher/PyDetector confirmed; full SLAM API unknown
- SimWorld step rate achievable on target hardware -- no benchmarks available
- Camera intrinsics availability in SimWorld observations -- not documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - RTAB-Map, Open3D, Rerun, evo are all well-documented and verified
- SimWorld integration: LOW - Gym API format, step rate, sensor availability all must be discovered empirically
- Architecture: MEDIUM - Patterns are sound but depend on SimWorld API discoveries
- Pitfalls: HIGH - Well-known from prior research and multi-robot SLAM literature

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (SimWorld is academic software; API could change with new releases)
