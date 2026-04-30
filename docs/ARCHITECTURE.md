# Architecture

> Argus is a local, simulation-first multi-robot perception workbench: MuJoCo runs simulated Unitree Go2 robots, Python coordinates exploration and perception pipelines, FastAPI streams state over WebSockets, and a React/Three.js dashboard renders command-and-control, maps, detections, metrics, and pipeline editing.

## Overview

Argus exists to make multi-robot perception and coordination experiments observable and swappable without turning every experiment into a hardware, networking, or map-registration project. The system deliberately uses MuJoCo CPU simulation as its platform boundary and uses simulator world poses as a controlled variable, so contributors can compare exploration, SLAM, detection, lifting, tracking, fusion, streaming, and UI behavior under repeatable conditions. That is the product; physical deployment is not secretly hiding behind the curtain. See ADR-0002 and ADR-0003.

The runtime is a single local Python process for the core simulator, robots, coordinator, backend state, and web server, with subprocesses only where failure isolation earns its keep: heavyweight SLAM or detector backends that can hang, crash, fight over native libraries, or poison thread pools. Local robot/coordinator messages are in-process callbacks, not DimOS pLCM. The README still contains DimOS heritage language and setup references; current planning and ADR-0004 supersede that for transport and dependency assumptions. Treat DimOS as historical/contextual unless current code proves otherwise.

The main architectural seam is data flow: MuJoCo sensor frames become SLAM clouds, occupancy grids, detection inputs, 3D boxes, semantic maps, metrics, and WebSocket payloads. Geometry is server-owned, registries make backends pluggable, and the browser is a renderer/operator surface, not a second robotics stack. That distinction is not cosmetic. It prevents the usual robotics bug farm: duplicated FOV math, stale queues, fake metrics, and five different quaternion conventions.

## Codemap

Execution starts at `src/main.py`, exposed as the `argus` console script in `pyproject.toml`. The default path is web mode: build the MuJoCo world, create robot instances and the coordinator, configure the FastAPI app, start the browser-facing server, and run the simulation loop that feeds `WebStreamingViz`.

The happy-path data flow is:

```text
MuJoCo bridge
  -> per-robot SensorFrame
  -> SLAM backend + voxel map
  -> exploration / coordination / merge logic
  -> perception worker pool -> detector -> 3D lifter -> tracker / semantic map
  -> metrics
  -> WebStreamingViz / FastAPI WebSocket
  -> React + Three.js + React Flow dashboard
```

### Entrypoint and runtime wiring: `src/main.py`

`src/main.py` is the composition root: CLI parsing, mode selection, backend registration imports, simulation boot, app creation, and web/runtime callbacks live here. Key files are `src/main.py`, `pyproject.toml`, and `backend/web/server.py`. It depends on almost every subsystem; nothing should depend on it. If reusable logic appears here, it has already started to rot.

### Simulation bridge: `src/bridge/`

The bridge owns MuJoCo interaction: scene/model loading, robot spawning, stepping physics, rendering RGB/depth, extracting camera intrinsics, and packaging `SensorFrame` objects. Key files are `multi_bridge.py`, `sim_bridge.py`, `sensor_types.py`, `multi_robot_config.py`, `scene_builder.py`, and `cloud_config.py`. It depends on MuJoCo and NumPy and is consumed by SLAM, exploration, perception, metrics, and runtime wiring. This is the platform boundary from ADR-0002.

### Locomotion and control: `src/locomotion/`, `src/control/`

Locomotion translates velocity commands into Go2 joint targets; control modules provide teleop, random walk, waypoint, and exploration-facing movement commands. Key files are `locomotion/gait_controller.py`, `locomotion/xml_patcher.py`, `control/waypoint_runner.py`, `control/random_walk.py`, and `control/teleop.py`. These modules depend on bridge-level robot state and feed commanded motion back into MuJoCo. They are support machinery, not the research surface.

### SLAM and map building: `src/slam/`

