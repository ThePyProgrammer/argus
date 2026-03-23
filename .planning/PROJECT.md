# Multi-Robot 3D Reconstruction

## What This Is

A simulation-based system where N Unitree Go2 quadruped robots autonomously explore a MuJoCo environment, split the space between them via Voronoi partitioning, and produce a combined real-time 3D reconstruction map — all controlled from a browser-based Command & Control interface with Three.js visualization.

## Core Value

Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.

## Requirements

### Validated

- ✓ Multi-robot MuJoCo simulation with independent SLAM pipelines — v1.0
- ✓ Autonomous frontier-based exploration with coverage tracking — v1.0
- ✓ Voronoi-partitioned coordinated exploration with re-partitioning — v1.0
- ✓ Real-time incremental map merging (voxel fusion + point cloud) — v1.0
- ✓ Proper quadruped locomotion (trot gait, position actuators) — v1.0
- ✓ Browser-based C2 with WebSocket streaming, Three.js viewer — v1.0
- ✓ N-robot scaling without frontend code changes — v1.0

### Active

- [ ] Generic SLAM API abstraction layer with pluggable backends
- [ ] 4 real SLAM backends: existing ICP, ORB-SLAM3, OpenVINS, SVO Pro
- [ ] Frontend algorithm picker with pre-session selection (hot-swap as stretch)
- [ ] Per-algorithm parameter tuning panel in C2 interface
- [ ] Live SLAM metrics comparison (accuracy, FPS, memory)
- [ ] Output format toggle (point cloud, voxel grid, mesh visualization)
- ✓ Replace ICP-based map merging with pose-graph optimization — Phase 10

### Out of Scope

- Physical/real-world deployment — simulation only
- Custom UE5 scene creation — using MuJoCo procedural scenes
- Post-processing refinement pipeline — real-time map is the deliverable
- Offline mode — real-time is core value
- DimOS dependency — replaced with in-process transport (v1.0)
- Deep learning SLAM backends (DROID-SLAM, DPV-SLAM, SL-SLAM) — requires NVIDIA GPU, defer to v3.0
- Neural representation SLAM backends (Photo-SLAM, SplaTAM) — requires GPU, defer to v3.0
- LiDAR SLAM — cameras only, system exists to replace LiDAR

## Current Milestone: v2.0 Generic SLAM API

**Goal:** Architect a pluggable SLAM backend abstraction that supports traditional, VIO, and classical methods with frontend controls for algorithm selection, parameter tuning, and live metrics comparison.

**Target features:**
- Generic SLAM API with registry pattern for pluggable backends
- 4 real backends: existing ICP (baseline), ORB-SLAM3, OpenVINS, SVO Pro
- Replace ICP map merging with pose-graph optimization
- Frontend algorithm picker, parameter tuning, live metrics, output format toggle
- Pre-session algorithm selection with hot-swap as stretch goal

## Context

Shipped v1.0 with 7,609 LOC Python + 2,486 LOC TypeScript.
Tech stack: MuJoCo, Open3D (ICP + VoxelGrid), FastAPI, React, Three.js, Zustand.
Pivoted from SimWorld (UE5, needed NVIDIA GPU) to MuJoCo (CPU-only) early in development.
Removed dimos dependency — replaced pLCM transport with in-process pub/sub.
Conducted systematic SLAM literature review (.research/) covering 40+ methods — informs backend selection and merge strategy.

## Constraints

- **Platform**: MuJoCo — CPU-only physics simulation
- **Robots**: N Unitree Go2 quadrupeds (simulated, default 2)
- **Real-time**: Map builds live as robots explore, not post-processed
- **Interface**: Browser-based C2 at localhost:8000

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MuJoCo over SimWorld | No NVIDIA GPU available; MuJoCo runs on CPU | ✓ Good — metric depth, faster iteration |
| ICP odometry over RTAB-Map | RTAB-Map Python bindings limited; ICP sufficient for simulation | ✓ Good — simple, works well |
| Open3D VoxelGrid over octomap-python | octomap-python CMake build fails in nix | ✓ Good — API-compatible |
| Voronoi perpendicular bisector | scipy.spatial.Voronoi degenerate for 2 robots | ✓ Good — generalizes to N |
| In-process transport over dimos pLCM | dimos has broken imports (TracebackType); single-process doesn't need IPC | ✓ Good — zero dependencies |
| WebStreamingViz over Rerun | Browser-accessible, no desktop app needed | ✓ Good — replaced Phase 4 Rerun path |
| Position actuators over torque | Go2 XML uses motor (torque); position servos needed for gait control | ✓ Good — reliable trot gait |

| Generic SLAM API over hardcoded ICP | Research shows ICP wrong for sparse clouds; abstraction enables algorithm comparison | — Pending |

---
*Last updated: 2026-03-23 after Phase 10 completion*
