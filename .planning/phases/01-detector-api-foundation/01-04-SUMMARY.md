---
phase: 01-detector-api-foundation
plan: 04
subsystem: perception
tags: [perception, lifter, median-depth, projection, consolidation, P3, Detection3DProtocol]

requires:
  - phase: 01-detector-api-foundation
    provides: Detection3DProtocol, OrientedBox3D skeleton, Detections3D, Detection3DRegistry, @detection_3d decorator
provides:
  - MedianDepthLifter registered under "median_depth" implementing Detection3DProtocol
  - project_center_median_depth() — the SINGLE source of median-depth 2D→3D projection math
  - src/perception/lifters/ package with side-effect-import __init__.py (mirrors src/slam/backends/)
  - ObjectDetector._detect() rewired to delegate to MedianDepthLifter (behavior-preserving)
  - 13 contract tests for lifter + detector delegation invariant
affects: [phase-01-plan-05 YOLOv11+regression, phase-02 DetectorWorker wiring, phase-04 PointClusterLifter]

tech-stack:
  added: []
  patterns:
    - "Lifter package side-effect registration (from src.perception.lifters import median_depth)"
    - "Lazy import pattern inside hot path (ObjectDetector._detect imports project_center_median_depth inline to avoid module-load-time circular imports)"
    - "Single-source projection math (no inline geometry in consumers; all routes through project_center_median_depth)"
    - "Identity-quaternion placeholder for lifters that cannot recover orientation (outputs_oriented=False)"

key-files:
  created:
    - src/perception/lifters/__init__.py
    - src/perception/lifters/median_depth.py
    - tests/perception/test_median_depth_lifter.py
  modified:
    - src/perception/detector.py

key-decisions:
  - "Hardcoded 70° vertical FOV preserved in MedianDepthLifter (not using CameraIntrinsics yet) — preserves bit-exact parity with pre-refactor detector.py math per CONTEXT.md D-13; Phase 4's src/perception/geometry.py retires the hardcode."
  - "project_center_median_depth() exposed as module-level function, not instance method — lets detector.py import it directly without instantiating the lifter class (avoids YOLO dependency on the legacy detector path)."
  - "detector.py uses LAZY (function-body) import of project_center_median_depth to sidestep any potential circular-import issues during coordinator.py top-level imports."
  - "slam_cloud argument accepted but silently ignored (documented in docstring) — D-04 protocol compliance; PointClusterLifter in Phase 4 will be the first consumer."
  - "detection_3d.py::project_detections_to_3d left as-is for now (Phase 1 coexisting shim per CONTEXT.md D-11); no consumer references it after Plan 04 — it's effectively dead code awaiting Phase 4 cleanup."

patterns-established:
  - "Lifter registration: @detection_3d(name, display) decorator at class-definition time; import from lifters/__init__.py triggers side-effect"
  - "Consumer delegation: any code needing median-depth 2D→3D projection imports project_center_median_depth (single call site, single source of truth)"
  - "Source-level invariant tests: test_detector_py_no_longer_has_inline_fov_math reads detector.py file content to guard against re-inlining regressions"

requirements-completed: [DET-API-03]

duration: 5min
completed: 2026-04-13
---

# Phase 1 Plan 4: MedianDepthLifter Summary

**MedianDepthLifter registered as the default `median_depth` Detection3DProtocol backend, consolidating the two legacy 2D→3D projection paths into a single `project_center_median_depth()` helper and rewiring `ObjectDetector._detect()` to delegate — closes Pitfall P3 in Phase 1.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-13T09:57:22Z
- **Completed:** 2026-04-13T10:02:51Z
- **Tasks:** 4
- **Files created:** 3
- **Files modified:** 1

## Accomplishments

- `MedianDepthLifter` class implementing `Detection3DProtocol` (runtime-checkable isinstance passes) and registered via `@detection_3d("median_depth", "Median Depth (legacy)")` — `Detection3DRegistry.list_backends()` now surfaces one entry with `available=True` and `outputs_oriented=False`.
- `project_center_median_depth()` module-level helper holds the ONE copy of median-depth projection math in the repo. Math is bit-identical to the pre-refactor `detector.py:221-236` inline block (hardcoded 70° FOV, `[cam_x, -cam_y, -d]` sign flip, `pose[:3,:3] @ cam_pt + pose[:3,3]` world transform).
- `ObjectDetector._detect()` rewired: 27 lines of inline projection math replaced with a 6-line lazy-import call site. `det.center_3d` and `det.depth_m` populated identically to before — `coordinator.py:637-654` consumer was NOT touched and continues working.
- `src/perception/lifters/__init__.py` side-effect-import package created, mirroring `src/slam/backends/__init__.py` per CONTEXT.md D-07.
- 13 contract tests cover: registration, protocol conformance, CAPABILITIES lock, slam_cloud independence, None-depth fallback, empty-ROI skip, identity-pose parity math, apply_params live-tunable echo, get_metrics output shape, and a source-level invariant guarding against re-inlining the 70° FOV math in detector.py.
- Pitfall P3 closed in Phase 1 — no duplicate projection paths remain in the active code graph.

## Task Commits

1. **Task 1: Create src/perception/lifters/median_depth.py** — `1f56d33` (feat)
2. **Task 2: Create src/perception/lifters/__init__.py** — `9523266` (feat)
3. **Task 3: Rewire ObjectDetector._detect() to MedianDepthLifter** — `b9421fa` (refactor)
4. **Task 4: Add tests/perception/test_median_depth_lifter.py** — `7e494bd` (test)

Base commit: `377d994` (main, after Wave 2 merge-back).

