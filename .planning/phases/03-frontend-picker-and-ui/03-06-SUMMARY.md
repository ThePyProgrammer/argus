---
phase: 03
plan: 06
subsystem: backend
tags:
  - backend
  - main-restart-block
  - worker-pool
  - lifter
one_liner: "main.py restart block + DetectorWorkerPool now consume pending_lifter / pending_lifter_params and emit detector_restart_complete with both backend AND lifter (single-event reuse per Open Question #3)"
requirements:
  - DET-UI-02
  - DET-UI-04
dependency_graph:
  requires:
    - DetectorWorkerPool (Plan 02-04)
    - app.state.pending_lifter / pending_lifter_params (set by lifter REST routes — sibling Phase 03 plan)
    - Detection3DRegistry.get_default (median_depth)
    - existing detector restart block (Plan 02-09 pattern)
  provides:
    - DetectorWorkerPool(lifter_params=...) kwarg
    - main.py wiring of pending_lifter -> Detection3DRegistry.create per-worker
    - detector_restart_complete payload {backend, lifter}
    - app.state.active_lifter populated after warmup
  affects:
    - useWebSocket.ts (frontend handler will read payload.lifter to update detectorStore.activeLifter)
    - LifterDropdown / DetectorSection (depend on app.state.active_lifter being populated)
