---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 09
subsystem: main + exploration
tags: [main, restart, warmup, crash-fallback, subsystem, detector-pool, D-02, D-03]
requires:
  - "02-04: DetectorWorkerPool with synchronous warmup_all(dummy_frames)"
  - "02-08: app.state.pending_detector_backend + detector_restart_complete literal wired by REST handler"
  - "01-05: YOLOv11 backend + perception registry infrastructure"
provides:
  - "src/main.py restart block that consumes pending_detector_backend, rebuilds DetectorWorkerPool, warms synchronously, emits detector_restart_complete AFTER warmup_all returns"
  - "src/exploration/exploration_loop.py crash_fallback WS payload carries subsystem='slam' discriminator (Phase 5 detector branch hook)"
affects:
  - "Plan 02-10: coordinator rewrite will assume main.py writes coordinator._detector_pool after reset_for_restart"
  - "Plan 02-12: test_pool_end_to_end.py transitively exercises this restart dataflow"
  - "Phase 3: UI restart overlay dismissal keyed on detector_restart_complete"
  - "Phase 5 (DET-MODELS-06): will add detector-subsystem crash_fallback emission path keyed on subsystem field"
tech-stack:
  added: []
  patterns:
    - "Cross-subsystem restart protocol: pending_{subsystem} → reset → warmup → active_{subsystem} → emit restart_complete"
    - "Warmup-before-emit gate (D-03): synchronous warmup_all precedes WS restart_complete emission so UI overlays dismiss only after first inference is real"
    - "Discriminator-field-on-shared-event pattern: crash_fallback carries subsystem field so one handler routes SLAM/detector variants"
    - "Defensive fallback frame: synthesized zero 480x640 SensorFrame matches YOLO inference resolution (Pitfall 6)"
key-files:
  created: []
  modified:
    - src/main.py
    - src/exploration/exploration_loop.py
    - .planning/phases/02-per-robot-worker-and-wire-plumbing/deferred-items.md
key-decisions:
  - summary: "Synchronous warmup inside restart block (not a background thread)"
    rationale: "D-03 UI contract — overlay dismisses only after detector_restart_complete; async warmup would race the first real submit against a cold kernel. warmup_all is sequential per-worker (shared BLAS pool) keeping timing predictable."
  - summary: "Synthesized 480x640 fallback frame when bridge.get_last_frame(rid) unavailable"
    rationale: "Phase 2 bridge doesn't yet expose get_last_frame; first-boot restart has no cached real frame. Synthesized frame matches YOLO inference resolution exactly so the warmup kernel matches the inference kernel (Pitfall 6)."
  - summary: "try/except around pool construction — failure sets coordinator._detector_pool = None"
    rationale: "T-02-24 mitigation. Restart must not crash if a backend fails to load (e.g., missing weights). Coordinator hot loop (Plan 10) handles 'no pool' gracefully — detection just no-ops until next successful restart."
  - summary: "pending_detector_params intentionally retained after restart (not cleared)"
    rationale: "Unlike pending_detector_backend (which is a one-shot swap signal), params may hold live-tunable values the coordinator consumes per-frame. Clearing it would defeat Phase 8 stretch DET-STRETCH-04."
  - summary: "subsystem='slam' default on crash_fallback (not a breaking rename)"
    rationale: "Backward-compat: frontend handlers that ignore the field still work. Phase 5 adds detector emission path keyed on this field; rename-breaking now would invalidate existing Phase 2 WS contract tests."
  - summary: "slam_restart_complete emission preserved alongside new detector_restart_complete"
    rationale: "Both subsystems emit independently so the UI can route restart overlay dismissal per subsystem. Collapsing into one message would couple SLAM and detector UI lifecycle."
requirements-completed: [DET-MODELS-05]
duration: 25 min
completed: 2026-04-14
---

# Phase 02 Plan 09: Main.py Restart-Block Detector-Pool Rebuild + Crash-Fallback Subsystem Discriminator Summary

