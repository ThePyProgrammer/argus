---
phase: 01-simulation-bridge-and-single-robot-slam
verified: 2026-03-17T07:00:00Z
status: gaps_found
score: 7/8 must-haves verified
re_verification: false
gaps:
  - truth: "Test suite for simulation bridge runs without collection errors"
    status: failed
    reason: "test_sim_bridge.py still imports SimWorldGymBridge and SimWorldEnvConfig, which were removed in the MuJoCo pivot commit (c8b1cbb). The file fails to collect, blocking a clean full-suite pytest run."
    artifacts:
      - path: "tests/test_sim_bridge.py"
        issue: "Line 13: 'from src.bridge.env_config import SimWorldEnvConfig' -- SimWorldEnvConfig does not exist; class was renamed to MuJoCoEnvConfig. Line 15-23: imports SimWorldGymBridge and ACTION_MOVE_* constants, none of which exist in the pivoted sim_bridge.py (which now only exports MuJoCoBridge)."
    missing:
      - "Update tests/test_sim_bridge.py to import MuJoCoBridge and MuJoCoEnvConfig instead of the deprecated SimWorld names"
      - "Update unit test class to mock mujoco calls rather than gym.make (or use the existing mock structure adapted for MuJoCoBridge)"
      - "The 4 integration test functions at the bottom (test_lifecycle, test_sensor_extraction, test_movement_command, test_ground_truth_pose) can remain as-is but should reference MuJoCoBridge"
human_verification:
  - test: "End-to-end SLAM run with random walk"
    expected: "python -m src.main --control random --max-steps 200 --no-viz produces console output showing cloud points growing and drift metrics printed at shutdown"
    why_human: "Requires MuJoCo rendering, cannot verify in headless CI. User confirmed this ran successfully (3627 pts, 886 voxels, ATE=0.21m, RPE=0.005m) but the verification must record this explicitly."
---

# Phase 1: Simulation Bridge and Single-Robot SLAM Verification Report

**Phase Goal:** A single Go2 robot connects to simulation (MuJoCo, replacing SimWorld after GPU-less pivot), receives sensor data, and produces a local 3D point cloud and occupancy grid via SLAM.
**Verified:** 2026-03-17T07:00:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Context: MuJoCo Pivot

The phase originally targeted SimWorld (UE5, NVIDIA GPU required). Mid-phase, the project pivoted to MuJoCo after discovering no GPU was available. This pivot is captured in commit `c8b1cbb` ("feat: pivot from SimWorld to MuJoCo"). The phase goal is interpreted as: simulation-backend-agnostic. All SIM-* and SLAM-* requirements are evaluated against MuJoCo.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Robot connects to simulation, lifecycle starts/steps/stops | VERIFIED | `MuJoCoBridge` in `src/bridge/sim_bridge.py` has `start()`, `step()`, `stop()`, `is_running`. Commit `c8b1cbb`. |
| 2 | Each step returns a SensorFrame with RGB, metric depth, ground-truth pose, sim_time | VERIFIED | `_capture_frame()` renders RGB + depth via MuJoCo offscreen renderer with linear depth conversion. Ground-truth extracted from `qpos[0:7]` via quaternion -> rotation matrix. |
| 3 | Velocity commands move the robot | VERIFIED | `set_velocity()` buffers linear/angular, `_velocity_to_ctrl()` applies sinusoidal trot gait modulated by velocity. Confirmed by user run showing pose change over 100 steps. |
| 4 | Depth images are converted to 3D point clouds using camera intrinsics | VERIFIED | `depth_to_pointcloud()` in `src/slam/depth_to_cloud.py` implements pinhole unprojection. Unit test `test_point_cloud_output` passes (5 frames -> >0 cloud points). |
| 5 | SLAM pipeline accumulates a growing global point cloud | VERIFIED | `SLAMPipeline.process_frame()` uses ICP odometry, accumulates via `_global_cloud +=`. User run: 3627 points in 100 frames. Unit tests pass. |
| 6 | OctoMap occupancy grid is built from point cloud | VERIFIED | `OctoMapBuilder` uses Open3D VoxelGrid (replaces unavailable `octomap-python`). `insert_scan()` + `get_occupied_voxels()`. User run: 886 voxels. Unit test passes. |
| 7 | ATE and RPE drift metrics are computed and reported | VERIFIED | `compute_drift_metrics()` uses evo library. Printed at shutdown in `main.py` finally block. User run: ATE RMSE=0.21m, RPE RMSE=0.005m. Unit tests pass (zero-error case + 1m-offset case). |
| 8 | Test suite for simulation bridge runs without collection errors | FAILED | `tests/test_sim_bridge.py` imports `SimWorldEnvConfig` and `SimWorldGymBridge` which no longer exist after the MuJoCo pivot. `pytest tests/` fails at collection. |