tech_stack:
  added: []
  patterns:
    - mirror of detector restart block (read pending_* before construction; clear pending_* AFTER successful warmup; retain pending_*_params for live-tunable path)
    - single WS event reused for conjoined detector+lifter restart (Open Question #3)
key_files:
  created:
    - tests/perception/test_worker_pool_lifter_params.py
  modified:
    - src/perception/worker_pool.py
    - src/main.py
decisions:
  - "D-09 / Open Question #3: reuse detector_restart_complete for the lifter event (no separate lifter_restart_complete WS type) — single round-trip per restart, payload carries both keys"
  - "Pitfall #6 honored: pending_lifter is read at the TOP of the detector-pool-rebuild section, BEFORE DetectorWorkerPool(...) construction, so a queued lifter switch cannot be silently dropped"
  - "pending_lifter_params is RETAINED after warmup (mirror of pending_detector_params) — these are live-tunable per-frame inputs, not single-shot restart inputs"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_changed: 3
  commits: 3
  completed: 2026-04-14T07:32:38Z
---

# Phase 3 Plan 06: main.py + DetectorWorkerPool lifter wiring Summary

## Objective Recap

Wire the `pending_lifter` / `pending_lifter_params` REST surface (sibling Phase 03 plan adds the routes; this plan adds the coordinator + worker plumbing) into the per-robot detector pool, mirroring the Phase 2 pattern that already consumes `pending_detector_backend` / `pending_detector_params`. Without this plan, the frontend's `POST /lifter-select` mutates `app.state.pending_lifter` but the coordinator silently ignores it — DET-UI-02 (lifter switch actually changes the active lifter) and DET-UI-04 (restart overlay dismisses only after warmup with the new lifter installed) cannot be satisfied.

## Tasks Executed

| # | Name | Type | Commit | Files |
|---|------|------|--------|-------|
| 1 (RED) | Failing tests for DetectorWorkerPool lifter_params kwarg | TDD-RED | `d0b0fcd` | tests/perception/test_worker_pool_lifter_params.py |
| 1 (GREEN) | DetectorWorkerPool accepts lifter_params and forwards to Detection3DRegistry.create | TDD-GREEN | `41d9287` | src/perception/worker_pool.py |
| 2 | main.py restart block consumes pending_lifter + enriches WS payload | auto | `874e0c6` | src/main.py |

All 14 worker_pool tests pass (10 pre-existing + 4 new).

## Implementation Detail

### Task 1 — `DetectorWorkerPool(lifter_params=...)`

`src/perception/worker_pool.py:107-159`:

```python
def __init__(
    self,
    robot_ids: list[str],
    backend_name: str,
    backend_params: dict | None,
    lifter_name: str,
    intrinsics_per_robot: dict[str, "CameraIntrinsics"],
    lifter_params: dict | None = None,   # NEW
) -> None:
    ...
    params = dict(backend_params or {})
    lifter_kwargs = dict(lifter_params or {})           # defensive copy
    self._lifter_params = lifter_kwargs                  # repr/debug
    self._workers: dict[str, DetectorWorker] = {}
    for rid in robot_ids:
        detector = DetectorRegistry.create(backend_name, **params)
        lifter = Detection3DRegistry.create(lifter_name, **lifter_kwargs)  # NEW kwargs
        self._workers[rid] = DetectorWorker(...)
```

`__repr__` includes `lifter_params=...` only when non-empty (keeps the common Phase 2 path tidy).

Tests cover: forwarded kwargs, default empty, explicit None=empty, per-robot fresh instances all receiving the same kwargs.

### Task 2 — `src/main.py` restart block (5 minimum-diff changes)

All inside the existing `if coordinator._restart_requested:` block (lines 491-580):

1. **Read pending_lifter BEFORE pool construction** (Pitfall #6):
   ```python
   pending_lifter = getattr(app.state, "pending_lifter", None)
   pending_lifter_params = getattr(app.state, "pending_lifter_params", {}) or {}
   ```
2. **Resolve lifter_name with the same fallback pattern as backend_name**:
   ```python
   from src.perception.registry import Detection3DRegistry, DetectorRegistry
   ...
   lifter_name = pending_lifter or Detection3DRegistry.get_default()
   ```
3. **Thread both into DetectorWorkerPool(...)** — replaces the literal `lifter_name="median_depth"`:
   ```python
   detector_pool = DetectorWorkerPool(
       ...,
       lifter_name=lifter_name,
       lifter_params=pending_lifter_params,
   )
   ```
4. **Update app.state after successful warmup** (mirrors detector cleanup):
   ```python
   app.state.active_lifter = lifter_name
   app.state.pending_lifter = None
   # pending_lifter_params intentionally retained (live-tunable per-frame path)
   ```
5. **Enrich detector_restart_complete WS payload** (D-09, single event):
   ```python
   streaming_viz._message_queue.append({
       "type": "detector_restart_complete",
       "payload": {
           "backend": getattr(app.state, "active_detector_backend", "yolov11"),
           "lifter":  getattr(app.state, "active_lifter", "median_depth"),
       },
   })
   ```

**No** separate `lifter_restart_complete` WS type was added. Per Open Question #3 (CONTEXT D-09): one WS event carries both keys — UX-consistent with the conjoined detector+lifter restart and avoids the frontend having to coordinate two separate dismissal signals.

## Verification

| Check | Command | Result |
|---|---|---|
| New tests pass | `pytest tests/perception/test_worker_pool_lifter_params.py -x` | 4 passed |
| No regression in existing pool tests | `pytest tests/perception/test_worker_pool.py -x` | 10 passed |
| Combined | `pytest .../test_worker_pool_lifter_params.py .../test_worker_pool.py -x` | 14 passed |
| AST validity of main.py | `python -c "import ast; ast.parse(open('src/main.py').read())"` | OK |
| Old literal removed | `grep -c 'lifter_name="median_depth"' src/main.py` | 0 |
| pending_lifter read present | `grep -c 'pending_lifter = getattr(app.state, "pending_lifter", None)' src/main.py` | 1 |
| pending_lifter_params read present | `grep -c 'pending_lifter_params = getattr(app.state, "pending_lifter_params", {}) or {}' src/main.py` | 1 |
| lifter_name fallback present | `grep -c 'lifter_name = pending_lifter or' src/main.py` | 1 |
| lifter_params kwarg threaded | `grep -c 'lifter_params=pending_lifter_params' src/main.py` | 1 |
| active_lifter set after warmup | `grep -c 'app.state.active_lifter = lifter_name' src/main.py` | 1 |
| pending_lifter cleared | `grep -c 'app.state.pending_lifter = None' src/main.py` | 1 |
| WS payload carries lifter | `grep -c '"lifter": getattr(app.state, "active_lifter"' src/main.py` | 1 |

All acceptance criteria met.

## Deviations from Plan

None — the plan executed exactly as written. The two `read_first` files (`src/main.py:491-567`, `src/perception/worker_pool.py:107-151`) were already loaded into context and the prescriptive task body matched the source perfectly.

The only optional polish applied (within the plan's body authority for repr-tidiness) was conditioning `lifter_params` in `DetectorWorkerPool.__repr__` on non-empty so the common Phase 2 path that omits the kwarg keeps an unchanged repr.

## Deferred Issues

Logged in `.planning/phases/03-frontend-picker-and-ui/deferred-items.md`:

- `python -c "import src.main"` fails on `import rerun as rr` at `src/main.py:36` — verified pre-existing via `git stash` + retry on baseline. NOT caused by this plan; AST parse of `src/main.py` succeeds. The plan's `<verification>` block lists this command, but it is a dev-env install gap (recommend a future infra plan to install rerun or make the import optional). Substituted: AST parse + grep checks (all pass).
- `tests/perception/test_lifter_routes.py` does not exist yet — that file is delivered by a sibling Phase 03 plan (the lifter REST routes plan, see CONTEXT D-10). Out of scope for 03-06 (which only touches the restart block + worker pool, NOT the REST surface).

## Authentication Gates

None — fully autonomous backend plan, no auth required.

## Threat Flags

None — this plan introduces no new network endpoints, no new file access, and no new schema changes at trust boundaries. It threads ONE additional kwarg from an already-validated REST surface (sibling plan's `POST /lifter-select` performs whitelist + parameter_schema validation BEFORE writing to `app.state.pending_lifter` / `pending_lifter_params`) into an existing in-process registry.create call.

T-03-15 (stale pending_lifter on failed rebuild) is mitigated as designed: `app.state.pending_lifter = None` is cleared INSIDE the `try:` block after `warmup_all` returns, so a failed rebuild leaves `pending_lifter` set and the next restart automatically retries (mirror of the existing detector cleanup pattern).

## Known Stubs

None. This plan ships fully wired functionality — every change is exercised by tests or used directly by the restart block.

## Self-Check: PASSED

**Files created:**
- FOUND: tests/perception/test_worker_pool_lifter_params.py

**Files modified:**
- FOUND: src/perception/worker_pool.py (lifter_params kwarg + repr tweak)
- FOUND: src/main.py (5 changes inside restart block)

**Commits:**
- FOUND: d0b0fcd (test RED)
- FOUND: 41d9287 (worker_pool GREEN)
- FOUND: 874e0c6 (main.py changes)

**Verification:**
- 14/14 pytest pass
- AST parse OK
- All 8 grep acceptance criteria for Task 2 pass
- Old `lifter_name="median_depth"` literal eliminated (count = 0)