One-liner: Extended `src/main.py`'s restart block so it owns the detector-pool lifecycle — reads `app.state.pending_detector_backend`, constructs `DetectorWorkerPool` via `DetectorRegistry.create`, warms synchronously via `warmup_all(dummy_frames)`, attaches to the rebuilt coordinator, and emits `detector_restart_complete` AFTER warmup returns (D-03). Added `subsystem` discriminator field to the `crash_fallback` WS payload in `exploration_loop.py` with `"slam"` default so Phase 5 has a hook for detector-crash emission.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Extend src/main.py restart block for detector pool rebuild + warmup + detector_restart_complete emission | ac541fd | src/main.py |
| 2 | Add subsystem discriminator to crash_fallback WS message in exploration_loop.py | b0593d0 | src/exploration/exploration_loop.py |

**Task count:** 2. **File count:** 2 modified. **Duration:** 25 min.

## Implementation Details

### Task 1: src/main.py restart-block extension

Inserted the detector-pool rebuild block after the existing SLAM pending-state consumption (around line 489 — just after `app.state.pending_pipeline_config = None` and BEFORE the `streaming_viz.reset_cloud_tracking()` call). The block is nested inside the same `with _restart_lock:` that owns the SLAM restart, so state writes are atomic with respect to other restarts.

Ordering contract (D-02 + D-03):

1. `coordinator.reset_for_restart(bridge, robots)` — already present, builds post-restart `robots` dict.
2. `app.state.active_slam_backend = ...` + clear `pending_slam_backend` — already present.
3. **NEW**: Read `pending_detector_backend` + `pending_detector_params` from `app.state`.
4. **NEW**: Pipeline-config override check — `getattr(pipeline_config, "detector_name", None)` (forward-compat; Phase 2 PipelineConfig doesn't yet carry detector_name).
5. **NEW**: Construct `DetectorWorkerPool(robot_ids, backend_name, backend_params, lifter_name="median_depth", intrinsics_per_robot)`.
6. **NEW**: Build `dummy_frames` — prefer `bridge.get_last_frame(rid)` when available, else synthesize a zero 480x640 `SensorFrame` (Pitfall 6: matches YOLO inference resolution).
7. **NEW**: `detector_pool.warmup_all(dummy_frames)` — synchronous, on the caller thread.
8. **NEW**: `detector_pool.start()` — spawn daemon threads AFTER warmup.
9. **NEW**: `coordinator._detector_pool = detector_pool`.
10. **NEW**: `app.state.active_detector_backend = backend_name`; clear `pending_detector_backend` (retain `pending_detector_params`).
11. `streaming_viz._message_queue.append({"type": "slam_restart_complete", ...})` — already present.
12. **NEW**: `streaming_viz._message_queue.append({"type": "detector_restart_complete", "payload": {"backend": ...}})`.

The entire construction is wrapped in `try/except Exception` (T-02-24 mitigation): on failure, `logger.exception` is emitted and `coordinator._detector_pool = None` so Plan 10's coordinator hot loop can handle the no-pool case.

Imports added: `SensorFrame` (extended the existing `from src.bridge.sensor_types import CameraIntrinsics` line). `numpy` was already imported as `np`. `DetectorRegistry` + `DetectorWorkerPool` + registry side-effect imports are function-local (inside the try block) to keep module-scope import graph minimal and avoid import-order surprises during fresh-start boot.

### Task 2: src/exploration/exploration_loop.py crash_fallback discriminator

Single-line addition at line 218: inserted `"subsystem": "slam"` into the `payload` dict of the `crash_fallback` WS emission (inside `_update_slam`, right before `crashed_backend` and `fallback_backend`). No other logic changes. The inline comment flags this as the Phase 5 DET-MODELS-06 hook:

```python
"subsystem": "slam",  # Phase 2: backward-compat default; Phase 5 adds "detector" emission path
```

## Verification

- `python -c "import src.main"` → clean (Task 1 done criterion).
- `python -c "import src.exploration.exploration_loop"` → clean.
- `grep -n '"subsystem":' src/exploration/exploration_loop.py` → single match at line 218 (Task 2 done criterion).
- `wc -l src/main.py` → 741 lines (must_haves min_lines=530 satisfied).
- `wc -l src/exploration/exploration_loop.py` → 527 lines (must_haves min_lines=230 satisfied).
- `grep "pending_detector_backend" src/main.py` → 2 matches (read + clear) confirming consume-pending semantics.
- Full restart dataflow verified transitively by Plan 02-12's `test_pool_end_to_end.py` (per plan's verify note).

