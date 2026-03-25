---
phase: 12-openvins-svo-pro-backends
verified: 2026-03-23T10:30:00Z
status: gaps_found
score: 11/12 must-haves verified
gaps:
  - truth: "REQUIREMENTS.md checkbox for BACK-03 reflects implementation status"
    status: partial
    reason: "BACK-03 is marked '[ ]' (Pending) in REQUIREMENTS.md and '| BACK-03 | Phase 12 | Pending |' in the status table, but the implementation is complete and verified. This is a documentation discrepancy, not an implementation gap."
    artifacts:
      - path: ".planning/REQUIREMENTS.md"
        issue: "Line 23 shows '- [ ] **BACK-03**' and line 88 shows 'Pending' — both stale after phase completion"
    missing:
      - "Update REQUIREMENTS.md line 23: change '- [ ] **BACK-03**' to '- [x] **BACK-03**'"
      - "Update REQUIREMENTS.md line 88: change '| BACK-03 | Phase 12 | Pending |' to '| BACK-03 | Phase 12 | Complete |'"
human_verification:
  - test: "Run OpenVINS harness end-to-end with real binary"
    expected: "OpenVINS subprocess accepts ZMQ frames, returns poses, bridge returns SLAMResult"
    why_human: "No OpenVINS C++ binary present in repo — harness is reference impl for users who build from source. Cannot verify subprocess communication without compiled binary."
  - test: "Run DSO harness end-to-end with real binary"
    expected: "DSO subprocess accepts ZMQ frames, returns poses, bridge returns SLAMResult"
    why_human: "No DSO C++ binary present — same as OpenVINS harness situation."
  - test: "Trigger crash fallback in running UI"
    expected: "CrashToast appears in bottom-right, auto-dismisses after 8 seconds, active backend indicator changes to ICP"
    why_human: "Visual and real-time behavior cannot be verified programmatically."
---

# Phase 12: OpenVINS + SVO Pro Backends Verification Report

**Phase Goal:** Users can run visual-inertial (OpenVINS) and semi-direct (SVO Pro) SLAM methods, each isolated in subprocesses so crashes cannot take down the system

**Verified:** 2026-03-23T10:30:00Z
**Status:** gaps_found (documentation discrepancy only — all implementation verified)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                        | Status     | Evidence                                                                              |
|----|----------------------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------|
| 1  | SensorFrame carries IMU readings collected at ~200Hz physics sub-steps                       | VERIFIED   | `sim_bridge.py` collects one `IMUReading` per `mj_step` call; `go2.xml` has `<accelerometer>` + `<gyro>` on `imu` site |
| 2  | Existing backends that ignore IMU continue to work unchanged                                 | VERIFIED   | `SensorFrame.imu_readings` defaults to empty list via `field(default_factory=list)`; 31 bridge tests pass |
| 3  | SubprocessSLAMBridge spawns C++ via ZMQ PAIR + msgpack and returns SLAMResult or None       | VERIFIED   | `subprocess_bridge.py` has `class SubprocessSLAMBridge`, `zmq.PAIR`, `HANG_TIMEOUT_MS=5000`, `send_multipart`, `msgpack.packb`, `os.unlink`; 11 tests pass |
| 4  | When subprocess crashes/hangs, bridge returns None (caller falls back)                       | VERIFIED   | `process.poll()` check returns `None` on non-zero exit; `zmq.Again` handler kills process and returns `None`; 5s `RCVTIMEO` |
| 5  | IPC socket files are cleaned up on process kill                                              | VERIFIED   | `_cleanup()` calls `os.unlink(sock_path)` for `ipc://` endpoints; unique path per `os.getpid() + id(self)` |
| 6  | OpenVINS backend accepts RGB + IMU and produces pose estimates via subprocess                | VERIFIED   | `openvins_backend.py` calls `self._bridge.send_frame(frame.rgb, frame.depth, frame.sim_time, frame.imu_readings)`; `supports_imu=True`; registered via `@slam_backend` |
| 7  | OpenVINS backend appears in SLAMRegistry when module is imported                            | VERIFIED   | `@slam_backend(name="openvins", display="OpenVINS (VIO)")` registers unconditionally; `__init__.py` imports with `try/except` |
| 8  | OpenVINS generates dense clouds from depth images (not native sparse)                       | VERIFIED   | `depth_to_pointcloud(frame.depth, frame.rgb, self._intrinsics)` called in `process_frame` |
| 9  | SVO Pro / DSO backend accepts RGB-D (visual-only, no IMU) via subprocess                    | VERIFIED   | `svopro_backend.py` calls `send_frame` without `imu_readings`; `supports_imu=False`; `T_MUJOCO_FROM_OPTICAL` applied |
| 10 | When subprocess backend crashes, frontend shows crash toast and backend changes to ICP       | VERIFIED   | `CrashToast.tsx` renders when `crashMessage != null`; `SceneViewer.tsx` mounts it; `useWebSocket.ts` handles `crash_fallback` message; `slamStore` has `setCrashMessage` + `setActive('icp')` |
| 11 | crash_fallback WS message emitted when subprocess returns LOST                               | VERIFIED   | `exploration_loop.py` line 206-217: checks `tracking_status.value == "lost"` AND `hasattr(self._slam, '_bridge')`, queues `{"type": "crash_fallback", "payload": {...}}` to `_message_queue` |
| 12 | REQUIREMENTS.md accurately reflects BACK-03 as complete                                     | FAILED     | Line 23 shows `- [ ] **BACK-03**` and line 88 shows `Pending` — stale after implementation completed |

