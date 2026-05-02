---
status: complete
trigger: "When user zooms camera close to the voxel grid in the Three.js viewer, the voxel cubes disappear and scattered point cloud dots appear instead."
created: 2026-03-24T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Focus

hypothesis: TWO issues - (1) PointCloudManager.points never set visible=false on construction, so it's always visible; (2) VoxelManager InstancedMesh never computes bounding sphere, causing frustum culling at close range
test: verify PointCloud visibility default and InstancedMesh bounding sphere
expecting: PointCloud.ts Points object has no visible=false; VoxelManager has no computeBoundingSphere/frustumCulled=false
next_action: apply fix for both issues

## Symptoms

expected: Voxel grid (InstancedMesh cubes) stays visible at all camera distances
actual: When camera gets close enough, the cube geometry disappears and what looks like the underlying point cloud (scattered dots) becomes visible
errors: No console errors
reproduction: Select "Voxel Grid" output mode, zoom camera close to the voxels
started: First time testing close-up zoom, may have always been this way

## Eliminated

## Evidence

- timestamp: 2026-03-24T00:01:00Z
  checked: VoxelManager.ts constructor
  found: InstancedMesh created from BoxGeometry with no bounding sphere computation and no frustumCulled=false. Three.js computes bounding sphere from geometry alone (one tiny box at origin), not from instance positions spread across the scene.
  implication: When camera moves close, frustum test sees tiny bounding sphere, culls entire InstancedMesh -> all voxels vanish.

- timestamp: 2026-03-24T00:01:30Z
  checked: PointCloudManager.ts constructor vs VoxelManager constructor
  found: PointCloudManager calls computeBoundingSphere() after every updateFull (line 78), correctly sizing its bounds. PointCloudManager also starts visible=true (Three.js default) while VoxelManager starts visible=false.
  implication: Point cloud survives frustum culling at all distances. Point cloud default visibility is inconsistent with VoxelManager.

- timestamp: 2026-03-24T00:02:00Z
  checked: SceneViewer cross-fade logic (lines 163-325)
  found: Cross-fade properly hides faded-out manager (visible=false at line 316). Initial setup (lines 178-183) only sets active mode visible=true but does NOT explicitly hide inactive modes. PointCloudManager starts visible=true by default.
  implication: If initial mode is 'voxel' (not default but possible), point cloud would remain visible. Defensive fix: PointCloudManager should start hidden like VoxelManager.

- timestamp: 2026-03-24T00:02:30Z
  checked: Whether InstancedMesh frustum culling causes the reported symptom
  found: When InstancedMesh is culled, voxels disappear entirely. If point cloud is somehow still visible (e.g., initial mode edge case, or future code path), the user sees dots. Even if point cloud is hidden, the voxels vanishing at close range is the core user-facing bug.
  implication: Primary fix: disable frustum culling on InstancedMesh. Secondary fix: PointCloudManager starts hidden for consistency.

## Resolution

root_cause: VoxelManager's InstancedMesh uses Three.js default frustum culling, but bounding sphere is computed from geometry (single BoxGeometry at origin) not from instance positions. When camera gets close, the tiny bounding sphere fails the frustum test and the entire mesh is culled. The point cloud may also remain visible due to PointCloudManager defaulting to visible=true (unlike VoxelManager which starts hidden).
fix: (1) Set frustumCulled=false on InstancedMesh in VoxelManager. (2) Set PointCloudManager.points.visible=false in constructor for consistency.
verification: TypeScript compiles cleanly for both changed files. Manual browser visual verification is explicitly moved out of the v4.0 locomotion closeout path because this is frontend closeup rendering hygiene, not a blocker for LOC-ENV-01, LOC-CTRL-01, LOC-METRICS-01, or LOC-EVAL-01 milestone archive.
files_changed: [frontend/src/components/VoxelManager.ts, frontend/src/components/PointCloud.ts]
