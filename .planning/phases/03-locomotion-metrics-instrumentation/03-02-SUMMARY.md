---
phase: 03-locomotion-metrics-instrumentation
plan: 02
subsystem: locomotion-metrics
tags: [python, pytest, numpy, mujoco, locomotion, metrics]

requires:
  - phase: 03-locomotion-metrics-instrumentation
    plan: 01
    provides: core locomotion metrics collector and nested contact_terrain family
provides:
  - Strict Go2 foot geom mapping for FL, FR, RL, and RR
  - Terrain-height helper for plane, slope, and rough heightfield scenarios
  - Per-step contact, slip, clearance, and transition metrics
  - Episode contact/terrain summaries with duty factor, slip, clearance, gait balance, and scenario success
  - Focused pytest coverage for LOC-METRICS-04 and D-09 through D-12
affects: [phase-03-env-metrics-wiring, phase-04-cli-evaluation-runner, locomotion-benchmarks]

tech-stack:
  added: []
  patterns: [strict MuJoCo name resolution, bounded collector histories, terrain-relative clearance, compact per-foot scalar payloads]

key-files:
  created:
    - tests/locomotion/test_locomotion_metrics_foot_mapping.py
  modified:
    - src/locomotion/metrics.py
    - src/locomotion/scenarios.py

key-decisions:
  - "Resolved Go2 feet only by exact MuJoCo geom names FL, FR, RL, and RR; no substring or prefixed fallback was added in Phase 3."
  - "Implemented rough-heightfield clearance using explicit sampled heightfield data and x/y extents rather than defaulting non-flat terrain to zero height."
  - "Kept contact/terrain payloads compact by exposing per-foot scalar dictionaries, not raw MuJoCo contact objects or unbounded position arrays."

requirements-completed: [LOC-METRICS-04]

duration: 52min
completed: 2026-04-30T14:52:36Z
---

# Phase 03 Plan 02: Strict Foot Mapping and Contact Terrain Metrics Summary

**Strict MuJoCo Go2 foot identity with terrain-relative contact, slip, clearance, duty-factor, and scenario-success metrics**

## Performance

- **Duration:** 52 min
- **Started:** 2026-04-30T14:00:00Z
- **Completed:** 2026-04-30T14:52:36Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `Go2FootMapping.from_mujoco_model()` with exact `mujoco.mj_name2id(..., mjOBJ_GEOM, name)` lookup for `FL`, `FR`, `RL`, and `RR`.
- Added fail-fast validation for missing required foot geoms, duplicate geom ids, and no substring fallback behavior.
- Added `terrain_height_at(sample, x, y)` for plane, slope, and rough heightfield terrain height estimates.
- Added rough-heightfield metadata plumbing for `heightfield_extent_x` and `heightfield_extent_y` in scenario samples.
- Extended `LocomotionMetricsCollector.record_step()` with optional contact inputs: `foot_positions_world`, `foot_contacts`, `terrain_height_m`, and `scenario_failed`.
- Added compact per-step `contact_terrain` dictionaries for per-foot contact booleans, contact-only XY slip velocity, terrain-relative clearance, and transition labels.
- Added episode summary fields for duty factor, slip mean/max, clearance min/max, gait symmetry contact balance, and scenario success.
- Added `foot_contact_payload_from_mujoco()` helper to convert `data.geom_xpos` and `data.contact` into collector-ready per-foot inputs.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create strict foot mapping and contact proxy tests** - `af069ce` (test)
2. **Task 2: Implement Go2 foot mapping and contact terrain aggregation** - `422a60d` (feat)

**Plan metadata:** committed after this summary is written.

_Note: This plan followed the TDD gate sequence with a failing test commit before implementation._

## Files Created/Modified

- `src/locomotion/metrics.py` - Adds strict foot mapping, MuJoCo contact extraction helper, terrain-height helper, contact metric recording, and contact/terrain summary aggregation.
- `src/locomotion/scenarios.py` - Adds explicit rough-heightfield x/y extent metadata for terrain-height sampling.
- `tests/locomotion/test_locomotion_metrics_foot_mapping.py` - Covers strict foot mapping, missing/duplicate/no-heuristic failures, per-step contact metrics, duty factor, scenario success, and plane/slope/rough terrain height helpers.

