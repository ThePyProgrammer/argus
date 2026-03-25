---
phase: 12-openvins-svo-pro-backends
plan: 01
subsystem: bridge
tags: [mujoco, imu, accelerometer, gyroscope, sensor-types, vio]

requires:
  - phase: 08-slam-protocol
    provides: SensorFrame dataclass and BridgeProtocol
provides:
  - IMUReading dataclass with accel/gyro/timestamp fields
  - SensorFrame.imu_readings field (backward-compatible default)
  - Go2 XML accelerometer and gyroscope sensor elements
  - MuJoCo bridge IMU sub-stepping (~200Hz collection)
affects: [12-openvins-svo-pro-backends, openvins-backend, svo-pro-backend]

tech-stack:
  added: []
  patterns: [IMU sub-step collection in physics loop, graceful sensor fallback via _has_imu flag]

key-files:
  created:
    - tests/bridge/test_sensor_types_imu.py
    - tests/bridge/test_imu_extraction.py
  modified:
    - src/bridge/sensor_types.py
    - src/bridge/sim_bridge.py
    - models/unitree_go2/go2.xml

key-decisions:
  - "IMU sensor addresses looked up once in start() and cached as instance attributes for zero-overhead per-step access"
  - "Graceful _has_imu fallback: models without sensor elements still work (empty imu_readings list)"
  - "SensorFrame.imu_readings uses field(default_factory=list) for backward compatibility"

patterns-established:
  - "IMU sub-step collection: one IMUReading per mj_step call inside the physics sub-stepping loop"
  - "Sensor address caching: mj_name2id + sensor_adr lookup in start(), reused in step()"

requirements-completed: [BACK-04]

duration: 3min
completed: 2026-03-23
---

# Phase 12 Plan 01: IMU Sensor Extraction Summary

**IMUReading dataclass and MuJoCo bridge sub-step IMU collection at physics rate for visual-inertial SLAM backends**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T09:44:16Z
- **Completed:** 2026-03-23T09:47:20Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- IMUReading dataclass with accel (3,), gyro (3,), and timestamp fields
- SensorFrame extended with backward-compatible imu_readings field (default empty list)
- Go2 XML model has accelerometer and gyroscope sensor elements on the existing imu site
- MuJoCo bridge collects one IMU reading per physics sub-step (10 readings per frame at default config)
- Graceful fallback for models without IMU sensors (empty list, no crash)

## Task Commits

Each task was committed atomically:

1. **Task 1: IMUReading dataclass + SensorFrame.imu_readings (RED)** - `2937198` (test)
2. **Task 1: IMUReading dataclass + SensorFrame.imu_readings (GREEN)** - `4c298dc` (feat)
3. **Task 2: Go2 XML sensors + bridge IMU sub-stepping (RED)** - `ea161a7` (test)
4. **Task 2: Go2 XML sensors + bridge IMU sub-stepping (GREEN)** - `5f6c730` (feat)

_TDD tasks: test (RED) then feat (GREEN) commits for each task._

## Files Created/Modified
- `src/bridge/sensor_types.py` - Added IMUReading dataclass and imu_readings field on SensorFrame
- `src/bridge/sim_bridge.py` - IMU sensor address lookup in start(), sub-step collection in step()
- `models/unitree_go2/go2.xml` - Added accelerometer and gyro sensor elements on imu site
- `tests/bridge/test_sensor_types_imu.py` - Unit tests for IMUReading and SensorFrame.imu_readings
- `tests/bridge/test_imu_extraction.py` - Integration tests for XML sensors and bridge IMU extraction

## Decisions Made
- IMU sensor addresses cached in start() to avoid per-step name lookups
- Graceful _has_imu flag pattern: models without sensor block get empty imu_readings (no crash)
- field(default_factory=list) for SensorFrame.imu_readings so all existing code works unchanged

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- IMU data pipeline ready for OpenVINS and SVO Pro backends
- SensorFrame.imu_readings available to all downstream consumers
- Existing ICP backend unaffected (ignores imu_readings)

## Self-Check: PASSED

All 5 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 12-openvins-svo-pro-backends*
*Completed: 2026-03-23*
