# Phase 8: stretch-tracker-fusion-semantic-map - Context

**Gathered:** 2026-04-16
**Status:** Ready for planning
**Source:** Discuss-phase `--auto` (4 gray areas, 14 recommended defaults selected -- no user input, see DISCUSSION-LOG.md)

<domain>
## Phase Boundary

Time-gated differentiators for the v3.0 perception stack -- ByteTrack per-detection `track_id` assignment (stable across frames via spatial IoU association), world-frame multi-robot detection fusion merging same-class detections within a 0.5 m cluster radius, SemanticMap with per-object TTL rendered as a ghosted Three.js layer alongside the 3D reconstruction map, and heterogeneous per-robot backend selection allowing each robot to run a different detector.

**In:**

Backend (ByteTrack tracker):
- `src/tracking/trackers/bytetrack.py` (new) -- `ByteTrackTracker` registered via `@tracker(name="bytetrack", ...)` with `produces_stable_ids: True`. Implements `TrackerProtocol.track(detections_3d) -> Detections3D` using world-frame 3D center distance association (not 2D IoU -- we operate on OBBs, not pixel bboxes). Stamps stable `track_id` on each `OrientedBox3D` across frames.
- `src/perception/worker.py::DetectorWorker._loop` -- EXTENDED: after `lifter.lift()` returns `Detections3D`, call `tracker.track(detections_3d)` to stamp `track_id` before storing to `_latest`. This is the Phase 7 D-14 deferred pump.
- `src/perception/worker_pool.py::DetectorWorkerPool.__init__` -- EXTENDED: accepts `tracker_name` + `tracker_params`; constructs per-robot `TrackerRegistry.create(tracker_name)` alongside per-robot detector + lifter.
- `src/perception/worker_pool.py::DetectorWorkerPool.swap_tracker` (new) -- mirrors `swap_lifter` / `swap_backend` pattern (construct outside lock, no warmup needed for trackers, rebind inside lock).

Backend (multi-robot fusion):
- `src/perception/fusion.py` (new) -- `DetectionFusionManager` class. Consumes per-robot tracked `Detections3D` per coordinator tick, groups same-class detections across robots within 0.5 m world-frame center distance, produces `FusedDetections` (list of `FusedObject` with shared `fused_track_id`, representative OBB from highest-confidence source, contributing robot_ids).
- `backend/web/streaming_viz.py` -- EXTENDED: `_update_stats` emits `fused_detections` WS key alongside per-robot `detection_metrics`. `WebStreamingViz` owns a `DetectionFusionManager` instance.

Backend (SemanticMap):
- `src/perception/semantic_map.py` (new) -- `SemanticMap` class. Maintains a dict of `{fused_track_id: SemanticObject}` where each `SemanticObject` holds the latest OBB, class_name, last_seen timestamp, and TTL. `update(fused_detections, sim_time)` refreshes timestamps; `get_active(sim_time)` returns objects whose `sim_time - last_seen < ttl`. `get_expired_since(last_check_time, sim_time)` returns objects that expired in the interval (for frontend removal).
- `backend/web/streaming_viz.py` -- EXTENDED: `_update_stats` emits `semantic_map` WS key with the active object list + expired object ids (delta update pattern -- frontend adds/updates active, removes expired).

Backend (heterogeneous per-robot backends):
- `src/perception/worker_pool.py::DetectorWorkerPool.swap_backend_for_robot` (new) -- single-robot targeted swap. Same construct-outside-lock -> warmup-outside-lock -> rebind-inside-lock pattern, but only for one `rid`.
- `backend/web/detector_routes.py::POST /api/detectors/select` -- EXTENDED: optional `robot_id` query param. When omitted = all robots (existing behavior). When present = single robot via `swap_backend_for_robot`. Returns per-robot backend status.