## Decisions Made

- Exact foot geom names are the only accepted Phase 3 mapping contract: `FL`, `FR`, `RL`, and `RR`.
- Slope terrain height uses the existing generated slope marker convention: `tan(slope_radians) * x + slope_z_offset`, with the default offset matching the marker `z=-0.04`.
- Rough terrain height uses bilinear sampling over explicit heightfield extents and stored `heightfield_data`.
- Slip history currently records zero for first-contact/no-previous-position steps, keeping per-foot histories aligned with step count for summary mean/max calculations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used project root virtualenv because the worktree has no local `.venv`**
- **Found during:** Task 1 and Task 2 verification
- **Issue:** The planned `.venv/bin/python` path does not exist inside this git worktree.
- **Fix:** Ran verification with `/home/prannayag/pragnition/robotics/argus/.venv/bin/python`, the project root virtualenv established by Phase 3 research and Plan 01.
- **Files modified:** None
- **Verification:** `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest ...`
- **Committed in:** N/A (environment execution adjustment)

**2. [Rule 2 - Missing Critical Functionality] Added rough-heightfield x/y extent metadata**
- **Found during:** Task 2 implementation
- **Issue:** Rough-heightfield samples carried `heightfield_data` and `heightfield_size`, but not explicit x/y extents needed to map world coordinates back into the generated hfield grid.
- **Fix:** Added `heightfield_extent_x` and `heightfield_extent_y` metadata in `src/locomotion/scenarios.py`, matching the generated MuJoCo hfield size convention.
- **Files modified:** `src/locomotion/scenarios.py`
- **Verification:** Foot mapping/terrain tests passed.
- **Committed in:** `422a60d`

---

**Total deviations:** 2 auto-handled (1 blocking environment adjustment, 1 missing critical metadata fix)
**Impact on plan:** The changes were required to verify and correctly compute terrain-relative clearance. No Phase 4 export or env wiring scope was added.

## Issues Encountered

- The RED run failed as expected before implementation with `ImportError: cannot import name 'FOOT_GEOM_NAMES' from 'src.locomotion.metrics'`.
- Existing pytest configuration warnings remain pre-existing: `asyncio_default_fixture_loop_scope` and `asyncio_mode` unknown config options.

## Verification

- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/tests/locomotion/test_locomotion_metrics_collector.py /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/tests/locomotion/test_locomotion_metrics_foot_mapping.py -q` -> 13 passed, 2 pre-existing pytest config warnings.
- Grep acceptance checks passed for `FOOT_GEOM_NAMES`, `mjOBJ_GEOM`, duplicate foot id validation, `duty_factor`, `terrain_height_at`, `heightfield_data`, and required test definitions/assertions.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None. The new MuJoCo model/contact/summary trust boundaries are covered by the plan threat model and mitigated through exact geom-name resolution, finite input validation, bounded collector histories, and compact scalar dictionaries.

## Next Phase Readiness

Plan 03 can wire `Go2FootMapping`, `foot_contact_payload_from_mujoco()`, `terrain_height_at()`, and the extended `LocomotionMetricsCollector.record_step()` into `ArgusGo2Env.reset()` and `ArgusGo2Env.step()` without changing the compact nested payload family contract established by Plan 01.

## Self-Check: PASSED

- Found modified file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/src/locomotion/metrics.py`
- Found modified file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/src/locomotion/scenarios.py`
- Found created file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/tests/locomotion/test_locomotion_metrics_foot_mapping.py`
- Found summary file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a2465290afa2d2d8a/.planning/phases/03-locomotion-metrics-instrumentation/03-02-SUMMARY.md`
- Found task commit: `af069ce`
- Found task commit: `422a60d`

---
*Phase: 03-locomotion-metrics-instrumentation*
*Completed: 2026-04-30*
