---
status: awaiting_human_verify
trigger: "Point cloud voxels may not be rotated based on the robot dog's facing direction, causing voxels to be placed at incorrect world positions."
created: 2026-03-24T00:00:00Z
updated: 2026-03-24T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED -- SimBridge uses body pose (freejoint qpos) instead of camera pose for ground_truth_pose, but depth is rendered from camera with different orientation
test: Verified by tracing full pipeline and comparing SimBridge vs MultiRobotBridge
expecting: N/A -- root cause confirmed
next_action: Fix SimBridge._capture_frame to use cam_xpos/cam_xmat like MultiRobotBridge does

## Symptoms

expected: Point cloud voxels should be in correct world-frame positions regardless of which direction the robot is facing.
actual: Certain voxels appear to be regenerated off from the original location, suggesting rotation is not applied.
errors: No explicit errors -- geometric correctness issue.
reproduction: Run simulation, observe point cloud placement as robots explore and turn.
started: Unclear -- may have always been present.

## Eliminated

- hypothesis: Rotation not applied in SLAM backends (OpenVINS, ORB-SLAM3, SVO Pro)
  evidence: All backends apply full pose transform via `pose @ pts_h.T` (lines 188, 224, 175 respectively)
  timestamp: 2026-03-24

- hypothesis: Rotation not applied in ICP SLAMPipeline
  evidence: Line 102 `cloud.transform(self._current_pose)` applies full 4x4 pose including rotation
  timestamp: 2026-03-24

- hypothesis: Y/Z flip in depth_to_pointcloud misaligns with cam_xmat convention
  evidence: Verified mathematically: Open3D optical (X-right,Y-down,Z-forward) -> fy=-1,fz=-1 -> MuJoCo cam frame (X-right,Y-up,Z-backward). cam_xmat correctly transforms MuJoCo cam frame to world.
  timestamp: 2026-03-24

- hypothesis: Frontend VoxelManager/SceneViewer drops rotation
  evidence: SceneViewer applies Z-up to Y-up conversion via worldRoot.rotation.x = -PI/2, all managers placed under worldRoot. Positions passed through directly.
  timestamp: 2026-03-24

- hypothesis: MultiRobotBridge has wrong camera pose construction
  evidence: Uses cam_xmat (no transpose) which is R_world_from_cam (verified via MuJoCo docs: xmat without transpose = body-to-world). Combined with cam_xpos, gives correct T_world_from_cam.
  timestamp: 2026-03-24

## Evidence

- timestamp: 2026-03-24
  checked: src/slam/depth_to_cloud.py
  found: depth_to_pointcloud returns camera-frame points (after Y/Z flip), no pose transform applied here
  implication: Pose transform must happen in caller

- timestamp: 2026-03-24
  checked: src/slam/slam_pipeline.py (ICP)
  found: Line 102 cloud.transform(self._current_pose) applies full 4x4 pose. Line 71 seeds initial pose from ground_truth_pose.
  implication: If ground_truth_pose is wrong, all subsequent ICP-chained poses will be wrong too

- timestamp: 2026-03-24
  checked: src/bridge/multi_bridge.py lines 385-399
  found: MultiRobotBridge uses cam_xpos + cam_xmat for ground_truth_pose (default config "cam_noT")
  implication: Multi-robot path has correct camera pose

- timestamp: 2026-03-24
  checked: src/bridge/sim_bridge.py lines 233-243
  found: SimBridge uses _extract_pose() which returns BODY pose from freejoint qpos, NOT camera pose
  implication: Single-robot path has WRONG pose -- body rotation != camera rotation

- timestamp: 2026-03-24
  checked: src/bridge/scene_builder.py line 150-151 and src/locomotion/xml_patcher.py lines 116-118
  found: Camera xyaxes="0 -1 0 0 0 1" means camera frame is rotated relative to body frame (cam X=body -Y, cam Y=body +Z, cam Z=body -X)
  implication: Body rotation matrix cannot be used to transform camera-frame points -- the axes don't match

## Resolution

root_cause: SimBridge._capture_frame() uses robot body pose (from freejoint qpos) as ground_truth_pose, but depth is rendered from a camera that has different axis orientation (xyaxes="0 -1 0 0 0 1"). The camera frame axes don't align with the body frame axes. When SLAM uses this body rotation to transform camera-frame point clouds to world frame, points end up at wrong positions because the rotation is for the body, not the camera.
fix: Updated SimBridge._capture_frame() to use cam_xpos and cam_xmat (same approach as MultiRobotBridge) for ground_truth_pose, respecting the cloud_config pose_mode setting. Also resolved cam_id during start() so it's available for pose extraction.
verification: All 13 SimBridge tests pass. 71 SLAM/coordination tests pass (4 skipped). Only pre-existing failures remain (OpenVINS binary not found, exploration config defaults).
files_changed: [src/bridge/sim_bridge.py]
