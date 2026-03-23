# Roadmap: Multi-Robot 3D Reconstruction

## Milestones

- ✅ **v1.0 MVP** — Phases 1-7 (shipped 2026-03-23)
- 🚧 **v2.0 Generic SLAM API** — Phases 8-13 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-7) — SHIPPED 2026-03-23</summary>

- [x] Phase 1: Simulation Bridge and Single-Robot SLAM (4/4 plans) — completed 2026-03-17
- [x] Phase 2: Autonomous Exploration (3/3 plans) — completed 2026-03-17
- [x] Phase 3: Multi-Robot Coordination and Map Merging (3/3 plans) — completed 2026-03-17
- [x] Phase 4: Visualization and Integration (1/2 plans) — superseded by Phase 6
- [x] Phase 5: Robot Locomotion Fix (2/2 plans) — completed 2026-03-18
- [x] Phase 6: React C2 Web Interface (3/4 plans) — integration done manually
- [x] Phase 7: Cleanup and Verification Gaps (2/2 plans) — completed 2026-03-23

</details>

### v2.0 Generic SLAM API

**Phase Numbering:**
- Integer phases (8, 9, ...13): Planned milestone work
- Decimal phases (e.g., 9.1): Urgent insertions (marked with INSERTED)

- [x] **Phase 8: Backend Abstraction + ICP Wrap** — SLAMProtocol interface, registry, and ICP baseline backend
- [x] **Phase 9: Frontend Algorithm Controls** — Algorithm picker, parameter panel, end-to-end plumbing with ICP (completed 2026-03-23)
- [x] **Phase 10: Pose-Graph Map Merger** — Replace ICP union merge with pose-graph optimization (completed 2026-03-23)
- [x] **Phase 11: ORB-SLAM3 Backend** — First new backend via pip-installable orbslam3-python (1/2 plans complete) (completed 2026-03-23)
- [x] **Phase 12: OpenVINS + SVO Pro Backends** — C++ subprocess-isolated backends with IMU pipeline (completed 2026-03-23)
- [x] **Phase 13: Live Metrics Dashboard + Output Toggle** — Metrics comparison and visualization modes (completed 2026-03-23)

## Phase Details

### Phase 8: Backend Abstraction + ICP Wrap
**Goal**: Any SLAM algorithm can plug into the system through a standard interface, with the existing ICP pipeline running unchanged as proof
**Depends on**: Phase 7 (v1.0 complete)
**Requirements**: ABST-01, ABST-02, ABST-03, ABST-04, ABST-05, ABST-06
**Success Criteria** (what must be TRUE):
  1. A new backend can be registered by implementing SLAMProtocol and calling SLAMRegistry.register() -- no other files need to change
  2. REST endpoint GET /api/slam/backends returns a list of available backends with their parameter schemas and capability badges
  3. REST endpoint POST /api/slam/select triggers a session restart with the chosen backend
  4. The full simulation runs identically to v1.0 when ICP backend is selected (zero behavioral regression)
**Plans:** 3 plans

