# Phase 1 Context: Simulation Bridge and Single-Robot SLAM

**Phase Goal:** A single Go2 robot connects to SimWorld, receives sensor data, and produces a local 3D point cloud and occupancy grid via SLAM
**Requirements:** SIM-01, SIM-02, SIM-03, SIM-04, SLAM-01, SLAM-02, SLAM-03, SLAM-04
**Discussed:** 2026-03-17

## Decisions

### SimWorld Gym Fallback Strategy

**Go/no-go criterion:** SimWorld gym must deliver sensor data at 5+ Hz. Below that, the project pivots to batch processing (drop real-time requirement).

**Sensor fallback:** If SimWorld provides RGB only (no depth images), switch to monocular SLAM (ORB-SLAM3 monocular mode). Scale ambiguity is accepted as a trade-off vs project viability.

**Investigation approach:** Work in parallel — one effort tries the gym API directly, another reads SimWorld source code to understand sensor internals. Don't block on one approach.

**Scope reduction plan:** If gym step rate is below 5 Hz, reduce scope to batch/offline processing. Pre-recording is not the fallback — just accept slower-than-realtime operation.

### Manual Driving Interface

**Control modes:** Build all three — keyboard teleop (WASD), scripted waypoints, and random walk. Keyboard teleop is the primary testing interface.

**Longevity:** Reusable across all phases. Build it properly — teleop is valuable for debugging in Phases 2-4, not just Phase 1 throwaway.

**Architecture:** Claude's call — DimOS Module with Out stream (preferred for blueprint integration and swappability with autonomy module) vs standalone script. Decision delegated to implementation.

### SLAM Output Validation

**Quality bar:** Three criteria must all pass before proceeding to Phase 2:
1. **Visual inspection** — Point cloud looks like the environment in Rerun viewer
2. **Drift metric** — ATE and RPE computed against ground-truth poses and reported (no hard numerical threshold — qualitative judgment)
3. **Map completeness** — After traversal, map covers the areas the robot actually visited

**Drift metrics:** Report both ATE (Absolute Trajectory Error) and RPE (Relative Pose Error). No hard pass/fail threshold — the user will judge qualitatively whether drift is acceptable for the project's needs.

**Viewer:** Rerun for all 3D visualization in Phase 1. Streams point cloud, occupancy grid, and trajectory live during SLAM operation.

## Code Context

**Reusable from existing codebase:**
- DimOS Module/Stream/Blueprint architecture (installed package, not in repo)
- Nix flake for reproducible dev environment
- Python 3.12 runtime

**Must be built:**
- SimWorldGymBridge module (gym API ↔ DimOS streams)
- SLAMPipeline module (RTAB-Map or ORB-SLAM3 integration)
- OctoMapBuilder module (point cloud → occupancy grid)
- TeleopController module (keyboard, waypoints, random walk)
- DriftMetrics module (ground-truth comparison, ATE/RPE)
- RerunVisualizer module (live 3D display)

**External dependencies to investigate:**
- SimWorld-Robotics gym interface (clone and study `simworld_gym/`)
- RTAB-Map Python bindings vs ROS 2 bridge
- Rerun Python SDK for streaming visualization
- OctoMap Python bindings or octomap_server2 ROS package

## Deferred Ideas

None captured during discussion.

## Research Implications

- Phase 1 research MUST investigate SimWorld gym observation/action space format
- Research should evaluate RTAB-Map vs ORB-SLAM3 based on available sensors
- Research should verify Rerun SDK compatibility with point cloud + occupancy grid streaming
- Parallel investigation: gym API trial + SimWorld source code reading

---
*Context captured: 2026-03-17*
