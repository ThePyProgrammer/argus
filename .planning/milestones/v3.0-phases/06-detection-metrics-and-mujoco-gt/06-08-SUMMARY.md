---
phase: 6
plan: 8
subsystem: backend-web
tags: [perception, metrics, streaming, integration, runtime-guard]
requires:
  - src/metrics/detection_metrics_tracker.py (Plan 04 — DetectionMetricsTracker w/ get_stats_payload)
  - src/metrics/detection_export.py (Plan 06 — DetectionExportWriter w/ rotate)
  - src/metrics/mujoco_gt.py (Plan 05 — MuJoCoGTExtractor)
provides:
  - backend.web.streaming_viz.WebStreamingViz (extended)
  - backend.web.streaming_viz._assert_no_map_keys (new module-level guard)
  - backend.web.streaming_viz._FORBIDDEN_METRIC_KEYS (frozenset)
  - public accessors: detection_metrics_tracker, detection_export, gt_extractor, current_session_id(), attach_gt_extractor()
affects:
  - Plan 09 REST route (consumes WebStreamingViz.current_session_id + .detection_export.path)
  - Plan 10 coordinator pump (consumes .detection_metrics_tracker + .detection_export + .gt_extractor)
  - Plan 11 frontend store (consumes detection_metrics + detection_history + detection_gt_metrics payload keys)
  - Plan 12 grep test (runtime-guard companion to the source-level grep)
tech-stack:
  added: []
  patterns: [composition-over-inheritance, graceful-degradation, defense-in-depth, uuid4-session-ids]
key-files:
  created:
    - tests/contract/test_no_map_in_payload.py (replaced Wave 0 stub with 8 real tests)
  modified:
    - backend/web/streaming_viz.py (+128 lines: imports, composition fields, 5 public accessors, recursive mAP-key guard, payload extension in _update_stats, writer rotation in reset_cloud_tracking)
decisions:
  - Module-level _assert_no_map_keys walks dicts AND lists recursively — any forbidden key at any depth (including inside the new detection_gt_metrics) raises at payload-build time.
  - reset_cloud_tracking rotates the export writer to a fresh UUID4 session id but deliberately does NOT clear the detection tracker — matches the SLAM tracker baseline-preservation pattern (CONTEXT D-12).
  - attach_gt_extractor is a post-construction hook: bootstrap code calls it once mj_model/mj_data exist; on ValueError/FileNotFoundError/OSError the extractor is set to None and a warning is logged (T-6-08 graceful degradation — coordinator boot never crashes on bad YAML).
  - Payload construction is additive only — all three existing SLAM keys (slam_metrics, baseline, metric_history) preserved; three new detection keys (detection_metrics, detection_history, detection_gt_metrics) added in one dict literal.
metrics:
  completed: 2026-04-15
  duration: ~15 minutes
  tasks: 2
  tests-added: 8 (all passing)
  lines-added: 235
  lines-removed: 20
requirements-completed:
  - DET-METRICS-01
  - DET-METRICS-03
  - DET-METRICS-04
---

# Phase 6 Plan 8: WebStreamingViz Detection-Metrics Composition + Runtime Guard Summary

Composed `DetectionMetricsTracker`, `DetectionExportWriter`, and optional `MuJoCoGTExtractor` into `WebStreamingViz`; extended the `_update_stats` WebSocket payload to additively carry `detection_metrics` + `detection_history` + `detection_gt_metrics`; shipped a recursive payload-time guard (`_assert_no_map_keys`) that rejects `mAP`/`map_50`/`map_75`/`mean_average_precision` keys at any nesting depth as defense-in-depth for SC#3.

## What Shipped

### 1. WebStreamingViz composition fields (Task 1)

`WebStreamingViz.__init__` now constructs four new instance attributes alongside the existing `_metrics_tracker`:

```python
self._detection_metrics_tracker = DetectionMetricsTracker(history_size=60)
self._session_id: str = uuid.uuid4().hex
self._detection_export = DetectionExportWriter(self._session_id)
self._gt_extractor: MuJoCoGTExtractor | None = None
```

The GT extractor defaults to `None`; it is set later by `attach_gt_extractor(mapping_yaml_path, mj_model, mj_data)` which catches `ValueError`/`FileNotFoundError`/`OSError` and logs a warning — coordinator boot is never crashed by a bad YAML file (T-6-08).

