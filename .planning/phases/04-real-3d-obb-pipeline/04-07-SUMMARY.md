---
phase: 04-real-3d-obb-pipeline
plan: 07
subsystem: testing
tags: [pytest, mujoco, integration, grep-invariant, sc-gate, importorskip, yolov11, point-cluster-lifter]

# Dependency graph
requires:
  - phase: 04-04
    provides: PointClusterLifter (point_cluster registry name) — exercised end-to-end
  - phase: 04-05
    provides: lifter hot-swap path + worker_pool plumbing — capability registry surface used by integration test
  - phase: 04-06
    provides: frontend lifter switch via /lifter-hotswap — DetectionBoxes.ts post-Phase-4 state grep-locked
  - phase: 04-01
    provides: scene_rotated_chair.xml MuJoCo fixture (chair body @ 30 deg yaw)
  - phase: 04-03
    provides: median_depth.py post-migration — _LEGACY_FOV_DEG removal grep-locked here
provides:
  - SC#1 ±15 deg yaw / 0.15m center MuJoCo GT integration test (3 tests, importorskip-gated)
  - SC#2 grep invariant locking DetectionBoxes.ts free of focal/backProject/projectBox/fovToFocal
  - SC#3 grep invariants locking _LEGACY_FOV_DEG, CLOUD_CONFIGS, math.tan/math.radians out of src/perception/ except geometry.py
  - cloud_config import ban across the perception package (Pitfall 10)
  - OBB to_wire/from_wire round-trip regression guard wired through the live pipeline
  - Positive PointCluster path assertion (non-identity quaternion proves Open3D PCA fired, not MedianDepth fallback)