SLAM turns sensor frames into poses, point clouds, and voxel maps behind a protocol/registry boundary. Key files are `protocol.py`, `registry.py`, `slam_pipeline.py`, `depth_to_cloud.py`, `octomap_builder.py`, and `backends/` (`icp_backend.py`, `orbslam3_backend.py`, `openvins_backend.py`, `svopro_backend.py`, `subprocess_bridge.py`). It depends on bridge sensor types, Open3D, optional native/model backends, and sometimes subprocess IPC. It is consumed by exploration, coordination, metrics, streaming, and the frontend schema routes. Backend pluggability follows ADR-0006; crashy backends follow ADR-0008.

### Exploration: `src/exploration/`

Exploration projects 3D map data into a 2D planning surface, finds frontiers, selects goals, plans paths, tracks coverage, and drives the robot toward useful unknown space. Key files are `occupancy_grid.py`, `frontier_detector.py`, `goal_selector.py`, `costmap.py`, `path_planner.py`, `path_smoother.py`, `coverage_tracker.py`, and `exploration_loop.py`. It depends on SLAM/voxel output and robot pose state; the coordinator depends on it for autonomous multi-robot behavior. The 2D planning boundary is deliberate: ground robots do not need a flying-robot planner just because the map is 3D.

### Coordination and merging: `src/coordination/`

Coordination owns multi-robot orchestration: robot instances, Voronoi partitioning, merge triggers, in-process transport, merge strategy registries, and pipeline construction. Key files are `coordinator.py`, `robot_instance.py`, `transport.py`, `voronoi_partitioner.py`, `map_merger.py`, `merge_protocol.py`, `merge_registry.py`, `merge_strategies/`, and `pipeline_builder.py`. It depends on bridge, SLAM, exploration, perception, metrics, and web streaming callbacks. Local transport is in-process by ADR-0004; map alignment is simplified by world poses per ADR-0003.

### Perception, 3D lifting, and semantic outputs: `src/perception/`

Perception is split into detector, lifter, worker, geometry, fusion, semantic-map, and subprocess boundaries. Key files are `protocol.py`, `registry.py`, `types.py`, `worker.py`, `worker_pool.py`, `geometry.py`, `subprocess_bridge.py`, `fusion.py`, `semantic_map.py`, `scene_describer.py`, `backends/`, and `lifters/`. It depends on bridge sensor frames and authoritative camera geometry; it feeds detections, OBBs, tracks, semantic maps, metrics, and WebSocket payloads. Detection and 3D lifting are separate by ADR-0007; workers are per-robot newest-wins by ADR-0009; OBBs and projection paths are server-owned by ADR-0010 and ADR-0013.

### Tracking: `src/tracking/`

Tracking associates detections over time behind its own protocol/registry boundary. Key files are `protocol.py`, `registry.py`, `trackers/bytetrack.py`, and `trackers/none.py`. It depends on perception output types and feeds IDs into 3D detections, semantic maps, and UI overlays. Keep this as an optional stage; do not make detector correctness depend on a tracker being present.

### Metrics and ground truth: `src/metrics/`

Metrics compares live system outputs against simulator truth where that is legitimate and reports runtime health where it is not. Key files are `mujoco_gt.py`, `ground_truth.py`, `drift_metrics.py`, `detection_metrics_tracker.py`, `detection_export.py`, `metrics_tracker.py`, and `mesh_reconstruction.py`. It depends on MuJoCo state, SLAM/perception outputs, and exported logs. Fake mAP is forbidden by ADR-0012; use MuJoCo ground-truth metrics or say the metric is unavailable. Numbers that lie are not “demo polish”; they are debt with a dashboard.

### Web backend and streaming: `backend/web/`

The backend exposes the operator API, WebSocket stream, static frontend, MCP route, and REST endpoints for backend/pipeline selection. Key files are `server.py`, `streaming_viz.py`, `message_types.py`, `connection_manager.py`, `slam_routes.py`, `detector_routes.py`, and `pipeline_routes.py`. It depends on registries and runtime callbacks but should not own robotics algorithms. The browser-based C2 architecture is ADR-0005; payload compatibility here is an architectural contract, not “just JSON.”

### Frontend dashboard: `frontend/src/`

