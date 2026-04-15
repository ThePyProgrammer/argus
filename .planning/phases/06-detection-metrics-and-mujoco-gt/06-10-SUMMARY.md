---
phase: 6
plan: 10
subsystem: coordinator + perception + cli
tags: [perception, metrics, coordinator, integration, cli, gt-extractor]
requires: [06-04, 06-07, 06-08]
provides:
  - "Coordinator._send_viz_update detection-metrics pump (DET-METRICS-01/02)"
  - "Coordinator bootstrap wiring of streaming_viz.attach_gt_extractor (BLOCKER 2)"
  - "DetectorWorker.detector public property (RESEARCH F3)"
  - "DetectorWorkerPool.workers_by_robot() public accessor"
  - "MultiBridge.mj_model + mj_data public properties (RESEARCH Pitfall 8)"
  - "src/main.py --labeled-eval-set CLI reservation (DET-METRICS-03 / CONTEXT D-10)"
affects:
  - "Plan 11 frontend now receives non-zero detection_metrics / detection_gt_metrics"
  - "Plan 09 export endpoint now receives real OBBs via detection_export.append"
tech-stack:
  added: []
  patterns: ["hasattr-guarded pump", "graceful-degradation extractor", "lazy import for optional deps"]
key-files:
  created:
    - "tests/integration/test_gt_extractor_attach.py"
  modified:
    - "src/perception/worker.py"
    - "src/perception/worker_pool.py"
    - "src/bridge/multi_bridge.py"
    - "src/coordination/coordinator.py"
    - "src/main.py"
    - "tests/test_main_args.py"
decisions:
  - "Use sim clock (frames[rid].sim_time) for pump sim_now per RESEARCH Pitfall 4 — never time.time()"
  - "Consume match_detection return value via tracker.record_gt_match (SC#2 end-to-end, not discard)"
  - "Attach GT extractor via set_viz AND run() post-bridge.start() — idempotent two-phase attach so it works regardless of bridge lifecycle at set_viz time"
  - "Lazy-import uvicorn inside run_web_mode so CLI flag test can run without web-server deps"
  - "Subprocess-only test for --labeled-eval-set (no argparse-only fallback) per WARNING 5 — the raise is load-bearing"
metrics:
  duration_minutes: 12
  commits: 4
  tasks_completed: 3
  files_created: 1
  files_modified: 6
  tests_added: 3
  tests_passing: 3
completed: 2026-04-15
---

# Phase 6 Plan 10: Coordinator Detection-Metrics Pump + GT Extractor Bootstrap + CLI Reservation Summary

One-liner: Pumped detection-metrics + GT-matching into the per-tick coordinator loop (consuming match_detection return value via record_gt_match, not discarding), wired attach_gt_extractor at coordinator bootstrap (BLOCKER 2), and reserved `--labeled-eval-set` CLI flag with NotImplementedError per CONTEXT D-10.

## What Was Built

### Task 1 — Public accessors for pump consumers (commits 59f0a94 + 724ea9a)

**Gap closed:** RESEARCH F3 (no public `DetectorWorker.detector` accessor) + RESEARCH Pitfall 8 (`MultiBridge.mj_model`/`mj_data` private).

- `src/perception/worker.py`: added `@property detector` on `DetectorWorker` returning `self._detector`. Intentionally un-annotated at runtime (duck-typed) — `DetectorProtocol` is TYPE_CHECKING-only to preserve P9 torch-free module invariant.
- `src/perception/worker_pool.py`: added `workers_by_robot() -> dict[str, DetectorWorker]` returning a shallow copy of the rid→worker map. Shallow copy prevents external mutation of pool internals; worker instances themselves remain live for per-tick state reads.
- `src/bridge/multi_bridge.py`: added `@property mj_model` + `@property mj_data` read-only accessors over private `_model` / `_data`. Return None before `start()` — callers guard with `hasattr` + `is not None`.

### Task 2 — Coordinator pump + CLI flag + real test (commit a1827ad)

**Gap closed:** SC#1 (detection pump not wired) + SC#2 (match_detection return was previously discarded in the revised plan) + D-10 (CLI flag unreserved).

