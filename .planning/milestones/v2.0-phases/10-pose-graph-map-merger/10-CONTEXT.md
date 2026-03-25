# Phase 10: Pose-Graph Map Merger - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace naive ICP union merge with pose-graph optimization. System supports three selectable merge strategies: ICP union (existing baseline), Open3D PGO, and GTSAM incremental PGO. Merged output remains API-compatible with existing Three.js visualization pipeline. Frontend merge strategy selector is Phase 9 scope (CTRL-02); this phase builds the backend infrastructure and REST API extensions.

</domain>

<decisions>
## Implementation Decisions

### Merge strategy architecture
- **Registry pattern** matching Phase 8 SLAM backends: `@merge_strategy(name='pgo_open3d', display='Open3D Pose-Graph')` decorator auto-registers on import
- Strategies are classes implementing `MergeProtocol` with a `merge()` method
- Each strategy declares `PARAMETER_SCHEMA` (JSON Schema) and `CAPABILITIES` dict — same pattern as SLAM backends
- Lazy-loading: only the selected strategy is imported. Registry stores class paths as strings.

### REST API & activation
- Extend existing `/api/slam/` namespace:
  - `GET /api/slam/merge-strategies` — list available strategies with schemas and availability
  - `POST /api/slam/merge-strategy` — select strategy by name
  - `GET /api/slam/merge-strategy` — current active strategy
  - `PATCH /api/slam/merge-params` — update merge strategy parameters
- Strategy change triggers same `Coordinator.reset_for_restart()` flow as SLAM backend change — pre-session setting, not hot-swappable

### Loop closure detection
- **Geometric ICP matching** on overlapping point cloud regions using Open3D `registration_icp`
- Loop closure checks run **every N merge cycles** (e.g., every 5-10 cycles) to amortize cost
- On ICP failure (low fitness score): **fall back to known spawn transforms** from MuJoCo config as the inter-robot edge. Always produce a valid graph.
- Loop closure quality metrics exposed: fitness score, number of successful/failed closures, graph edge count — feeds Phase 13 metrics dashboard

### PGO library choice
- **Both Open3D PGO and GTSAM** implemented as separate merge strategies (per MERG-01)
- Open3D PGO: full graph optimization each cycle (simulation-scale graphs are small enough)
- GTSAM: incremental optimization (iSAM2) — update without re-solving from scratch
- **GTSAM is optional dependency** with try-import availability check. If not installed, strategy shows `available: false` with install hint. ICP union and Open3D PGO are always available (Open3D already in deps).

### Merge output contract
- **MergeResult dataclass**: `merged_voxels` (Nx3 ndarray), `merged_cloud` (Open3D PointCloud), `optimized_poses` (dict[robot_id, list[4x4 ndarray]]), `metrics` (dict). Mirrors SLAMResult pattern.
- **Input contract**: `Dict[robot_id, RobotMapData]` where `RobotMapData` contains: `poses` (list of 4x4 transforms), `frame_clouds` (list of Nx3 arrays), `current_voxels` (Nx3 array)
- ICP union strategy accepts the full `RobotMapData` input but only uses `current_voxels` — uniform interface, strategy decides what to consume
- PGO strategies **re-project raw clouds using optimized poses** then union-merge into voxels+cloud. Most correct approach for globally consistent output.
- All strategies produce `last_merged_voxels` and `last_merged_cloud` — downstream viz pipeline unchanged (MERG-04)

### Claude's Discretion
- Exact MergeProtocol method signatures beyond `merge()`
- ICP registration parameters (max correspondence distance, fitness threshold for loop closure acceptance)
- How `RobotMapData` accumulates frame clouds (buffer size, decimation)
- GTSAM factor graph structure (noise models, prior factors)
- Open3D PoseGraph edge/node construction details
- Exact N for "every N merge cycles" loop closure check frequency

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing merge implementation
- `src/coordination/map_merger.py` — Current ICP union merger to wrap as baseline strategy. Key: `merge_from_voxels()`, `last_merged_voxels`, `last_merged_cloud` properties
- `src/coordination/coordinator.py` — Coordinator creates and uses MapMerger. Integration point for strategy swap. See `_merge_maps()` method and `reset_merger()`
- `tests/coordination/test_map_merger.py` — Existing tests for union merge behavior

### SLAM backend pattern (to mirror)
- `src/slam/protocol.py` — SLAMProtocol, SLAMResult, TrackingStatus. Model for MergeProtocol and MergeResult
- `src/slam/backends/icp_backend.py` — ICP backend with `@slam_backend` decorator. Model for `@merge_strategy` decorator
- `src/slam/registry.py` — SLAMRegistry with lazy-loading. Model for MergeRegistry (if exists, else reference pattern)

### REST API extension points
- `backend/web/slam_routes.py` — SLAM REST routes (backends, select, params). Extend with merge strategy endpoints
- `src/main.py` — FastAPI app setup, route mounting

### Research
- `.research/report.md` §319 — "Replace ICP with pose-graph optimization" recommendation
- `.research/findings/axis-4-icp-merge-compatibility.md` — ICP merge alternatives including PGO, FPFH+RANSAC+ICP, non-rigid deformation
- `.research/findings/axis-5-multi-camera-integration.md` — Multi-robot merge approaches (COVINS-G, Kimera-Multi)

### Visualization pipeline (must remain compatible)
- `backend/web/streaming_viz.py` — Streams `last_merged_voxels` and `last_merged_cloud` to frontend via WebSocket

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MapMerger`: 150 LOC, wraps directly as ICP union strategy. `merge_from_voxels()` and `merge_voxels()` are the core logic.
- `Open3D`: Already a dependency. Has `registration_icp`, `PoseGraph`, `GlobalOptimizationLevenbergMarquardt` built-in.
- `SLAMProtocol` / `SLAMResult`: Established protocol+result pattern to mirror for merge strategies.
- `@slam_backend` decorator + `SLAMRegistry`: Established registry pattern to replicate.
- `Coordinator.reset_for_restart()`: Existing restart mechanism for strategy switching.

### Established Patterns
- **Dataclass results**: SLAMResult is a dataclass with ndarray fields + metrics dict. MergeResult should follow same pattern.
- **Registry with lazy import**: SLAM backends use string class paths. Merge strategies should too.
- **JSON Schema parameters**: SLAM backends declare PARAMETER_SCHEMA as class attribute. Merge strategies should match.
- **REST routes in separate module**: SLAM routes in `slam_routes.py`. Merge routes can extend same module or create `merge_routes.py`.

### Integration Points
- `Coordinator._merger` field: Currently typed as `MapMerger`. Must change to `MergeProtocol`.
- `Coordinator._merge_maps()`: Currently calls `merge_from_voxels()` directly. Must pass `RobotMapData` instead.
- `Coordinator` needs to accumulate pose history per robot to feed PGO strategies.
- `streaming_viz.py` reads `merger.last_merged_voxels` — MergeResult must populate these properties.

</code_context>

<specifics>
## Specific Ideas

- Registry pattern should feel identical to SLAM backends — a developer who added a SLAM backend should know exactly how to add a merge strategy
- GTSAM availability follows the same try-import pattern as future SLAM backends (ORB-SLAM3, OpenVINS) — consistent "optional heavy dependency" handling
- Loop closure metrics feed directly into Phase 13's live metrics dashboard — design the metrics dict structure to be dashboard-friendly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-pose-graph-map-merger*
*Context gathered: 2026-03-23*