**Score:** 11/12 truths verified (gap is documentation only)

---

## Required Artifacts

| Artifact                                           | Provides                                           | Status     | Details                                                      |
|----------------------------------------------------|----------------------------------------------------|------------|--------------------------------------------------------------|
| `src/bridge/sensor_types.py`                       | IMUReading dataclass + SensorFrame.imu_readings    | VERIFIED   | `class IMUReading` at line 35; `imu_readings: list[IMUReading] = field(default_factory=list)` at line 64 |
| `src/bridge/sim_bridge.py`                         | IMU sub-stepping in step()                         | VERIFIED   | `_has_imu` flag, `sensordata` slicing, `imu_readings.append(IMUReading(...))` per sub-step |
| `models/unitree_go2/go2.xml`                       | Accelerometer and gyroscope sensor elements        | VERIFIED   | `<sensor>` block at lines 203-206 with `<accelerometer site="imu">` and `<gyro site="imu">` |
| `tests/bridge/test_sensor_types_imu.py`            | Unit tests for IMUReading and SensorFrame          | VERIFIED   | 62 lines; 10 tests pass                                      |
| `tests/bridge/test_imu_extraction.py`              | Integration tests for XML sensors + bridge         | VERIFIED   | 81 lines; 21 tests pass (in combined suite)                  |
| `src/slam/backends/subprocess_bridge.py`           | Generic SubprocessSLAMBridge class                 | VERIFIED   | All acceptance criteria present; 327 lines                   |
| `tests/slam/test_subprocess_bridge.py`             | Unit tests with mocked subprocess                  | VERIFIED   | 327 lines; 11 tests pass                                     |
| `pyproject.toml`                                   | pyzmq and msgpack dependencies                     | VERIFIED   | `pyzmq>=26.0` and `msgpack>=1.0` at lines 13-14             |
| `src/slam/backends/openvins_backend.py`            | OpenVINS backend implementing SLAMProtocol         | VERIFIED   | `class OpenVINSBackend`; `supports_imu=True`; `SubprocessSLAMBridge` composed |
| `extern/openvins_harness/main.cpp`                 | C++ subprocess wrapping OpenVINS VioManager + ZMQ  | VERIFIED   | `VioManager`, `zmq`, `msgpack`, `feed_measurement_imu` present |
| `extern/openvins_harness/CMakeLists.txt`           | CMake build for OpenVINS harness                   | VERIFIED   | `openvins_harness` target present                            |
| `tests/slam/test_openvins_backend.py`              | Unit tests with mocked subprocess bridge           | VERIFIED   | 340 lines; 17 tests pass                                     |
| `src/slam/backends/svopro_backend.py`              | SVO Pro / DSO backend implementing SLAMProtocol    | VERIFIED   | `class SVOProBackend`; `supports_imu=False`; `T_MUJOCO_FROM_OPTICAL` |
| `extern/dso_harness/main.cpp`                      | C++ subprocess wrapping DSO FullSystem + ZMQ       | VERIFIED   | `FullSystem`, `zmq`, `msgpack` present                       |
| `extern/dso_harness/CMakeLists.txt`                | CMake build for DSO harness                        | VERIFIED   | File exists; dso_harness target                              |
| `tests/slam/test_svopro_backend.py`                | Unit tests with mocked subprocess bridge           | VERIFIED   | 177 lines; 14 tests pass                                     |
| `frontend/src/components/CrashToast.tsx`           | Dismissible toast for crash fallback               | VERIFIED   | `useSlamStore`, `crashMessage`, auto-dismiss 8s, portal      |
| `frontend/src/stores/slamStore.ts`                 | crashMessage state + setCrashMessage action        | VERIFIED   | `crashMessage: string | null`; `setCrashMessage`; `clearCrashMessage` |
| `frontend/src/components/SceneViewer.tsx`          | Mounts CrashToast alongside RestartOverlay         | VERIFIED   | Import at line 13; `{crashMessage && <CrashToast />}` at line 267 |
| `src/exploration/exploration_loop.py`              | Emits crash_fallback WS message on LOST            | VERIFIED   | Lines 205-217: detects LOST + `_bridge` attr, queues `crash_fallback` to `_message_queue` |
| `.planning/REQUIREMENTS.md`                        | BACK-03 marked complete                            | FAILED     | Still shows `- [ ]` and `Pending` — stale status             |