Plans:
- [x] 08-01-PLAN.md — Protocol + Registry + ICPBackend with unit tests
- [x] 08-02-PLAN.md — Consumer migration (RobotInstance, ExplorationLoop, Coordinator, main.py)
- [x] 08-03-PLAN.md — REST API endpoints (/api/slam/*) + human regression verification

### Phase 9: Frontend Algorithm Controls
**Goal**: Users can browse available SLAM algorithms, select one before a session, and tune its parameters -- all from the browser C2 interface
**Depends on**: Phase 8
**Requirements**: CTRL-01, CTRL-02, CTRL-03, CTRL-04
**Success Criteria** (what must be TRUE):
  1. Algorithm picker dropdown in C2 shows all registered backends with capability badges (supports_imu, outputs_dense, etc.)
  2. Selecting an algorithm and clicking start restarts the session with that backend active
  3. Parameter tuning panel renders controls dynamically from the backend's JSON schema (sliders for numeric, toggles for boolean)
  4. Changing a parameter value in the panel sends it via WebSocket and the backend applies it within the current session
**Plans:** 3/3 plans complete

Plans:
- [x] 09-01-PLAN.md — slamStore, Vite proxy, messageTypes, leaf components (CapabilityBadge, ConfirmModal, RestartOverlay)
- [x] 09-02-PLAN.md — AlgorithmDropdown, ParameterPanel, AlgorithmSection, ControlPanel wiring
- [x] 09-03-PLAN.md — Backend WS handler, useWebSocket SLAM handlers, SceneViewer overlay, human verification

### Phase 10: Pose-Graph Map Merger
**Goal**: Multi-robot maps merge via pose-graph optimization instead of naive ICP union, producing globally consistent reconstructions
**Depends on**: Phase 8
**Requirements**: MERG-01, MERG-02, MERG-03, MERG-04
**Success Criteria** (what must be TRUE):
  1. System supports three merge strategies selectable at session start: ICP union (existing), Open3D PGO, and GTSAM incremental PGO
  2. Merge strategy selector appears in frontend alongside algorithm picker
  3. Pose-graph merger accepts inter-robot loop closure constraints and produces globally consistent aligned maps
  4. Merged map output feeds the existing Three.js visualization pipeline without changes (last_merged_voxels, last_merged_cloud)
**Plans:** 3/3 plans complete

Plans:
- [ ] 10-01-PLAN.md — MergeProtocol + MergeRegistry + ICP Union baseline strategy
- [ ] 10-02-PLAN.md — Open3D PGO + GTSAM iSAM2 strategies with loop closure
- [ ] 10-03-PLAN.md — REST API merge endpoints + Coordinator MergeProtocol integration

### Phase 11: ORB-SLAM3 Backend
**Goal**: Users can run ORB-SLAM3 as an alternative SLAM backend, validating that the abstraction layer works with a real feature-based algorithm
**Depends on**: Phase 8
**Requirements**: BACK-01, BACK-02
**Success Criteria** (what must be TRUE):
  1. Selecting "ORB-SLAM3" from the algorithm picker and starting a session produces pose estimates and 3D map output
  2. ORB-SLAM3 provides pose estimates while the system generates dense point clouds from depth images using those poses (not sparse ORB features)
  3. The full exploration-to-merged-map pipeline works end-to-end with ORB-SLAM3 selected
**Plans:** 2/2 plans complete

Plans:
- [x] 11-01-PLAN.md — ORB-SLAM3 backend implementation + tests + vocab download script
- [x] 11-02-PLAN.md — MuJoCo scene textures + frontend tracking status + end-to-end verification

### Phase 12: OpenVINS + SVO Pro Backends
**Goal**: Users can run visual-inertial (OpenVINS) and semi-direct (SVO Pro) SLAM methods, each isolated in subprocesses so crashes cannot take down the system
**Depends on**: Phase 8, Phase 11 (validates pattern)
**Requirements**: BACK-03, BACK-04, BACK-05, BACK-06
**Success Criteria** (what must be TRUE):
  1. OpenVINS backend accepts RGB frames and IMU data (accelerometer + gyroscope extracted from MuJoCo) and produces pose estimates
  2. SVO Pro backend accepts RGB-D frames via subprocess bridge and produces pose estimates
  3. Both C++ backends run in subprocess isolation -- a backend crash is caught and reported without killing the main simulation process
  4. Selecting either backend from the algorithm picker and running a session produces a merged 3D map end-to-end
**Plans:** 4 plans

Plans:
- [x] 12-01-PLAN.md — IMU sensor types + MuJoCo bridge IMU sub-stepping + Go2 XML sensors
- [x] 12-02-PLAN.md — SubprocessSLAMBridge generic class + ZMQ IPC + crash detection
- [x] 12-03-PLAN.md — OpenVINS backend + C++ harness
- [x] 12-04-PLAN.md — SVO Pro / DSO backend + C++ harness + crash toast notification

### Phase 13: Live Metrics Dashboard + Output Toggle
**Goal**: Users can compare SLAM algorithm performance in real time and switch between visualization modes to inspect map quality
**Depends on**: Phase 8, Phase 9 (frontend infrastructure)
**Requirements**: CTRL-05, CTRL-06, CTRL-07
**Success Criteria** (what must be TRUE):
  1. Live metrics panel shows ATE, RPE, processing time (ms/frame), and tracking status per robot, updating in real time
  2. Metrics comparison view shows current algorithm's metrics alongside ICP baseline numbers side-by-side
  3. Output format toggle switches the Three.js viewer between point cloud, voxel grid, and mesh rendering modes without restarting the session
**Plans:** 3/3 plans complete

Plans:
- [ ] 13-01-PLAN.md — MetricsTracker backend + metricsStore + messageTypes + useWebSocket dispatch
- [ ] 13-02-PLAN.md — MetricsPanel + Sparkline + ControlPanel output toggle + App layout
- [ ] 13-03-PLAN.md — VoxelManager + MeshManager + SceneViewer cross-fade + mesh reconstruction

## Progress

**Execution Order:**
Phases execute in numeric order: 8 -> 9 -> 10 -> 11 -> 12 -> 13

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Simulation Bridge & SLAM | v1.0 | 4/4 | Complete | 2026-03-17 |
| 2. Autonomous Exploration | v1.0 | 3/3 | Complete | 2026-03-17 |
| 3. Multi-Robot Coordination | v1.0 | 3/3 | Complete | 2026-03-17 |
| 4. Visualization & Integration | v1.0 | 1/2 | Complete | 2026-03-18 |
| 5. Robot Locomotion Fix | v1.0 | 2/2 | Complete | 2026-03-18 |
| 6. React C2 Web Interface | v1.0 | 3/4 | Complete | 2026-03-23 |
| 7. Cleanup & Verification Gaps | v1.0 | 2/2 | Complete | 2026-03-23 |
| 8. Backend Abstraction + ICP Wrap | v2.0 | 3/3 | Complete | 2026-03-23 |
| 9. Frontend Algorithm Controls | v2.0 | 3/3 | Complete | 2026-03-23 |
| 10. Pose-Graph Map Merger | 3/3 | Complete    | 2026-03-23 | - |
| 11. ORB-SLAM3 Backend | 2/2 | Complete    | 2026-03-23 | - |
| 12. OpenVINS + SVO Pro Backends | v2.0 | 4/4 | Complete | 2026-03-23 |
| 13. Live Metrics Dashboard + Output Toggle | 3/3 | Complete   | 2026-03-23 | - |

### Phase 14: Interactive ComfyUI esque React Flow state graph creation system to customize the end-to-end SLAM pipeline + parameters

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 13
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 14 to break down)
