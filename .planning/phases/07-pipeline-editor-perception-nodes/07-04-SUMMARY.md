---
phase: 07
plan: 04
subsystem: coordination
tags: [pipeline-builder, node-catalog, perception, registry-driven, validation]
requirements: [DET-PIPELINE-01, DET-PIPELINE-05]
dependency_graph:
  requires:
    - Plan 07-01 (Wave 0 pytest stub for tests/coordination/test_pipeline_builder_perception.py)
    - Plan 07-03 (TrackerRegistry + NoneTracker side-effect registration entry point)
    - src/perception/registry.py (DetectorRegistry + Detection3DRegistry — already populated by Phase 5)
    - src/perception/backends/__init__.py (registers yolov11 via side-effect import)
    - src/perception/lifters/__init__.py (registers point_cluster via side-effect import)
  provides:
    - PipelineConfig dataclass extended with 6 perception fields (detector_name/params, lifter_name/params, tracker_name/params)
    - _REQUIRED_INPUTS prefix table extended with detector_/detection3d_/tracker_ required handles
    - NodeCatalog.get_catalog() emits category='perception' entries for every registered detector / 3D lifter / tracker
    - PipelineBuilder.build() recognizes the three new prefixes, validates registry names, populates perception fields
  affects:
    - Plan 07-05 (frontend PaletteDrawer can now call /node-catalog and render perception section)
    - Plan 07-09 (REST /apply wires graph JSON through PipelineBuilder — now carries perception config)
    - Plan 07-10 (perception_rgbd preset can save/load detector_yolov11 + detection3d_point_cluster + tracker_none)
    - Plan 07-11 (coordinator hot-apply diff reads config.detector_name/lifter_name/tracker_name)
    - main.py line 523 pipeline_config.detector_name hook flips from no-op to live
tech-stack:
  added: [msgpack, pyzmq]  # transitive test-time deps previously absent in this worktree
  patterns:
    - "Registry-driven catalog enumeration (mirrors existing SLAM/merger pattern line-by-line)"
    - "Prefix-based node type validation with available-names ValueError on miss"
    - "Side-effect imports inside build() guarantee registry population at call time"
    - "Python startswith strictness exploited to avoid detector_/detection3d_ aliasing (Pitfall 1 lockdown)"
key-files:
  created: []
  modified:
    - src/coordination/pipeline_builder.py (PipelineConfig +6 fields, _REQUIRED_INPUTS +3 prefixes, NodeCatalog.get_catalog +3 loops, PipelineBuilder.build +3 validators +3 extractors +6 return-args)
    - tests/coordination/test_pipeline_builder_perception.py (Wave 0 pytest.skip stub → 7 green assertions)
decisions:
  - "Extended fixture to register SLAM 'icp' + merger 'icp_union' (plan only listed perception side-effect imports — without SLAM/merger registration the fixture graph fails the slam_icp type-validation branch with 'Unknown SLAM backend: icp'). This mirrors the existing tests/coordination/test_pipeline_builder.py fixture pattern."
  - "Installed msgpack + pyzmq at test time (Rule 3 blocking fix): side-effect import of src.perception.backends transitively loads src.perception.subprocess_bridge which imports both modules at module-scope. Pre-existing environmental issue in this worktree; unrelated to the plan's extension scope."
  - "Kept extraction-default literals in sync with dataclass defaults ('yolov11' / 'point_cluster' / 'none') at both sites rather than delegating to PipelineConfig defaults — matches the existing SLAM/merger extraction pattern (backend_name='icp' / merger_name='icp_union' duplicated at lines 373+379)."
metrics:
  duration: "~6min"
  completed_date: "2026-04-15"
  tasks_completed: 1
  files_created: 0
  files_modified: 2
  tests_passed: "13/13 (7 new + 6 existing regression)"
---

# Phase 07 Plan 04: pipeline-builder-perception-extension Summary

## One-liner

