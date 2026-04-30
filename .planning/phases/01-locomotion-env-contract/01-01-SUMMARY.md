---
phase: 01-locomotion-env-contract
plan: 01
subsystem: locomotion
tags: [python, gymnasium, mujoco, locomotion, unitree-go2, pytest]

requires: []
provides:
  - Gymnasium-style ArgusGo2Env reset/step contract for LOC-ENV-01
  - State-only Go2 observation helpers for qpos, qvel, command, and previous_action
  - Focused contract tests for default config, spaces, reset, and step semantics
affects: [controller-plugin-baseline, locomotion-metrics-instrumentation, evaluation-runner-and-regression]

tech-stack:
  added: [gymnasium>=1.3.0]
  patterns:
    - Gymnasium Env subclass with super().reset(seed=seed)
    - State-only observation extraction from optional MuJoCo data
    - Velocity-command action validation before gait-control conversion

key-files:
  created:
    - tests/locomotion/test_argus_go2_env_contract.py
    - src/locomotion/env.py
    - src/locomotion/observations.py
  modified:
    - pyproject.toml
    - src/locomotion/__init__.py

key-decisions:
  - "ArgusGo2Env does not import MuJoCo at module import time; model loading is deferred behind explicit reset options for future integration work."
  - "Phase 1 Plan 01 keeps the action mode scope to velocity_command while preserving reproducibility metadata required by later scenario/action plans."

patterns-established:
  - "Gymnasium contract boundary: reset returns (observation, info), step returns (observation, reward, terminated, truncated, info)."
  - "Observation helpers zero-fill qpos/qvel when MuJoCo data is not loaded, keeping contract tests state-only and fast."

requirements-completed: [LOC-ENV-01]

duration: 3 min
completed: 2026-04-30
---

# Phase 1 Plan 01: ArgusGo2Env Contract Summary

**Gymnasium reset/step boundary for Go2 velocity-command locomotion with state-only observations and LOC-ENV-01 contract tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-30T06:42:47Z
- **Completed:** 2026-04-30T06:46:24Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added `gymnasium>=1.3.0` as the hard runtime dependency for the benchmark environment API.
- Added focused LOC-ENV-01 tests covering import/config behavior, Gymnasium spaces, seeded reset info, and five-value step returns.
- Implemented `ArgusGo2Env`, `ArgusGo2EnvConfig`, and observation helpers without modifying existing bridge files.
- Preserved reproducibility metadata keys in reset/step `info`: seed, scenario id, action mode, step count, sim time, sampled parameters, command schedule, and disturbance schedule.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add dependency and LOC-ENV-01 contract tests before implementation** - `3388ebb` (test)
2. **Task 2: Implement ArgusGo2Env reset/step contract and observation helpers** - `da35479` (feat)

**Plan metadata:** pending at summary creation

_Note: This TDD plan produced the required RED `test(...)` commit followed by the GREEN `feat(...)` commit._

## Files Created/Modified

- `pyproject.toml` - Adds the `gymnasium>=1.3.0` runtime dependency after MuJoCo.
- `tests/locomotion/test_argus_go2_env_contract.py` - Encodes the LOC-ENV-01 import, config, space, reset, and step contract tests.
- `src/locomotion/env.py` - Defines `ArgusGo2EnvConfig` and `ArgusGo2Env(gymnasium.Env)` with validated velocity-command stepping.
- `src/locomotion/observations.py` - Defines Gymnasium Dict observation space and zero-fill/copy observation extraction helpers.
- `src/locomotion/__init__.py` - Exports `ArgusGo2Env` and `ArgusGo2EnvConfig` from the locomotion package.

## Decisions Made

- Deferred MuJoCo imports and model loading out of module import and default reset paths, so contract tests can remain fast and state-only while future plans wire concrete scenario/model lifecycle.
- Kept Plan 01 action support intentionally limited to `velocity_command`, matching the plan scope; later Phase 1 plans own joint-position and residual action modes.
- Used empty `sampled_parameters`, `command_schedule`, and `disturbance_schedule` values as intentional metadata placeholders for later scenario/determinism plans, not UI-rendered stubs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing Gymnasium dependency in the project venv**
- **Found during:** Task 2 (Implement ArgusGo2Env reset/step contract and observation helpers)
- **Issue:** Focused tests failed with `ModuleNotFoundError: No module named 'gymnasium'` even after adding the dependency to `pyproject.toml`; the local venv had no `pip` module.
- **Fix:** Installed `gymnasium>=1.3.0` into the existing `.venv` with `uv pip install --python .venv/bin/python "gymnasium>=1.3.0"`.
- **Files modified:** None tracked beyond the planned `pyproject.toml` dependency change.
- **Verification:** `.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` passed.
- **Committed in:** N/A (environment-only fix; no tracked file changes)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Local dependency installation was required to execute the planned Gymnasium tests. No product scope changed.

## Issues Encountered

- The local `.venv` did not include `pip`; dependency installation used `uv pip install --python` instead.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `src/locomotion/env.py` returns empty `sampled_parameters`, `command_schedule`, and `disturbance_schedule` metadata by design for Plan 01. These are required keys for reproducibility and are populated by later Phase 1 scenario/determinism plans.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: local-api-boundary | `src/locomotion/env.py` | Introduces a local Gymnasium environment API where caller-provided actions are validated for shape and finite values before control conversion. |

## TDD Gate Compliance

- RED gate: `3388ebb` (`test(01-01): add ArgusGo2Env contract tests`) added tests and failed before implementation because `src.locomotion.env` did not exist.
- GREEN gate: `da35479` (`feat(01-01): implement ArgusGo2Env contract`) implemented the contract and passed focused tests.

## Verification

- `.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_contract.py -q -x` — passed, 5 tests.
- `.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_contract.py tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` — passed, 26 tests.
- Bridge file modification check — passed; no `src/bridge/*` or `tests/bridge/*` files changed in plan commits.

## Next Phase Readiness

- Ready for Plan 01-02 to add the named scenario catalog and deterministic reset metadata for LOC-ENV-02/03.
- The Gymnasium boundary now exists for future controller, metrics, and evaluation phases.

## Self-Check: PASSED

- Found all expected created/modified files: `pyproject.toml`, `tests/locomotion/test_argus_go2_env_contract.py`, `src/locomotion/env.py`, `src/locomotion/observations.py`, `src/locomotion/__init__.py`, and this summary.
- Verified task commits exist: `3388ebb` and `da35479`.
- Re-ran focused and wave-gate tests successfully.

---
*Phase: 01-locomotion-env-contract*
*Completed: 2026-04-30*
