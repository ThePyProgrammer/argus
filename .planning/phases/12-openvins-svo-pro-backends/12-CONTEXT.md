# Phase 12: OpenVINS + SVO Pro Backends - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Integrate OpenVINS (visual-inertial) and SVO Pro (semi-direct) as C++ SLAM backends running in subprocess isolation. Includes IMU sensor extraction from MuJoCo for OpenVINS, a generic subprocess bridge for C++ backends, and crash recovery with ICP fallback. SVO Pro has DSO as a fallback if catkin de-tangling fails.

</domain>

<decisions>
## Implementation Decisions

### Subprocess IPC protocol
- **ZMQ + msgpack** for transport: ZeroMQ IPC sockets with msgpack serialization. ~0.5ms per frame transfer.
- **Raw numpy bytes + msgpack header**: Send shape/dtype as msgpack header, then raw `.tobytes()` for frame data. Fast for large arrays (~1.5MB/frame).
- **Generic SubprocessSLAMBridge**: One shared bridge class reusable for any C++ SLAM backend. Handles spawn, IPC, crash detection, restart. Each backend just provides binary path + config.

### IMU sensor extraction
- **Sub-step MuJoCo for IMU**: Run MuJoCo physics sub-steps between camera frames to collect IMU at ~200Hz. Camera captures at normal rate (~30Hz). Batch IMU readings between frames.
- **Add to SensorFrame**: Add optional `imu_readings: list[IMUReading]` field to SensorFrame. Each IMUReading has `accel` (3,), `gyro` (3,), `timestamp`. Backends that don't need IMU ignore it.
- **Go2 IMU sensors**: Research should check if Go2 MuJoCo XML already has accelerometer/gyroscope sensors. If not, add them. If yes, use them.

### SVO Pro viability
- **Attempt SVO Pro with DSO as fallback**: Try de-catkinizing SVO Pro build. If it takes more than ~1 day of build issues, pivot to DSO (Direct Sparse Odometry) which has clean CMake.
- **Subprocess for all C++ backends**: Both SVO Pro (or DSO) and OpenVINS use the generic SubprocessSLAMBridge. Validates the bridge with multiple backends.

### Crash recovery
- **Fall back to ICP immediately** on subprocess crash (no retry). Switch to ICP and notify user.
- **Toast notification + status change** in frontend: Show dismissible toast "Backend X crashed, fell back to ICP" + change active backend indicator.
- **5-second hang timeout**: If subprocess doesn't respond within 5 seconds, treat as crash. Kill process and apply crash recovery (fall back to ICP).

### Claude's Discretion
- ZMQ socket type (PAIR vs REQ/REP vs PUSH/PULL) for the subprocess bridge
- Exact IMU noise model parameters for MuJoCo sensors (or no noise for simulation)
- DSO vs SVO Pro build investigation strategy and time-boxing
- Toast notification styling and auto-dismiss behavior
- Exact SubprocessSLAMBridge process management (signal handling, cleanup)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing backends (templates)
- `src/slam/backends/icp_backend.py` — Reference in-process backend
- `src/slam/backends/orbslam3_backend.py` — Reference for GT offset seeding, coordinate transforms, depth_to_pointcloud usage
- `src/slam/protocol.py` — SLAMProtocol, SLAMResult, TrackingStatus
- `src/slam/registry.py` — SLAMRegistry, @slam_backend decorator

### Sensor types
- `src/bridge/sensor_types.py` — SensorFrame (must add imu_readings field), CameraIntrinsics, BridgeProtocol

### MuJoCo bridge
- `src/bridge/mujoco_bridge.py` — Where IMU extraction sub-stepping would be added
- `models/unitree_go2/` — Go2 XML model files (check for existing IMU sensors)

### Research
- `.research/report.md` §OpenVINS, §SVO Pro — Capabilities, limitations, CPU requirements
- `.planning/research/PITFALLS.md` — SVO Pro catkin blocker, coordinate frame differences, OpenVINS IMU requirements
- `.planning/research/STACK.md` — OpenVINS ROS-free build path, DSO as fallback
- `.planning/research/ARCHITECTURE.md` — Subprocess isolation design

### Frontend (for crash notification)
- `frontend/src/components/` — Existing React components for toast/notification pattern
- `frontend/src/stores/slamStore.ts` — SLAM state management (active backend, etc.)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ORBSlam3Backend`: Template for GT offset seeding, depth_to_pointcloud integration, coordinate transforms
- `@slam_backend` decorator + `SLAMRegistry`: Same registration pattern for new backends
- `depth_to_pointcloud()`: Same dense cloud generation for OpenVINS/SVO Pro poses
- `backend/web/slam_routes.py`: REST API already handles backend listing/selection — new backends auto-appear

### Established Patterns
- Backend wraps external library, delegates to SLAMPipeline-like internal state
- CAPABILITIES dict + PARAMETER_SCHEMA dict as class attributes
- `process_frame` returns SLAMResult with all fields populated
- GT offset seeding from first frame's ground truth pose

### Integration Points
- `src/slam/backends/__init__.py` — Add imports for openvins_backend and svopro_backend (try/except)
- `src/bridge/sensor_types.py` — Add IMUReading dataclass and imu_readings field to SensorFrame
- `src/bridge/mujoco_bridge.py` — Add IMU sub-stepping between camera frames
- `pyproject.toml` — Add pyzmq and msgpack to dependencies
- `frontend/src/components/` — Add toast notification component for crash fallback

</code_context>

<specifics>
## Specific Ideas

- The SubprocessSLAMBridge should feel like a drop-in replacement for in-process backends — same SLAMProtocol interface, just backed by IPC instead of direct calls
- IMU noise can be zero for simulation (clean sensor data) — OpenVINS will still work, just won't exercise its noise-handling code paths
- The 5-second timeout should be configurable per backend in PARAMETER_SCHEMA (SVO Pro may need longer init)
- pyzmq is pip-installable and lightweight — no build issues expected

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-openvins-svo-pro-backends*
*Context gathered: 2026-03-23*
