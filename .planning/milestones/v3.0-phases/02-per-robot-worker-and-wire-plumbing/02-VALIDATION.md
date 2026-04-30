---
phase: 2
slug: per-robot-worker-and-wire-plumbing
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-13
updated: 2026-04-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python) + tsc --noEmit (TypeScript, no jest yet) |
| **Config file** | `pyproject.toml` (implicit pytest discovery); no `pytest.ini` |
| **Quick run command** | `pytest tests/perception/ -x --no-header -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Frontend typecheck** | `cd frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~25 seconds for quick run (first-inference YOLO warmup dominates); ~60 seconds full suite |

Wave 0 existing infrastructure covers all phase requirements — no new pytest plugins, no new fixtures beyond what tests carry themselves.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/perception/ -x -q`.
- **After Wave 1 merge:** Run `pytest tests/perception/test_obb_round_trip.py tests/perception/test_no_inline_quaternion.py -x -q`.
- **After Wave 2 merge:** Run `pytest tests/perception/test_worker_backpressure.py tests/perception/test_worker_pool.py tests/perception/test_worker_capture_pose.py -x -q`.
- **After Wave 3 merge:** Run `pytest tests/perception/test_subprocess_bridge.py -x -q`.
- **After Wave 4 merge (each plan 08..12):** Run full suite `pytest tests/ -x -q` + frontend typecheck.
- **Before `/gsd-verify-work`:** Full suite green TWICE in same shell (W-02 warm-cache acceptance), frontend typecheck green, grep-clean audit.
- **Max feedback latency:** ≤30 s for the quick run (YOLO model load is ~2 s first invocation, cached afterward).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 1 | DET-3D-03, DET-API-05 | T-02-01 / T-02-02 | Wire-format shape validation + capture_pose size check raise ValueError on malformed input | unit | `pytest tests/perception/test_obb_round_trip.py::test_wire_shape_matches_d09 -x -q` | ❌ W1 | ⬜ pending |
| 2-01-02 | 01 | 1 | DET-3D-04 | T-02-01 | 1000-box round-trip + edge cases + negative-qw rejection + bbox_xyxy optional + envelope round-trip | unit | `pytest tests/perception/test_obb_round_trip.py -x -q` | ❌ W1 | ⬜ pending |
| 2-02-01 | 02 | 1 | DET-3D-03 | T-02-04 | Grep invariant: only OrientedBox3D.to_wire constructs "quaternion": literal | unit | `pytest tests/perception/test_no_inline_quaternion.py -x -q` | ❌ W1 | ⬜ pending |
| 2-03-01 | 03 | 2 | DET-API-04 | T-02-05, T-02-06, T-02-07 | Per-robot single-slot newest-wins queue + defensive pose copy + exception resilience | integration | `pytest tests/perception/test_worker_backpressure.py -x -q` | ❌ W2 | ⬜ pending |
| 2-03-02 | 03 | 2 | DET-API-04 | T-02-05 | Backpressure under 30 Hz submit / 2 FPS backend; queue_depth ≤ 1, drops ≥ 50 | integration | `pytest tests/perception/test_worker_backpressure.py::test_backpressure_drops_stale_frames -x -q` | ❌ W2 | ⬜ pending |
| 2-04-01 | 04 | 2 | DET-API-04, DET-MODELS-05 | T-02-08, T-02-09 | Pool dispatch keyed by rid; unknown-rid safe no-op; synchronous warmup_all; per-robot instance separation | integration | `pytest tests/perception/test_worker_pool.py -x -q` | ❌ W2 | ⬜ pending |
| 2-05-01 | 05 | 2 | DET-API-05 | T-02-10, T-02-11 | capture_pose snapshotted at submit-time not lift-time; envelope-level not per-box | integration | `pytest tests/perception/test_worker_capture_pose.py -x -q` | ❌ W2 | ⬜ pending |
| 2-06-01 | 06 | 3 | DET-MODELS-05 | T-02-12, T-02-13, T-02-14, T-02-15 | Subprocess bridge with D-16 endpoint separation, hardened msgpack ingress, LINGER=0 cleanup | unit | `python -c "from src.perception.subprocess_bridge import SubprocessDetectorBridge; b = SubprocessDetectorBridge('/bin/true'); assert 'detector_bridge_' in b.endpoint"` | ❌ W3 | ⬜ pending |
| 2-07-01 | 07 | 3 | DET-MODELS-05 | T-02-16, T-02-17 | Echo worker helper ships as permanent repo script (D-15) | smoke | `python scripts/echo_detector_worker.py --help` | ❌ W3 | ⬜ pending |
| 2-07-02 | 07 | 3 | DET-MODELS-05 | T-02-14, T-02-15, T-02-18 | Handshake: spawn/send/recv/msgpack-fidelity/kill/timeout/IPC-file-cleanup | integration | `pytest tests/perception/test_subprocess_bridge.py -x -q` | ❌ W3 | ⬜ pending |
| 2-08-01 | 08 | 4 | DET-MODELS-05 | T-02-19, T-02-20, T-02-21, T-02-22 | REST route validates backend/param before app.state write; 404/400 on bad input; WS detector_param_update schema-validated | integration | `pytest tests/perception/test_detector_routes.py -x -q` | ❌ W4 | ⬜ pending |
| 2-09-01 | 09 | 4 | DET-MODELS-05 | T-02-23, T-02-24, T-02-25 | main.py restart block rebuilds pool + synchronous warmup_all + emits detector_restart_complete per D-03 | smoke | `python -c "import src.main"` + manual POST /api/detectors/select integration (covered by Plan 12's pool-end-to-end once the restart callback wiring is stable) | ❌ W4 | ⬜ pending |
| 2-10-01 | 10 | 4 | DET-API-04, DET-API-05, DET-3D-03 | T-02-26, T-02-27, T-02-28 | Coordinator rewired to _detector_pool; streaming_viz emits DETECTIONS_3D via to_wire() (no inline quaternion) | smoke+unit | `pytest tests/perception/test_no_inline_quaternion.py -x -q && python -c "import src.coordination.coordinator; import backend.web.streaming_viz"` | ❌ W4 | ⬜ pending |
| 2-11-01 | 11 | 4 | DET-API-05, DET-3D-03 | T-02-29, T-02-30 | Frontend consumes Detection3DEnvelope; bbox_xyxy survives CameraFeed overlay; crash_fallback subsystem-aware | typecheck | `cd frontend && npx tsc --noEmit` | ❌ W4 | ⬜ pending |
| 2-12-01 | 12 | 4 | DET-API-04, DET-MODELS-01 | T-02-31 | Deletions complete; repo grep-clean for src.perception.detector / detection_3d | smoke | `bash -c 'set -e; ! test -f src/perception/detector.py; ! test -f src/perception/detection_3d.py; ! test -f tests/perception/test_yolov11_regression.py; python -c "import src.perception; import src.coordination.coordinator"'` | ❌ W4 | ⬜ pending |
| 2-12-02 | 12 | 4 | DET-MODELS-01 | T-02-33 | W-02 registry fixture fix: full-suite green in warm-cache second pass | regression | `pytest tests/ -x -q && pytest tests/ -x -q` (twice) | ❌ W4 | ⬜ pending |
| 2-12-03 | 12 | 4 | DET-MODELS-01 | T-02-32 | W-01 fixture generator asserts ≥1 YOLO detection before np.savez | regression | `python tests/fixtures/generate_yolo_regression_fixture.py` (skips cleanly if MuJoCo unavailable) | ❌ W4 | ⬜ pending |
| 2-12-04 | 12 | 4 | DET-API-04, DET-MODELS-01 | T-02-32 | Pool end-to-end parity: pool.submit→latest produces same detections as direct YOLOv11Backend+MedianDepthLifter | integration | `pytest tests/integration/test_pool_end_to_end.py -x -q` | ❌ W4 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity check:** every plan has at least one Automated row; no 3 consecutive tasks without automated verify. Max same-wave gap: Plan 06→07 both have automated commands (no gap). Plan 09 is the thinnest coverage (python -c smoke + transitive coverage from Plan 12's end-to-end test because an actual restart round-trip requires a running uvicorn) — accepted as a smoke check with explicit downstream coverage.

---

## Wave 0 Requirements

None — existing test infrastructure in `tests/perception/` covers all Phase 2 test files. `tests/integration/` is a new directory created by Plan 12 Task 3 with an empty `__init__.py`; no framework install needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| End-to-end REST restart round-trip (POST /api/detectors/select → coordinator restarts → detector_restart_complete observed on WS → GET /api/detectors/active reflects new backend) | DET-MODELS-05 success criterion #1 | Requires running uvicorn + MuJoCoBridge + coordinator sim loop — integration harness is heavy; automated WS receiver exists in Plan 08 test_ws_detector_param_update_* but full restart round-trip spans main.py's sim thread which pytest cannot easily orchestrate | 1. `python src/main.py --scene office1 --robots r0,r1` 2. Open http://localhost:8000/docs → POST /api/detectors/select {"backend": "yolov11"} 3. Tail uvicorn logs for "Detector pool rebuild" + "detector_restart_complete" 4. GET /api/detectors/active → {"backend": "yolov11"} |
| Frontend 2D overlay survives D-18 cutover | DET-API-05 success criterion #4 (implicit) + Pitfall 8 research bridge | Visual rendering requires browser + live simulation | 1. `npm run dev` in frontend/ 2. Start argus via step 1 above 3. Open browser → RobotCard shows detections with class_name + score 4. CameraFeed shows bbox overlay on detected objects (pulled from items[].bbox_xyxy) |
| Frontend RestartOverlay dismisses on detector_restart_complete | DET-UI-04 (Phase 3 scope but Phase 2 emits the signal) | Visual confirmation of WS → React state propagation | Phase 3's DET-UI-04 owns this; Phase 2 only ships the signal. Manual check: browser DevTools console sees `[detector] restart complete: yolov11` log when POST /select completes. |

Automated coverage: 17 of 18 task rows above. Manual rows are integration + visual verifications that the pytest harness cannot economically reach this phase.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 30 s (first-invocation YOLO warmup tax accepted)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-14 (planner)
