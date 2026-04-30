---
phase: 01-locomotion-env-contract
plan: 02
subsystem: locomotion
tags: [gymnasium, mujoco, locomotion, scenarios, determinism, pytest]

requires:
  - phase: 01-locomotion-env-contract
    plan: 01
    provides: Gymnasium-style ArgusGo2Env reset/step contract and baseline observation/action wiring
provides:
  - Named locomotion scenario catalog for flat_ground, low_friction, slope, rough_heightfield, and push_disturbance
  - Deterministic scenario sampling for spawn pose, terrain parameters, command schedule, and disturbance schedule
  - ArgusGo2Env reset and step info populated with ScenarioSample reproducibility metadata
affects: [controller-plugin-baseline, locomotion-metrics-instrumentation, evaluation-runner-and-regression]

tech-stack:
  added: []
  patterns:
    - Central fixed catalog for benchmark scenario selection
    - Gymnasium reset RNG drives all reset-time benchmark metadata
    - Serializable tuple/dict metadata in reset and step info

key-files:
  created:
    - src/locomotion/scenarios.py
    - tests/locomotion/test_argus_go2_env_scenarios.py
    - tests/locomotion/test_argus_go2_env_determinism.py
  modified:
    - src/locomotion/env.py

key-decisions:
  - "Scenario ids are fixed catalog keys only; arbitrary model/XML paths are rejected before sampling."
  - "ScenarioSample metadata uses Python scalar tuple/dict structures so same-seed reproducibility can be compared directly."
  - "ArgusGo2Env stores the reset ScenarioSample and reuses it in step info until the next reset."

patterns-established:
  - "Scenario catalog: use SCENARIOS plus list_scenarios/sample_scenario for all named scenario selection."
  - "Reset determinism: derive spawn pose, terrain parameters, command schedule, and disturbance schedule exclusively from self.np_random."

requirements-completed: [LOC-ENV-02, LOC-ENV-03]

duration: 2min
completed: 2026-04-30
---

# Phase 01-locomotion-env-contract Plan 02: Scenario Catalog and Deterministic Reset Metadata Summary

**Fixed locomotion scenario catalog with seeded reset metadata for terrain, command, spawn, and push-disturbance reproducibility.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-30T06:52:58Z
- **Completed:** 2026-04-30T06:55:16Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added the central `src/locomotion/scenarios.py` catalog with the required `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance` scenario ids.
- Implemented deterministic `sample_scenario(...)` metadata for spawn pose, terrain parameters, command schedule, and disturbance schedule using the provided NumPy generator.
- Integrated sampled scenario metadata into `ArgusGo2Env.reset(...)` and `step(...)` info so benchmark runs can report the seed, scenario id, action mode, sampled parameters, command schedule, and disturbance schedule.
- Added focused tests proving catalog selection, unknown scenario rejection, same-seed reproducibility, and different-seed variation for rough terrain and push disturbances.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add scenario catalog and deterministic reset tests** - `80c4e33` (test)
2. **Task 2: Implement named scenario sampling and reset info integration** - `fb39cec` (feat)

**Plan metadata:** pending final docs commit

_Note: TDD tasks used separate RED and GREEN commits._

## Files Created/Modified

- `src/locomotion/scenarios.py` - Defines `ScenarioSpec`, `ScenarioSample`, fixed `SCENARIOS`, sorted `list_scenarios()`, and deterministic `sample_scenario(...)`.
- `src/locomotion/env.py` - Samples the configured scenario during reset, initializes the first command, stores the reset seed, and returns ScenarioSample metadata in reset/step info.
- `tests/locomotion/test_argus_go2_env_scenarios.py` - Tests required catalog entries, unknown scenario errors, sampler defaults, and env reset scenario selection.
- `tests/locomotion/test_argus_go2_env_determinism.py` - Tests same-seed and different-seed metadata behavior for rough heightfield and push disturbance scenarios, plus step info preservation.

## Decisions Made

- Scenario selection remains data-driven through fixed ids in `SCENARIOS`; scenario ids are not treated as paths or dynamic model references.
- Rough heightfield size is clipped during sampling and the bounded value is stored in metadata, satisfying the DoS mitigation without changing the config dataclass contract in this plan.
- Reset and step info expose tuple/dict metadata directly rather than NumPy arrays so equality comparisons and JSON-like export paths remain straightforward in later evaluation phases.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The RED test run failed as expected because `src.locomotion.scenarios` did not exist yet. This confirmed the tests exercised the planned missing functionality before implementation.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None.

## Threat Flags

None.

## Verification

- `./.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py tests/locomotion/test_argus_go2_env_determinism.py -q -x` — passed, 20 tests.
- `./.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_contract.py tests/locomotion/test_argus_go2_env_scenarios.py tests/locomotion/test_argus_go2_env_determinism.py -q` — passed, 26 tests.

## Next Phase Readiness

Ready for Plan 01-03 action-mode spaces and safe decoding helpers. Scenario ids and reset metadata are now stable enough for later action helpers, environment API wiring, metrics attribution, and evaluation exports.

## Self-Check: PASSED

- Found `src/locomotion/scenarios.py`.
- Found `tests/locomotion/test_argus_go2_env_scenarios.py`.
- Found `tests/locomotion/test_argus_go2_env_determinism.py`.
- Found task commit `80c4e33`.
- Found task commit `fb39cec`.

---
*Phase: 01-locomotion-env-contract*
*Completed: 2026-04-30*
