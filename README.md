# Multi-Robot 3D Reconstruction (MuJoCo)

Two simulated Unitree Go2 quadrupeds autonomously explore a MuJoCo office environment, each running independent SLAM, merging their maps into a unified real-time 3D reconstruction. Includes a browser-based C2 (Command & Control) interface for live visualization and control. Built on [DimOS](https://github.com/dimensionalOS/dimos).

> **Note:** This project originally targeted SimWorld-Robotics (UE5) but pivoted to MuJoCo during Phase 1. MuJoCo provides native RGB-D rendering, ground-truth poses via physics state, and runs without a GPU.

## Quick Start

### Prerequisites

- [Nix](https://nixos.org/download.html) (provides Python 3.12, system deps)
- Node.js 18+ (for the frontend)
- Git LFS (for DimOS scene data)

```bash
# Enter the Nix dev shell
nix develop

# Pull MuJoCo scene data from LFS
cd dimos && git lfs pull --include "data/.lfs/mujoco_sim.tar.gz" && cd ..

# Extract scene data (if not already extracted)
cd dimos/data && tar xzf .lfs/mujoco_sim.tar.gz && cd ../..

# Install frontend dependencies
cd frontend && npm install && cd ..

# Convert scene to GLB for the web viewer (one-time)
pip install trimesh
python scripts/convert_scene_glb.py
```

### Running the System

There are three modes:

#### 1. Web C2 Interface (recommended)

The full experience: browser-based dashboard with 3D visualization, robot tracking, camera feeds, and controls.

```bash
# Start backend + simulation (serves frontend at http://localhost:8000)
python src/main.py --control web --scene office --multi-max-steps 1000

# Or run frontend and backend separately for development:
# Terminal 1: Backend
python src/main.py --control web --scene office --multi-max-steps 1000

# Terminal 2: Frontend (hot reload, proxies /ws to backend)
cd frontend && npm run dev
# Open http://localhost:5173
```

#### 2. Desktop Visualization (Rerun + MuJoCo viewer)

Two desktop windows: Rerun for the reconstruction dashboard, MuJoCo native viewer for ground truth.

```bash
python src/main.py --control multi --scene office --multi-max-steps 1000
```

#### 3. Single Robot Exploration

One robot with Rerun visualization:

```bash
python src/main.py --control explore --max-steps 500
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--control` | `teleop` | Mode: `web`, `multi`, `explore`, `teleop`, `random` |
| `--scene` | `flat` | Scene: `office` (DimOS office with walls/furniture) or `flat` (checkerboard) |
| `--multi-max-steps` | `10000` | Max simulation steps for multi-robot modes |
| `--multi-boot-steps` | `200` | Physics settling steps before exploration starts |
| `--octomap-resolution` | `0.1` | Voxel resolution in meters |

## Project Structure

```
dimensional-applications/
├── src/                        # Python simulation & robotics code
│   ├── main.py                 # Entry point for all modes
│   ├── bridge/                 # MuJoCo bridge (single + multi-robot)
│   ├── slam/                   # ICP SLAM pipeline, depth-to-cloud, octomap
│   ├── exploration/            # Frontier detection, A* path planning, coverage
│   ├── coordination/           # Multi-robot coordinator, Voronoi partitioning
│   ├── control/                # Waypoint runner, random walk, locomotion
│   ├── viz/                    # Rerun-based visualizer (desktop mode)
│   └── metrics/                # Ground truth comparison, drift metrics
├── backend/                    # FastAPI WebSocket server for C2 interface
│   ├── app.py                  # Entry point: uvicorn backend.app:app
│   └── web/
│       ├── server.py           # FastAPI app, /ws endpoint, static file serving
│       ├── streaming_viz.py    # WebStreamingViz (replaces Rerun for web mode)
│       ├── message_types.py    # WebSocket protocol, JPEG encoding, cloud delta
│       └── connection_manager.py
├── frontend/                   # React/Vite/Three.js C2 dashboard
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx             # Mission control layout (CSS Grid)
│   │   ├── components/
│   │   │   ├── SceneViewer.tsx  # Three.js 3D viewer (hero panel)
│   │   │   ├── PointCloud.ts   # 200K pre-allocated point buffer
│   │   │   ├── RobotMarker.ts  # Go2 mesh model per robot (tinted)
│   │   │   ├── TrajectoryTrail.ts
│   │   │   ├── Sidebar.tsx     # Robot status cards + controls
│   │   │   ├── CameraFeed.tsx  # RGB + depth side-by-side
│   │   │   └── CameraStrip.tsx # Collapsible camera feed row
│   │   ├── stores/             # Zustand state (robotStore, controlStore)
│   │   ├── hooks/              # useWebSocket, useSceneLoader
│   │   └── utils/              # Palette, message types
│   └── public/                 # Static assets (scene.glb, go2.glb)
├── models/unitree_go2/         # Go2 MJCF model + mesh assets
├── dimos/                      # DimOS framework (submodule/local install)
├── scripts/                    # Scene conversion, cloud config testing
├── tests/                      # pytest tests (SLAM, viz, web server)
└── .planning/                  # GSD planning docs, roadmap, requirements
```

**IMPORTANT:** The frontend lives in `frontend/`, NOT `src/c2-frontend/`. The old path is removed. Always work in `frontend/`.

## Architecture

### Data Flow

```
MuJoCo Simulation
    │
    ├─ RGB + Depth per robot ──► SLAM Pipeline ──► Point Cloud + Occupancy Grid
    │                                                      │
    ├─ Ground-truth poses ──────────────────────────────────┤
    │                                                      │
    ├─ Coordinator (Voronoi partition, map merge, explore) ◄┘
    │       │
    │       ├─ WebStreamingViz ──► WebSocket ──► React Frontend (Three.js)
    │       │                                        ├─ 3D merged point cloud
    │       │                                        ├─ Go2 robot models (tinted)
    │       │                                        ├─ Trajectory trails
    │       │                                        ├─ RGB + depth camera feeds
    │       │                                        └─ Stats + controls
    │       │
    │       └─ MultiRobotVisualizer ──► Rerun (desktop mode)
    │
    └─ MuJoCo Viewer (interactive 3D, trajectory traces)
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Ground-truth pose for SLAM | MuJoCo gives perfect poses; ICP odometry runs for drift metrics only |
| Voronoi partitioning | Split space between robots; soft constraint (can enter other's zone if no local frontiers) |
| Obstacle inflation costmap | A* inflates obstacles by 40cm for path clearance; reactive depth avoidance at 40cm |
| WebSocket + JPEG streaming | Camera frames as binary JPEG (~30KB each); point cloud as JSON deltas with periodic full sync |
| Three.js (not R3F) | Imperative updates via Zustand subscriptions avoid React re-render overhead for 60fps 3D |
| Z-up worldRoot rotation | MuJoCo is Z-up, Three.js is Y-up; single Group rotation converts all data |

### Multi-Robot Color Scheme

Robots are assigned colors from an 8-color colorblind-safe (Okabe-Ito) palette:
- Robot A: Blue
- Robot B: Orange
- Robot 3+: auto-assigned from palette

## Development

### Frontend Development

```bash
cd frontend
npm install        # First time only
npm run dev        # Hot reload dev server on :5173 (proxies /ws to :8000)
npm run build      # Production build to dist/
npx tsc --noEmit   # Type check without building
```

### Running Tests

```bash
# All tests
nix develop --command bash -c "python -m pytest tests/ -x --timeout=30"

# Web server + streaming viz tests only
nix develop --command bash -c "python -m pytest tests/test_web_server.py tests/test_streaming_viz.py -x"

# Visualization tests
nix develop --command bash -c "python -m pytest tests/test_multi_robot_viz.py -x"
```

### Regenerating Scene GLB

If the office scene meshes change:

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
| 5. Locomotion & Stuck Recovery | Complete | Trot gait controller, stuck detection, turn recovery |
| 6. React C2 Web Interface | In Progress | Browser-based C2 dashboard with Three.js |

See [.planning/ROADMAP.md](.planning/ROADMAP.md) for detailed plans and success criteria.

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Modules, streams, blueprints, transports |
| [Robots & Hardware](docs/robots.md) | Supported platforms, sensors, blueprints |
| [CLI Reference](docs/cli.md) | All commands, flags, configuration |
| [Examples](docs/examples.md) | Workflows for replay, simulation, real robots |
