---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 10
subsystem: integration
tags: [crash-fallback, websocket, streaming-viz, frontend-wiring, d-03]

# Dependency graph
requires:
  - phase: 05-second-backends-boxer-rtdetr-owlv2
    provides: "Plan 09 DetectorWorkerPool.set_streaming_viz + on_backend_crash; Plan 08 BoxeR composer; Plan 07 RT-DETRv2 backend"
  - phase: 03-detector-dropdown-lifter-ui
    provides: "detectorStore.crashMessage + setCrashMessage; CrashToast component; useWebSocket crash_fallback handler scaffold with SLAM branch"
provides:
  - "main.py restart block wires streaming_viz into DetectorWorkerPool via set_streaming_viz() post-start"
  - "useWebSocket.ts detector-subsystem crash_fallback branch — populates detectorStore.crashMessage + setActive(fallback_backend)"
  - "End-to-end D-03 path complete: subprocess crash -> pool.on_backend_crash -> WS envelope -> detectorStore -> CrashToast render"
affects: [05-11-download-integration, 05-12-e2e-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred streaming_viz wiring via post-construction setter (pool rebuild happens in the restart block where streaming_viz is in scope)"
    - "SLAM/detector symmetry in useWebSocket crash_fallback handler — same envelope shape, same textContent render path, same setActive fallback mirror"
    - "Unknown-subsystem console.warn fallback for forward-compatibility with future subsystems"

key-files:
  created:
    - ".planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-10-SUMMARY.md"
  modified:
    - "src/main.py — +4 lines: if streaming_viz is not None: detector_pool.set_streaming_viz(streaming_viz) + 'Phase 5 D-03' comment, inside the detector-pool try block after warmup_all + start"
    - "frontend/src/hooks/useWebSocket.ts — +10 -3 lines: replaced 4-line console.log placeholder with real else-if (subsystem === 'detector') branch calling detectorStore.setCrashMessage + setActive(payload.fallback_backend, 'YOLOv11-nano', {}); added console.warn else-clause for unknown subsystems"

key-decisions:
  - "Setter over constructor kwarg for streaming_viz wiring — pool is constructed inside a try block that catches pool-rebuild failures; keeping streaming_viz as a post-construction setter avoids coupling the construction failure path to streaming_viz availability"
  - "Use payload.fallback_backend (dynamic) for detectorStore.setActive first arg instead of hardcoded 'yolov11' — forward-compat with any future fallback choice the pool decides"
  - "Preserve SLAM branch verbatim — Plan 10 is strictly additive for the detector branch"
  - "Added explicit console.warn for unknown subsystems (instead of silent log) — future subsystem additions will surface immediately during development"

patterns-established:
  - "D-03 completion path: pool emits WS envelope with subsystem field; frontend router dispatches on subsystem to the correct store's setCrashMessage + setActive"
  - "Post-warmup streaming_viz wiring in main.py restart block: call set_streaming_viz AFTER warmup_all + start so the pool is fully operational before the WS queue is wired"

requirements-completed: [DET-MODELS-02, DET-MODELS-03, DET-MODELS-06]

# Metrics
duration: ~2min
completed: 2026-04-15
---

# Phase 05 Plan 10: main.py streaming_viz wiring + useWebSocket detector crash branch Summary

**Closes D-03 crash_fallback path end-to-end: main.py hooks streaming_viz into DetectorWorkerPool via set_streaming_viz so pool.on_backend_crash can enqueue WS messages, and useWebSocket.ts routes subsystem='detector' crash_fallback envelopes to detectorStore.setCrashMessage + setActive(fallback_backend) so CrashToast (shipped Phase 3) renders on detector subprocess crashes.**

## Performance

- **Duration:** ~2 min
- **Completed:** 2026-04-15
- **Tasks:** 2/2
- **Files modified:** 2 (src/main.py, frontend/src/hooks/useWebSocket.ts)

## Accomplishments
- Added 4-line main.py insertion (comment + if-guard + setter call) between detector_pool.start() and coordinator._detector_pool = detector_pool. Pool now has the StreamingVisualizer ref it needs for on_backend_crash to enqueue the crash_fallback WS envelope.
- Replaced the Phase 3 placeholder console.log in useWebSocket.ts crash_fallback handler with a real detector branch: setCrashMessage(`Backend X crashed, fell back to Y`) + setActive(payload.fallback_backend, 'YOLOv11-nano', {}). Added console.warn for unknown subsystems.
- End-to-end D-03 flow is now complete:
  1. Subprocess dies -> SubprocessDetectorBridge raises BridgeHangError/SubprocessDiedError
  2. DetectorWorker catches and escalates to pool.on_backend_crash (Plan 09)
  3. Pool appends crash_fallback envelope to streaming_viz._message_queue (Plan 10 wires this)
  4. StreamingVisualizer flushes the message via WS to frontend
  5. useWebSocket routes subsystem='detector' to detectorStore.setCrashMessage (Plan 10 finishes this)
  6. CrashToast (Phase 3 shipped) reads detectorStore.crashMessage and renders

## Task Commits

Each task was committed atomically with --no-verify (parallel Wave 5 execution — orchestrator runs pre-commit hooks once after both Wave 5 agents complete):

1. **Task 1: Wire streaming_viz into DetectorWorkerPool in main.py restart block** — `c388baf` (feat)
2. **Task 2: Replace useWebSocket.ts console.log placeholder with setCrashMessage + setActive** — `324a13f` (feat)

## Files Created/Modified
- `src/main.py` — +4 lines. Inside the restart block's detector-pool try block, between `detector_pool.start()` and `coordinator._detector_pool = detector_pool`, added:
  ```python
  # Phase 5 D-03 — wire streaming_viz so pool.on_backend_crash
  # can append crash_fallback messages to the WS queue.
  if streaming_viz is not None:
      detector_pool.set_streaming_viz(streaming_viz)
  ```
- `frontend/src/hooks/useWebSocket.ts` — +10 / -3 lines. Replaced `else { console.log(...) }` with `else if (subsystem === 'detector') { detectorStore.setCrashMessage(...); detectorStore.setActive(payload.fallback_backend, 'YOLOv11-nano', {}); } else { console.warn(...) }`.

## Success Criteria Met
- [x] src/main.py calls `detector_pool.set_streaming_viz(streaming_viz)` post-construction (after warmup_all + start) — grep=1.
- [x] src/main.py has comment referencing "Phase 5 D-03" — grep=1.
- [x] useWebSocket.ts routes `subsystem === 'detector'` crash_fallback to detectorStore.setCrashMessage — grep=1.
- [x] useWebSocket.ts calls detectorState.setActive(payload.fallback_backend, ...) — grep=1.
- [x] Placeholder comment "Phase 5 DET-MODELS-06 will handle subsystem" is gone — grep=0.
- [x] SLAM branch preserved verbatim — unchanged.
- [x] console.warn unknown-subsystem fallback added — grep=1.
- [x] src/main.py parses: `uv run python -c "import ast; ast.parse(open('src/main.py').read())"` exits 0.
- [x] Each task committed individually with `--no-verify`.
- [x] SUMMARY.md created.

## Verification Commands & Results
- `uv run python -c "import ast; ast.parse(open('src/main.py').read())"` -> exits 0 (ast-parse-ok).
- `uv run pytest tests/perception/test_worker_pool.py tests/perception/test_crash_fallback.py -x --timeout=60` -> 15 passed.
- Grep matrix on useWebSocket.ts:
  - `detectorState.setCrashMessage` -> 1
  - `detectorState.setActive(payload.fallback_backend` -> 1
  - `Phase 5 DET-MODELS-06 will handle subsystem` -> 0 (placeholder gone)
  - `else if (subsystem === 'detector')` -> 1
  - `console.warn` -> 1
  - `useDetectorStore` -> 3 (import + this hook's getState + fetchDetectorState chain)
  - `from '../stores/detectorStore'` -> 1
- TypeScript compile: frontend/node_modules absent at plan time; `npx tsc` not installed. Per Plan 10 acceptance criteria this gate is skipped ("if tsc is not installed at plan time, skip this gate").

## Deviations from Plan
None — plan executed exactly as written.

## Parallel-Wave Notes
Plan 10 executed in parallel with Plan 12 (orchestrator Wave 5). Both used `--no-verify` per the parallel-execution contract; orchestrator is responsible for running the pre-commit hook once after both agents complete.

## Threat-Model Disposition
- **T-5-02 (Tampering of crash_fallback message rendered in frontend):** mitigated — React renders `detectorStore.crashMessage` via textContent (CrashToast component, Phase 3), not innerHTML. Strings embedded in the message come from pool-owned code (`type(exc).__name__: {exc}` format from Plan 09), not remote-controlled input. No new attack surface introduced by Plan 10's two-line wiring.

## Self-Check: PASSED
- Commit `c388baf` confirmed in `git log`.
- Commit `324a13f` confirmed in `git log`.
- `src/main.py` modified — `Phase 5 D-03` grep=1, `detector_pool.set_streaming_viz(streaming_viz)` grep=1.
- `frontend/src/hooks/useWebSocket.ts` modified — `else if (subsystem === 'detector')` grep=1, `detectorState.setCrashMessage` grep=1, placeholder comment grep=0.
- `.planning/phases/05-second-backends-boxer-rtdetr-owlv2/05-10-SUMMARY.md` created by this writer.
