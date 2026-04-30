---
phase: 03-locomotion-metrics-instrumentation
reviewed: 2026-04-30T15:11:52Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/locomotion/actions.py
  - src/locomotion/env.py
  - src/locomotion/metrics.py
  - src/locomotion/scenarios.py
  - tests/locomotion/test_argus_go2_env_contract.py
  - tests/locomotion/test_argus_go2_env_metrics.py
  - tests/locomotion/test_locomotion_metrics_collector.py
  - tests/locomotion/test_locomotion_metrics_foot_mapping.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-30T15:11:52Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase 03 locomotion metrics instrumentation across the environment, action helpers, scenario XML generation, metrics collector, and associated tests. The implementation introduces useful metric plumbing, but there are correctness defects that can terminate valid episodes immediately, corrupt duty-factor/contact summaries after the bounded history rolls over, and make rough-heightfield simulation fail or use incomplete terrain data.

## Critical Issues

### CR-01: Default progress-stall threshold terminates standing/zero-command episodes

**File:** `src/locomotion/metrics.py:284-302`

**Issue:** `_stability_payload` always invokes `_progress_stalled` once enough history exists, and the default `min_progress_m_per_s` is `0.03` even when the desired command is zero. The default scenario starts with a zero velocity command, and callers can also validly command `[0, 0, 0]` to stand still. After `progress_window_steps` steps without moving, `_progress_stalled` returns true and terminates the episode with `progress_stalled`, even though no forward progress was requested. This is incorrect environment behavior and invalidates standing baselines/early command-schedule windows.

**Fix:** Gate progress-stall failure on a non-trivial commanded translational speed, or disable progress checks when desired velocity is below a threshold. One concrete approach is to pass the desired command into the stability helper:

```python
# in record_step
stability, failure_reason = self._stability_payload(roll, pitch, height, xy, delta_t, desired)

# in _stability_payload
elif np.linalg.norm(desired[:2]) > 1e-6 and self._progress_stalled(distance, dt):
    failure_reason = "progress_stalled"
```

## Warnings

### WR-01: Contact summary divides lifetime contact counts by lifetime steps while aggregating only retained records

**File:** `src/locomotion/metrics.py:125-132, 230-231, 478-510`

**Issue:** `_steps` is bounded by `history_size`, but `_contact_counts`, `_slip_history`, and `_clearance_history` are unbounded lifetime episode accumulators. `_contact_terrain_summary` then uses `self._total_steps_seen` and these lifetime accumulators while `command_tracking`, `stability`, and `action_quality` summarize only retained records. Once an episode exceeds `history_size`, summaries mix different time horizons. That makes duty factor, slip, and clearance incomparable to the other summary families and can misreport the latest retained window. The unbounded per-foot lists also violate the stated bounded-history design for contact metrics.

**Fix:** Keep contact aggregation on the same bounded horizon as `_steps`. Store per-step contact booleans/slip/clearance in `LocomotionMetricStep.contact_terrain` and derive summary values from the retained `steps` list, or maintain bounded deques for contact counts/slip/clearance with the same `maxlen` as `_steps`.

### WR-02: Rough heightfield XML creates an hfield without embedding or referencing data

**File:** `src/locomotion/scenarios.py:186-195`

**Issue:** `_add_rough_heightfield` validates and reshapes `heightfield_data`, then discards `heights` and creates an `<hfield>` with only `nrow`, `ncol`, and `size`. MuJoCo hfields require either a `file` attribute or data supplied through the compiled model. In this implementation the model is compiled before `_load_heightfield_data` runs, so there may be no `hfield_data` storage to populate, or compilation can fail before the later assignment. At minimum the validated `heights` variable is dead, which is a strong signal the sampled terrain is not actually being wired into the model XML.

**Fix:** Supply hfield data through a supported MuJoCo path before compilation. For example, write a deterministic in-memory asset file and reference it from the hfield, or use the correct MJCF mechanism supported by the target MuJoCo version. If using post-compilation assignment, first create a valid hfield asset that compiles and assert `self._model.hfield_data.size == bounded_size * bounded_size` before stepping.

## Info

### IN-01: Phase-scope guard test inspects source files by string scanning instead of behavior

**File:** `tests/locomotion/test_locomotion_metrics_collector.py:244-251`

**Issue:** `test_phase3_metrics_tests_do_not_encode_deferred_scope_terms` reads test files and fails on forbidden substrings. This is brittle: comments, future legitimate test names, or documentation strings can break the suite without any behavior regression, while string concatenation already works around the guard for the terms it introduces itself.

**Fix:** Replace the source-text guard with behavior/API assertions for the Phase 03 boundary, or move scope enforcement to planning/review tooling rather than runtime unit tests.

---

_Reviewed: 2026-04-30T15:11:52Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
