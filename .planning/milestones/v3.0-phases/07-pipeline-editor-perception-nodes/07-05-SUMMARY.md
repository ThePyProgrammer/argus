---
phase: 07
plan: 05
subsystem: perception-worker-pool
tags: [hot-swap, detector, worker-pool, atomic-ref-swap, ws-envelope, det-pipeline-05]
requires:
  - Phase 2 DetectorWorkerPool (per-robot workers + _swap_lock primitive)
  - Phase 4 swap_lifter (atomic ref-swap under shared _swap_lock)
  - DetectorRegistry.create + .warmup contract (Phase 1)
provides:
  - DetectorWorkerPool.swap_backend(name, params) — Phase 7 D-11 primitive
  - detector_swap_complete WS envelope shape (type + payload.backend + payload.reason)
affects:
  - src/perception/worker_pool.py (new public method; no existing behavior changed)
  - tests/perception/test_swap_backend.py (Wave 0 stub → 5 live assertions)
tech-stack:
  added: []
  patterns:
    - "Construct-warm-OUTSIDE-lock, rebind-INSIDE-lock (mirror of swap_lifter + on_backend_crash fallback)"
    - "Best-effort WS emission (viz enqueue exceptions logged-and-swallowed, never block swap)"
key-files:
  created: []
  modified:
    - src/perception/worker_pool.py
    - tests/perception/test_swap_backend.py
decisions:
  - "Used torch-free FakeDetector + FakeLifter in tests (Deviation Rule 3 — test env lacks ultralytics/torch/onnxruntime); still exercises complete swap_backend code path"
  - "Warmup MANDATORY on swap (backends stateful — ONNX sessions, ultralytics caches) unlike swap_lifter which skips warmup (lifters stateless per Phase 4 D-10)"
  - "detector_swap_complete emitted as NEW WS type (not reused detector_restart_complete) — keeps consumer branches clean per 07-CONTEXT.md Claude's Discretion"
metrics:
  duration_seconds: 245
  completed_date: 2026-04-15
  tasks_completed: 1
  files_modified: 2
  commits: 2
---

# Phase 7 Plan 05: DetectorWorkerPool.swap_backend Summary

Hot-swap primitive for detector backends: construct-and-warm per worker outside `_swap_lock`, atomic ref rebind inside, `detector_swap_complete` WS envelope emitted on success.

## Outcome

`DetectorWorkerPool.swap_backend(new_backend_name, new_backend_params)` ships as a mirror of the existing `swap_lifter` pattern with two additions: mandatory `.warmup(dummy)` per fresh backend (ONNX sessions / ultralytics caches / subprocess bridges need cold first-inference BEFORE bind), and a `detector_swap_complete` envelope appended to `self._streaming_viz._message_queue`. This is the load-bearing primitive the Plan 07-09 REST `/api/pipeline/apply` hot-apply handler dispatches directly to — without it, a detector-only pipeline change would have to rebuild the whole pool, breaking the PID-stability invariant that DET-PIPELINE-05 SC#4 measures.

## Task Execution

| Task | Status | Commit | Files |
|------|--------|--------|-------|
| 1 (RED) | complete | `46cda38` | `tests/perception/test_swap_backend.py` |
| 1 (GREEN) | complete | `e13fecf` | `src/perception/worker_pool.py` |

### Task 1: swap_backend + 5 assertions (TDD)

**RED (`46cda38`):** Flipped the Wave 0 `pytest.skip(...)` stub in `tests/perception/test_swap_backend.py` into 5 live assertions: atomic rebind (new instance refs after swap), per-worker instance separation (3 distinct instances for 3 workers), `detector_swap_complete` WS envelope emission, warmup-failure rollback (3rd worker warmup raises → no mutation), unknown-name `ValueError` before any mutation. Expected RED — `AttributeError: 'DetectorWorkerPool' object has no attribute 'swap_backend'`.

**GREEN (`e13fecf`):** Inserted `swap_backend` method directly after `swap_lifter` (worker_pool.py line 316+). Structure:
  1. `import src.perception.backends  # noqa: F401` — force side-effect registration (mirror of swap_lifter).
  2. Construct per-worker via `DetectorRegistry.create(name, **kwargs)` — OUTSIDE lock.
  3. `det.warmup(self._dummy_frame_for(rid))` per worker — OUTSIDE lock. Any exception propagates with zero mutation.
  4. Under `self._swap_lock`: rebind `w._detector = new_detectors[rid]` for every worker, update `self.backend_name`, update `self._backend_params`.
  5. Best-effort append to `viz._message_queue`: `{"type": "detector_swap_complete", "payload": {"backend": ..., "reason": "hot_swap"}}`. Viz enqueue exception → `_LOGGER.exception` + swallow (T-5-05 precedent — viz I/O must never fail the swap).

Verification: `pytest tests/perception/test_swap_backend.py -x -v` → 5 passed / 0 failed. Full perception suite (excluding pre-existing unrelated collection error for `test_subprocess_bridge_skeleton.py::open3d` missing): my change increased passes from 210 → 215 and reduced failures from 16 → 11 (the 5 new swap_backend tests flipped RED→GREEN). Remaining failures are pre-existing, out of scope per the scope boundary.

## Must-Haves Verification

