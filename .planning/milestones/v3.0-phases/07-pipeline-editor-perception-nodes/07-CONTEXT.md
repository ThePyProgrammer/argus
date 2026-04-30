# Phase 7: pipeline-editor-perception-nodes - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning
**Source:** Discuss-phase `--auto` (5 gray areas, 14 recommended defaults selected — no user input, see DISCUSSION-LOG.md)

<domain>
## Phase Boundary

Expose the v3.0 perception stack as first-class React Flow nodes in the pipeline editor. Users drag `DetectorNode`, `Detection3DNode`, `TrackerNode` from a new `perception` palette category, connect typed `Detections2D` / `Detections3D` / `Tracks` ports (with distinct colors + per-edge validation), load a built-in `perception_rgbd` preset that wires `sensor_rgbd → detector_generic(yolov11) → detection3d_generic(point_cluster) → tracker_generic(none) → viz_output`, and apply pipeline changes that swap backends in place via `DetectorWorkerPool.swap_backend()` / `swap_lifter()` — NO coordinator restart when only perception params changed. Fix the `pipelineStore.ts:101` hardcoded `dataType: 'PointCloud'` bug with a regression test that locks it down.

**In:**

Frontend (typed nodes + validation):
- `frontend/src/utils/pipelineTypes.ts` — EXTEND `PortDataType` enum with `'Detections2D' | 'Detections3D' | 'Tracks'`; EXTEND `NodeCategory` with `'perception'`.
- `frontend/src/utils/nodeDefinitions.ts` — ADD static defs `detector_generic`, `detection3d_generic`, `tracker_generic`; ADD color entries for 3 new port types + `perception` category; EXTEND `viz_output` inputs with `tracks_in: Tracks` (optional).
- `frontend/src/utils/pipelineValidation.ts` — ADD `findPortTypeMismatches(nodes, edges)` that walks each edge, resolves source output `PortDef.dataType` and target input `PortDef.dataType`, emits `ValidationError` when they disagree; hook into `validateGraph()`. Regression test for `pipelineStore.ts:101` bug (see `07/tests/pipelineStore.dataType.test.ts`).
- `frontend/src/stores/pipelineStore.ts` — FIX line 101 hardcoded `dataType: 'PointCloud' as const`. Resolve dataType from source node's output handle: look up `nodes.find(n => n.id === connection.source).data.outputs.find(p => p.id === connection.sourceHandle)`; fall back to `PointCloud` only when lookup fails (defensive).
- `frontend/src/components/pipeline/NodePalette.tsx` — ADD `'perception'` to `CATEGORY_ORDER` + `CATEGORY_LABELS` (`"Perception"`). No other changes needed — palette auto-groups.
- `frontend/src/components/pipeline/ApplyBar.tsx` — When `POST /api/pipeline/apply` returns `{"status": "hot-applied"}`, skip restart-overlay expectation and show a brief non-blocking toast `"Pipeline updated in place"`. `{"status": "restarting"}` flow unchanged.