Extends `PipelineBuilder` + `PipelineConfig` + `NodeCatalog` with the three perception node prefixes (`detector_`, `detection3d_`, `tracker_`) so a React Flow graph containing `detector_yolov11` + `detection3d_point_cluster` + `tracker_none` now round-trips through the coordinator as a `PipelineConfig` carrying `detector_name="yolov11"` / `lifter_name="point_cluster"` / `tracker_name="none"` + per-node params — unblocking the hot-apply diff surface (Plan 09) and the coordinator restart block (Plan 11).

## What Shipped

### `src/coordination/pipeline_builder.py` (4 additive extensions, 153 insertions)

1. **`PipelineConfig` +6 fields** (lines 30-36): `detector_name="yolov11"` + `detector_params={}` + `lifter_name="point_cluster"` + `lifter_params={}` + `tracker_name="none"` + `tracker_params={}`. Defaults match CONTEXT D-12 / RESEARCH Pattern Template 7. Existing 5 fields untouched.

2. **`_REQUIRED_INPUTS` +3 prefixes** (lines 179-182):
   - `"detector_": ["image_in"]` — forces the Image source connection that CONTEXT D-03 specifies.
   - `"detection3d_": ["detections_2d_in", "depth_in"]` — forces both 2D detection + depth inputs per CONTEXT D-04.
   - `"tracker_": ["detections_3d_in"]` — forces the 3D detections input per CONTEXT D-05. `_validate_required_connections` now enforces these on Plan 09's REST /apply path.

3. **`NodeCatalog.get_catalog()` +3 enumeration blocks** (appended before final `return catalog`):
   - Side-effect imports `src.perception.backends` + `src.perception.lifters` + `src.tracking.trackers` to guarantee registry population regardless of call order.
   - Enumerates `DetectorRegistry.list_backends()` into `detector_{name}` entries with category='perception', Image+Depth inputs, Detections2D+Detections3D outputs, and — critically — `capabilities` exposed so the frontend can gate on `outputs_3d_natively` per CONTEXT D-15.
   - Enumerates `Detection3DRegistry.list_backends()` into `detection3d_{name}` entries with Detections2D+Depth+Pose inputs and Detections3D output.
   - Enumerates `TrackerRegistry.list_backends()` into `tracker_{name}` entries with Detections3D input and Tracks output (Phase 7 ships exactly 1: tracker_none).

4. **`PipelineBuilder.build()` +3 validators +3 finders +3 extractors +6 return-args**:
   - Validation loop (lines 368-402): three new prefix branches, each doing a lazy `import` + `list_backends()` availability check, raising `ValueError("Unknown {detector backend|3D lifter|tracker}: {name}. Available: [...]")` on miss. Ordered after `slam_`/`merger_` but before the generic `Unknown node type:` fallback. Inline comment documents the Python-startswith strictness that prevents `detector_` from swallowing `detection3d_`.
   - Node finders (lines 416-425): a second loop populates `detector_node` / `detection3d_node` / `tracker_node` mirroring the existing `slam_node`/`merger_node` pattern.
   - Config extraction (lines 449-466): three default-then-override blocks keyed on whether the corresponding node was found. Defaults match `PipelineConfig` defaults exactly.
   - Return statement (lines 478-484): 6 new kwargs passed through to `PipelineConfig(...)`.

### `tests/coordination/test_pipeline_builder_perception.py` (stub → 7 assertions, 149 insertions)

Replaced the Wave 0 `pytest.skip(allow_module_level=True)` with a full test module:

1. **`test_pipeline_builder_populates_perception_fields`** — builds the canonical 7-node perception graph (sensor+slam+merger+detector_yolov11+detection3d_point_cluster+tracker_none+viz) with all required edges wired, asserts all 6 new config fields populate correctly including `detector_params == {"conf_threshold": 0.3}`.

2. **`test_missing_perception_nodes_fall_back_to_defaults`** — SLAM-only graph (no perception nodes), asserts config still carries `detector_name="yolov11"` / `lifter_name="point_cluster"` / `tracker_name="none"`. Proves the hot-apply diff will always see a defined value.

3. **`test_unknown_detector_raises_value_error`** — swaps detector_yolov11 → detector_bogusname AND rewires edges (to prevent the unconnected-required-input guard from firing first), asserts `ValueError("Unknown detector backend: bogusname")`.

