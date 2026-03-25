---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: Generic SLAM API
status: Milestone complete
last_updated: "2026-03-25T07:26:48.423Z"
last_activity: 2026-03-25
progress:
  total_phases: 7
  completed_phases: 6
  total_plans: 24
  completed_plans: 23
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-23)

**Core value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.
**Current focus:** Phase 15 — close-v2-0-audit-gaps

## Current Position

Phase: 15
Plan: Not started

## Performance Metrics

**Velocity:**

- Total plans completed: 20 (v2.0)
- Average duration: 6min
- Total execution time: ~145min (includes post-checkpoint ORB-SLAM3 fixes)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 08 | 3/3 | 33min | 11min |
| 10 | 3/3 | 10min | 3min |
| 09 | 3/3 | 12min | 4min |
| 11 | 2/2 | ~78min | ~39min |
| 12 | 4/4 | 12min | 3min |
| Phase 13 P01 | 5min | 2 tasks | 9 files |
| Phase 13 P02 | 3min | 2 tasks | 5 files |
| Phase 13 P03 | 6min | 2 tasks | 6 files |
| Phase 14 P01 | 3min | 2 tasks | 6 files |
| Phase 14 P02 | 5min | 2 tasks | 9 files |
| Phase 14 P03 | 4min | 2 tasks | 4 files |
| Phase 14 P04 | 4min | 2 tasks | 4 files |
| Phase 14 P05 | 4min | 2 tasks | 5 files |
| Phase 15 P02 | 1min | 1 tasks | 2 files |
| Phase 15 P01 | 2min | 2 tasks | 4 files |

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
- [11-02]: Store last_tracking_status on ExplorationLoop (closest to SLAMResult) rather than RobotInstance
- [11-02]: Propagate tracking_status via pose_update WS message (piggyback on frequent updates)
- [11-02]: Use getattr with default "ok" for backward compat with ICP backend
- [11-02]: ORB-SLAM3 returns T_cw; must invert to T_wc before frame conversion
- [11-02]: Seed ground truth offset from first frame so map aligns with MuJoCo world origin
- [11-02]: Return INITIALIZING status (not LOST) before first successful track; use ground truth pose during init
- [09-02]: AlgorithmDropdown uses custom div-based dropdown (not native select) for rich badge rendering
- [09-02]: Module-scope debouncedSendParam avoids recreating debounce timer per render
- [09-02]: Robot poses/rotations/trajectories reset to identity/empty during algorithm restart
- [09-02]: Staged params captured before clearStagedParams to prevent loss on failed POST
- [09-01]: slamStore follows controlStore flat state + setter pattern for consistency
- [09-01]: fetchSlamState uses Promise.all for parallel backend and active endpoint fetches
- [09-01]: ConfirmModal uses ReactDOM.createPortal to document.body for proper z-index stacking
- [09-03]: Backend WS handler reuses SLAMRegistry schema lookup (same as REST PATCH /params) for consistency
- [09-03]: slam_param_ack sent per-param immediately (not batched) for responsive UI feedback
- [09-03]: RestartOverlay rendered inside SceneViewer container div as sibling to imperatively-appended Three.js canvas
- [12-01]: IMU sensor addresses cached in start() for zero-overhead per-step access
- [12-01]: Graceful _has_imu fallback: models without sensor elements get empty imu_readings list
- [12-01]: SensorFrame.imu_readings uses field(default_factory=list) for backward compatibility
- [12-02]: Duck-typed IMU readings in SubprocessSLAMBridge (no hard dependency on IMUReading class)
- [12-02]: ZMQ PAIR socket with IPC transport for low-latency C++ subprocess communication
- [12-02]: Unique IPC endpoint per PID+instance ID to prevent address collisions
- [12-04]: DSO is visual-only (no IMU) -- send_frame called without imu_readings
- [12-04]: Reuse T_MUJOCO_FROM_OPTICAL from ORB-SLAM3 for DSO (same camera-optical convention)
- [12-04]: CrashToast uses createPortal to document.body (same z-index pattern as ConfirmModal)
- [12-04]: ExplorationLoop accepts optional streaming_viz parameter for crash_fallback WS emission
- [12-04]: Crash notification pipeline: exploration_loop -> crash_fallback WS -> slamStore.crashMessage -> CrashToast
- [Phase 13]: MetricsTracker uses deque(maxlen=60) ring buffers -- bounded memory, O(1) append
- [Phase 13]: Drift computed every 100 sim steps (10 viz updates) with rolling 50-pose window
- [Phase 13]: Baseline persists across MetricsTracker.reset() for cross-session comparison
- [Phase 13]: updateAllMetrics uses single set() call to avoid 3 re-renders per stats message
- [Phase 13]: ExplorationLoop stores last_slam_metrics for coordinator access
- [Phase 13]: Sparkline uses pure SVG polyline -- zero dependencies, inline rendering
- [Phase 13]: MetricsPanel collapse toggle uses button element for keyboard accessibility
- [Phase 13]: Baseline view references first robot only; multi-robot baseline deferred
- [Phase 13]: Output toggle buttons always enabled; mesh-available gating deferred to Plan 03
- [Phase 13]: VoxelManager uses InstancedMesh with BoxGeometry for single-draw-call voxel rendering
- [Phase 13]: MeshManager uses indexed BufferGeometry with Uint32Array index and flat shading
- [Phase 13]: Cross-fade uses transparent=true and depthWrite=false during 300ms transition
- [Phase 13]: mesh_reconstruction.py follows _AVAILABLE/INSTALL_HINT pattern for graceful Open3D degradation
- [Phase 13]: Poisson reconstruction chosen over BPA for robustness with noisy SLAM data
- [14-01]: Used type alias (not interface) for PipelineNodeData/PipelineEdgeData to satisfy React Flow Record<string, unknown> constraint
- [14-01]: Parameter node override resolution in serializer via edge traversal -- parameter nodes inject value into connected target node params
- [Phase 14]: Kahn's algorithm for DAG cycle detection in PipelineBuilder
- [Phase 14]: param_scalar nodes override target params via edge targetHandle mapping
- [Phase 14]: Pipeline presets use flat JSON files in data/presets/{builtin,user}/
- [14-03]: Module-scope nodeTypes/edgeTypes prevents React Flow remounting nodes on re-render
- [14-03]: getState() in isValidConnection callback avoids stale closure pitfall
- [14-03]: Edge animation respects prefers-reduced-motion via module-level matchMedia check
- [14-03]: IsValidConnection typed with PipelineEdge generic for @xyflow/react v12 compatibility
- [14-04]: NodeInspector uses typeof narrowing for schema description rendering to satisfy TS unknown type
- [14-04]: PresetSelector dropdown positioned above bar (bottom: 100%) for bottom-bar context
- [14-04]: Outside-click handler via mousedown event listener for dropdown dismiss
- [14-05]: InspectorWrapper subscribes reactively to selectedNodeId (not getState()) for proper re-render
- [14-05]: Node catalog fetched on activeView change to 'pipeline', not on mount
- [14-05]: setNodeStatus/setEdgeThroughput update both status maps and node/edge data arrays
- [14-05]: pipeline_status added to WSMessage type union for type-safe dispatch
- [Phase 15-02]: ICP fallback swap placed inside same if-guard as crash_fallback WS emission
- [Phase 15]: slam_restart_complete emitted inside _restart_lock block to guarantee all restart state committed before notification

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

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260324-euj | allow me to hide the output rendering on the C2 portal | 2026-03-24 | f87a052 | [260324-euj-allow-me-to-hide-the-output-rendering-on](./quick/260324-euj-allow-me-to-hide-the-output-rendering-on/) |
| 260324-ffy | persist output mode across page reloads | 2026-03-24 | ee4b663 | [260324-ffy-persist-output-mode-across-page-reloads](./quick/260324-ffy-persist-output-mode-across-page-reloads/) |
| 260324-gfi | fix scene mesh not rendering (Strict Mode) | 2026-03-24 | c69227a | — |
| 260324-gov | extract SliderField reusable component | 2026-03-24 | 9943ba9 | [260324-gov-extract-slider-number-field-as-reusable-](./quick/260324-gov-extract-slider-number-field-as-reusable-/) |
| 260324-h1l | polish SliderField dark mode styling + sig figs | 2026-03-24 | 3aee430 | — |
| 260324-hb0 | add colored scene GLB with material colors from MuJoCo XML | 2026-03-24 | a28d18f | [260324-hb0-add-colored-scene-glb-with-material-colo](./quick/260324-hb0-add-colored-scene-glb-with-material-colo/) |
| 260324-ksf | spawn robots facing opposite directions | 2026-03-24 | ffb3df0 | — |

## Session Continuity

Last activity: 2026-03-25
Resume file: None
