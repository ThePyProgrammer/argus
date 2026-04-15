---
phase: 6
plan: 6
subsystem: metrics
tags: [perception, metrics, export, jsonl, threading]
requirements: [DET-METRICS-04]
dependency_graph:
  requires:
    - src/perception/types.py::OrientedBox3D (Phase 2 D-10 sole quaternion path)
  provides:
    - src/metrics/detection_export.py::DetectionExportWriter
  affects:
    - Plan 06-08 (WebStreamingViz owns writer lifecycle, calls .rotate on reset_cloud_tracking)
    - Plan 06-09 (GET /api/detections/export reads writer.file_path)
tech_stack:
  added: []
  patterns:
    - "tempfile.gettempdir() + UUID4 subdir composition (OS-portable, no user input on path)"
    - "text-mode line-buffered append (buffering=1) — SIGKILL-safe flush on '\\n'"
    - "threading.Lock-protected write/rotate (single-writer lock, atomic file-handle swap)"
key_files:
  created:
    - src/metrics/detection_export.py
    - tests/metrics/test_detection_export.py
    - tests/metrics/__init__.py
  modified: []
decisions:
  - "No separate FakeOBB/fixture module: kept dataclass inline in the test file for locality"
  - "append() silently no-ops after close() to avoid crashing a late shutdown pump"
  - "base_dir defaults to tempfile.gettempdir() at __init__ time — captured once so later tmpdir churn cannot redirect mid-session"
metrics:
  completed_date: 2026-04-15
  tasks_completed: 1
  commits: 2
---

# Phase 6 Plan 6: JSONL Detection Export Writer Summary

**One-liner:** `DetectionExportWriter` streams `OrientedBox3D.to_wire()` payloads into `<tempdir>/argus_sessions/<uuid4>/detections.jsonl` as append-on-emit JSONL, with a single `threading.Lock` that makes `rotate()` safe against in-flight `append()` from a different thread.

## What Was Built

`src/metrics/detection_export.py` (~90 SLOC excluding docstrings) owning the correctness half of DET-METRICS-04. Plan 06-09 will mount the streaming FastAPI route that reads the file; Plan 06-08 will own lifecycle (construction on coordinator boot + `rotate()` on `reset_cloud_tracking`).

### Public contract

```python
class DetectionExportWriter:
    def __init__(self, session_id: str, base_dir: Path | None = None) -> None: ...
    def append(self, obb, robot_id: str, backend_id: str, capture_timestamp: float) -> None: ...
    def rotate(self, new_session_id: str) -> None: ...
    @property
    def session_id(self) -> str: ...
    @property
    def file_path(self) -> Path: ...
    def close(self) -> None: ...
```

### JSONL line format (compact, locked by tests)

```json
{"robot_id":"robot_0","backend_id":"yolov11","capture_timestamp":12.345,"obb":{"center":[...],"half_extents":[...],"quaternion":[...],"class_id":56,"class_name":"chair","score":0.87,"track_id":null}}
```

The `obb` object is produced exclusively by `OrientedBox3D.to_wire()` — Phase 1 D-10 invariant that no other code path constructs quaternions on the wire.

## How Invariants Are Enforced

| Invariant | Mechanism | Evidence |
|-----------|-----------|----------|
| No hardcoded `/tmp/` (OS portability + T-6-02 security) | `tempfile.gettempdir()` composed with UUID4 subdir; `grep -c '"/tmp/"'` = 0 | Acceptance gate in plan |
| Sole quaternion path is `OrientedBox3D.to_wire()` (Phase 1 D-10) | `obb.to_wire()` called inside `append()`; 4 occurrences of `to_wire()` in file (docstring + callsite) | `grep to_wire` |
| SIGKILL-safe per-line flush (Pitfall 6) | `open(path, "a", buffering=1, encoding="utf-8")` — text-mode line-buffered | Verified against RESEARCH Pitfall 6 pattern |
| Rotate vs append is race-safe (Open Question 4) | Single `threading.Lock` guards both write and file-handle swap; `rotate()` closes under lock, opens new, all within same critical section | Test 6 (thread-safety smoke) passes |
| Prior session files preserved (D-12) | `rotate()` never calls `unlink()`; test 4 asserts old file still exists post-rotate | `test_rotate_opens_new_file` |

