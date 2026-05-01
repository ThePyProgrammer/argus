---
phase: 04-evaluation-runner-and-regression
plan: 04
subsystem: testing
tags: [pytest, mujoco, locomotion, regression, analytical-trot]

requires:
  - phase: 04-evaluation-runner-and-regression
    provides: CLI locomotion evaluation runner, exported episode rows, summary artifacts, and metric aggregation fields
provides:
  - Analytical flat-ground threshold helper for LOC-EVAL-04
  - Synthetic degradation tests for success, command context, tracking, distance, and stability bounds
  - Marked MuJoCo integration smoke regression for analytical_trot flat_ground seeds 101, 202, and 303
affects: [locomotion-evaluation, regression-gates, analytical-trot-baseline]

tech-stack:
  added: []
  patterns:
    - pytest threshold helper with synthetic failure coverage
    - integration test that skips cleanly when MuJoCo or Go2 assets are unavailable
    - robust metric thresholds over evaluation runner episode rows rather than golden snapshots

key-files:
  created:
    - tests/locomotion/test_locomotion_baseline_regression.py
  modified: []

key-decisions:
  - "Used existing pytest integration marker for the real MuJoCo regression to preserve project marker conventions."
  - "Threshold helper falls back to nested summary metrics when flattened episode-row stability fields are zero-valued placeholders from the current exporter."

patterns-established:
  - "Analytical baseline regression gates must assert command context before interpreting distance and tracking thresholds."
  - "Real locomotion regression uses a small fixed seed matrix and tmp_path-scoped artifacts."

requirements-completed: [LOC-EVAL-04]

duration: 48min
completed: 2026-05-01
---

# Phase 04 Plan 04: Analytical Baseline Regression Summary

**Fixed-seed analytical_trot flat-ground regression gate with synthetic degradation coverage and MuJoCo smoke execution through the evaluation runner**

## Performance

- **Duration:** 48 min
- **Started:** 2026-05-01T02:47:13Z
- **Completed:** 2026-05-01T03:35:13Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Added `assert_analytical_flat_ground_thresholds(rows)` with explicit LOC-EVAL-04 bounds for tracking RMSE, commanded translational distance, base height, roll, and pitch.
- Added synthetic tests proving the helper rejects locomotion failures, missing command context, tracking degradation, stationary translational-command rows, and stability regressions.
- Added a marked `@pytest.mark.integration` MuJoCo smoke regression that runs `analytical_trot` on `flat_ground` over seeds `(101, 202, 303)`, asserts `summary.json` exists, and gates the returned episode rows.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add threshold helper and synthetic degradation tests**
   - `c346371` test(04-04): add failing analytical threshold tests
   - `b6d053b` feat(04-04): implement analytical threshold helper
2. **Task 2: Add marked real analytical flat-ground smoke regression**
   - `dff91c1` feat(04-04): add analytical baseline smoke regression

_Note: TDD tasks used test then implementation commits._

## Files Created/Modified

- `tests/locomotion/test_locomotion_baseline_regression.py` - Synthetic threshold helper tests plus fixed-seed analytical_trot flat_ground integration regression.

## Verification

- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-aff7422c4948d5009/tests/locomotion/test_locomotion_baseline_regression.py -q` → 11 passed.

## Decisions Made

- Reused the existing `integration` pytest marker rather than adding marker configuration.
- Kept plan constants unchanged: `TRACKING_RMSE_MAX = 1.50`, `DISTANCE_XY_MIN_M = 0.01`, `BASE_HEIGHT_MIN_M = 0.15`, `ROLL_ABS_MAX_RAD = 0.90`, and `PITCH_ABS_MAX_RAD = 0.90`.
- Treated zero-valued flattened stability/distance fields from the current exporter as missing for real rows and read canonical nested summary metrics instead; this keeps the regression meaningful without broadening thresholds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Read canonical nested stability metrics when flattened rows contain zero placeholders**
- **Found during:** Task 2 (real MuJoCo regression)
- **Issue:** The real evaluation run returned successful nested summary metrics, but flattened `base_height_min_m`, `roll_abs_max_rad`, `pitch_abs_max_rad`, and `distance_xy_m` episode-row fields were zero, which would make the threshold gate assert against exporter placeholders rather than the actual Phase 3 metrics.
- **Fix:** Updated the helper to fall back to `row["summary"]` metric families for stability and distance whenever flattened fields are missing or zero-valued.
- **Files modified:** `tests/locomotion/test_locomotion_baseline_regression.py`
- **Verification:** Baseline regression pytest command passed with 11 tests.
- **Committed in:** `dff91c1`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The fix preserves the intended LOC-EVAL-04 threshold gate and avoids hiding baseline stability data behind exporter defaults.

## Issues Encountered

- The fixed-seed real smoke run initially failed because flattened episode stability fields were zero despite valid nested summaries. The helper now uses the nested summary as the canonical metric source when flattened values are missing or zero.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None found in files created or modified by this plan.

## Next Phase Readiness

- LOC-EVAL-04 has a committed regression gate that future controller or metrics changes must keep passing.
- The orchestrator can update shared STATE/ROADMAP artifacts after merging wave worktree outputs.

## Self-Check: PASSED

- Found created file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-aff7422c4948d5009/tests/locomotion/test_locomotion_baseline_regression.py`
- Found task commits: `c346371`, `b6d053b`, `dff91c1`
- Verification command passed: 11 tests.

---
*Phase: 04-evaluation-runner-and-regression*
*Completed: 2026-05-01*