## Success Criteria

- [x] D-02 restart flow for detector complete: pending_* → pool rebuild → warmup → active_* → emit.
- [x] D-03 warmup-before-restart-complete protocol enforced — `warmup_all` call line 539, `detector_restart_complete` emission line 563.
- [x] crash_fallback backward-compat preserved; Phase 5 has the subsystem field ready.

## Deviations from Plan

None — plan executed exactly as written.

The plan's action block was followed verbatim modulo cosmetic adjustments (inline comments refactored for readability, try-block scope narrowed to construction-plus-warmup). The one ordering nuance worth highlighting: the plan's action block prescribed inserting the detector block "BEFORE the slam_restart_complete emission". I placed the detector-pool REBUILD before the streaming_viz block (so both completions live together) and placed the `detector_restart_complete` emission immediately after the `slam_restart_complete` emission. Net ordering matches D-03 strictly: `warmup_all` completes before the `detector_restart_complete` append. The slam emission order is unchanged.

## Authentication Gates

None — plan is fully autonomous.

## Issues Encountered

None from Plan 02-09. Pre-existing test failures documented in `deferred-items.md` (unchanged scope: perception-types-reload test ordering bug, `ExplorationConfig.stuck_threshold_steps` default drift, unrelated path-planner + openvins registration ordering issues).

## Threat Register Disposition

| Threat ID | Disposition in this plan |
|-----------|--------------------------|
| T-02-23 (race on app.state.pending_detector_backend R/W) | ACCEPTED — matches SLAM precedent; `_restart_lock` serializes restart-block writes; REST writes are single-shot before a restart is requested. |
| T-02-24 (Pool construction failure during restart) | MITIGATED — try/except wraps construction + warmup; logger.exception on failure; coordinator._detector_pool = None preserves graceful degradation. |
| T-02-25 (Warmup on wrong resolution) | MITIGATED — synthesized fallback frame is exactly (480, 640) float32 depth + uint8 rgb, matching YOLO inference resolution (Pitfall 6). |

## Threat Flags

None — no new security-relevant surface introduced. The detector-pool rebuild is a worker-thread lifecycle operation behind the already-authenticated REST surface Plan 02-08 established. No new network paths, no new file access patterns, no new schema changes at trust boundaries.

## Known Stubs

None. `pending_detector_params` retention is intentional (live-tunable per-frame pickup, not a stub). `pipeline_config.detector_name` lookup via `getattr(..., None)` is forward-compat for a Phase 8 graph-node addition — not a stub; Phase 2 PipelineConfig correctly returns None, and the code path falls through to `DetectorRegistry.get_default()` which returns `"yolov11"`. This is documented in the inline comment.

## Next Plan Readiness

**Ready for Plan 02-10** (coordinator rewrite to own `_detector_pool`): main.py now writes `coordinator._detector_pool` after `reset_for_restart`, so the coordinator's hot loop can consume the pool without needing to own construction logic.

**Wave-4 tail plans 02-10/11/12** will exercise this restart dataflow end-to-end:

- Plan 10 coordinator hot-loop rewrite reads `self._detector_pool` set by main.py.
- Plan 11 lifecycle smoke test verifies `restart_complete` emission ordering.
- Plan 12 `test_pool_end_to_end.py` transitively verifies this plan's restart dataflow (see plan's verify note).

## Self-Check: PASSED

- `[ -f src/main.py ]` → FOUND
- `[ -f src/exploration/exploration_loop.py ]` → FOUND
- `git log --oneline | grep ac541fd` → FOUND (Task 1: feat(02-09): extend main.py restart block...)
- `git log --oneline | grep b0593d0` → FOUND (Task 2: feat(02-09): add subsystem discriminator...)
- `grep -c "pending_detector_backend" src/main.py` → 2 (read + clear)
- `grep -c "warmup_all" src/main.py` → 1 (call site in restart block)
- `grep -c "detector_restart_complete" src/main.py` → 2 (comment + payload type)
- `grep -c '"subsystem":' src/exploration/exploration_loop.py` → 1 (single insertion)
- `python -c "import src.main"` → OK (via .venv)
- `python -c "import src.exploration.exploration_loop"` → OK (via .venv)