Backend (catalog + hot-apply + tracker registry):
- `src/coordination/pipeline_builder.py` — ADD `detector_name`, `detector_params`, `lifter_name`, `lifter_params`, `tracker_name`, `tracker_params` fields to `PipelineConfig`. EXTEND `NodeCatalog.get_catalog()` to iterate `DetectorRegistry.list_backends()`, `Detection3DRegistry.list_backends()`, `TrackerRegistry.list_backends()` and emit `detector_{name}` / `detection3d_{name}` / `tracker_{name}` catalog entries. EXTEND `_REQUIRED_INPUTS` with `detector_`, `detection3d_`, `tracker_` prefixes. EXTEND `PipelineBuilder.build()` to identify detector/lifter/tracker nodes and populate the new PipelineConfig fields (mirroring the existing slam/merger pattern).
- `backend/web/pipeline_routes.py::apply_pipeline` — EXTEND to diff the newly-built `PipelineConfig` against `app.state.last_applied_pipeline_config`. If `topology_digest` (nodes+edges) is identical AND `backend_name / merger_name / filter_chain / tracker_name` unchanged AND only `detector_name / detector_params / lifter_name / lifter_params` moved, call `detector_pool.swap_backend(...)` / `detector_pool.swap_lifter(...)` directly and return `{"status": "hot-applied", "changed": ["detector_name", ...]}` WITHOUT triggering `command_callback({"action": "restart"})`. Else fall back to existing restart path and return `{"status": "restarting"}`. On hot-apply success, update `app.state.last_applied_pipeline_config` in place.
- `src/perception/worker_pool.py` — ADD `swap_backend(new_backend_name, new_backend_params)` mirroring the existing `swap_lifter()` pattern (same `_swap_lock`, same "construct per-worker outside lock, warmup outside lock, bind inside lock" sequence); on success update `self.backend_name`.
- `src/main.py` restart block (lines 440–630) — EXISTING code already consumes `pipeline_config.detector_name` via `getattr` (line 523). EXTEND to also consume `pipeline_config.lifter_name` when present (set `active_lifter_name` before pool construction).
- `src/tracking/` (new package) — `protocol.py::TrackerProtocol` (runtime-checkable), `registry.py::TrackerRegistry` (mirrors `DetectorRegistry` shape with `@tracker` decorator + availability reporting), `trackers/none.py::NoneTracker` (passthrough — assigns `track_id = monotonic incrementing int per frame` so Phase 7 SC#1 passes without ByteTrack). Registered as `"none"` with capability `{framework: "stub", produces_stable_ids: false}`.
- `data/presets/builtin/perception_rgbd.json` (new) — built-in preset wiring `sensor_rgbd → [slam_icp → merger_icp_union, detector_generic(yolov11) → detection3d_generic(point_cluster) → tracker_generic(none)] → viz_output`. Depth output of `sensor_rgbd` connects to `detection3d_generic`'s `depth_in`. Satisfies SC#3 end-to-end (live OBBs in the 3D viewer).

Tests:
- `frontend/src/stores/__tests__/pipelineStore.dataType.test.ts` — regression test for `pipelineStore.ts:101` bug. Creates two nodes with distinct output dataTypes (e.g., `sensor_rgbd.image_out: Image` and `slam_generic.pose_out: Pose`), calls `onConnect` for each; asserts the resulting edge carries the source-handle's `dataType`, not the hardcoded `PointCloud`.
- `frontend/src/utils/__tests__/pipelineValidation.typeMismatch.test.ts` — SC#2 lockdown: wires `sensor_rgbd.image_out (Image)` to `detector_generic.image_in (Image)` → PASS; wires `slam_generic.cloud_out (PointCloud)` to `detector_generic.image_in (Image)` → FAIL with mismatch error.
- `tests/unit/test_pipeline_builder_perception.py` — SC#5 lockdown: builds a graph with `detector_generic` + `detection3d_generic` nodes with specific registry names + params; asserts the resulting `PipelineConfig` carries `detector_name="yolov11"`, `detector_params={...}`, `lifter_name="point_cluster"`, `lifter_params={...}`.
- `tests/integration/test_pipeline_apply_hot.py` — SC#4 lockdown: apply a baseline perception pipeline, capture PID of the main coordinator process (via `os.getpid()` from a live endpoint or stash in app.state at startup), change ONLY `backend` param on `detector_generic` from `yolov11` to `rtdetrv2`, apply, assert response is `{"status": "hot-applied"}`, assert PID unchanged, assert `/api/detectors/active` reports `rtdetrv2`.
- `tests/unit/test_tracker_registry.py` — `TrackerRegistry.list()` returns `none` with `available: true`; `TrackerRegistry.create("none")` returns a `TrackerProtocol` instance that emits incrementing `track_id`s when called.
- `tests/contract/test_perception_rgbd_preset.py` — load `data/presets/builtin/perception_rgbd.json`, run through `PipelineBuilder.build()`, assert no `ValueError`, assert resulting `PipelineConfig.detector_name == "yolov11"` + `.lifter_name == "point_cluster"` + `.tracker_name == "none"` + `.backend_name == "icp"` + `.merger_name == "icp_union"`.

**Out:**
- ByteTrack implementation — Phase 8 DET-STRETCH-01 (Phase 7 ships `TrackerRegistry` + `tracker_none` passthrough only; ByteTrack registers as a drop-in `tracker_bytetrack` entry in Phase 8).
- Multi-robot per-robot backend dispatch UI on pipeline graph — Phase 8 DET-STRETCH-04 (Phase 7's hot-swap changes ALL robots' detectors atomically via `DetectorWorkerPool.swap_backend`).
- SemanticMap TTL / fusion nodes — Phase 8 DET-STRETCH-03 (no `semantic_map_generic` catalog entry yet).
- Input-type capability gating on detector ports (e.g., dynamic port set when `input_type: RGB_TEXT_PROMPT` — DET-MODELS-04 territory, dropped 2026-04-15; reservation intact for future).
- Tracker parameter panel UX — `tracker_none` has no params; ByteTrack params ship alongside in Phase 8.
- Pipeline-editor-driven concurrent SLAM + detector restart UX polish — Phase 3 D-12 already ships stacked overlays; the "aggregate into single message" polish remains deferred.
- `PipelineConfig` versioning / schema migration — additive fields today, no migration needed.

</domain>

<decisions>
## Implementation Decisions

### Node Surface Pattern (DET-PIPELINE-01)

- **D-01 (Registry-driven generic pattern):** Ship `detector_generic` + `detection3d_generic` + `tracker_generic` as the three new node definitions — the same registry-lookup pattern as today's `slam_generic` + `merger_generic`. The node palette shows one generic entry PER registered backend via `NodeCatalog.get_catalog()` iteration (e.g., `detector_yolov11`, `detector_rtdetrv2`, `detector_boxer`). The user drags any of them onto the canvas; the ACTIVE backend is the `registryName` on that node. Per-backend concrete node types (distinct `DetectorNode_YOLO` / `DetectorNode_RTDETR` classes) are REJECTED — they would double the maintenance cost of every new backend (add a backend → add a node def → keep them in sync) and break from the existing pattern for zero UX benefit. Matches the "DetectorRegistry mirrors SLAMRegistry" invariant from PROJECT.md.

- **D-02 (Changing `backend` param = hot-swap, not node-type change):** Users change the active backend by editing the node's `backend` param in the Inspector (a dropdown sourced from `DetectorRegistry.list()`) — NOT by deleting and replacing the node. `registryName` on the node data is mutable; `updateNodeParam` on key `backend` updates `data.registryName` + the `parameterSchema` (refetched from `/api/pipeline/node-catalog`). This is what enables SC#4 — a topology-preserving param change routes to the hot-swap path. Deleting a detector node and adding a new one WILL trigger a restart (topology changed).

- **D-03 (Port definitions — `detector_generic`):**
  - Inputs: `image_in: Image` (required), `depth_in: Image` (optional — consumed by 3D-native backends like BoxeR; IGNORED by 2D-only backends).
  - Outputs: `detections_2d_out: Detections2D` (always), `detections_3d_out: Detections3D` (present in the node def but only PRODUCES data when `capabilities.outputs_3d_natively === true`; edges from this port on a 2D-only backend simply carry zero-count Detections3D envelopes — documented behavior, not an error).
  - Rationale: a single node definition fits all detector backends; capability flags gate runtime behavior, NOT the port surface. Hiding the 3d output on 2D-only backends creates port-churn on backend swap (SC#4 would need to tear down/recreate edges) — worse than a documented zero-count envelope.

- **D-04 (Port definitions — `detection3d_generic`):**
  - Inputs: `detections_2d_in: Detections2D` (required), `depth_in: Image` (required — lifters need depth frustum per Phase 4 D-04/D-05), `pose_in: Pose` (optional — future world-frame lifters may need it, unused by `point_cluster` and `median_depth` which read pose from the SensorFrame envelope).
  - Outputs: `detections_3d_out: Detections3D` (always).
  - Rationale: matches the `Detection3DProtocol.lift(frame, detection_2d, slam_cloud)` signature from Phase 1. `slam_cloud` is NOT exposed as a port yet — lifters that need the fused SLAM cloud can read it from the `SensorFrame`-carried pose/extrinsics via the coordinator (Phase 4 decision). If a future lifter needs explicit cloud input, ADD a `cloud_in: PointCloud` port then.

- **D-05 (Port definitions — `tracker_generic`):**
  - Inputs: `detections_3d_in: Detections3D` (required).
  - Outputs: `tracks_out: Tracks` (always).
  - Rationale: Phase 8 ByteTrack will slot into this shape unchanged. `Tracks` is a new port type so downstream consumers (currently only `viz_output` via the new optional `tracks_in`) can be type-checked.

- **D-06 (viz_output gains `tracks_in`):** `viz_output` node definition gains `tracks_in: Tracks` (optional). The `perception_rgbd` preset routes `tracker_generic(none) → viz_output.tracks_in` so the tracker branch has a sink and SC#1's three-node drag-and-connect completes without dangling-output validation errors. Frontend renderer today ignores `tracks` — Phase 8 adds the ghosted `track_id` label layer (DET-STRETCH-03 territory).

### Port Types, Colors, and Edge Validation (DET-PIPELINE-02, DET-PIPELINE-03)

- **D-07 (New PortDataType values + colors):** Extend `PortDataType` union in `pipelineTypes.ts`: `'Image' | 'PointCloud' | 'Pose' | 'IMU' | 'Scalar' | 'Boolean' | 'Config' | 'Detections2D' | 'Detections3D' | 'Tracks'`. Color palette additions (UI-SPEC style, distinct from existing 7):
  - `Detections2D`: `#ff8a65` (coral) — 2D detection data
  - `Detections3D`: `#ec407a` (pink) — 3D OBB data
  - `Tracks`: `#26a69a` (teal) — track envelope
  - Shape: all three use `'circle'` (same as Image/PointCloud/Pose/IMU — reserve diamond/square for Scalar/Boolean/Config).
  New category color: `perception: '#ad1457'` (magenta) — distinct from sensor blue / slam green / merger orange.

- **D-08 (`pipelineStore.ts:101` fix — source-handle dataType inference):** The current hardcoded `dataType: 'PointCloud' as const` at line 101 is the bug DET-PIPELINE-03 calls out. Fix: inside `onConnect`, resolve the source node + source handle and use that port's `dataType`:
  ```ts
  onConnect: (connection) => set((state) => {
    const sourceNode = state.nodes.find((n) => n.id === connection.source);
    const sourcePort = sourceNode?.data.outputs.find((p) => p.id === connection.sourceHandle);
    const dataType: PortDataType = sourcePort?.dataType ?? 'PointCloud';
    return {
      edges: addEdge(
        { ...connection, type: 'animated', data: { fps: 0, dataType } },
        state.edges,
      ) as PipelineEdge[],
      isDirty: true,
    };
  }),
  ```
  The defensive `?? 'PointCloud'` fallback covers the unreachable case where the source node/handle cannot be resolved (shouldn't happen under React Flow's `onConnect` contract, but keeps the edge valid if it does). Regression test `pipelineStore.dataType.test.ts` creates an `sensor_rgbd` + `slam_generic` pair, connects `image_out (Image) → image_in (Image)`, asserts resulting `edge.data.dataType === 'Image'` (not `'PointCloud'`).

- **D-09 (Per-edge type mismatch validation):** Add `findPortTypeMismatches(nodes, edges): ValidationError[]` to `pipelineValidation.ts`. For each edge: look up source output port's `dataType` and target input port's `dataType`. If different AND neither matches a polymorphic wildcard (none today; reserved for a future `Any` type if it ever ships), emit `ValidationError { nodeId: edge.target, message: \`Edge from ${sourceLabel}.${sourcePort.label} (${sourceType}) to ${targetLabel}.${targetPort.label} (${targetType}) has mismatched types\` }`. Hook into `validateGraph()` BEFORE `findMissingOutput` (type errors are more actionable than structural errors). SC#2's "connecting PointCloud to Detections2D input" is exercised by the new `typeMismatch.test.ts`.

### Hot-Swap Apply Path (DET-PIPELINE-05, SC#4)

- **D-10 (Server-side diff in `/api/pipeline/apply`):** The apply handler in `backend/web/pipeline_routes.py::apply_pipeline` computes the new `PipelineConfig`, compares to `app.state.last_applied_pipeline_config`, and decides between hot-apply and restart. Diff policy (strict AND):
  - `topology_digest(nodes_ids, edges_tuples)` of old == new (same node ids, same edges) — any add/remove = restart.
  - `backend_name` (SLAM), `backend_params`, `merger_name`, `merger_params`, `filter_chain`, `tracker_name`, `tracker_params` all unchanged — SLAM/merger/filter/tracker restart paths are NOT wired for hot-swap in Phase 7.
  - Only `detector_name` / `detector_params` / `lifter_name` / `lifter_params` moved.

  On match: call `detector_pool.swap_backend(new_detector_name, new_detector_params)` (when changed) and/or `detector_pool.swap_lifter(new_lifter_name, new_lifter_params)` (when changed) directly, update `app.state.active_detector_backend` + `active_lifter`, update `app.state.last_applied_pipeline_config`, return `{"status": "hot-applied", "changed": ["detector_name", ...]}` (200 OK, no restart overlay). On mismatch: existing path — stash `pending_pipeline_config`, call `command_callback({"action": "restart"})`, return `{"status": "restarting"}`.

  Server-side wins over client-side short-circuit: the diff rules live with `PipelineConfig` in Python, a single source of truth; the client only needs to handle the two-valued response. Also avoids duplicating topology-digest math in TypeScript.

- **D-11 (`DetectorWorkerPool.swap_backend`):** Mirror of `swap_lifter` (existing). Signature: `swap_backend(new_backend_name: str, new_backend_params: dict | None = None) -> None`. Sequence:
  1. Force side-effect import of `src.perception.backends` to ensure the registry is populated.
  2. Construct ONE backend instance per worker via `DetectorRegistry.create(new_backend_name, **new_backend_params)` — OUTSIDE `self._swap_lock`. If `create` raises (unknown name, missing dep), no worker is mutated.
  3. Call `.warmup(dummy_frame)` on each fresh backend — OUTSIDE the lock. Acceptable because the apply request is user-initiated (no 30 Hz submit contention); blocks the response for ≤30 s matching Phase 5 SC#1 warmup budget.
  4. Under `self._swap_lock`: rebind `worker._detector = new_detectors[rid]` for each worker; set `self.backend_name = new_backend_name`. Atomic attribute write under GIL per Phase 4 D-10 pattern.
  5. Emit `detector_swap_complete` WS message via `self._streaming_viz._message_queue` (new envelope type; mirrors `detector_restart_complete` shape but without the restart semantics) so the frontend can dismiss the hot-apply toast and show the new active backend in the DetectorDropdown.

  Does NOT reset worker queue state (retain `drops_since_session_start` for metrics continuity). In-flight `process_frame` calls complete on the OLD backend (Python captured method-bound ref); next submit uses the new one (same documented behavior as `swap_lifter`).

- **D-12 (`last_applied_pipeline_config` lifecycle):** `app.state.last_applied_pipeline_config` is set:
  - At coordinator boot (after first pool construction) — set to the initial config (`PipelineConfig(backend_name="icp", ..., detector_name="yolov11", ..., lifter_name="point_cluster", ..., tracker_name="none")`) so the FIRST apply has a baseline to diff against.
  - On every successful apply (both hot-apply and restart paths) — updated to the newly-applied config.
  - On crash_fallback — updated `detector_name` field to the fallback backend ("yolov11") so a subsequent user-initiated apply that switches back doesn't get mis-diffed as "no change".

  Stored as a `PipelineConfig` dataclass instance directly (no JSON serialization in app.state — the diff is field-level equality).

### Tracker Scope (SC#1 passthrough)

- **D-13 (Ship `TrackerRegistry` + `tracker_none` passthrough in Phase 7):** Phase 7 creates `src/tracking/` package with:
  - `protocol.py::TrackerProtocol` — runtime-checkable with `track(detections_3d: Detections3D) -> Detections3D` method that stamps `track_id` on each `OrientedBox3D`, plus `CAPABILITIES: dict` (framework, produces_stable_ids, license).
  - `registry.py::TrackerRegistry` — mirror of `DetectorRegistry` (class-path loading, `@tracker` decorator, `list()` + `create()` + `available` reporting). Module-scope invariants: NO torch/numpy imports at class-path level; backends register themselves via side-effect import.
  - `trackers/__init__.py` — registers `none` by importing `trackers.none`.
  - `trackers/none.py::NoneTracker` — zero-ops tracker that assigns `track_id = self._counter` (monotonic incrementing int) per detection per frame. No cross-frame association. `capabilities = {framework: "stub", produces_stable_ids: False, license: "MIT"}`. This is explicitly NOT a real tracker — it's a scaffolding that makes the node plumb end-to-end so SC#1 passes today without blocking on Phase 8. ByteTrack slots in Phase 8 as `trackers/bytetrack.py::ByteTrack` with `produces_stable_ids: True`.
  
  Rationale: alternatives considered and rejected:
  - Register NOTHING until Phase 8 — SC#1 fails (TrackerNode cannot be dragged + connected end-to-end since `viz_output.tracks_in` would have no valid source; worse, `TrackerRegistry.list_backends()` returns empty, so `tracker_generic` has zero catalog entries).
  - Skip the tracker from `perception_rgbd` preset — SC#3 is `DetectorNode → Detection3DNode → visualization` (reads the scope literally) which WOULD pass, but SC#1 explicitly names `TrackerNode` as one of three required palette entries, so a tracker node must exist and be connectable.

- **D-14 (Tracker pool integration is Phase 8-deferred):** `DetectorWorkerPool` does NOT run the tracker in Phase 7. The `tracker_none` passthrough lives in the pipeline graph for editor surface completeness, but the per-frame coordinator pump does NOT call `tracker.track(detections_3d)` before emitting the WS envelope. `DetectionExportWriter` (Phase 6) continues to export `track_id=None` — no regression. Phase 8's ByteTrack integration adds the pool-side pump (`worker_pool.py` gains `_tracker` ref + invocation inside `_loop` after `lift` returns, mirroring the lifter invocation). This keeps Phase 7 purely editor-surface work and leaves the runtime tracking contract locked for Phase 8.

### Built-in Preset (DET-PIPELINE-04)

- **D-15 (`perception_rgbd` preset composition — parallel SLAM + perception branches):** `data/presets/builtin/perception_rgbd.json` wires:
  ```
  sensor_rgbd.image_out ─→ slam_icp.image_in
  sensor_rgbd.depth_out ─→ detection3d_generic.depth_in
  sensor_rgbd.image_out ─→ detector_generic.image_in
  detector_generic.detections_2d_out ─→ detection3d_generic.detections_2d_in
  detection3d_generic.detections_3d_out ─→ tracker_generic.detections_3d_in
  tracker_generic.tracks_out ─→ viz_output.tracks_in
  slam_icp.cloud_out ─→ merger_icp_union.cloud_in
  slam_icp.pose_out ─→ merger_icp_union.pose_in
  merger_icp_union.merged_out ─→ viz_output.cloud_in
  slam_icp.pose_out ─→ viz_output.pose_in
  ```
  Node registryNames: `slam_icp` (SLAM backend), `merger_icp_union` (merger), `detector_generic` with `registryName: "yolov11"`, `detection3d_generic` with `registryName: "point_cluster"`, `tracker_generic` with `registryName: "none"`. Name: `"Perception + RGBD"`. builtIn: true. Matches SC#3 literal "MuJoCoBridge → DetectorNode(YOLOv11) → Detection3DNode(PointCluster) → visualization" (the SLAM branch is additive — the PROJECT.md pipeline runs SLAM + perception simultaneously on live scenes).

  Alternatives rejected: perception-only preset (no SLAM branch) — would break the "live 3D map + live detection overlay" dual-output that's the v3.0 value proposition; users loading perception_rgbd would see detections but no map.

- **D-16 (Preset positions — visual layout):** node positions chosen for a clear left-to-right flow, SLAM branch on top row (y=150), perception branch on middle row (y=300), tracker/viz on right column. Exact coords:
  - `sensor_1` (sensor_rgbd) at (50, 225)
  - `slam_1` (slam_icp) at (350, 100)
  - `merger_1` (merger_icp_union) at (650, 100)
  - `detector_1` (detector_generic/yolov11) at (350, 300)
  - `detection3d_1` (detection3d_generic/point_cluster) at (650, 300)
  - `tracker_1` (tracker_generic/none) at (950, 300)
  - `viz_1` (viz_output) at (1150, 200)

### Claude's Discretion

- Exact TypeScript type narrowing on `PortDataType` after the extension (preserve strict exhaustiveness checks in `PORT_COLORS` / `PORT_SHAPES`).
- Frontend ApplyBar toast styling for `hot-applied` response (reuse existing error-banner colors, swap to success green `#4caf50`).
- Hot-apply response keys beyond `status` and `changed` — planner may add `elapsed_ms` or `active_detector`/`active_lifter` echoes for convenience; ApplyBar reads `status` and `changed` only.
- Diff implementation — dataclass equality via `dataclasses.asdict` comparison OR explicit field-by-field — planner picks; both correct, former is terser.
- Node palette section heading copy: "Perception" vs "Object Detection" vs "Perception Nodes" — first is concise and matches SLAM's palette label style.
- Whether to emit `detector_swap_complete` as a new WS type or reuse `detector_restart_complete` with a `reason: "hot_swap"` discriminator — planner picks. Slight preference for new type to keep consumer branches clean.
- `NoneTracker` internal counter reset cadence (per-frame new batch vs session-lifetime monotonic) — session-lifetime monotonic is simpler; `track_id` semantics don't guarantee stability with the passthrough, so either works.

### Folded Todos

None — no pending todos matched Phase 7 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 7 spec
- `.planning/REQUIREMENTS.md` §DET-PIPELINE-01..05 — the 5 requirements this phase must deliver.
- `.planning/ROADMAP.md` §Phase 7 — goal + 5 success criteria (SC#2 literally calls out `pipelineStore.ts:101` bug).
- `.planning/PROJECT.md` — v3.0 vision + "React Flow pipeline editor" as a v2.0 validated requirement this phase extends.

### Prior phase contracts (must not break)
- `.planning/phases/01-detector-api-foundation/01-CONTEXT.md` — DetectorProtocol / Detection3DProtocol / registry invariants (module-scope purity, `outputs_3d_natively` capability key).
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/02-CONTEXT.md` — OBB wire format, pool per-robot isolation, pending_detector_backend REST contract.
- `.planning/phases/03-frontend-picker-and-ui/03-CONTEXT.md` — detectorStore structure, ConfirmModal + RestartOverlay reuse conventions, `input_type` capability reservation (D-05).
- `.planning/phases/04-real-3d-obb-pipeline/04-CONTEXT.md` — D-09/D-10 lifter hot-swap pattern (the template for Phase 7 D-11 `swap_backend`), `POST /api/detectors/lifter-hotswap` surface.
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-CONTEXT.md` — on_backend_crash + warmup budget (≤30 s per SC#1); `detector_restart_complete` emission order.
- `.planning/phases/06-detection-metrics-and-mujoco-gt/06-CONTEXT.md` — `track_id=None` proxy for jitter computation (unchanged by Phase 7's tracker_none scaffold).

### In-tree Python patterns to mirror
- `src/slam/registry.py::SLAMRegistry` + `src/coordination/merge_registry.py::MergeRegistry` — TrackerRegistry shape template.
- `src/perception/registry.py::DetectorRegistry` + `Detection3DRegistry` — registration decorator + availability reporting template.
- `src/perception/worker_pool.py::DetectorWorkerPool.swap_lifter` (lines 269–315) — EXACT template for new `swap_backend` method (D-11).
- `src/perception/worker_pool.py::on_backend_crash` (lines 339–500) — reference for emitting WS envelopes via `_streaming_viz._message_queue`.
- `src/coordination/pipeline_builder.py::PipelineBuilder.build` (lines 234–335) — extend to populate new PipelineConfig fields; `NodeCatalog.get_catalog()` (lines 177–223) — extend to enumerate perception registries.
- `src/main.py` restart block (lines 440–630) — ALREADY has forward-compat hook for `pipeline_config.detector_name` at line 523; add parallel hook for `pipeline_config.lifter_name` at the same level.

### In-tree frontend patterns to mirror
- `frontend/src/utils/nodeDefinitions.ts` (279 lines) — ADD perception entries; EXTEND `PORT_COLORS` / `PORT_SHAPES` / `CATEGORY_COLORS`.
- `frontend/src/utils/pipelineTypes.ts` (72 lines) — EXTEND `PortDataType` + `NodeCategory` unions.
- `frontend/src/utils/pipelineValidation.ts` (111 lines) — ADD `findPortTypeMismatches`; hook into `validateGraph`.
- `frontend/src/stores/pipelineStore.ts` (218 lines) — FIX line 101 `dataType` hardcoding; source-handle lookup pattern.
- `frontend/src/components/pipeline/NodePalette.tsx` (232 lines) — ADD `'perception'` to CATEGORY_ORDER + CATEGORY_LABELS.
- `frontend/src/components/pipeline/ApplyBar.tsx` (171 lines) — EXTEND `POST /api/pipeline/apply` response handling (hot-applied vs restarting branches).

### In-tree REST route patterns
- `backend/web/detector_routes.py::lifter_hotswap` (lines 157–200 referenced via grep) — template for hot-apply direct-call pattern in `pipeline_routes.py`.
- `backend/web/pipeline_routes.py::apply_pipeline` (lines 43–62) — the handler to extend with diff-then-dispatch logic.

### External references
- React Flow `onConnect` docs — https://reactflow.dev/api-reference/types/on-connect (confirms source/sourceHandle are always present in `Connection`).
- Open3D OrientedBoundingBox quaternion conventions — unchanged from Phase 4 (frontend DetectionBoxManager consumes the same wire format).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DetectorWorkerPool.swap_lifter` (`src/perception/worker_pool.py:269-315`) — proven atomic-swap pattern; `swap_backend` clones the structure directly.
- `NodeCatalog.get_catalog` (`src/coordination/pipeline_builder.py:177-223`) — existing registry-enumeration pattern for SLAM/merger; perception additions are ~30 LOC of the same loop.
- `frontend/src/utils/pipelineValidation.ts::findUnconnectedPorts` — iteration pattern for `findPortTypeMismatches` (edge loop with handle lookup).
- `data/presets/builtin/default_icp.json` — exact preset JSON shape; `perception_rgbd.json` extends with two additional branches.
- `backend/web/detector_routes.py::lifter_hotswap` — direct-call-on-pool pattern; `pipeline_routes.py::apply_pipeline` hot-apply branch follows.
- `frontend/src/components/pipeline/NodePalette.tsx:27-45` — category ordering + labels; one-line perception addition.

### Established Patterns
- **Registry-driven generic node + registryName param** — `slam_generic` / `merger_generic` with `registryName` field drives backend selection. `detector_generic` / `detection3d_generic` / `tracker_generic` mirror 1:1.
- **Atomic ref swap under `_swap_lock`** — lifter hot-swap (Phase 4) + crash fallback (Phase 5) both use: construct-outside-lock → rebind-inside-lock → attribute-write atomicity under GIL. `swap_backend` matches.
- **Side-effect registry registration** — all registries populate via `import src.perception.backends` side-effects; tracker follows (`import src.tracking.trackers`).
- **Side-by-side pipeline branches** — `comparison_mode.json` preset (SLAM branches) establishes the multi-branch pattern `perception_rgbd` reuses.
- **Pending config + restart callback** — `app.state.pending_*` + `command_callback({"action": "restart"})`; hot-apply SHORT-CIRCUITS this path instead of replacing it.
- **WS envelope via streaming_viz._message_queue** — all subsystem status messages (SLAM restart, detector crash, lifter hot-swap-equivalent) queue here; `detector_swap_complete` joins.

### Integration Points
- **`pipelineStore.ts:101`** — the literal bug SC#2 calls out; fix location.
- **`apply_pipeline` handler** (`backend/web/pipeline_routes.py:43`) — the single extension point for the hot-apply diff.
- **`main.py:523`** — existing forward-compat hook for `pipeline_config.detector_name`; Phase 7 unblocks this by populating `detector_name` in `PipelineBuilder.build`.
- **`NodePalette.tsx:27`** — `CATEGORY_ORDER` insert point (between `merger` and `filter` conceptually — perception is a post-SLAM/pre-filter chain).
- **`DetectorWorkerPool.__init__`** — `backend_name` + `backend_params` already plumbed; `swap_backend` just rebinds. Warmup path already exists via `warmup_all`.

### Constraints
- No `torch` / `numpy` / `ultralytics` / `transformers` imports at module scope in perception package (Phase 1 thread-config invariant). `src/tracking/` follows the same constraint — `NoneTracker` is pure-Python integer arithmetic (no heavy deps), ByteTrack (Phase 8) uses lazy imports.
- `PipelineConfig` is a dataclass with no serializer; adding fields is source-compatible. `app.state.pending_pipeline_config` is already `Optional[PipelineConfig]`.
- Hot-swap warmup budget: ≤30 s matches Phase 5 SC#1. RT-DETRv2 ONNX first-inference is ~25 s cold, well under. BoxeR subprocess spawn takes longer; documented as "BoxeR hot-swap is slow but still hot — no restart".
- Phase 7 does NOT ship the per-robot heterogeneous backend UI (Phase 8 DET-STRETCH-04). `swap_backend` swaps all workers' detectors uniformly.

</code_context>

<specifics>
## Specific Ideas

- **Category label:** `"Perception"` in `CATEGORY_LABELS` (matches "SLAM Backends", "Mergers" style).
- **Category color:** `#ad1457` (magenta) — distinct from sensor blue / slam green / merger orange / filter purple / parameter brown / output red.
- **Port colors:** `Detections2D: #ff8a65` (coral), `Detections3D: #ec407a` (pink), `Tracks: #26a69a` (teal).
- **`Image` → `Detections2D`** is the canonical detector 2D-output path; `Detections2D + Image (depth) → Detections3D` is the lifter path; `Detections3D → Tracks` is the tracker path.
- **Preset name:** `"Perception + RGBD"` (user-visible); file `perception_rgbd.json` (SC#3 literal).
- **Hot-apply response shape:** `{"status": "hot-applied", "changed": ["detector_name"], "active_detector": "rtdetrv2"}` — `changed` is an informational array for client logging/toasts.
- **Tracker passthrough name:** registry key `"none"`, display `"Passthrough (no tracking)"`.
- **`NoneTracker.track(detections_3d) -> Detections3D`** — stamps `track_id = self._counter; self._counter += 1` on each box, returns the same envelope (clone with stamped boxes). No state beyond the counter.
- **Regression test literal:** `pipelineStore.dataType.test.ts` uses `sensor_rgbd.image_out (Image) → slam_generic.image_in (Image)` and asserts `edge.data.dataType === 'Image'`. This is the minimum reproducer.

</specifics>

<deferred>
## Deferred Ideas

- **ByteTrack tracker implementation** — Phase 8 DET-STRETCH-01 (Phase 7 ships only the registry + `none` passthrough).
- **Per-robot heterogeneous detector dispatch from pipeline graph** — Phase 8 DET-STRETCH-04 (Phase 7's hot-swap is pool-wide uniform).
- **SLAM hot-swap via pipeline apply** — REJECTED for Phase 7; SLAM restart carries spawn positions + map state invalidation that the diff cannot safely skip. Only perception (stateless geometry + stateless detector model refs) hot-swaps.
- **Merger / filter chain hot-swap** — REJECTED for Phase 7; filter chain swap would need a coordinator-side pump rewire not currently factored for live mutation.
- **`Any` / polymorphic port type** — deferred; current types are all nominal. Revisit if a generic Splitter needs to accept any input data type without per-instance typing.
- **Pipeline-editor-driven concurrent restart aggregation** — Phase 3 D-12 ships stacked overlays; aggregate single-message polish remains deferred.
- **Node-level parameter schema live tuning for perception nodes** — deferred; current ParameterPanel targets the ACTIVE detector via `detector_param_update` WS, NOT the graph's detector_generic node. Unifying the two panels is a Phase 8+ polish. For Phase 7, editing `detector_generic.params` in NodeInspector + pressing Apply routes through the hot-apply path.
- **Pipeline diff details in frontend** — the client currently reads only `status`; showing a structured diff ("Detector backend: yolov11 → rtdetrv2") is a polish item.
- **Input type capability (`RGB_TEXT_PROMPT`) → dynamic port set on `detector_generic`** — Phase 3 D-05 reservation; OWLv2 is dropped from v3.0, so no backend exercises it in Phase 7.
- **`detection3d_generic.cloud_in: PointCloud` port** — deferred; lifter protocol takes `slam_cloud` but `point_cluster` and `median_depth` don't need an external cloud source. Add when a lifter needs it.
- **Saving user pipelines that include perception nodes** — existing `POST /api/pipeline/presets` save path already writes arbitrary `nodes + edges`; Phase 7 changes are transparent to save/load.
- **Tracker ParameterPanel** — `tracker_none` has no params; ByteTrack params ship in Phase 8's NodeInspector surface.

### Reviewed Todos (not folded)

None — no pending todos matched Phase 7 scope.

</deferred>

---

*Phase: 07-pipeline-editor-perception-nodes*
*Context gathered: 2026-04-15*
*Discussion log: 07-DISCUSSION-LOG.md*
