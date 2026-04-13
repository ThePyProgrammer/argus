# Phase 2: per-robot-worker-and-wire-plumbing - Context

**Gathered:** 2026-04-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the per-robot `DetectorWorker` pool with newest-wins backpressure, REST/WS detector selection with restart (mirroring v2.0 SLAM), and lock the canonical `OrientedBox3D` wire format with a bit-rigorous `to_wire()/from_wire()` round-trip test. Ship a `SubprocessDetectorBridge` skeleton whose handshake + 5 s watchdog are proven by a standalone echo worker — no BoxeR / RT-DETR / OWLv2 code lands in Phase 2. Retire `ObjectDetector` and rewire `Coordinator` to the new pool. Flip the frontend `DetectionBoxManager` over to the new `"detections_3d"` WS payload; no dual-emit.

**Out of scope (deferred to Phase 3+):**
- Detector dropdown, Lifter dropdown, param panel, restart overlay UI polish — Phase 3 (DET-UI-*)
- `PointClusterLifter` (PCA-OBB) + `src/perception/geometry.py` canonical projection — Phase 4
- Non-YOLO backends (RT-DETRv2, BoxeR, OWLv2) — Phase 5 (Phase 2 ships only the subprocess bridge skeleton)
- Crash-fallback to YOLO on subprocess death — Phase 5 (DET-MODELS-06)
- Per-robot backend dispatch (different backends per robot) — Phase 8 stretch (DET-STRETCH-04); Phase 2's pool keys by robot_id but reads ONE global `pending_detector_backend`
- MetricsPanel, MuJoCo GT, JSONL export — Phase 6

</domain>

<decisions>
## Implementation Decisions

### Worker Pool Lifecycle + Restart

