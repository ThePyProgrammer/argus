---
phase: 13-live-metrics-dashboard-output-toggle
plan: 03
subsystem: rendering, api, ui
tags: [three.js, instanced-mesh, buffer-geometry, open3d, poisson, cross-fade, voxel, mesh]

# Dependency graph
requires:
  - phase: 13-live-metrics-dashboard-output-toggle
    plan: 01
    provides: metricsStore with outputMode/meshData state, stats WebSocket pipeline
provides:
  - VoxelManager class rendering cubes via Three.js InstancedMesh with single draw call
  - MeshManager class rendering indexed BufferGeometry with computed vertex normals
  - mesh_reconstruction.py with Open3D Poisson reconstruction and graceful degradation
  - SceneViewer cross-fade transitions between point cloud, voxel, and mesh modes
  - PointCloudManager extended with setVisible/getMaterial for cross-fade compatibility
affects: [13-UI-SPEC, MetricsPanel, ControlPanel-output-toggle]

# Tech tracking
tech-stack:
  added: []
  patterns: [instanced-mesh-voxel-rendering, cross-fade-opacity-transition, optional-dep-graceful-degradation]

key-files:
  created:
    - src/metrics/mesh_reconstruction.py
    - frontend/src/components/VoxelManager.ts
    - frontend/src/components/MeshManager.ts
    - tests/web/test_mesh_reconstruction.py
  modified:
    - frontend/src/components/PointCloud.ts
    - frontend/src/components/SceneViewer.tsx

key-decisions:
  - "VoxelManager uses InstancedMesh with BoxGeometry for single-draw-call voxel rendering (not individual geometries)"
  - "MeshManager uses indexed BufferGeometry with Uint32Array index for large meshes, flat shading, double-sided"
  - "Cross-fade uses requestAnimationFrame with transparent=true and depthWrite=false during transition to prevent z-fighting"
  - "mesh_reconstruction.py follows project _AVAILABLE/INSTALL_HINT pattern for graceful Open3D degradation"
  - "Poisson reconstruction chosen over BPA for robustness with noisy SLAM data"

patterns-established:
  - "InstancedMesh voxel: BoxGeometry + setMatrixAt/setColorAt with instanceMatrix.needsUpdate"
  - "Cross-fade manager: getManager(mode) returns {getMaterial, setVisible} interface for uniform opacity control"
  - "Optional dependency: try/import, _AVAILABLE flag, INSTALL_HINT string, ImportError in function body"

requirements-completed: [CTRL-07]

# Metrics
duration: 6min
completed: 2026-03-23
---

# Phase 13 Plan 03: Rendering Modes Summary

**Three.js VoxelManager (InstancedMesh) and MeshManager (BufferGeometry) with Open3D Poisson mesh reconstruction and 300ms cross-fade transitions between point cloud, voxel grid, and mesh rendering modes**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-23T11:21:56Z
- **Completed:** 2026-03-23T11:27:49Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- VoxelManager renders cubes via InstancedMesh with single draw call performance (200K max instances)
- MeshManager renders indexed BufferGeometry with computed vertex normals and flat shading
- mesh_reconstruction.py uses Open3D Poisson surface reconstruction with density-based artifact cleanup
- SceneViewer orchestrates 300ms cross-fade transitions between all three rendering modes via requestAnimationFrame
- PointCloudManager extended with setVisible/getMaterial for cross-fade compatibility

## Task Commits

Each task was committed atomically:

1. **Task 1: mesh_reconstruction.py + VoxelManager + MeshManager** (TDD)
   - RED: `aa1810b` (test) -- 5 test cases for mesh reconstruction
   - GREEN: `d470098` (feat) -- mesh_reconstruction.py, VoxelManager.ts, MeshManager.ts
2. **Task 2: SceneViewer output mode switching with cross-fade + PointCloud.ts extension** - `63e0486` (feat)

## Files Created/Modified
- `src/metrics/mesh_reconstruction.py` - Open3D Poisson reconstruction with _AVAILABLE flag, INSTALL_HINT, graceful ImportError
- `frontend/src/components/VoxelManager.ts` - Three.js InstancedMesh voxel rendering manager with setMatrixAt/setColorAt
- `frontend/src/components/MeshManager.ts` - Three.js indexed BufferGeometry mesh rendering with vertex normals
- `tests/web/test_mesh_reconstruction.py` - 5 tests covering reconstruction, min-points guard, availability, unavailability
- `frontend/src/components/PointCloud.ts` - Added setVisible() and getMaterial() methods for cross-fade
- `frontend/src/components/SceneViewer.tsx` - VoxelManager/MeshManager instantiation, metricsStore subscription, cross-fade animation loop

## Decisions Made
- VoxelManager uses InstancedMesh for single-draw-call rendering (not individual BoxGeometry per voxel)
- MeshManager uses indexed BufferGeometry with Uint32Array for supporting large meshes
- Cross-fade uses transparent=true and depthWrite=false during transition to avoid z-fighting
- Poisson reconstruction chosen over BPA for robustness with noisy point clouds
- mesh_reconstruction.py follows existing _AVAILABLE/INSTALL_HINT optional dependency pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing TypeScript compilation errors in DetectionBoxes.ts, SceneViewer.tsx, and useWebSocket.ts continue from prior phases (unrelated to rendering mode changes). No new errors introduced.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three rendering modes operational: point cloud (existing), voxel grid (new), mesh (new)
- Cross-fade transitions wired to metricsStore.outputMode changes
- Mesh data pipeline ready: metricsStore.meshVertices/meshFaces -> MeshManager.updateMesh
- CTRL-07 requirement fully implemented
- Phase 13 complete (all 3 plans executed): metrics pipeline, dashboard UI, rendering modes

## Self-Check: PASSED

All created files verified to exist on disk. All 3 commit hashes (aa1810b, d470098, 63e0486) verified in git log.

---
*Phase: 13-live-metrics-dashboard-output-toggle*
*Completed: 2026-03-23*
