---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 12
subsystem: perception
tags: [cleanup, deletions, regression, fixtures, w01, w02, phase-exit]
requires:
  - src/perception/worker_pool.py (Plan 02-04)
  - src/coordination/coordinator.py (Plan 02-10 detector_pool rewire)
  - src/main.py (Plan 02-09 restart-block pool rebuild)
provides:
  - D-19 deletions (src/perception/detector.py + detection_3d.py + test_yolov11_regression.py)
  - W-01 non-degenerate YOLO regression fixture (≥1 detection guaranteed at generation time)
  - W-02 sys.modules pollution fix (split enum-identity closed across 3 test files)
  - tests/integration/test_pool_end_to_end.py — pool dataflow parity regression guard
affects:
  - Every file that imported src.perception.detector or src.perception.detection_3d
    (grep-clean: only historical docstring mentions remain)
tech-stack:
  added:
    - tests/fixtures/yolo_regression_source_bus.jpg (137KB — ultralytics bus.jpg deterministic source)
  patterns:
    - Lazy module-identity resolver (_DetectorInput()) to survive sys.modules pollution
    - Snapshot-and-restore try/finally around del sys.modules[...] in P9-delta tests
key-files:
  created:
    - tests/integration/test_pool_end_to_end.py
    - tests/fixtures/yolo_regression_source_bus.jpg
  deleted:
    - src/perception/detector.py
    - src/perception/detection_3d.py
    - tests/perception/test_yolov11_regression.py
  modified:
    - src/perception/backends/yolov11_backend.py (drift guard removed, docstring updated)
    - tests/perception/test_median_depth_lifter.py (dead test removed, docstring updated)
    - tests/perception/test_protocol_contracts.py (W-02 sys.modules restore)
    - tests/perception/test_registry.py (W-02 lazy DetectorInput + teardown pops)
    - tests/perception/test_worker_pool.py (W-02 delta-mode torch check)
    - tests/fixtures/generate_yolo_regression_fixture.py (W-01 hard gate + Mode A')
    - tests/fixtures/yolo_regression_scene_01.npz (regenerated, 4 detections)
key-decisions:
  - "Mode A' fixture source = ultralytics bus.jpg deterministically resized to 480x640 via cv2.INTER_AREA. MuJoCo office scene produced zero YOLO detections at every tested resolution (go2 front_cam views untextured walls); bus.jpg is YOLO's de facto demo scene and yields 4 persons at conf >= 0.69."
  - "W-02 fix is 3-part because no single pop list works: popping types/protocol/registry breaks downstream tests whose CAPABILITIES captured DetectorInput at class-def time (FakeDetector); NOT popping breaks test_registry's decorator re-registration. Resolution: fix enum-identity pollution at the source (test_protocol_contracts restore-on-finally) + keep decorator re-registration via backends/lifters pops + defense-in-depth lazy resolver."
  - "test_pool_module_does_not_import_torch was refactored from absolute-absence to delta-mode check — torch legitimately loads via prior TorchBackendMixin tests; P9 only requires worker_pool itself doesn't pull it."
requirements-completed: [DET-API-04, DET-MODELS-01]
duration: ~60 min
completed: 2026-04-14
---

# Phase 2 Plan 12: Cleanup + W-01/W-02 Closure Summary

Phase 2 exit plan — delete the legacy ObjectDetector / detection_3d modules whose
production consumers were already removed by Plans 02-09..02-11, replace the
now-defunct D-12 regression test with a pool-level parity test that actually
exercises the Phase 2 dataflow, and close the two Phase 1 verifier warnings
(W-01 zero-detection fixture; W-02 sys.modules-pollution registry flake).

## One-Liner

Retired 455 lines of dead ObjectDetector code, regenerated the YOLO regression
fixture with a deterministic Mode A' source (bus.jpg → 4 detections, non-tautological
parity), and closed the W-02 enum-identity split that was causing 7 failures + 9
errors in full-suite runs of `tests/perception/`.

## Metrics

- Duration: ~60 minutes
- Tasks completed: 4/4
- Files created: 2 (test_pool_end_to_end.py, yolo_regression_source_bus.jpg)
- Files deleted: 3 (detector.py, detection_3d.py, test_yolov11_regression.py)
- Files modified: 7
- Commits: 4 (one per task)
- Net LoC: -69 (+532/-601)
- Suite impact: tests/perception/ went from 8 failed + 9 errors (on main@6a80f93) → 0 failed + 0 errors (161 passed); full-suite reduced from 17F+18E → 9F+9E (remaining are pre-existing issues outside Plan 02-12 scope)

## Commits

