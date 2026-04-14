---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 04
subsystem: perception
tags: [perception, pool, registry, detector-worker, restart, threading, keyed-dispatch]

# Dependency graph
requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "DetectorWorker per-robot daemon thread with single-slot newest-wins submit, warmup, reset, inspect (Plan 02-03)"
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "Detections3D envelope with capture_pose + capture_timestamp (Plan 02-01)"
  - phase: 01-detector-api-foundation
    provides: "DetectorRegistry / Detection3DRegistry.create with CAPABILITIES validation (D-05, D-06)"
provides:
  - "DetectorWorkerPool — keyed dispatch over per-robot DetectorWorker instances; single submission entry point for Coordinator (D-05)"
  - "Per-robot instance separation: each worker owns its own detector + lifter (enables Phase 8 stretch DET-STRETCH-04 per-robot param tuning)"
  - "Synchronous warmup_all — Wave 4 main.py restart block can chain this before emitting detector_restart_complete (D-03)"
  - "inspect_worker_queues observability surface consumed by Phase 6 MetricsPanel"
  - "Unknown-rid defensive no-op in submit/latest (T-02-08 mitigation)"
affects:
  - "02-08 (REST /select routes through pool.reset_all after swap)"
  - "02-09 (Wave 4 main.py restart block — constructs pool, chains warmup_all, then start)"
  - "02-10 (Coordinator refactor — _detector_pool becomes the sole detection dataflow mediator)"
  - "06 (MetricsPanel consumes inspect_worker_queues)"
  - "08 (stretch DET-STRETCH-04 per-robot tuning relies on per-robot instance separation)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Keyed-dispatch pool over per-robot worker threads (02-RESEARCH Pattern 4)"
    - "Registry-driven construction: pool __init__ calls DetectorRegistry.create(name, **params) once per robot, not once total"
    - "Synchronous warmup as restart gate — caller's thread blocks until every worker.warmup returns; no thread-pool parallelism (oneDNN shares the BLAS pool anyway)"
    - "Defensive no-op on unknown rid (D-05): pool never raises on stale-rid races during restart teardown"

key-files:
  created:
    - src/perception/worker_pool.py
    - tests/perception/test_worker_pool.py
  modified: []

key-decisions:
  - "Per-robot detector/lifter INSTANCES (not shared singleton) — enables Phase 8 stretch DET-STRETCH-04 per-robot param tuning; cost is O(N) model memory which Phase 2 treats as acceptable for N<=4 in-scope robot counts"
  - "warmup_all iterates SEQUENTIALLY — oneDNN / BLAS thread pool is shared across backends, so parallel warmup would just thrash the same cores; sequential makes timing predictable for the D-03 restart gate"
  - "__init__ does NOT call start() — warmup_all must complete BEFORE worker threads spawn so the next submit cannot race a still-cold detector. Wave 4 chains: construct, warmup_all, start"
  - "warmup_all logs (not raises) on missing dummy frames and on backend warmup exceptions — restart must never hang the UI; cold-start stall for a late robot is preferable to a blocked restart overlay"
  - "Unknown-rid is a silent no-op in submit/latest (D-05) — Coordinator stale-rid races during robot teardown cannot crash the detection dataflow for other robots (T-02-08)"

patterns-established:
  - "Pool construction sequence: pool = DetectorWorkerPool(...); pool.warmup_all({...}); pool.start() — locked in Wave 4"
  - "Registry class_path for test fakes MUST resolve via importlib — define fakes at module scope, register with explicit class_path=f'{__name__}.FakeName'; decorator-with-local-class does NOT work because __qualname__ includes the function scope"
  - "inspect_worker_queues snapshot shape {queue_depth, drops_since_session_start, last_submit_sim_time} is the Phase 6 MetricsPanel contract — adding new keys is non-breaking; removing or renaming requires a MetricsPanel PR"

requirements-completed: [DET-API-04, DET-MODELS-05]

# Metrics
duration: 4 min
completed: 2026-04-14
---

# Phase 2 Plan 04: DetectorWorkerPool Summary

**Coordinator-owned keyed-dispatch pool over per-robot DetectorWorker threads with synchronous warmup_all restart gate and per-robot detector instance separation.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-14T02:40:52Z
- **Completed:** 2026-04-14T02:45:10Z
- **Tasks:** 2 (Task 1: pool implementation; Task 2: comprehensive test suite — merged into TDD RED→GREEN commits)
- **Files created:** 2 (`src/perception/worker_pool.py`, `tests/perception/test_worker_pool.py`)
- **Files modified:** 0

