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

- ☐ Generic object-detection API with pluggable backends (v3.0)
- ☐ facebook/BoxeR (HuggingFace) detector integrated alongside YOLO (v3.0)
- ☐ Real 3D oriented bounding box regression (replace depth-median 2D→3D projection) (v3.0)
- ☐ Frontend detector picker, parameter panel, live detection metrics (v3.0)
- ☐ Pipeline-editor nodes for detector + 3D-projection stages (v3.0)

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

## Current Milestone: v3.0 Pluggable Perception & 3D Object Detection

**Goal:** Extend the v2.0 pluggable-backend pattern to perception — decouple object detection from Ultralytics YOLO behind a generic detector API, add transformer-based backends (facebook/BoxeR and others surfaced by research), and upgrade the 3D bounding box pipeline from depth-median 2D→3D projection to real oriented 3D boxes.

**Target features:**
- Generic detector API + registry (mirror of SLAMProtocol / SLAMRegistry)
- Existing YOLO detector refactored behind the new interface (zero behavioral regression)
- facebook/BoxeR (HuggingFace) detector plugged in as a second backend
- Real 3D oriented bounding box regression (replace depth-median center projection)
- Frontend detector picker, per-algorithm parameter panel, restart overlay
- Live detection metrics (FPS, #detections, confidence stats) in MetricsPanel
- Pipeline-editor nodes for detector + 3D-projection stages
- Additional backends discovered by deep research — scope locked after research completes

**Key context:** CPU-only constraint (no NVIDIA GPU). Subprocess isolation + ZMQ transport reused from v2.0 for heavy models. Graceful fallback when backends missing.

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

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-13 — v3.0 Pluggable Perception milestone started*
