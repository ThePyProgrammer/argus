---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 09
subsystem: perception
tags: [crash-fallback, backend-swap, typed-exceptions, websocket, resilience]

# Dependency graph
requires:
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: "Plan 05 BridgeHangError + SubprocessDiedError typed exceptions; Plan 08 BoxeR composer backend; Plan 04 crash_fallback test skeleton"
  - phase: 04-spawn-swap-lift-panel-rtmdet
    provides: "DetectorWorkerPool.swap_lifter pattern + _swap_lock discipline (D-10) mirrored here for D-03"
provides:
  - "DetectorWorkerPool.on_backend_crash(crashed_backend, reason) — atomic detector swap across N workers"
  - "DetectorWorkerPool.set_streaming_viz(viz) — deferred wiring hook for main.py"
  - "DetectorWorker typed-except on BridgeHangError/SubprocessDiedError → escalates to pool.on_backend_crash"
  - "crash_fallback WS envelope mirroring SLAM precedent (exploration_loop.py:207)"
  - "D-04 session-scoped registry lockout via DetectorRegistry.set_available"
affects: [05-10-frontend-crash-toast, 05-11-e2e-integration, phase-06-future-detectors]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reverse pool_ref: worker holds weak-ish ref to its pool for escalation on typed exceptions"
    - "Atomic ref swap under _swap_lock with pre-warmed fallback instances (mirror D-10)"
    - "WS envelope parity with SLAM crash (type=crash_fallback, payload.subsystem, crashed_backend, fallback_backend, reason)"
    - "Test fixture registers fake backends so fallback path runs without ultralytics/torch"

key-files:
  created:
    - ".planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-09-SUMMARY.md"
  modified:
    - "src/perception/worker_pool.py — on_backend_crash, set_streaming_viz, _dummy_frame_for, pool_ref=self at DetectorWorker construction"
    - "src/perception/worker.py — pool_ref kwarg, BridgeHangError/SubprocessDiedError catch in _loop, _backend_registry_name helper, split lift try/except"
    - "tests/perception/test_crash_fallback.py — activated 3 Wave 2 tests, added pool_registry fixture with _FakeYolo + _FakeLifter + fake boxer row"

key-decisions:
  - "Worker catches typed exceptions (BridgeHangError, SubprocessDiedError) and skips the frame rather than retrying inline — next submit picks up with swapped detector, avoiding reentrancy hazards"
  - "Fallback failure is swallowed+logged rather than re-raised: a failed fallback is still better than leaving the caller thread with a dead bridge"
  - "Split detector.process_frame try/except from lifter try/except in worker._loop so lifter bugs never trigger the crash-fallback path"
  - "Pool registers fake 'boxer' row in tests so set_available has a deterministic target regardless of whether real BoxeR is importable"

patterns-established:
  - "D-03 crash-fallback: typed bridge exception in worker → pool.on_backend_crash(name, reason) → WS emit → registry lockout → per-worker warmup+atomic swap"
  - "pool_ref reverse edge: workers escalate session-affecting events to the pool; pool handles WS + registry side effects"

requirements-completed: [DET-MODELS-06]

# Metrics
duration: ~25min (split across two agents; ~5min for this continuation)
completed: 2026-04-14
---

# Phase 05 Plan 09: Pool Crash Handler + Worker Typed-Except Summary

**DetectorWorkerPool.on_backend_crash wires typed-exception-driven backend swap with SLAM-parity WS envelope and D-04 registry lockout; DetectorWorker escalates BridgeHangError/SubprocessDiedError via reverse pool_ref.**

## Performance

- **Duration:** ~25 min (cross-agent; this continuation ~5 min)
- **Completed:** 2026-04-14
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments
- Wired DetectorWorkerPool.on_backend_crash with the full D-03 flow: WS emit → registry lockout → per-worker fallback construction + warmup → atomic ref swap under _swap_lock.
- DetectorWorker now catches BridgeHangError/SubprocessDiedError at the detector.process_frame call site and escalates to pool.on_backend_crash(crashed_backend, reason); next loop iteration runs with the swapped detector.
- All 5 crash_fallback tests green (2 from Plan 05, 3 activated here) — no skips remaining in test_crash_fallback.py.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add on_backend_crash to pool + typed-except in worker** — `7f80805` (feat)
2. **Task 2: Activate the three remaining crash_fallback tests** — `91e390b` (test)

