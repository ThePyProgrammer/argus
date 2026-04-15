---
phase: 06-detection-metrics-and-mujoco-gt
plan: 04
subsystem: metrics
tags: [perception, metrics, tracker, python, tdd]

# Dependency graph
requires:
  - phase: 06
    plan: 02
    provides: "Wave 0 skip-stub at tests/metrics/test_detection_metrics_tracker.py — named-successor points here"
provides:
  - "DetectionMetricsTracker class (src/metrics/detection_metrics_tracker.py) consumable by Plan 08 (WebStreamingViz wiring) and Plan 10 (coordinator pump)"
  - "get_stats_payload() shape with 3 top-keys (detection_metrics / detection_history / detection_gt_metrics) — Plan 08 payload consumer contract"
  - "record_gt_match(robot_id, class_name, center_err_m, matched) + reset_gt() — Plan 05 MuJoCoGTExtractor calls this"
affects:
  - 06-08 WebStreamingViz extension (DetectionMetricsTracker composed into _update_stats)
  - 06-10 coordinator pump (record_frame called per tick per robot)
  - 06-05 MuJoCoGTExtractor (emits record_gt_match calls into this tracker)
  - 06-11 frontend metricsStore (receives detection_metrics + detection_gt_metrics keys)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Parallel-sibling tracker (no inheritance) — mirrors MetricsTracker shape but keeps a separate per_robot dict + separate gt_state dict per CONTEXT D-01"
    - "Isolated GT state dict enables surgical reset_gt() without destroying SC#1 live history continuity"
    - "Nearest-neighbor jitter as degradable proxy for track_id (Phase 8 ByteTrack will swap the matching step only — jitter stddev API stable)"
    - "Per-class jitter history deque (maxlen=30) reseeds on NN-gate failure instead of polluting history with cross-class distances"

key-files:
  created:
    - src/metrics/detection_metrics_tracker.py
  modified:
    - tests/metrics/test_detection_metrics_tracker.py

key-decisions:
  - "D-01 enforced: zero inheritance — `grep -cw MetricsTracker` on the new module returns 0 (docstrings refer to it as 'the SLAM tracker' / 'src/metrics/metrics_tracker.py')"
  - "D-02 enforced: record_frame takes (robot_id, sim_now, latest, inspect, backend_metrics) — backend p50/p95 flow through verbatim (no in-tracker percentile recomputation)"
  - "D-03 enforced: 0.5m NN gate per class, maxlen=30 history, per-class stddev aggregated via max() across classes for the single jitter_m UI value"
  - "D-09 enforced via record_gt_match: caller (Plan 05 MuJoCoGTExtractor) owns the 1.0m match gate; this tracker just records (center_err_m, matched) outcomes. Keeps matching policy single-source"
  - "Pitfall 4 enforced: freshness = max(0, sim_now - capture_timestamp) — NO time.time() reads in the tracker (sim-clock purity)"
  - "Test file uses local FakeOBB/FakeDetections3D dataclasses instead of importing src.perception.types — keeps the unit test decoupled from Phase 2 wiring"
  - "center_error_m returned as Python None (not NaN, not 0.0) before any matches — UI (Plan 11) renders '—' on None per SC#2 UI-SPEC"
  - "per_class_recall returned as 0.0 (not None) when frames_observed == 0 — avoids UI having to distinguish 'never observed' from 'observed, no matches'"

patterns-established:
  - "Parallel tracker class with zero shared state — cleaner than mixins when metrics subsystems have disjoint inputs"
  - "Separate internal dict for GT state lets `reset_gt()` be surgical without violating SC#1 history continuity"

requirements-completed: [DET-METRICS-01]

# Metrics
duration: 8min
completed: 2026-04-15
---

# Phase 6 Plan 4: DetectionMetricsTracker Implementation Summary

**Per-robot detection-metrics tracker with ring buffers (p50/p95, det/frame, confidence, queue, freshness, NN jitter) plus SC#2 GT-match accumulation (center_error_m + per_class_recall) — replaces the Wave 0 skip-stub with 7 passing unit tests**

## Performance

- **Duration:** ~8 min (RED commit → GREEN commit → ACs verified)
- **Started:** 2026-04-15T00:00:00Z (worktree reset to base)
- **Completed:** 2026-04-15T00:08:00Z
- **Tasks:** 1 (single TDD-flagged task with 7 behavior specs)
- **Files created:** 1
- **Files modified:** 1 (skip-stub replaced in full)

## Accomplishments