### 2. Public accessor surface

Five new members exposed for Plan 09 REST and Plan 10 coordinator:

| Accessor | Type | Caller |
|----------|------|--------|
| `detection_metrics_tracker` | `DetectionMetricsTracker` property | Plan 10 coordinator pump (`record_frame`, `record_gt_match`) |
| `detection_export` | `DetectionExportWriter` property | Plan 10 coordinator pump (`append`); Plan 09 REST handler (`.path`) |
| `gt_extractor` | `MuJoCoGTExtractor \| None` property | Plan 10 coordinator pump (`match_detection`) |
| `current_session_id()` | `() -> str` method | Plan 09 REST handler (filename header) |
| `attach_gt_extractor(...)` | builder | `src/main.py` at coordinator boot |

### 3. Runtime mAP-key guard (T-6-01 / D-10)

Module-level helper recursively walks dict keys AND list elements, raising `AssertionError` on any forbidden key at any nesting depth:

```python
_FORBIDDEN_METRIC_KEYS = frozenset({
    "mAP", "map_50", "map_75", "mean_average_precision",
})

def _assert_no_map_keys(obj: Any, path: str = "$") -> None:
    ...
```

Called once per stats emit — immediately before the payload is enqueued. The recursive descent is the only correct design: forbidden keys nested under `detection_gt_metrics[rid][class_name]` (three levels deep) would otherwise slip past a shallow check.

### 4. Stats payload extension (SC#2 revision 2026-04-15)

`_update_stats` now forwards ALL THREE keys from `detection_metrics_tracker.get_stats_payload()` into the STATS WebSocket frame:

```python
detection_payload = self._detection_metrics_tracker.get_stats_payload()
payload = {
    "total_coverage": total_coverage,
    "merge_count": merge_count,
    "elapsed": elapsed,
    "robots": robots,
    "slam_metrics": metrics_payload["slam_metrics"],
    "baseline": metrics_payload["baseline"],
    "metric_history": metrics_payload["metric_history"],
    "detection_metrics": detection_payload["detection_metrics"],
    "detection_history": detection_payload["detection_history"],
    "detection_gt_metrics": detection_payload["detection_gt_metrics"],
}
_assert_no_map_keys(payload)
```

Additive only — no existing SLAM key was removed or renamed.

### 5. Export writer rotation in reset_cloud_tracking (D-12)

```python
def reset_cloud_tracking(self) -> None:
    self._last_voxel_set = set()
    new_session_id = uuid.uuid4().hex
    self._detection_export.rotate(new_session_id)
    self._session_id = new_session_id
```

`self._detection_metrics_tracker.reset()` is deliberately NOT called — tracker state is preserved across cloud-tracking resets per RESEARCH Anti-Patterns + CONTEXT D-12 (mirrors SLAM tracker baseline preservation).

### 6. Runtime-guard test file (Task 2)

`tests/contract/test_no_map_in_payload.py` replaces the Wave 0 `pytest.skip(allow_module_level=True)` scaffold with 8 tests:

1. `test_assert_no_map_keys_passes_on_healthy_payload` — full Phase 6 payload shape with all valid keys does not raise.
2. `test_assert_no_map_keys_raises_on_mAP_key` — `{"detection_metrics": {"r0": {"mAP": 0.7}}}` raises with `mAP` in the message.
3. `test_assert_no_map_keys_raises_on_map_50` — same shape with `map_50`.
4. `test_assert_no_map_keys_raises_on_map_75` — completes forbidden-key coverage.
5. `test_assert_no_map_keys_raises_on_mean_average_precision` — full-name variant.
6. `test_assert_no_map_keys_catches_nested_list` — forbidden key inside `[{...}, {"mAP": 0.9}]` still raises (list-walker coverage).
7. `test_assert_no_map_keys_catches_forbidden_under_detection_gt_metrics` — SC#2 revision 2026-04-15: walker descends into `detection_gt_metrics[rid][class]`.
8. `test_assert_no_map_keys_message_includes_det_metrics_03_reference` — locks the `DET-METRICS-03` breadcrumb in the AssertionError message for on-call debuggability.

