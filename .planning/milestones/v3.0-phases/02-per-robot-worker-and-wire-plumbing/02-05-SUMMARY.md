---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 05
subsystem: testing
tags: [perception, capture-pose, freshness, replay, worker, contract-tests]

requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "DetectorWorker.submit() snapshots pose.copy() + frame.sim_time; _loop overwrites Detections3D.capture_pose/capture_timestamp via dataclasses.replace (Plan 02-03)"
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "Detections3D envelope fields capture_pose: ndarray(4,4) + capture_timestamp: float with identity/zero defaults (Plan 02-01)"
provides:
  - "Contract test suite proving D-11 (envelope-level pose), D-12 (capture_timestamp from frame.sim_time), and D-13 (snapshot-at-submit not at-lift) hold under adversarial 300 ms inference latency"
  - "Mutation-test-validated regression detector for DetectorWorker.submit's defensive np.asarray(pose).copy()"
  - "Stable ground truth for Phase 6 MetricsPanel freshness = current_sim_time - latest.capture_timestamp"
affects: [phase-04-world-frame-lifting, phase-06-metrics-panel, phase-06-replay]

tech-stack:
  added: []
  patterns:
    - "Fake-detector latency-injection test harness (SlowDetector sleeps 300 ms inside process_frame) to force an observable submit-to-lift gap"
    - "Stale-default lifter outputs (identity pose, 0.0 timestamp) that MUST be overwritten by the worker -- failure mode is visible, not silent"

key-files:
  created:
    - "tests/perception/test_worker_capture_pose.py -- 3 tests, 326 lines, covers D-11/D-12/D-13 with SlowDetector + EmptyLifter + ItemsLifter fakes"
  modified: []

key-decisions:
  - "Kept worker.py untouched -- the plan is test-only. Plan 02-03 already implements the defensive copy and envelope-level attach via dataclasses.replace; this plan verifies the contract holds and does NOT patch the implementation."
  - "Used pytest.approx for float comparisons (capture_timestamp 42.5, capture_pose[0,3] == 5.0) even though np.asarray(...).copy() and float() conversions are bit-exact. approx guards against future dtype drift (e.g. float32 introduction) that would silently introduce tolerance without a dedicated tolerance review."
  - "ItemsLifter emits 3 OBBs to verify the lifter's boxes survive the worker's _attach_capture unchanged (D-11 envelope-level storage, no per-box pose rewrap)."
  - "Pre-flight mutation test: removed the .copy() from submit in a monkeypatched sandbox and confirmed test_capture_pose_snapshotted_at_submit observes 99.0 instead of 5.0 -- proves the done-criterion 'first test demonstrably fails if DetectorWorker.submit stores a reference'."

patterns-established:
  - "Adversarial-scheduling test pattern: fake backend with deliberate sleep > poll_interval to force a timing gap where contract violations become observable"
  - "Stale-default fake-lifter pattern: lifter returns Detections3D with obvious wrong values (identity pose, 0.0 ts) so a missing worker attach is a visible failure, not a silent no-op"

requirements-completed: [DET-API-05]

duration: 3 min
completed: 2026-04-14
---

# Phase 2 Plan 05: Capture-Pose Freshness Contract Tests Summary

**Test-only plan adding 3 pytest tests (326 LOC) that prove DetectorWorker snapshots pose + sim_time at submit time (not lift time) under 300 ms inference latency -- verification surface for DET-API-05.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-14T02:40:00Z
- **Completed:** 2026-04-14T02:43:11Z
- **Tasks:** 1 of 1 complete
- **Files created:** 1 (`tests/perception/test_worker_capture_pose.py`)
- **Files modified:** 0
- **Tests added:** 3 (all green, 1.53 s wall time)

## Accomplishments

