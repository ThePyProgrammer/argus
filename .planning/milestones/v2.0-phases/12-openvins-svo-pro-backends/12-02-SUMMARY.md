---
phase: 12-openvins-svo-pro-backends
plan: 02
subsystem: slam
tags: [zmq, msgpack, subprocess, ipc, slam-bridge]

# Dependency graph
requires:
  - phase: 08-slam-protocol-registry
    provides: SLAMResult, TrackingStatus types
provides:
  - SubprocessSLAMBridge class for spawning C++ SLAM backends via ZMQ IPC
  - Wire protocol: msgpack header + raw numpy multipart (RGB, depth, IMU)
  - Crash/hang detection with automatic cleanup
affects: [12-03-openvins-backend, 12-04-svo-pro-backend]

# Tech tracking
tech-stack:
  added: [pyzmq, msgpack]
  patterns: [zmq-pair-ipc, msgpack-multipart-wire-protocol, subprocess-bridge]

key-files:
  created:
    - src/slam/backends/subprocess_bridge.py
    - tests/slam/test_subprocess_bridge.py
  modified:
    - pyproject.toml

key-decisions:
  - "Duck-typed IMU readings (no hard dependency on Plan 01 IMUReading class)"
  - "ZMQ PAIR socket with IPC transport for low-latency local communication"
  - "Unique endpoint per PID+instance ID to prevent address collisions"

patterns-established:
  - "Subprocess bridge pattern: Python spawns C++ binary, ZMQ PAIR IPC, msgpack headers + raw numpy bytes"
  - "Crash detection via process.poll(), hang detection via RCVTIMEO, IPC socket cleanup on kill"

requirements-completed: [BACK-06]

# Metrics
duration: 3min
completed: 2026-03-23
---

# Phase 12 Plan 02: Subprocess Bridge Summary

**Generic SubprocessSLAMBridge with ZMQ PAIR IPC, msgpack+numpy multipart wire protocol, 5s hang detection, and IPC socket cleanup**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T09:44:19Z
- **Completed:** 2026-03-23T09:47:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- SubprocessSLAMBridge class wrapping any C++ SLAM backend via ZMQ IPC
- Wire protocol: msgpack header (timestamp, shapes, dtypes, n_imu) + raw numpy bytes (RGB, depth, IMU)
- Crash detection (process.poll), hang detection (5s RCVTIMEO), ZMQError handling
- IPC socket file cleanup on kill prevents address-already-in-use on relaunch
- 11 comprehensive tests with mocked subprocess + real ZMQ sockets

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pyzmq and msgpack to project dependencies** - `857e174` (chore)
2. **Task 2 RED: Failing tests for SubprocessSLAMBridge** - `6a2c4dd` (test)
3. **Task 2 GREEN: Implement SubprocessSLAMBridge** - `2fe993b` (feat)

## Files Created/Modified
- `src/slam/backends/subprocess_bridge.py` - Generic subprocess bridge with ZMQ PAIR IPC + msgpack wire protocol
- `tests/slam/test_subprocess_bridge.py` - 11 tests covering spawn, multipart, result parsing, timeout, crash, cleanup, IMU packing
- `pyproject.toml` - Added pyzmq>=26.0 and msgpack>=1.0 dependencies

## Decisions Made
- Duck-typed IMU readings: bridge accepts any object with timestamp/accel/gyro attributes, no hard dependency on Plan 01 IMUReading class
- ZMQ PAIR socket (not PUB/SUB or REQ/REP) for bidirectional 1:1 IPC
- Unique endpoint includes both PID and object id() for collision avoidance across processes and within same process

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Duck-typed IMU to avoid Plan 01 dependency**
- **Found during:** Task 2 (SubprocessSLAMBridge implementation)
- **Issue:** Plan references IMUReading from sensor_types.py but Plan 01 (which adds it) has not been executed yet
- **Fix:** Used duck-typing -- bridge accepts any object with timestamp, accel, gyro attributes
- **Files modified:** src/slam/backends/subprocess_bridge.py
- **Verification:** IMU packing test passes with minimal _FakeIMU dataclass
- **Committed in:** 2fe993b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to avoid circular dependency. No scope creep.

## Issues Encountered
- IPC socket test initially failed because ZMQ bind creates a real socket file at the IPC path, preventing file creation at same path. Fixed by using the ZMQ-created file directly in the assertion.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SubprocessSLAMBridge ready for concrete backends (Plan 03: OpenVINS, Plan 04: SVO Pro)
- Concrete backends inherit and provide binary_path + config
- When Plan 01 completes, real IMUReading objects will work with the bridge (duck-typed)

---
*Phase: 12-openvins-svo-pro-backends*
*Completed: 2026-03-23*
