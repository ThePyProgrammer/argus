# Roadmap: Multi-Robot 3D Reconstruction (SimWorld)

## Overview

This roadmap delivers a two-robot autonomous exploration and 3D reconstruction system in four phases. Phase 1 resolves the riskiest unknowns (SimWorld gym API) and proves single-robot SLAM end-to-end. Phase 2 adds autonomous frontier-based exploration so one robot can map without human input. Phase 3 introduces the second robot with coordinated region splitting and real-time map merging -- the core deliverable. Phase 4 adds the visualization layer for observing the live reconstruction.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Simulation Bridge and Single-Robot SLAM** - Connect to SimWorld, extract sensor data, and produce a local 3D map from one Go2 robot
- [x] **Phase 2: Autonomous Exploration** - One robot autonomously discovers and navigates to frontiers, building its map without human input
- [x] **Phase 3: Multi-Robot Coordination and Map Merging** - Two robots split the environment between them and fuse their maps into a unified 3D reconstruction in real-time (completed 2026-03-17)
- [ ] **Phase 4: Visualization and Integration** - Real-time 3D dashboard showing merged map, robot positions, and exploration progress (1/2 plans complete)
- [x] **Phase 5: Robot Locomotion Fix** - Fix actuator mismatch and replace sinusoidal gait with proper trot locomotion so robots actually walk (completed 2026-03-18)
- [ ] **Phase 6: React C2 Web Interface** - Browser-based Command & Control interface replacing desktop Rerun viewer with Three.js 3D visualization and WebSocket streaming
- [x] **Phase 7: Cleanup and Verification Gaps** - Fix stale tests, remove dead code, update requirements traceability, close all v1.0 audit gaps (completed 2026-03-23)

## Phase Details

### Phase 1: Simulation Bridge and Single-Robot SLAM
**Goal**: A single Go2 robot connects to SimWorld, receives sensor data, and produces a local 3D point cloud and occupancy grid via SLAM
**Depends on**: Nothing (first phase)
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, SLAM-01, SLAM-02, SLAM-03, SLAM-04
**Success Criteria** (what must be TRUE):
  1. System starts a SimWorld gym environment, spawns a Go2, steps the simulation, and cleanly shuts down
  2. A manually driven Go2 produces a growing 3D point cloud and occupancy grid as it moves through the environment
  3. Movement commands sent to the Go2 result in observable position changes in the simulation
  4. SLAM pose drift metrics are computed against ground-truth poses and printed per step
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Test infrastructure, shared data types, and SimWorld API discovery
- [x] 01-02-PLAN.md — SimWorld gym bridge and three control modes (teleop, waypoints, random walk)
- [x] 01-03-PLAN.md — SLAM pipeline (ICP odometry), OctoMap builder, and drift metrics
- [x] 01-04-PLAN.md — Rerun visualization, main.py wiring, and end-to-end verification

### Phase 2: Autonomous Exploration
**Goal**: A single robot autonomously explores the environment using frontier-based navigation, building its map without any human commands
**Depends on**: Phase 1
**Requirements**: EXPL-01, EXPL-02, EXPL-03
**Success Criteria** (what must be TRUE):
  1. Robot identifies frontier cells (boundary between explored and unexplored space) from its current occupancy grid
  2. Robot autonomously selects a frontier goal and navigates to it, then repeats the explore-map-navigate cycle without human input
  3. Exploration completeness percentage increases over time and is reported as the robot covers new area
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Frontier detection, goal selection, 2D occupancy projection, and A* path planning
- [x] 02-02-PLAN.md — Exploration loop orchestrator, coverage tracking, and integration tests
- [x] 02-03-PLAN.md — MuJoCo wiring: --control explore mode in main.py and end-to-end integration test

### Phase 3: Multi-Robot Coordination and Map Merging
**Goal**: Two Go2 robots operate independently with coordinated region assignments and produce a single unified 3D map in real-time
**Depends on**: Phase 2
**Requirements**: COORD-01, COORD-02, COORD-03, MERGE-01, MERGE-02, MERGE-03, MERGE-04
**Success Criteria** (what must be TRUE):
  1. Two Go2 robots run as separate DimOS instances with independent SLAM pipelines and namespaced streams
  2. The environment is partitioned into Voronoi regions and each robot explores only its assigned zone
  3. When one robot finishes its zone, regions are re-partitioned so the other robot receives help in unexplored areas
  4. A unified 3D occupancy grid and point cloud are produced by merging both robots' local maps in real-time as they explore
  5. The merged map grows continuously during exploration, not as a batch operation after exploration ends
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Multi-robot MuJoCo bridge, scene builder, config, and Voronoi partitioner
- [x] 03-02-PLAN.md — MapMerger (voxel fusion + point cloud merge), RobotInstance, Coordinator lifecycle
- [x] 03-03-PLAN.md — main.py --control multi wiring and end-to-end integration test

### Phase 4: Visualization and Integration
**Goal**: A real-time dashboard displays the merged 3D reconstruction with robot tracking and exploration progress
**Depends on**: Phase 3
**Requirements**: VIZ-01, VIZ-02, VIZ-03
**Success Criteria** (what must be TRUE):
  1. The merged 3D map is displayed in real-time via Rerun or RViz2 and updates live as robots explore
  2. Both robots' current positions and historical trajectories are visible as overlays on the merged map
  3. A coverage heatmap distinguishes explored regions from unexplored regions