**Score:** 7/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/bridge/sensor_types.py` | SensorFrame + CameraIntrinsics | VERIFIED | Contains both dataclasses with correct field types. |
| `src/bridge/sim_bridge.py` | MuJoCoBridge (was SimWorldGymBridge) | VERIFIED | Full implementation: start/step/stop/set_velocity/_capture_frame/_extract_pose. 268 lines. |
| `src/bridge/env_config.py` | MuJoCoEnvConfig | VERIFIED | `model_path`, `resolution`, `camera_name`, `sim_steps_per_frame`, `target_step_hz`. |
| `src/slam/depth_to_cloud.py` | `def depth_to_pointcloud` | VERIFIED | Pinhole unprojection with valid-pixel masking and max_depth clipping. |
| `src/slam/slam_pipeline.py` | `class SLAMPipeline` | VERIFIED | ICP odometry, global cloud accumulation, voxel downsampling every 10 frames. |
| `src/slam/octomap_builder.py` | `class OctoMapBuilder` | VERIFIED | Open3D VoxelGrid backend (documented deviation from octomap-python). |
| `src/metrics/drift_metrics.py` | `def compute_drift_metrics` | VERIFIED | ATE + RPE via evo, handles length mismatch (min_len truncation). |
| `src/metrics/ground_truth.py` | `class GroundTruthCollector` | VERIFIED | Accumulates poses/timestamps from SensorFrames. |
| `src/control/teleop.py` | `class TeleopController` | VERIFIED | pynput keyboard listener, WASD + QE strafe, thread-safe. |
| `src/control/waypoint_runner.py` | `class WaypointRunner` | VERIFIED | Present (not read in detail but confirmed by summary and git log). |
| `src/control/random_walk.py` | `class RandomWalkController` | VERIFIED | Present (confirmed by summary and git log commit `1d6ae22`). |
| `src/viz/rerun_viz.py` | `class RerunVisualizer` | VERIFIED | log_frame, log_point_cloud, log_occupancy_grid, log_trajectory, log_robot_pose. |
| `src/main.py` | Entry point wiring all modules | VERIFIED | Imports all 6 modules, run loop wires bridge->SLAM->OctoMap->viz, ATE/RPE at shutdown. |
| `tests/test_sim_bridge.py` | Runnable tests for SIM-01 to SIM-04 | STUB | File exists but fails to collect due to stale SimWorld imports. 14 unit tests + 4 integration tests written for SimWorldGymBridge, not MuJoCoBridge. |
| `pytest.ini` | Pytest config with timeout | VERIFIED | Contains `[pytest]`, `timeout = 30`, markers for `integration` and `unit`. |
| `tests/conftest.py` | Shared fixtures | VERIFIED | `mock_sensor_frame`, `mock_camera_intrinsics`, `sample_point_cloud`, `sample_poses` all present and correct. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `src/slam/depth_to_cloud.py` | `src/bridge/sensor_types.py` | `from src.bridge.sensor_types import CameraIntrinsics` | WIRED | Line 10 of depth_to_cloud.py, used in function signature and unprojection. |
| `src/slam/slam_pipeline.py` | `src/slam/depth_to_cloud.py` | `depth_to_pointcloud` called in `process_frame` | WIRED | Lines 57, 84 of slam_pipeline.py call `depth_to_pointcloud`. |
| `src/slam/slam_pipeline.py` | `src/bridge/sensor_types.py` | `SensorFrame` type in `process_frame` signature | WIRED | Line 15: `from src.bridge.sensor_types import CameraIntrinsics, SensorFrame`. |
| `src/main.py` | `src/bridge/sim_bridge.py` | `MuJoCoBridge` instantiated and stepped | WIRED | Lines 27, 108, 137, 157 of main.py. |
| `src/main.py` | `src/slam/slam_pipeline.py` | `SLAMPipeline` receives SensorFrames | WIRED | Line 32, 120, 161 of main.py. |
| `src/main.py` | `src/slam/octomap_builder.py` | `OctoMapBuilder.insert_scan()` called periodically | WIRED | Lines 31, 121, 171 of main.py. |
| `src/main.py` | `src/metrics/drift_metrics.py` | `compute_drift_metrics` in finally block | WIRED | Lines 30, 207 of main.py. |
| `src/main.py` | `src/viz/rerun_viz.py` | `RerunVisualizer` logs every frame | WIRED | Lines 34, 123, 175-185 of main.py. |
| `src/main.py` | `src/control/teleop.py` | `TeleopController.get_velocity()` called in loop | WIRED | Lines 82-84, 143 of main.py. |
| `tests/test_sim_bridge.py` | `src/bridge/sim_bridge.py` | Import of `SimWorldGymBridge` | NOT WIRED | Import fails: `SimWorldGymBridge` does not exist post-pivot. `MuJoCoBridge` exists instead. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SIM-01 | 01-02 | Connects to gym/sim, manages lifecycle start/stop/reset | SATISFIED | `MuJoCoBridge.start()`, `stop()`, `is_running`. Confirmed by user run. |
| SIM-02 | 01-01, 01-02 | Extracts depth and RGB sensor data per step | SATISFIED | `_capture_frame()` renders RGB (H,W,3 uint8) and metric depth (H,W float32). |
| SIM-03 | 01-02 | Dispatches movement commands to robot | SATISFIED | `set_velocity(linear, angular)` -> `_velocity_to_ctrl()` -> 12-DOF joint targets applied via MuJoCo ctrl. |
| SIM-04 | 01-02 | Extracts ground-truth pose (position + orientation) per step | SATISFIED | `_extract_pose()` reads `qpos[0:3]` (position) and `qpos[3:7]` (quaternion) -> 4x4 homogeneous transform. |
| SLAM-01 | 01-03, 01-04 | SLAM pipeline produces local pose graph and map | SATISFIED | ICP odometry (not RTAB-Map -- documented deviation). Produces cumulative pose and growing point cloud. ATE=0.21m over 100 frames. |
| SLAM-02 | 01-03, 01-04 | SLAM outputs 3D point cloud | SATISFIED | `SLAMPipeline.global_cloud` and `get_cloud_points()`. 3627 points confirmed by user run. |
| SLAM-03 | 01-03, 01-04 | SLAM outputs OctoMap 3D occupancy grid | SATISFIED | `OctoMapBuilder` (Open3D VoxelGrid -- documented deviation from octomap-python). 886 voxels confirmed by user run. |
| SLAM-04 | 01-03, 01-04 | SLAM drift metrics compared to ground-truth | SATISFIED | `compute_drift_metrics()` computes ATE RMSE and RPE RMSE. Printed at shutdown. User run: ATE=0.21m, RPE=0.005m. |

All 8 Phase 1 requirements are SATISFIED. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_sim_bridge.py` | 13-23 | Stale imports from deleted module names (`SimWorldEnvConfig`, `SimWorldGymBridge`, `ACTION_MOVE_FORWARD` etc.) | Blocker | `pytest tests/` fails to collect this file. Test suite cannot run cleanly from root. |
| `src/main.py` | 283-285 (pre-pivot code comment) | Comment "These are placeholder values; replace with actual intrinsics" -- this comment exists in Plan 04 template but was replaced in the actual file with computed MuJoCo intrinsics (`fx = (w/2) / tan(fov/2)`). | Info | Not a real issue; the actual code computes correct intrinsics. |

