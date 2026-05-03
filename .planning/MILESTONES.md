# Milestones

## v4.0 Benchmarkable Locomotion Environment (Shipped: 2026-05-03)

**Phases completed:** 9 phases, 35 plans, 68 tasks

**Delivered:** A repeatable locomotion benchmark harness for the existing Go2 analytical trot baseline, with Gymnasium-style environment semantics, scenario/seed reproducibility, controller seams, metrics, evaluation artifacts, and documentation for comparing future controller families.

**Key accomplishments:**

- Added `ArgusGo2Env` with Gymnasium-style reset/step semantics, deterministic scenario sampling, required flat/low-friction/slope/rough/push scenarios, and velocity/joint/residual action-mode seams.
- Put locomotion control behind protocol/registry and dispatch helpers, with analytical trot as the default baseline and residual/direct/MPC/WBC families exposed as unavailable future-controller placeholders.
- Instrumented command tracking, stability, action quality, and terrain/contact metrics with per-step info and episode summaries.
- Shipped `argus eval-locomotion` for controller x scenario x seed matrices, JSONL/CSV/summary/comparison artifacts, reproducibility metadata, saved-run regeneration, and analytical flat-ground regression checks.
- Published the locomotion benchmark guide and controller-family support/deferred matrix grounded in `outputs/locomotion-rd-systems.md`.
- Closed milestone audit gaps through Phases 6-9: command-schedule semantics, distance export flattening, action-mode metadata, WBC placeholder wording, multi-robot validation-before-mutation, and pre-close artifact hygiene.

### Requirements

- 20/20 v4.0 active requirements satisfied.
- See: `.planning/milestones/v4.0-REQUIREMENTS.md`

### Known Debt Accepted

- Phase 08 `08-VALIDATION.md` still contains stale draft/pending validation metadata despite `08-VERIFICATION.md` passing 8/8.
- Multi-robot locomotion control remains an explicit platform-runtime boundary rather than the exact single-robot controller registry path; this was accepted under the "where practical" requirement caveat.
- `audit-open` does not catch stale phase validation metadata, so validation consistency still needs explicit audit attention.

### Archive

- Roadmap: `.planning/milestones/v4.0-ROADMAP.md`
- Requirements: `.planning/milestones/v4.0-REQUIREMENTS.md`
- Audit: `.planning/milestones/v4.0-MILESTONE-AUDIT.md`

---

## v3.0 Pluggable Perception & 3D Object Detection (Shipped: 2026-04-30)

**Phases completed:** 8 phases, 79 plans

**Key accomplishments:**

- Generic detector and 3D lifter protocols/registries, mirroring the v2.0 SLAM abstraction pattern
- Existing YOLOv11 detector refactored behind the detector protocol with regression coverage
- Per-robot detector workers with newest-wins backpressure, restart plumbing, and canonical OBB wire format
- Frontend detector/lifter picker, parameter panel, restart overlay, RGB bbox overlay, and detector Zustand store
- PointClusterLifter replacing median-depth projection with real oriented 3D boxes from depth-frustum point clusters
- RT-DETRv2 and subprocess-isolated BoxeR backends with pinned-model/download infrastructure, crash fallback, and license documentation
- Honest MuJoCo-grounded detection metrics, detection export, and UI guards against unsupported mAP claims
- React Flow perception nodes for detector, 3D lifter, and tracker stages with typed ports and hot-apply backend dispatch
- ByteTrack tracking, multi-robot detection fusion, semantic map TTL layer, and heterogeneous per-robot detector support

### Requirements

- See: `.planning/milestones/v3.0-REQUIREMENTS.md`

### Archive

- Roadmap: `.planning/milestones/v3.0-ROADMAP.md`
- Requirements: `.planning/milestones/v3.0-REQUIREMENTS.md`
- Research: `.planning/milestones/v3.0-research/`

---

## v2.0 Generic SLAM API (Shipped: 2026-03-25)

**Phases completed:** 7 phases, 24 plans, 46 tasks

**Key accomplishments:**