Frontend:
- `frontend/src/components/three/SemanticMapLayer.tsx` (new) -- Three.js `<group>` with `InstancedMesh` for OBBs, `MeshBasicMaterial` with alpha-blend (`transparent: true, opacity: f(remaining_ttl/total_ttl)`). Managed via `semantic_map` WS messages: add/update active objects, remove expired. Toggle visibility via existing layer control pattern.
- `frontend/src/stores/semanticMapStore.ts` (new) -- Zustand store: `objects: Record<fused_track_id, SemanticObject>`, `addOrUpdate(objects)`, `remove(ids)`, `clear()`.
- `frontend/src/stores/detectorStore.ts` -- EXTENDED: `perRobotBackend: Record<robotId, string>` to track which robot runs which backend (populated from `GET /api/detectors/active` response extension).
- `frontend/src/components/DetectorDropdown.tsx` or NodeInspector -- EXTENDED: per-robot backend selector when DET-STRETCH-04 is active (dropdown per robot in NodeInspector, sourced from `DetectorRegistry.list()`).
- `frontend/src/stores/metricsStore.ts` -- EXTENDED: `fusedDetections` field for the merged cross-robot detection view in MetricsPanel.
- `frontend/src/components/MetricsPanel.tsx` -- EXTENDED: fused detection count row showing merged cross-robot detections.
- `frontend/src/utils/messageTypes.ts` -- NEW: `SemanticMapObject`, `FusedDetection`, `PerRobotBackendStatus` types.

Tests:
- `tests/tracking/test_bytetrack_tracker.py` -- SC#1 lockdown: run ByteTrack on 100+ frames with a stationary chair, assert single stable `track_id` persists.
- `tests/tracking/test_bytetrack_association.py` -- unit tests for spatial association: within-gate match, cross-gate miss, multi-object disambiguation.
- `tests/perception/test_fusion_manager.py` -- SC#2 lockdown: two robots detecting same chair within 0.5 m, assert single fused entry.
- `tests/perception/test_semantic_map.py` -- SC#3 lockdown: insert object, advance time past TTL, assert expired.
- `tests/perception/test_heterogeneous_backends.py` -- SC#4 lockdown: swap robot_0 to yolov11 and robot_1 to rtdetrv2, assert both produce detections under their respective backend labels.
- `tests/integration/test_bytetrack_e2e.py` -- integration test running ByteTrack in the full coordinator loop for 30 frames, asserting stable track_ids in the WS stream.

**Out:**
- ByteTrack re-ID features (DeepSORT CNN) -- explicitly out of scope per PROJECT.md (CPU killer).
- Kalman filter prediction for occluded objects -- ByteTrack tracks via association only; prediction is a v4.0+ enhancement.
- Fusion of SLAM map + detection map into a unified semantic SLAM loop -- v4.0+ requirement per REQUIREMENTS.md.
- Per-robot tracker selection (heterogeneous trackers) -- all robots share the same tracker; per-robot detector heterogeneity is sufficient for v3.0.
- SemanticMap persistence across sessions -- ephemeral, reset on coordinator restart.
- Fusion threshold auto-tuning -- 0.5 m is fixed for v3.0; adaptive thresholds are v4.0+.
- Track-to-track fusion (merging track histories across robots) -- Phase 8 fuses per-frame snapshots, not track histories.

</domain>

<decisions>
## Implementation Decisions

### ByteTrack Tracker (DET-STRETCH-01)

- **D-01 (ByteTrack in DetectorWorker._loop, post-lift):** ByteTrack runs inside the per-robot `DetectorWorker` thread, called after `lifter.lift()` returns `Detections3D`. Sequence: `detector.process_frame(frame) -> Detections2D` -> `lifter.lift(frame, detections_2d) -> Detections3D` -> `tracker.track(detections_3d) -> Detections3D` (with `track_id` stamped). This is the Phase 7 D-14 deferred pump -- the tracked output is visible to ALL downstream consumers: `latest()`, MetricsPanel, JSONL export, WS stream, pipeline graph `tracks_out` port. No separate tracker thread (ByteTrack association is O(N*M) on detection count, not inference -- microseconds, not milliseconds).

- **D-02 (World-frame 3D center distance association):** ByteTrack's original paper uses 2D IoU on pixel bboxes. Phase 8 adapts to 3D: use Euclidean distance between OBB centers in world frame as the association cost. Threshold: `match_thresh` parameter (default 0.5 m for indoor office scenes). Rationale: we have world-frame 3D OBBs from the lifter pipeline (Phase 4); 2D IoU would require back-projecting to pixel space which is backwards. The 0.5 m default matches Phase 6 D-03's jitter gate and the SC#2 fusion radius.