4. **`test_unknown_lifter_raises_value_error`** — swaps detection3d_point_cluster → detection3d_bogusname, asserts `ValueError("Unknown 3D lifter: bogusname")`.

5. **`test_unknown_tracker_raises_value_error`** — swaps tracker_none → tracker_bogusname, asserts `ValueError("Unknown tracker: bogusname")`.

6. **`test_node_catalog_lists_perception_entries`** — pulls full catalog, asserts ≥1 detector entry all with category='perception', ≥1 lifter entry all with category='perception', exactly 1 tracker entry (tracker_none), and the yolov11 entry exposes `capabilities["outputs_3d_natively"]` for UI gating.

7. **`test_detector_and_detection3d_do_not_alias`** — Pitfall 1 lockdown: both `detector_yolov11` and `detection3d_point_cluster` are present in the same graph; asserts `lifter_name=="point_cluster"` (NOT `detector_name=="3d_point_cluster"`). Locks the prefix-ordering invariant.

Autouse fixture clears+registers SLAM `icp` + merger `icp_union` (mirrors `tests/coordination/test_pipeline_builder.py` pattern) and side-effect-imports the three perception packages.

## How It Fits (Wiring)

```
React Flow graph JSON
  └─> PipelineBuilder.build()
      ├─ validates detector_/detection3d_/tracker_ node types against registries
      ├─ validates required input handles via _REQUIRED_INPUTS
      └─ returns PipelineConfig(
           detector_name=..., detector_params=...,
           lifter_name=...,   lifter_params=...,
           tracker_name=...,  tracker_params=...
         )
            └─> [Plan 09] hot-apply diff compares old vs new config fields
            └─> [Plan 11] coordinator restart block acts on detector/lifter/tracker changes
            └─> main.py:523 pipeline_config.detector_name hook (previously no-op) now live

/node-catalog REST
  └─> NodeCatalog.get_catalog()
      └─ returns [..., {type:"detector_yolov11", category:"perception", capabilities:{outputs_3d_natively:False,...}, ...}, ...]
            └─> [Plan 05] PaletteDrawer renders "Perception" section keyed on category=='perception'
            └─> [Plan 15] UI gating disables detection3d_* for detectors with outputs_3d_natively=True
```

## Verification

```
$ pytest tests/coordination/test_pipeline_builder_perception.py tests/coordination/test_pipeline_builder.py -v
...
13 passed in 0.04s
```

- 7 new perception assertions green.
- 6 existing SLAM/merger assertions still green (no regression).
- Broader `tests/coordination/` has pre-existing `open3d` / `torch` collection errors in `test_map_merger.py` / `test_merge_registry.py` / `test_merge_strategies.py` / `test_coordinator.py` / `test_voronoi_partitioner.py` — those files are unchanged by this plan and out of scope (SCOPE BOUNDARY).

### Acceptance Criteria

- [x] `grep "detector_name: str" src/coordination/pipeline_builder.py` → 1 hit (line 31)
- [x] `grep "lifter_name: str" src/coordination/pipeline_builder.py` → 1 hit (line 33)
- [x] `grep "tracker_name: str" src/coordination/pipeline_builder.py` → 1 hit (line 35)
- [x] `grep '"detector_": \["image_in"\]'` → 1 hit (line 180)
- [x] `grep '"detection3d_": \["detections_2d_in", "depth_in"\]'` → 1 hit (line 181)
- [x] `grep '"tracker_": \["detections_3d_in"\]'` → 1 hit (line 182)
- [x] `grep "Unknown detector backend:" src/coordination/pipeline_builder.py` → 1 hit (line 375)
- [x] `grep "Unknown 3D lifter:" src/coordination/pipeline_builder.py` → 1 hit (line 387)
- [x] `grep "Unknown tracker:" src/coordination/pipeline_builder.py` → 1 hit (line 399)
- [x] `grep "import src.tracking.trackers" src/coordination/pipeline_builder.py` → 2 hits (catalog loop at 240, build() validator at 394)
- [x] `grep "pytest.skip" tests/coordination/test_pipeline_builder_perception.py` → 0 hits
- [x] 7 PASSED / 0 FAILED / 0 SKIPPED on test_pipeline_builder_perception.py
- [x] 6 PASSED / 0 FAILED on test_pipeline_builder.py (no regression)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended fixture with SLAM + merger registration**