- Shipped `src/metrics/detection_metrics_tracker.py::DetectionMetricsTracker` — 282 lines (exceeds min_lines=180), parallel sibling of SLAM tracker with zero inheritance
- Implemented all 7 live-metric keys (`inference_ms_p50`, `inference_ms_p95`, `detections_per_frame`, `mean_confidence`, `queue_depth`, `freshness_s`, `jitter_m`) + 5 history rings (deque maxlen=history_size)
- Implemented `record_gt_match(robot_id, class_name, center_err_m, matched)` + `reset_gt()` for SC#2 delivery per CONTEXT D-09
- Emits `detection_gt_metrics` top-key in `get_stats_payload()` — empty dict until first match, per-robot per-class `{center_error_m, per_class_recall}` thereafter
- Replaced Wave 0 skip-stub at `tests/metrics/test_detection_metrics_tracker.py` with 7 passing tests (274 lines, exceeds min_lines=160): p50/p95 propagation, ring eviction, empty-state/no-NaN, NN jitter gate, payload shape, GT accumulation, `reset_gt` isolation
- `pytest tests/metrics/test_detection_metrics_tracker.py -v` → `7 passed, 1 warning in 0.03s`
- All 10 acceptance criteria from plan verified green (class count, NO MetricsTracker word-ref, decision IDs ≥2, record_gt_match/reset_gt presence, detection_gt_metrics count ≥2, stub removal, empty-state smoke)

## Task Commits

1. **Task 1 RED (failing tests)** — `848f4ab` (test): replace Wave 0 stub with 7 real tests; RED verified via `ModuleNotFoundError`
2. **Task 1 GREEN (impl + test helper fix)** — `bb7ada2` (feat): `DetectionMetricsTracker` class + fix of `zip` argument-order bug in the test helper (`classes/scores` unpacking was swapped). All 7 tests pass.

_No metadata commit by this executor — parent orchestrator owns STATE.md / ROADMAP.md updates per parallel-execution contract._

## Files Created / Modified

### Created

- `src/metrics/detection_metrics_tracker.py` (282 lines) — `DetectionMetricsTracker` with:
  - `__init__(history_size=60)` — per-robot live dict + isolated GT-state dict
  - `record_frame(robot_id, sim_now, latest, inspect, backend_metrics)` — ingest one coordinator tick
  - `record_gt_match(robot_id, class_name, center_err_m, matched)` — SC#2 / D-09 accumulator
  - `get_stats_payload()` → 3 top-keys (`detection_metrics`, `detection_history`, `detection_gt_metrics`)
  - `reset()` / `reset_gt()` — full vs. surgical clear
  - Module-level constants: `_JITTER_GATE_M=0.5` (D-03), `_JITTER_HISTORY=30` (D-03), `_GT_ERR_RING_LEN=60` (D-09)

### Modified

- `tests/metrics/test_detection_metrics_tracker.py` (274 lines) — Wave 0 skip replaced with 7 real tests using local `FakeOBB` / `FakeDetections3D` dataclasses (decoupled from `src.perception.types`)

## Decisions Made

- **Docstrings avoid bare-word `MetricsTracker`** — acceptance criterion `grep -cw 'MetricsTracker' == 0` is strict; references use the path `src/metrics/metrics_tracker.py` or the phrase "the SLAM tracker" instead. Clarity preserved without violating the invariant.
- **Jitter aggregation = max across classes** — per D-03 step 3, one number per robot per frame. When no classes have ≥2 samples, `jitter_m` retains its previous value (no oscillation to 0).
- **NN-gate failure re-seeds the class history** — per D-03 step 2; avoids polluting stddev with cross-instance distances. A class-track "teleport" restarts the history, so stddev reflects the new instance only.
- **`record_gt_match(matched=False, center_err_m=None)` bumps `frames_observed` but NOT `matched_count`** — recall denominator grows on unmatched detections (false positives dilute recall numerator). Matches CONTEXT D-09's "false positive contributes to frames_observed".
- **`center_error_m is None` before any matches; `per_class_recall == 0.0` when `frames_observed == 0`** — distinct sentinels so UI can render "—" for unknown vs. "0.0" for "observed but all misses".
- **`reset()` clears both live AND GT**; **`reset_gt()` clears ONLY GT** — latter preserves SC#1 history continuity. Callers who want a surgical reset between eval windows use `reset_gt`; a cloud-tracking reset still uses `reset`.

## Deviations from Plan

### Auto-fixed issues

**1. [Rule 1 — Bug] Fixed `zip` argument-order bug in test helper `_make_det`**

