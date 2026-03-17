# Multi-Robot 3D Reconstruction (SimWorld)

Two simulated Unitree Go2 quadrupeds autonomously explore a SimWorld-Robotics (UE5) environment, each running independent SLAM, merging their maps into a unified real-time 3D reconstruction suitable for autonomous navigation. Built on [DimOS](https://github.com/dimensionalOS/dimos) as the agentic robotics framework.

## Architecture

The system uses a **two-instance DimOS architecture** -- one separate blueprint process per robot, not DimOS fleet mode (which is broadcast-only). Each robot runs its own SLAM pipeline producing a local map. A centralized map merge server fuses both maps into a single global reconstruction in real-time using LCM inter-process communication.

**Key insight:** Known spawn transforms in simulation eliminate ICP-based map alignment. Map merging reduces to a coordinate transform plus voxel fusion.

### Stack

| Component | Role |
|-----------|------|
| DimOS 0.0.11 | Agentic robotics framework, module composition, typed pub/sub streams |
| RTAB-Map 0.23.1 | Per-robot RGB-D visual SLAM (via ROS 2 Humble) |
| OctoMap 1.10.0 | 3D occupancy grid generation for navigation |
| Open3D 0.18+ | Point cloud processing and merging |
| SimWorld-Robotics (UE5) | Simulation environment with procedural urban scenes and gym interface |

## Roadmap

The project is delivered in four phases, ordered by risk (SimWorld gym API is the biggest unknown):

1. **Simulation Bridge and Single-Robot SLAM** -- Connect to SimWorld, extract sensor data, produce a local 3D map from one Go2 robot. Resolves the riskiest unknowns first.
2. **Autonomous Exploration** -- One robot autonomously discovers and navigates to frontiers, building its map without human input.
3. **Multi-Robot Coordination and Map Merging** -- Two robots split the environment via Voronoi partitioning and fuse their maps into a unified 3D reconstruction in real-time.
4. **Visualization and Integration** -- Real-time 3D dashboard (Rerun or RViz2) showing merged map, robot positions, and exploration progress.

See [.planning/ROADMAP.md](.planning/ROADMAP.md) for detailed phase plans and success criteria.

## Requirements Overview

21 requirements across 6 categories:

- **Simulation Bridge** (4) -- Gym lifecycle, sensor extraction, movement commands, ground-truth poses
- **SLAM Pipeline** (4) -- RTAB-Map integration, point cloud output, occupancy grid, drift metrics
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
- **Progress:** 0% -- not yet started
- **Tracking:** [.planning/ROADMAP.md](.planning/ROADMAP.md)

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Modules, streams, blueprints, transports |
| [Robots & Hardware](docs/robots.md) | Supported platforms, sensors, blueprints |
| [Agents & Skills](docs/agents.md) | LLM agents, MCP, skills system |
| [CLI Reference](docs/cli.md) | All commands, flags, configuration |
| [Claude Code Integration](docs/claude-code.md) | Using dimos as an MCP server with Claude Code |
| [Examples](docs/examples.md) | Workflows for replay, simulation, real robots |