**Plan metadata:** [this commit] (docs: complete plan)

## Files Created/Modified
- `src/perception/worker_pool.py` — +177 lines. on_backend_crash method, set_streaming_viz setter, _streaming_viz attr, _dummy_frame_for helper, BridgeHangError/SubprocessDiedError import, DetectorWorker construction with pool_ref=self.
- `src/perception/worker.py` — +79/-5 lines. pool_ref kwarg + _pool_ref attr, BridgeHangError/SubprocessDiedError import, typed-except around detector.process_frame calling pool.on_backend_crash, _backend_registry_name helper, split lift try/except.
- `tests/perception/test_crash_fallback.py` — +235/-9 lines. Added _FakeYolo + _FakeLifter classes, pool_registry fixture (registers "yolov11"→_FakeYolo, "boxer"→_FakeYolo, "median_depth"→_FakeLifter with save+restore of prior registry state), activated test_pool_on_backend_crash_emits_ws_message, test_pool_swaps_to_yolo (with warmup_count assertion), test_pool_marks_crashed_backend_unavailable.

## Success Criteria Met
- [x] on_backend_crash emits SLAM-pattern WS envelope (type=crash_fallback, payload.subsystem=detector, crashed_backend, fallback_backend=yolov11, reason).
- [x] Atomic YOLOv11 swap works across N workers under _swap_lock.
- [x] D-04 registry lockout wired — DetectorRegistry.set_available(name, False, reason).
- [x] All 5 crash_fallback tests green (2 Plan-05 + 3 activated here); 0 pytest.skip remain.
- [x] Phase 2/4 pool tests unaffected (test_worker_pool + test_worker_backpressure + test_worker_capture_pose + test_worker_pool_lifter_params = 21 passed).
- [x] Phase 2 subprocess bridge lock intact (test_subprocess_bridge_skeleton — 17 passed).

## Verification Commands & Results
- `uv run pytest tests/perception/test_crash_fallback.py -x --timeout=30 -v` → 5 passed.
- `uv run pytest tests/perception/test_subprocess_bridge_skeleton.py -x --timeout=30` → 17 passed.
- `uv run pytest tests/perception/test_worker_pool.py tests/perception/test_worker_backpressure.py tests/perception/test_worker_capture_pose.py tests/perception/test_worker_pool_lifter_params.py --timeout=60` → 21 passed.
- All grep acceptance checks pass: on_backend_crash=1, set_streaming_viz=1, streaming_viz refs=12 (≥3), "type":"crash_fallback"=1, "subsystem":"detector"=1, DetectorRegistry.set_available=1 in worker_pool.py; BridgeHangError|SubprocessDiedError=2 (≥2), pool_ref=4 (≥2) in worker.py; pool_ref=self=1 in worker_pool.py; pytest.skip=0 in test file.

## Deviations from Plan
None — plan executed as written.

The prior agent (worktree agent-aea2d4b5) split lifter invocation into its own try/except (outside Plan 09's task list but architecturally consistent with D-03 — ensures lifter bugs cannot trigger the crash-fallback path designed for detector subprocess death). Documented here as an intentional correctness refinement rather than a deviation.

## Out-of-Scope Observations
- `tests/perception/test_lifter_hotswap.py` errors at setup with `ModuleNotFoundError: No module named 'fastapi'`. Verified pre-existing (reproduces without Plan 09's diff applied). Out of Plan 09's scope — test env missing fastapi is a separate install/env concern.

## Self-Check: PASSED
- Commit 7f80805 confirmed in `git log`.
- Commit 91e390b confirmed in `git log`.
- `src/perception/worker_pool.py` confirmed modified (on_backend_crash grep=1).
- `src/perception/worker.py` confirmed modified (BridgeHangError grep=2).
- `tests/perception/test_crash_fallback.py` confirmed modified (pytest.skip grep=0).
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-09-SUMMARY.md` created by this writer.
