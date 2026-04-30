---
phase: 07
plan: 10
subsystem: pipeline-presets
tags: [preset, perception, rgbd, contract-test, DET-PIPELINE-04]
requires:
  - Plan 07-01 (Wave 0 stubs — tests/contract/test_perception_rgbd_preset.py)
  - Plan 07-04 (PipelineBuilder extensions for detector_/detection3d_/tracker_ prefixes)
provides:
  - data/presets/builtin/perception_rgbd.json (built-in preset, 7 nodes + 11 edges)
  - 3 green contract assertions locking preset integrity
affects:
  - GET /api/pipeline/presets listing (new entry)
  - GET /api/pipeline/presets/perception_rgbd (serves preset JSON verbatim)
tech-stack:
  added: []
  patterns:
    - "JSON preset with parallel SLAM + perception branches (mirrors comparison_mode.json topology style)"
    - "Contract test that manually populates SLAMRegistry + MergeRegistry to avoid open3d import (mirrors tests/integration/test_pipeline_apply_hot.py fixture)"
key-files:
  created:
    - data/presets/builtin/perception_rgbd.json
  modified:
    - tests/contract/test_perception_rgbd_preset.py
decisions:
  - "Reuse manual-registry-populate pattern from test_pipeline_apply_hot.py instead of importing src.slam.backends (which pulls open3d). Contract test is about registry membership + node validation, not runtime behavior."
metrics:
  duration_minutes: ~5
  tasks_completed: 1
  files_touched: 2
  completed_date: 2026-04-15
---

# Phase 07 Plan 10: perception_rgbd Built-in Preset Summary

Ship the `Perception + RGBD` built-in preset JSON wiring MuJoCoBridge → parallel SLAM/ICP branch + Detector(YOLOv11) → Detection3D(PointCluster) → Tracker(none) → viz, locked down by 3 contract-test assertions on topology, PipelineBuilder output, and D-16 node positions.

## Completed Tasks

| Task | Name                                                              | Commit   |
| ---- | ----------------------------------------------------------------- | -------- |
| 1    | Create perception_rgbd.json preset + fill contract test assertions | 6252276  |

## What Was Built

### data/presets/builtin/perception_rgbd.json
Brand-new built-in preset, structurally identical to existing presets (`{name, nodes, edges}`). Contains:
- **7 nodes**: `sensor_1 (sensor_rgbd)`, `slam_1 (slam_icp)`, `merger_1 (merger_icp_union)`, `detector_1 (detector_yolov11)`, `detection3d_1 (detection3d_point_cluster)`, `tracker_1 (tracker_none)`, `viz_1 (viz_output)`.
- **11 edges** forming three flows:
  - SLAM branch: `sensor_1.image_out → slam_1.image_in`, `slam_1.{cloud,pose}_out → merger_1.{cloud,pose}_in`, `merger_1.merged_out → viz_1.cloud_in`.
  - Cross-branch pose: `slam_1.pose_out → viz_1.pose_in`.
  - Perception branch: `sensor_1.image_out → detector_1.image_in`, `sensor_1.depth_out → detector_1.depth_in`, `detector_1.detections_2d_out → detection3d_1.detections_2d_in`, `sensor_1.depth_out → detection3d_1.depth_in`, `detection3d_1.detections_3d_out → tracker_1.detections_3d_in`, `tracker_1.tracks_out → viz_1.tracks_in`.
- Positions locked exactly per CONTEXT D-16 (SLAM on top row y=100, perception on middle row y=300, viz at right column (1150,200)).

### tests/contract/test_perception_rgbd_preset.py
Replaced the Wave 0 skip stub with 3 active assertions:
1. **`test_perception_rgbd_preset_builds_cleanly`** — Loads the JSON, invokes `PipelineBuilder().build`, asserts `PipelineConfig(detector_name='yolov11', lifter_name='point_cluster', tracker_name='none', backend_name='icp', merger_name='icp_union')`.
2. **`test_perception_rgbd_preset_has_expected_topology`** — Asserts 7 nodes with expected ids, 11 edges, every edge endpoint resolves to a known node id, all edges have sourceHandle/targetHandle keys.
3. **`test_perception_rgbd_preset_positions_match_ui_spec`** — Asserts the exact (x, y) coordinates of all 7 nodes per CONTEXT D-16.

The autouse fixture `_populate_registries` manually registers `icp` in `SLAMRegistry` and `icp_union` in `MergeRegistry` without importing `src.slam.backends` (avoids open3d dependency), and imports the perception/lifter/tracker packages whose `__init__` triggers decorator registration. Mirrors the proven pattern in `tests/integration/test_pipeline_apply_hot.py`.

## Verification

```
$ pytest tests/contract/test_perception_rgbd_preset.py -x -v
tests/contract/test_perception_rgbd_preset.py::test_perception_rgbd_preset_builds_cleanly PASSED
tests/contract/test_perception_rgbd_preset.py::test_perception_rgbd_preset_has_expected_topology PASSED
tests/contract/test_perception_rgbd_preset.py::test_perception_rgbd_preset_positions_match_ui_spec PASSED
========================= 3 passed, 1 warning in 0.04s =========================
```

Acceptance criteria checks:
- `jq '.nodes | length, .edges | length' perception_rgbd.json` → `7 11` ✓
- `jq -r '.name' perception_rgbd.json` → `Perception + RGBD` ✓
- `grep -c detector_yolov11` → 1 ✓
- `grep -c detection3d_point_cluster` → 1 ✓
- `grep -c tracker_none` → 1 ✓
- `grep -c tracks_in` → 1 ✓
- `grep -c pytest.skip` in contract test → 0 ✓
- `pytest ... -v` → 3 PASSED ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended `_populate_registries` fixture to avoid empty SLAMRegistry/MergeRegistry**

- **Found during:** Task 1 verification — initial test run failed with `ValueError: Unknown SLAM backend: icp. Available: []`.
- **Issue:** The plan's fixture body only imported perception/lifter/tracker packages. `PipelineBuilder.build` also validates `slam_` and `merger_` prefixed nodes against their respective registries, which start empty.
- **Attempted first fix:** `import src.slam.backends` — failed because `src.slam.backends.icp_backend` imports `open3d` via `src.slam.slam_pipeline`, and the current dev environment has no open3d installed.
- **Final fix:** Mirror the manual-register pattern from `tests/integration/test_pipeline_apply_hot.py`: `SLAMRegistry.register("icp", ...)` + `MergeRegistry.register("icp_union", ...)` with class-path strings (never resolved in `build`). Class-path resolution only happens at runtime instantiation, not during preset validation.
- **Files modified:** `tests/contract/test_perception_rgbd_preset.py`
- **Commit:** 6252276

This was a straightforward blocking-issue auto-fix; no architectural decision. The integration test (`tests/integration/test_perception_rgbd_end_to_end.py`) remains skip-stubbed per Plan 01, as the plan explicitly allows.

## Threat Flags

None. The only surface touched is adding a JSON file to `data/presets/builtin/`, which goes through the existing `load_preset` route (path-traversal-safe per T-07-27 mitigation). No new network endpoints, no new auth paths, no schema changes.

## Self-Check: PASSED

- `data/presets/builtin/perception_rgbd.json` — FOUND.
- `tests/contract/test_perception_rgbd_preset.py` — modified (no longer contains `pytest.skip`).
- Commit `6252276` — FOUND in `git log`.
- 3/3 contract tests pass.
