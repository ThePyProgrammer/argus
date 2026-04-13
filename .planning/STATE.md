---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: milestone
status: executing
stopped_at: Phase 2 context gathered
last_updated: "2026-04-13T09:48:20.127Z"
last_activity: 2026-04-13
progress:
  total_phases: 8
  completed_phases: 0
  total_plans: 5
  completed_plans: 2
  percent: 40
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-13)

**Core value:** Multiple simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time — with user-selectable SLAM algorithms, detection backends, and live metrics.
**Current focus:** Phase 1 — detector-api-foundation

## Current Position

Phase: 1 (detector-api-foundation) — EXECUTING
Plan: 3 of 5
Status: Ready to execute
Last activity: 2026-04-13

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity (v2.0 historical, for trend reference):**

- Total plans completed: 20 (v2.0)
- Average duration: 6min
- Total execution time: ~145min (includes post-checkpoint ORB-SLAM3 fixes)

**v3.0 Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: —

**By Phase (v2.0 history preserved):**

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

### Decisions (v3.0 — locked pre-roadmap from research)

Full decision log in PROJECT.md. Recent decisions affecting current work:

- **Protocol split:** `DetectorProtocol` (2D) and `Detection3DProtocol` (3D lifter) are separate runtime-checkable Protocols with separate registries; end-to-end backends signal `outputs_3d_natively` and bypass the lifter.
- **Per-robot DetectorWorker:** one worker thread per robot (not a shared drain), single-slot latest-frame queue with newest-wins backpressure; `DetectorWorkerPool = {rid -> DetectorWorker}`.
- **Subprocess bridge:** `SubprocessDetectorBridge` is a distinct class from `SubprocessSLAMBridge` (same shape, separate failure domain); BoxeR is always subprocess-isolated (CC-BY-NC-4.0, 5–30 s/frame, heavy dep cocktail).
- **OBB wire format locked:** `(center[3], half_extents[3], quaternion[4] in xyzw with qw>=0, class_id, class_name, score, track_id)` — server owns all geometry, frontend is a dumb renderer. Inline quaternion construction in backends is forbidden; `OrientedBox3D.to_wire()` is the only path.
- **Default 3D lifter:** `PointClusterLifter` — MAD-filtered depth frustum + DBSCAN + Open3D `compute_oriented_bounding_box(robust=True)`, yaw-only for indoor MVP. `MedianDepthLifter` is a named legacy lifter, not default.
- **Thread config:** moved to `src/_thread_config.py` imported before any torch/numpy import in `main.py`; no module-scope `torch.set_num_threads()` anywhere else.
- **Honest metrics:** `mAP` forbidden in UI without a committed labeled eval set; `center_error_m` + `per_class_recall` against MuJoCo GT via `mj_name2id + data.xpos` is the replacement.
- **Checkpoint pinning:** every HF checkpoint pinned by `revision=<sha>`; `make download-models` pre-fetches weights to `./models/` for offline/CI.

### Decisions (v2.0 — historical reference)

Full v2.0 decision log retained in PROJECT.md. Key architectural precedents v3.0 reuses:

- v2.0: Generic SLAM API over hardcoded ICP — research shows ICP wrong for sparse point clouds
- v2.0: 4 backends: existing ICP (baseline), ORB-SLAM3, OpenVINS, SVO Pro
- v2.0: Pre-session algorithm selection primary; hot-swap deferred to v3.0 (now confirmed deferred further)
- v2.0: SLAM backends produce poses only; dense clouds generated from depth images (sparse/dense mismatch fix)
- [Phase 15-02]: ICP fallback swap placed inside same if-guard as crash_fallback WS emission
- [Phase 15]: slam_restart_complete emitted inside _restart_lock block to guarantee all restart state committed before notification
- [Phase 14]: Kahn's algorithm for DAG cycle detection in PipelineBuilder (reused in v3.0 DET-PIPELINE-03)
- [12-02]: ZMQ PAIR socket with IPC transport for low-latency C++ subprocess communication (mirror for `SubprocessDetectorBridge`)

### Roadmap Evolution

- 2026-03-23: v2.0 roadmap created — 6 phases (8-13), 23 requirements mapped
- 2026-03-23: Phase 14 added: Interactive ComfyUI esque React Flow state graph creation system to customize the end-to-end SLAM pipeline + parameters
- 2026-04-13: v3.0 milestone started — Pluggable Perception & 3D Object Detection, phase numbering reset to 1
- 2026-04-13: v3.0 ROADMAP.md created — 8 phases, 42 requirements, 100% coverage

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 5 (BoxeR) requires live research:** verify `facebook/boxer` repo state, current checkpoint names, and Python 3.12 compatibility via Context7 at phase-planning time. Do not trust April 2026 memory for 2022 CVPR code.
- **Phase 6 requires scene inventory:** 30-min MuJoCo office scene XML class-labeled geom check at phase-planning time (needed for MuJoCo GT extractor).
- **Phase 8 is time-gated:** cut if core phases (1–7) slip.
- CPU-only constraint remains (no NVIDIA GPU). Subprocess isolation + ZMQ transport reused from v2.0 for heavy models (BoxeR).
- BoxeR is CC-BY-NC-4.0 — must be documented in LICENSES.md (DET-MODELS-08).

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

Last activity: 2026-04-13 — v3.0 roadmap created
Stopped at: Phase 2 context gathered
Resume file: .planning/phases/02-per-robot-worker-and-wire-plumbing/02-CONTEXT.md