- `src/coordination/coordinator.py::_send_viz_update`: added the Phase 6 pump block immediately after the existing SLAM pump. Per robot per tick: calls `det_tracker.record_frame(...)`, appends each OBB via `det_export.append(...)`, and CONSUMES `match_detection` return via `det_tracker.record_gt_match(robot_id, class_name, center_err_m, matched=(err is not None))`. Uses `float(frames[robot_ids[0]].sim_time)` for `sim_now` (Pitfall 4). `hasattr` guard so pre-Phase-6 viz objects no-op silently.
- `src/main.py::parse_args`: added `--labeled-eval-set PATH` argument with the reserved-feature help text referencing CONTEXT D-10.
- `src/main.py::main()`: raises `NotImplementedError("Labeled eval set ingestion arrives in a future milestone")` BEFORE any heavy init (coordinator / bridge / scene loading) so the CLI test is fast and deterministic.
- `src/main.py`: lazy-imported `uvicorn` inside `run_web_mode` (was module-scope `import uvicorn`) so `src.main` is importable in environments without the web-server deps — unblocks the subprocess CLI test on systems with partial dep installs.
- `tests/test_main_args.py`: replaced the Wave-0 `pytest.skip(...)` stub with a real subprocess invocation that asserts non-zero exit, the exact CONTEXT D-10 message, and `NotImplementedError` in the traceback. No argparse-only fallback (WARNING 5 fix).

### Task 3 — GT extractor bootstrap + integration test (commit a11b698)

**Gap closed:** BLOCKER 2 (plan-checker iteration 2/3 flagged that nothing actually called `streaming_viz.attach_gt_extractor`) + WARNING 6 (no test covered scene_office1_gt.yaml against the real scene).

- `src/coordination/coordinator.py`: introduced `_attach_gt_extractor_if_possible()` helper invoked from BOTH `set_viz` (early, optimistic — works when constructing with a started bridge) AND `run()` immediately after `self._bridge.start()` (guaranteed usable). The second call is idempotent: once `viz.gt_extractor is not None`, subsequent calls early-return. Graceful no-op if viz missing `attach_gt_extractor`, if bridge lacks `mj_model`/`mj_data`, or if the YAML file doesn't exist in this checkout.
- `tests/integration/test_gt_extractor_attach.py` (NEW, 85 lines, 2 tests):
  1. `test_scene_office1_gt_mapping_resolves` — loads REAL `scene_office1.xml` + `scene_office1_gt.yaml`, constructs `MuJoCoGTExtractor`, asserts `"chair" in all_classes()`, and walks every mapped body to confirm `mj_name2id` > 0 AND at least one geom exists (required by RESEARCH F1 — `data.geom_xpos[first_geom_of_body]` is the lookup path).
  2. `test_streaming_viz_attach_gt_extractor_end_to_end` — constructs `WebStreamingViz` with a minimal `ConnectionManager`, asserts `viz.gt_extractor is None` pre-attach, calls `viz.attach_gt_extractor(GT_YAML, model, data)`, asserts post-attach is non-None with `"chair"` in `all_classes()`.
  Both tests honest-skip if the scene/YAML artifacts are absent (release-gate environments that ship without the MuJoCo scene bundle).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Lazy-import `uvicorn` inside `run_web_mode`**
- **Found during:** Task 2 (CLI test execution)
- **Issue:** `src/main.py` had module-scope `import uvicorn`. The subprocess CLI test (`python -m src.main --labeled-eval-set /tmp/eval.json`) failed with `ModuleNotFoundError: No module named 'uvicorn'` at import time — BEFORE reaching `main()` where the NotImplementedError raises.
- **Fix:** Moved `import uvicorn` into `run_web_mode` as a lazy import; left a comment at the original site explaining why.
- **Files modified:** `src/main.py`
- **Commit:** a1827ad