- **D-03 (Track lifecycle: creation, association, deletion):** Per-robot tracker maintains a `tracks: dict[int, TrackState]` where `TrackState = {track_id, last_center, class_name, frames_since_seen, confidence}`.
  - **Creation:** Unmatched detection with confidence >= `track_thresh` (default 0.3) creates a new track with `track_id = self._next_id`.
  - **Association:** Each frame, compute cost matrix (Euclidean distance) between active tracks and new detections (class-gated -- only same-class matches). Hungarian assignment with `match_thresh` gate. Matched tracks update center + reset `frames_since_seen`.
  - **Deletion:** Tracks with `frames_since_seen > frame_gap` (default 30 frames) are deleted. This means an object can disappear for ~1 second at 30 Hz before losing its track.

- **D-04 (PARAMETER_SCHEMA):** ByteTrack exposes three parameters via `PARAMETER_SCHEMA`:
  ```python
  PARAMETER_SCHEMA = {
      "track_thresh": {"type": "float", "default": 0.3, "min": 0.0, "max": 1.0,
                       "description": "Minimum confidence to create a new track"},
      "match_thresh": {"type": "float", "default": 0.5, "min": 0.1, "max": 2.0,
                       "description": "Max center distance (m) for track association"},
      "frame_gap": {"type": "int", "default": 30, "min": 1, "max": 300,
                    "description": "Frames before a lost track is deleted"},
  }
  ```
  Rendered in NodeInspector via Phase 7's existing `tracker_generic` param surface. Tunable via pipeline apply (hot-apply path for tracker params -- extend Phase 7 D-10 diff policy).

- **D-05 (Worker + pool construction extension):** `DetectorWorker.__init__` gains a `tracker` kwarg. `DetectorWorkerPool.__init__` gains `tracker_name` + `tracker_params` kwargs (defaulting to `"none"` + `{}`); constructs per-robot tracker instances via `TrackerRegistry.create(tracker_name, **tracker_params)`. Per-robot instance separation maintained (same invariant as detector + lifter). `swap_tracker()` added as a peer of `swap_lifter()` / `swap_backend()` -- same lock, same construct-outside-rebind-inside pattern, NO warmup needed (trackers are pure-Python state machines, not model-loading backends).

- **D-06 (Phase 6 jitter upgrade):** Phase 6 D-03's nearest-neighbor jitter proxy is replaced with `track_id`-based lookup: `DetectionMetricsTracker` now keys jitter history by `track_id` (when non-null) instead of nearest-neighbor match. The ring-buffer + stddev math is unchanged -- only the matching step swaps. When `track_id` is null (tracker_none or pre-Phase-8 code), falls back to the existing nearest-neighbor proxy. Backward-compatible.

### Multi-Robot Detection Fusion (DET-STRETCH-02)

- **D-07 (Centralized FusionManager per coordinator tick):** `DetectionFusionManager` is a new class owned by `WebStreamingViz`, called once per coordinator stats tick (same cadence as `_update_stats`). It collects `latest()` from all robots' workers, transforms all detections to world frame (already in world frame from the lifter pipeline), and produces a fused detection list. NOT per-worker -- fusion is inherently cross-robot and must see all robots simultaneously.

- **D-08 (Nearest-neighbor class-gated clustering):** Fusion algorithm:
  1. Collect all tracked `OrientedBox3D` from all robots for the current tick.
  2. Group by `class_name`.
  3. Within each class group, cluster by world-frame center distance: if two detections from different robots have centers within 0.5 m, they are the same object.
  4. For each cluster: pick the detection with highest `score` as the representative OBB. Assign a `fused_track_id` (monotonic session counter). Record contributing `robot_ids`.
  5. Unclustered detections (only one robot sees the object) pass through as single-source fused entries.
  
  Complexity: O(R * D^2) per class per tick where R = robot count, D = detections per class. At 2 robots, ~10 detections per class, this is negligible. No need for a spatial index (k-d tree) at this scale.

- **D-09 (Fused output wire format):** New `fused_detections` key in the WS stats payload:
  ```json
  "fused_detections": [
      {"fused_track_id": 1, "class_name": "chair", "score": 0.92,
       "center": [1.2, 0.5, 0.8], "half_extents": [0.3, 0.4, 0.5],
       "quaternion": [0, 0, 0, 1], "robot_ids": ["robot_0", "robot_1"],
       "source_track_ids": [42, 87]}
  ]
  ```
  Additive -- does not replace per-robot `detection_metrics`. MetricsPanel shows fused count; CameraFeed continues per-robot overlays unchanged.