The frontend is the operator surface: React state, Three.js rendering, controls, metrics, camera feeds, detections, semantic map overlays, and the pipeline editor. Key files are `App.tsx`, `hooks/useWebSocket.ts`, stores under `stores/`, Three.js components such as `SceneViewer.tsx`, `PointCloud.ts`, `VoxelManager.ts`, `DetectionBoxes.ts`, `SemanticMapLayer.ts`, and pipeline components under `components/pipeline/`. It depends on WebSocket/REST contracts and server-owned geometry. It must render canonical OBBs and typed graph state; it must not reinvent projection math. React Flow typed DAG editing is ADR-0014.

### MCP and debug visualization: `src/mcp/`, `src/viz/`

MCP exposes a JSON-RPC control/query surface for agents, while `src/viz/` keeps Rerun-style visualization paths useful for debugging. Key files are `mcp/server.py`, `viz/rerun_viz.py`, and `viz/multi_robot_viz.py`. These modules depend on runtime state and should remain secondary surfaces. Per ADR-0005, the browser is the primary product UI; debug visualizers must not become competing sources of truth.

### Tests and contracts: `tests/`

Tests mirror the architecture: bridge, SLAM, coordination, exploration, perception, tracking, metrics, web, integration, smoke, and contract tests. Particularly important are contract tests around no fake maps, no frontend projection math, OBB round trips, worker backpressure, subprocess fallback, and pipeline apply behavior. If an ADR states an invariant, this is where it should get teeth.

## Invariants

- MuJoCo CPU simulation is the platform boundary. Do not add hardware, GPU-first, or UE/SimWorld assumptions to the main path without a new ADR. See ADR-0002.
- World-frame map fusion relies on MuJoCo ground-truth poses. Do not quietly reintroduce inter-robot ICP or pose-estimation-dependent merge correctness into the default path. See ADR-0003.
- Local robot/coordinator communication is in-process. Do not revive DimOS pLCM or split core services over the network because it feels “more distributed.” Distribution needs a fresh boundary decision. See ADR-0004.
- The browser dashboard is the primary command-and-control surface. Rerun and scripts are debugging aids, not alternate product architectures. See ADR-0005.
- Pluggable algorithms use small runtime-checkable Protocols plus registries. Do not add central switch statements or force optional heavy imports just to list available backends. See ADR-0006.
- 2D detection and 3D lifting are separate stages unless a backend explicitly advertises native 3D output. Do not bury lifting back inside a detector. See ADR-0007.
- Heavy or crash-prone backends run behind subprocess bridges with explicit serialization and fallback. Do not let torch/native-code experiments share the simulation failure domain by default. See ADR-0008.
- Perception workers are per-robot and newest-wins. Do not replace bounded live backpressure with FIFO queues that produce stale “real-time” detections. See ADR-0009.
- 3D boxes cross the wire in the canonical server-owned OBB format: center, half extents, xyzw quaternion with positive hemisphere, class/score, and optional track ID. Do not build backend-specific box payloads. See ADR-0010.
- Model choices must fit CPU tiers, pinned checkpoints, and offline/CI expectations. Do not add unpinned first-run downloads or GPU-required defaults. See ADR-0011.
- Do not display mAP unless a committed labeled evaluation set exists. Use MuJoCo ground-truth center/recall/jitter/freshness/latency metrics where available. See ADR-0012.
- Geometry is server-owned and has one projection path. The frontend renders world-frame outputs; it does not hardcode FOV, intrinsics, depth lifting, or quaternion construction. See ADR-0013.
- Pipeline editing is a typed React Flow DAG. Node/port schemas and backend registries must stay compatible across Python and TypeScript. See ADR-0014.
- ADRs are the source of architectural rationale. Update them when changing boundaries; do not bury policy in README prose or UI comments. See ADR-0001.

## Layer Boundaries

