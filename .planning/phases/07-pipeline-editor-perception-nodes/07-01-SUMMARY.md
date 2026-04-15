---
phase: 07-pipeline-editor-perception-nodes
plan: 01
subsystem: testing
tags: [pytest, scaffolding, wave0, perception, tracker, hot-apply, preset]

# Dependency graph
requires:
  - phase: 07-pipeline-editor-perception-nodes
    provides: 07-VALIDATION.md (Wave 0 Requirements list, 11 test files), 07-RESEARCH.md (Phase Requirements -> Test Map)
provides:
  - 7 pytest skip-stub files that collect cleanly
  - tests/tracking/ as importable test package (new)
  - <automated> verification anchors for Wave 1+ implementation plans (07-03, 07-04, 07-05, 07-10, 07-11)
  - DET-PIPELINE-01/03/04/05 lockdown surface (skip stubs flip to assertions later)
affects: [07-02, 07-03, 07-04, 07-05, 07-10, 07-11, all Wave 1+ Plan 07-XX]

# Tech tracking
tech-stack:
  added: []  # Wave 0 scaffold; no new dependencies
  patterns:
    - "module-level pytest.skip(..., allow_module_level=True) for Wave 0 anchors"
    - "TODO Plan NN-NN comments inside stub bodies pointing at the implementing plan"
    - "stub docstring -> behavior contract (mirrors v2.0 SLAM scaffold pattern)"

key-files:
  created:
    - tests/tracking/__init__.py
    - tests/tracking/test_tracker_registry.py
    - tests/coordination/test_pipeline_builder_perception.py
    - tests/perception/test_swap_backend.py
    - tests/contract/test_perception_rgbd_preset.py
    - tests/integration/test_pipeline_apply_hot.py
    - tests/integration/test_perception_rgbd_end_to_end.py
  modified: []

key-decisions:
  - "Module-level pytest.skip with allow_module_level=True (over per-function skipif decorator) so import-time failures cannot occur and Wave 1+ plans only need to delete the skip call."
  - "Reuse existing pytest.mark.slow_boxer marker on the end-to-end test (no new markers added in Phase 7 scaffold)."
  - "tests/tracking/__init__.py created as the only new test package (other dirs already exist)."

patterns-established:
  - "Pattern: every Wave 1+ implementation plan inherits an <automated> command pointing at a real file from day one"
  - "Pattern: TODO Plan NN-NN comments inside stub functions tell the implementing plan exactly what to assert"

requirements-completed: [DET-PIPELINE-01, DET-PIPELINE-03, DET-PIPELINE-04, DET-PIPELINE-05]

# Metrics
duration: 5min
completed: 2026-04-15
---

# Phase 07 Plan 01: Wave 0 Python Pytest Skip-Stubs Summary

**Landed 7 pytest skip-stub files (6 module-level skips + 1 package marker) anchoring DET-PIPELINE-01/03/04/05 verification commands so every Wave 1+ implementation plan ships with a real `<automated>` file from day one.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-15T10:21:00Z (approx, plan execution start)
- **Completed:** 2026-04-15T10:25:57Z
- **Tasks:** 1
- **Files created:** 7

## Accomplishments

- Created `tests/tracking/` as an importable test package (new directory).
- Landed 6 module-level `pytest.skip(..., allow_module_level=True)` test files spanning coordination, perception, contract, integration, and tracking suites.
- All 6 stubs collect cleanly under `pytest --collect-only -q` (exit 0, zero collection errors) and report as **6 skipped** under `pytest -x` (no FAIL, no ERROR).
- Stub docstrings encode the behavioral contract Wave 1+ implementation plans must assert; inline `TODO Plan NN-NN` comments name the implementing plan for each test function.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create 7 Python pytest skip-stub files** — `df135ee` (test)

## Files Created/Modified

- `tests/tracking/__init__.py` — package marker for new tracker test suite (Plan 07-03 target)
- `tests/tracking/test_tracker_registry.py` — TrackerRegistry skeleton + NoneTracker stub (5 test functions)
- `tests/coordination/test_pipeline_builder_perception.py` — PipelineConfig perception fields stub (5 test functions)
- `tests/perception/test_swap_backend.py` — DetectorWorkerPool.swap_backend stub (5 test functions)
- `tests/contract/test_perception_rgbd_preset.py` — perception_rgbd preset integrity stub (3 test functions)
- `tests/integration/test_pipeline_apply_hot.py` — hot-apply PID stability stub (6 test functions)
- `tests/integration/test_perception_rgbd_end_to_end.py` — end-to-end detection emission stub (1 slow_boxer-marked test function)

## Decisions Made

- **Module-level skip vs per-function skipif:** chose `pytest.skip(..., allow_module_level=True)` so any import-time error in stub bodies (today: none; future regression-safe) is shielded by the skip itself; flipping the stub to live assertions in Wave 1+ requires deleting exactly one statement.
- **Marker reuse:** the end-to-end stub uses the existing `pytest.mark.slow_boxer` marker — Phase 7 introduces zero new pytest markers (avoids `pytest.ini` churn during Wave 0).
- **Empty-but-discoverable package:** `tests/tracking/__init__.py` carries only a docstring; no fixtures imported (none needed at scaffold time, registry side-effect fixtures land in Plan 07-03).

## Deviations from Plan

None — plan executed exactly as written. All 7 files created with the verbatim content specified in the `<action>` block; verification commands passed first try.

## Issues Encountered

None.

## User Setup Required

None — pure test-tree scaffold, no external service, env var, or dashboard configuration touched.

## Next Phase Readiness

- **Wave 0 Python half complete.** Wave 1+ plans (07-03, 07-04, 07-05, 07-10, 07-11) can now point their `<automated>` fields at these 6 stub files and flip individual test functions from `assert False` to live assertions as they implement.
- **Wave 0 frontend half pending:** Plan 07-02 still owes the 4 frontend-side stubs to complete the 11-file Wave 0 set listed in 07-VALIDATION.md.
- **No blockers introduced.** Verification confirms `pytest -x` still passes (6 skipped, 0 failed, 0 errored) on the new files; existing suite unchanged.

## Self-Check: PASSED

Verified post-write:

- `tests/tracking/__init__.py` — FOUND
- `tests/tracking/test_tracker_registry.py` — FOUND
- `tests/coordination/test_pipeline_builder_perception.py` — FOUND
- `tests/perception/test_swap_backend.py` — FOUND
- `tests/contract/test_perception_rgbd_preset.py` — FOUND
- `tests/integration/test_pipeline_apply_hot.py` — FOUND
- `tests/integration/test_perception_rgbd_end_to_end.py` — FOUND
- Commit `df135ee` — FOUND in git log
- `pytest --collect-only -q` on all 6 non-`__init__` files — exit 0, zero collection errors
- `pytest -x` on the same 6 files — `6 skipped, 0 failed, 0 errored`
- `grep allow_module_level=True tests/` — 6 hits across 6 files (matches acceptance criterion)

---
*Phase: 07-pipeline-editor-perception-nodes*
*Completed: 2026-04-15*
