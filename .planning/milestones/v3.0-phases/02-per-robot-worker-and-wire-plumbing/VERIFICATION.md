---
phase: 02
phase_name: per-robot-worker-and-wire-plumbing
verified_at: 2026-04-14
verified_against_head: dfb3e95
status: PASS (5/5 success criteria, 5/5 requirements, W-01 + W-02 closed)
---

# Phase 2 — Goal-Backward Verification

**Phase:** 02-per-robot-worker-and-wire-plumbing
**HEAD at verification:** `dfb3e95`
**Verifier:** orchestrator inline (gsd-verifier agent hit usage limit)

---

## Success Criteria (ROADMAP.md Phase 2)

### SC#1 — POST /api/detectors/select → restart → GET /api/detectors/active reflects new backend
**Status:** PASS

Evidence:
- `backend/web/detector_routes.py` clones slam_routes.py pattern; `POST /select` sets `app.state.pending_detector_backend` + `pending_detector_params`, invokes `command_callback({"action": "restart"})`, returns `{"status": "restarting", "backend": req.backend}`.
- `GET /active` reads `app.state.active_detector_backend` (updated by `main.py` restart block after warmup).
- `tests/perception/test_detector_routes.py` (10 tests) — REST round-trip + WS param update + pydantic validation; all green.
- `src/main.py` restart block (lines ~430-500 extended by Plan 02-09) reads `pending_detector_backend`, constructs `DetectorWorkerPool` via `DetectorRegistry.create`, calls `warmup_all()` synchronously, assigns to `coordinator._detector_pool`, updates `active_detector_backend`, emits `detector_restart_complete` AFTER warmup.

### SC#2 — Every detection payload carries capture_pose + capture_timestamp from submission time
**Status:** PASS

Evidence:
- `src/perception/types.py::Detections3D` envelope has `capture_pose: np.ndarray(4,4)` + `capture_timestamp: float` (envelope-level, not per-box per D-11).
- `src/perception/worker.py::DetectorWorker.submit()` captures `frame.sim_time` + defensively copies `pose` into pending job (D-12, D-13).
- `backend/web/streaming_viz.py` emits `detections_3d` envelope via `Detections3D.to_wire()` which includes both fields as flat 16-float row-major + float.
- `tests/perception/test_worker_capture_pose.py` (3 tests) — asserts pose snapshotted at submit time (caller mutation post-submit does NOT alter stored capture_pose); timestamp from frame.sim_time.
- Mutation probe in executor report: disabling `.copy()` causes test failure — contract enforced.

### SC#3 — 30 Hz / 2 FPS queue depth stays at 1 (newest-wins backpressure)
**Status:** PASS

Evidence:
- `src/perception/worker.py::DetectorWorker` single-slot `_pending: tuple | None` with lock; `submit()` drops older pending on every call.
- `tests/perception/test_worker_backpressure.py::test_backpressure_drops_stale_frames` — 30 Hz submit with simulated 2 FPS backend (`SlowDetector` with `time.sleep`); asserts `queue_depth <= 1` at every submission; asserts `drops >= 50` after drain.
- `DetectorWorkerPool.inspect_worker_queues()` returns `{rid: {queue_depth, drops_since_session_start, last_submit_sim_time}}` for tests + Phase 6 metrics.
- 4 backpressure tests all pass in 3.87s.

### SC#4 — 1000-random-OBB round-trip ±1e-6 + D-10 no inline quaternion
**Status:** PASS

Evidence:
- `tests/perception/test_obb_round_trip.py::test_round_trip_1000_boxes` — 1000 boxes with `scipy.spatial.transform.Rotation.random` (fixed seed), half negated (qw<0), half with track_id set; all round-trip to ±1e-6.
- `src/perception/types.py:135` is the **only** `"quaternion":` literal in `src/` — verified by grep:
  ```
  $ grep -rn '"quaternion":' src/
  src/perception/types.py:135:            "quaternion": [float(q[0]), float(q[1]), float(q[2]), float(q[3])],
  ```
- `tests/perception/test_no_inline_quaternion.py` locks this invariant for every future plan.
- `OrientedBox3D.to_wire()` auto-flips qw when qw<0; `from_wire()` asserts invariant + raises `ValueError` on violation.

### SC#5 — SubprocessDetectorBridge handshake test passes without BoxeR
**Status:** PASS

Evidence:
- `src/perception/subprocess_bridge.py::SubprocessDetectorBridge` — separate class from `SubprocessSLAMBridge` (D-16), own endpoint pattern `ipc:///tmp/detector_bridge_<pid>_<id>`, ZMQ PAIR + msgpack multipart, `HANG_TIMEOUT_MS=5000`, hardened ingress `msgpack.unpackb(raw=False, strict_map_key=True)`.
- `scripts/echo_detector_worker.py` — standalone echo worker (D-15 permanent helper), accepts `--zmq` + `--sleep-ms`, echoes fixed 0-detection msgpack reply.
- `tests/perception/test_subprocess_bridge.py` (7 tests) + `test_subprocess_bridge_skeleton.py` (17 tests) = **24 green** — covers spawn, multipart send/recv, msgpack round-trip, slow-backend simulation, external SIGKILL → watchdog fires within HANG_TIMEOUT_MS → `_alive` flips false, cleanup unlinks IPC socket + closes zmq context (no leaked fds).

---

## Requirements Delivered

