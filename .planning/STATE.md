---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Generic SLAM API
status: unknown
stopped_at: Completed 11-01-PLAN.md
last_updated: "2026-03-23T07:53:41.814Z"
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 11
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.
**Current focus:** Phase 09 — frontend-algorithm-controls

## Current Position

Phase: 09 (frontend-algorithm-controls) — EXECUTING
Plan: 3 of 3

## Performance Metrics

**Velocity:**

- Total plans completed: 10 (v2.0)
- Average duration: 6min
- Total execution time: 58min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 08 | 3/3 | 33min | 11min |
| 10 | 3/3 | 10min | 3min |
| 09 | 2/3 | 7min | 4min |
| 11 | 1/2 | 4min | 4min |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [08-01]: SLAMProtocol uses runtime_checkable Protocol (same pattern as BridgeProtocol)
- [08-01]: Registry stores class paths as strings for lazy import
- [08-01]: ICPBackend copies points/colors arrays to prevent mutable reference bugs
- [08-02]: All SLAM consumers migrated to SLAMProtocol; no direct SLAMPipeline construction outside backends
- [08-02]: Single-robot mode in main.py also uses protocol methods (SLAMResult, get_poses, get_global_cloud)
- [08-02]: Coordinator passes slam_cloud=None to detector (last_frame_cloud no longer a direct attribute)
- [08-03]: SLAM routes use app.state for pending/active backend tracking across requests
- [08-03]: Select endpoint reuses command_callback restart mechanism (no new restart path)
- [08-03]: Parameter patch distinguishes live_tunable vs startup-only via schema metadata
- [v2.0]: Generic SLAM API over hardcoded ICP — research shows ICP wrong for sparse point clouds
- [v2.0]: 4 backends: existing ICP (baseline), ORB-SLAM3, OpenVINS, SVO Pro
- [v2.0]: Pre-session algorithm selection primary; hot-swap deferred to v3.0
- [v2.0]: DL SLAM backends deferred to v3.0 (requires NVIDIA GPU)
- [v2.0]: SLAM backends produce poses only; dense clouds generated from depth images (sparse/dense mismatch fix)
- [10-01]: MergeRegistry mirrors SLAMRegistry exactly: class-path strings, lazy import, @merge_strategy decorator
- [10-01]: ICPUnionStrategy delegates to MapMerger with zero behavioral change
- [10-01]: MergeResult includes optimized_poses dict for future pose graph strategies
- [10-02]: PointToPlane ICP with automatic normal estimation for loop closure detection
- [10-02]: AVAILABLE class attribute + INSTALL_HINT pattern for optional dependency checking in MergeRegistry
- [10-02]: pgo_gtsam reuses _detect_loop_closure from pgo_open3d to avoid duplication
- [10-03]: Merge endpoints appended to slam_routes.py (same router, /api/slam prefix) mirroring SLAM backend pattern
- [10-03]: Coordinator uses isinstance(merger, MergeProtocol) for clean protocol dispatch
- [10-03]: Legacy MapMerger path preserved in _legacy_merge for backward compatibility
- [10-03]: Default merger created via MergeRegistry.create() with ImportError fallback to MapMerger
- [11-01]: All orbslam3 tests mock C++ binding via sys.modules patching for CI portability
- [11-01]: vocab_path param allows test injection; defaults to models/orbslam3/ORBvoc.txt
- [11-01]: Dense cloud from depth_to_pointcloud, sparse ORB count in metrics only (BACK-02)
- [11-01]: Optional dependency pattern: try/import, _AVAILABLE flag, ImportError in __init__
- [09-02]: AlgorithmDropdown uses custom div-based dropdown (not native select) for rich badge rendering
- [09-02]: Module-scope debouncedSendParam avoids recreating debounce timer per render
- [09-02]: Robot poses/rotations/trajectories reset to identity/empty during algorithm restart
- [09-02]: Staged params captured before clearStagedParams to prevent loss on failed POST
- [09-01]: slamStore follows controlStore flat state + setter pattern for consistency
- [09-01]: fetchSlamState uses Promise.all for parallel backend and active endpoint fetches
- [09-01]: ConfirmModal uses ReactDOM.createPortal to document.body for proper z-index stacking

### Roadmap Evolution

- 2026-03-23: v2.0 roadmap created — 6 phases (8-13), 23 requirements mapped
- 2026-03-23: Phase 14 added: Interactive ComfyUI esque React Flow state graph creation system to customize the end-to-end SLAM pipeline + parameters

### Pending Todos

None yet.

### Blockers/Concerns

- ORB-SLAM3 codebase frozen since Dec 2021 — may have build issues with modern toolchains
- OpenVINS requires IMU data not in v1.0 sensor pipeline — must add MuJoCo accelerometer/gyroscope extraction
- SVO Pro open-source release entangled with catkin — de-catkinization effort uncertain
- All CPU-only constraint remains (no NVIDIA GPU)

## Session Continuity

Last session: 2026-03-23T07:59:31Z
Stopped at: Completed 09-02-PLAN.md
Resume file: .planning/phases/09-frontend-algorithm-controls/09-03-PLAN.md
