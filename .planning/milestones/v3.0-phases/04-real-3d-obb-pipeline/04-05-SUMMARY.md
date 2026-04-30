---
phase: 04
plan: 05
subsystem: perception
tags:
  - hotswap
  - worker-pool
  - rest-api
  - wave-3
dependency-graph:
  requires:
    - "04-04"
  provides:
    - "DetectorWorkerPool.swap_lifter(name, params) — atomic per-worker lifter rebind under _swap_lock"
    - "POST /api/detectors/lifter-hotswap REST route — no restart, no warmup"
    - "app.state.detector_pool exposure in main.py restart block + server.py baseline"
  affects:
    - "backend/web/server.py (drops pending_lifter init; adds detector_pool baseline)"
    - "src/main.py (restart block preserves active_lifter; pending_lifter consumption removed)"
    - "tests/perception/test_lifter_routes.py (removes /lifter-select coverage; keeps list/active/params)"
tech-stack:
  added: []
  patterns:
    - "threading.Lock for serialized hot-swap (_swap_lock) — ≪1ms hold window"
    - "GIL-atomic attribute rebind for worker._lifter reads (Research Pattern Template 3, Pitfall 6)"
    - "fail-before-mutate: Detection3DRegistry.create runs OUTSIDE _swap_lock so unknown/unavailable names 404/400 before any worker touch"
key-files:
  created:
    - tests/perception/test_lifter_hotswap.py
  modified:
    - src/perception/worker_pool.py
    - src/main.py
    - backend/web/server.py
    - backend/web/detector_routes.py
    - tests/perception/test_lifter_routes.py
    - .planning/phases/04-real-3d-obb-pipeline/deferred-items.md
decisions:
  - "D-09 supersession landed backend-side: /lifter-select removed, /lifter-hotswap added"
  - "D-10 swap_lifter uses module-level threading.Lock held ONLY for per-worker ref rebind; registry.create runs OUTSIDE the lock"
  - "Restart block preserves hot-swapped lifter via app.state.active_lifter read (pending_lifter field retired)"
  - "server.py initializes app.state.detector_pool = None so /lifter-hotswap returns 503 before first restart (T-04-21)"
metrics:
  duration: "~25min"
  completed: "2026-04-14"
requirements: [DET-3D-01]
---

# Phase 4 Plan 05: DetectorWorkerPool.swap_lifter + /lifter-hotswap Route Summary

Wave 3 backend hot-swap cutover: lifter selection becomes a sub-millisecond
atomic ref swap with no worker restart and no warmup — Phase 4 D-09
supersedes Phase 3 D-09's restart-driven `/lifter-select` flow.

## What shipped

**Pool-level (Task 1):**

- `src/perception/worker_pool.py` gains `DetectorWorkerPool.swap_lifter(name, params)`:
  - Module-level `import threading`; `self._swap_lock = threading.Lock()` in `__init__`.
  - `swap_lifter` constructs a FRESH lifter per worker via
    `Detection3DRegistry.create(name, **kwargs)` BEFORE touching any worker
    (fail-loud on unknown name / missing dep — no partial swap).
  - Holds `_swap_lock` only during the per-worker `w._lifter = new_lifter`
    rebind loop (≪1ms; non-blocking for `submit`/`latest` which use their own
    per-worker locks).
  - Does NOT call `warmup()` — lifters are stateless geometry per D-10.
  - Mutates `self.lifter_name` and `self._lifter_params` under the lock so
    repr/accessors stay consistent with the live workers.
- `src/main.py` restart block:
  - `app.state.detector_pool = detector_pool` on success (Research Open
    Question #4 resolution — `request.app.state.detector_pool` is how the
    new route reaches the pool).
  - `app.state.detector_pool = None` on failure (T-04-23 mitigation keeps
    coordinator and app.state in sync).
  - Phase 3's `pending_lifter` consumption in the detector-pool rebuild
    block is removed; `lifter_name = active_lifter_name or registry-default`
    preserves the user's hot-swap pick across a detector restart.

**Route-level (Task 2):**