- **Found during:** Task 1, first test run after writing RED-phase tests
- **Issue:** Plan's `_populate_registries` fixture only did the three side-effect imports. Running any test that built `_perception_graph()` (which contains `slam_icp` + `merger_icp_union` nodes) failed with `ValueError: Unknown SLAM backend: icp. Available: []` because `SLAMRegistry` was not populated.
- **Root cause:** The existing `tests/coordination/test_pipeline_builder.py` fixture does explicit `SLAMRegistry.register(...)` + `MergeRegistry.register(...)` calls — SLAM backends are NOT auto-registered via side-effect (their real registration happens in a different orchestrator pathway not exercised at test import time).
- **Fix:** Added `SLAMRegistry._clear()` + `SLAMRegistry.register("icp", ...)` and mirrored for `MergeRegistry` to the perception fixture, plus `yield` + post-test clear. Directly clones the existing test module's pattern.
- **Files modified:** `tests/coordination/test_pipeline_builder_perception.py` (fixture only)
- **Commit:** `52e448e` (fixture was part of the RED commit, caught before GREEN)

**2. [Rule 3 - Blocking] Installed msgpack + pyzmq test-time dependencies**

- **Found during:** Task 1, initial pytest collection
- **Issue:** `import src.perception.backends` (autouse fixture side-effect) transitively loads `src.perception.subprocess_bridge` which imports `msgpack` and `zmq` at module scope. Neither was present in the worktree's Python environment → `ModuleNotFoundError` crashed collection before any test ran.
- **Fix:** `pip install --break-system-packages msgpack pyzmq` (distro-managed Python 3.14; PEP 668 required the override flag). Both packages are standard; msgpack==1.1.2, pyzmq==27.1.0 landed successfully.
- **Impact:** Environmental only — no code changes needed. This is a pre-existing gap in the worktree's dev environment unrelated to Plan 07-04's scope; Phase 5 BoxeR backend skeleton requires both. Added to `tech-stack.added` for traceability.
- **Scope note:** These modules were already imported by the codebase before this plan; plan did not introduce the dependency.

### Deferred Issues

None within scope. Pre-existing `open3d` / `torch` `ModuleNotFoundError` in unrelated coordination tests (`test_map_merger.py`, `test_merge_registry.py`, `test_merge_strategies.py`, `test_coordinator.py`, `test_voronoi_partitioner.py`) are out of scope per SCOPE BOUNDARY — those modules existed unchanged before this plan.

## Threat Flags

None. Plan's threat register (T-07-08/09/10) covered the new surface exhaustively:

- **T-07-08 (Tampering):** Mitigated — `build()` raises `ValueError` with available-names list on unknown detector/lifter/tracker prefixes. Verified by `test_unknown_detector_raises_value_error` + `test_unknown_lifter_raises_value_error` + `test_unknown_tracker_raises_value_error`.
- **T-07-09 (Information Disclosure via install_hint):** Accepted per plan — install_hint is author-controlled at registration time; no user input flows through it.
- **T-07-10 (DoS via catalog balloon):** Accepted per plan — catalog size is linear in registry size (≤10 backends total in Phase 7).

No new security-relevant surface introduced beyond what the plan anticipated.

## Commits

| Hash      | Type     | Subject |
| --------- | -------- | ------- |
| 52e448e   | test     | add failing tests for PipelineBuilder perception extension |
| 8f3a126   | feat     | extend PipelineBuilder for perception nodes (DET-PIPELINE-01/05) |

## Self-Check: PASSED

- `src/coordination/pipeline_builder.py` modified — FOUND (153 insertions, ripgrep confirms all 10 acceptance-criteria greps)
- `tests/coordination/test_pipeline_builder_perception.py` modified — FOUND (0 pytest.skip hits, 7 test functions present)
- Commit `52e448e` — FOUND (`git log --oneline` line 2)
- Commit `8f3a126` — FOUND (`git log --oneline` line 1)
- 13/13 tests green — FOUND (pytest output captured above)
