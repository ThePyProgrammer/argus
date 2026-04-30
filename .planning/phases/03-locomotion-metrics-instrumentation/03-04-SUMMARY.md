---
phase: 03-locomotion-metrics-instrumentation
plan: 04
subsystem: testing
tags: [pytest, locomotion, metrics, nyquist, traceability]
requires:
  - phase: 03-03
    provides: env metrics wiring, terminal summaries, and fake-env locomotion metrics assertions
provides:
  - behavior-level traceability for LOC-METRICS-01 through LOC-METRICS-04
  - behavior-level traceability for locked decisions D-01 through D-16
  - Phase 3 quick/wave/full validation results with implementation gap documented
affects: [phase-03-validation, phase-04-evaluation-runner]
tech-stack:
  added: []
  patterns:
    - pytest docstring/comment traceability for requirements and locked decisions
    - test-only source-scope guard for deferred Phase 4 terms
key-files:
  created:
    - .planning/phases/03-locomotion-metrics-instrumentation/03-04-SUMMARY.md
  modified:
    - tests/locomotion/test_locomotion_metrics_collector.py
    - tests/locomotion/test_locomotion_metrics_foot_mapping.py
    - tests/locomotion/test_argus_go2_env_metrics.py
key-decisions:
  - "Kept Plan 04 test-only: production behavior gaps were documented for replanning instead of patched in this worktree."
  - "Used the repository project venv at /home/prannayag/pragnition/robotics/argus/.venv/bin/python because the worktree does not contain its own .venv symlink."
patterns-established:
  - "Metrics tests carry grep-visible requirement and decision IDs adjacent to behavior-level assertions."
  - "Deferred Phase 4 scope strings are guarded without embedding literal forbidden terms outside out-of-scope comments/constants."
requirements-completed: [LOC-METRICS-01, LOC-METRICS-02, LOC-METRICS-03, LOC-METRICS-04]
duration: 5min
completed: 2026-04-30
---

# Phase 03 Plan 04: Locomotion Metrics Validation Hardening Summary

**Phase 3 locomotion metrics tests now encode requirement/decision traceability and expose one non-Phase-3 fake-MuJoCo validation gap for replanning.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-30T14:59:37Z
- **Completed:** 2026-04-30T15:04:18Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added grep-visible `LOC-METRICS-01` through `LOC-METRICS-04` and `D-01` through `D-16` traceability near behavior-level metrics assertions.
- Hardened threat regression tests for malformed metric inputs/config, bounded history, compact nested info payload, proxy label integrity, strict foot mapping, and no raw MuJoCo array sprawl.
- Ran quick, wave, and full Phase 3 validation commands and documented the remaining implementation/test-fixture gap without modifying production code.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add source-audit and threat regression assertions to metrics tests** - `6f5ab9d` (test)
2. **Task 2: Run final Phase 3 validation commands and record any implementation gaps** - `6ead42f` (test, empty validation-record commit)

**Plan metadata:** committed separately after this summary.

## Files Created/Modified

- `tests/locomotion/test_locomotion_metrics_collector.py` - Added requirement/decision traceability, malformed input/config assertions, proxy-label assertions, bounded compact payload assertions, and a deferred-scope guard.
- `tests/locomotion/test_locomotion_metrics_foot_mapping.py` - Added LOC-METRICS-04/D-09 through D-12 traceability and strict malformed contact payload assertions.
- `tests/locomotion/test_argus_go2_env_metrics.py` - Added D-01 through D-08/LOC-METRICS-01/02 traceability and compact info/no raw MuJoCo payload assertions.
- `.planning/phases/03-locomotion-metrics-instrumentation/03-04-SUMMARY.md` - This execution summary.

## Decisions Made

- Kept this plan test-only as instructed. The wave/full suite failure points at a production/test-fixture mismatch outside the three listed Phase 3 metrics test files, so it is recorded below rather than fixed here.
- Used `/home/prannayag/pragnition/robotics/argus/.venv/bin/python` to run validation because `.venv/bin/python` is absent inside the worktree checkout.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used parent project virtualenv for verification**
- **Found during:** Task 1 verification
- **Issue:** The exact worktree-relative command `.venv/bin/python ...` failed because the worktree has no `.venv` directory.
- **Fix:** Ran equivalent validation through `/home/prannayag/pragnition/robotics/argus/.venv/bin/python`.
- **Files modified:** None
- **Verification:** Quick metrics test command passed through the project venv.
- **Committed in:** N/A, no file changes

**2. [Rule 1 - Test bug] Fixed self-referential deferred-scope guard**
- **Found during:** Task 1 verification
- **Issue:** The new guard failed on its own out-of-scope comment because it removed only the phrase `out-of-scope`, leaving the documented forbidden examples searchable.
- **Fix:** Changed the guard to ignore lines containing `out-of-scope` before searching forbidden deferred-scope strings.
- **Files modified:** `tests/locomotion/test_locomotion_metrics_collector.py`
- **Verification:** Quick metrics test command passed.
- **Committed in:** `6f5ab9d`

---

**Total deviations:** 2 auto-fixed (1 blocking environment issue, 1 test assertion bug)
**Impact on plan:** No production code or Phase 4 scope was added.

## Validation Results

- Quick command: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_metrics_foot_mapping.py tests/locomotion/test_argus_go2_env_metrics.py -q` -> **23 passed, 2 existing pytest config warnings**.
- Wave command: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion tests/metrics -q` -> **1 failed, 190 passed, 2 existing pytest config warnings**.
- Full command: `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion tests/metrics tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` -> **1 failed, 226 passed, 2 existing pytest config warnings**.
- Scope guard grep: `grep -R -n "jsonl\|csv\|evaluation_runner\|rl_policy\|mpc\|wbc\|ros2\|frontend" tests/locomotion/test_locomotion_metrics_collector.py tests/locomotion/test_locomotion_metrics_foot_mapping.py tests/locomotion/test_argus_go2_env_metrics.py | grep -v "out-of-scope"` -> **no matches**.

## Issues Encountered

### Implementation gap for replanning

- **Failing test:** `tests/locomotion/test_argus_go2_env_contract.py::test_reset_rebuilds_mujoco_model_for_new_randomized_terrain_sample`
- **Failure:** `Go2FootMapping.from_mujoco_model()` calls `mujoco.mj_name2id` and `mujoco.mjtObj.mjOBJ_GEOM`, but this existing contract test patches `sys.modules["mujoco"]` with a fake object that does not provide those attributes.
- **Why not fixed here:** Plan 04 explicitly allowed changes only to the three Phase 3 metrics tests and instructed that production gaps should be recorded in the summary for replanning rather than patched.
- **Likely follow-up:** Adjust the contract test fake MuJoCo module to include strict foot mapping APIs, or update env reset test seams so fake terrain-rebuild tests can satisfy the new Phase 3 strict foot mapping dependency.

## Known Stubs

None found in files modified by this plan.

## Threat Flags

None. This plan modified tests only and introduced no new runtime network, auth, file-access, schema, or trust-boundary surface.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 3 metrics-specific quick validation is green and traceability coverage is strengthened. Phase closure should not claim the full wave/full validation gate is green until the fake-MuJoCo foot mapping gap above is resolved or explicitly waived by the orchestrator.

## Self-Check: PASSED

- FOUND: `.planning/phases/03-locomotion-metrics-instrumentation/03-04-SUMMARY.md`
- FOUND: task commit `6f5ab9d`
- FOUND: task commit `6ead42f`

---
*Phase: 03-locomotion-metrics-instrumentation*
*Completed: 2026-04-30*
