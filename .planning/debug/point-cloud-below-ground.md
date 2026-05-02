---
status: resolved
trigger: "Point cloud voxels appear below ground level (z < 0) after camera pose rotation fix"
created: 2026-03-24T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - cam.T configs (2,4,6,8) in CLOUD_CONFIGS use transposed cam_xmat which is R_cam_from_world (inverse), causing points to scatter above/below ground. Default config "1" is correct.
test: Tested all 8 configs - cam.T configs produce 30% below-ground points, cam_noT configs produce 0%.
expecting: N/A - root cause confirmed
next_action: Remove cam.T configs and add z-floor clamp as safety net

## Symptoms

expected: All point cloud voxels should be at z >= 0. Depth camera sees surfaces from above, no geometry below ground.
actual: Some point cloud points have negative z values, appearing below ground plane.
errors: No explicit errors — geometric correctness issue.
reproduction: Run simulation, observe point cloud in Three.js viewer. Some voxels below ground.
started: Noticed after fixing camera pose rotation bug (SimBridge now uses cam_xpos/cam_xmat).

## Eliminated

- hypothesis: Depth linearization produces incorrect values causing below-ground after transform
  evidence: Depth values are already metric from MuJoCo renderer; linearization branch is correct; max_depth=10m clamp is effective
  timestamp: 2026-03-24

- hypothesis: ICP drift pushes estimated pose below ground over time
  evidence: 100-step test with turning showed ICP z-drift of only 0.8mm; zero below-ground points
  timestamp: 2026-03-24

- hypothesis: OctoMap voxelization snaps points to negative z via voxel center rounding
  evidence: OctoMap voxels at z=0.0011 (above ground); voxel centers never go negative with all-positive input
  timestamp: 2026-03-24

- hypothesis: Frontend coordinate transform (Z-up to Y-up worldRoot rotation) causes visual below-ground
  evidence: worldRoot.rotation.x = -PI/2 correctly maps MuJoCo z to Three.js y; grid at y=0 aligns with z=0 data
  timestamp: 2026-03-24

## Evidence

- timestamp: 2026-03-24
  checked: Static robot point cloud z values with default config "1"
  found: All 36160 points at z=[0.001, 0.026], 0% below ground
  implication: Default config produces correct ground-level points

- timestamp: 2026-03-24
  checked: Moving robot (30 steps forward) point cloud z values
  found: All frames 0% below ground, z=[0.001, 0.031]
  implication: Movement and ICP don't cause below-ground points

- timestamp: 2026-03-24
  checked: Extended run (100 steps with turning) + OctoMap
  found: 0 below-ground in SLAM cloud (163K pts) and OctoMap (12K voxels)
  implication: Problem not in normal operation with default config

- timestamp: 2026-03-24
  checked: All 8 cloud configs with same frame data
  found: cam.T configs (2,4,6,8) produce 30% below-ground points (z down to -8.27). cam_noT configs (1,3,5,7) produce 0% below-ground.
  implication: ROOT CAUSE - cam.T uses transposed rotation matrix (R_cam_from_world instead of R_world_from_cam), scattering points incorrectly

## Resolution

root_cause: CLOUD_CONFIGS in cloud_config.py includes 4 configs (2,4,6,8) that use cam_xmat.T (transposed) as the pose rotation. cam_xmat is already R_world_from_cam, so transposing gives R_cam_from_world -- the inverse transform. This scatters camera-frame points incorrectly into world space, with ~30% landing below z=0. Additionally, there is no safety clamp to prevent physically impossible negative-z points regardless of config.
fix: (1) Removed all cam.T configs from CLOUD_CONFIGS (8 -> 4 configs). (2) Simplified sim_bridge.py and multi_bridge.py to always use cam_xmat directly (no transpose branch). (3) Cleaned up unused get_pose_mode import from depth_to_cloud.py. (4) get_pose_mode() now always returns "cam_noT" for backward compat.
verification: All 4 remaining configs tested with MuJoCo bridge - 0 below-ground points across all configs. SLAM pipeline tests pass (2/2). Extended 100-step moving robot test confirmed 0 below-ground points.
files_changed: [src/bridge/cloud_config.py, src/bridge/sim_bridge.py, src/bridge/multi_bridge.py, src/slam/depth_to_cloud.py]