## Test Coverage (6/6 green)

`uv run pytest tests/metrics/test_detection_export.py -v` → `6 passed in 0.05s`

1. **test_writer_creates_session_directory** — init creates `<base>/argus_sessions/<id>/detections.jsonl` (possibly empty).
2. **test_append_writes_one_line_per_call** — N calls → exactly N valid JSON lines.
3. **test_envelope_keys** — top-level keys = `{robot_id, backend_id, capture_timestamp, obb}`; `obb` carries the 7 `to_wire()` keys.
4. **test_rotate_opens_new_file** — `rotate("new")` preserves old file, opens new, updates `session_id`.
5. **test_round_trip_via_from_wire** — real `OrientedBox3D` round-trips through `append → json.loads → OrientedBox3D.from_wire` to `atol=1e-6` on center/half_extents/quaternion, exact on `class_id`/`track_id`.
6. **test_rotate_is_thread_safe** — 50× `append` in one thread + 50× `rotate` in another via `ThreadPoolExecutor`; no exception, no malformed JSON lines across any produced session file (no lost-write guarantee — that's by design, rotate-during-append may split lines across the old/new file).

## Threat Model Status (from PLAN.md)

| Threat | Disposition | Implementation |
|--------|-------------|----------------|
| T-6-02 (path traversal / symlink on `_open_for_session`) | **mitigated** | Caller-provided UUID4 composed with `tempfile.gettempdir() / "argus_sessions"`; docstring explicitly forbids user-supplied `session_id` |
| T-6-03 (unbounded `/tmp` growth) | **accepted** (per CONTEXT D-12) | Documented in module docstring — debug directory, OS/user cleanup responsibility |
| T-6-06 (concurrent rotate mid-write) | **mitigated** | Single `threading.Lock` guards `append` and `rotate`; atomic fp swap |

## Deviations from Plan

None — plan executed exactly as written. Implementation matches the reference code block in `<action>` verbatim (with added `__all__`, explicit `TextIO` typing, and expanded docstrings).

## Commits

| Task | Message | Commit |
|------|---------|--------|
| 1 (RED) | `test(06-06): add failing tests for DetectionExportWriter` | `ec7993c` |
| 1 (GREEN) | `feat(06-06): implement DetectionExportWriter for JSONL session export` | `b1c24a0` |

## Known Stubs

None. The module is feature-complete for its scope; Plan 06-08 wiring (lifecycle owner) and Plan 06-09 (streaming route) are downstream integrations, not stubs.

## Downstream Hooks for Plan 06-08 / 06-09

- **Plan 06-08 (WebStreamingViz owner):** construct as `DetectionExportWriter(session_id=uuid.uuid4().hex)`; call `writer.rotate(uuid.uuid4().hex)` from `reset_cloud_tracking()`. No other accessor needed from outside.
- **Plan 06-09 (streaming endpoint):** read `writer.file_path` and open it `"rb"` for `StreamingResponse`; snapshot-at-request-time matches D-13 (chunked read, not `tail -f`).

## Self-Check: PASSED

- Files present: `src/metrics/detection_export.py`, `tests/metrics/test_detection_export.py`, `tests/metrics/__init__.py`
- Commits in `git log`: `ec7993c` (RED) and `b1c24a0` (GREEN) both present
- Acceptance gates: `tempfile.gettempdir` = 4 (≥1 ✓); hardcoded `/tmp/` = 0 ✓; `to_wire()` = 4 (≥1 ✓); `threading.Lock`/`self._lock` = 7 (≥2 ✓); module importable ✓
- Test count: `6 passed, 0 failed`
