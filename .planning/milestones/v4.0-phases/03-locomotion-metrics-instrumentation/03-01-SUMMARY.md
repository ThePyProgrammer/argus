---
phase: 03-locomotion-metrics-instrumentation
plan: 01
subsystem: locomotion-metrics
tags: [python, pytest, numpy, locomotion, metrics, gymnasium]

requires:
  - phase: 02-controller-plugin-baseline
    provides: controller protocol seam and validated 12-joint target path
provides:
  - Core locomotion metrics collector for command tracking, stability, and action quality
  - Copied public Go2 joint-position bounds helper for metrics consumers
  - Focused pytest coverage for LOC-METRICS-01, LOC-METRICS-02, and LOC-METRICS-03
  - Bounded history and baseline-preserving episode reset semantics
affects: [phase-03-env-metrics-wiring, phase-04-cli-evaluation-runner, locomotion-benchmarks]

tech-stack:
  added: []
  patterns: [dataclass config and records, deque bounded histories, nested metric-family payloads, position-servo proxy labels]

key-files:
  created:
    - src/locomotion/metrics.py
    - tests/locomotion/test_locomotion_metrics_collector.py
  modified:
    - src/locomotion/actions.py

key-decisions:
  - "Kept contact_terrain as a compact pass-through family in Plan 01 so Plan 02 can extend contact and terrain semantics without redefining core payload shape."
  - "Count clipped_target_count as targets beyond joint bounds, while near_joint_limit_count and position_target_saturation_proxy count targets inside the configured saturation margin."

patterns-established:
  - "LocomotionMetricsCollector.record_step validates exact finite vector shapes before recording metric state."
  - "latest_info_payload() exposes only nested command_tracking, stability, action_quality, and contact_terrain families."
  - "episode_summary() keeps fall_rate nested under stability and never emits top-level fall_rate in per-step info."

requirements-completed: [LOC-METRICS-01, LOC-METRICS-02, LOC-METRICS-03]

duration: 45min
completed: 2026-04-30
---

# Phase 03 Plan 01: Core Locomotion Metrics Collector Summary

**Controller-agnostic locomotion metrics collector with command tracking, stability/failure summaries, position-servo action-quality proxies, and bounded per-step payloads**

## Performance

- **Duration:** 45 min
- **Started:** 2026-04-30T14:00:00Z
- **Completed:** 2026-04-30T14:45:48Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added red/green pytest coverage for command tracking errors, stability failure summaries, action-quality proxy metrics, baseline-preserving episode resets, and bounded finite payloads.
- Added `joint_position_bounds()` to return copied Go2 12-joint low/high position bounds without exposing mutable module arrays.
- Implemented `LocomotionMetricsConfig`, `LocomotionMetricStep`, `LocomotionEpisodeSummary`, and `LocomotionMetricsCollector` with finite shape validation and nested metric families.
- Implemented command tracking signed/absolute errors and RMSE summaries for `vx`, `vy`, and `yaw_rate`.
- Implemented stability records and summaries including roll, pitch, base height, base-height deviation, XY distance, failure reason, fall count, nested single-episode fall rate, and distance before failure.
- Implemented action quality metrics including action delta norm, jerk proxy norm, joint-limit violation counts, per-joint violation dictionaries, `position_servo_effort_proxy`, `position_target_saturation_proxy`, `near_joint_limit_count`, and `clipped_target_count`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create core collector tests for command, stability, and action quality** - `e007d66` (test)
2. **Task 2: Implement metrics config, collector records, summaries, and joint-bound helper** - `ffeda74` (feat)

**Plan metadata:** committed after this summary is written.

_Note: This plan followed the TDD gate sequence with a failing test commit before implementation._

## Files Created/Modified