### SemanticMap with TTL (DET-STRETCH-03)

- **D-10 (Server-side SemanticMap with delta WS updates):** `SemanticMap` class (`src/perception/semantic_map.py`) maintains `{fused_track_id: SemanticObject}` where `SemanticObject` holds the latest representative OBB, class_name, `last_seen_sim_time`, and configurable `ttl` (default 10 s). Server owns truth -- frontend is a dumb renderer (DET-3D-05 precedent: "server owns all geometry, frontend is a dumb renderer").

  Per tick: `semantic_map.update(fused_detections, sim_time)` refreshes `last_seen_sim_time` for matched fused entries; adds new entries. `semantic_map.get_delta(sim_time)` returns:
  - `active`: list of `SemanticObject` that are alive (for frontend add/update)
  - `expired_ids`: list of `fused_track_id` whose `sim_time - last_seen > ttl` (for frontend removal)
  
  Emitted via `semantic_map` WS key in the stats payload (same cadence as all other metrics).

- **D-11 (TTL fade-out rendering):** Frontend `SemanticMapLayer.tsx` renders each active object as a wireframe OBB in the Three.js scene, using `InstancedMesh` with `MeshBasicMaterial({transparent: true, wireframe: true, color: class_color})`. Opacity is proportional to remaining TTL: `opacity = clamp((ttl - (sim_now - last_seen)) / ttl, 0, 1)`. As an object ages without re-observation, it ghosts from fully opaque to invisible. On `expired_ids`: remove from the instanced mesh + store.

  The semantic map is a SEPARATE `<group>` from the reconstruction point cloud and the per-robot detection boxes. Layered rendering order: reconstruction cloud (opaque) -> semantic map OBBs (transparent wireframe) -> detection boxes (solid). Users can toggle the semantic map layer via the existing output-mode/layer control pattern.

- **D-12 (Default TTL: 10 seconds, configurable):** `SemanticMap` accepts `ttl` as a constructor parameter, defaultable to 10 s. Exposed via a future `semantic_map` pipeline node's PARAMETER_SCHEMA if Phase 8 ships a pipeline node for it (Claude's discretion -- if the node surface is trivial, include it; if not, defer). 10 s is long enough to show spatial memory (object persists after robot moves away) and short enough to not clutter the scene with stale entries.

### Heterogeneous Per-Robot Backends (DET-STRETCH-04)

- **D-13 (Per-robot swap via `swap_backend_for_robot(rid, ...)`):** New method on `DetectorWorkerPool`:
  ```python
  def swap_backend_for_robot(self, rid: str, new_backend_name: str,
                              new_backend_params: dict | None = None) -> None:
  ```
  Same pattern as `swap_backend` but targets a single worker. Construct backend outside lock -> warmup outside lock -> rebind `worker._detector` inside `self._swap_lock`. Updates a new `self._per_robot_backends: dict[str, str]` mapping (initialized from uniform `backend_name` at construction). `self.backend_name` becomes the "default" backend; `_per_robot_backends[rid]` overrides it per robot.

  `swap_backend(all_robots)` continues to work -- it calls `swap_backend_for_robot` for each rid and updates `self.backend_name` uniformly.

- **D-14 (REST extension: `POST /api/detectors/select?robot_id=robot_0`):** Backward-compatible extension of the existing endpoint. When `robot_id` is omitted: existing behavior (all robots). When present: calls `pool.swap_backend_for_robot(robot_id, backend_name)`. Response extends with `per_robot` status:
  ```json
  {"status": "ok", "active": "yolov11",
   "per_robot": {"robot_0": "yolov11", "robot_1": "rtdetrv2"}}
  ```
  `GET /api/detectors/active` also extends to show per-robot breakdown.

- **D-15 (Frontend per-robot selector):** In NodeInspector, when a `detector_generic` node is selected and the system has >1 robot, show a per-robot dropdown section:
  ```
  Backend (all robots): [YOLOv11 v]
  --- Per-Robot Override ---
  Robot 0: [YOLOv11 v]
  Robot 1: [RT-DETRv2 v]
  ```
  The "all robots" dropdown is the existing Phase 7 D-02 implementation. Per-robot dropdowns are additive. Selecting a per-robot override calls `POST /api/detectors/select?robot_id=robot_0&backend=rtdetrv2`. Pipeline apply hot-swap path (Phase 7 D-10) is extended to detect per-robot changes.