### Human Verification Required

#### 1. End-to-End SLAM Run

**Test:** `./run.sh python -m src.main --control random --max-steps 200` (or `nix develop --command uv run python -m src.main --control random --max-steps 200`)
**Expected:** Console shows step progress (cloud growing), drift metrics printed at shutdown. Rerun viewer shows point cloud, occupancy grid (green voxels), trajectory.
**Why human:** Requires MuJoCo physics simulation and rendering. Cannot mock in CI. User has already confirmed this works (3627 pts, 886 voxels, ATE=0.21m, RPE=0.005m).

#### 2. Teleop Control Mode

**Test:** `nix develop --command uv run python -m src.main --control teleop` then press WASD keys
**Expected:** Robot moves in MuJoCo, point cloud grows in Rerun as environment is explored.
**Why human:** Requires keyboard input and visual confirmation of responsive control.

## Documented Deviations (Accepted)

These deviations from the original plan are documented and accepted. They do not constitute gaps:

1. **SimWorld -> MuJoCo:** The entire simulation backend was replaced. MuJoCo provides superior depth (metric float32 vs JET-colorized uint8 in SimWorld) and CPU-only operation. Commit `c8b1cbb`.

2. **RTAB-Map -> ICP odometry:** RTAB-Map Python bindings only expose PyMatcher/PyDetector, not full SLAM. Open3D ICP is sufficient for Phase 1 single-robot mapping. ATE=0.21m is acceptable for phase 1. Documented in 01-03-SUMMARY.md.

3. **octomap-python -> Open3D VoxelGrid:** `octomap-python` fails CMake build in the nix environment. Open3D VoxelGrid provides equivalent voxel discretization. API-compatible for future swap. Documented in 01-03-SUMMARY.md.

## Gaps Summary

One gap blocks a clean full-suite test run:

`tests/test_sim_bridge.py` was never updated after the MuJoCo pivot. It still imports `SimWorldGymBridge`, `SimWorldEnvConfig`, and `ACTION_MOVE_*` constants that no longer exist. The file fails at collection time. The fix is mechanical: update the imports and mock targets to reference `MuJoCoBridge` and `MuJoCoEnvConfig` instead. The test assertions themselves (pose shape, dtype, position change) are still valid for MuJoCoBridge.

This does not affect goal achievement -- all 8 requirements are satisfied, the pipeline ran successfully, and the 5 SLAM/OctoMap/metrics unit tests pass. But the test suite is not fully clean, which was a stated acceptance criterion in Plan 01.

---
_Verified: 2026-03-17_
_Verifier: Claude (gsd-verifier)_
