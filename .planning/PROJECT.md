# Multi-Robot 3D Reconstruction

## What This Is

A simulation-based system where N Unitree Go2 quadruped robots autonomously explore a MuJoCo environment, split the space between them via Voronoi partitioning, and produce a combined real-time 3D reconstruction map — all controlled from a browser-based Command & Control interface with Three.js visualization, pluggable SLAM backends, and a visual pipeline editor.

## Core Value

Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time — with user-selectable SLAM algorithms, merge strategies, and live performance metrics.

## Requirements

### Validated

- ✓ Multi-robot MuJoCo simulation with independent SLAM pipelines — v1.0
- ✓ Autonomous frontier-based exploration with coverage tracking — v1.0
- ✓ Voronoi-partitioned coordinated exploration with re-partitioning — v1.0
- ✓ Real-time incremental map merging (voxel fusion + point cloud) — v1.0
- ✓ Proper quadruped locomotion (trot gait, position actuators) — v1.0
- ✓ Browser-based C2 with WebSocket streaming, Three.js viewer — v1.0
- ✓ N-robot scaling without frontend code changes — v1.0
- ✓ Generic SLAM API abstraction layer with pluggable backends — v2.0
- ✓ 4 real SLAM backends: ICP, ORB-SLAM3, OpenVINS, SVO Pro — v2.0
- ✓ Frontend algorithm picker with pre-session selection — v2.0
- ✓ Per-algorithm parameter tuning panel in C2 interface — v2.0
- ✓ Live SLAM metrics comparison (ATE, RPE, ms/frame, tracking status) — v2.0
- ✓ Output format toggle (point cloud, voxel grid, mesh visualization) — v2.0
- ✓ Replace ICP-based map merging with pose-graph optimization — v2.0
- ✓ Interactive pipeline graph editor (ComfyUI-style) — v2.0

### Active

(None — awaiting v3.0 milestone definition)

### Out of Scope

- Physical/real-world deployment — simulation only
- Custom UE5 scene creation — using MuJoCo procedural scenes
- Post-processing refinement pipeline — real-time map is the deliverable
- Offline mode — real-time is core value
- DimOS dependency — replaced with in-process transport (v1.0)
- Deep learning SLAM backends (DROID-SLAM, DPV-SLAM, SL-SLAM) — requires NVIDIA GPU, defer to v3.0
- Neural representation SLAM backends (Photo-SLAM, SplaTAM) — requires GPU, defer to v3.0
- LiDAR SLAM — cameras only, system exists to replace LiDAR
- Hot-swap SLAM algorithm mid-session — pre-session selection sufficient

## Current State

**Shipped:** v2.0 Generic SLAM API (2026-03-25)

**Codebase:** ~18,400 LOC (Python + TypeScript), 219 files
**Tech stack:** MuJoCo, Open3D, GTSAM (optional), FastAPI, React 18, Three.js, React Flow, Zustand 5
**Tests:** 122+ passing (pytest), TypeScript clean on all pipeline/SLAM code

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
| Generic SLAM API over hardcoded ICP | Research shows ICP wrong for sparse clouds; abstraction enables algorithm comparison | ✓ Good — 4 backends plugged in cleanly |
| Subprocess isolation for C++ backends | ORB-SLAM3/OpenVINS/SVO Pro crash risk; subprocess + ZMQ keeps main process alive | ✓ Good — crash detection + ICP fallback |
| Pose-graph optimization over ICP merge | ICP union naive for multi-robot; PGO produces globally consistent maps | ✓ Good — Open3D PGO + GTSAM iSAM2 |
| React Flow for pipeline editor | Only mature React node-graph library; ComfyUI-style UX | ✓ Good — 10 presets, typed ports, live animation |

---
*Last updated: 2026-03-25 after v2.0 milestone completion*
