# Multi-Robot 3D Reconstruction (MuJoCo)

Two simulated Unitree Go2 quadrupeds autonomously explore a MuJoCo office environment, each running independent SLAM, merging their maps into a unified real-time 3D reconstruction. Includes a browser-based C2 (Command & Control) interface for live visualization, YOLO object detection, and robot control. Built on [DimOS](https://github.com/dimensionalOS/dimos).

> **Note:** This project originally targeted SimWorld-Robotics (UE5) but pivoted to MuJoCo during Phase 1. MuJoCo provides native RGB-D rendering, ground-truth poses via physics state, and runs without a GPU.

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

# Extract scene data (if not already extracted)
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

### Running the System

#### Web C2 Interface (recommended)

```bash
# Start everything -- backend + simulation + frontend at http://localhost:8000
uv run c2 --scene office

# Or equivalently:
uv run src/main.py --scene office

# Runs indefinitely. Ctrl+C to stop.
# MuJoCo viewer opens automatically for ground-truth comparison.
# Open http://localhost:8000 for the C2 dashboard.
```

For frontend development with hot reload:

```bash
# Terminal 1: Backend
uv run c2 --scene office

# Terminal 2: Frontend dev server (proxies /ws to :8000)
cd frontend && npm run dev
# Open http://localhost:5173
```

#### Desktop Visualization (Rerun + MuJoCo viewer)

```bash
uv run src/main.py --control multi --scene office
```

#### Single Robot Exploration

```bash
uv run src/main.py --control explore --max-steps 500
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--control` | `web` | Mode: `web`, `multi`, `explore`, `teleop`, `random` |
| `--scene` | `flat` | Scene: `office` (DimOS office) or `flat` (checkerboard) |
| `--multi-max-steps` | `0` | Max steps (0 = unlimited, Ctrl+C to stop) |
| `--multi-boot-steps` | `200` | Physics settling steps before exploration |
| `--octomap-resolution` | `0.1` | Voxel resolution in meters |
| `--static` | off | Keep robots stationary (SLAM still runs) |

## Features

### Core System
- **Multi-robot SLAM** -- Two Go2 robots with independent ICP odometry + Open3D voxel grids
- **Autonomous exploration** -- Frontier-based navigation with A* path planning
- **Voronoi partitioning** -- Splits space between robots; soft constraint (can cross if no local frontiers)
- **Real-time map merging** -- Union-OR voxel fusion, triggered on frontier rescan events
- **Trot gait locomotion** -- Raibert-style analytical gait with position-controlled actuators
- **Stuck recovery** -- Reverse 25 steps + 135° random turn when stuck detected

### C2 Web Interface
- **3D merged point cloud** -- Live reconstruction colored per-robot (Okabe-Ito palette)
- **Go2 robot models** -- Tinted 3D meshes at robot positions with heading
- **Camera frustum visualization** -- Wireframe FOV cone showing camera direction
- **Trajectory trails** -- Full path history from start with fade effect (up to 500 points)
- **RGB + depth camera feeds** -- Side-by-side with interactive YOLO detection overlays
- **3D detection bounding boxes** -- Wireframe boxes with labels at detected object positions
- **Robot status cards** -- Per-robot coverage %, voxel count, scene description, detection badges
- **Controls** -- Start/Stop, Pause/Resume, Speed slider, Restart (random or custom positions)
- **Cloud config switcher** -- 8 depth transform configs for debugging cloud alignment
- **Scene mesh toggle** -- Show/hide the office GLB model

### Perception (Optional)
- **YOLO object detection** -- YOLOv11-nano on CPU (~0.5 FPS), filtered to indoor classes only
- **3D object detection** -- Projects YOLO bboxes onto point cloud using camera intrinsics
- **VLM scene descriptions** -- Moondream2 generates text descriptions of robot camera views (requires libvips)

### Integration
- **MCP server** -- JSON-RPC 2.0 at `/mcp` for Claude Code integration (get_status, get_detections, send_command)
- **DimOS compatibility** -- Camera setup matches DimOS's `xyaxes="0 -1 0 0 0 1"` standard

## Project Structure

```
dimensional-applications/
├── src/                        # Python simulation & robotics code
│   ├── main.py                 # Entry point for all modes
│   ├── bridge/                 # MuJoCo bridge (single + multi-robot)
│   ├── slam/                   # ICP SLAM, depth-to-cloud, octomap
│   ├── exploration/            # Frontier detection, A* planning, coverage
│   ├── coordination/           # Multi-robot coordinator, Voronoi, map merger
│   ├── control/                # Waypoint runner, random walk
│   ├── locomotion/             # Trot gait controller, XML actuator patcher
│   ├── perception/             # YOLO detector, VLM scene describer, 3D detection
│   ├── mcp/                    # MCP server for Claude Code integration
│   ├── viz/                    # Rerun-based visualizer (desktop mode)
│   └── metrics/                # Ground truth comparison, drift metrics
├── backend/                    # FastAPI WebSocket server for C2 interface
│   └── web/
│       ├── server.py           # FastAPI app, /ws endpoint, /mcp endpoint
│       ├── streaming_viz.py    # WebStreamingViz (replaces Rerun for web mode)
│       ├── message_types.py    # WebSocket protocol, JPEG encoding, cloud delta
│       └── connection_manager.py
├── frontend/                   # React/Vite/Three.js C2 dashboard
│   ├── src/
│   │   ├── components/
│   │   │   ├── SceneViewer.tsx  # Three.js 3D viewer
│   │   │   ├── PointCloud.ts   # 200K pre-allocated point buffer
│   │   │   ├── RobotMarker.ts  # Go2 mesh with rotation
│   │   │   ├── CameraFrustum.ts # Wireframe FOV visualization
│   │   │   ├── DetectionBoxes.ts # 3D bounding boxes with labels
│   │   │   ├── TrajectoryTrail.ts # Fading path history
│   │   │   ├── CameraFeed.tsx  # RGB + depth with interactive YOLO overlay
│   │   │   ├── RobotCard.tsx   # Status card with detections + scene desc
│   │   │   └── ControlPanel.tsx # Play/pause/restart/cloud config
│   │   ├── stores/             # Zustand (robotStore, controlStore)
│   │   ├── hooks/              # useWebSocket, useSceneLoader
│   │   └── utils/              # Palette, message types
│   └── public/                 # scene.glb, go2.glb
├── models/unitree_go2/         # Go2 MJCF model + mesh assets
├── dimos/                      # DimOS framework (submodule)
├── scripts/                    # Scene conversion utilities
├── tests/                      # pytest tests
└── .planning/                  # GSD planning docs, roadmap
```

## Architecture

### Data Flow

```
MuJoCo Simulation (5 physics steps/frame, 320x240 depth+RGB)
    │
    ├─ Per-robot SensorFrame (rgb, depth, ground-truth pose)
    │       │
    │       ├─ SLAM Pipeline (Open3D create_from_depth_image + Y/Z flip + cam_mat)
    │       │       ├─ Statistical outlier filtering (every 5th frame)
    │       │       ├─ Global point cloud accumulation
    │       │       └─ OctoMap voxel grid (0.05m resolution)
    │       │
    │       ├─ YOLO Detector (background thread, 0.5 FPS)
    │       │       └─ 2D bboxes → 3D positions via camera intrinsics
    │       │
    │       └─ Exploration Loop
    │               ├─ Frontier detection (FREE→UNKNOWN on 2D grid)
    │               ├─ Goal selection + A* path planning (0.8m inflation)
    │               └─ Waypoint runner (trot gait locomotion)
    │
    ├─ Coordinator
    │       ├─ Voronoi partitioning (perpendicular bisector)
    │       ├─ Map merging (union-OR voxels, no spawn transform)
    │       ├─ Stuck recovery (reverse 25 steps + 135° turn)
    │       └─ Visualization dispatch (every 10 steps)
    │
    ├─ WebStreamingViz → WebSocket → React Frontend
    │       ├─ Cloud delta/full sync (per-robot color by 3D proximity)
    │       ├─ Pose + rotation (cam_xmat, 9-element flat)
    │       ├─ Trajectory (up to 500 downsampled points)
    │       ├─ Camera frames (JPEG, RGB + turbo-colored depth)
    │       ├─ Detections (class, confidence, bbox, 3D position)
    │       └─ Stats (coverage, voxel count, merge count, elapsed)
    │
    └─ MCP Server (/mcp endpoint)
            └─ get_status, get_detections, send_command, get_coverage
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| DimOS camera `xyaxes="0 -1 0 0 0 1"` | Matches DimOS standard; camera looks along body -Y; proven SLAM transform |
| Ground-truth pose for SLAM | MuJoCo gives perfect poses; ICP runs for drift metrics only |
| Y/Z flip + cam_mat (no transpose) | DimOS-proven depth-to-world transform for the standard camera orientation |
| Depth always uses znear/zfar conversion | Auto-detect was broken; raw buffer values need `znear*zfar/(zfar-raw*(zfar-znear))` |
| No depth-based obstacle avoidance | Camera faces sideways (-Y) while robot moves forward (+X); depth avoidance falsely triggers |
| Curated office spawn positions | Random spawning placed robots outside the room; 12 tested positions guarantee indoor placement |
| VLM disabled by default | Heavy CPU load + requires libvips; enable manually if needed |

### Known Limitations

- **Camera faces sideways** -- The DimOS standard camera looks along body -Y, not forward (+X). The RGB feed shows the side view. SLAM cloud forms correctly due to the Y/Z flip transform.
- **YOLO on synthetic images** -- YOLOv11 is trained on real photos; MuJoCo renders are simplistic. Detections are filtered to indoor classes with 50% confidence threshold.
- **No GPU acceleration** -- All processing runs on CPU. YOLO at 0.5 FPS, VLM disabled, 320x240 camera resolution.
- **Point cloud Z offset** -- The SLAM cloud may appear slightly above/below ground due to camera height and coordinate frame transforms.

## Claude Code Integration (MCP)

The system exposes robot control via MCP at `http://localhost:8000/mcp`:

```bash
# Connect Claude Code
claude mcp add --transport http dimensional http://localhost:8000/mcp

# Available tools:
# - get_status: robot positions, voxel counts, step count
# - get_detections: YOLO detections per robot
# - get_scene_description: VLM descriptions (if enabled)
# - send_command: pause/resume/stop/set_speed
# - get_coverage: exploration coverage stats
```

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

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Simulation Bridge & SLAM | Complete | MuJoCo bridge, ICP odometry, Open3D voxel grid |
| 2. Autonomous Exploration | Complete | Frontier detection, A* planning, coverage tracking |
| 3. Multi-Robot Coordination | Complete | Voronoi partitioning, map merging, pLCM transport |
| 4. Visualization & Integration | Complete | Rerun dashboard, MuJoCo viewer, trajectory traces |
| 5. Locomotion & Stuck Recovery | Complete | Trot gait controller, stuck detection, reverse+turn recovery |
| 6. React C2 Web Interface | Complete | Browser dashboard with Three.js, camera feeds, controls |
| 7. Perception Pipeline | Complete | YOLO detection, 3D bounding boxes, VLM scene descriptions |
| 8. Claude Code Integration | Complete | MCP server with robot control tools |

### Future Work

- **Forward-facing camera** -- Fix SLAM transform to work with a camera looking along body +X
- **GPU acceleration** -- CUDA VoxelGridMapper, real-time YOLO, faster VLM
- **Spatial memory** -- ChromaDB-backed queryable memory of explored areas (from DimOS)
- **Person following** -- EdgeTAM tracking + visual servoing (from DimOS)
- **Loop closure** -- Visual place recognition + pose graph optimization
- **Phone teleop** -- WebSocket-based phone tilt control (from DimOS)

See [.planning/ROADMAP.md](.planning/ROADMAP.md) for detailed phase plans and success criteria.