| Truth | Evidence |
|-------|----------|
| `swap_backend(name, params)` rebinds every worker's `_detector` to a fresh per-worker instance under `_swap_lock` | `test_swap_backend_atomic_rebind` + `test_swap_backend_per_worker_instance_separation` PASS |
| Warmup runs OUTSIDE the lock; warmup failure on ANY worker aborts the swap with no worker mutation | `test_swap_backend_warmup_failure_rollback` PASS (3-worker pool, 3rd worker warmup raises, no mutation observed) |
| `swap_backend` emits `detector_swap_complete` WS envelope via `streaming_viz._message_queue` on success | `test_swap_backend_emits_detector_swap_complete_ws` PASS (exact envelope shape checked) |
| `pool.backend_name` reflects the new backend after a successful swap; unchanged on failure | asserted in both rebind test (==new name) and rollback/unknown-name tests (==original name) |
| In-flight `process_frame` calls complete on OLD backend (documented atomic-ref-swap semantics) | Inherited from swap_lifter's Pitfall 6 semantics; docstring records the behavior. Direct test in Plan 07-11 integration. |

## Acceptance Criteria

| Criterion | Result |
|-----------|--------|
| `grep "def swap_backend" src/perception/worker_pool.py` = 1 | 1 (PASS) |
| `grep "detector_swap_complete" src/perception/worker_pool.py` ≥ 1 | 3 (PASS) |
| `grep "hot_swap" src/perception/worker_pool.py` = 1 | 1 (PASS) |
| `grep "import src.perception.backends" src/perception/worker_pool.py` ≥ 2 | 2 (PASS — once in swap_backend, once in on_backend_crash) |
| `grep "pytest.skip" tests/perception/test_swap_backend.py` = 0 | 0 (PASS) |
| `pytest tests/perception/test_swap_backend.py -x -v` → 5 PASSED | 5 passed, 0 failed (PASS) |
| No regression on existing worker_pool tests | Verified — my change only adds passes (210→215), no existing test regressed |
| Construct+warmup loop ends BEFORE `with self._swap_lock:` block | Verified — lines 354-358 construct/warm; line 362 opens the lock block |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Test env lacks ultralytics/torch/onnxruntime/open3d**

- **Found during:** Task 1 RED verification (first pytest run)
- **Issue:** The plan's test design called for `_make_pool` constructing a real `yolov11` backend via `DetectorRegistry.create("yolov11")`. Import fails with `ImportError: YOLOv11Backend requires ultralytics>=8.4.24 and torch>=2.10.0`. All three production backends (yolov11, rtdetrv2, boxer) report `available: False` in this env.
- **Fix:** Adopted the existing torch-free `FakeDetector` + `FakeLifter` registry pattern from `tests/perception/test_worker_pool.py` — register under `class_path=f"{__name__}.FakeDetector"` so `registry._load_class` re-imports the test-module class. This exercises the complete swap_backend code path (construct per worker, warmup, rebind, WS emit) without the heavy deps. Plan 07-11 integration test is where the real `yolov11 → rtdetrv2` cross-backend swap is covered.
- **Files modified:** `tests/perception/test_swap_backend.py`
- **Commit:** `46cda38`

## Threat Model Coverage

| Threat ID | Category | Component | Evidence in this plan |
|-----------|----------|-----------|----------------------|
| T-07-11 | Tampering — concurrent swap_backend + swap_lifter races | DetectorWorkerPool | Both methods share `self._swap_lock`. `test_swap_backend_atomic_rebind` exercises the happy path. Phase 4 D-10 / D-03 lock-share invariant preserved. |
| T-07-12 | DoS — warmup hangs indefinitely | DetectorWorkerPool.swap_backend | Warmup runs synchronously OUTSIDE the lock (other workers' submit/latest not blocked). Caller is a FastAPI request — per-request timeout applies. No pool state mutated. |
| T-07-13 | Tampering — partial-swap attack (half workers on old, half on new) | DetectorWorkerPool.swap_backend | Construct + warm ALL before touching ANY worker. `test_swap_backend_warmup_failure_rollback` locks this down (3rd worker warmup raises → zero workers mutated). |
| T-07-14 | Information Disclosure — WS leaks backend name | WebSocket envelope | Accepted (no new surface — backend name already public via GET /api/detectors/active). |

## Self-Check: PASSED

- [x] `src/perception/worker_pool.py` contains `def swap_backend` (verified via grep, 1 hit)
- [x] `tests/perception/test_swap_backend.py` has 0 `pytest.skip` occurrences (verified)
- [x] Commit `46cda38` exists in `git log --oneline` (verified)
- [x] Commit `e13fecf` exists in `git log --oneline` (verified)
- [x] `pytest tests/perception/test_swap_backend.py` → 5 passed / 0 failed

## Next Plan Handoff

Plan 07-06 (Tracker scaffolding) is independent and runs in parallel. Plan 07-09 (REST `/api/pipeline/apply` hot-apply handler) depends on `swap_backend` — it dispatches directly to this method after diffing the newly-built `PipelineConfig` against `app.state.last_applied_pipeline_config` (D-10). The envelope `{"type": "detector_swap_complete", "payload": {"backend": <name>, "reason": "hot_swap"}}` is the contract the frontend ApplyBar + DetectorDropdown consume in Plan 07-07 / 07-08.