---

## Key Link Verification

| From                                        | To                                          | Via                                         | Status   | Details                                                    |
|---------------------------------------------|---------------------------------------------|---------------------------------------------|----------|------------------------------------------------------------|
| `src/bridge/sim_bridge.py`                  | `src/bridge/sensor_types.py`                | imports IMUReading, constructs imu_readings | WIRED    | Line 17: `from src.bridge.sensor_types import ... IMUReading` |
| `src/slam/backends/subprocess_bridge.py`   | `src/slam/protocol.py`                      | imports SLAMResult, TrackingStatus          | WIRED    | Line 19: `from src.slam.protocol import SLAMResult, TrackingStatus` |
| `src/slam/backends/subprocess_bridge.py`   | `zmq`                                       | ZMQ PAIR socket for IPC                     | WIRED    | Line 64: `self._socket = self._ctx.socket(zmq.PAIR)`      |
| `src/slam/backends/openvins_backend.py`    | `src/slam/backends/subprocess_bridge.py`   | composes SubprocessSLAMBridge for IPC       | WIRED    | Line 21: import; lines 133, 231: `SubprocessSLAMBridge(...)` instantiated |
| `src/slam/backends/openvins_backend.py`    | `src/slam/protocol.py`                      | returns SLAMResult from process_frame       | WIRED    | `SLAMResult(pose=..., tracking_status=...)` returned       |
| `src/slam/backends/openvins_backend.py`    | `src/slam/depth_to_cloud.py`               | generates dense cloud from depth image      | WIRED    | Line 22: import; line 180: `depth_to_pointcloud(...)` called |
| `src/slam/backends/svopro_backend.py`      | `src/slam/backends/subprocess_bridge.py`   | composes SubprocessSLAMBridge for IPC       | WIRED    | Line 21: import; line 112: `SubprocessSLAMBridge(...)` instantiated |
| `frontend/src/components/CrashToast.tsx`   | `frontend/src/stores/slamStore.ts`          | reads crashMessage from slamStore           | WIRED    | Line 3: `import { useSlamStore }`; line 14: `useSlamStore((s) => s.crashMessage)` |
| `frontend/src/components/SceneViewer.tsx`  | `frontend/src/components/CrashToast.tsx`   | renders CrashToast alongside RestartOverlay | WIRED    | Line 13: import; line 267: `{crashMessage && <CrashToast />}` |
| `frontend/src/hooks/useWebSocket.ts`       | `frontend/src/stores/slamStore.ts`          | handles crash_fallback WS message           | WIRED    | Line 167-175: `case 'crash_fallback'` reads `msg.payload`, calls `setCrashMessage` + `setActive('icp')` |
| `src/exploration/exploration_loop.py`      | `backend/web/streaming_viz.py`              | queues crash_fallback message to WS         | WIRED    | Line 211: `self._streaming_viz._message_queue.append({"type": "crash_fallback", ...})` |

---

## Requirements Coverage

| Requirement | Source Plan | Description                                                           | Status   | Evidence                                                                          |
|-------------|-------------|-----------------------------------------------------------------------|----------|-----------------------------------------------------------------------------------|
| BACK-03     | 12-03-PLAN  | OpenVINS backend integrates via subprocess bridge, accepting RGB + IMU | SATISFIED (stale doc) | `openvins_backend.py` fully implemented: `SubprocessSLAMBridge`, `imu_readings` passed to `send_frame`, registered in registry. REQUIREMENTS.md checkbox is stale. |
| BACK-04     | 12-01-PLAN  | System extracts accelerometer and gyroscope data from MuJoCo simulation | SATISFIED | `go2.xml` has sensor elements; `sim_bridge.py` collects `IMUReading` per sub-step; 10 tests pass |
| BACK-05     | 12-04-PLAN  | SVO Pro backend integrates via subprocess bridge with de-catkinized build | SATISFIED | `svopro_backend.py` uses DSO (de-catkinized) via `SubprocessSLAMBridge`; registered; tests pass |
| BACK-06     | 12-02-PLAN, 12-04-PLAN | Each C++ backend runs in subprocess isolation so crashes do not take down system | SATISFIED | `SubprocessSLAMBridge` isolates crashes via `process.poll()`, `zmq.Again`, `ZMQError` — all return `None`, not raise; unique IPC endpoint per instance |