| Req ID | Description | Evidence |
|--------|-------------|----------|
| DET-API-04 | Per-robot DetectorWorker + single-slot queue + pool keyed by robot_id | `src/perception/worker.py`, `worker_pool.py`; tests backpressure + pool |
| DET-API-05 | capture_pose + capture_timestamp at submission time | `Detections3D` envelope; `test_worker_capture_pose.py` |
| DET-MODELS-05 | POST /api/detectors/select → restart | `detector_routes.py` + main.py restart block + `test_detector_routes.py` |
| DET-3D-03 | OBB wire format | `OrientedBox3D.to_wire/from_wire`; flat dict + qw>=0; test_obb_round_trip |
| DET-3D-04 | Round-trip ±1e-6 for 1000 boxes | `test_round_trip_1000_boxes` green |

All marked complete via `requirements mark-complete DET-API-04 DET-API-05 DET-MODELS-05 DET-3D-03 DET-3D-04`.

---

## Phase 1 Warnings Closed in Phase 2

### W-01 — Zero-detection fixture tautology
**Status:** CLOSED

- `tests/fixtures/generate_yolo_regression_fixture.py` now uses Mode A' (bus.jpg real image with 4 detections); asserts `len(detections) >= 1` before `np.savez`.
- `tests/integration/test_pool_end_to_end.py` asserts pool submit→latest parity with direct `YOLOv11Backend.process_frame()` AND detection count ≥ 1 — no longer a `0==0` tautology.
- 2/2 integration tests pass with 4 detections.

### W-02 — Full-suite sys.modules pollution
**Status:** CLOSED

- `tests/perception/test_registry.py::_clean_registries` autouse fixture now pops 6 sys.modules entries: backends, lifters, their submodules, types, protocol.
- `test_protocol_contracts.py` restore-on-finally fix (Plan 02-12 executor expanded W-02 fix beyond plan spec to address actual root cause).
- Verification: ran `pytest tests/perception/ tests/integration/test_pool_end_to_end.py` TWICE consecutively:
  - **Cold:** 187 passed, 1 skipped, 0 failed in 15.58s
  - **Warm:** 187 passed, 1 skipped, 0 failed in 16.47s
- Cold/warm parity confirmed.

---

## Cutover Invariants (Grep-based)

| Invariant | Command | Result |
|-----------|---------|--------|
| D-10 quaternion literal only in types.py | `grep -rn '"quaternion":' src/` | 1 hit (`src/perception/types.py:135`) — PASS |
| D-19 ObjectDetector deleted | `ls src/perception/detector.py src/perception/detection_3d.py` | Both missing — PASS |
| Frontend legacy fields gone | `grep -rn "det\.class\|det\.bbox\|det\.confidence\|det\.pos_3d" frontend/src/` | Empty — PASS |
| Frontend typecheck | `cd frontend && npx tsc --noEmit` | exit 0 — PASS |
| Registries populate at startup | `python -c "import src.main; ..."` | `['yolov11']` + `['median_depth']` — PASS |

(ObjectDetector mentions remain ONLY in docstring comments inside `src/coordination/coordinator.py:186` and `src/perception/lifters/median_depth.py` — historical references explaining the pre-refactor math parity. No runtime imports. Acceptable per scope.)

---

## Non-Blocking Pre-Existing Issues (Out of Phase 2 Scope)

Baseline on main at `1a804fe` (Phase 2 start) already had:
- `tests/integration/test_multi_mode.py::test_viz_update_interval` — `AttributeError: 'dict' object has no attribute 'rescan_triggered'` at `coordinator.py:491`. This is an exploration-loop/coordinator contract drift predating Phase 2. Phase 2 did not touch this code path.
- `tests/integration/test_multi_robot_integration.py` — similar drift.
- `tests/exploration/test_coverage_tracker.py::test_default_values` — `stuck_threshold_steps` drift (logged in `deferred-items.md` by Plan 02-09).
- `tests/slam/test_openvins_backend.py` — subprocess binary not available in CI.
- `tests/smoke/test_detector_rss.py` — pre-existing RSS smoke flake (Phase 1 deliverable, not a Phase 2 regression).

Phase 2 start baseline failures: 17F+18E. After Phase 2: 8F+9E (Plan 02-12 closed 9F+9E net via W-01/W-02 work + registry registration fixes).

**Recommendation:** Defer these to a dedicated test-hygiene plan in Phase 3 or slot into coordinator refactor work. None block Phase 3 (frontend picker, param panel, restart overlay) — those depend on REST/WS contract stability, which is intact.

---

## Phase 3 Readiness

Phase 3 (frontend-picker-and-ui, DET-UI-01..06) depends on:
- `GET /api/detectors/backends` returning capability badges — **working** (verified in `test_detector_routes.py`)
- `POST /api/detectors/select` → restart → `detector_restart_complete` WS fires after warmup — **working** (D-02/D-03 at the protocol layer)
- `Detection3DRegistry.list_backends()` returning lifters for lifter dropdown — **working** (`median_depth` registered; Phase 4 will add `point_cluster`)
- `outputs_3d_natively` capability on every detector (hide lifter dropdown when true) — **working** (MANDATORY key enforced at registry registration since Phase 1)
- WS `DETECTIONS_3D` envelope with `capture_pose` + `capture_timestamp` + `items[].bbox_xyxy` — **working** (CameraFeed 2D overlay still renders despite Phase 4-deferred PCA-OBB)

Phase 3 can proceed.

---

*Verified: 2026-04-14*
