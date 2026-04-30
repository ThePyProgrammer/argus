---
phase: 01-locomotion-env-contract
plan: 05
subsystem: locomotion
tags: [mujoco, gymnasium, locomotion, scenarios, tdd]

requires:
  - phase: 01-locomotion-env-contract
    provides: deterministic ArgusGo2Env contract, scenario catalog, action decoding, and reset/action-mode seams
provides:
  - Scenario MJCF builder for flat, low-friction, slope, rough-heightfield, and push-disturbance scenarios
  - Optional MuJoCo reset/step lifecycle in ArgusGo2Env with decoded control writes and deterministic runtime pushes
  - Integration-gated and fake-data tests pinning XML safety, yaw quaternion reset, ctrl writes, mj_step counts, and xfrc_applied clearing
affects: [locomotion-env-contract, future metrics runner, future controller evaluation]

tech-stack:
  added: []
  patterns:
    - ElementTree in-memory MJCF mutation using patched Go2 XML
    - Optional MuJoCo lifecycle guarded by import/model availability
    - Runtime push disturbance through MuJoCo xfrc_applied

key-files:
  created:
    - .planning/phases/01-locomotion-env-contract/01-05-SUMMARY.md
  modified:
    - src/locomotion/scenarios.py
    - src/locomotion/env.py
    - tests/locomotion/test_argus_go2_env_scenarios.py
    - tests/locomotion/test_argus_go2_env_contract.py

key-decisions:
  - "Push disturbance remains runtime-only metadata in MJCF generation and is applied through xfrc_applied during step."
  - "Scenario XML builder removes compiler meshdir/texturedir and returns asset bytes for from_xml_string loading."
  - "Fake-data tests cover MuJoCo step/control/push/reset semantics without requiring rendering or unsupported Python environments."

patterns-established:
  - "Scenario XML generation mutates patched XML in memory only and checks source preservation."
  - "ArgusGo2Env reset attempts MuJoCo when available but preserves pure unit-test behavior with None model/data fallback."

requirements-completed: [LOC-ENV-01, LOC-ENV-02, LOC-ENV-03]

duration: 66 min
completed: 2026-04-30
---

# Phase 1 Plan 05: Locomotion Scenario MJCF and MuJoCo Runtime Summary

**Executable Go2 scenario MJCF builder with optional MuJoCo reset/step lifecycle, deterministic spawn yaw, decoded control writes, and runtime push forces**

## Performance

- **Duration:** 66 min
- **Started:** 2026-04-30T06:38:00Z
- **Completed:** 2026-04-30T07:44:10Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Added TDD tests that first failed on missing `build_scenario_xml`, then pinned parseable scenario XML, source `go2.xml` preservation, low-friction/slope/rough-heightfield markers, integration-gated resets, step control writes, `mj_step` counts, push `xfrc_applied`, and yaw-to-quaternion reset behavior.
- Implemented `build_scenario_xml(model_dir, sample)` using `patch_actuators_to_position`, in-memory `ElementTree` mutation, floor friction updates, slope marker geometry, bounded rough heightfield assets, and Go2 asset byte loading.
- Updated `ArgusGo2Env` so reset optionally initializes MuJoCo, applies sampled spawn pose and yaw quaternion, sets standing qpos, zeroes qvel/ctrl, calls `mj_forward`, writes decoded controls to `self._data.ctrl[:]`, applies/clears push forces via `xfrc_applied`, steps exactly `sim_steps_per_frame`, and clears renderer/model/data on close.
- Verified existing bridge paths remained untouched and bridge regressions still pass.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add scenario XML and integration-gated reset/step tests** - `bced323` (test)
2. **Task 2: Implement scenario MJCF builder and env MuJoCo lifecycle/stepping** - `1c17d09` (feat)

**Plan metadata:** pending final docs commit

_Note: TDD task 1 produced the RED commit; task 2 produced the GREEN commit._

## Files Created/Modified

- `src/locomotion/scenarios.py` - Adds scenario MJCF builder, asset loading, floor/slope/rough-heightfield XML helpers, and source-safe patching flow.
- `src/locomotion/env.py` - Adds optional MuJoCo model/data lifecycle, reset qpos/qvel/ctrl initialization, configured physics stepping, runtime push force application, and close cleanup.
- `tests/locomotion/test_argus_go2_env_scenarios.py` - Adds scenario XML parseability, terrain marker, asset, and source-file preservation tests.
- `tests/locomotion/test_argus_go2_env_contract.py` - Adds integration-gated reset/step tests and fake-data unit coverage for decoder-to-ctrl writes, `mj_step`, push force lifecycle, and yaw quaternion assignment.
- `.planning/phases/01-locomotion-env-contract/01-05-SUMMARY.md` - Records execution outcome and verification.

