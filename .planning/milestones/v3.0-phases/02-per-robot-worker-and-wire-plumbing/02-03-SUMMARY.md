---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 03
subsystem: perception
tags: [perception, worker, threading, backpressure, daemon-thread, newest-wins]

# Dependency graph
requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "Detections3D envelope with capture_pose + capture_timestamp fields (Plan 02-01)"
  - phase: 01-detector-api-foundation
    provides: "DetectorProtocol + Detection3DProtocol + SensorFrame + CameraIntrinsics"
provides:
  - "DetectorWorker class — per-robot daemon thread with single-slot newest-wins queue"
  - "_attach_capture helper — authoritative capture_pose/capture_timestamp attachment via dataclasses.replace"
  - "Backpressure test proving 30 Hz submit / 2 FPS backend maintains queue_depth ≤ 1 and drops ≥ 50"
  - "T-02-05/T-02-06/T-02-07 STRIDE mitigations with test coverage"
affects: [02-04 DetectorWorkerPool, 02-05 capture_pose tests, 02-09 coordinator rewire, Phase-6 MetricsPanel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-robot daemon-thread worker with single-slot newest-wins queue"
    - "Lock-held _pending grab-and-clear pattern (detector runs outside lock)"
    - "TYPE_CHECKING guard for protocol imports (P9 — worker stays torch-free)"
    - "dataclasses.replace envelope overwrite for frozen Detections3D"

key-files:
  created:
    - src/perception/worker.py
    - tests/perception/test_worker_backpressure.py
  modified: []

key-decisions:
  - "10 ms poll interval: chosen because it's well below both the 200 Hz sim tick and the 30 Hz submit cadence, so the worker picks up new frames within one tick without burning CPU on a tighter spin."
  - "Session-lifetime drop counter: reset() does NOT clear _drops — pool owns metric lifecycle, and detector-swap (the reset() caller) is orthogonal to the backpressure metric exposed via inspect()."
  - "Defensive pose copy outside the lock: np.asarray(pose).copy() touches only caller data so it runs before acquiring _lock; this keeps the locked critical section to a pure tuple write + counter increment."
  - "Detector + lifter run WITHOUT the lock: a 2 FPS backend must not block the 30 Hz submit path. Only the _pending grab-and-clear and _latest write are lock-held."
  - "Thread name `det-{rid}`: Phase 6 MetricsPanel filters by thread name — formalizing the convention here so future backends don't drift."

patterns-established:
  - "Newest-wins backpressure: single-slot _pending + drop counter + lock-held grab-and-clear"
  - "Worker-never-dies: try/except Exception + logger.exception + continue in the inference loop"
  - "Envelope-level capture attachment: worker is the authoritative source for capture_pose/capture_timestamp; Phase 1 lifter defaults are always overwritten"
  - "Test fakes with zero heavy deps: SlowDetector / FlakyDetector / DummyLifter defined inline so Plan 02-03 tests run in ~4 s without torch"

requirements-completed: [DET-API-04]

# Metrics
duration: 5 min
completed: 2026-04-14
---

# Phase 2 Plan 03: DetectorWorker — Per-Robot Daemon Thread with Newest-Wins Queue Summary

**Per-robot daemon thread (`det-{rid}`) with a single-slot `_pending` tuple, lock-held grab-and-clear drain, and session-lifetime drop counter — proves newest-wins backpressure under 30 Hz / 2 FPS adversarial load and defends against pose-snapshot corruption + worker-thread death.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-14T02:31:34Z (base commit)
- **Completed:** 2026-04-14T02:36:44Z (Task 2 commit)
- **Tasks:** 2
- **Files created:** 2 (`src/perception/worker.py`, `tests/perception/test_worker_backpressure.py`)
- **Test suite runtime:** 4.21 s (4 tests)

## Accomplishments

- `DetectorWorker` class with the full public API locked by must_haves: `start / submit / latest / inspect / warmup / reset / shutdown`.
- Single-slot `_pending: tuple | None` under `threading.Lock` — overwriting submits increment `_drops` (session-lifetime counter exposed via `inspect()`).
- Defensive `np.asarray(pose, dtype=np.float64).copy()` in `submit()` protects the worker snapshot from later in-place caller mutation (T-02-06).
- `_loop()` drains `_pending` under lock, runs detector + lifter OUTSIDE the lock, catches `Exception` with `logger.exception` and continues (T-02-07: worker never dies).
- `_attach_capture` module-level helper uses `dataclasses.replace` to overwrite envelope-level `capture_pose` + `capture_timestamp` on the returned `Detections3D` per D-11/D-12/D-13.
- Thread named `det-{robot_id}` for Phase 6 MetricsPanel filtering.
- Backpressure test proves queue_depth ≤ 1 at every submit AND drops ≥ 50 over 60 submits at 30 Hz into a 0.5 s/frame fake detector; plus tests for exception survival, defensive pose copy, and Pitfall P9 (no torch leak).

## Task Commits

1. **Task 1: Implement DetectorWorker** — `df74826` (feat)
2. **Task 2: Backpressure + safety tests** — `0b70058` (test)

_Plan metadata commit deferred to the parallel-mode merge orchestrator._

## Files Created/Modified

- `src/perception/worker.py` — 280 lines. `DetectorWorker` class + `_attach_capture` helper. Module-top imports: `logging, threading, time, dataclasses.replace, numpy`. Protocol types imported under `TYPE_CHECKING` only (P9).
- `tests/perception/test_worker_backpressure.py` — 260 lines. Four tests: `test_backpressure_drops_stale_frames`, `test_worker_never_dies_on_inference_exception`, `test_defensive_pose_copy`, `test_worker_module_does_not_import_torch`. Inline `SlowDetector` / `FlakyDetector` / `DummyLifter` fakes with zero heavy deps.

## Decisions Made

- **10 ms poll interval** — Module constant `_POLL_INTERVAL_SEC = 0.01`. Below the 200 Hz sim tick and 30 Hz submit cadence, so new frames are picked up within one tick without CPU spin.
- **2 s shutdown-join timeout** — Module constant `_SHUTDOWN_JOIN_TIMEOUT_SEC = 2.0`. Bounded because `_loop`'s blocking operations are either `time.sleep(0.01)` or one detector inference.
- **Session-lifetime drop counter** — `_drops` is NOT reset by `reset()`. The pool owns metric lifecycle; `reset()` is for detector-swap, orthogonal to the backpressure metric.
- **Pose copy outside the lock** — `np.asarray(pose).copy()` only touches caller data, so it runs before `_lock` acquisition. Keeps the critical section minimal (tuple write + counter increment).
- **Detector + lifter run WITHOUT the lock** — Only `_pending` grab-and-clear and `_latest` write are lock-held. A slow 2 FPS backend cannot block the 30 Hz submit path.

## Deviations from Plan

None — plan executed exactly as written. The reference implementation from 02-RESEARCH.md §Pattern 3 (line 309) translated verbatim into `src/perception/worker.py` with the exact thread name, poll interval, drop-counter semantics, defensive-copy placement, and `_attach_capture` helper specified by the plan.

## Issues Encountered

- **Worktree base mismatch (corrected)**: The worktree branch was initially pointing at `1a804fe` (a pre-main-merge commit) instead of the expected base `80fe7bea`. Detected via the `<worktree_branch_check>` guidance in `execute-plan.md` by running `git merge-base HEAD 80fe7bea`. Resolved with `git reset --hard 80fe7bea` before starting work — no task changes were lost because nothing was committed yet. This is the known Windows-style branch-base issue noted in the workflow; on Linux it triggered because the worktree was cut from an older HEAD. Post-reset, Plan 02-01's `capture_pose` / `capture_timestamp` fields on `Detections3D` were present, allowing `dataclasses.replace(..., capture_pose=..., capture_timestamp=...)` to work.
- **Pre-existing msgpack / torch test collection failures** — `tests/perception/test_subprocess_bridge_skeleton.py` (Plan 02-06 artifact) fails collection with `ModuleNotFoundError: msgpack`; `test_protocol_contracts.py` + `test_registry.py` have pre-existing torch-related failures documented in prior commits (`01-05: close torch-missing deferred item — Plan 05 installs perception extra`). **Out of scope for this plan** per scope boundary rules. Plan 02-03's own test file (`test_worker_backpressure.py`) passes 4/4 in 4.21 s with zero regressions.

## Next Phase Readiness

- **Ready for Plan 02-04** (`DetectorWorkerPool`): wraps `DetectorWorker` one-per-robot, calls `start()` / `warmup_all()` / `submit()` / `latest()` / `inspect_worker_queues()`. Pattern 4 in `02-RESEARCH.md` line 417 is the reference.
- **Ready for Plan 02-05** (capture_pose integration tests): extends `test_worker_backpressure.py`'s defensive-copy coverage with real-pose / multi-frame scenarios.
- **Ready for Plan 02-09** (coordinator rewire): coordinator will call `pool.submit(rid, frame, robot.get_pose(), slam_cloud)` at 30 Hz and `pool.latest(rid)` from the render/WS thread.
- **Ready for Phase 6** MetricsPanel: `inspect()` dict shape is locked (`queue_depth`, `drops_since_session_start`, `last_submit_sim_time`) and the thread-name convention `det-{rid}` is documented.

### Contracts locked for downstream consumers

- `DetectorWorker(robot_id, detector, lifter, intrinsics)` — constructor does NOT start the thread.
- `submit(frame, pose, slam_cloud)` — pose is deep-copied; `sim_time` comes from `frame.sim_time`; drops counted when `_pending` was non-None.
- `_loop` envelope attachment — `capture_pose` is the defensive copy from `submit()`; `capture_timestamp` is `frame.sim_time` at submit time, NOT lift time.
- `inspect()` keys — `queue_depth`, `drops_since_session_start`, `last_submit_sim_time` (float, sim-clock seconds).
- Thread naming — `det-{robot_id}` (literal f-string format).

## Self-Check: PASSED

- `src/perception/worker.py` exists (280 lines ≥ 130 required) — contains `class DetectorWorker`.
- `tests/perception/test_worker_backpressure.py` exists (260 lines ≥ 60 required) — contains `def test_backpressure_drops_stale_frames`.
- Commit `df74826` found on branch (Task 1: DetectorWorker implementation).
- Commit `0b70058` found on branch (Task 2: backpressure tests).
- `pytest tests/perception/test_worker_backpressure.py -x -q` → 4 passed, 1 warning in 4.21 s.
- `python -c "import sys; import src.perception.worker; print('torch' in sys.modules)"` → `False` (P9 invariant upheld).
- Plan requirements: `DET-API-04` satisfied.

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*
