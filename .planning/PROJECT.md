# Multi-Robot 3D Reconstruction

## What This Is

A simulation-based system where N Unitree Go2 quadruped robots autonomously explore a MuJoCo environment, split the space between them via Voronoi partitioning, and produce a combined real-time 3D reconstruction map — all controlled from a browser-based Command & Control interface with Three.js visualization, pluggable SLAM and perception backends, and a benchmarkable locomotion harness for comparing robot-dog controllers.

## Core Value

Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real time — with user-selectable SLAM/perception algorithms, live metrics, and repeatable locomotion benchmarks that make controller changes comparable instead of anecdotal.

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
- ✓ Generic object-detection API with pluggable detector and 3D lifter backends — v3.0
- ✓ YOLOv11 baseline, RT-DETRv2, and subprocess-isolated BoxeR detection backends — v3.0
- ✓ Real oriented 3D bounding boxes with canonical server-owned wire format — v3.0
- ✓ Frontend detector/lifter picker, parameter panel, restart overlay, and live detection metrics — v3.0
- ✓ Pipeline-editor nodes for detector, 3D-projection, and tracker stages — v3.0
- ✓ ByteTrack tracking, multi-robot detection fusion, semantic map layer, and heterogeneous per-robot detector support — v3.0

### Active

- ✓ Gymnasium-style `ArgusGo2Env` benchmark wrapper with deterministic seeded resets — v4.0 Phase 1
- ✓ Named locomotion scenario catalog: flat ground, low friction, slope, rough heightfield, and push disturbance — v4.0 Phase 1
- ✓ Controller plugin seam for analytical trot, residual policies, direct policies, and future MPC/WBC adapters — v4.0 Phase 2
- ✓ Locomotion metrics suite for command tracking, stability, control quality, contact/terrain proxies, and failure rates — v4.0 Phase 3
- ✓ Repeatable CLI evaluation runner with JSONL/CSV exports, aggregate comparison table, metadata, and baseline regression test — v4.0 Phase 4
- ☐ Harness guide and explicit controller-family comparison matrix grounded in the locomotion R&D report (v4.0)

### Out of Scope

- Physical/real-world deployment — simulation only
- Custom UE5 scene creation — using MuJoCo procedural scenes
- Post-processing refinement pipeline — real-time map is the deliverable
- Offline-only C2 mode — real-time is core value
- DimOS dependency — replaced with in-process transport (v1.0)
- Deep learning SLAM backends (DROID-SLAM, DPV-SLAM, SL-SLAM) — requires NVIDIA GPU
- Neural representation SLAM backends (Photo-SLAM, SplaTAM) — requires GPU
- LiDAR SLAM — cameras only, system exists to replace LiDAR
- Hot-swap SLAM algorithm mid-session — pre-session selection sufficient
- RL policy training — v4.0 builds the benchmark harness, not trained policies
- MPC/WBC implementation — v4.0 creates compatible seams and metrics, not full model-based control
- ROS 2 / hardware deployment — future architecture milestone after simulation evaluation is repeatable
- Frontend visualization overhaul — v4.0 can expose artifacts through CLI/docs first

## Current Milestone: v4.0 Benchmarkable Locomotion Environment

**Goal:** Turn Argus locomotion from a hard-coded analytical baseline into a benchmarkable comparison harness for analytical gait, residual learning, direct RL, MPC/WBC, and future ROS/hardware-oriented controllers.

**Target features:**
- Gymnasium-style `ArgusGo2Env` with `reset(seed=...)` and `step(action)` semantics
- Scenario catalog for flat ground, low friction, slope, rough heightfield, and push-disturbance tests
- Deterministic seeded resets covering spawn pose, terrain, command schedule, and disturbances
- Action modes for velocity command, joint-position target, and residual-over-baseline control
- Controller protocol/registry with analytical trot as the default deterministic baseline
- Metrics suite for command tracking, stability, action quality, contact/terrain proxies, and failures
- CLI evaluation runner over controller × scenario × seed matrices with reproducible metadata
- Harness documentation and comparison matrix linking scope to `outputs/locomotion-rd-systems.md`

**Key context:** The locomotion R&D report concludes Argus currently sits in the analytical gait + MuJoCo position-servo baseline family. v4.0 deliberately benchmarks and instruments this baseline before adding RL, MPC, WBC, or hardware-oriented control.

## Current State

**Shipped:** v3.0 Pluggable Perception & 3D Object Detection (2026-04-30)

**Active:** v4.0 Benchmarkable Locomotion Environment Phase 4 complete; Phase 5 harness docs and comparison matrix is next.

**Codebase:** Python + TypeScript robotics/web stack with MuJoCo, Open3D, FastAPI, React 18, Three.js, React Flow, and Zustand.

## Constraints

- **Platform**: MuJoCo — CPU-first physics simulation
- **Robots**: N Unitree Go2 quadrupeds (simulated, default 2)
- **Real-time**: Map builds live as robots explore, not post-processed
- **Interface**: Browser-based C2 at localhost:8000
- **Locomotion benchmark**: repeatable seeds, explicit scenarios, and machine-readable metrics are required before controller claims count

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
| Subprocess isolation for C++/heavy backends | Native and ML backends can crash or stall; subprocess + ZMQ keeps main process alive | ✓ Good — crash detection + fallback |
| Pose-graph optimization over ICP merge | ICP union naive for multi-robot; PGO produces globally consistent maps | ✓ Good — Open3D PGO + GTSAM iSAM2 |
| React Flow for pipeline editor | Only mature React node-graph library; ComfyUI-style UX | ✓ Good — typed ports, presets, live animation |
| Benchmark harness before new locomotion controllers | The research report shows advanced locomotion requires state/contact instrumentation and repeatable metrics first | v4.0 formalizes env, scenarios, metrics, and controller seams before RL/MPC/WBC |
| Gymnasium-style environment API | Standard reset/step contract makes RL, evaluation, and regression tests share one interface | v4.0 uses `ArgusGo2Env` as the benchmark boundary |
| Analytical trot remains the baseline | The existing controller is deterministic, inspectable, and already integrated with MuJoCo position actuators | v4.0 registers it behind the same controller protocol as future controllers |
| Metrics are first-class output | Locomotion claims need scenario/seed aggregates, not visual demos | v4.0 exports JSONL/CSV plus summaries for comparisons |
| Future-controller adapters are seams, not implementations | Avoid half-building RL/MPC/WBC without training/control infrastructure | v4.0 ships placeholders and extension points only |

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
*Last updated: 2026-05-01 — v4.0 Phase 4 evaluation-runner-and-regression completed*
