---
phase: 01-locomotion-env-contract
plan: 03
subsystem: locomotion
tags: [gymnasium, action-spaces, gait-controller, validation, loc-env-04]

requires:
  - phase: 01-locomotion-env-contract/01-01
    provides: Gymnasium dependency and ArgusGo2Env contract foundation
provides:
  - LOC-ENV-04 action mode helper module with velocity, joint-position, and residual-baseline contracts
  - Focused action mode tests for action spaces, decoding behavior, and malformed input rejection
affects: [01-04-env-wiring, controller-plugin-baseline, locomotion-evaluation]

tech-stack:
  added: []
  patterns:
    - Central action mode constants and Gymnasium Box construction
    - Pre-physics exact-shape and finite-value validation
    - Analytical trot baseline reused for velocity and residual decoding

key-files:
  created:
    - src/locomotion/actions.py
    - tests/locomotion/test_argus_go2_env_action_modes.py
  modified: []

key-decisions:
  - "Keep action decoding in src/locomotion/actions.py as a MuJoCo-free helper so env.step can validate before writing data.ctrl."
  - "Use the existing TrotGaitController as the baseline for both velocity_command and residual_baseline modes."

patterns-established:
  - "Action helpers expose exact mode constants and available_action_modes for future environment config validation."
  - "Every action enters through _as_finite_vector before decoded controls can reach physics."

requirements-completed: [LOC-ENV-04]

duration: 2 min
completed: 2026-04-30
---

# Phase 01 Plan 03: Action Mode Contracts Summary

**Velocity-command, direct joint-position, and residual-over-analytical-baseline action modes with strict pre-physics validation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-30T07:06:02Z
- **Completed:** 2026-04-30T07:08:21Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added focused LOC-ENV-04 tests covering all three required action spaces, decode paths, residual clipping, wrong-shape rejection, NaN rejection, and unknown-mode errors.
- Added `src/locomotion/actions.py` with exact action mode constants, `available_action_modes`, `build_action_space`, and `decode_action`.
- Preserved the single `ArgusGo2Env.step(action)` direction by keeping mode-specific semantics in a standalone helper that future env wiring can call before mutating MuJoCo controls.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add action mode tests for spaces, decoding, and invalid input** - `0e300af` (test)
2. **Task 2: Implement action mode spaces and safe decoding** - `989f325` (feat)

**Plan metadata:** pending final docs commit

_Note: TDD tasks used separate RED and GREEN commits._

## Files Created/Modified

- `src/locomotion/actions.py` - Defines LOC-ENV-04 action mode constants, Gymnasium `Box` spaces, finite vector validation, and mode-specific decoding into 12 joint targets.
- `tests/locomotion/test_argus_go2_env_action_modes.py` - Pins action space bounds, velocity gait decoding, joint-position pass-through, residual baseline addition/clipping, wrong-shape failures, NaN failures, and unknown-mode errors.

## Decisions Made

- Kept `decode_action` MuJoCo-free; callers receive a finite `(12,)` `np.float64` vector and remain responsible for writing `data.ctrl`.
- Used the existing `TrotGaitController.compute` for velocity-command and residual-baseline decoding rather than adding a second gait implementation.
- Returned exact `np.float64` decoded controls even when callers pass `np.float32` actions so validation and downstream control assignment have a consistent numeric dtype.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Verification

- `/.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py -q -x` equivalent with absolute project path: **14 passed**.
- `/.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_action_modes.py tests/locomotion/test_argus_go2_env_contract.py -q` equivalent with absolute project path: **20 passed**.
- Task 1 RED gate failed as expected before implementation with `ModuleNotFoundError: No module named 'src.locomotion.actions'`.

## Known Stubs

None.

## Threat Flags

None beyond the plan threat model. The new helper implements the planned action-input trust-boundary validation and does not introduce network, auth, file-access, schema, or direct MuJoCo mutation surfaces.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for Plan 01-04 to wire `build_action_space` and `decode_action` into `ArgusGo2Env` config and `step(action)` handling.

## Self-Check: PASSED

- Found `src/locomotion/actions.py`.
- Found `tests/locomotion/test_argus_go2_env_action_modes.py`.
- Found `.planning/phases/01-locomotion-env-contract/01-03-SUMMARY.md`.
- Found task commit `0e300af`.
- Found task commit `989f325`.

---
*Phase: 01-locomotion-env-contract*
*Completed: 2026-04-30*