**Plans**: 2 plans

Plans:
- [x] 04-01-PLAN.md — MultiRobotVisualizer class: split-panel Rerun dashboard, merged 3D map, robot overlays, coverage heatmap, stats HUD
- [ ] 04-02-PLAN.md — Wire visualization into Coordinator and main.py --control multi mode, integration tests, human verification

### Phase 5: Make sure the robots do not get stuck at one place without being able to move off
**Goal**: Go2 robots physically walk when given velocity commands by fixing the torque-vs-position actuator mismatch and replacing the sinusoidal gait with a proper Raibert-style trot, plus adding turn-in-place stuck recovery
**Depends on:** Phase 4
**Requirements**: LOCO-01, LOCO-02, LOCO-03, LOCO-04, LOCO-05, LOCO-06
**Success Criteria** (what must be TRUE):
  1. Robot translates >0.5m in 100 steps when given a forward velocity command (currently ~0m)
  2. Robot turns >45 degrees in 50 steps when given an angular velocity command
  3. Both single-robot and multi-robot bridges use the same trot gait controller
  4. Stuck detection triggers a physical turn-in-place recovery before rescanning frontiers
  5. All existing tests continue to pass (no regression)
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Locomotion module: XML actuator patcher, TrotGaitController, GaitParams, and movement tests
- [x] 05-02-PLAN.md — Bridge integration, scene builder patching, stuck recovery, and human verification

### Phase 6: React C2 Web Interface for Multi-Robot Visualization and Control
**Goal**: A browser-based Command & Control interface replaces the desktop Rerun viewer with a React/Three.js dashboard showing the merged 3D reconstruction, robot positions, camera feeds, and exploration controls -- all streamed via WebSocket from a FastAPI backend
**Depends on:** Phase 5
**Requirements**: C2-01, C2-02, C2-03, C2-04, C2-05, C2-06, C2-07, C2-08, C2-09, C2-10
**Success Criteria** (what must be TRUE):
  1. `python src/main.py --control web` launches FastAPI + MuJoCo simulation, serving React app at localhost:8000
  2. Browser displays mission control layout: large 3D viewer (~70%), right sidebar with robot cards, collapsible camera strip
  3. Merged point cloud updates in real-time via WebSocket delta + periodic full sync
  4. Per-robot camera feeds stream as JPEG binary WebSocket messages
  5. Robot status cards show coverage %, action, voxel count; clicking centers 3D view on robot
  6. Control panel sends start/stop/pause/speed commands that reach the Coordinator
  7. UI adapts dynamically to N robots without frontend code changes
**Plans**: 4 plans

Plans:
- [x] 06-01-PLAN.md — FastAPI backend: message types, ConnectionManager, WebStreamingViz, WebSocket server, tests
- [x] 06-02-PLAN.md — React/Vite frontend scaffold: Zustand stores, WebSocket hook, layout, sidebar, camera components
- [x] 06-03-PLAN.md — Three.js 3D viewer: scene setup, point cloud manager, robot markers, trajectory trails, GLB loader
- [ ] 06-04-PLAN.md — End-to-end integration: Coordinator wiring, main.py --control web, scene GLB conversion, human verification

### Phase 7: Cleanup and Verification Gaps
**Goal**: Close all audit gaps from v1.0 milestone: fix stale tests, remove dead code, update REQUIREMENTS.md traceability, and resolve type inconsistencies
**Depends on:** Phase 6
**Requirements**: VIZ-01, VIZ-02, VIZ-03 (mark satisfied via web interface), LOCO-01-06, C2-01-10 (add to traceability)
**Gap Closure:** Closes gaps from v1.0-MILESTONE-AUDIT.md
**Success Criteria** (what must be TRUE):
  1. `pytest tests/` runs without collection errors (stale test_sim_bridge.py fixed)
  2. All LOCO and C2 requirements present in REQUIREMENTS.md traceability table
  3. VIZ-01/02/03 marked satisfied with evidence pointing to WebStreamingViz (Phase 6 supersedes Rerun)
  4. Dead code removed: unreachable _log_coverage_heatmap() path, BridgeProtocol type mismatch resolved
  5. No remaining gaps in v1.0-MILESTONE-AUDIT.md after re-audit
**Plans**: 2 plans

Plans:
- [ ] 07-01-PLAN.md — Fix stale test assertions, missing model paths, install pytest-asyncio
- [ ] 07-02-PLAN.md — Remove dead code, fix BridgeProtocol docstring, mark VIZ requirements satisfied

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Simulation Bridge and Single-Robot SLAM | 4/4 | Complete    | 2026-03-17 |
| 2. Autonomous Exploration | 3/3 | Complete    | 2026-03-17 |
| 3. Multi-Robot Coordination and Map Merging | 3/3 | Complete    | 2026-03-17 |
| 4. Visualization and Integration | 1/2 | In progress | - |
| 5. Robot Locomotion Fix | 2/2 | Complete    | 2026-03-18 |
| 6. React C2 Web Interface | 3/4 | In progress | - |
| 7. Cleanup and Verification Gaps | 2/2 | Complete   | 2026-03-23 |