- `src/bridge/` owns simulator truth and sensor acquisition. Downstream modules consume `SensorFrame`, camera intrinsics, poses, and model state; they do not reach around the bridge for ad hoc MuJoCo access unless they are metrics/ground-truth code.
- `src/slam/`, `src/perception/`, `src/tracking/`, and merge strategies expose Protocol/Registry surfaces. Runtime wiring can select implementations; implementations should not import the coordinator to call back upward.
- `src/coordination/` is the orchestration layer. It may compose bridge, SLAM, exploration, perception, metrics, and streaming. Those lower layers must not depend on coordinator control flow.
- `backend/web/` is an adapter layer between runtime state and browser contracts. It owns routes and serialization, not robotics decisions.
- `frontend/src/` is a client layer. It owns interaction and rendering state, not camera geometry, backend discovery truth, or simulator evaluation semantics.
- Subprocess bridges are failure-domain boundaries. Crossing them requires explicit flat serialization contracts, watchdogs, and tests. If that feels tedious, good. That is the price of not losing the main process.

## Cross-Cutting Concerns

### Error handling and fallbacks

Optional backends should fail as unavailable registry entries, subprocess crashes should trigger subsystem-specific fallback, and frontend controls should surface restart-required versus live-tunable parameters honestly. Silent fallback is only acceptable if the UI/logs make the active backend obvious.

### Logging and observability

Python uses standard logging around runtime state transitions, backend changes, cloud config changes, and subprocess behavior. The frontend exposes user-facing health through stores, metrics panels, crash toasts, and restart overlays. Keep operational truth close to the boundary where users can act on it.

### Configuration

Runtime configuration flows through CLI args, FastAPI app state, registry metadata/parameter schemas, frontend Zustand stores, and pipeline presets. Backend metadata should be generated from registries where possible; duplicating a parameter schema in TypeScript is a contract hazard, not documentation.

### Geometry and coordinate frames

MuJoCo, Open3D, and Three.js disagree enough to ruin your afternoon. Server-side geometry in `src/perception/geometry.py` and SLAM depth conversion code are the authorities. Tests should lock projection, OBB serialization, quaternion order, and “no focal math in frontend” behavior.

### Performance and backpressure

The simulation loop must not wait on slow model inference. Detection uses per-robot newest-wins queues, WebSocket streaming uses compact/delta-style payloads, model backends are CPU-tiered, and frontend rendering should treat large clouds as a resource budget. Real-time systems that process every stale frame are not real-time; they are archivists with latency.

### Testing strategy

Unit tests cover contracts and pure logic; integration/smoke tests cover subprocesses, model availability, end-to-end workers, and web routes; network/model-download tests must be marked separately. ADR invariants deserve tests when enforceable: fake mAP, frontend projection math, OBB wire format, worker backpressure, registry contracts, and subprocess fallback.

### Security and trust boundary

Argus is a localhost research tool, not a hardened multi-tenant service. Still, REST/WebSocket inputs must be schema-validated before mutating app state, model downloads must be pinned, and optional subprocesses must not inherit more authority than needed. If this becomes remotely exposed, write a security ADR first.

## Architecture Decisions

Architecture rationale lives in `/home/prannayag/pragnition/robotics/argus/docs/adr/`. This document is the map: where the countries are, what borders matter, and which roads are paved. ADRs are the law books: why the borders exist and what trade-offs were accepted.

Accepted ADRs currently referenced here:

- ADR-0001: Use Architecture Decision Records
- ADR-0002: Use MuJoCo CPU Simulation as the Platform Boundary
- ADR-0003: Use Ground-Truth World Poses to Remove Map Alignment as a Variable
- ADR-0004: Use In-Process Transport for Local Coordination
- ADR-0005: Use Browser-Based Command and Control with WebSocket Streaming
- ADR-0006: Use Protocol and Registry Pattern for Pluggable Backends
- ADR-0007: Split 2D Detection from 3D Lifting
- ADR-0008: Isolate Heavy and Crashy Backends in Subprocesses
- ADR-0009: Use Newest-Wins Per-Robot Workers for Perception
- ADR-0010: Use Canonical Server-Owned OBB Wire Format
- ADR-0011: Use CPU-Viable Model Tiers and Pinned Offline Checkpoints
- ADR-0012: Forbid Fake mAP and Use MuJoCo Ground-Truth Metrics
- ADR-0013: Use Server-Owned Geometry and a Single Projection Path
- ADR-0014: Use React Flow Typed DAG for Pipeline Editing
