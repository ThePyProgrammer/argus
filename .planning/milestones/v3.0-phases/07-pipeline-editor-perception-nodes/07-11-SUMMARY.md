---
phase: 07
plan: 11
subsystem: perception
tags: [pipeline, hot-apply, lifecycle, crash-fallback, diff-baseline]
requires: [07-04, 07-05, 07-09]
provides: [last_applied_pipeline_config lifecycle, crash-fallback baseline update]
affects: [src/main.py, src/perception/worker_pool.py]
tech-stack:
  added: []
  patterns:
    - "dataclasses.replace for atomic baseline update"
    - "Post-construction setter for optional app.state ref"
key-files:
  created: []
  modified:
    - src/main.py
    - src/perception/worker_pool.py
decisions:
  - "pipeline_config-driven restart is the ONLY path that writes last_applied_pipeline_config in the restart block — spawn-change / SLAM-restart paths leave the baseline untouched so a prior hot-apply is preserved."
  - "Initial boot seed synthesizes PipelineConfig from app.state.active_* attrs at the last moment before uvicorn.run, NOT from the graph — the graph hasn't been applied yet at boot, and the app.state attrs carry the exact defaults the coordinator will use on first tick."
  - "DetectorWorkerPool._app_state is optional (None in unit-test construction path); on_backend_crash no-ops the baseline update when unwired so the existing 25+ pool tests need no changes."
metrics:
  duration: "~12 min"
  completed: "2026-04-15T11:26:15Z"
---

# Phase 07 Plan 11: last_applied_pipeline_config Lifecycle Summary

Wired the `app.state.last_applied_pipeline_config` lifecycle (D-12) across initial boot, pipeline-driven restart, and crash-fallback so Plan 09's server-side diff always has a real baseline to compare against — without this, every post-restart apply would see `last_applied is None` and force another full restart, defeating SC#4's hot-swap requirement.

## What Shipped

### src/main.py — restart block

1. **Lifter + detector_params hook** (line ~520): extended the existing `pipeline_config.detector_name` hook to also consume `pipeline_config.lifter_name`, `pipeline_config.detector_params`, and `pipeline_config.lifter_params` when present. Mirrors the SLAM/merger override pattern immediately above and gives the restart flow full perception-config parity with the graph.

2. **Baseline update after restart** (after `detector_restart_complete` WS emit): when the restart was pipeline-driven (`pipeline_config is not None`), writes `app.state.last_applied_pipeline_config = pipeline_config` verbatim. Spawn-change / SLAM-only restarts leave the baseline untouched so any prior hot-apply state is preserved.

3. **`detector_pool.set_app_state(app.state)` wire-up** (after `set_streaming_viz`): gives the newly-constructed pool a back-ref to `app.state` so its `on_backend_crash` can keep the baseline consistent with the live detector.

4. **Initial boot seed** (just before `uvicorn.run`): constructs a `PipelineConfig` from `app.state.active_slam_backend` / `active_merge_strategy` / `active_detector_backend` / `active_lifter` (falling back to `"icp"` / `"icp_union"` / `"yolov11"` / `"point_cluster"` / `"none"`). Also seeds `app.state.last_applied_topology_digest = None` so the first apply writes it.

### src/perception/worker_pool.py

1. **`self._app_state = None` in `__init__`** + **`set_app_state(app_state)` setter** mirroring the existing `set_streaming_viz` pattern. Optional, defaults to `None` so every existing pool-construction site (unit tests + pre-wire callers) keeps working.

2. **`on_backend_crash` appends a baseline update** inside the step-3 try block, after the successful atomic ref swap and the `_LOGGER.info("swapped crashed …")` line. Uses `dataclasses.replace(last, detector_name=fallback)` for an atomic rebind of the `last_applied_pipeline_config` field. Guarded by `if last is not None` — a pre-wire caller or a worker whose pool was created before the boot seed ran sees a no-op, preserving the existing crash-fallback behavior.

## Acceptance Criteria — all met

- `grep pipeline_config.lifter_name src/main.py` → 1 hit (OK, ≥1 required)
- `grep pipeline_config.detector_params src/main.py` → 1 hit (OK)
- `grep last_applied_pipeline_config src/main.py` → 5 hits (OK, ≥2)
- `grep last_applied_topology_digest src/main.py` → 2 hits (OK, ≥1)
- `grep last_applied_pipeline_config src/perception/worker_pool.py` → 5 hits (OK, ≥1)
- `grep set_app_state src/perception/worker_pool.py` → 3 hits (OK; includes docstring + method + self assignment)
- `grep detector_pool.set_app_state src/main.py` → 1 hit (OK, ≥1)
- `pytest tests/integration/test_pipeline_apply_hot.py -x -v` → **6 passed**
- `pytest tests/perception/test_swap_backend.py -x -v` → **5 passed**

## Deviations from Plan

### Simplification (not a deviation — plan explicitly allowed)

**Synthesis branch deferred:** The plan offered two forms for the restart-block baseline update: (A) `pipeline_config` verbatim when non-None, (B) a synthesized `PipelineConfig(...)` from individual `pending_*` selections when pipeline_config is None. Chose A-only (the plan's first bullet) because:

- The plan's own design allows B to be omitted: "If pipeline_config is None in the restart block (e.g., restart triggered by spawn change, not apply), last_applied_pipeline_config is NOT overwritten — preserves any prior hot-apply state."
- Preserving a stale baseline across spawn-change restart is safer than speculatively synthesizing a "full config" from possibly-incomplete pending fields that could drift from what the pool actually got constructed with.

Tracked as an **intentional simplification**, not an out-of-scope Rule 3 deferral. If a future milestone needs the synthesized form, the hook is trivially additive.

### No other deviations

- No Rule 1 (bug) fixes — restart block was working; this plan is purely additive.
- No Rule 2 (missing critical) fixes — the threat model (T-07-29 to T-07-31) was already fully covered by the specified GIL-protected writes + except-swallow crash guards; no additional mitigations needed.
- No Rule 3 (blocking) fixes — imports, dataclass shape, and test fixtures all worked as specified on first run.
- No Rule 4 (architectural) escalations.

## Verification

```
pytest tests/integration/test_pipeline_apply_hot.py tests/perception/test_swap_backend.py -x -v
```
Result: **11 passed, 0 failed.**

The broader `pytest tests/` surface has pre-existing collection errors (missing `mujoco` / `open3d` in the dev environment — documented in Plan 07-10 SUMMARY's Notes section). These are untouched by this plan and reproducible on the pre-plan base commit. No regressions attributable to this change.

## Files

- `src/main.py` — 4 edits (lifter hook, set_app_state wire-up, baseline update after WS emit, initial boot seed)
- `src/perception/worker_pool.py` — 3 edits (`_app_state` init, `set_app_state` setter, `on_backend_crash` baseline update)

## Commits

- `3a2040e` feat(07-11): wire last_applied_pipeline_config lifecycle (D-12)

## Self-Check: PASSED

- FOUND: src/main.py
- FOUND: src/perception/worker_pool.py
- FOUND commit: 3a2040e