- **Found during:** Task 1 GREEN verification run (4 of 7 tests raised `ValueError: could not convert string to float: 'chair'`)
- **Issue:** The helper did `for c, s, cn in zip(centers, classes, scores)` — unpacking `s` from the second arg (which is `classes`) and `cn` from the third (which is `scores`). Swap was silent because `zip` tuples are positional.
- **Fix:** Renamed loop vars to `for c, cn, s in zip(centers, classes, scores)` — unpacks in the declared positional order. No production-code change; test-only.
- **Files modified:** `tests/metrics/test_detection_metrics_tracker.py`
- **Commit:** `bb7ada2` (bundled with GREEN impl — the zip bug did not mask the RED signal, since RED was `ModuleNotFoundError` at import time)

### Docstring normalization (not a deviation — precision tweak)

- Plan's `<action>` sample used the phrase "Parallel to src/metrics/metrics_tracker.py::MetricsTracker" in the module docstring. AC #2 requires `grep -cw 'MetricsTracker' == 0` on the new module. I rewrote the docstring to reference the path (`src/metrics/metrics_tracker.py`) and the phrase "the SLAM tracker" — satisfies AC while preserving the cross-reference.

## Authentication Gates

None.

## Known Stubs

None. All methods are fully implemented; no placeholders; empty-state defaults are sentinels, not stubs.

## Threat Flags

No new network endpoints, auth paths, or trust-boundary changes. Threat register items T-6-01 (payload key-tampering) and T-6-06 (unbounded deque growth) mitigations are in place:

- T-6-01: `get_stats_payload()` emits only hard-coded keys (`inference_ms_p50`, `inference_ms_p95`, `detections_per_frame`, `mean_confidence`, `queue_depth`, `freshness_s`, `jitter_m`, plus `detection_gt_metrics` subtree). No dynamic key insertion paths.
- T-6-06: live jitter history deque bounded at `maxlen=_JITTER_HISTORY=30` per class; GT err_ring bounded at `maxlen=_GT_ERR_RING_LEN=60` per (robot, class); `matched_count` / `frames_observed` are int counters (no growth). Class dict grows at most linearly with unique COCO class names encountered per robot.

## Verification

### Acceptance criteria (plan §acceptance_criteria)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | `pytest tests/metrics/test_detection_metrics_tracker.py -v` exits 0 with 7 passing | PASS (`7 passed, 1 warning in 0.03s`) |
| 2 | `grep -c 'class DetectionMetricsTracker' src/metrics/detection_metrics_tracker.py` == 1 | PASS (1) |
| 3 | `grep -cw 'MetricsTracker' src/metrics/detection_metrics_tracker.py` == 0 | PASS (0) |
| 4 | `grep -c 'D-01\|D-02\|D-03\|D-09' src/metrics/detection_metrics_tracker.py` >= 2 | PASS (16) |
| 5 | `grep -c 'def record_gt_match' src/metrics/detection_metrics_tracker.py` == 1 | PASS (1) |
| 6 | `grep -c 'def reset_gt' src/metrics/detection_metrics_tracker.py` == 1 | PASS (1) |
| 7 | `grep -c 'detection_gt_metrics' src/metrics/detection_metrics_tracker.py` >= 2 | PASS (5) |
| 8 | `grep -c 'allow_module_level=True' tests/metrics/test_detection_metrics_tracker.py` == 0 | PASS (0) |
| 9 | 7 live metric keys + detection_gt_metrics in payload | PASS (tests 3, 5, 6, 7) |
| 10 | Empty-state smoke | PASS (`python -c "..."` prints ok) |

### Plan §verification

- [x] 7 unit tests pass (5 live-metric + 2 GT-match)
- [x] Module exports `DetectionMetricsTracker` only (no helpers leaked; all private symbols prefixed `_`)
- [x] Ring buffers bounded (live `maxlen=history_size`, GT err_ring `maxlen=60`); no NaN propagation (Test 3)
- [x] `detection_gt_metrics` top-key present in payload; empty dict until first `record_gt_match` (Test 5)

## Self-Check

- [x] `src/metrics/detection_metrics_tracker.py` present
- [x] `tests/metrics/test_detection_metrics_tracker.py` present (Wave 0 stub replaced)
- [x] Commit `848f4ab` (RED) present in `git log`
- [x] Commit `bb7ada2` (GREEN) present in `git log`
- [x] `pytest` run green
- [x] All 10 acceptance criteria pass

## Self-Check: PASSED