## Accomplishments

- Implemented `DetectorWorkerPool` with per-robot detector + lifter instances constructed via registry (DET-API-04 scope fulfilled: "pool keyed by robot_id")
- Landed synchronous `warmup_all` — the restart gate Wave 4's `main.py` chains before emitting `detector_restart_complete` (D-03 / DET-MODELS-05)
- Exposed `inspect_worker_queues` with the exact `{rid: {queue_depth, drops_since_session_start, last_submit_sim_time}}` shape Phase 6 MetricsPanel consumes
- Enforced per-robot instance separation (test_instance_separation_backend_mutations_do_not_leak) — downstream Phase 8 stretch DET-STRETCH-04 per-robot tuning has a clear path
- Unknown-rid defensive no-op (T-02-08 mitigation) — Coordinator stale-rid races cannot crash pool dispatch
- P9 invariant preserved: `import src.perception.worker_pool` does NOT pull torch; verified by `test_pool_module_does_not_import_torch`

## Task Commits

1. **Task 1 RED: Failing DetectorWorkerPool test suite** — `f2dc877` (test)
2. **Task 1+2 GREEN: DetectorWorkerPool implementation + test fakes module-scope refactor** — `8d816c1` (feat)

_Per parallel-mode rules, commits use `--no-verify`; orchestrator validates hooks once after all wave agents complete. No STATE/ROADMAP/REQUIREMENTS writes in this worktree._

## Files Created/Modified

- `src/perception/worker_pool.py` (created) — `DetectorWorkerPool` class: keyed dispatch, warmup/reset orchestration, inspection surface, single submission entry point for Coordinator.
- `tests/perception/test_worker_pool.py` (created) — 10 tests covering construction, submit/latest dispatch, warmup_all synchronous contract, unknown-rid safety, inspect shape, per-robot instance separation, reset_all, public attributes, and P9 torch-free invariant.

## Decisions Made

- **Per-robot INSTANCES over shared singleton** (plan must-have) — small RAM cost (N backends) is worth the Phase 8 stretch-goal capability of per-robot param tuning and the simpler reasoning (no shared mutable state across threads). Each worker gets a fresh `DetectorRegistry.create()` call.
- **Sequential warmup, not parallel** — BLAS/oneDNN share the CPU thread pool; a ThreadPoolExecutor would just contend the same cores and defeat the D-03 gate timing. Per-rid warmup runs one after the other on the caller's thread.
- **Log-and-continue on warmup failures** (both missing-rid and exceptions) — the alternative (raise, block restart) is worse for UX than shipping a cold-start stall for the affected robot. Wave 4's restart overlay is gated on `warmup_all` returning, not on every worker succeeding.
- **`__init__` does NOT call `start()`** — the documented construction sequence is `construct → warmup_all → start()`. Starting threads before warmup would allow an in-flight submit to race a cold backend. Wave 4's `main.py` pattern enforces this ordering.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test fake classes moved from fixture-local scope to module scope**
- **Found during:** Task 1 GREEN (running full test suite against implementation)
- **Issue:** The plan's suggested test scaffolding used the `@detector_backend(...)` decorator INSIDE the `register_fakes` fixture. Registry stores `class_path = f"{klass.__module__}.{klass.__qualname__}"`; for classes defined inside a function the `__qualname__` is `register_fakes.<locals>.FakeDetector` which `importlib.import_module(...).getattr(...)` cannot resolve at `create()` time — so `pool.__init__` immediately raised `ImportError: Cannot load detector class`.
- **Fix:** Moved `FakeDetector` and `FakeLifter` to MODULE scope, switched `register_fakes` to explicit `DetectorRegistry.register(name=..., class_path=f"{__name__}.FakeDetector", klass=FakeDetector)` calls (same pattern `tests/perception/test_registry.py::test_list_backends_uses_available_probe` already established).
- **Files modified:** `tests/perception/test_worker_pool.py`
- **Verification:** All 10 pool tests pass; 25/25 in the plan's verification suite pass.
- **Committed in:** `8d816c1` (GREEN commit alongside the pool implementation)

