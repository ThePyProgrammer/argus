---
plan: "12-03"
phase: "12"
status: complete
started: "2026-03-23"
completed: "2026-03-23"
---

# Plan 12-03: OpenVINS Backend — Summary

## One-liner
OpenVINS visual-inertial SLAM backend with SubprocessSLAMBridge composition and C++ harness.

## What was built
- OpenVINSBackend class wrapping SubprocessSLAMBridge, with IMU pass-through, GT offset seeding, dense cloud via depth_to_pointcloud
- C++ harness (extern/openvins_harness/) with CMakeLists.txt and main.cpp wrapping VioManager over ZMQ
- 17 tests passing with mocked bridge

## Key files
### Created
- `src/slam/backends/openvins_backend.py` — OpenVINS backend implementation
- `tests/slam/test_openvins_backend.py` — 17 unit tests
- `extern/openvins_harness/CMakeLists.txt` — CMake build for C++ harness
- `extern/openvins_harness/main.cpp` — C++ ZMQ harness wrapping OpenVINS

### Modified
- `src/slam/backends/__init__.py` — Added openvins_backend import

## Commits
- `95477ad`: feat(12-03): implement OpenVINS visual-inertial SLAM backend
- `34ca058`: feat(12-03): add OpenVINS C++ subprocess harness

## Self-Check: PASSED
- [x] All files created
- [x] Tests pass (17/17)
- [x] No regressions in SLAM suite