| Task | Description                                                           | Hash     |
| ---- | --------------------------------------------------------------------- | -------- |
| 1    | D-19 delete detector.py + detection_3d.py + defunct regression test   | f66c7f5  |
| 2    | W-02 sys.modules pollution fix (3-part: contracts + registry + pool)  | e669e54  |
| 4    | W-01 regenerate YOLO fixture — Mode A' bus.jpg + hard gate            | 8e51614  |
| 3    | tests/integration/test_pool_end_to_end.py — pool parity regression    | 8b19c52  |

## Task Matrix

### Task 1 — D-19 deletions (commit f66c7f5)

- Deleted `src/perception/detector.py` (221 LoC — ObjectDetector class, INDOOR_CLASSES, _detect, _run_loop). Production consumers were removed by Plan 02-10; this is the grave-clean.
- Deleted `src/perception/detection_3d.py` (83 LoC — `project_detections_to_3d`). MedianDepthLifter.project_center_median_depth owns the math per D-13.
- Deleted `tests/perception/test_yolov11_regression.py` (151 LoC — D-12 ObjectDetector vs YOLOv11Backend bit-exact parity). Reference implementation retired; the test is meaningless. Replaced by Task 3's pool-end-to-end test.
- Removed `_assert_indoor_classes_drift_guard()` from `yolov11_backend.py` (Rule 3 blocking: the guard tried to import the now-deleted detector.py and would crash at backend import).
- Removed `test_detector_py_no_longer_has_inline_fov_math` from `test_median_depth_lifter.py` (Rule 3 blocking: test opened `src/perception/detector.py` which no longer exists).

Verification: `grep -rn 'from src.perception.detector\|from src.perception.detection_3d' src/ backend/ tests/` returns empty (only historical docstring/comment mentions remain).

### Task 2 — W-02 closure (commit e669e54)

Phase 1 VERIFICATION.md §W-02: `pytest tests/perception/` produced 7 failures + 9 errors when run as a suite but passed per-file. Root cause: `tests/perception/test_protocol_contracts.py` did `del sys.modules["src.perception.types"]` then re-imported to measure P9 delta, leaving a FRESHLY-CONSTRUCTED types module in sys.modules. Previously-imported modules (`registry.py`, `worker_pool.py`, `FakeDetector.CAPABILITIES`, ...) still held references to the ORIGINAL `DetectorInput` class — subsequent `isinstance(value, DetectorInput)` checks compared v1 vs v2 enum identities with the same name and failed.

**3-part fix:**

1. `tests/perception/test_protocol_contracts.py` — snapshot the original module object(s), pop for the P9 delta measurement, then restore via `try/finally` so sys.modules stays bit-identical post-test. Two functions fixed (types + protocol delta tests).
2. `tests/perception/test_registry.py` — `_clean_registries` autouse fixture now pops ONLY the `backends` + `lifters` packages + their submodules (to re-trigger @decorator registration). It explicitly does NOT pop `types` / `protocol` / `registry` (doing so creates the same identity split for tests whose CAPABILITIES capture DetectorInput at class-def time — e.g. `FakeDetector` in test_worker_pool.py). Defense-in-depth: `_full_det_caps()` now uses a lazy `_DetectorInput()` resolver that reads from the CURRENT sys.modules on every call.
3. `tests/perception/test_worker_pool.py::test_pool_module_does_not_import_torch` — the test asserted absolute `"torch" not in sys.modules`, which broke under full-suite ordering because earlier tests (e.g. `test_torch_backend_mixin_enforces_eval_and_freeze`) legitimately pull torch. Refactored to delta-mode: skip when torch was already loaded before the worker_pool import under test.

Verification: `pytest tests/perception/ -q` (cold) → `161 passed, 1 skipped`. Same result on warm run. Was 8F + 9E on main@6a80f93.

### Task 3 — Pool end-to-end parity test (commit 8b19c52)

`tests/integration/test_pool_end_to_end.py` — two tests:

1. `test_pool_submit_latest_matches_direct_backend` — the W-01 parity gate. Builds YOLOv11Backend + MedianDepthLifter directly (reference path), runs `process_frame` + `lift` on the W-01 fixture, then builds a single-robot `DetectorWorkerPool(backend_name='yolov11', lifter_name='median_depth')`, submits the same frame, polls `latest` with a 10 s deadline, and asserts detection count + class_id + class_name + center + half_extents + quaternion match (atol=1e-6). W-01 skip-guard if the fixture degenerates to zero detections.
2. `test_pool_latest_carries_envelope_pose_and_timestamp` — D-11/D-12/D-13 envelope plumbing. Submits with `submit_pose[0,3]=7.77` + `sim_time=12.34` and asserts the `Detections3D` returned by `latest` echoes both fields.