- `backend/web/detector_routes.py`:
  - DELETE `async def select_lifter` handler at `POST /lifter-select`.
  - ADD `async def lifter_hotswap` at `POST /api/detectors/lifter-hotswap`:
    - Validate `req.lifter` ∈ `Detection3DRegistry.list_backends()` BEFORE
      state mutation (T-04-18 → 404 on unknown; T-04-19 → 400 on
      unavailable).
    - Reach the pool via `request.app.state.detector_pool`; return 503 when
      None (T-04-21 — pool not yet built).
    - Call `pool.swap_lifter(req.lifter, req.params or {})` (atomic ref
      swap under `_swap_lock` — T-04-20 serialization).
    - Update `request.app.state.active_lifter` so `GET /active-lifter`
      reflects the new lifter and the next restart block preserves it.
    - Return `{"status": "swapped", "lifter": req.lifter}`.
  - `LifterSelectRequest` pydantic class is retained — it is reused by the
    new hot-swap handler (same `{lifter, params?}` shape).
  - Section header comment + threat-model notes rewritten from Phase 3
    D-10 (T-03-11) to Phase 4 D-09 (T-04-18..22).
- `backend/web/server.py`:
  - Drop `app.state.pending_lifter` init (field retired — no restart path
    exists for lifter selection anymore).
  - Add `app.state.detector_pool = None` baseline so `/lifter-hotswap`
    returns 503 before the first restart block runs (T-04-21 mitigation).
  - Retain `app.state.pending_lifter_params` for PATCH `/lifter-params`
    live-tunable threading (unchanged — same pattern as detector params).

**Test surface:**

- `tests/perception/test_lifter_hotswap.py` (new, 10 tests):
  - Pool-level: `test_swap_lifter_replaces_every_workers_lifter_ref`,
    `test_swap_lifter_is_fast_no_warmup`, `test_swap_lifter_rejects_unknown_name`,
    `test_hotswap_under_30hz_submit` (all guarded by
    `pytest.importorskip("ultralytics")`).
  - Route-level (torch-free, uses a `_FakePool` fixture):
    `test_lifter_hotswap_returns_swapped`, `..._unknown_returns_404`,
    `..._no_pool_returns_503`, `..._calls_pool_swap_lifter`,
    `..._updates_active_lifter_state`, `test_lifter_select_route_removed`.
