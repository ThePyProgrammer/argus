# Phase 8: Backend Abstraction + ICP Wrap - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a pluggable SLAM backend abstraction layer where any algorithm can register, be discovered, configured, and selected via REST API — with the existing ICP pipeline wrapped as the first backend running unchanged as proof. Frontend algorithm controls, new backends, and metrics are separate phases.

</domain>

<decisions>
## Implementation Decisions

### SLAMResult contract
- `process_frame(frame: SensorFrame) -> SLAMResult` replaces the current `-> np.ndarray` return
- `SLAMResult` is a dataclass with: `pose` (4x4 ndarray), `points` (Nx3 ndarray), `colors` (Nx3 ndarray), `metrics` (dict), `tracking_status` (TrackingStatus enum)
- `TrackingStatus` is a mandatory enum: `OK`, `LOST`, `INITIALIZING`, `RELOCALIZING`
- Each backend is responsible for producing its own per-frame cloud (not delegated to consumer)
- Full lifecycle protocol: `process_frame()`, `reset()`, `get_global_cloud()`, `get_poses()` all required

### Registry & discovery
- **Decorator pattern**: `@slam_backend(name='icp', display='ICP Odometry')` on the class auto-registers on import
- **Lazy-loading**: Only the selected backend is imported. Registry stores class paths (strings), not instances. Avoids loading C++ bindings for unused backends.
- **Class-level attributes** for metadata: each backend class has `CAPABILITIES: dict` and `PARAMETER_SCHEMA: dict` as class attributes. Registry reads these after import.
- **ICP as default**: If no backend explicitly selected, fall back to ICP — preserves v1.0 behavior exactly

### Parameter schema depth
- **Full JSON Schema** for parameter declarations (standard format, frontend renders automatically)
- **Live-tunable where supported**: Backend declares which params are live-tunable vs startup-only. Live-tunable params take effect immediately via PATCH.
- **ICP exposes key params only**: `voxel_size` and `max_cloud_points` — not `max_correspondence_distance` or `fitness_threshold` (implementation details)

### REST API & restart flow
- **In-process teardown+rebuild**: Algorithm selection calls `Coordinator.reset_for_restart()`, recreates `RobotInstance` objects with the new backend. No process restart.
- **Endpoint structure**: Nested under `/api/slam/`
  - `GET /api/slam/backends` — list all backends with capabilities, schemas, and availability status
  - `POST /api/slam/select` — select backend by name, triggers in-process restart
  - `GET /api/slam/active` — current active backend name + config
  - `PATCH /api/slam/params` — update parameters (immediate for live-tunable, returns "requires restart" for startup-only)
- **Availability with install hints**: Each backend shows `available: true/false` + reason string (e.g., "orbslam3-python not installed"). Frontend grays out unavailable ones.

### Claude's Discretion
- Exact decorator implementation details (metaclass vs simple function decorator)
- Error handling for backend crashes during process_frame
- Exact SLAMResult field naming and optional fields
- How to handle the transition from current `np.ndarray` return to `SLAMResult` in tests

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing SLAM implementation
- `src/slam/slam_pipeline.py` — Current ICP implementation to wrap. Key: `process_frame()`, `reset()`, `global_cloud`, `last_frame_cloud`, `slam_poses` properties
- `src/slam/depth_to_cloud.py` — Depth-to-pointcloud conversion used by SLAMPipeline
- `src/slam/octomap_builder.py` — OctoMapBuilder that consumes SLAM frame clouds

### Consumer integration points
- `src/exploration/exploration_loop.py` §192-207 — `_update_slam()` method that calls `process_frame()` and accesses `last_frame_cloud`
- `src/coordination/robot_instance.py` §39-60 — `RobotInstance` dataclass holding `slam: SLAMPipeline`
- `src/coordination/coordinator.py` — Coordinator that creates RobotInstances
- `src/main.py` §175,503 — Two places where `SLAMPipeline(intrinsics)` is constructed directly

### Sensor types
- `src/bridge/sensor_types.py` — `SensorFrame`, `CameraIntrinsics`, `BridgeProtocol` definitions

### Research
- `.research/report.md` — Full SLAM literature review with method comparison tables
- `.planning/research/ARCHITECTURE.md` — Integration architecture with data flow diagrams
- `.planning/research/FEATURES.md` — Feature patterns for SLAM API wrappers (SlamPy, pySLAM references)
- `.planning/research/PITFALLS.md` — 13 pitfalls covering abstraction design, sparse/dense mismatch

### Existing restart mechanism
- `src/coordination/coordinator.py` — `Coordinator.reset_for_restart()` method for in-process teardown

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SLAMPipeline`: Already has the right shape — `process_frame()`, `reset()`, `global_cloud`, `slam_poses`. Wrapping into the new protocol is straightforward.
- `Coordinator.reset_for_restart()`: Existing restart mechanism handles simulation teardown. Algorithm switching piggybacks on this.
- `depth_to_pointcloud()`: Shared utility for all backends that need to generate dense clouds from depth images.
- `SensorFrame` dataclass: Already carries rgb, depth, ground_truth_pose, sim_time — the input contract for all backends.

### Established Patterns
- **Dataclass-heavy**: RobotInstance, SensorFrame, CameraIntrinsics are all dataclasses. SLAMResult should follow this pattern.
- **FastAPI routing**: Existing routes in main.py use `@app.get()` / `@app.post()` directly. New SLAM endpoints follow this.
- **WebSocket streaming**: Existing `push_loop` pattern for real-time data. Live parameter updates can use the same WebSocket.

### Integration Points
- `RobotInstance.slam` field: Currently typed as `SLAMPipeline`. Must change to `SLAMProtocol` (the abstract type).
- `ExplorationLoop.__init__` receives `slam` parameter: Must accept `SLAMProtocol` instead of `SLAMPipeline`.
- `main.py` constructs `SLAMPipeline(intrinsics)` directly in 2 places: Must go through registry instead.
- Tests mock `SLAMPipeline.process_frame` — must update mock return type from `np.ndarray` to `SLAMResult`.

</code_context>

<specifics>
## Specific Ideas

- The decorator registration pattern should feel like Flask's `@app.route()` or pytest's `@pytest.fixture` — familiar to Python developers
- Availability checks should try-import the backend's key dependency (e.g., `import orbslam3`) and catch ImportError to determine availability
- The `/api/slam/backends` response should be rich enough that the frontend can render the full algorithm picker without additional API calls

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 08-backend-abstraction-icp-wrap*
*Context gathered: 2026-03-23*