### Claude's Discretion

- ByteTrack internal data structures beyond the `TrackState` dict (numpy arrays for cost matrix, scipy for Hungarian assignment vs manual greedy).
- Whether to use `scipy.optimize.linear_sum_assignment` or a simpler greedy matcher for the association step (at 2 robots with <20 detections, greedy is sufficient; planner picks).
- Exact class color mapping for SemanticMapLayer (reuse CameraFeed per-class colors from Phase 3 D-16, or assign new semantic-specific palette).
- Whether `SemanticMap` pipeline node ships in Phase 8 or is deferred (if the node surface is trivial -- just `ttl` param + passthrough -- include it; if it requires new port types or complex wiring, defer).
- `fused_detections` MetricsPanel rendering details (count-only vs expanded per-class breakdown).
- Exact opacity curve for TTL fade (linear vs ease-out).
- Whether `swap_backend_for_robot` emits a per-robot WS message or reuses `detector_swap_complete` with a `robot_id` field.
- Hot-apply diff extension for tracker params (add `tracker_name` / `tracker_params` to the Phase 7 D-10 diff policy as hot-applicable fields, or require restart for tracker changes).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 8 spec
- `.planning/REQUIREMENTS.md` -- DET-STRETCH-01, DET-STRETCH-02, DET-STRETCH-03, DET-STRETCH-04
- `.planning/ROADMAP.md` -- Phase 8 section: 4 success criteria, research flag `light`, UI hint `yes`
- `.planning/PROJECT.md` -- v3.0 vision + "time-gated differentiators" scope gate

### Tracker infrastructure (Phase 7 -- extend, don't replace)
- `src/tracking/protocol.py::TrackerProtocol` -- runtime-checkable interface; `track(detections_3d) -> Detections3D` + `reset()` + `CAPABILITIES`
- `src/tracking/registry.py::TrackerRegistry` -- decorator-based registration; `create(name)`, `list_backends()`, `_clear()`
- `src/tracking/trackers/none.py::NoneTracker` -- passthrough reference implementation; ByteTrack follows same shape
- `.planning/phases/07-pipeline-editor-perception-nodes/07-CONTEXT.md` -- D-13/D-14 (tracker scope), D-05 (tracker_generic ports), D-06 (viz_output.tracks_in)

### Worker pool + hot-swap patterns (MUST follow)
- `src/perception/worker_pool.py::DetectorWorkerPool.swap_lifter` (L288-L333) -- EXACT template for `swap_tracker`
- `src/perception/worker_pool.py::DetectorWorkerPool.swap_backend` (L335-L416) -- template for `swap_backend_for_robot`
- `src/perception/worker_pool.py::DetectorWorkerPool.on_backend_crash` (L440-L579) -- crash fallback pattern (crash fallback for heterogeneous backends must fall back the crashed robot only, not all)
- `src/perception/worker.py::DetectorWorker._loop` -- the pump site where `tracker.track()` call is inserted (after lifter.lift, before storing to _latest)

### OBB wire format + types (MUST NOT break)
- `src/perception/types.py::OrientedBox3D` -- `track_id` field already present (Optional[int]); ByteTrack stamps it
- `src/perception/types.py::Detections3D` -- `capture_pose` + `capture_timestamp` (Phase 2 D-11); tracker MUST NOT mutate these
- Phase 1 D-10 invariant: `OrientedBox3D.to_wire()` is the sole quaternion path; SemanticMap + FusionManager consume wire format, never construct quaternions

### Metrics integration (Phase 6 -- extend)
- `src/metrics/detection_metrics_tracker.py::DetectionMetricsTracker` -- D-03 jitter computation upgrades from nearest-neighbor to track_id-based
- `backend/web/streaming_viz.py::WebStreamingViz._update_stats` -- add `fused_detections` + `semantic_map` WS keys
- `frontend/src/stores/metricsStore.ts` -- extend with `fusedDetections` state
- `frontend/src/components/MetricsPanel.tsx` -- extend with fused detection count row

