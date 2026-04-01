# Argus

*The hundred-eyed giant that never sleeps.*

---

A multi-robot perception pipeline manager that connects simulated quadrupeds in MuJoCo to a real-time browser dashboard with pluggable SLAM, autonomous exploration, 3D reconstruction, object detection, and live map merging. Argus watches everything at once — multiple robots, multiple cameras, multiple SLAM backends — and streams unified situational awareness to a single pane of glass.

The name references [Argus Panoptes](https://en.wikipedia.org/wiki/Argus_Panoptes) — the all-seeing giant of Greek mythology with a hundred eyes, only some of which slept at any given time. The rest kept watching. Argus the system does what Argus the giant embodied: it distributes perception across multiple vantage points and fuses them into a single, coherent picture of the world.

Built on [DimOS](https://github.com/dimensionalOS/dimos). Inspired by the conviction that multi-robot perception is a systems integration problem before it is an algorithms problem.

## Three Commands

That's all you need.

```
uv run argus --scene office           Start the simulation + dashboard
uv run argus --scene office --static  Watch without moving
uv run argus --control explore        Single-robot autonomous exploration
```

Open the browser. Watch robots explore an office. See their point clouds merge in real time. Click the ground to teleport them. Switch SLAM backends mid-run. Toggle between cloud, voxel, and mesh views. Everything streams over a single WebSocket.

## Table of Contents

- [When Robots Are Cheap, Coordination Is Everything](#when-robots-are-cheap-coordination-is-everything)
- [The Perception Problem](#the-perception-problem)
- [Philosophical Foundations](#philosophical-foundations)
- [How Argus Works](#how-argus-works)
- [The SLAM Pipeline](#the-slam-pipeline)
- [The Exploration System](#the-exploration-system)
- [The Coordination Layer](#the-coordination-layer)
- [The Bridge Layer](#the-bridge-layer)
- [The Locomotion System](#the-locomotion-system)
- [The Perception Pipeline](#the-perception-pipeline)
- [The Streaming Architecture](#the-streaming-architecture)
- [The Frontend](#the-frontend)
- [Key Design Decisions](#key-design-decisions)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Project Structure](#project-structure)
- [Claude Code Integration (MCP)](#claude-code-integration-mcp)
- [Development](#development)
- [Intellectual Heritage](#intellectual-heritage)

## When Robots Are Cheap, Coordination Is Everything

> *"The whole is greater than the sum of its parts."* — Aristotle, *Metaphysics*

A single robot with a single camera sees the world through a keyhole. It moves, it maps, it builds a point cloud — but it sees only what is directly in front of it, and it has no way to know what is behind the next corner until it gets there. Its map is always incomplete, always one step behind reality.

Add a second robot and something qualitative changes. Two keyholes become a window. The office that took one robot ten minutes to map takes two robots five — not because each robot is faster, but because they can *divide the space* and explore simultaneously. The map converges from two directions at once. Blind spots shrink. Coverage accelerates not linearly but *combinatorially*, because each robot's discoveries reduce the search space for the other.

But coordination introduces a problem that single-robot systems never face: **how do you merge two independently constructed maps into one coherent picture?** Each robot has its own coordinate frame, its own drift, its own accumulated error. Simply overlaying their point clouds produces garbage unless you solve the alignment problem first.

This is where most multi-robot systems get complicated. Inter-robot loop closure. Distributed pose graph optimization. Consensus protocols for map consistency. The literature is vast and the implementations are brittle.

Argus sidesteps this entirely — not by solving the hard problem, but by *removing it*. In simulation, ground-truth poses are free. MuJoCo knows exactly where every robot is at every timestep. If you seed SLAM with the ground-truth pose on the first frame and chain relative transforms from there, every robot's map is already in world coordinates. Maps merge with a union operation, not a registration algorithm. This is not a shortcut — it is a *design decision* that says: **the interesting research question in multi-robot perception is not map alignment; it is everything else.**

Everything else: frontier detection, space partitioning, stuck recovery, real-time streaming, pluggable backends, live reconfiguration. The parts that matter when you're iterating on coordination strategies, not fighting with ICP convergence.

*When robots are cheap and simulation is free, the differentiator is not the SLAM algorithm — it is the system that orchestrates, streams, and visualizes the output of multiple SLAM algorithms running simultaneously.*

## The Perception Problem

> *"To see is to forget the name of the thing one sees."* — Paul Valéry

A robot does not "see" the world. It acquires depth images — 320x240 grids of floating-point numbers representing how far away each pixel is. These numbers must be unprojected into 3D points, transformed into world coordinates, filtered for noise, accumulated into a persistent map, projected onto a 2D grid for planning, and streamed to a human operator who can make sense of it all.

Each of these steps involves a coordinate frame transformation. MuJoCo's camera convention is not Open3D's convention, which is not Three.js's convention. The depth buffer is normalized to [0, 1]; it must be converted to meters using the near/far clipping planes. The camera looks along the body's -Y axis (a DimOS convention), not the +Z axis that most vision libraries assume. Every handoff between systems is an opportunity for a sign flip, a transposed matrix, or a coordinate frame mismatch that scatters your point cloud across the wrong hemisphere.

Argus makes these transformations *explicit and configurable*. The depth-to-cloud pipeline applies Y/Z sign flips that are switchable at runtime from the web dashboard. Eight pre-measured configurations are available — one for each combination of Y flip, Z flip, and matrix transpose. You can watch the point cloud reform in real time as you toggle between them. This is not because the correct configuration is ambiguous; it is because *debugging coordinate frames is the most common failure mode in robotics perception*, and the fastest way to debug is to see all the options side by side.

## Philosophical Foundations

### On Ground Truth as a Research Accelerant

> *"All models are wrong, but some are useful."* — George Box

There is a school of thought that says simulation-based robotics research is cheating. Real robots have real sensor noise, real actuator imprecision, real drift. A system that works in MuJoCo may fail catastrophically on hardware.

This criticism is correct and irrelevant.

The purpose of Argus is not to produce a production SLAM system. It is to produce a *research platform* where multi-robot coordination strategies can be iterated on rapidly. Ground-truth poses from MuJoCo eliminate the map alignment problem so that researchers can focus on the coordination problem. Perfect depth rendering eliminates sensor noise so that researchers can focus on the planning problem. Known spawn positions eliminate global localization so that researchers can focus on the exploration problem.

Each simplification is a *controlled variable*. You don't study everything at once — you hold some things constant and vary others. Argus holds perception constant (ground-truth poses, clean depth) so you can vary coordination (partitioning strategies, merge triggers, replan frequency). When the coordination algorithm works in simulation, you *then* add noise, drift, and hardware constraints — one at a time, with a working baseline to compare against.

This is not a shortcut. It is the [scientific method](https://en.wikipedia.org/wiki/Scientific_method).

### On Pluggability as a Research Methodology

> *"Make the change easy, then make the easy change."* — Kent Beck

Argus implements a [registry pattern](https://en.wikipedia.org/wiki/Service_locator_pattern) for SLAM backends, merge strategies, and exploration algorithms. A new SLAM backend is a Python class that satisfies a `@runtime_checkable Protocol` and registers itself with a single decorator:

```python
@slam_backend("my-slam", display="My Custom SLAM")
class MySLAM:
    def process_frame(self, frame: SensorFrame) -> SLAMResult: ...
    def get_cloud(self) -> o3d.geometry.PointCloud: ...
    def reset(self) -> None: ...
```

This is not over-engineering. It is a direct response to a specific research need: *the ability to swap algorithms mid-experiment without restarting the simulation*. The Argus dashboard exposes a dropdown that switches SLAM backends in real time. You can watch ICP's drift accumulate on the left while ORB-SLAM3's feature matching runs on the right. Same robots, same trajectory, different algorithms, live comparison.

The registry pattern makes this possible because it decouples *discovery* from *instantiation*. Backends register at import time via decorator. The coordinator queries the registry at runtime. No conditional imports, no factory functions, no configuration files that fall out of sync with the code.

### On Simplicity in Map Merging

> *"Perfection is achieved, not when there is nothing more to add, but when there is nothing left to take away."* — Antoine de Saint-Exupery

Argus merges maps with a union operation: a voxel is occupied if *any* robot observed it. No probabilistic weighting. No confidence scores. No Bayesian fusion.

This sounds naive until you consider the alternative. Probabilistic map merging requires maintaining per-voxel observation counts, handling conflicting observations (one robot sees a voxel as occupied, another sees it as free), and defining a fusion policy that produces sensible results under drift. The literature on this is extensive and the implementations are fragile.

Union-OR merging works because Argus controls its assumptions:
1. Ground-truth poses mean no drift — observations don't conflict
2. Binary voxels (occupied/free) are sufficient for exploration planning
3. The merge trigger is tied to frontier rescans, not a fixed timer

The result is a merge operation that is correct by construction, runs in microseconds, and never produces artifacts. It is the simplest thing that could possibly work — and in a research platform, *simple and correct beats sophisticated and fragile every time*.

## How Argus Works

```
MuJoCo Simulation (5 physics steps/frame, 320x240 depth + RGB)
    |
    +-- Per-robot SensorFrame (rgb, depth, ground-truth pose)
    |       |
    |       +-- SLAM Pipeline (pluggable via registry)
    |       |       +-- Depth unprojection (Open3D + configurable Y/Z flip)
    |       |       +-- ICP frame-to-frame alignment (or ORB-SLAM3, OpenVINS, etc.)
    |       |       +-- Statistical outlier removal (every 5th frame)
    |       |       +-- Global cloud accumulation (capped at 500K points)
    |       |       +-- OctoMap voxel grid (0.05m resolution)
    |       |
    |       +-- Perception (optional, background threads)
    |       |       +-- YOLOv11-nano (0.5 FPS on CPU)
    |       |       +-- 2D bbox -> 3D position via camera intrinsics
    |       |       +-- VLM scene descriptions (Moondream2, disabled by default)
    |       |
    |       +-- Exploration Loop
    |               +-- 2D occupancy grid (3D voxels projected by height)
    |               +-- Frontier detection (FREE cells adjacent to UNKNOWN)
    |               +-- BFS clustering + minimum size filter
    |               +-- A* path planning (Voronoi-gradient costmap)
    |               +-- Pure pursuit waypoint following (0.5m lookahead)
    |
    +-- Coordinator
    |       +-- Voronoi partitioning (perpendicular bisector, soft constraint)
    |       +-- Map merging (union-OR, triggered on frontier rescan)
    |       +-- Stuck recovery (reverse 25 steps + 135 degree random turn)
    |       +-- In-process pub/sub transport (replaced DimOS pLCM)
    |       +-- Visualization dispatch (every 10 steps)
    |
    +-- WebStreamingViz --> WebSocket --> React/Three.js Frontend
    |       +-- Cloud delta protocol (only new voxels sent, full sync every 10s)
    |       +-- Per-robot pose + rotation (cam_xmat, 9-element flat)
    |       +-- Trajectory history (downsampled to 500 points)
    |       +-- Camera frames (binary JPEG: RGB + turbo-colored depth)
    |       +-- Detections (class, confidence, bbox, 3D world position)
    |       +-- SLAM metrics (coverage %, voxel count, merge count, drift)
    |
    +-- MCP Server (/mcp, JSON-RPC 2.0)
            +-- get_status, get_detections, send_command, get_coverage
```

## The SLAM Pipeline

### Depth-to-Cloud Conversion

The most error-prone step in any depth-camera pipeline is the conversion from pixel coordinates to 3D world points. Argus makes this explicit:

1. **Depth buffer decoding** — MuJoCo renders depth as normalized [0, 1] values. Conversion to metric meters uses `znear * zfar / (zfar - raw * (zfar - znear))` where znear/zfar come from the model's visual settings multiplied by the statistic extent. An earlier implementation tried to auto-detect the encoding; it was wrong. The formula is now hardcoded.

2. **Unprojection** — Open3D's `create_from_depth_image()` unprojects depth pixels to 3D points in camera frame using pinhole intrinsics: `f = height / (2 * tan(fovy/2))`. This assumes the standard Open3D convention (x-right, y-down, z-forward).

3. **Y/Z sign flip** — MuJoCo cameras follow a different convention (x-right, y-up, z-backward). The flip is applied post-unprojection and is configurable at runtime via the `CloudConfig` system. Eight configurations are pre-measured. The default (Y-, Z-) was validated against ground-truth point positions.

4. **World transform** — Each frame's cloud is transformed from camera frame to world frame using `cam_xmat @ point + cam_xpos`. The DimOS standard camera (`xyaxes="0 -1 0 0 0 1"`) looks along body -Y; the Y/Z flip compensates so the cloud forms correctly.

5. **Noise filtering** — Statistical outlier removal (Open3D, `nb_neighbors=10, std_ratio=2.0`) runs every 5th frame. Running it every frame kills throughput; never running it accumulates phantom points from depth discontinuities.

6. **Accumulation** — Per-frame clouds accumulate into a global Open3D PointCloud, downsampled at 0.03m voxel resolution every 30 frames. The cloud is hard-capped at 500K points with progressive downsampling to prevent OOM on long runs.

### The Generic SLAM API (v2.0)

Argus v2.0 introduced a pluggable SLAM abstraction. Backends register themselves via decorator and are lazily imported:

```python
@slam_backend("icp", display="ICP (Open3D)")
class ICPBackend:
    """Frame-to-frame ICP. No loop closure. Drift accumulates."""
    ...

@slam_backend("orb-slam3", display="ORB-SLAM3")
class OrbSLAM3Backend:
    """Feature-based visual SLAM with loop closure."""
    ...
```

The registry uses `@runtime_checkable Protocol` to verify at startup that every backend satisfies the contract. This catches missing methods before the simulation starts, not 500 frames in when the coordinator first calls `get_cloud()` on a backend that forgot to implement it.

**Why ICP as the default:** It always works. No external dependencies, no feature extraction, no vocabulary trees. For synthetic MuJoCo depth with ground-truth pose seeding, frame-to-frame ICP produces clean clouds with manageable drift. It is the baseline that every other backend is measured against.

**Why the registry instead of a factory or config file:** Factories require a central switch statement that grows with every new backend. Config files drift out of sync with the code. The decorator pattern puts registration at the point of definition — if the class exists, it's registered. If it doesn't exist, it's not. No stale entries. No missing imports.

## The Exploration System

### Why 2D Planning on 3D Data

> *"Plans are useless, but planning is indispensable."* — Dwight D. Eisenhower

Argus projects 3D voxels onto a 2D occupancy grid for frontier detection and path planning. This loses vertical information, but gains tractability: A* on a 2D grid is fast, well-understood, and sufficient for ground robots that cannot fly.

The projection uses a height filter to separate ground, obstacles, and ceiling. A ground-plane filter removes the dominant Z-layer (the floor), preventing it from masking obstacles. Robot trajectory positions are stamped as FREE to ensure navigable corridors — if the robot walked there, it's passable.

### Frontier Detection

Frontiers are FREE cells adjacent to UNKNOWN cells on the 2D occupancy grid. They represent the boundary between the known and the unknown — the most informative places to visit next.

An earlier implementation detected frontiers on the 3D voxel grid directly. This produced a pathological failure mode in enclosed office scenes: wall edges appeared as frontiers because they bordered unexplored space *above* the wall. The robot would navigate to a wall, find no new information, declare the area explored, and get stuck. Switching to 2D frontier detection eliminated this entirely.

Frontiers are clustered via BFS and filtered by minimum size (small clusters are noise, not information). The goal selector picks the nearest frontier centroid, biased by the Voronoi partition in multi-robot mode.

### Path Planning

A five-stage navigation pipeline:

1. **Voronoi-gradient costmap** — Two-layer costmap that replaces simple inflation:
   - Binary inflation: obstacles dilated by robot half-width (0.15m), creating hard impassable zones
   - Voronoi gradient: labels connected obstacle clusters, finds Voronoi edges (corridor centers), computes cost as `50 * d_voronoi / (d_obstacle + d_voronoi)`. This pushes A* paths toward the center of corridors and doorways, eliminating corner-clipping that causes collisions.

2. **A* search** — 8-connected grid with octile heuristic. UNKNOWN cells are traversable with 5x cost penalty (prefer explored terrain, but don't refuse unknown). Occupied and lethal-zone cells are impassable.

3. **Path smoothing** — Raw A* paths are upsampled 10x, smoothed with a moving-average filter (window=50), and resampled at 0.1m uniform spacing. This removes grid artifacts and produces smooth curves for the waypoint follower.

4. **Pure pursuit** — 0.5m lookahead along the smoothed path. Finds the closest path point, walks 0.5m ahead to compute the steering target. Rotate-in-place if heading error exceeds 90 degrees; otherwise drive with proportional angular correction. Top speed: 0.8 m/s (office-safe).

5. **Mid-path replanning** — Every 10 steps, if the occupancy grid has changed (new obstacles discovered), the current path is invalidated and A* replans from the current position.

### Stuck Recovery

If position unchanged for 30 steps (0.05m threshold): reverse 25 steps at 1.0 m/s, then execute a 135-degree random turn. This is crude, effective, and handles the two most common failure modes — wedging into a corner, and oscillating between two adjacent frontiers.

## The Coordination Layer

### Voronoi Partitioning

In the two-robot case, Argus computes the perpendicular bisector of the line segment between robots. Each robot's "territory" is the half-plane on its side of the bisector.

This is a **soft constraint**: frontiers in a robot's own region are scored 2x higher, but the robot *can* enter the other's region if no local frontiers remain. This prevents two failure modes:
- **Thrashing**: without bias, both robots chase the same frontier
- **Deadlock**: with hard boundaries, a robot ignores reachable frontiers because they're across the line

Repartitioning triggers when one robot exhausts its local frontiers. The bisector is recomputed from current positions, and exploration continues.

For N > 2 robots, the system scales via `scipy.spatial.Voronoi`, though the current implementation is optimized for the two-robot case.

### Map Merging

Union-OR: a voxel is occupied if any robot observed it. Merge triggers are tied to frontier rescans (the same event that causes a robot to search for new frontiers). This means merges happen precisely when new information is available, not on a fixed timer.

No probabilistic fusion. No confidence weighting. No inter-robot ICP. These are not needed because ground-truth poses already place every robot's observations in the same world frame. The merge is a set union, and set unions are idempotent, commutative, and associative — properties that make the system correct regardless of merge order or timing.

### In-Process Transport

Argus originally used DimOS's pLCM (a lightweight pub/sub transport). This was replaced with an in-process callback registry because all robots and the coordinator run in the same Python process. Serialization overhead was pure waste.

The replacement is a global topic registry: publishers and subscribers on the same topic share a callback list. `RobotInstance` publishes `RobotMapMessage` to `/{robot_id}/occupancy`. The coordinator subscribes to all robot topics and triggers merges. No sockets, no serialization, no network stack. A function call.

## The Bridge Layer

### One Simulation, N Robots

`MultiRobotBridge` loads N Unitree Go2 models into a shared MuJoCo scene. Joint indices, actuator IDs, and camera IDs are discovered dynamically via `mj_name2id()` using per-robot name prefixes. This means adding a third or fourth robot requires no code changes — just a larger spawn position list.

Each robot gets its own `mujoco.Renderer` for RGB/depth capture, but all robots share the same physics simulation. One `mj_step()` advances all robots simultaneously.

### Sensor Acquisition

Ground-truth camera pose is extracted from `data.cam_xpos[cam_id]` (position) and `data.cam_xmat[cam_id]` (3x3 rotation matrix, flattened). These are world-frame quantities — MuJoCo computes them from the forward kinematics chain at every timestep.

Depth is rendered as a normalized [0, 1] buffer and converted to metric meters using the near/far clip planes. Per-robot depth is capped at 20m to handle far-field artifacts from the MuJoCo renderer.

### BridgeProtocol

Both `MuJoCoBridge` (single-robot) and `MultiRobotBridge` (multi-robot) satisfy a `@runtime_checkable Protocol`. This enables duck-typing verification at startup: if a bridge doesn't implement `step()`, `get_frame()`, or `stop()`, the error is immediate and obvious, not a cryptic `AttributeError` 200 frames into a run.

## The Locomotion System

### Raibert-Style Analytical Trot

The gait controller produces 12 joint position targets (3 per leg: hip, thigh, calf) from a velocity command (vx, vy, omega). It is an analytical controller, not a learned policy — every output is a closed-form function of the inputs.

**Phase structure:** Diagonal leg pairs (FL+RR vs FR+RL) are 180 degrees out of phase. While one pair is in stance (pushing the body forward), the other is in swing (repositioning for the next stance).

**Swing phase:** Parabolic foot lift trajectory provides ground clearance. The leg repositions from behind the hip to in front of it, preparing for the next ground contact.

**Stance phase:** The foot sweeps backward relative to the body, producing forward thrust. Stride length scales with commanded velocity.

**Turning:** Differential stride — inside legs take shorter steps, outside legs take longer steps. This produces smooth yaw rotation without sliding.

**Why position control (not torque):** Position-controlled actuators are deterministic. Given a joint angle target, the actuator drives to that angle regardless of external forces (within limits). Torque control requires a dynamics model, contact estimation, and careful tuning. For a research platform where locomotion is a means, not an end, position control is the right level of abstraction.

## The Perception Pipeline

### Object Detection

YOLOv11-nano runs in a background thread on CPU at 0.5 FPS (2-second intervals). This is intentionally slow — perception should not bottleneck the simulation loop.

Detections are filtered to 25 indoor-relevant COCO classes (chair, table, person, couch, laptop, etc.). MuJoCo renders are synthetic and visually simplistic; running YOLO on them requires a higher confidence threshold (50%) than real-world images.

### 3D Detection Projection

Each 2D bounding box center is unprojected to a 3D ray using camera intrinsics. The median depth within the bounding box provides the distance along that ray. The resulting camera-frame point is Y/Z flipped (same configuration as the SLAM pipeline) and transformed to world frame via `cam_xmat`. The result is a 3D wireframe bounding box rendered in the Three.js scene at the detected object's world position.

### VLM Scene Descriptions (Optional)

Moondream2 vision-language model generates one-sentence scene descriptions every 15 seconds per robot. Disabled by default because it is CPU-intensive and requires the `libvips` system library. When enabled, descriptions appear on robot status cards in the dashboard.

## The Streaming Architecture

### The Delta Protocol

The naive approach to streaming a point cloud over WebSocket is to send the entire cloud every frame. At 500K points with RGB, that's ~6MB per message at ~10 FPS — 60 MB/s. Unacceptable.

Argus implements a delta protocol:

1. Track the last voxel set (rounded to 0.01m precision)
2. On update: compute set difference (delta = new - old)
3. Send only delta voxels over WebSocket
4. Full sync every 10 seconds as a fallback

Typical bandwidth reduction: ~90%. The frontend accumulates deltas into a pre-allocated Three.js `BufferGeometry` (200K point capacity). Full syncs clear and rebuild the buffer.

### Message Types

| Type | Encoding | Content |
|------|----------|---------|
| `CLOUD_DELTA` / `CLOUD_FULL` | JSON | Point positions + RGB colors |
| `POSE_UPDATE` | JSON | Position, rotation, tracking status, body yaw |
| `TRAJECTORY` | JSON | Pose history (downsampled to 500 points max) |
| `STATS` | JSON | Coverage %, merge count, SLAM metrics |
| `CAMERA_FRAME` / `DEPTH_FRAME` | Binary | JPEG with structured header |

Camera frames use binary encoding: a JSON header (length-prefixed) followed by raw JPEG bytes. This avoids base64 overhead (~33% size increase) that JSON-only encoding would require.

### Color Modes

Point clouds can be colored two ways:
- **Robot tint** (default): each voxel is colored by the nearest robot using the [Okabe-Ito palette](https://jfly.uni-koeln.de/color/) (colorblind-safe)
- **True RGB**: voxels are mapped back to SLAM point cloud colors via grid quantization

## The Frontend

### State Management

Zustand stores with no boilerplate:

| Store | Responsibility |
|-------|---------------|
| `slamStore` | Active SLAM backend, parameters, crash messages |
| `robotStore` | Robot positions, trajectories, detections, camera frames |
| `metricsStore` | Coverage stats, output mode, history |
| `controlStore` | Speed, pause/resume, cloud config, scene toggle |

### 3D Scene

Three.js with dynamic point cloud updates driven by the WebSocket delta protocol. Robot markers are tinted Go2 meshes loaded from GLB. Camera frustums are wireframe FOV cones. Trajectory trails fade from full opacity to transparent over 500 points.

Click-to-navigate: click the ground plane to teleport a robot. The click position is unprojected from screen coordinates to world coordinates and sent to the coordinator as a `place_robot` command.

### Pipeline Editor

A visual DAG editor (React Flow) for connecting SLAM, detection, and description nodes. Switch SLAM backends, change merge strategies, and tune parameters without restarting the simulation. The pipeline graph is rendered as a directed acyclic graph with interactive node inspectors.

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Ground-truth poses for SLAM | Eliminates map alignment as a variable. Focus on coordination, not registration. |
| DimOS camera `xyaxes="0 -1 0 0 0 1"` | Matches DimOS standard. Camera looks along body -Y. Proven SLAM transform chain. |
| Y/Z flip configurable at runtime | Coordinate frame debugging is the #1 failure mode. Make it visible, make it switchable. |
| Union-OR map merging | Correct by construction when poses are ground-truth. Idempotent, commutative, associative. |
| Voronoi partitioning (soft constraint) | Prevents thrashing without causing deadlock. Repartitions automatically on frontier exhaustion. |
| pLCM replaced with in-process transport | All robots in same process. Serialization is waste. A function call is sufficient. |
| Registry pattern for SLAM backends | Swap algorithms mid-run. No conditional imports. Lazy loading. Runtime contract verification. |
| Delta protocol for cloud streaming | 90% bandwidth reduction. Full sync fallback every 10s. Transparent to frontend. |
| Depth always uses znear/zfar formula | Auto-detect was broken. Hardcoded formula is correct. Don't be clever with depth buffers. |
| No depth-based obstacle avoidance | Camera faces sideways (-Y), not forward (+X). Depth avoidance falsely triggers on walls. |
| Curated office spawn positions | Random spawning placed robots outside the room. 12 tested positions guarantee indoor placement. |
| Position-controlled gait (not torque) | Deterministic. No dynamics model needed. Locomotion is a means, not an end. |
| 2D frontier detection (not 3D) | 3D frontiers on wall edges caused false "fully explored" declarations in enclosed rooms. |
| 500K point cap with progressive downsampling | Prevents OOM on long runs. Acceptable quality loss at this density. |

## Quick Start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 18+ (for the frontend)
- Git LFS (for DimOS scene data)

```bash
# Install Python 3.12 and create venv
uv python install 3.12
uv venv --python 3.12
uv pip install -e .
uv pip install -e ./dimos

# Pull MuJoCo scene data from LFS
cd dimos && git lfs pull --include "data/.lfs/mujoco_sim.tar.gz" && cd ..

# Extract scene data
cd dimos/data && tar xzf .lfs/mujoco_sim.tar.gz && cd ../..

# Install frontend dependencies
cd frontend && npm install && cd ..

# Convert scene to GLB for the web viewer (one-time)
python scripts/convert_scene_glb.py
```

### Optional Dependencies

```bash
# YOLO object detection (2D + 3D bounding boxes)
pip install ultralytics

# VLM scene descriptions (requires libvips system library)
pip install transformers torch
sudo pacman -S libvips  # Arch/CachyOS
```

### Running

```bash
# Start everything — backend + simulation + frontend
uv run argus --scene office

# Custom port (default: 8000)
uv run argus --scene office --port 8001

# Frontend dev server with hot reload (separate terminal)
VITE_BACKEND_PORT=8001 cd frontend && npm run dev
```

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--control` | `web` | Mode: `web`, `multi`, `explore`, `teleop`, `random` |
| `--scene` | `flat` | Scene: `office` (DimOS office) or `flat` (checkerboard) |
| `--port` | `8000` | Web server port |
| `--multi-max-steps` | `0` | Max steps (0 = unlimited, Ctrl+C to stop) |
| `--multi-boot-steps` | `200` | Physics settling steps before exploration |
| `--octomap-resolution` | `0.1` | Voxel resolution in meters |
| `--static` | off | Keep robots stationary (SLAM still runs) |
| `--num-robots` | `2` | Number of robots |

## Project Structure

```
argus/
├── src/                        # Python simulation & robotics code
│   ├── main.py                 # Entry point for all modes
│   ├── bridge/                 # MuJoCo bridge (single + multi-robot)
│   │   ├── multi_bridge.py     # N robots in shared MuJoCo scene
│   │   ├── sim_bridge.py       # Single-robot bridge
│   │   ├── sensor_types.py     # SensorFrame, CameraIntrinsics
│   │   └── cloud_config.py     # 8 Y/Z flip configurations
│   ├── slam/                   # Pluggable SLAM system
│   │   ├── registry.py         # @slam_backend decorator + lazy registry
│   │   ├── protocol.py         # SLAMProtocol (runtime_checkable)
│   │   ├── slam_pipeline.py    # Frame processing orchestrator
│   │   ├── depth_to_cloud.py   # Depth unprojection + configurable flips
│   │   ├── backends/           # ICP, ORB-SLAM3, OpenVINS, SVO-Pro
│   │   └── octomap_builder.py  # Open3D voxel grid
│   ├── exploration/            # Autonomous navigation
│   │   ├── frontier_detector.py # 2D frontier detection + BFS clustering
│   │   ├── path_planner.py     # A* with Voronoi-gradient costmap
│   │   ├── occupancy_grid.py   # 3D-to-2D projection + height filter
│   │   └── exploration_loop.py # Goal selection + waypoint dispatch
│   ├── coordination/           # Multi-robot orchestration
│   │   ├── coordinator.py      # Main loop, merge triggers, viz dispatch
│   │   ├── voronoi_partitioner.py # Perpendicular bisector partitioning
│   │   ├── map_merger.py       # Union-OR voxel fusion
│   │   └── transport.py        # In-process pub/sub (replaced pLCM)
│   ├── locomotion/             # Trot gait controller
│   ├── perception/             # YOLO, VLM, 3D detection projection
│   ├── control/                # Waypoint runner, random walk, teleop
│   ├── mcp/                    # MCP server for Claude Code integration
│   ├── viz/                    # Rerun-based visualizer (desktop mode)
│   └── metrics/                # Ground truth comparison, drift metrics
├── backend/                    # FastAPI WebSocket server
│   └── web/
│       ├── server.py           # FastAPI app, /ws endpoint, /mcp route
│       ├── streaming_viz.py    # Delta protocol, cloud encoding
│       ├── message_types.py    # Binary JPEG, Okabe-Ito palette
│       └── connection_manager.py
├── frontend/                   # React/Vite/Three.js dashboard
│   ├── src/
│   │   ├── components/         # SceneViewer, CameraFeed, RobotCard, etc.
│   │   ├── stores/             # Zustand (slam, robot, metrics, control)
│   │   ├── hooks/              # useWebSocket, useSceneLoader
│   │   └── utils/              # Palette, message types
│   └── public/                 # scene.glb, go2.glb, favicon.svg
├── models/unitree_go2/         # Go2 MJCF model + mesh assets
├── dimos/                      # DimOS framework (submodule)
├── scripts/                    # Scene conversion utilities
└── tests/                      # pytest tests
```

## Claude Code Integration (MCP)

Argus exposes robot control via MCP at `/mcp` (JSON-RPC 2.0):

```bash
# Connect Claude Code
claude mcp add --transport http argus http://localhost:8000/mcp

# Available tools:
# - get_status: robot positions, voxel counts, step count
# - get_detections: YOLO detections per robot
# - get_scene_description: VLM descriptions (if enabled)
# - send_command: pause/resume/stop/set_speed
# - get_coverage: exploration coverage stats
```

This enables an AI agent to observe and control the simulation — querying robot positions, reading detections, and issuing commands without touching the GUI. The hundred-eyed giant, directed by another kind of intelligence.

## Development

### Frontend

```bash
cd frontend
npm install        # First time only
npm run dev        # Hot reload on :5173
npm run build      # Production build to dist/
npx tsc --noEmit   # Type check
```

### Tests

```bash
uv run python -m pytest tests/ -x --timeout=30
```

### Regenerating Scene GLB

```bash
pip install trimesh
python scripts/convert_scene_glb.py
# Output: frontend/public/scene.glb
```

## Intellectual Heritage

- **[Argus Panoptes](https://en.wikipedia.org/wiki/Argus_Panoptes)** — the hundred-eyed giant; only some eyes slept at any time, the rest kept watching. The architectural metaphor for distributed multi-camera perception.
- **[DimOS](https://github.com/dimensionalOS/dimos)** (Dimensional, 2024) — the robotics framework that defined the camera conventions, sensor abstractions, and scene data that Argus builds upon.
- **[MuJoCo](https://mujoco.org/)** (DeepMind, 2012) — physics-first simulation. Ground-truth poses for free. The controlled variable that makes coordination research tractable.
- **[Open3D](http://www.open3d.org/)** (Zhou, Park & Koltun, 2018) — the point cloud processing library. ICP, voxel grids, statistical outlier removal. The workhorse behind every SLAM backend.
- **[Frontier-Based Exploration](https://ieeexplore.ieee.org/document/613851)** (Yamauchi, 1997) — the insight that the boundary between known and unknown space is the most informative place to visit next. Still the foundation of autonomous exploration 30 years later.
- **[Voronoi Partitioning for Multi-Robot Exploration](https://ieeexplore.ieee.org/document/1307178)** (Burgard et al., 2005) — dividing space between robots using geometric bisectors. Simple, effective, scales to N agents.
- **[Pure Pursuit](https://www.ri.cmu.edu/pub_files/pub3/coulter_r_craig_1992_1/coulter_r_craig_1992_1.pdf)** (Coulter, 1992) — lookahead-based path following. Thirty years old and still the right choice for smooth trajectory tracking on ground robots.
- **[Raibert's Legged Machines](https://mitpress.mit.edu/9780262181174/)** (Raibert, 1986) — the analytical gait framework. Swing phase, stance phase, phase offsets. The physics of how legs make bodies move.
- **[Okabe-Ito Palette](https://jfly.uni-koeln.de/color/)** (Okabe & Ito, 2008) — colorblind-safe categorical colors. If your visualization excludes 8% of men, your visualization is broken.
- **[Goodhart's Law](https://en.wikipedia.org/wiki/Goodhart%27s_law)** — "When a measure becomes a target, it ceases to be a good measure." The reason Argus uses ground-truth for benchmarking but never for navigation: if the robot navigates by ground truth, it learns nothing about real-world perception.
- **[The Scientific Method](https://en.wikipedia.org/wiki/Scientific_method)** — hold some variables constant, vary others, measure the result. The architectural philosophy behind every simplification in Argus.

---

*"The real voyage of discovery consists not in seeking new landscapes, but in having new eyes."* — Marcel Proust

*"I see everything. I am always watching."* — Argus Panoptes, before Hermes put all hundred eyes to sleep

*Argus watches with a hundred eyes. You decide where to point them.*
