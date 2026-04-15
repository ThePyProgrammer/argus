---
phase: 6
plan: 9
subsystem: backend-web-detections-export
tags: [perception, metrics, fastapi, streaming, export, DET-METRICS-04]
requirements: [DET-METRICS-04]
wave: 3
depends_on: [2, 6, 8]
dependency-graph:
  requires:
    - "WebStreamingViz.detection_export (DetectionExportWriter)  # Plan 08"
    - "WebStreamingViz.current_session_id()                       # Plan 08"
    - "DetectionExportWriter.append / file_path / rotate          # Plan 06"
    - "OrientedBox3D.from_wire + to_wire                          # Phase 2 D-06/D-09"
    - "backend.web.connection_manager.ConnectionManager           # Phase 2"
  provides:
    - "GET /api/detections/export             # DET-METRICS-04 REST endpoint"
    - "backend.web.detector_routes.export_router  # FastAPI router (new)"
  affects:
    - "backend/web/detector_routes.py  # + export_router, + StreamingResponse import"
    - "backend/web/server.py           # + include_router(export_router)"
    - "tests/integration/test_detections_export.py  # stub → 3 real tests"
tech-stack:
  added: []
  patterns:
    - "Dual-router pattern in detector_routes.py: detector registry (router) vs detections export (export_router) — distinct prefixes"
    - "StreamingResponse(generate()) with 65536-byte chunk generator (CONTEXT D-13 snapshot semantics)"
    - "Hermetic DetectionExportWriter via tmp_path rebind in test fixture (keeps /tmp clean across runs)"
key-files:
  created:
    - "tests/integration/test_detections_export.py  # replaces Wave 0 skip-stub; 3 tests"
  modified:
    - "backend/web/detector_routes.py  # + export_router + export_detections handler"
    - "backend/web/server.py           # include_router(detections_export_router)"
decisions:
  - "Introduced a second APIRouter (export_router) with prefix /api/detections instead of piggy-backing on the existing /api/detectors router — the CONTEXT D-13 path is /api/detections/export, not /api/detectors/detections/export. Wired in server.py alongside the existing detector_router include."
metrics:
  duration_seconds: 185
  completed_date: "2026-04-15"
  task_count: 2
  commits: 2
---

# Phase 6 Plan 9: Detections Export REST Endpoint (DET-METRICS-04 reader) Summary

Shipped `GET /api/detections/export` streaming-JSONL endpoint plus its 30-frame round-trip integration test; reader half of DET-METRICS-04 closes the loop on writer from Plan 06.

## One-liner

FastAPI `StreamingResponse` over `WebStreamingViz.detection_export.file_path` with 65536-byte chunks, `application/x-ndjson`, session-id in `Content-Disposition`, 404 when the current session has emitted no detections yet; three TestClient tests verify behavior end-to-end including lossless `OrientedBox3D.from_wire` round-trip to ±1e-6.

## Scope Delivered

### Task 1 — Route: `GET /api/detections/export` (commit `205c8af`)

- Imported `StreamingResponse` from `fastapi.responses`.
- Introduced `export_router = APIRouter(prefix="/api/detections", tags=["detections"])` so the endpoint resolves at `/api/detections/export` (the existing `router` carries prefix `/api/detectors`, which would have produced the wrong path).
- Handler `export_detections(request)`:
  - Reads `request.app.state.streaming_viz.detection_export.file_path` + `.current_session_id()` (Wave 2 Plan 08 accessors).
  - Returns 404 if the file doesn't exist (new session, no emits).
  - Otherwise opens the file `rb`, streams in 65536-byte chunks via a synchronous generator (snapshot-at-request-time per CONTEXT D-13 — not `tail -f`).
  - `media_type="application/x-ndjson"`, `Content-Disposition: attachment; filename="detections-<session>.jsonl"`.
- No path parameter on the handler → no traversal surface (T-6-02 mitigation).
- `backend/web/server.py` imports `export_router as detections_export_router` and includes it alongside the existing `detector_router`.

### Task 2 — Integration tests (commit `70fffdf`)

Replaced the Wave 0 skip-stub with three tests at `tests/integration/test_detections_export.py`:

1. `test_endpoint_returns_404_when_no_session` — `DetectionExportWriter.__init__` auto-creates an empty file; we `unlink()` it to simulate the pre-first-emit state, then assert `GET /api/detections/export` returns 404.
2. `test_endpoint_streams_ndjson_and_round_trips` — builds 30 deterministic `OrientedBox3D` instances, appends them via `viz.detection_export.append(...)`, hits the endpoint, asserts `Content-Type` starts with `application/x-ndjson`, splits response on `\n` into 30 non-empty lines, and round-trips every `rec["obb"]` through `OrientedBox3D.from_wire` with `np.allclose(..., atol=1e-6)` on center, half_extents, quaternion plus exact class_id / class_name / score checks.
3. `test_endpoint_content_disposition_has_session_id` — verifies header starts with `attachment; filename="detections-` and ends with `.jsonl"`, with the full `viz.current_session_id()` embedded.