### Frontend rendering patterns (mirror these)
- `frontend/src/components/three/DetectionBoxManager.tsx` (or equivalent) -- InstancedMesh OBB rendering pattern for SemanticMapLayer
- `frontend/src/stores/detectorStore.ts` -- extend with `perRobotBackend` state
- `frontend/src/components/pipeline/NodeInspector.tsx` -- extend with per-robot backend dropdown (Phase 7 D-02 backend dropdown is the base)

### REST endpoints (backward-compatible extension)
- `backend/web/detector_routes.py::POST /api/detectors/select` -- extend with optional `robot_id` param
- `backend/web/detector_routes.py::GET /api/detectors/active` -- extend response with per-robot breakdown
- `backend/web/pipeline_routes.py::apply_pipeline` -- extend hot-apply diff for tracker params + per-robot backend changes

### Phase 5 crash fallback (adapt for heterogeneous)
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-CONTEXT.md` -- D-03/D-04: crash watchdog + session-scoped availability lockout. For heterogeneous backends, crash fallback must target the crashed robot only, not swap all robots to YOLOv11.

### External references
- ByteTrack paper: Zhang et al., "ByteTrack: Multi-Object Tracking by Associating Every Detection Box" (ECCV 2022) -- association algorithm reference
- `scipy.optimize.linear_sum_assignment` -- Hungarian algorithm for cost-matrix assignment (if planner chooses over greedy)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/tracking/registry.py::TrackerRegistry` -- decorator-based registration; ByteTrack registers via `@tracker(name="bytetrack", ...)` with zero registry changes
- `src/tracking/trackers/none.py::NoneTracker` -- structural template for ByteTrack (same `track()` signature, same `CAPABILITIES` shape, same `reset()` contract)
- `src/perception/worker_pool.py::swap_lifter` (L288-L333) -- proven atomic-swap pattern; `swap_tracker` clones it directly
- `src/perception/worker_pool.py::swap_backend` (L335-L416) -- template for `swap_backend_for_robot` (same construct-warmup-rebind sequence, scoped to one worker)
- `src/perception/worker_pool.py::on_backend_crash` (L440-L579) -- WS envelope + fallback pattern; heterogeneous crash fallback adapts this
- `frontend/src/components/three/` -- Three.js rendering components; SemanticMapLayer follows the same `<group>` + `InstancedMesh` pattern
- `backend/web/streaming_viz.py::_update_stats` -- stats payload emitter; Phase 8 adds 2 new keys (fused_detections, semantic_map)

### Established Patterns
- **Atomic ref swap under `_swap_lock`** -- swap_lifter / swap_backend / on_backend_crash all use: construct-outside-lock -> rebind-inside-lock. `swap_tracker` and `swap_backend_for_robot` follow identically.
- **Registry-driven generic node** -- `detector_generic` / `detection3d_generic` / `tracker_generic` pattern; ByteTrack registers and appears in NodeInspector automatically.
- **Side-effect registry registration** -- `import src.tracking.trackers` populates the registry; ByteTrack follows.
- **Per-robot instance separation** -- each worker owns its own detector + lifter + (now) tracker instance. Mutations to one worker never leak to another (DET-STRETCH-04 foundation from Phase 2).
- **WS delta updates** -- existing patterns in streaming_viz emit per-tick snapshots; SemanticMap adapts to delta (active + expired_ids) for efficiency.
- **Server owns geometry, frontend is dumb renderer** -- DET-3D-05 / DET-UI-05 pattern. SemanticMap follows: server computes TTL/fusion, frontend renders verbatim.

### Integration Points
- `src/perception/worker.py::DetectorWorker._loop` -- insert `tracker.track()` call after lifter.lift() returns
- `src/perception/worker_pool.py::DetectorWorkerPool.__init__` -- add `tracker_name` + `tracker_params` kwargs; construct per-robot tracker
- `backend/web/streaming_viz.py::WebStreamingViz` -- owns FusionManager + SemanticMap instances; pumps them per tick in `_update_stats`
- `backend/web/detector_routes.py` -- extend `/select` + `/active` for per-robot breakdown
- `backend/web/pipeline_routes.py::apply_pipeline` -- extend hot-apply diff for tracker param changes
- `frontend/src/stores/detectorStore.ts` -- add `perRobotBackend` state
- `frontend/src/components/MetricsPanel.tsx` -- add fused detection count row