**2. [Rule 3 - Blocking] Second-phase attach of GT extractor in `Coordinator.run()`**
- **Found during:** Task 3 (reading main.py run_web_mode lifecycle)
- **Issue:** Plan called for the attach at `set_viz` only, but in `run_web_mode` `coordinator.set_viz(streaming_viz)` is called BEFORE `coordinator.run()` invokes `bridge.start()`. At `set_viz` time `mj_model`/`mj_data` are None — attach would always no-op.
- **Fix:** Factored a `_attach_gt_extractor_if_possible()` helper. `set_viz` calls it optimistically (works for test fixtures that pre-start the bridge); `run()` calls it again post-`bridge.start()` (guaranteed usable). Helper is idempotent — early-returns once `gt_extractor is not None`.
- **Files modified:** `src/coordination/coordinator.py`
- **Commit:** a11b698

**3. [Rule 1 - Bug] Restored Task 1 accessors clobbered by stash-pop collision**
- **Found during:** Post-Task-3 verification
- **Issue:** During regression-test verification I used `git stash` + `git checkout <base> -- <files>` to compare against baseline, then `git stash pop`. The pop-merge with the concurrently-staged Task 3 changes clobbered the Task 1 additions in the working tree; the Task 3 commit then persisted the regression.
- **Fix:** Re-applied the Task 1 diff (`git diff BASE 59f0a94 -- <files> | git apply`) and committed as `fix(06-10): restore Task 1 accessors lost to stash-pop collision` (724ea9a). Verified `DetectorWorker.detector`, `DetectorWorkerPool.workers_by_robot`, and `MultiBridge.mj_model`/`mj_data` are present via Python import-time checks.
- **Files modified:** `src/perception/worker.py`, `src/perception/worker_pool.py`, `src/bridge/multi_bridge.py`
- **Commit:** 724ea9a

### Out-of-Scope (deferred, not fixed)

8 pre-existing perception test failures (`tests/perception/test_lifter_hotswap.py`, `test_point_cluster_lifter.py`, `test_rtdetrv2_backend.py::test_construct_registers_in_registry`) — each test passes in isolation but fails in the full pytest run. Baseline verified by `git checkout 6a9cf81` → same 8 failures + 257 passed, confirming these are pre-existing test-interaction / state-leak issues unrelated to Plan 6-10 scope (SCOPE BOUNDARY rule applied). Not this plan's responsibility.

## Commits

| Hash | Message |
|------|---------|
| 59f0a94 | feat(06-10): add public accessors for detection-metrics pump (F3 + Pitfall 8) |
| a1827ad | feat(06-10): wire detection-metrics pump + reserve --labeled-eval-set CLI |
| a11b698 | feat(06-10): wire attach_gt_extractor at coordinator bootstrap + integ test |
| 724ea9a | fix(06-10): restore Task 1 accessors lost to stash-pop collision |

## Verification

- `grep -c 'record_gt_match' src/coordination/coordinator.py` → 2 (SC#2 BLOCKER 1 — match_detection return CONSUMED, not discarded)
- `grep -c 'record_frame' src/coordination/coordinator.py` → 2 (SC#1 pump present)
- `grep -c 'attach_gt_extractor' src/coordination/coordinator.py` → 9 (BLOCKER 2 wired; helper-oriented design)
- `grep -c '@property' src/perception/worker.py` → 1 (F3 accessor added — Python descriptor check confirms)
- `grep -c 'labeled-eval-set\|labeled_eval_set' src/main.py` → 6 (D-10 CLI reserved)
- `grep -c 'NotImplementedError' src/main.py` → 4
- `grep -c 'parse_args' tests/test_main_args.py` → 0 (subprocess-only test; WARNING 5 fix)
- `pytest tests/test_main_args.py tests/integration/test_gt_extractor_attach.py -v --timeout=60` → 3 passed
- `pytest tests/metrics/ -q --timeout=30` → 18 passed (no SLAM metric regression)

## Self-Check: PASSED

- All acceptance criteria met
- All three tests pass (1 CLI subprocess + 2 integration)
- No regression in metrics/ tests
- Pre-existing perception/ test failures confirmed as baseline (not introduced by this plan)
- All 4 commits present on current branch
- SC#2 end-to-end delivery confirmed: `match_detection` return value is consumed via `record_gt_match`, not discarded