All 8 tests pass in 0.77s.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] fastapi not installed in .venv**
- **Found during:** Task 1 verification
- **Issue:** `.venv/bin/python -c "from backend.web.streaming_viz import ..."` failed with `ModuleNotFoundError: No module named 'fastapi'` because `backend.web.connection_manager` imports `fastapi.WebSocket`. Prior Phase 6 plans shipped without this check because they worked entirely inside `src/metrics/` (no backend import chain).
- **Fix:** `VIRTUAL_ENV=/home/prannayag/pragnition/robotics/argus/.venv uv pip install fastapi` — installed fastapi 0.135.3 + starlette + pydantic into the project venv. No source code change; this was pure environment setup.
- **Files modified:** None (venv state)
- **Commit:** N/A (environment-only)

### Plan Additions

**Added test 8 (`test_assert_no_map_keys_message_includes_det_metrics_03_reference`).** Plan specified 6 tests but the `<behavior>` description emphasised "message contains DET-METRICS-03". Added an explicit test locking this breadcrumb in because the message is the on-call debugging surface — regressing it silently would defeat half the guard's value.

**Added test 4 (`test_assert_no_map_keys_raises_on_map_75`).** Plan listed 4 forbidden-key tests covering mAP / map_50 / mean_average_precision but omitted `map_75`. Added explicit coverage for the fourth forbidden key so all four members of `_FORBIDDEN_METRIC_KEYS` have direct test coverage.

Both additions are additive — they strengthen the plan without contradicting any requirement.

## Threat Flags

None. This plan introduces only in-process wiring + a defense-in-depth assertion. No new network surface, no new file access, no new auth paths, no new schema changes. The `_assert_no_map_keys` helper IS a mitigation for T-6-01 (identified in the plan's own threat model).

## Success Criteria Verification

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| `grep -c 'detection_gt_metrics' backend/web/streaming_viz.py` | >=1 | 4 | pass |
| `grep -c 'detection_metrics' backend/web/streaming_viz.py` | >=1 | 7 | pass |
| `grep -cE '(mAP\|map_50\|map_75\|mean_average_precision)' backend/web/streaming_viz.py` | >=3 | 8 | pass |
| `grep -c 'attach_gt_extractor' backend/web/streaming_viz.py` | >=1 | 1 | pass |
| `tests/contract/test_no_map_in_payload.py` replaces Wave 0 stub | `allow_module_level=True` absent | 0 occurrences | pass |
| `pytest tests/contract/test_no_map_in_payload.py -v` | passes | 8/8 in 0.77s | pass |

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `4a1566f` | feat(06-08): compose detection metrics subsystems into WebStreamingViz |
| 2 | `b4bf37f` | test(06-08): replace Wave 0 stub with runtime-guard tests for mAP keys |

## Handoff to Downstream Plans

- **Plan 09 (REST route):** Call `request.app.state.streaming_viz.current_session_id()` + `.detection_export.path` to build `GET /api/detections/export` response headers + body.
- **Plan 10 (coordinator pump):** Call `streaming_viz.detection_metrics_tracker.record_frame(rid, latest, inspect, backend_metrics)` and `.detection_export.append(obb, rid, backend_id, capture_ts)` each coordinator tick per robot. If `streaming_viz.gt_extractor is not None`, call `.match_detection(class_name, center)` and forward the result to `detection_metrics_tracker.record_gt_match(...)`. Also call `streaming_viz.attach_gt_extractor(mapping_path, mj_model, mj_data)` once at boot.
- **Plan 11 (frontend store):** WebSocket STATS frames now carry `detection_metrics`, `detection_history`, `detection_gt_metrics` keys. Extend `metricsStore.updateAllMetrics()` to forward all three.
- **Plan 12 (grep test):** Source-level grep companion to this plan's runtime guard. The two form a belt-and-suspenders pair — source regressions caught at test time, runtime regressions (dict-merge-injected keys) caught at payload-emit time.

## Self-Check: PASSED

- FOUND: `backend/web/streaming_viz.py` (138 net +lines)
- FOUND: `tests/contract/test_no_map_in_payload.py` (107 net +lines, no `allow_module_level`)
- FOUND: commit `4a1566f` (Task 1)
- FOUND: commit `b4bf37f` (Task 2)
- FOUND: `_assert_no_map_keys` importable + guard triggers on forbidden key + passes clean payload
- FOUND: 8 pytest tests collected, 8 passing