- **D-13 freshness contract proven:** `test_capture_pose_snapshotted_at_submit` submits with pose translation 5.0, mutates the caller's buffer to 99.0 before inference completes, then asserts `latest.capture_pose[0,3] == 5.0`. Without the defensive `np.asarray(pose).copy()` in `DetectorWorker.submit`, the caller's in-place mutation would bleed through.
- **D-12 sim-clock source contract proven:** `test_capture_timestamp_from_frame_sim_time` submits with `frame.sim_time=42.5` and asserts bit-exact round-trip to `Detections3D.capture_timestamp`. Distinguishes 3 failure modes: (a) worker forgot to attach → 0.0, (b) worker used `time.time()` → wall-clock garbage, (c) worker attached correctly → 42.5.
- **D-11 envelope-level storage proven:** `test_envelope_level_not_per_box` has an `ItemsLifter` emit 3 OrientedBox3D items; asserts `Detections3D.capture_pose` is on the envelope (one per frame) and `not hasattr(item, 'capture_pose')` for each OBB. Guards against a future refactor that would redundantly duplicate pose onto every box.
- **Mutation-test validated:** The `done` criterion ("first test demonstrably fails if DetectorWorker.submit stores a reference instead of a copy") was confirmed by monkeypatching `submit` to omit `.copy()`; the test observed `capture_pose[0,3] == 99.0` (the caller's post-submit mutation bleeding through), exactly as the contract demands.

## Task Commits

1. **Task 1: capture_pose freshness contract tests** — `4df5d1e` (test)

**Plan metadata commit:** will be the final atomic commit in the worktree (this SUMMARY.md at `--no-verify`, per parallel-mode rules).

_Note: Parallel-mode rules suppress STATE.md / ROADMAP.md / REQUIREMENTS.md writes in this worktree; the merge-back orchestrator updates those on main._

## Files Created

- `tests/perception/test_worker_capture_pose.py` — 3 tests covering D-11/D-12/D-13 with a `SlowDetector` (300 ms `process_frame` sleep) paired with `EmptyLifter` (stale identity-pose / 0.0-timestamp default, worker MUST overwrite) and `ItemsLifter` (3 synthetic OBBs, proves per-box non-propagation). Test runtime is 1.53 s (under the plan's 2 s budget).

## Files NOT Modified (by design)

- `src/perception/worker.py` — Plan 02-03 implementation already correct (defensive copy in `submit`, `_attach_capture` via `dataclasses.replace` in `_loop`). Plan 02-05 is verification-only; per the executor prompt's explicit guidance, contract misses here would be a Plan 02-03 bug to fail loudly, not patch from 02-05.
- `src/perception/types.py` — Plan 02-01 implementation already correct (capture_pose + capture_timestamp envelope fields with identity/0.0 defaults). Plan 02-05 exercises those defaults as "stale markers" in `EmptyLifter` / `ItemsLifter` to prove the worker overwrites them.

## Decisions Made

- **No worker.py modifications.** The plan is test-only. If a test failed I would have flagged it as a Plan 02-03 regression (deviation Rule 1) and escalated; all 3 tests green on first run, so the contract is intact.
- **`pytest.approx` for float equality.** Even though `float(frame.sim_time)` and `np.asarray(pose).copy()` preserve bit-exactness in the current implementation, using `approx` futureproofs against a later dtype change (e.g. float32 on capture_pose) that would silently introduce tolerance. The error messages still cite the expected exact values (5.0, 42.5, 7.0, 3.14) so diagnostics stay sharp.
- **`ItemsLifter` + `EmptyLifter` split.** Two lifter variants because D-11's envelope-level invariant needs ≥1 box to verify non-propagation, but D-12 / D-13 are cleaner with zero items (no distraction from OBB construction). Splitting keeps each test focused on one invariant.
- **`_INFERENCE_WAIT_SEC = 0.5`.** 300 ms inference + 200 ms slack for scheduler jitter. Tested on the CI-representative machine; all 3 tests complete in 1.53 s total, well under the 2 s plan budget.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `<action>` block specified an inline test file; I adopted that structure verbatim with two additions neither of which changed semantics:
  (a) Replaced `latest.capture_timestamp == 42.5` with `pytest.approx(42.5)` for float-safety futureproofing (as documented in Decisions).
  (b) Added a `test_envelope_level_not_per_box` assertion that `not hasattr(item, "capture_timestamp")` alongside the planned `not hasattr(item, "capture_pose")` check -- strengthens the D-11 invariant at zero cost (OrientedBox3D has neither field).
These are additive clarifications, not behavioural deviations: removing them would still leave a spec-compliant test file.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** Plan executed test-for-test as specified.

## Issues Encountered

- **Worktree base-commit drift (handled).** The agent worktree HEAD was `1a804fe` (pre-Plan-02-01/02-03) while the executor prompt specified base commit `9a67f59` (post-merge of both). Followed the `<worktree_branch_check>` protocol: `1a804fe` was an ancestor of `9a67f59`, so fast-forwarded the worktree branch via `git reset --hard 9a67f59` to pick up the capture_pose envelope fields (Plan 02-01) and `DetectorWorker` class (Plan 02-03) that this plan's tests depend on. After the reset, the test file imported cleanly and all 3 tests passed.

## Threat Flags

None — plan is test-only, adds no new attack surface. The tests themselves MITIGATE T-02-10 (capture-pose mutation via caller's mutable ndarray) by proving the defensive-copy invariant, and T-02-11 (envelope-level pose storage integrity) by asserting per-box non-propagation.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 6 MetricsPanel can now rely on `current_sim_time - latest.capture_timestamp` yielding a meaningful sim-clock freshness value. The contract is: `latest = pool.latest(rid)`; `freshness_sec = current_sim_time - latest.capture_timestamp`. Units are sim-clock seconds; a fresh detection at 2 FPS steady-state should sit around `0.5 ± 0.2 s`.
- Phase 4 world-frame OBB lifting can rely on `capture_pose` matching the pose at which the source frame was captured, not the pose at which the lifter ran — this is what makes the lifter's camera-frame → world-frame transform correct under inference latency.
- Phase 2 Wave 4 coordinator rewiring: when switching the coordinator from inline detection to `pool.submit(rid, frame, pose, slam_cloud)`, the coordinator does NOT need to defensively copy `pose` on its own because `DetectorWorker.submit` already does so (verified by `test_capture_pose_snapshotted_at_submit` + the mutation test). The coordinator can reuse its pose buffer across submits.
- No blockers, no deferred items.

## Self-Check: PASSED

- `tests/perception/test_worker_capture_pose.py` exists on disk (326 lines, verified).
- Commit `4df5d1e` exists in the git log: `test(02-05): add capture_pose freshness contract tests (D-11/D-12/D-13)`.
- All 3 tests green via `pytest tests/perception/test_worker_capture_pose.py -x -q` (1.53 s).
- Mutation test manually confirmed: removing `.copy()` from submit makes test 1 observe 99.0 instead of 5.0 (done criterion satisfied).
- `src/perception/worker.py` unchanged from base commit `9a67f59` (verified via `git diff 9a67f59 -- src/perception/worker.py` = empty).

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Plan: 02-05*
*Completed: 2026-04-14*