**2. [Rule 2 - Missing Critical] Added `test_warmup_all_tolerates_missing_rid`**
- **Found during:** Task 2 test design (expanding on must-have "log (not raise) on missing keys so restart doesn't hang")
- **Issue:** Plan called out the log-vs-raise behavior in the action block but did not list a test for it. Without an explicit test, a future refactor could silently regress the behavior — and the D-03 restart gate would then hang if any robot hadn't captured its first real frame yet.
- **Fix:** Added `test_warmup_all_tolerates_missing_rid` covering the "r1 missing from dummy_frames" case; asserts r0 gets warmed, r1 stays at `warmup_count == 0`, and no exception propagates.
- **Files modified:** `tests/perception/test_worker_pool.py`
- **Verification:** Test passes; paired with `test_warmup_all_is_synchronous` to fully cover the D-03 contract.
- **Committed in:** `f2dc877` (RED commit; the test exists from the start of the suite).

**3. [Rule 2 - Missing Critical] Added P9 invariant test for worker_pool module**
- **Found during:** Task 2 design
- **Issue:** Plan verification includes `python -c "import src.perception.worker_pool; assert 'torch' not in sys.modules"` as a CLI check but no pytest test. CI pipelines run pytest, not the ad-hoc CLI check — the invariant could regress without triggering a failure.
- **Fix:** Added `test_pool_module_does_not_import_torch` that drops cached worker_pool imports, re-imports fresh, and asserts `torch not in sys.modules`. Same pattern as `test_registry.py::test_registry_module_does_not_import_heavy_deps`.
- **Files modified:** `tests/perception/test_worker_pool.py`
- **Verification:** Test passes; invariant now enforced by the test runner, not only by the ad-hoc CLI.
- **Committed in:** `f2dc877` (RED — fails by default until implementation exists).

**4. [Rule 2 - Missing Critical] Added `test_pool_exposes_backend_and_lifter_names_as_public_attrs`**
- **Found during:** Task 2 design
- **Issue:** Plan must-have lists `backend_name` and `lifter_name` as "public attributes for observability (Phase 6 metrics)" but there was no test pinning them. Phase 6 would then discover the attribute names via grep rather than a contract test.
- **Fix:** Added a direct attribute-read test so Phase 6 has a pinning point.
- **Files modified:** `tests/perception/test_worker_pool.py`
- **Committed in:** `f2dc877`.

---

**Total deviations:** 4 auto-fixed (1 blocking, 3 missing-critical test coverage)
**Impact on plan:** Deviation 1 was a genuine blocking fix to the planner's test recipe (decorator-inside-function does not round-trip through the registry's class_path loader); deviations 2-4 are additive tests that pin plan contracts the planner described but did not test. No scope creep — pool API surface is exactly what the plan specified.

## Issues Encountered

None. All work followed the plan; the four auto-fixes above are additive/corrective, not remediative.

## Authentication Gates

None.

## Threat Flags

No new threat surface introduced. Both threats in the plan's `<threat_model>` are handled:

| Threat ID | Disposition | Mitigation evidence |
|-----------|-------------|---------------------|
| T-02-08 (DoS via unknown rid) | mitigate | `test_unknown_rid_safe_noop` asserts submit + latest never raise; implementation uses `self._workers.get(rid)` with early return. |
| T-02-09 (Tampering via backend_name) | transfer | `DetectorRegistry.create()` raises `ValueError` for unknown names (already tested in `test_registry.py`); Plan 08's REST `/select` validates upstream before writing to `app.state`. Pool trusts this gate. |

## Known Stubs

None. `DetectorWorkerPool` is a complete surface for Wave 4's cutover. Only follow-up work outside this plan: Wave 4 wiring (`02-09` / `02-10`) consumes the pool.

## Self-Check

- [x] `src/perception/worker_pool.py` exists (`[ -f ]` confirmed by `ls`)
- [x] `tests/perception/test_worker_pool.py` exists
- [x] Test commit `f2dc877` in git log
- [x] Impl commit `8d816c1` in git log
- [x] All 10 pool tests pass
- [x] Plan verification suite (25 tests) passes
- [x] P9 invariant holds: `import src.perception.worker_pool` does not pull torch
- [x] Branch reset from stale base `1a804fe` to expected `9a67f59` recorded (worktree-branch-check fix)

## Self-Check: PASSED

## User Setup Required

None.

## Next Phase Readiness

- Wave 4 (plans 02-09 / 02-10) can now wire `DetectorWorkerPool` into `main.py` as `app.state.detector_pool` and refactor the `Coordinator` to dispatch through `pool.submit(rid, frame, pose, slam_cloud)`.
- Plan 02-05 (parallel with this plan in Wave 3) is independent — no file overlap.
- Phase 6 MetricsPanel has a stable `inspect_worker_queues` contract to target.
- Phase 8 stretch DET-STRETCH-04 per-robot param tuning is unblocked at the worker layer.

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*