- `tests/perception/test_lifter_routes.py`:
  - DELETE the four `test_lifter_select_*` tests (sets_pending_lifter /
    unknown_returns_404 / unavailable_returns_400 / with_params_stashes).
    The hot-swap route contract is locked in `test_lifter_hotswap.py` —
    duplicating coverage here would drift.
  - ADD `test_lifter_select_route_removed` — regression lock asserting the
    old path returns 404/405 under the real `create_app` client.
  - Retain `list_lifters` (Pitfall #4 cold-boot guard),
    `get_active_lifter`, `patch_lifter_params` tests — those routes are
    unchanged.

## Commits

| Task | Type | Commit  | Message                                                                |
| ---- | ---- | ------- | ---------------------------------------------------------------------- |
| RED  | test | b851829 | test(04-05): add failing tests for hot-swap — pool + route contract    |
| 1    | feat | eb680d9 | feat(04-05): DetectorWorkerPool.swap_lifter + app.state pool exposure  |
| 2    | feat | 20bd04c | feat(04-05): replace /lifter-select with /lifter-hotswap route (D-09)  |
| —    | chore| fe1f832 | chore(04-05): log pre-existing out-of-scope failures to deferred-items |

## Verification

Run under this plan:

```
pytest tests/perception/test_lifter_routes.py \
       tests/perception/test_lifter_hotswap.py \
       tests/perception/test_worker_pool.py \
       tests/perception/test_worker_pool_lifter_params.py \
       tests/perception/test_detector_routes.py -q
# → 35 passed, 4 skipped (ultralytics-gated), 0 failed
```

Grep invariants:

- `grep -c "def swap_lifter" src/perception/worker_pool.py` → **1**
- `grep -c "self._swap_lock" src/perception/worker_pool.py` → **3** (init comment, init bind, swap body)
- `grep -c "^import threading" src/perception/worker_pool.py` → **1**
- `grep -c '@router.post("/lifter-select")' backend/web/detector_routes.py` → **0**
- `grep -c '@router.post("/lifter-hotswap")' backend/web/detector_routes.py` → **1**
- `grep -c "pool.swap_lifter" backend/web/detector_routes.py` → **2** (handler body + docstring)
- `grep -c "async def select_lifter" backend/web/detector_routes.py` → **0**
- `grep -c "async def lifter_hotswap" backend/web/detector_routes.py` → **1**
- `grep -c "Detector pool not initialized" backend/web/detector_routes.py` → **1**
- `grep -c "app.state.detector_pool" src/main.py` → **3** (success + failure + comment)

## Deviations from Plan

**Plan-spec adjustments (no user permission needed — Rule 2: critical correctness):**

**1. [Rule 2 - Correctness] Removed `pending_lifter` restart consumption in `src/main.py`**
- **Found during:** Task 1 (main.py edit)
- **Issue:** Plan 04-05's `<must_haves>` says `POST /lifter-select` is REMOVED
  and D-09 says lifter no longer participates in the restart flow, but the
  literal plan action text only described ADDING `app.state.detector_pool`;
  leaving the Phase 3 `pending_lifter`/`app.state.pending_lifter` read +
  write in place would let a stale pending value from a pre-Phase-4 run
  override a live hot-swapped lifter on the next restart.
- **Fix:** Replaced `pending_lifter = getattr(app.state, "pending_lifter", None)`
  with `active_lifter_name = getattr(app.state, "active_lifter", None)` and
  removed `app.state.pending_lifter = None` from the post-construction
  block. The restart path now preserves the user's hot-swap pick. Also
  dropped `app.state.pending_lifter` from `server.py`'s init block so no
  surface leaks. `pending_lifter_params` is retained for PATCH
  `/lifter-params` live-tunable threading (detector-param-style path).
- **Files modified:** `src/main.py`, `backend/web/server.py`
- **Commit:** eb680d9

**2. [Rule 2 - Defensive baseline] `app.state.detector_pool = None` added to `server.py` init**
- **Found during:** Task 1 (matching the failure-branch pattern)
- **Issue:** The plan sets `app.state.detector_pool` inside the restart
  block, but boot-time requests to `/lifter-hotswap` land BEFORE any restart
  runs — `getattr(..., None)` works but an explicit `None` baseline makes
  the 503 path explicit and consistent with the `active_*` / `pending_*`
  baselines already in `create_app`.
- **Fix:** Added `app.state.detector_pool = None` at the bottom of the
  lifter block in `create_app`.
- **Files modified:** `backend/web/server.py`
- **Commit:** eb680d9

No architectural deviations (Rule 4) were necessary.

## Deferred Issues

See `.planning/phases/04-real-3d-obb-pipeline/deferred-items.md` for the
full log. Summary of pre-existing failures verified against base commit
`5056293` (all unrelated to 04-05):

- `tests/web/test_slam_routes.py` — `KeyError: 'supports_imu'` (SLAM
  capability schema mismatch).
- `tests/perception/test_subprocess_bridge*.py` + `tests/web/test_merge_routes.py` —
  `ModuleNotFoundError: msgpack`.
- `tests/web/test_streaming_viz.py::TestCameraFrame` encode tests —
  same encoding-dep gap.
- `tests/perception/test_protocol_contracts.py` torch-mixin tests —
  `ModuleNotFoundError: torch` (already tracked from plan 04-04).

## Threat Flags

None — all new surface is covered by the `<threat_model>` in 04-05-PLAN.md
(T-04-18..24) and the handler enforces all five mitigations.

## Self-Check: PASSED

**Files:**

- FOUND: src/perception/worker_pool.py
- FOUND: src/main.py
- FOUND: backend/web/server.py
- FOUND: backend/web/detector_routes.py
- FOUND: tests/perception/test_lifter_hotswap.py
- FOUND: tests/perception/test_lifter_routes.py

**Commits:**

- FOUND: b851829 (RED)
- FOUND: eb680d9 (Task 1 GREEN)
- FOUND: 20bd04c (Task 2 GREEN)
- FOUND: fe1f832 (deferred-items log)
