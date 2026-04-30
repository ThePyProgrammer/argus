---
phase: 07-pipeline-editor-perception-nodes
plan: 09
subsystem: api

tags: [fastapi, pipeline, hot-apply, detector-swap, lifter-swap, diff-dispatch]

# Dependency graph
requires:
  - phase: 07
    provides: "PipelineBuilder perception fields (Plan 04), pool.swap_backend (Plan 05)"
provides:
  - "apply_pipeline diff-then-dispatch REST handler"
  - "_digest_topology helper for stable graph topology comparison"
  - "server-side decision between hot-apply (no restart) and coordinator restart"
  - "pool.swap_backend + pool.swap_lifter direct dispatch from /api/pipeline/apply"
  - "app.state.last_applied_topology_digest lifecycle (both paths update)"
  - "app.state.last_applied_pipeline_config lifecycle (hot-apply writes; restart defers to main.py per Plan 11)"
affects: [07-10, 07-11, Phase 08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "strict-AND diff (CONTEXT D-10): topology_digest + all non-perception fields unchanged => hot-apply eligibility"
    - "pool direct-call on REST handler (mirrors detector_routes.py::lifter_hotswap)"
    - "digest baseline written on BOTH restart and hot-apply so next diff is always valid"

key-files:
  created:
    - "tests/integration/test_pipeline_apply_hot.py (filled — 6 tests, was Wave 0 skip stub)"
    - ".planning/phases/07-pipeline-editor-perception-nodes/deferred-items.md"
  modified:
    - "backend/web/pipeline_routes.py (+_digest_topology helper + diff-then-dispatch apply_pipeline)"

key-decisions:
  - "Test fixture registers SLAM + merger backends directly via SLAMRegistry.register / MergeRegistry.register instead of importing src.slam.backends, which transitively pulls in open3d (unavailable in this env)"
  - "Wrap non-ValueError/ImportError swap_backend exceptions in a broad except + log.exception + 400 response, matching Pitfall 8 rollback semantics (pool untouched on failure)"
  - "Both hot-apply and restart paths update last_applied_topology_digest so the next apply can compute a valid diff even if the restart path never finishes committing last_applied_pipeline_config"

patterns-established:
  - "Pattern: server-side graph diff with strict-AND classifier — any deviation outside the perception-only whitelist falls through to the existing restart path"
  - "Pattern: integration tests mock app.state.detector_pool + command_callback so the handler can be exercised without booting a coordinator"

requirements-completed: [DET-PIPELINE-05]

# Metrics
duration: ~15min
completed: 2026-04-15
---

# Phase 07 Plan 09: apply_pipeline Diff-Then-Dispatch Summary

**apply_pipeline now computes a topology + PipelineConfig diff and routes perception-only changes to pool.swap_backend / pool.swap_lifter directly, returning `{"status": "hot-applied", ...}` without a coordinator restart.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-15
- **Completed:** 2026-04-15
- **Tasks:** 1
- **Files modified:** 2 (1 implementation, 1 test)
- **Files created:** 1 (deferred-items.md)

## Accomplishments

- `_digest_topology(nodes, edges)` helper produces a stable tuple of `(sorted_node_ids, sorted_edge_tuples)` for O(n log n) diff comparison.
- `apply_pipeline` now implements CONTEXT D-10 strict-AND diff: topology unchanged AND backend/merger/filter/tracker unchanged AND (detector or lifter changed) ⇒ hot-apply; otherwise restart path.
- Hot-apply calls `pool.swap_backend(name, params)` and/or `pool.swap_lifter(name, params)` directly, updates `app.state.active_detector_backend`, `active_lifter`, `pending_detector_params`, `pending_lifter_params`, `last_applied_pipeline_config`, `last_applied_topology_digest`, then returns `{"status": "hot-applied", "changed": [...], "active_detector": ..., "active_lifter": ...}`.
- Restart path preserved: stashes `pending_pipeline_config`, updates digest, calls `command_callback({"action": "restart"})`, returns `{"status": "restarting"}`. `last_applied_pipeline_config` is deliberately NOT written here — main.py commits it after a successful restart (Plan 07-11, CONTEXT D-12).
- Error taxonomy: 422 (PipelineBuilder ValueError) / 400 (swap_backend or swap_lifter ValueError/ImportError/warmup failure) / 503 (detector_pool missing).
- Integration test suite `tests/integration/test_pipeline_apply_hot.py`: 6/6 PASS. Pre-existing `tests/web/test_pipeline_routes.py`: 6/6 still PASS (no regression).

## Task Commits

1. **Task 1 RED — Add failing tests for hot-apply diff-then-dispatch** — `8d3f6cb` (test)
2. **Task 1 GREEN — diff-then-dispatch apply_pipeline with hot-apply path** — `6682dfd` (feat)
3. **Deferred items log (pre-existing open3d collection errors)** — `477f548` (chore)

_Plan metadata commit follows this SUMMARY._

## Files Created/Modified

- `backend/web/pipeline_routes.py` — replaced `apply_pipeline` body with diff-then-dispatch; added `_digest_topology` helper at module scope; expanded module docstring to document CONTEXT D-10 behavior. Other handlers (`node_catalog`, presets) untouched.
- `tests/integration/test_pipeline_apply_hot.py` — removed Wave-0 `pytest.skip`; added 6 end-to-end tests exercising baseline restart, detector hot-apply, topology-change restart, SLAM-change restart, last_applied_pipeline_config update, and swap_backend failure. Fixture registers `icp`, `orbslam3`, `icp_union` directly (avoids open3d transitive import).
- `.planning/phases/07-pipeline-editor-perception-nodes/deferred-items.md` — logs pre-existing open3d ModuleNotFoundError affecting ~30 unrelated tests on the base commit.

## Decisions Made

1. **Fixture registers backends directly (not via `src.slam.backends` import).** The apply handler only reads registry membership, never resolves the backend class path, so bypassing the heavy import keeps the test fast AND portable to environments without open3d. Mirrors the pattern in `tests/web/test_pipeline_routes.py`.
2. **Add catch-all `except Exception` branch around `swap_backend`.** Protects against warmup crashes in registered-but-broken backends (Pitfall 8 rollback semantics). Logged via `logger.exception` and surfaced as HTTP 400.
3. **Update `last_applied_topology_digest` on the restart path too.** Otherwise the next apply after the first-ever restart would still see `last_topology == None` and route back through restart, breaking subsequent hot-apply decisions.
4. **Write `last_applied_pipeline_config` ONLY on hot-apply success.** Per CONTEXT D-12, main.py owns this lifecycle on the restart path because the coordinator might fail to boot and we don't want to mark a bad config as "last successfully applied".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Test fixture populated registries via side-effect imports that pulled open3d**

- **Found during:** Task 1 (GREEN phase — first test run after implementation)
- **Issue:** The plan-specified fixture used `import src.perception.backends` + lifters + trackers, but the test graph also exercises `slam_icp` and `merger_icp_union`, which PipelineBuilder validates against SLAMRegistry and MergeRegistry. Without `src.slam.backends` imported, PipelineBuilder raises `ValueError: Unknown SLAM backend: icp. Available: []` ⇒ all 6 tests 422. Attempting to import `src.slam.backends` cascades to `open3d` which isn't installed in this env.
- **Fix:** Fixture now calls `SLAMRegistry.register("icp", ...)` and `SLAMRegistry.register("orbslam3", ...)` and `MergeRegistry.register("icp_union", ...)` directly (matches `tests/web/test_pipeline_routes.py` pattern). Class paths are registered but never resolved — the apply handler only reads names. Still imports the lifter/tracker/detector modules because those are lightweight and register via decorator side-effect.
- **Files modified:** `tests/integration/test_pipeline_apply_hot.py`
- **Verification:** 6/6 tests green; `tests/web/test_pipeline_routes.py` still 6/6 green.
- **Committed in:** `6682dfd` (bundled with the GREEN implementation)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary fix; does not alter handler behavior or acceptance criteria. The test is arguably MORE correct this way because it exercises the handler in isolation without dragging in the SLAM pipeline.

## Issues Encountered

- Pre-existing open3d ModuleNotFoundError affects ~30 unrelated tests in `tests/web/`, `tests/coordination/`, `tests/perception/`. Confirmed pre-existing via `git stash`. Out of scope for this plan. Documented in `deferred-items.md`.

## Self-Check: PASSED

- `_digest_topology` helper present: 1 hit (def) + 3 call sites ✅
- `"status": "hot-applied"` present: 3 hits (docstring + return + comment) ✅
- `"status": "restarting"` present: 2 hits (docstring + return) ✅
- `pool.swap_backend` present: 3 hits ✅
- `pool.swap_lifter` present: 2 hits ✅
- `last_applied_topology_digest` present: 3 hits (read + hot-apply write + restart write) ✅
- `last_applied_pipeline_config` present: 3 hits (read + hot-apply write + main-docstring note) ✅
- `pytest.skip` in test: 0 hits ✅
- `pytest tests/integration/test_pipeline_apply_hot.py -x -v`: 6 passed ✅
- `pytest tests/web/test_pipeline_routes.py -v`: 6 passed (no regression) ✅
- Commits verified: 8d3f6cb (test RED), 6682dfd (feat GREEN), 477f548 (chore deferred)

## Next Plan Readiness

- `apply_pipeline` now emits `{"status": "hot-applied", ...}` that Plan 07-10 (UI toast) can key off.
- `app.state.last_applied_pipeline_config` write-on-hot-apply is in place; Plan 07-11 only needs to handle the restart-path write in main.py after a successful coordinator boot.
- No blockers for Plan 07-10 or 07-11.

---
*Phase: 07-pipeline-editor-perception-nodes*
*Completed: 2026-04-15*