- Runtime-checkable SLAMProtocol interface, decorator-based SLAMRegistry, and ICPBackend wrapping existing SLAMPipeline with zero behavioral regression
- All 5 SLAM consumer files migrated from SLAMPipeline to SLAMProtocol/SLAMRegistry with zero behavioral regression across 190+ passing tests
- Four REST endpoints for SLAM backend discovery, selection, active query, and parameter management wired into FastAPI server with restart integration
- Zustand slamStore with REST fetch, Vite /api proxy, extended WS message types, debounce utility, CSS spin keyframes, and three leaf UI components (CapabilityBadge, ConfirmModal, RestartOverlay)
- Custom dropdown for SLAM backend selection with capability badges, schema-driven parameter sliders/toggles with debounced WebSocket sends, and confirmation modal for algorithm switching with restart polling
- WebSocket slam_param_update handler with schema validation and per-param ack, useWebSocket SLAM message dispatchers, SceneViewer restart overlay, verified end-to-end in browser
- Pluggable merge strategy abstraction with MergeProtocol, MergeRegistry, and ICP Union baseline wrapping existing MapMerger
- Open3D PGO and GTSAM iSAM2 merge strategies with ICP loop closure detection and spawn transform fallback on ICP failure
- Four merge strategy REST endpoints and MergeProtocol-based dispatch in Coordinator with backward-compatible MapMerger fallback
- ORB-SLAM3 backend wrapping orbslam3-python with dense depth clouds, sparse feature metrics, RGBD/monocular modes, and mocked CI tests
- Textured MuJoCo walls for ORB feature extraction plus robot marker color changes based on SLAM tracking status (green=OK, red=LOST, yellow=INITIALIZING/RELOCALIZING)
- IMUReading dataclass and MuJoCo bridge sub-step IMU collection at physics rate for visual-inertial SLAM backends
- Generic SubprocessSLAMBridge with ZMQ PAIR IPC, msgpack+numpy multipart wire protocol, 5s hang detection, and IPC socket cleanup
- DSO backend via SubprocessSLAMBridge with visual-only mode, C++ ZMQ harness, and full crash->toast notification pipeline
- MetricsTracker with per-robot ATE/RPE/ms_per_frame ring buffers, coordinator wiring feeding SLAM data into tracker, extended stats WebSocket with slam_metrics/baseline/metric_history, and metricsStore Zustand store with useWebSocket dispatch
- Collapsible MetricsPanel with live per-robot SLAM table, vs-baseline sparkline comparison, and output format toggle buttons in ControlPanel
- Three.js VoxelManager (InstancedMesh) and MeshManager (BufferGeometry) with Open3D Poisson mesh reconstruction and 300ms cross-fade transitions between point cloud, voxel grid, and mesh rendering modes
- Pipeline type system with 7 port data types, 11 node definitions across 7 categories, Kahn's algorithm graph validation, parameter-override-aware serializer, and Zustand pipelineStore with React Flow integration
- PipelineBuilder with DAG validation, NodeCatalog aggregating registries, REST API for apply/catalog/presets, and 3 built-in pipeline preset configs
- Custom React Flow canvas with typed pipeline nodes (colored headers, port handles by data type, inline params, status badges) and animated flowing-dot edges
- 4 surrounding panel components for pipeline graph editor: categorized node palette with drag-to-add, full-parameter inspector with live-tunable indicators, preset load/save dropdown, and apply bar with validation status
- ViewToggle switches hero area between 3D Viewer and full Pipeline Editor layout, with WebSocket pipeline status dispatch to pipelineStore

---

## v1.0 — Multi-Robot 3D Reconstruction MVP

**Shipped:** 2026-03-23
**Phases:** 7 (1-7) | **Plans:** 20 | **Timeline:** 7 days (2026-03-17 to 2026-03-23)
**Codebase:** 7,609 LOC Python + 2,486 LOC TypeScript | 372 commits

### Delivered

Two Unitree Go2 quadruped robots autonomously explore a MuJoCo environment, split the space via Voronoi partitioning, and produce a unified real-time 3D reconstruction map — all controlled from a browser-based Command & Control interface.

### Key Accomplishments

1. MuJoCo simulation bridge with ICP-based SLAM pipeline producing 3D point clouds and occupancy grids
2. Autonomous frontier-based exploration with A* path planning, coverage tracking, and stuck recovery
3. Multi-robot coordination with Voronoi partitioning, real-time map merging, and in-process pub/sub transport
4. Proper quadruped locomotion via Raibert-style trot gait controller with position-controlled actuators
5. Browser-based C2 interface: FastAPI + WebSocket streaming to React/Three.js with real-time point cloud, robot markers, camera feeds, and click-to-navigate
6. N-robot scaling — system adapts dynamically to any number of robots without code changes

### Requirements

- 37/37 v1 requirements satisfied (SIM, SLAM, EXPL, COORD, MERGE, VIZ, LOCO, C2)
- See: `.planning/milestones/v1.0-REQUIREMENTS.md`

### Known Gaps (accepted)

- Phase 4 plan 04-02 (Rerun wiring) — intentionally skipped, replaced by Phase 6 web interface
- Phase 6 plan 06-04 (end-to-end integration) — done manually outside GSD pipeline
- SLAM-04 drift metrics not computed in multi-robot modes (diagnostic only)

### Archive

- Roadmap: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`
- Audit: `.planning/v1.0-MILESTONE-AUDIT.md`