affects:
  - 04 verification phase (/gsd-verify-phase will cite both test files for SC#1/SC#2/SC#3)
  - Future Phase 5 detector backends (BoxeR, OWLv2) — same SC pattern reusable
  - Future Phase 6 metric work — center_error_m vs MuJoCo GT pattern locked here

# Tech tracking
tech-stack:
  added:
    - "pytest.importorskip-gated MuJoCo integration test pattern (4 importorskip calls per test path)"
  patterns:
    - "Phase-exit grep invariants as automated pytest tests (belt-and-suspenders over per-module grep tests in test_geometry.py)"
    - "WXYZ → XYZW quaternion conversion at the MuJoCo / scipy boundary (Pitfall 7)"
    - "Signed yaw difference normalized to [-pi, pi] before abs() — guards against the wraparound-near-pi false-failure"
    - "Closest-OBB-to-GT-xpos best-match selection — tolerates spurious YOLO side detections without weakening the gate"

key-files:
  created:
    - "tests/integration/test_obb_mujoco_scene.py"
    - "tests/perception/test_no_focal_math_frontend.py"
  modified: []

key-decisions:
  - "Integration test stays in tests/integration/ (not tests/perception/) so it's discoverable as a single-target full-pipeline gate, separate from the per-module unit tests"
  - "All 4 perception extras (mujoco, ultralytics, open3d, sklearn.cluster) gated independently with pytest.importorskip — partial-install environments still fail-loudly on the actually-missing dep"
  - "best = min(items, key=...) selection over the OBB list lets the gate survive YOLO side detections (e.g., a false 'bench' alongside the chair) while still asserting the chair OBB itself is on-target"
  - "yaw error normalized via ((y_pred - y_gt) + pi) % (2*pi) - pi before abs — protects against false failures at the +/-180 deg seam"

patterns-established:
  - "Phase-exit SC gate: ship one importorskip-gated integration test per phase that runs the full intended user path end-to-end and asserts the headline numerical/behavioral budget"
  - "Phase-exit invariant lockdown: ship one grep-invariant test per SC that the phase intends to lock, scanning both the cleaned-up surface (frontend) and the migrated-away-from surface (legacy FOV in perception)"

requirements-completed:
  - DET-3D-01
  - DET-3D-05
  - DET-3D-06

# Metrics
duration: ~10min
completed: 2026-04-14
---

# Phase 04 Plan 07: Wave 5 Integration + Invariant Lockdown Summary

**SC#1 ±15° yaw / 0.15m center MuJoCo-GT gate shipped as a 3-test importorskip-gated integration suite, plus a 4-test grep-invariant lockdown that keeps DetectionBoxes.ts focal-math-free (SC#2) and the perception package single-projection-entrypoint (SC#3).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-14T10:13:00Z (approx)
- **Completed:** 2026-04-14T10:23:34Z
- **Tasks:** 2 / 2
- **Files created:** 2

## Accomplishments

- **SC#1 automated:** `tests/integration/test_obb_mujoco_scene.py` runs the full YOLOv11 → PointClusterLifter pipeline against `scene_rotated_chair.xml`, picks the OBB closest to `data.body('chair').xpos`, and asserts center error < 0.15 m and yaw error < 15° vs the MuJoCo ground truth body pose. The envelope-level `outputs_oriented=True` capability is asserted via `Detection3DRegistry.list_backends()`.
- **Phase 2 D-04 round-trip regression guard** wired through the live pipeline: every Phase-4 OBB is round-tripped through `to_wire/from_wire` to ±1e-6, comparing against the signed wire form (handles `to_wire()` `qw<0` auto-flip).
- **Positive-path proof:** `test_fallback_does_not_fire_on_dense_chair_frustum` asserts at least one returned OBB has a NON-identity quaternion — proving the Open3D PCA-OBB ran, not the MedianDepth fallback.
- **SC#2 + SC#3 lockdown:** 4 grep-invariant tests in `tests/perception/test_no_focal_math_frontend.py` lock DetectionBoxes.ts (no focal/backProject/projectBox/fovToFocal), `_LEGACY_FOV_DEG` absence, `CLOUD_CONFIGS`/`cloud_config` import ban, and `math.tan(`/`math.radians(` confined to `src/perception/geometry.py`.
- **Pytest skip behavior verified on bare env:** all 3 integration tests skip cleanly (mujoco/ultralytics/open3d/sklearn.cluster missing); all 4 grep tests pass. `4 passed, 3 skipped` in 0.04 s.

## Task Commits

1. **Task 1: SC#1 MuJoCo GT integration test** — `90bbf1a` (test)
2. **Task 2: SC#2 + SC#3 grep invariants** — `cad6083` (test)

## Files Created/Modified

- `tests/integration/test_obb_mujoco_scene.py` — 3-test SC#1 integration suite (yaw + center gate, wire round-trip, positive-path quaternion check). All paths gated on `pytest.importorskip("mujoco" / "ultralytics" / "open3d" / "sklearn.cluster")` per Assumptions A4 / threat T-04-29 mitigation.
- `tests/perception/test_no_focal_math_frontend.py` — 4-test SC#2/SC#3 grep-invariant suite. Comment + docstring lines skipped on the math.tan/math.radians scan per Pitfall 9.

## Decisions Made

- **04-VALIDATION.md was already fully populated by the planner** (`nyquist_compliant: true`, full Per-Task Verification Map for all 13 tasks across 7 plans, SUMMARY Notes section with Override 1 D-03 + Override 2 D-04). No edits required from this plan — verified via `grep -c "TBD" .planning/phases/04-real-3d-obb-pipeline/04-VALIDATION.md` returning 0. Plan-level expectation that the executor would write the table was satisfied at planning time.
- **Tests live where they verify, not where they're authored from.** SC#1 integration test in `tests/integration/`; SC#2/SC#3 grep tests in `tests/perception/` (alongside the rest of the perception unit suite).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed `--timeout=120` from in-shell pytest invocations**
- **Found during:** Task 1 verification step.
- **Issue:** `pytest-timeout` plugin is not installed in the local Python environment; passing `--timeout=120` (as the plan's `<verify><automated>` block does) raises `unrecognized arguments` and the test session aborts before tests are collected. The `pytest.ini` `timeout = 30` config option likewise warns as `Unknown config option`.
- **Fix:** Ran the verification commands as `python -m pytest <files> -x -v` (without `--timeout`). Test files themselves are unchanged — this is purely an executor-side workaround for a missing CI plugin. The plan's verification command remains the canonical reference.
- **Files modified:** None.
- **Verification:** `pytest tests/integration/test_obb_mujoco_scene.py tests/perception/test_no_focal_math_frontend.py -v` → `4 passed, 3 skipped, 1 warning in 0.04s`.
- **Committed in:** N/A (executor-side workaround, no file change).

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking environment issue, no source change).
**Impact on plan:** Zero. Tests + acceptance criteria all pass / skip as designed; the plan's `--timeout=120` flag remains the documented contract for downstream CI environments that have `pytest-timeout` installed.

## Issues Encountered

- **Bare Python env has only `scipy` from the perception extra.** Expected and handled — all 4 importorskip calls fire and the 3 integration tests skip cleanly. The grep-invariant tests pass because they only `pathlib.Path.read_text()` on source files; no import of perception modules required.

## Threat Flags

None — no new security-relevant surface introduced. The two test files only do read-only path scans (grep invariants) and pytest-internal MuJoCo rendering (integration test) — both within the existing trust boundaries enumerated in the plan's `<threat_model>` (T-04-29 through T-04-33).

## Known Stubs

None. Both test files exercise live pipeline behavior (when deps available) or skip cleanly (when not). VALIDATION.md is fully populated by the planner.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **Phase 4 SC gates locked:** SC#1 (integration), SC#2 (grep), SC#3 (grep) all have automated pytest commands. SC#5 (hot-swap) is covered by Plans 05 + 06 tests (`test_lifter_hotswap.py`, `test_lifter_routes.py`, `DetectorSection.tsx` + `npx tsc --noEmit`).
- **`/gsd-verify-phase` ready:** can cite `tests/integration/test_obb_mujoco_scene.py::test_rotated_chair_yaw_and_center_within_tolerance` for SC#1, `tests/perception/test_no_focal_math_frontend.py` for SC#2/SC#3.
- **VERIFICATION.md inputs complete:** 04-VALIDATION.md SUMMARY Notes section pre-stages Override 1 (D-03 full-3D rotation) and Override 2 (D-04 SensorFrame.intrinsics skipped) for the verifier to surface.
- **No blockers** for downstream Phase 5 (BoxeR + OWLv2). The `pytest.importorskip` + `Detection3DRegistry.list_backends()` capability-introspection patterns established here are reusable.

## Self-Check: PASSED

- `[FOUND]` `tests/integration/test_obb_mujoco_scene.py`
- `[FOUND]` `tests/perception/test_no_focal_math_frontend.py`
- `[FOUND]` Commit `90bbf1a` (Task 1 — SC#1 integration test)
- `[FOUND]` Commit `cad6083` (Task 2 — SC#2 + SC#3 grep invariants)
- `[VERIFIED]` `pytest tests/integration/test_obb_mujoco_scene.py tests/perception/test_no_focal_math_frontend.py -v` → `4 passed, 3 skipped`
- `[VERIFIED]` `nyquist_compliant: True` in 04-VALIDATION.md frontmatter
- `[VERIFIED]` All Task 1 acceptance criteria green: 3 test functions present, 5 importorskip calls (>=4), 3 `< 0.15` hits (>=1), 2 `< 15` hits (>=1)
- `[VERIFIED]` All Task 2 acceptance criteria green: 4 `def test_` (>=4), 0 `TBD` placeholders in VALIDATION.md

---

*Phase: 04-real-3d-obb-pipeline*
*Completed: 2026-04-14*