- **D-01:** `DetectorWorkerPool` is owned by `Coordinator` as `self._detector_pool`. Constructed in `__init__` / `reset_for_restart` alongside `self._robots`. Dies and rebuilds with every coordinator restart. Mirrors the current `self._detector: ObjectDetector` ownership shape. No `app.state.detector_pool` singleton; no module-level global.
- **D-02:** Backend selection via `POST /api/detectors/select` uses the **exact SLAM pattern**: the route sets `app.state.pending_detector_backend` (plus optional `pending_detector_params`) and calls `command_callback({"action": "restart"})`. `src/main.py`'s restart block reads `pending_detector_backend`, constructs the new `DetectorWorkerPool` via `DetectorRegistry.create()`, and assigns it to the rebuilt coordinator. No surgical `pool.swap_backend()` codepath in Phase 2.
- **D-03:** `detector_restart_complete` WS message fires **only after** every per-robot worker has finished `warmup(dummy_frame)`. The restart flow: (1) rebuild pool, (2) for each robot, `worker.warmup(dummy_rgbd_frame)`, (3) `main.py` appends `{"type": "detector_restart_complete", "payload": {"backend": ...}}` to `streaming_viz._message_queue`. UI restart overlay (Phase 3) dismisses on this signal and not before. Locks DET-UI-04 at the protocol layer in Phase 2.
- **D-04:** `DetectorWorker` per robot is structurally exactly as research `ARCHITECTURE.md` Answer to Q7 specifies: `_pending: tuple | None` single-slot queue with lock + `submit()` drops older pending → newest-wins backpressure. `_loop()` drains; `_latest: Detections3D | None` holds result. `pool.inspect_worker_queues()` exposes `{rid: {queue_depth: 0|1, drops_since_last_poll: int}}` for tests AND for Phase 6's MetricsPanel.
- **D-05:** `pool.submit(rid, frame, pose, slam_cloud)` is the ONLY submission entry point. Coordinator replaces its current `self._detector.submit_frame(...)` call in `_send_viz_update` (coordinator.py:637) with `self._detector_pool.submit(rid, frames[rid], pose, slam_cloud=None)`. Result read: `self._detector_pool.latest(rid)` replaces `self._detector.get_detections(rid)` at coordinator.py:647. Slam-cloud wiring is deferred to Phase 4 (Phase 4's `PointClusterLifter` is what actually consumes it; Phase 2 passes `None` exactly as today).

### OBB Wire Format (DET-3D-03, DET-3D-04)

- **D-06:** `OrientedBox3D.to_wire()` **auto-flips** the quaternion when `qw < 0`: returns `-q` in that case. Wire invariant: `qw >= 0` always. `from_wire()` asserts this invariant as a validation check and raises `ValueError` if violated. Callers never touch the sign explicitly; round-trip test exercises both inputs (qw>=0 and qw<0) and confirms both deserialize to equivalent rotations to ±1e-6.
- **D-07:** `track_id` wire convention: **key is OMITTED entirely** when no tracker is attached. `to_wire()` emits `track_id` only when `obb.track_id is not None`. `from_wire()` uses `obj.get("track_id")` → defaults to `None`. No `null`, no `-1` sentinel.
- **D-08:** WS encoding for `"detections_3d"` is **JSON with plain Python floats** — matches every other WS message (SLAM params, stats, poses). No msgpack, no base64 binary arrays. Double-precision JSON round-trips to well within the ±1e-6 tolerance required by DET-3D-04. 1000-random-box round-trip test asserts this.
- **D-09:** `OrientedBox3D.to_wire()` returns a **flat dict** with the field order from research ARCHITECTURE.md line 507: `{"center": [x,y,z], "half_extents": [x,y,z], "quaternion": [x,y,z,w], "class_id": int, "class_name": str, "score": float, "track_id"?: int}`. No nested `geometry`/`metadata` sub-dicts.
- **D-10:** Backend code paths are FORBIDDEN from constructing quaternions inline on the wire — the only quaternion-to-wire call site is `OrientedBox3D.to_wire()`. A grep-based test asserts no WS message construction in `src/` contains the literal substring `"quaternion":` except within `src/perception/types.py::OrientedBox3D.to_wire`.

### capture_pose + capture_timestamp (DET-API-05)

- **D-11:** `Detections3D` dataclass carries `capture_pose: np.ndarray (4, 4)` + `capture_timestamp: float` as **envelope-level fields**, not repeated per-box. Every box in `Detections3D.items` shares the pose/timestamp of the source frame. Per-box repetition rejected (wasteful; semantically wrong — a single frame produced all N boxes).
- **D-12:** `capture_timestamp` source is `frame.sim_time` — the `SensorFrame` already carries it. Captured at the moment `DetectorWorker.submit()` runs (coordinator call site). Phase 6 freshness metric computes `sim_now - capture_timestamp` directly off this field.
- **D-13:** `capture_pose` is captured at `pool.submit()` time — the coordinator reads `robot.get_pose()` and passes it as `pool.submit(rid, frame, pose, slam_cloud)`. The worker stores it in the `_pending` tuple and attaches it to `Detections3D` after lift. Pose drift during inference latency is eliminated: downstream consumers always see the pose as-of frame capture, not lift-time.
- **D-14:** `capture_pose` wire serialization is a **flat 16-float list, row-major**. Matches `THREE.Matrix4.fromArray()` on the frontend. JSON-compact. Not nested `[[...],[...],[...],[...]]`, not decomposed `(position[3] + quaternion[4])`.

### Subprocess Skeleton + Legacy Cutover

- **D-15:** The handshake test uses a **standalone** `scripts/echo_detector_worker.py` — a permanent helper script (not a test-only fixture, not an inline Python-c subprocess). Reads ZMQ endpoint from argv, loops on `recv_multipart`, echoes a fixed `{"n_det": 0, ...}` reply in msgpack. Reusable as a dev workflow harness for Phase 5 BoxeR work. Checked into repo.
- **D-16:** `SubprocessDetectorBridge` uses its OWN endpoint pattern: `ipc:///tmp/detector_bridge_<pid>_<id>`. NOT shared with SLAM (`ipc:///tmp/slam_bridge_*`). No shared ZMQ context. Locks research ARCHITECTURE.md's rejection of "reuse SLAM bridge" as a pitfall. Blast-radius isolation.
- **D-17:** Handshake test (`tests/perception/test_subprocess_bridge.py`) covers: (a) spawn echo worker, (b) ZMQ PAIR bind + multipart send of `[msgpack_header, rgb_bytes]`, (c) receive echo reply within 5 s, (d) msgpack round-trip fidelity on header fields, (e) kill echo worker → next send raises `zmq.Again` within `HANG_TIMEOUT_MS` and `_alive` flips false, (f) `_kill_process` path cleans up socket + context (no leaked file descriptors). No BoxeR-specific semantics — pure transport.
- **D-18:** Legacy `"detections"` WS message is **cut over immediately** — Phase 2 emits only `"detections_3d"`. `backend/web/streaming_viz.py:337-344` emits the new envelope with `{items, metrics, capture_pose, capture_timestamp, image_hw}`. No dual-emit, no env flag. Frontend `DetectionBoxManager.updateDetections` signature changes in the same phase to consume the new shape (OBB fields) — the client-side FOV/intrinsic back-projection removal (DET-3D-05) still waits for Phase 4 since Phase 2 lifters are still `MedianDepthLifter` with identity quaternion + AABB-sized half_extents.
- **D-19:** `src/perception/detector.py` **file is deleted** at end of Phase 2, along with `src/perception/detection_3d.py` (Phase 1 moved the math into `MedianDepthLifter` but kept the file as a shim; Phase 2 removes the shim). `Coordinator.__init__` imports `DetectorWorkerPool` instead of `ObjectDetector`. `INDOOR_CLASSES` lives only in `YOLOv11Backend` (Phase 1's runtime assert guard still applies across the remaining call site). Any test or module still importing `src.perception.detector.ObjectDetector` fails loudly — grep-clean the repo before merge.

### Claude's Discretion

- Exact `DetectorWorkerPool` class surface (`__init__`, `submit`, `latest`, `inspect_worker_queues`, `shutdown`, `warmup_all`, `reset_all`) — Claude picks method names and signatures consistent with SLAM registry usage patterns.
- Per-worker backpressure `drops_since_last_poll` counter reset semantics (per-poll vs session-lifetime) — Claude decides; Phase 6 will specify MetricsPanel surface.
- `crash_fallback` WS message `subsystem` field addition — Claude adds to the existing SLAM message schema, backward compat via `subsystem` default of `"slam"`.
- `pending_detector_params` live-tunable vs restart-required split on PATCH `/api/detectors/params` — Claude mirrors SLAM's `live_tunable` attribute read path.
- Frontend `detectorStore` scaffolding — Phase 2 only ships the backend surface; the store lands in Phase 3 but Phase 2's REST/WS contract must be stable before Phase 3 starts. Any frontend edits in Phase 2 are limited to `DetectionBoxManager` payload shape change.
- `OrientedBox3D.from_wire(obj)` input validation strictness — Claude decides (accept missing optional fields, raise on missing required fields). Round-trip test enforces the required-field set.
- Test fixture for 1000-randomized-OBB round-trip — Claude picks RNG seed; deterministic regeneration required.

### Folded Todos

None — no pending todos matched Phase 2 scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §Phase 2 — goal, success criteria (5 items), requirements list
- `.planning/REQUIREMENTS.md` §DET-API-04, §DET-API-05, §DET-MODELS-05, §DET-3D-03, §DET-3D-04 — the 5 requirements this phase must deliver
- `.planning/PROJECT.md` — overall v3.0 vision, subprocess-for-heavy-models non-negotiable
- `.planning/research/ARCHITECTURE.md` §Answer to Q5 (FastAPI routes + WS messages), §Answer to Q7 (DetectorWorker threading model), §Subprocess Protocol, §Common Failure Modes — wire format + transport protocol spec
- `.planning/research/PITFALLS.md` — reuse-SLAM-bridge anti-pattern, stale-pose downstream trap, dual-emit WS drift
- `.planning/research/SUMMARY.md` — v3.0 research executive summary
- `.planning/research/STACK.md` — pinned dep versions (msgpack, pyzmq already in tree; no new pins)
- `.planning/phases/01-detector-api-foundation/01-CONTEXT.md` §D-01–D-14 — Phase 1 locked decisions (Protocol shape, capability contract, eval-mode, YOLO migration, thread config, median-depth lifter consolidation)

### In-Tree Patterns to Mirror
- `src/slam/protocol.py` — runtime-checkable Protocol template (Phase 1 already mirrored for `DetectorProtocol`)
- `src/slam/registry.py::SLAMRegistry` — Phase 2's `DetectorRegistry` is Phase 1 deliverable; Phase 2 consumes it
- `src/slam/backends/subprocess_bridge.py::SubprocessSLAMBridge` — structural template for `SubprocessDetectorBridge` (separate class, separate endpoint pattern per D-16)
- `backend/web/slam_routes.py` — exact clone structure for `backend/web/detector_routes.py` (D-02 restart pattern)
- `backend/web/server.py:51-58, 127` — `command_callback` wiring + `active_slam_backend`/`pending_slam_backend` state pattern to clone for detector
- `src/main.py:432-498` — restart block pattern to extend for detector pool rebuild + warmup + `detector_restart_complete` emission
- `backend/web/streaming_viz.py:337-344` — legacy `"detections"` emission site being replaced with `"detections_3d"` per D-18

### Code to Modify (Phase 2)
- `src/coordination/coordinator.py` — replace `self._detector: ObjectDetector | None` (line ~140) with `self._detector_pool: DetectorWorkerPool`; rewire submit/read call sites at ~637-654; update `reset_for_restart` to rebuild pool
- `src/main.py` — add `pending_detector_backend` branch in restart block (~432); construct DetectorWorkerPool; warmup; emit `detector_restart_complete`
- `backend/web/server.py` — register detector_router; init `app.state.active_detector_backend = "yolov11"`, `app.state.pending_detector_backend = None`
- `backend/web/streaming_viz.py` — replace legacy `"detections"` emitter with `"detections_3d"` emitter consuming `Detections3D` envelope
- `frontend/src/components/DetectionBoxes.ts::DetectionBoxManager.updateDetections` — signature change to consume new wire shape (still axis-aligned half_extents with identity quaternion in Phase 2; PCA-OBB rendering is Phase 4)
- `frontend/src/utils/messageTypes.ts` — add `detections_3d`, `detector_restart_complete`, `detector_param_ack` message type literals
- `src/perception/types.py::OrientedBox3D` — flesh out `to_wire()`/`from_wire()` (Phase 1 shipped skeleton fields; Phase 2 adds the serialization methods)

### Code to Create (Phase 2)
- `src/perception/worker.py` — `DetectorWorker` class (per-robot thread, single-slot `_pending`, newest-wins `submit()`, `_loop()`, `warmup()`, `reset()`)
- `src/perception/worker_pool.py` — `DetectorWorkerPool` class (keyed by `robot_id`, `submit/latest/inspect_worker_queues/warmup_all/reset_all/shutdown`)
- `src/perception/subprocess_bridge.py` — `SubprocessDetectorBridge` class (separate from SLAM bridge per D-16; ZMQ PAIR + msgpack multipart; 5 s watchdog; own endpoint pattern)
- `backend/web/detector_routes.py` — `GET /api/detectors/backends`, `POST /api/detectors/select`, `GET /api/detectors/active`, `PATCH /api/detectors/params` (clone of slam_routes.py)
- `scripts/echo_detector_worker.py` — standalone ZMQ PAIR echo worker for handshake test + dev harness
- `tests/perception/test_obb_round_trip.py` — 1000-randomized-OBB round-trip test (DET-3D-04); ±1e-6 tolerance; seed fixed
- `tests/perception/test_worker_backpressure.py` — 30 Hz submit / 2 FPS backend; asserts queue depth stays ≤1 and drop counter advances
- `tests/perception/test_subprocess_bridge.py` — handshake test using `scripts/echo_detector_worker.py`; spawn/send/recv/msgpack round-trip/kill/timeout/cleanup (D-17)
- `tests/perception/test_detector_routes.py` — REST round-trip test: select → pending_detector_backend set → restart → active reflects new backend
- `tests/perception/test_no_inline_quaternion.py` — grep-based invariant per D-10 (quaternion-to-wire only from `OrientedBox3D.to_wire`)

### Code to Delete (Phase 2)
- `src/perception/detector.py` — entire file (D-19)
- `src/perception/detection_3d.py` — shim removal (D-19); MedianDepthLifter owns projection math

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/slam/backends/subprocess_bridge.py::SubprocessSLAMBridge` — exact ZMQ PAIR + msgpack + `HANG_TIMEOUT_MS=5000` + `_kill_process` + endpoint-cleanup pattern to clone structurally into `SubprocessDetectorBridge`. Do NOT subclass — separate class per D-16.
- `backend/web/slam_routes.py::select_backend/patch_params/get_active` — exact handler shape for detector_routes.py; the `live_tunable` attribute pattern on `parameter_schema.properties` is the live-vs-restart split logic to mirror.
- `src/main.py:436-496` restart block — uses `getattr(app.state, "pending_slam_backend", None)` + pipeline_config override + `reset_for_restart(bridge, robots)` + `app.state.active_slam_backend = pending_backend or "icp"` + `streaming_viz._message_queue.append({"type": "slam_restart_complete", ...})`. Extend this block (don't branch) to handle both subsystems in one restart.
- `src/bridge/sensor_types.py::SensorFrame.sim_time` — already populated; D-12 reads it at pool.submit() time.
- `src/coordination/coordinator.py::RobotVizData.detections` (line 58) — field becomes `detections_3d: Detections3D | None` replacing the current `list[dict]`.
- Phase 1 Wave 1 deliverables (just merged):
  - `src/_thread_config.py` imported first in main.py — Phase 2's worker threads inherit the thread budget
  - `src/perception/types.py::Detections2D, OrientedBox3D skeleton, Detections3D wrapper, DetectorInput` enum — Phase 2 extends `OrientedBox3D` with `to_wire/from_wire`
  - `src/perception/protocol.py::DetectorProtocol, Detection3DProtocol, TorchBackendMixin` — Phase 2's workers call `protocol.process_frame(frame)` and `lifter.lift(..., slam_cloud)`

### Established Patterns
- **Side-effect import for backends** — `main.py` already has `import src.slam.backends` and will get `import src.perception.backends` from Phase 1 plan 01-05. Phase 2 adds nothing to this pattern (registry itself ships in Phase 1).
- **Restart via `command_callback({"action": "restart"})`** — single entry point driven by REST handlers; sim loop drains, then reset_for_restart executes the swap. Phase 2 extends the existing restart branch, doesn't add a new dispatch.
- **WS envelope via `WSMessage`** — `backend/web/message_types.py`. Phase 2 adds type literals `DETECTIONS_3D`, `DETECTOR_RESTART_COMPLETE`, `DETECTOR_PARAM_ACK`, `DETECTOR_PARAM_UPDATE` to this module.
- **Lazy ImportError swallow in registry** — `backend.available()` classmethod drives install hint text (Phase 1 decision D-05 carries forward; Phase 2 does not revisit).

### Integration Points
- **Coordinator ↔ Pool** — `_send_viz_update` (`coordinator.py:637`) is the hot loop; Phase 2 swaps `self._detector.submit_frame(...)` → `self._detector_pool.submit(...)` AND `self._detector.get_detections(...)` → `self._detector_pool.latest(...)`. Detection list construction (coordinator.py:647-654) is replaced by packing `Detections3D` envelope directly into `RobotVizData.detections_3d`.
- **Viz ↔ WS** — `streaming_viz.py:337-344` reads `data.get("detections")` today (list[dict]). Phase 2 reads `data.get("detections_3d")` (Detections3D) and emits the new envelope shape. `data` shape is `RobotVizData.__getitem__` compatibility dict.
- **REST ↔ app.state** — same `command_callback + pending_*_backend` pattern as SLAM.

### Constraints
- No frontend UI polish in Phase 2 — only the `DetectionBoxManager` signature change and message type literals. The picker, overlay, param panel are all Phase 3.
- `OrientedBox3D` was shipped as a skeleton in Phase 1 (field order locked); Phase 2 cannot change the field order, only flesh out serialization methods.
- Phase 2 warm-up path depends on Phase 1's `warmup(dummy_frame)` method being mandatory on every backend (Phase 1 decision D-02). If Phase 1 Wave 4 lands `YOLOv11Backend.warmup` as a no-op, Phase 2 fixes that before the warm-up test can assert first-inference parity.
- YOLO's NMS must remain bit-deterministic across the rewire — the Phase 1 regression fixture (`yolo_regression_scene_01.npz`) must still pass when run end-to-end through `DetectorWorkerPool.submit() → latest()` in Phase 2.

</code_context>

<specifics>
## Specific Ideas

- The 1000-randomized-OBB round-trip test generates boxes with: center uniform in [-10, 10]^3, half_extents log-uniform in [0.05, 2.0]^3, quaternion sampled via `scipy.spatial.transform.Rotation.random()` with a fixed seed (then randomly negated to exercise qw<0 inputs), class_id in {56..75}, score uniform [0.5, 1.0]. `track_id` is set on half the boxes (even indices) and None on the other half — round-trip must preserve the omission/presence distinction.
- `DetectorWorkerPool.inspect_worker_queues()` returns `dict[str, dict]` with fields `{"queue_depth": 0|1, "drops_since_session_start": int, "last_submit_sim_time": float}` — the session-lifetime drop counter wins over per-poll because it's strictly-monotonic (easier test assertions) and Phase 6 can diff it across metrics emissions.
- `scripts/echo_detector_worker.py` accepts `--zmq <endpoint>` and optionally `--sleep-ms N` to simulate slow backend for backpressure tests.
- `detector_param_ack` WS message mirrors SLAM's exactly: `{"type": "detector_param_ack", "payload": {"param": ..., "status": "applied"|"requires_restart"|"unknown_parameter", "value": ...}}`.
- Grep invariant test for D-10: `grep -rn '"quaternion"' src/` must return exactly ONE hit — inside `OrientedBox3D.to_wire`. Exemption list: none.

</specifics>

<deferred>
## Deferred Ideas

- **Surgical `pool.swap_backend()` without full coordinator restart** — rejected for Phase 2; full restart is consistent with SLAM and low-risk. Phase 7's pipeline-editor backend swap (DET-PIPELINE-05) will revisit because pipeline param changes should NOT trigger full restart.
- **Per-robot backend dispatch** — stretch (Phase 8, DET-STRETCH-04). Phase 2's pool keys by robot_id but reads ONE global `pending_detector_backend`.
- **`"detections"` legacy dual-emit** — rejected; immediate cutover.
- **msgpack binary WS encoding** — rejected for Phase 2; revisit only if Phase 5's multi-backend profiling shows JSON overhead matters.
- **Crash-fallback auto-switch to YOLO on subprocess death** — Phase 5 (DET-MODELS-06); Phase 2's bridge skeleton surfaces the `_alive` flag and emits a placeholder `crash_fallback` event but there is no fallback backend to switch to until RT-DETR/BoxeR exist.
- **Frontend `detectorStore` (Zustand)** — Phase 3 (DET-UI-06).

### Reviewed Todos (not folded)

None — no pending todos matched Phase 2 scope.

</deferred>

---

*Phase: 02-per-robot-worker-and-wire-plumbing*
*Context gathered: 2026-04-13*
