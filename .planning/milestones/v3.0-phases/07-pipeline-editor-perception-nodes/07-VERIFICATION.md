---
phase: 07-pipeline-editor-perception-nodes
verified: 2026-04-15T19:45:00Z
status: human_needed
score: 5/5 must-haves verified (automated)
overrides_applied: 0
human_verification:
  - test: "SC#3 live OBBs end-to-end in running coordinator"
    expected: "Loading perception_rgbd preset + Apply produces live OBBs in the 3D viewer with a running MuJoCo scene; preset topology asserts already green via contract test but the runtime visual render is browser-rendered Three.js"
    why_human: "Requires running coordinator + frontend + MuJoCo scene end-to-end; vitest + pytest stubs do not exercise the Three.js InstancedMesh render path. All wiring (preset JSON, builder, worker pool, catalog, WS envelope) verified automated."
---

# Phase 7: pipeline-editor-perception-nodes Verification Report

**Phase Goal:** Expose detector, 3D lifter, and tracker stages as first-class React Flow nodes with typed ports, per-edge validation, a built-in preset, and runtime dispatch that swaps backends via node params without coordinator restart.
**Verified:** 2026-04-15T19:45:00Z
**Status:** human_needed (all automated gates green; SC#3 visual render requires live browser)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (merged from ROADMAP SCs + PLAN must-haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User opens pipeline editor, sees `perception` category with DetectorNode/Detection3DNode/TrackerNode and connects typed Detections2D → Detections3D without validation error | VERIFIED | `pipelineStore.connect.perception.test.ts` (3 tests pass); `nodeDefinitions.ts:247-296` defines all three with typed Detections2D/3D/Tracks ports; `NodePalette.tsx:23,34` adds `perception` category + "Perception" label |
| 2 | Connecting PointCloud → Detections2D shows per-edge type-mismatch in `pipelineValidation.ts`; `pipelineStore.ts:101` bug fixed + regression test | VERIFIED | `pipelineValidation.ts:90-119` `findPortTypeMismatches`; `validateGraph:139` hooks it before structural checks; `pipelineStore.ts:102-122` resolves dataType from source handle (no hardcoded `'PointCloud'`); `pipelineStore.dataType.test.ts` (5 regression tests pass); `pipelineValidation.typeMismatch.test.ts` (5 tests pass incl. PointCloud→Image, Detections2D→Detections3D) |
| 3 | `perception_rgbd` preset wires MuJoCoBridge → DetectorNode(YOLOv11) → Detection3DNode(PointCluster) → visualization and produces live OBBs | VERIFIED (contract) / HUMAN_NEEDED (live render) | `data/presets/builtin/perception_rgbd.json` has correct 7-node topology incl. slam_icp, merger_icp_union, detector_yolov11, detection3d_point_cluster, tracker_none; `test_perception_rgbd_preset.py` (3 tests pass — `test_perception_rgbd_preset_builds_cleanly`, `test_perception_rgbd_preset_has_expected_topology`, `test_perception_rgbd_preset_positions_match_ui_spec`). Live OBB rendering through WS pump + Three.js requires human runtime verification. |
| 4 | Changing `backend` on DetectorNode from yolov11 → rtdetrv2 and applying swaps DetectorWorker backend without full coordinator restart (PID stable) | VERIFIED | `worker_pool.py:335-415` `swap_backend` with atomic `_swap_lock` rebind + out-of-lock warmup + `detector_swap_complete` WS emit; `pipeline_routes.py:89-187` server-side diff routes detector-only change to `pool.swap_backend` and returns `{"status": "hot-applied"}` WITHOUT calling `command_callback({"action":"restart"})`; `test_swap_backend.py` 5 tests (atomic_rebind, per_worker_instance_separation, ws_emit, warmup_failure_rollback, unknown_name_raises_before_mutation); `test_pipeline_apply_hot.py::test_detector_backend_change_triggers_hot_apply` asserts command_callback NOT called (PID-stability proxy) |
| 5 | `pipeline_routes.py` maps `detector_generic` node definitions to DetectorWorkerPool entries so node params flow through to worker construction kwargs | VERIFIED | `pipeline_builder.py:31-36` PipelineConfig adds detector/lifter/tracker name+params; `:444-490` PipelineBuilder.build populates all 6 fields from catalog entries; `NodeCatalog.get_catalog:235-284` enumerates `DetectorRegistry.list_backends()` → `detector_{name}` catalog entries; `pipeline_routes.py:89-169` passes `detector_name`+`detector_params` to `pool.swap_backend`; `test_pipeline_builder_perception.py` 7 tests lock this mapping including `unknown_detector_raises_value_error` and `node_catalog_lists_perception_entries` |

**Score:** 5/5 truths verified via automated gates; SC#3 additionally routes to human for live render.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/tracking/protocol.py` | TrackerProtocol runtime-checkable with `track()`, `reset()`, `CAPABILITIES` | VERIFIED | 38 lines, @runtime_checkable, docstring references Phase 2 D-03 wire-format invariant |
| `src/tracking/registry.py` | TrackerRegistry mirror of DetectorRegistry with @tracker decorator | VERIFIED | 132 lines, validates `_REQUIRED_CAPABILITIES` (framework, produces_stable_ids, license), deterministic sort, lazy class-path loading |
| `src/tracking/trackers/none.py` | NoneTracker session-monotonic passthrough | VERIFIED | 55 lines, `@tracker(name="none", display="Passthrough (no tracking)")`, `CAPABILITIES = {framework:"stub", produces_stable_ids:False, license:"MIT"}`, uses `itertools.count` + `dataclasses.replace` (no numpy/torch) |
| `data/presets/builtin/perception_rgbd.json` | 7-node preset with correct topology and positions | VERIFIED | 23-line JSON; all nodes + 11 edges match CONTEXT D-15/D-16; positions match UI-SPEC (sensor@50,225; slam@350,100; merger@650,100; detector@350,300; detection3d@650,300; tracker@950,300; viz@1150,200) |
| `src/coordination/pipeline_builder.py` | PipelineConfig.detector_name/lifter_name/tracker_name + NodeCatalog perception entries | VERIFIED | 6 new fields with defaults; NodeCatalog iterates 3 new registries; _REQUIRED_INPUTS extended with `detector_`, `detection3d_`, `tracker_` prefixes |
| `src/perception/worker_pool.py` | swap_backend mirror of swap_lifter | VERIFIED | `swap_backend(new_backend_name, new_backend_params)` at :335, same `_swap_lock`, out-of-lock construct+warmup, atomic rebind; `detector_swap_complete` WS emit; last_applied_pipeline_config update on crash fallback |
| `backend/web/pipeline_routes.py` | apply_pipeline diff-then-dispatch (hot-apply vs restart) | VERIFIED | 187-line file with `_perception_only_diff` helper at :53, hot-apply branch calls `pool.swap_backend/swap_lifter` directly, writes `last_applied_pipeline_config`, returns `{"status":"hot-applied", "changed":[...], "active_detector":..., "active_lifter":...}`; fallback branch returns `{"status":"restarting"}` |
| `src/main.py` | lifter hook + last_applied_pipeline_config lifecycle | VERIFIED | `:518,530` extracts `pipeline_config.lifter_name`; `:647` updates `last_applied_pipeline_config` on successful restart; `:675` seeds initial config at boot |
| `frontend/src/utils/pipelineTypes.ts` | PortDataType + NodeCategory extensions | VERIFIED | `PortDataType` union adds `Detections2D \| Detections3D \| Tracks` (lines 13-15); `NodeCategory` union adds `perception` (line 35) |
| `frontend/src/utils/nodeDefinitions.ts` | 3 perception node defs + PORT_COLORS + CATEGORY_COLORS | VERIFIED | `detector_generic`, `detection3d_generic`, `tracker_generic` definitions; color entries for all 3 new port types (#ff8a65, #ec407a, #26a69a); category color #ad1457; `viz_output.tracks_in` optional port added |
| `frontend/src/utils/pipelineValidation.ts` | findPortTypeMismatches + validateGraph hook | VERIFIED | 119-line file, function at :90, validateGraph adds mismatches BEFORE structural errors at :139 |
| `frontend/src/stores/pipelineStore.ts` | onConnect source-handle dataType resolution (fix for line 101) | VERIFIED | `:102-122` resolves `sourcePort?.dataType ?? 'PointCloud'` defensive fallback; `:150-218` updateNodeParam hot-swap branch for `backend` key (D-02) |
| `frontend/src/components/pipeline/NodePalette.tsx` | perception category in CATEGORY_ORDER + CATEGORY_LABELS | VERIFIED | `:23` perception inserted; `:34` "Perception" label |
| `frontend/src/components/pipeline/ApplyBar.tsx` | hot-applied response handling + toast | VERIFIED | `:61-68` branches on `body.status === 'hot-applied'`; `:214` "Pipeline updated in place" toast text |
| `frontend/src/components/pipeline/NodeInspector.tsx` | backend dropdown for perception nodes (D-02) | VERIFIED | `:21` reads availableRegistryNodes; `:93-105` renders `<select>` that calls `updateNodeParam(id, 'backend', ...)` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| NodePalette | nodeDefinitions | Groups perception defs into `perception` category | WIRED | CATEGORY_ORDER iteration auto-groups; tested by `nodeDefinitions.perception.test.ts` |
| pipelineStore.onConnect | source port dataType | `state.nodes.find(...).data.outputs.find(...)` | WIRED | 5-test regression `pipelineStore.dataType.test.ts` |
| pipelineValidation.validateGraph | findPortTypeMismatches | Direct call at line 139, before structural checks | WIRED | `typeMismatch.test.ts::validateGraph hooks findPortTypeMismatches BEFORE findUnconnectedPorts` passes |
| NodeInspector backend dropdown | updateNodeParam | onChange → `updateNodeParam(id, 'backend', value)` | WIRED | `NodeInspector.backendDropdown.test.tsx` 7 tests including registryName mutation + parameterSchema replace |
| pipeline_routes.apply_pipeline | DetectorWorkerPool.swap_backend | Direct call in hot-apply branch | WIRED | `test_pipeline_apply_hot.py::test_detector_backend_change_triggers_hot_apply` asserts exactly-once call + no restart |
| pipeline_routes.apply_pipeline | last_applied_pipeline_config | Written on both hot-apply (:169) and restart (main.py:647) | WIRED | `test_hot_apply_updates_last_applied_config` + `test_apply_baseline_sets_last_applied_config` pass |
| swap_backend | StreamingVisualizer._message_queue | `_streaming_viz._message_queue.append({type:"detector_swap_complete", ...})` | WIRED | `test_swap_backend_emits_detector_swap_complete_ws` passes |
| NodeCatalog.get_catalog | DetectorRegistry/Detection3DRegistry/TrackerRegistry | Side-effect imports + `list_backends()` iteration | WIRED | `test_node_catalog_lists_perception_entries` passes |
| PipelineBuilder.build | PipelineConfig fields | Populates detector_name/lifter_name/tracker_name from node types (strips prefix) | WIRED | 7 tests in `test_pipeline_builder_perception.py` |
| main.py restart block | pipeline_config.lifter_name | `active_lifter_name = pipeline_config.lifter_name` at :530 | WIRED | Code inspection confirms forward-compat hook populated |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `perception_rgbd.json` preset | `nodes` + `edges` in PipelineConfig | Loaded via existing preset loader → deserializeGraph → serializeGraph → PipelineBuilder.build | FLOWING (contract-verified) | Contract test loads JSON through PipelineBuilder.build and asserts no ValueError + correct field population |
| DetectorWorkerPool._workers[rid]._detector | detector instance | `DetectorRegistry.create(name, **params)` at swap_backend:387 | FLOWING | Registry dispatch lazily imports backend module; test `test_swap_backend_per_worker_instance_separation` confirms real instances bound |
| NodeInspector backend dropdown | availableRegistryNodes | `setAvailableRegistryNodes` called by App.tsx when `/api/pipeline/node-catalog` returns | FLOWING | Store slice test `backendHotSwap.test.ts::setAvailableRegistryNodes writes the catalog list into the store` |
| NoneTracker.track output | detections_3d.items with track_id stamped | `itertools.count()` monotonic + `dataclasses.replace` | FLOWING | `test_none_tracker_stamps_monotonic_ids` + `preserves_capture_pose_and_timestamp` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Python phase test suite | `pytest tests/tracking/ tests/coordination/test_pipeline_builder_perception.py tests/perception/test_swap_backend.py tests/contract/test_perception_rgbd_preset.py tests/integration/test_pipeline_apply_hot.py -q` | 26 passed in 0.55s, zero skips/fails | PASS |
| Frontend vitest suite | `cd frontend && npm run test -- --run` | 9 files, 41 tests passed in 1.41s | PASS |
| Preset JSON parses + conforms to UI-SPEC positions | `test_perception_rgbd_preset_positions_match_ui_spec` | PASS | PASS |
| PipelineBuilder unknown backend raises | `test_unknown_detector_raises_value_error` + `test_unknown_lifter_raises_value_error` + `test_unknown_tracker_raises_value_error` | PASS | PASS |
| Hot-apply leaves command_callback untouched (PID stability proxy) | `test_detector_backend_change_triggers_hot_apply` | PASS | PASS |
| Topology change triggers restart (not hot-apply) | `test_topology_change_triggers_restart` | PASS | PASS |
| SLAM change triggers restart (hot-swap scope guard) | `test_slam_backend_change_triggers_restart` | PASS | PASS |
| Swap backend warmup-failure rollback preserves pool state | `test_swap_backend_warmup_failure_rollback` | PASS | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DET-PIPELINE-01 | 07-07 | Pipeline editor exposes DetectorNode/Detection3DNode/TrackerNode under `perception` category | SATISFIED | nodeDefinitions.ts 3 defs + NodePalette perception category + 5 tests in nodeDefinitions.perception.test.ts |
| DET-PIPELINE-02 | 07-06, 07-07 | Detections2D/3D/Tracks port data types with distinct colors | SATISFIED | pipelineTypes.ts union + PORT_COLORS (coral/pink/teal) + portColors.test.ts (5 tests) |
| DET-PIPELINE-03 | 07-06, 07-08 | pipelineValidation.ts per-edge type mismatch + pipelineStore.ts:101 bug fix | SATISFIED | findPortTypeMismatches + validateGraph hook + pipelineStore source-handle dataType lookup + 10 regression tests across dataType.test.ts and typeMismatch.test.ts |
| DET-PIPELINE-04 | 07-10 | perception_rgbd built-in preset wires MuJoCoBridge → YOLOv11 → PointCluster → viz | SATISFIED | perception_rgbd.json (7 nodes, 11 edges) + test_perception_rgbd_preset.py (3 tests) |
| DET-PIPELINE-05 | 07-04, 07-05, 07-09, 07-11 | pipeline_routes.py maps detector_generic → DetectorWorkerPool without restart | SATISFIED | PipelineConfig extension + NodeCatalog perception entries + swap_backend + pipeline_routes hot-apply branch + main.py lifecycle + 19 tests across test_pipeline_builder_perception.py, test_swap_backend.py, test_pipeline_apply_hot.py |

All 5 requirements SATISFIED. No ORPHANED requirements detected — REQUIREMENTS.md maps DET-PIPELINE-01..05 exclusively to Phase 7 and plans cover all 5.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None detected in Phase 7 files | — | — |

The `dataType ?? 'PointCloud'` defensive fallback at `pipelineStore.ts:110` and `pipelineSerializer.ts:112` is documented in CONTEXT D-08 as intentional (covers the unreachable React Flow `onConnect` contract edge case); regression test `pipelineStore.dataType.test.ts::falls back to PointCloud defensively when source port cannot be resolved` locks it down.

No TODO/FIXME/placeholder/empty-handler patterns in Phase 7 files.

### Deferred Items (Step 9b)

Known environmental gaps (documented in `deferred-items.md`) that do NOT affect Phase 7 verification:

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | open3d/onnxruntime/msgpack/pyzmq not installed in current env | Environment setup (not a phase) | deferred-items.md explicitly scopes as "Pre-existing on `main` at fc2dc24"; Phase 7 test suite explicitly bypasses by registering backends directly — demonstrated by `test_pipeline_apply_hot.py::_populate_registries` fixture |
| 2 | ByteTrack stable-id tracker implementation | Phase 8 | ROADMAP Phase 8 SC#1: "Running a session with ByteTrack enabled produces stable track_id values across frames" |
| 3 | Tracker pool integration (per-frame coordinator pump) | Phase 8 | CONTEXT D-14: "DetectorWorkerPool does NOT run the tracker in Phase 7. ByteTrack slots in Phase 8 with pool-side pump" |
| 4 | Per-robot heterogeneous detector dispatch from pipeline graph | Phase 8 | ROADMAP Phase 8 SC#4 (DET-STRETCH-04); CONTEXT scope note "Phase 7's hot-swap is pool-wide uniform" |

### Human Verification Required

#### 1. SC#3 live OBBs end-to-end render

**Test:** Boot coordinator against MuJoCo scene with `scene_rotated_chair.xml`, open frontend pipeline editor, load `Perception + RGBD` preset from the Presets dropdown, click Apply, then switch to the 3D viewer panel.

**Expected:** 3D viewer shows live rotating chair mesh from slam_icp reconstruction AND live oriented bounding boxes (rendered via Three.js InstancedMesh + wireOBBToMesh) enclosing the detected chair, updating at ≥3 FPS per Phase 5 SC#1. Camera feed panel shows matching 2D bbox overlay.

**Why human:** Automated suite verifies preset topology (contract test), PipelineBuilder.build consumes it without error, swap_backend wires correctly, and coordinator restart consumes lifter/detector/tracker from PipelineConfig. The visual Three.js render path and live coordinator pump cannot be exercised by vitest/pytest without booting a full stack. The Phase 7 scope explicitly leaves this as the "end-to-end gate" confirming the plumbing is connected.

### Gaps Summary

No automated gaps. All 5 ROADMAP Success Criteria have substantive test coverage that goes beyond task completion — tests assert behavior (atomic rebind, PID-stable command_callback, topology-digest-based diff, type-mismatch validation errors, monotonic track_id stamping) rather than just artifact presence. All 5 DET-PIPELINE-XX requirements map to concrete code+tests.

The phase delivers its goal:
- Three perception nodes with typed ports (verified by 5 tests)
- Per-edge validation with PointCloud→Image / Detections2D→Detections3D coverage (verified by 5 tests)
- Built-in perception_rgbd preset buildable through PipelineBuilder.build (verified by 3 contract tests + 7 PipelineBuilder tests)
- Hot-swap path bypasses restart callback (verified by 6 integration tests including PID-stability proxy + warmup rollback)
- pipeline_routes.py → DetectorWorkerPool mapping with node-param flow-through (verified by full apply-to-swap_backend call chain in test_pipeline_apply_hot.py)

SC#3 live-render gate is routed to human verification because rendering live OBBs in Three.js requires a running coordinator + frontend + MuJoCo — the automated suite verifies every upstream link through the preset+builder+pool but stops short of the browser-rendered mesh.

---

*Verified: 2026-04-15T19:45:00Z*
*Verifier: Claude (gsd-verifier)*