Both tests skip cleanly via `pytest.importorskip("ultralytics")` / `importorskip("torch")` when the perception extra is not installed.

Result: `2 passed in 4.97s`.

### Task 4 — W-01 fixture regeneration (commit 8e51614)

Phase 1 VERIFICATION.md §W-01: `tests/fixtures/yolo_regression_scene_01.npz` produced 0 YOLO detections, making every D-12-style parity test a `0==0` silent tautology.

`tests/fixtures/generate_yolo_regression_fixture.py` rewritten:

- **Hard gate:** `assert len(detections) >= 1` BEFORE `np.savez(...)`. Any future scene regression fails LOUDLY at generation time.
- **Single mode (Mode A'):** source image is `tests/fixtures/yolo_regression_source_bus.jpg` (copied once from `ultralytics/assets/bus.jpg`, committed to the repo). Deterministically resized to 480x640 via `cv2.INTER_AREA`. Produces 4 person detections at conf 0.69–0.90 with stable bbox coords.
- **Mode A rejection rationale documented in module docstring:** MuJoCo's go2 scene (`models/unitree_go2/scene.xml` via default `MuJoCoEnvConfig`) renders an untextured office — YOLOv11 returns 0 detections at every tested resolution (320x240, 640x480, 1280x960).
- **Mode B removed:** synthetic rectangles produced 0 detections too (former fallback was the 0==0 root cause).

Regenerated NPZ committed via git-lfs (`.gitattributes` tracks `tests/fixtures/*.npz`).

## Deviations from Plan

### Auto-fixed Issues

1. **[Rule 3 - Blocking] INDOOR_CLASSES drift guard in yolov11_backend.py imports deleted detector.py**
   - Found during: Task 1 pre-deletion grep
   - Issue: `src/perception/backends/yolov11_backend.py:60-79` defined `_assert_indoor_classes_drift_guard()` that did `from src.perception.detector import ObjectDetector`. Deleting detector.py would crash on yolov11_backend import.
   - Fix: Replaced the guard with a comment explaining INDOOR_CLASSES is now the single source of truth.
   - Files modified: src/perception/backends/yolov11_backend.py
   - Commit: f66c7f5

2. **[Rule 3 - Blocking] test_detector_py_no_longer_has_inline_fov_math reads deleted file**
   - Found during: Task 1 pre-deletion scan
   - Issue: `tests/perception/test_median_depth_lifter.py:207` did `open("src/perception/detector.py").read()` — deleting detector.py would break the test.
   - Fix: Removed the test (its invariant — "detector.py does not inline FOV math" — is trivially true when detector.py itself doesn't exist).
   - Files modified: tests/perception/test_median_depth_lifter.py
   - Commit: f66c7f5

3. **[Rule 1 - Bug] W-02 fix required pop-registry AND not-pop-registry (resolved by 3-part fix)**
   - Found during: Task 2 verification
   - Issue: The plan's action block prescribed popping `src.perception.types` + `src.perception.protocol` on `_clean_registries` teardown. In practice this either (a) left stale enum identities when those modules were NOT popped alongside `src.perception.registry`, or (b) broke test_worker_pool setup when registry WAS popped. The prescribed single-fix action in the plan could not close W-02.
   - Fix: Three-part fix — fix pollution at source (test_protocol_contracts.py restore-on-finally), fix decorator re-registration without breaking identity (test_registry.py pops only backends+lifters + lazy `_DetectorInput()` resolver), refactor test_worker_pool's absolute-absence assertion to delta-mode.
   - Files modified: 3 test files
   - Commit: e669e54

4. **[Rule 3 - Blocking] MuJoCo Mode A produces 0 YOLO detections**
   - Found during: Task 4 Mode A probe
   - Issue: The plan preferred MuJoCo render for Mode A. The actual scene (`models/unitree_go2/scene.xml`) produces 0 detections at every tested resolution. The plan permitted Mode A' fallback; this deviation confirms the fallback was necessary.
   - Fix: Committed `yolo_regression_source_bus.jpg` (copy of `ultralytics/assets/bus.jpg`, 137KB plain git) and rewrote the generator to use it as the deterministic source.
   - Files modified: tests/fixtures/generate_yolo_regression_fixture.py + new yolo_regression_source_bus.jpg
   - Commit: 8e51614

5. **[Rule 3 - Blocking] Worktree base mismatch (plans 02-09..02-11 missing)**
   - Found during: Pre-execution state check
   - Issue: Worktree HEAD was `1a804fe` (phase 2 planning complete, no phase-2 execution commits). Expected base per spawn prompt was `6a80f93` (post-Plan 02-11). Plan 02-12 depends on 02-09/02-10/02-11 being on-branch.
   - Fix: `git rebase 6a80f9308805c4cad1cb20b4d1aaae19c82db4ed`. Worktree now based correctly; planning-doc-only commits that were superseded by the upstream execution were dropped.
   - Files modified: N/A (rebase only)
   - Commit: (pre-task-1)

**Total deviations:** 5 auto-fixed (2× Rule 1, 3× Rule 3). **Impact:** every deviation was a correctness requirement to land the plan intent; no architectural changes needed.

## Verification Gate Results

- [x] **D-19 deletions:** 3 files deleted, 0 stale imports in src/ backend/ tests/.
- [x] **`pytest tests/perception/` green cold:** 161 passed, 1 skipped (was 8 failed + 9 errors on main).
- [x] **`pytest tests/perception/` green warm:** identical result — 161 passed, 1 skipped.
- [x] **`pytest tests/integration/test_pool_end_to_end.py` green:** 2 passed, ≥1 detection in fixture (W-01 gate confirmed non-tautological).
- [x] **`cd frontend && npx tsc --noEmit` green:** exit 0, 0 errors.
- [x] **Full `pytest tests/` suite:** 524 passed, 9 failed + 9 errors remain. ALL remaining failures are pre-existing on main@6a80f93 (17F+18E before my changes) and are outside Plan 02-12 scope — see "Deferred Issues" below.

## Deferred Issues

The remaining 9 failures + 9 errors in `pytest tests/` are **pre-existing on main** (verified by reverting my changes and re-running the suite). None were caused by Plan 02-12; none are within its scope:

- `tests/exploration/` — 6 failures (TestExplorationConfig, ExplorationLoopIntegration, PathPlanner). Unrelated to perception.
- `tests/perception/test_median_depth_lifter.py::test_lifter_registered_under_median_depth` — 1 failure only in full-suite mode (test-isolation residue from other subsystems). Passes in `tests/perception/` alone.
- `tests/slam/test_openvins_backend.py::TestOpenVINSRegistration::test_registered_as_openvins` — 1 failure, same test-isolation pattern (SLAMRegistry empty after subsystem suite pollution).
- `tests/smoke/test_detector_rss.py::test_rss_growth_bounded[yolov11]` — 1 failure, `DetectorRegistry.create("yolov11")` finds empty registry in full-suite mode.
- `tests/integration/test_multi_mode.py` (5 errors) + `test_multi_robot_integration.py` (4 errors) — coordinator dict-vs-dataclass issue unrelated to detector dataflow.

These all share a common signature (test-isolation bleed across subsystems) but are NOT the W-02 enum-identity bug — they were present on main before Plan 02-12 and are out of scope. Logged to `.planning/phases/02-per-robot-worker-and-wire-plumbing/deferred-items.md` recommendation: Phase 3 or a standalone test-hygiene plan should address per-subsystem registry-isolation autouse fixtures.

## Phase Exit Checklist (Plan 02-12 closes Phase 2)

- [x] D-19 — src/perception/detector.py + detection_3d.py DELETED; grep-clean.
- [x] W-01 — `yolo_regression_scene_01.npz` regenerated, ≥1 detection asserted at generation time; generator script ships with the hard gate.
- [x] W-02 — `pytest tests/perception/` green cold AND warm (161 passed, 1 skipped, 0 failed, 0 errors).
- [x] Pool end-to-end test (`tests/integration/test_pool_end_to_end.py`) green (2 passed); ≥1 detection from regenerated fixture.
- [x] Frontend typecheck (`npx tsc --noEmit`) still green (no stale detector imports).
- [x] `grep -rn 'from src.perception.detector\|from src.perception.detection_3d' src/ backend/ tests/` → empty.
- [x] `ls src/perception/detector.py src/perception/detection_3d.py tests/perception/test_yolov11_regression.py` → 3× "No such file or directory".

## Self-Check: PASSED

Files verified on disk:
- `tests/integration/test_pool_end_to_end.py` — FOUND (243 lines)
- `tests/fixtures/yolo_regression_source_bus.jpg` — FOUND (137419 bytes)
- `tests/fixtures/yolo_regression_scene_01.npz` — FOUND (regenerated via git-lfs)

Files verified deleted:
- `src/perception/detector.py` — MISSING (expected — D-19 deletion)
- `src/perception/detection_3d.py` — MISSING (expected — D-19 deletion)
- `tests/perception/test_yolov11_regression.py` — MISSING (expected — D-19 deletion)

Commits verified in `git log`:
- f66c7f5 (Task 1) — FOUND
- e669e54 (Task 2) — FOUND
- 8e51614 (Task 4) — FOUND
- 8b19c52 (Task 3) — FOUND

All self-check assertions pass.
