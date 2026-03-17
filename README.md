# Multi-Robot 3D Reconstruction (MuJoCo)

Two simulated Unitree Go2 quadrupeds autonomously explore a MuJoCo environment, each running independent SLAM, merging their maps into a unified real-time 3D reconstruction suitable for autonomous navigation. Built on [DimOS](https://github.com/dimensionalOS/dimos) as the agentic robotics framework.

> **Note:** This project originally targeted SimWorld-Robotics (UE5) but pivoted to MuJoCo during Phase 1. MuJoCo provides native RGB-D rendering, ground-truth poses via physics state, and runs without a GPU -- eliminating the SimWorld API uncertainties that were the project's biggest risk.

## Architecture

The system uses a **two-instance DimOS architecture** -- one separate blueprint process per robot, not DimOS fleet mode (which is broadcast-only). Each robot runs its own SLAM pipeline producing a local map. A centralized map merge server fuses both maps into a single global reconstruction in real-time using LCM inter-process communication.

**Key insight:** Known spawn transforms in simulation eliminate ICP-based map alignment. Map merging reduces to a coordinate transform plus voxel fusion.

### Stack

| Component | Role |
|-----------|------|
| DimOS 0.0.11 | Agentic robotics framework, module composition, typed pub/sub streams |
| MuJoCo 3.x | Physics simulation, native RGB-D rendering, ground-truth poses |
| Open3D 0.18+ | Point cloud processing, voxel grid (OctoMap replacement), merging |
| mujoco_menagerie | Unitree Go2 MJCF model (`models/unitree_go2/`) |
| Rerun | Real-time 3D visualization |

## Roadmap

The project is delivered in four phases:

1. **Simulation Bridge and Single-Robot SLAM** -- Load Go2 in MuJoCo, extract RGB-D + poses, produce a local 3D map via ICP odometry and Open3D voxel grid.
2. **Autonomous Exploration** -- One robot autonomously discovers and navigates to frontiers, building its map without human input.
3. **Multi-Robot Coordination and Map Merging** -- Two robots split the environment via Voronoi partitioning and fuse their maps into a unified 3D reconstruction in real-time.
4. **Visualization and Integration** -- Real-time 3D dashboard (Rerun or RViz2) showing merged map, robot positions, and exploration progress.

See [.planning/ROADMAP.md](.planning/ROADMAP.md) for detailed phase plans and success criteria.

## Requirements Overview

21 requirements across 6 categories:

- **Simulation Bridge** (4) -- MuJoCo lifecycle, RGB-D rendering, movement commands, ground-truth poses
- **SLAM Pipeline** (4) -- ICP odometry, point cloud output, occupancy grid (Open3D voxel), drift metrics
- **Autonomous Exploration** (3) -- Frontier detection, autonomous navigation, coverage tracking
- **Multi-Robot Coordination** (3) -- Separate DimOS instances, Voronoi region splitting, dynamic re-partitioning
- **Map Merging** (4) -- Frame alignment via spawn transforms, voxel fusion, point cloud merge, real-time incremental operation
- **Visualization** (3) -- Live 3D map display, robot position overlays, coverage heatmap

See [.planning/REQUIREMENTS.md](.planning/REQUIREMENTS.md) for full requirement definitions and traceability.

## Development Setup

```bash
# Enter the Nix dev shell (provides Python 3.12, system deps, etc.)
nix develop

# Or use the strict isolated shell (xome-based, fake home)
nix develop .#isolated

# Install dimos with common extras
pip install 'dimos[base,unitree]'

# Run in replay mode (no hardware or API keys needed)
dimos --replay run unitree-go2

# Run with LLM agent
export OPENAI_API_KEY=...
dimos --replay run unitree-go2-agentic
```

The Nix flake provides: Python 3.12, portaudio, ffmpeg, OpenGL/X11/GTK, GStreamer, LCM, CycloneDDS, Open3D build deps, and documentation tools. A Docker image can be built with `nix build .#devcontainer`.

## Project Status

- **Current phase:** 1 of 4 (Simulation Bridge and Single-Robot SLAM)
- **Progress:** 1/4 plans complete in Phase 1
- **Next up:** Phase 2 (Autonomous Exploration) -- fully planned, 2 plans in 2 waves
- **Tracking:** [.planning/ROADMAP.md](.planning/ROADMAP.md)

### Phase Progress

| Phase | Status | Plans |
|-------|--------|-------|
| 1. Simulation Bridge & SLAM | Executing | 1/4 complete |
| 2. Autonomous Exploration | Planned | 2 plans ready |
| 3. Multi-Robot Coordination | Not started | TBD |
| 4. Visualization & Integration | Not started | TBD |

### Key Discoveries (Phase 1)

- Pivoted from SimWorld (UE5) to MuJoCo -- no GPU required, native RGB-D, reliable ground-truth
- MuJoCo provides metric float32 depth directly (no JET-colormap workaround needed)
- Ground-truth pose from `qpos[0:3]` (position) + `qpos[3:7]` (quaternion) -- full precision
- MuJoCo default camera FOV: 45 degrees
- Go2 model from mujoco_menagerie (`models/unitree_go2/scene.xml`)
- OctoMap built with Open3D VoxelGrid (octomap-python has build issues)

### Phase 2 Design Decisions

- 3D frontier detection in voxel space (not 2D projected)
- DimOS replanning A* for pathfinding, adapted for discrete actions
- Frontier re-evaluation on distance/map-change triggers
- Termination on zero reachable frontiers + configurable max step safety net

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Modules, streams, blueprints, transports |
| [Robots & Hardware](docs/robots.md) | Supported platforms, sensors, blueprints |
| [Agents & Skills](docs/agents.md) | LLM agents, MCP, skills system |
| [CLI Reference](docs/cli.md) | All commands, flags, configuration |
| [Claude Code Integration](docs/claude-code.md) | Using dimos as an MCP server with Claude Code |
| [Examples](docs/examples.md) | Workflows for replay, simulation, real robots |