## Files Created/Modified

- `src/perception/lifters/__init__.py` — Side-effect-import package root (11 lines). Triggers `@detection_3d` registration when `src.perception.lifters` is imported.
- `src/perception/lifters/median_depth.py` — MedianDepthLifter + `project_center_median_depth()` helper (271 lines). Numpy-only; no torch, open3d, or cv2 imports.
- `src/perception/detector.py` — `ObjectDetector._detect()` 2D→3D block replaced with lazy-import call to `project_center_median_depth`. Net: +9 lines, -28 lines. Everything outside the projection block (YOLO wrapper, INDOOR_CLASSES filter, Detection dataclass, run loop) is untouched.
- `tests/perception/test_median_depth_lifter.py` — 13 tests, 212 lines. Runs fully offline (synthetic depth maps, no MuJoCo, no YOLO).

## Decisions Made

- **Hardcoded 70° FOV preserved.** The lifter receives `intrinsics: CameraIntrinsics` per D-04 but ignores it in Phase 1. Rationale: the Plan 05 regression test needs bit-exact parity with the pre-refactor `ObjectDetector._detect` output. Switching to real `fx/fy/cx/cy` changes the pixel-to-world math (even when `CameraIntrinsics.from_fov(640, 480, 70.0)` is used, because the legacy math divides by `h_img / (2*tan(fov/2))` for BOTH x and y, whereas real intrinsics would use `fx != fy` — though here they happen to be equal). Phase 4's `src/perception/geometry.py` is where the real-intrinsics switch happens; this is documented in-file as a retiring-constant.
- **Module-level `project_center_median_depth()` helper.** Not an instance method. Rationale: `ObjectDetector._detect` needs to call it WITHOUT instantiating a `MedianDepthLifter` (the lifter class is "too high up the stack" — requires Detections2D wrapping). Exposing the pure function keeps the call site minimal (one line) and lets the lifter's `lift()` reuse the same function internally, guaranteeing single-source math.
- **Lazy import in detector.py.** `from src.perception.lifters.median_depth import project_center_median_depth` lives INSIDE the `_detect` method body, not at module top. Rationale: `src/coordination/coordinator.py` imports `ObjectDetector` at module-load time; if the lifter import chain lights up (types → protocol → registry → lifters → median_depth) at that moment, any import ordering mishap becomes a top-level error. Deferring to first-detection call trades one `dict` lookup per detection for a hard guarantee against circular imports.
- **detection_3d.py::project_detections_to_3d left alone.** It has no live consumers after Plan 04, but the file exists as a coexistence shim per CONTEXT.md D-11. Deleting it is a Phase 4 cleanup (same time as `src/perception/geometry.py` lands).

## Deviations from Plan

None — plan executed exactly as written. All 4 tasks completed in order, all acceptance criteria satisfied, zero auto-fixes needed.

## Issues Encountered

### Worktree base mismatch (operational, resolved before Task 1)

- **Issue:** The worktree was created from commit `b6bb40f` (pre-Plan-01-03 state), but the plan requires base commit `377d994` (post-Plan-03 merge-back). `src/perception/protocol.py`, `types.py`, `registry.py` did not exist at `b6bb40f`.
- **Fix:** `git reset --hard 377d994149a53e5a30dd5c8abf553f42a7896c9a` — matches the `<worktree_branch_check>` protocol documented in `execute-plan.md`. Known issue.
- **Impact:** Zero code impact. Task commits all sit on top of `377d994` as expected.

### Pre-existing test failures (out-of-scope, logged in deferred-items.md)

Full `pytest tests/perception/` reports 9 failures (2 torch + 7 sys.modules-pollution). All 9 are pre-existing at base commit `377d994` — verified by removing Plan 04's test file and re-running: same 9 failures. Plan 04's own 13 tests pass in every ordering, and `test_registry.py` all 16 tests pass in isolation. Details + proposed resolution in `.planning/phases/01-detector-api-foundation/deferred-items.md`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

**Ready for Plan 05** (YOLOv11 wrapper + regression test + RSS SLAM backend):
- `Detection3DRegistry` now has a working default backend (`median_depth`, available=True).
- `project_center_median_depth` is the stable projection contract Plan 05's regression test can exercise against synthetic depth maps if needed (though the Plan 05 regression test compares YOLO 2D bbox counts, not 3D math).
- The lifter package + side-effect import pattern is ready for Phase 4 to drop in `point_cluster.py` as a sibling.
- `ObjectDetector` remains the Phase 1 coexisting shim (D-11) — fully compatible with `coordinator.py` and unchanged in external API surface.

**Phase 1 coordinator-wiring preservation: VERIFIED.** `src/coordination/coordinator.py:140-148, 637-654` was NOT modified; `ObjectDetector` continues to set `det.center_3d`/`det.depth_m` exactly as before, just via delegation.

**Gate status (from the plan's `<verification>` block):**
1. Lifter registered in `Detection3DRegistry.list_backends()` — **PASS**
2. `import src.perception.detector` succeeds — **PASS**
3. `pytest tests/perception/test_median_depth_lifter.py -x -v` 13/13 — **PASS**
4. `pytest tests/perception/ -x -v` — **PASS for Plan 01/04 scope; 9 pre-existing failures in Plan 02/03 tests out-of-scope (deferred)**
5. `grep "math.radians(70" src/perception/detector.py` returns nothing — **PASS**
6. Coordinator untouched — **PASS**

## Self-Check: PASSED

All key files exist on disk; all task commit hashes present in `git log --all`.

---
*Phase: 01-detector-api-foundation*
*Completed: 2026-04-13*