**Orphaned requirements check:** REQUIREMENTS.md Phase 12 rows — BACK-03, BACK-04, BACK-05, BACK-06. All 4 claimed by plans. No orphans.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `extern/openvins_harness/main.cpp` lines 17-19 | "Reference implementation" advisory comment | Info | Expected per plan design — harness requires OpenVINS C++ libs to compile; not a code defect |
| `.planning/REQUIREMENTS.md` lines 23, 88 | Stale `[ ]` checkbox and `Pending` status for BACK-03 | Warning | Misleads future readers about phase completion. Update required. |

No blocker anti-patterns found.

---

## Human Verification Required

### 1. OpenVINS Subprocess End-to-End

**Test:** Build `extern/openvins_harness/` against an installed OpenVINS, set `OPENVINS_BINARY`, run the sim, select OpenVINS backend, observe pose stream.
**Expected:** Pose estimates flow from OpenVINS subprocess to frontend; no system crash when subprocess is killed externally.
**Why human:** No compiled binary in repo; harness is a reference implementation requiring user's OpenVINS installation.

### 2. DSO Subprocess End-to-End

**Test:** Build `extern/dso_harness/` against DSO built from source, set `DSO_BINARY`, run the sim, select SVO Pro backend, observe pose stream.
**Expected:** Pose estimates flow from DSO subprocess to frontend; visual-only (no IMU) operation.
**Why human:** Same binary availability constraint as OpenVINS.

### 3. Crash Toast Visual Verification

**Test:** With a running frontend, trigger a crash in the subprocess (kill the spawned process manually or send malformed data), observe the toast notification.
**Expected:** Red/orange toast appears in bottom-right corner reading "Backend SVOProBackend crashed, fell back to ICP", auto-dismisses after 8 seconds, manual close button works, active backend indicator changes to ICP.
**Why human:** Visual rendering and real-time behavior cannot be verified statically.

---

## Test Results Summary

All automated tests pass:

| Suite                               | Tests | Result |
|-------------------------------------|-------|--------|
| `tests/bridge/` (full suite)        | 31    | PASS   |
| `tests/slam/test_subprocess_bridge` | 11    | PASS   |
| `tests/slam/test_openvins_backend`  | 17    | PASS   |
| `tests/slam/test_svopro_backend`    | 14    | PASS   |
| **Total**                           | **73**| **PASS** |

## Git Commits Verified

All 11 commits claimed in summaries confirmed in `git log`:

| Commit   | Plan  | Description                                              |
|----------|-------|----------------------------------------------------------|
| 2937198  | 12-01 | test: IMUReading and SensorFrame.imu_readings (RED)      |
| 4c298dc  | 12-01 | feat: IMUReading dataclass and SensorFrame.imu_readings  |
| ea161a7  | 12-01 | test: Go2 XML sensors and IMU sub-stepping (RED)         |
| 5f6c730  | 12-01 | feat: Go2 XML IMU sensors and bridge sub-step collection |
| 857e174  | 12-02 | chore: add pyzmq and msgpack dependencies                |
| 6a2c4dd  | 12-02 | test: SubprocessSLAMBridge (RED)                         |
| 2fe993b  | 12-02 | feat: SubprocessSLAMBridge with ZMQ IPC + msgpack        |
| 95477ad  | 12-03 | feat: OpenVINS visual-inertial SLAM backend              |
| 34ca058  | 12-03 | feat: OpenVINS C++ subprocess harness                    |
| e922103  | 12-04 | feat: SVO Pro / DSO backend with SubprocessSLAMBridge    |
| c061948  | 12-04 | feat: DSO C++ harness, crash toast, crash_fallback WS    |

---

## Gaps Summary

The single gap is a stale documentation entry: BACK-03 is marked `[ ]` (Pending) in `.planning/REQUIREMENTS.md` at line 23 and `Pending` in the status table at line 88. The implementation is fully complete — `src/slam/backends/openvins_backend.py` accepts RGB + IMU via `SubprocessSLAMBridge`, is registered in `SLAMRegistry`, and all 17 tests pass. This was not updated after plan 12-03 completed.

This is a two-line documentation fix, not an implementation gap. The phase goal is functionally achieved.

---

_Verified: 2026-03-23T10:30:00Z_
_Verifier: Claude (gsd-verifier)_