### Constraints
- No `torch` / `numpy` at module scope in `src/tracking/` (Phase 1 thread-config invariant). ByteTrack uses numpy for cost matrix computation but imports lazily inside `track()`.
- `OrientedBox3D` wire format is immutable (Phase 1 D-10). ByteTrack stamps `track_id` via `dataclasses.replace()` (same pattern as NoneTracker).
- Tracker MUST NOT mutate geometry fields (center, half_extents, quaternion), `capture_pose`, or `capture_timestamp` (TrackerProtocol contract).
- CPU-only constraint remains. ByteTrack is pure-Python + numpy; no GPU dependency.
- Phase 8 is time-gated (PROJECT.md) -- if implementation budget is exceeded, cut SemanticMap first (DET-STRETCH-03 is lowest priority), then fusion (DET-STRETCH-02), keeping ByteTrack (DET-STRETCH-01) and heterogeneous backends (DET-STRETCH-04) as the minimum viable phase.

</code_context>

<specifics>
## Specific Ideas

- ByteTrack adapts to 3D: use world-frame OBB center Euclidean distance as the association cost, NOT 2D IoU. We have 3D OBBs from the lifter pipeline; going back to 2D would be backwards.
- 0.5 m cluster radius for fusion matches Phase 6 D-03's jitter gate -- consistency in the spatial threshold across the system.
- SemanticMap TTL creates a "spatial memory" effect: the robot sees a chair, moves to another room, and the chair persists as a ghosted wireframe for 10 seconds before fading. This is the visual differentiator for the 3D viewer.
- Heterogeneous backends = the architectural completion of Phase 2's per-robot instance separation. The per-worker detector ref has ALWAYS been independent; Phase 8 just exposes that independence to the user.
- `tracker_none` passthrough remains the default -- ByteTrack is opt-in via pipeline graph or REST selection.
- Crash fallback for heterogeneous backends: if robot_1 runs BoxeR and it crashes, only robot_1 falls back to YOLOv11. Robot_0's detector is untouched. This is a per-robot scoping of Phase 5 D-03.
- Priority if time-constrained: DET-STRETCH-01 (ByteTrack) > DET-STRETCH-04 (heterogeneous) > DET-STRETCH-02 (fusion) > DET-STRETCH-03 (SemanticMap). ByteTrack is the foundation everything else builds on.

</specifics>

<deferred>
## Deferred Ideas

- **DeepSORT CNN re-ID** -- out of scope per PROJECT.md (CPU killer). ByteTrack's spatial-only association is the v3.0 ceiling.
- **Kalman filter prediction for occluded objects** -- ByteTrack tracks via association only; prediction adds complexity for marginal benefit in an indoor office sim.
- **Semantic SLAM loop closure** -- using detected objects as SLAM landmarks is a v4.0+ requirement. Phase 8's SemanticMap is a visualization layer, not a SLAM input.
- **Per-robot tracker heterogeneity** -- all robots share the same tracker. Unnecessary for v3.0 where ByteTrack is the only real tracker.
- **SemanticMap persistence across sessions** -- ephemeral by design; restart clears it. Session replay is a separate product feature.
- **Fusion threshold auto-tuning** -- 0.5 m is fixed; adaptive thresholds for scenes with differently-sized objects are v4.0+.
- **Track-to-track fusion** -- Phase 8 fuses per-frame snapshots; fusing full track histories (temporal alignment + gap-filling) is v4.0+.
- **3D IoU for fusion association** -- OBB IoU computation is expensive and overkill for indoor scenes at 2-robot scale; center distance is sufficient.
- **SemanticMap pipeline node** -- if the node surface is trivial (passthrough + TTL param), planner may include it. If complex, defer.
- **Fused detection MetricsPanel breakdown per class** -- Phase 8 shows count-only; per-class expansion is a polish item.
- **Hot-swap tracker mid-session via REST** -- currently requires pipeline apply; a dedicated REST endpoint is not needed for v3.0.

</deferred>

---

*Phase: 08-stretch-tracker-fusion-semantic-map*
*Context gathered: 2026-04-16*
*Discussion log: 08-DISCUSSION-LOG.md*