- `src/locomotion/actions.py` - Adds public copied `joint_position_bounds()` helper for metrics and future env wiring.
- `src/locomotion/metrics.py` - Defines the core locomotion metrics config, per-step record, episode summary, collector, validation, and aggregation logic.
- `tests/locomotion/test_locomotion_metrics_collector.py` - Covers command tracking, stability/failure semantics, action-quality proxies, reset/baseline behavior, and bounded finite payloads.

## Decisions Made

- Kept Plan 01 contact/terrain handling intentionally compact as an always-present `contact_terrain` family, with detailed foot/contact semantics deferred to Plan 02.
- Treated `clipped_target_count` as out-of-bounds/clipping evidence rather than merely being near a legal bound; near-limit legal targets are counted by `near_joint_limit_count` and `position_target_saturation_proxy`.
- Used single-episode `fall_rate` semantics exactly as planned: `1.0` when a failure reason exists, `0.0` otherwise, nested under summary `stability` only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used project root virtualenv because the worktree has no local `.venv`**
- **Found during:** Task 1 verification
- **Issue:** The planned `.venv/bin/python` path did not exist inside the git worktree.
- **Fix:** Ran verification with `/home/prannayag/pragnition/robotics/argus/.venv/bin/python`, the project root virtualenv referenced by Phase 3 research.
- **Files modified:** None
- **Verification:** `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest tests/locomotion/test_locomotion_metrics_collector.py -q`
- **Committed in:** N/A (environment execution adjustment)

**2. [Rule 1 - Bug] Corrected clipped target semantics during implementation**
- **Found during:** Task 2 verification
- **Issue:** Initial implementation counted exact legal joint bounds as clipped targets, conflating clipping with near-limit saturation.
- **Fix:** Changed `clipped_target_count` to count targets outside bounds while retaining near-bound legal targets under `near_joint_limit_count` and `position_target_saturation_proxy`.
- **Files modified:** `src/locomotion/metrics.py`
- **Verification:** Collector pytest file passed.
- **Committed in:** `ffeda74`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were required for reliable verification and correct action-quality semantics. No scope creep.

## Issues Encountered

- The first RED run failed as expected with `ModuleNotFoundError: No module named 'src.locomotion.metrics'` before implementation.
- The action-quality test fixture initially reused front-leg upper bounds for rear thigh joints; the test target was corrected to match the asymmetric Go2 joint bounds exposed by `joint_position_bounds()`.
- Existing pytest configuration warnings remain pre-existing: `asyncio_default_fixture_loop_scope` and `asyncio_mode` unknown config options.

## Verification

- `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest /home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a721544548d8a68bf/tests/locomotion/test_locomotion_metrics_collector.py -q` -> 5 passed, 2 pre-existing pytest config warnings.
- Grep acceptance checks passed for `joint_position_bounds`, `LocomotionMetricsConfig`, `LocomotionMetricsCollector`, `position_servo_effort_proxy`, absence of physical energy names, and nested `fall_rate` implementation.

## Known Stubs

None.

## User Setup Required

None - no external service configuration required.

## Threat Flags

None. The new metrics collector is an internal simulation telemetry component and implements the plan's threat mitigations for finite input validation, bounded histories, proxy labels, and compact payload families.

## Next Phase Readiness

Plan 02 can extend the always-present `contact_terrain` family with strict Go2 foot mapping, contact timing, slip, and clearance metrics. Plan 03 can wire `LocomotionMetricsCollector` into `ArgusGo2Env.step()` using the stable nested payload and episode summary contracts from this plan.

## Self-Check: PASSED

- Found created file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a721544548d8a68bf/src/locomotion/metrics.py`
- Found created file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a721544548d8a68bf/tests/locomotion/test_locomotion_metrics_collector.py`
- Found modified file: `/home/prannayag/pragnition/robotics/argus/.claude/worktrees/agent-a721544548d8a68bf/src/locomotion/actions.py`
- Found task commit: `e007d66`
- Found task commit: `ffeda74`

---
*Phase: 03-locomotion-metrics-instrumentation*
*Completed: 2026-04-30*