Fixture `app_with_streaming_viz(tmp_path)` constructs a real `WebStreamingViz(ConnectionManager(), robot_ids=["robot_0", "robot_1"])`, then closes the auto-opened writer and rebinds `viz._detection_export` to a `DetectionExportWriter(session_id, base_dir=tmp_path)` so nothing leaks into `/tmp/argus_sessions/` across test runs. The session id is preserved across the rebind so the Content-Disposition assertion is meaningful.

## Acceptance Criteria

### Task 1

- `grep -c '/detections/export' backend/web/detector_routes.py` = **2** (>= 1) ✓
- `grep -c 'StreamingResponse' backend/web/detector_routes.py` = **2** (>= 2, import + return) ✓
- `grep -c 'application/x-ndjson' backend/web/detector_routes.py` = **2** (>= 1) ✓
- `grep -c 'Content-Disposition' backend/web/detector_routes.py` = **1** (>= 1) ✓
- `grep -c 'HTTPException' backend/web/detector_routes.py` = **7** (>= 2, import + raise + existing handlers) ✓
- `current_session_id()` used (no `_session_id` private access) ✓
- `python -c "from backend.web.detector_routes import router"` exits 0 ✓
- Introspection: `export_router.routes` contains `/api/detections/export` ✓

### Task 2

- `grep -c 'allow_module_level=True' tests/integration/test_detections_export.py` = **0** (stub replaced) ✓
- `pytest tests/integration/test_detections_export.py -v` → **3 passed** in 0.63s ✓
- `grep -c 'OrientedBox3D.from_wire' tests/integration/test_detections_export.py` = **3** (>= 1) ✓
- `grep -c 'application/x-ndjson' tests/integration/test_detections_export.py` = **1** (>= 1) ✓
- `grep -c 'DET-METRICS-04' tests/integration/test_detections_export.py` = **3** (>= 1) ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Route prefix mismatch between plan sketch and existing router**

- **Found during:** Task 1, reading `backend/web/detector_routes.py`
- **Issue:** The plan's interface sketch used `@router.get("/detections/export")` on the existing `router`. That router carries `prefix="/api/detectors"`, so the resulting path would have been `/api/detectors/detections/export` — not the `/api/detections/export` locked by CONTEXT D-13 and the plan's `key_links` pattern.
- **Fix:** Declared a dedicated second router `export_router = APIRouter(prefix="/api/detections", tags=["detections"])` at the top of `detector_routes.py`, attached the handler with `@export_router.get("/export")`, and added a second `app.include_router(...)` call in `backend/web/server.py` to mount it.
- **Files modified:** `backend/web/detector_routes.py`, `backend/web/server.py`
- **Commit:** `205c8af`
- **Scope note:** `server.py` was not in the plan's `files_modified` list, but this single-line addition (the include_router call) is the minimum necessary to make the new router reachable — classic Rule 3 blocking-issue scope.

## Authentication Gates

None — endpoint is read-only, no auth; fits the existing unauthenticated-localhost pattern of the other `/api/**` routes.

## Known Stubs

None — the Wave 0 skip-stub is replaced with real assertions; the endpoint has no placeholder logic.

## Threat Flags

No new threat surface beyond the `<threat_model>` in the plan.

- T-6-02 (path traversal): **mitigated** — handler reads no request parameters for path resolution; path comes from `streaming_viz.detection_export.file_path`.
- T-6-05 (streaming buffering): **mitigated** — explicit `media_type="application/x-ndjson"` and 65536-byte chunk reads; integration test asserts content-type starts with `application/x-ndjson`, which would fail if middleware buffered the generator.
- T-6-03 (unbounded file growth): **accepted** (per D-12) — handler streams rather than loading into memory, so size is a disk problem not a memory problem.

## Self-Check

All claimed artifacts verified present. Commits 205c8af + 70fffdf exist on the current branch.

## Self-Check: PASSED

- FOUND: backend/web/detector_routes.py
- FOUND: backend/web/server.py
- FOUND: tests/integration/test_detections_export.py
- FOUND: .planning/phases/06-detection-metrics-and-mujoco-gt/06-09-SUMMARY.md
- FOUND: commit 205c8af (Task 1 — handler)
- FOUND: commit 70fffdf (Task 2 — integration tests)
