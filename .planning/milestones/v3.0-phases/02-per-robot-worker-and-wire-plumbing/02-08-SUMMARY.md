---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 08
subsystem: api
tags: [backend, fastapi, rest, websocket, detector-routes, det-models-05]

# Dependency graph
requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "DetectorRegistry (Plan 02-01 foundation), Detections3D envelope, SubprocessDetectorBridge (02-06/02-07), DetectorWorkerPool (02-04)"
provides:
  - "POST /api/detectors/select (D-02 SLAM-clone pattern) — writes app.state.pending_detector_backend + triggers restart command"
  - "GET /api/detectors/backends + /active + PATCH /params — parity with slam_routes.py surface"
  - "app.state.active_detector_backend / pending_detector_backend / pending_detector_params — contract for Plan 02-09 restart reader"
  - "WS detector_param_update dispatch branch mirroring slam_param_update"
  - "4 new WS message-type literals: DETECTIONS_3D, DETECTOR_RESTART_COMPLETE, DETECTOR_PARAM_ACK, DETECTOR_PARAM_UPDATE — Plan 02-10 streaming_viz emission targets"
affects: [02-09-main-restart-extension, 02-10-streaming-viz-coordinator, phase-03-frontend-detector-panel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SLAM-pattern clone for backend registry REST surface (4-endpoint shape: /backends, /select, /active, /params)"
    - "Lazy DetectorRegistry import inside WS handler — preserves torch-free startup path"
    - "pydantic BaseModel request bodies (SelectRequest, ParamPatch) — automatic 422 on malformed payloads"

key-files:
  created:
    - backend/web/detector_routes.py
    - tests/perception/test_detector_routes.py
  modified:
    - backend/web/server.py
    - backend/web/message_types.py

key-decisions:
  - "Clone slam_routes.py structurally but DROP merge-strategy handlers — perception stack has no merge equivalent"
  - "Module-level fake backends in tests (not nested in fixtures) because DetectorRegistry resolves class_path via importlib + getattr — nested qualnames like register_fakes.<locals>.FakeYolo fail that lookup"
  - "Lazy-import DetectorRegistry inside the detector_param_update WS branch to keep server.py startup torch-free when the detector subsystem is not yet wired"
  - "Stash pending_detector_params on both live_tunable and requires_restart PATCH paths — UI needs to see the queued value regardless of live/deferred split"

patterns-established:
  - "Per-subsystem REST surface on FastAPI: one router module per domain (slam_routes, pipeline_routes, detector_routes), registered in create_app"
  - "WS param_update handlers validate param ∈ schema_props BEFORE any app.state mutation (T-02-20 mitigation)"
  - "Module-level test fakes registered via DetectorRegistry.register(...) directly, not the @detector_backend decorator, because the decorator captures class_path from the caller's qualname"

requirements-completed: [DET-MODELS-05]

# Metrics
duration: ~15 min
completed: 2026-04-14
---

# Phase 2 Plan 08: Detector REST + WS Surface Summary

**DET-MODELS-05 REST surface (GET /backends, POST /select, GET /active, PATCH /params) cloned structurally from slam_routes.py + WS detector_param_update handler + 4 new detector WS message-type literals for Plan 09/10 consumption.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files created:** 2
- **Files modified:** 2
- **Test count:** 10 (all green)

## Accomplishments

- `backend/web/detector_routes.py` — 4-endpoint FastAPI router at `/api/detectors/*` with pydantic request validation, structural clone of `slam_routes.py` (minus merge-strategy handlers).
- `backend/web/server.py` — `create_app` now initializes `app.state.active_detector_backend="yolov11"`, `pending_detector_backend=None`, `pending_detector_params={}` and includes `detector_router`. `_dispatch_ws_message` gained a `detector_param_update` branch mirroring `slam_param_update` with lazy `DetectorRegistry` import.
- `backend/web/message_types.py` — 4 new literal constants: `DETECTIONS_3D`, `DETECTOR_RESTART_COMPLETE`, `DETECTOR_PARAM_ACK`, `DETECTOR_PARAM_UPDATE`.
- `tests/perception/test_detector_routes.py` — 10 REST + WS round-trip tests covering happy path, 404/400 validation, live_tunable vs requires_restart vs unknown_parameter, and the 3-way WS ack split. Module-level fake backends keep the suite torch-free.

## Task Commits

1. **Task 1: detector_routes.py + message_types.py literals** — `dcf6156` (feat)
2. **Task 2: server.py app.state wiring + WS handler** — `ce780a7` (feat)
3. **Task 3: REST + WS round-trip tests** — `5231fda` (test)

_Final SUMMARY metadata commit is left to the phase orchestrator per parallel-mode rules._

## Files Created/Modified

- `backend/web/detector_routes.py` — 4 endpoints: `/backends` (registry list), `/select` (pending + restart command), `/active` (active metadata), `/params` (per-key live/restart/unknown status).
- `backend/web/server.py` — detector state fields + router include + `detector_param_update` WS branch. No existing SLAM path touched.
- `backend/web/message_types.py` — 4 new Phase 2 WS literals appended to the existing literal block.
- `tests/perception/test_detector_routes.py` — 10 tests, FastAPI TestClient + `websocket_connect`, module-level FakeYolo / UnavailableBackend.

## API Contract Surface (for Plan 09 / Plan 10 / Phase 3 UI)

### REST

| Method | Path | Body | Response |
|--------|------|------|----------|
| GET | `/api/detectors/backends` | — | `{backends: [{name, display, available, reason?, capabilities, parameter_schema}]}` |
| POST | `/api/detectors/select` | `{backend: str, params?: dict}` | 200 `{status: "restarting", backend}` / 404 unknown / 400 unavailable |
| GET | `/api/detectors/active` | — | `{backend, display, parameters}` |
| PATCH | `/api/detectors/params` | `{params: {key: value, ...}}` | `{results: {key: {status: applied\|requires_restart\|unknown_parameter, value?}}}` |

### app.state (consumed by Plan 02-09 main.py restart extension)

- `app.state.active_detector_backend: str` (default `"yolov11"`)
- `app.state.pending_detector_backend: str | None` (written by POST /select, read by coordinator restart)
- `app.state.pending_detector_params: dict[str, Any]` (merged on restart, also buffered by PATCH /params and WS detector_param_update)

### WS message-type literals (Plan 02-10 streaming_viz emission targets)

- `DETECTIONS_3D = "detections_3d"`
- `DETECTOR_RESTART_COMPLETE = "detector_restart_complete"`
- `DETECTOR_PARAM_ACK = "detector_param_ack"` (sent by server.py branch)
- `DETECTOR_PARAM_UPDATE = "detector_param_update"` (received by server.py branch)

### Live-tunable vs requires-restart split (Phase 3 UI will consume)

Backends declare per-parameter `live_tunable: bool` in their `PARAMETER_SCHEMA.properties[key]`. UI:
- `live_tunable=True` → value sent via PATCH /params or WS detector_param_update applies immediately.
- `live_tunable=False` → value queued in `pending_detector_params`; restart required (explicit via POST /select, or user-triggered).
- Unknown param → `unknown_parameter` status; no state change (T-02-20 mitigation).

## Decisions Made

- **Drop merge-strategy handlers from the clone:** perception stack has no merge equivalent, so `/merge-strategies`, `/merge-strategy`, `/merge-params` are SLAM-only.
- **Module-level test fakes:** `DetectorRegistry.list_backends()` calls `importlib.import_module(module_path)` then `getattr(module, class_name)`. Nested classes get qualnames like `register_fakes.<locals>.FakeYolo`; after `rsplit('.', 1)` the registry tries `getattr(module, '<locals>')` and fails, marking the backend `available=False`. Fix: define fake classes at module scope and register them by hand via `DetectorRegistry.register(...)`.
- **Lazy DetectorRegistry import in server.py's WS branch:** mirrors the SLAM handler's deferred-import pattern so `create_app` does not drag perception/torch into the startup path.
- **Stash pending_detector_params on both applied AND requires_restart PATCH paths:** Plan 02-09's restart reader needs to see the new value on both paths (a user setting a live_tunable value should still survive a subsequent restart).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test fakes must live at module scope, not inside fixtures**
- **Found during:** Task 3 (first test run — `test_select_sets_pending_backend` failed with 400 instead of 200)
- **Issue:** Plan's test pattern defined FakeYolo/Unavailable inside `register_fakes` fixture with the `@detector_backend` decorator. `DetectorRegistry.list_backends()` then tried to reload the class via `importlib.import_module(module_path) + getattr(module, class_name)` but the class_path embedded `<locals>` from the nested qualname. The lookup failed, marking `fake_yolo` as `available=False`, which made POST /select return 400 "Backend unavailable".
- **Fix:** Moved `FakeYolo` and `UnavailableBackend` to module scope. Register them inside the fixture via `DetectorRegistry.register(name, display, class_path, klass)` directly (not via decorator) so class_path is an accurate module + qualname pair.
- **Files modified:** `tests/perception/test_detector_routes.py`
- **Verification:** All 10 tests pass.
- **Committed in:** `5231fda` (Task 3 commit).

**2. [Rule 2 - Missing Critical] PATCH /params buffers requires_restart values too**
- **Found during:** Task 1 (implementing detector_routes.py)
- **Issue:** The `slam_routes.py` patch_params handler only buffers values on the `requires_restart` path — live_tunable values are ack'd "applied" but never stashed. For the detector surface, Plan 02-09's restart reader needs both paths to buffer so that a user who sets a live_tunable param and then manually triggers a restart sees the value preserved. Without this, the live_tunable setting would be lost on restart.
- **Fix:** Added `pending_detector_params[key] = value` on BOTH `applied` and `requires_restart` branches in `detector_routes.py::patch_params`. The slam_routes behavior is preserved separately; only the detector clone diverges.
- **Files modified:** `backend/web/detector_routes.py`
- **Verification:** `test_patch_params_live_tunable_and_requires_restart` asserts `pending_detector_params.get("confidence_threshold") == 0.8` AND `pending_detector_params.get("model_path") == "yolo11s.pt"` — both pass.
- **Committed in:** `dcf6156` (Task 1 commit).

_Note: This divergence from the slam_routes template is intentional and documented here. The plan's `<action>` snippet for Task 1 actually includes this buffering on both branches, so the deviation was from the SLAM template, not from the plan — but flagging here because readers comparing slam_routes.py and detector_routes.py will see the asymmetry._

---

**Total deviations:** 2 auto-fixed (1 Rule 3 Blocking, 1 Rule 2 Missing Critical)
**Impact on plan:** No scope creep. Test fix was a mechanical registration-pattern correction. PATCH buffering on both branches was called out by the plan's `<action>` snippet and is now consistent across both code and tests.

## Issues Encountered

- Pre-existing test failures observed but out of scope per plan verification boundary:
  - `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_enforces_eval_and_freeze` — `ModuleNotFoundError: torch` (unrelated; torch missing in worktree env).
  - `tests/web/test_merge_routes.py` — `ModuleNotFoundError: open3d` (unrelated; open3d missing in worktree env).
  - `tests/web/test_slam_routes.py` 4 failures — verified pre-existing on baseline HEAD (not introduced by this plan).

- `tests/perception/test_worker_pool.py` referenced by plan `<verification>` does not exist in the repo. Plan 02-04's deliverable appears to have been tested under a different file path. Not blocking this plan; flagged for phase verifier.

## Threat Flags

None — the 4 endpoints all live inside the existing trust boundaries enumerated in the plan's `<threat_model>` (REST and WS control channels). No new network endpoints, auth paths, filesystem access, or schema changes at trust boundaries were introduced.

## Self-Check

- `backend/web/detector_routes.py` FOUND on disk.
- `tests/perception/test_detector_routes.py` FOUND on disk.
- `backend/web/server.py` modified (app.state + router + WS handler).
- `backend/web/message_types.py` modified (4 literals appended).
- Task commits `dcf6156`, `ce780a7`, `5231fda` all present in `git log --oneline`.
- `pytest tests/perception/test_detector_routes.py`: 10 passed.
- `python -c "from backend.web.detector_routes import router; from backend.web.server import create_app"` succeeds.
- `create_app(robot_ids=['r0'])` produces `app.state.active_detector_backend == 'yolov11'`, `pending_detector_backend is None`, `pending_detector_params == {}`, and routes include `/api/detectors/{backends,select,active,params}` AND `/api/slam/backends` (SLAM path untouched).

## Self-Check: PASSED

## Next Plan Readiness

Plan 02-09 (main.py restart extension) can now read `app.state.pending_detector_backend` on restart and consume `pending_detector_params`. Plan 02-10 (streaming_viz + coordinator) can emit `DETECTIONS_3D` and `DETECTOR_RESTART_COMPLETE` using the literals exported from `backend/web/message_types.py`. REST + WS contract surface is locked; no follow-up touches to these files required within Phase 2.

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*