## Decisions Made

- Kept push disturbance out of XML and applied it only at runtime through `xfrc_applied`, matching the plan threat model and preserving deterministic schedule metadata.
- Used an in-memory bounded `hfield` declaration for rough terrain and retained `heightfield_size <= 64` from sampling/config validation.
- Added fake-data tests for MuJoCo-facing semantics so correctness remains pinned even when integration tests are skipped or rendering is unavailable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed invalid MJCF hfield `data` attribute**
- **Found during:** Task 2 (Implement scenario MJCF builder and env MuJoCo lifecycle/stepping)
- **Issue:** Initial rough-heightfield XML used a `data` attribute that MuJoCo rejected with `Schema violation: unrecognized attribute: 'data'`.
- **Fix:** Replaced inline height samples with a bounded MJCF `hfield` declaration using `nrow`, `ncol`, and `size`, while keeping the `rough_heightfield` marker and bounded metadata.
- **Files modified:** `src/locomotion/scenarios.py`
- **Verification:** Focused locomotion tests and full phase gate passed.
- **Committed in:** `1c17d09`

**2. [Rule 1 - Bug] Guarded fake-data reset from real MuJoCo C-extension calls**
- **Found during:** Task 2 (Implement scenario MJCF builder and env MuJoCo lifecycle/stepping)
- **Issue:** With MuJoCo installed, fake-data unit tests could reach `mujoco.mj_resetData` using fake objects and fail type validation.
- **Fix:** Added a small real-model check before `mj_resetData`/`mj_forward`, preserving real integration behavior and fake-data unit coverage.
- **Files modified:** `src/locomotion/env.py`
- **Verification:** Fake-data contract tests and integration-gated focused tests passed.
- **Committed in:** `1c17d09`

**3. [Rule 1 - Bug] Made push active-window timing robust to discretized step counts**
- **Found during:** Task 2 (Implement scenario MJCF builder and env MuJoCo lifecycle/stepping)
- **Issue:** Test setup using `int(active_time / dt)` could land just before the sampled active window; runtime logic itself needed tolerance for floating point comparisons.
- **Fix:** Added an active-window epsilon and adjusted the fake-data test to start at the first step inside the sampled window.
- **Files modified:** `src/locomotion/env.py`, `tests/locomotion/test_argus_go2_env_contract.py`
- **Verification:** Push active/clear assertions passed.
- **Committed in:** `1c17d09`

---

**Total deviations:** 3 auto-fixed (3 bugs)
**Impact on plan:** All fixes were required for correctness and testability of the planned MuJoCo scenario/runtime behavior. No scope creep.

## Issues Encountered

- The isolated worktree did not contain `.venv/bin/python`; per user constraint to use the project venv rather than system Python 3.14, tests were run with `/home/prannayag/pragnition/robotics/argus/.venv/bin/python`.
- Pytest emitted existing warnings about unknown asyncio config options; tests still passed and no config files were changed.

## Verification

- RED observed before implementation: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py tests/locomotion/test_argus_go2_env_contract.py -q -x` failed with `ImportError: cannot import name 'build_scenario_xml'`.
- Focused: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_argus_go2_env_scenarios.py tests/locomotion/test_argus_go2_env_contract.py -q -x` — 41 passed.
- Regression: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q -x` — 21 passed.
- Full phase gate candidate: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` — 121 passed.

## Known Stubs

None found in files created/modified for this plan.

## Threat Flags

None. The new MJCF, filesystem model-dir, reset, action/control, and runtime force surfaces were already covered by the plan threat model.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 1 now has an executable scenario-backed MuJoCo environment contract with deterministic scenario metadata and runtime stepping semantics. Ready for orchestrator merge and Phase 1 verification.

## Self-Check: PASSED

- Found `.planning/phases/01-locomotion-env-contract/01-05-SUMMARY.md`.
- Found task commits `bced323` and `1c17d09` in git log.
- Confirmed no changes to `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`, or `src/main.py`.

---
*Phase: 01-locomotion-env-contract*
*Completed: 2026-04-30*
