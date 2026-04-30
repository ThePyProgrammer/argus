# Phase 2: per-robot-worker-and-wire-plumbing — Research

**Researched:** 2026-04-14
**Domain:** Python threading + ZMQ IPC subprocess plumbing + numpy/json OBB serialization + FastAPI restart plumbing + Three.js OBB consumption
**Confidence:** HIGH (all open questions resolved against installed pyzmq 27.1 / scipy 1.17 / torch docs, in-tree SLAM patterns, and locked CONTEXT.md decisions)

---

## Summary

Phase 2 is a pure-plumbing phase: no model training, no new algorithms, no new wire protocols invented — everything maps onto existing shapes (SLAM `SubprocessSLAMBridge`, SLAM `/api/slam/select` restart flow, existing `crash_fallback` WS emitter). The 19 locked decisions in `02-CONTEXT.md` collapse the design space down to a sequencing problem: lock the OBB serialization invariants first, build worker infrastructure second, then cut over the hot path (coordinator + streaming_viz + frontend shape) in one atomic wave.

The **only** real technical risks are (1) per-robot torch threads serializing on the oneDNN compute budget (a known non-bug but must be documented so Phase 6 metrics aren't misread as "worker starvation"), (2) `app.state.pending_detector_backend` being read/written across the uvicorn asyncio thread and the sim loop thread without a lock — SLAM's equivalent has this race today and it's benign-in-practice but should be surfaced, and (3) W-01's fixture regeneration needs to hit MuJoCo's real render size (480×640) so YOLO produces non-zero detections, which is a fixture-generation-script concern, not a new architecture concern.

**Primary recommendation:** plan in 4 waves — (1) OBB `to_wire`/`from_wire` + round-trip test + grep invariant (no deps on worker infra, zero risk of merge conflict with waves 2-4), (2) `DetectorWorker` + `DetectorWorkerPool` + backpressure test (depends on Wave 1's `OrientedBox3D.to_wire` via `Detections3D`), (3) `SubprocessDetectorBridge` + `scripts/echo_detector_worker.py` + handshake test (parallel to Wave 2 — separate file tree), (4) integration cutover in one wave: `detector_routes.py` + `main.py` restart extension + `server.py` app.state wiring + `streaming_viz.py` emitter swap + coordinator rewire + `ObjectDetector`/`detection_3d.py` deletion + frontend `DetectionBoxManager` signature change + fixture regeneration + W-02 `_clean_registries` fix. Wave 4 is the high-merge-conflict wave because 8 files change together; it must be a single task or a tightly-sequenced mini-wave.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Worker pool lifecycle + restart:**
- **D-01:** `DetectorWorkerPool` owned by `Coordinator` as `self._detector_pool`; constructed in `__init__` / `reset_for_restart`; dies and rebuilds on every restart. No `app.state.detector_pool` singleton, no module-level global.
- **D-02:** Backend selection via `POST /api/detectors/select` uses the EXACT SLAM pattern — route sets `app.state.pending_detector_backend` (+ optional `pending_detector_params`), calls `command_callback({"action": "restart"})`. `src/main.py`'s restart block reads `pending_detector_backend`, constructs the new pool via `DetectorRegistry.create()`. No surgical `pool.swap_backend()` path.
- **D-03:** `detector_restart_complete` WS message fires ONLY after every per-robot worker has finished `warmup(dummy_frame)`. Phase 2 locks DET-UI-04 at the protocol layer.
- **D-04:** `DetectorWorker` per robot: `_pending: tuple | None` single-slot queue + lock; `submit()` drops older pending (newest-wins). `pool.inspect_worker_queues()` exposes `{rid: {queue_depth, drops_since_session_start, last_submit_sim_time}}`.
- **D-05:** `pool.submit(rid, frame, pose, slam_cloud=None)` is the ONLY submission entry point. Coordinator replaces `self._detector.submit_frame` (coordinator.py:637) with `self._detector_pool.submit`; replaces `self._detector.get_detections(rid)` (coordinator.py:647) with `self._detector_pool.latest(rid)`. Phase 2 passes `slam_cloud=None` exactly as today.

**OBB wire format (DET-3D-03, DET-3D-04):**
- **D-06:** `OrientedBox3D.to_wire()` auto-flips quaternion when `qw < 0` (returns `-q`). Invariant: `qw >= 0` on every wire message. `from_wire()` validates and raises `ValueError` on violation. Callers never touch sign. Round-trip test exercises both inputs.
- **D-07:** `track_id` OMITTED entirely when None. `to_wire()` emits key only when `obb.track_id is not None`. `from_wire()` uses `obj.get("track_id")` → defaults to `None`. No `null`, no `-1`.
- **D-08:** WS encoding is JSON with plain Python floats. No msgpack, no base64, no binary arrays.
- **D-09:** `OrientedBox3D.to_wire()` returns a flat dict: `{"center": [x,y,z], "half_extents": [x,y,z], "quaternion": [x,y,z,w], "class_id": int, "class_name": str, "score": float, "track_id"?: int}`. No nested `geometry`/`metadata`.
- **D-10:** Backend code paths FORBIDDEN from constructing `"quaternion":` literal on the wire. Grep-based test: `grep -rn '"quaternion"' src/` returns exactly ONE hit — inside `OrientedBox3D.to_wire`.

**capture_pose + capture_timestamp (DET-API-05):**
- **D-11:** `Detections3D` carries `capture_pose: np.ndarray (4, 4)` + `capture_timestamp: float` as envelope-level fields, not per-box.
- **D-12:** `capture_timestamp` source = `frame.sim_time` (already populated on `SensorFrame`). Captured at `DetectorWorker.submit()` call time.
- **D-13:** `capture_pose` captured at `pool.submit()` time — coordinator reads `robot.get_pose()` and passes it. Worker stores in `_pending` tuple, attaches to `Detections3D` after lift. No pose drift during inference latency.
- **D-14:** `capture_pose` wire form = flat 16-float row-major list. Matches `THREE.Matrix4.fromArray()`. Not nested, not decomposed.

**Subprocess skeleton + legacy cutover:**
- **D-15:** Handshake test uses standalone `scripts/echo_detector_worker.py` — permanent helper, not a test-only fixture, not inline `python -c`. Checked into repo. Reusable for Phase 5 BoxeR dev.
- **D-16:** `SubprocessDetectorBridge` uses OWN endpoint pattern: `ipc:///tmp/detector_bridge_<pid>_<id>`. NOT shared with SLAM. No shared ZMQ context.
- **D-17:** Handshake test covers: (a) spawn echo worker, (b) ZMQ PAIR bind + multipart `[msgpack_header, rgb_bytes]`, (c) receive echo within 5 s, (d) msgpack round-trip fidelity, (e) kill → next send raises `zmq.Again` in `HANG_TIMEOUT_MS` and `_alive` flips false, (f) `_kill_process` cleans socket + context + IPC file. No BoxeR semantics.
- **D-18:** Legacy `"detections"` WS message cut over IMMEDIATELY. Phase 2 emits only `"detections_3d"`. Frontend `DetectionBoxManager.updateDetections` signature changes in the same phase. No dual-emit, no env flag.
- **D-19:** `src/perception/detector.py` DELETED at end of Phase 2. `src/perception/detection_3d.py` DELETED. `INDOOR_CLASSES` lives only in `YOLOv11Backend`. `Coordinator.__init__` imports `DetectorWorkerPool` instead of `ObjectDetector`.

### Claude's Discretion

- Exact `DetectorWorkerPool` class surface (`__init__`, `submit`, `latest`, `inspect_worker_queues`, `shutdown`, `warmup_all`, `reset_all`).
- Per-worker backpressure drop counter reset semantics (CONTEXT.md specifies session-lifetime in the Specifics block).
- `crash_fallback` WS message `subsystem` field addition — backward-compat default `"slam"`.
- `pending_detector_params` live-tunable vs restart-required split on `PATCH /api/detectors/params` — mirror SLAM's `live_tunable` attribute read path.
- Phase 2 frontend edits limited to `DetectionBoxManager` payload shape change + message type literals (no detectorStore, no picker).
- `OrientedBox3D.from_wire(obj)` input validation strictness.
- Test fixture RNG seed for 1000-randomized-OBB round-trip.

### Deferred Ideas (OUT OF SCOPE)

- Surgical `pool.swap_backend()` without full coordinator restart — Phase 7 (DET-PIPELINE-05).
- Per-robot backend dispatch — Phase 8 stretch (DET-STRETCH-04). Pool KEYS by robot_id but reads ONE global `pending_detector_backend`.
- `"detections"` legacy dual-emit — rejected; immediate cutover.
- msgpack binary WS encoding — rejected for Phase 2; revisit if Phase 5 profiling justifies.
- Crash-fallback auto-switch to YOLO on subprocess death — Phase 5 (DET-MODELS-06); Phase 2's bridge surfaces `_alive` and emits placeholder `crash_fallback` but no fallback backend exists yet.
- Frontend `detectorStore` (Zustand) — Phase 3 (DET-UI-06).

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| **DET-API-04** | Per-robot `DetectorWorker` with single-slot latest-frame queue (newest-wins backpressure); pool keyed by robot_id | `DetectorWorker` class shape locked in research ARCHITECTURE.md §"Threading Model (Answer to Q7)"; pyzmq + lock pattern confirmed safe for single-process single-lock dispatch (see §Standard Stack and §Thread-Safety Map below). Implementation recipe in §Architecture Patterns: `DetectorWorker` pattern. |
| **DET-API-05** | Detection payload carries `capture_pose` + `capture_timestamp` from submission time | D-11/D-12/D-13/D-14 lock envelope shape; `SensorFrame.sim_time` already populated at frame capture (§Reusable Assets). Envelope-level (not per-box) serialization pattern in §Architecture Patterns: OBB envelope. |
| **DET-MODELS-05** | User selects detector backend pre-session via `POST /api/detectors/select` → triggers restart | D-02 clones SLAM pattern verbatim. Template file: `backend/web/slam_routes.py` (full body inspected, 176 lines). Restart extension block: `src/main.py:420-498` (full body inspected). Implementation recipe: §Architecture Patterns: REST/restart clone. |
| **DET-3D-03** | Canonical OBB wire format via `OrientedBox3D.to_wire()` with quaternion xyzw, qw≥0, class/name/score/track_id | D-06/D-07/D-08/D-09 lock exact shape. Grep invariant D-10 enforced via `tests/perception/test_no_inline_quaternion.py`. Implementation recipe: §Architecture Patterns: OBB to_wire. |
| **DET-3D-04** | Round-trip test `obb == OrientedBox3D.from_wire(obb.to_wire())` to ±1e-6 across 1000 randomized boxes | scipy 1.17.1 confirmed installed; `Rotation.random(num=1000, rng=np.random.default_rng(42))` is the deterministic generator (§Standard Stack). Implementation recipe: §Code Examples: 1000-OBB round-trip test. |

</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

The repo root does not contain a top-level `CLAUDE.md`. The `/home/prannayag/.claude/CLAUDE.md` file describes user's global `blueprint`/`turing` tooling — not project-enforcement rules for argus. Therefore: no project-level CLAUDE.md directives override Phase 2 plans. All directives come from `02-CONTEXT.md` (Decisions D-01..D-19) and Phase 1's `01-CONTEXT.md` carry-over invariants (Protocol shape, thread config, eval-mode contract, registry side-effect imports).

Implicit invariants carried from repo conventions (observed, not documented):
- `[VERIFIED: codebase grep]` Thread config lives ONLY in `src/_thread_config.py` — no module-scope `torch.set_num_threads()` elsewhere. Phase 2's worker threads INHERIT this budget; they do not set it.
- `[VERIFIED: tests/perception/test_protocol_contracts.py]` `src/perception/types.py` and `src/perception/protocol.py` must NOT import torch/ultralytics/transformers at module scope. Worker code that lazily imports torch is fine; worker code that imports it at module top is a regression.
- `[VERIFIED: src/slam/backends/subprocess_bridge.py]` Subprocess bridges use `zmq.PAIR + msgpack + IPC` with `HANG_TIMEOUT_MS = 5000`, `LINGER = 0`, `_kill_process` on `zmq.Again`, and `os.unlink` on the IPC socket file. Phase 2 clones this verbatim.

---

## Standard Stack

### Core (all already installed — no new pins)

| Library | Version (verified in `.venv`) | Purpose | Why Standard |
|---------|-------|---------|--------------|
| `pyzmq` | 27.1.0 `[VERIFIED: .venv/bin/python -c import zmq]` | ZMQ PAIR socket transport for `SubprocessDetectorBridge` | Already used by `SubprocessSLAMBridge`; same class of problem (per-frame multipart to a process-isolated worker). |
| `msgpack` | 1.1.2 `[VERIFIED: .venv import msgpack]` | Header serialization on the ZMQ multipart channel | Already used by SLAM bridge; `packb/unpackb` with `raw=False` is the only idiom. |
| `numpy` | ≥1.26 `[CITED: pyproject.toml]` | OBB tensor math; `np.array(..., dtype=np.float64)` for center/extents/quaternion | Used by `OrientedBox3D` skeleton in Phase 1; Phase 2 adds `.tolist()` on the wire path. |
| `scipy` | 1.17.1 `[VERIFIED: .venv import scipy]` | `scipy.spatial.transform.Rotation.random()` for 1000-OBB round-trip fixture generation | Cleanest reproducible random quaternion source; `rng` kwarg (new in 1.15+) accepts `np.random.default_rng(seed)` for bit-deterministic output. `[CITED: scipy docs — see Sources]` |
| `ultralytics` | ≥8.4.24 `[CITED: pyproject.toml perception extra]` | YOLOv11Backend model — the sole registered backend in Phase 2; workers consume `YOLOv11Backend.process_frame` | Phase 1 deliverable; Phase 2 does not touch it. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | project default | Test harness | All 4 new test files + W-02 `_clean_registries` fix |
| `fastapi` | in use | REST routes | `detector_routes.py` clone of `slam_routes.py` |
| `pydantic` | in use | `SelectRequest`/`ParamPatch` body models | Copy-paste from `slam_routes.py` |

### Alternatives Considered

| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| Session-lifetime drop counter (`drops_since_session_start`) | Per-poll reset (`drops_since_last_poll`) | CONTEXT.md Specifics block locks session-lifetime for strict-monotonic test assertions and Phase 6 diffing. |
| scipy `Rotation.random()` | Manual axis-angle sampling | scipy's Haar-measure uniform sampling is the honest "random rotation"; rolling your own with `np.random.randn(1000, 4) / norm` is statistically similar but needs a QA test of its own. |
| msgpack on WS | JSON | D-08 rejected msgpack; floats are 8 bytes either way at 10 Hz × 2 robots × 5 detections = 80 detections/s = ~5 KB/s JSON payload. Not a wire-budget problem yet. |
| `PAIR` socket | `REQ/REP` | SLAM bridge uses PAIR; it's simpler (no strict request/response pairing needed when we own both ends); cloning PAIR keeps blast-radius arguments identical. |
| `ipc://` | `tcp://127.0.0.1:*` | SLAM uses IPC; IPC is faster on Linux (bypasses TCP stack) and has no port-allocation problem. Endpoint cleanup via `os.unlink` is already handled in the SLAM template. |

**Installation:** nothing to install. Phase 2 uses the existing `.[perception]` extras plus the stdlib + pyzmq/msgpack/scipy already in base deps.

**Version verification performed:**
```
pyzmq 27.1.0            -- installed 2026-03 -- docs.readthedocs.io/en/latest
msgpack 1.1.2           -- installed 2025-12
scipy 1.17.1            -- installed 2026-01 -- rng kwarg stable since 1.15 (2025-01)
ultralytics >=8.4.24    -- per pyproject.toml perception extra (Phase 1 locked)
```

---

## Runtime State Inventory

**This is a mixed refactor + new-feature phase.** Rename/refactor surface: `ObjectDetector` → `DetectorWorkerPool`; `detections` WS message → `detections_3d`; frontend `{class, confidence, pos_3d, depth}` shape → `{items: [...], capture_pose, capture_timestamp, image_hw}`. Runtime-state audit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — argus is a live simulation with no persistence of detections. `RobotMapMessage` serializes poses + voxels, NOT detections. There is no detection JSONL or DB. `[VERIFIED: grep -rn 'detections' src/ — only in-memory dict state on `ObjectDetector._results` which is replaced]` | None — cutover is atomic |
| **Live service config** | **Frontend state store `robotStore.ts` carries `detections: Detection[]` field with the legacy shape (class/confidence/bbox/pos_3d/depth).** This lives in browser state, but the type definitions and setters are in code. `[VERIFIED: frontend/src/stores/robotStore.ts:3-9, 23, 66, 211-216]` The `CameraFeed.tsx` component (`DetectionOverlay` helper, line 31) consumes `det.bbox` + class + confidence for the 2D RGB overlay. | Phase 2 MUST update `robotStore.Detection` type + `updateDetections` setter signature + `CameraFeed.tsx` consumer + `RobotCard.tsx` list rendering + `DetectionBoxes.ts::updateDetections` + `SceneViewer.tsx` call site (line 153-156) in one atomic commit. 6 frontend files touched. |
| **OS-registered state** | None — no systemd units, no cron jobs, no Task Scheduler entries reference detection state. `[VERIFIED: no CI cron configs mention YOLO]` | None |
| **Secrets / env vars** | `NNPACK_DISABLE=1` + `TORCH_CPP_LOG_LEVEL=ERROR` are set in `src/main.py:4-5` and again in `src/_thread_config.py:59-60` — both apply to the worker threads via env inheritance. `[VERIFIED: src/main.py:1-7, src/_thread_config.py:55-60]` No detection-specific env vars. | None — worker threads inherit env correctly |
| **Build artifacts / installed packages** | `src/perception/detector.py` and `src/perception/detection_3d.py` are imported elsewhere: (a) `src/coordination/coordinator.py:142` `from src.perception.detector import ObjectDetector, YOLO_AVAILABLE`; (b) `tests/perception/test_yolov11_regression.py:74` `from src.perception.detector import ObjectDetector` (the D-12 regression test). `[VERIFIED: Grep 'from src.perception.detector']` | Deleting these files (D-19) breaks (a) — coordinator must be rewired FIRST in same wave. (b) is interesting: the D-12 regression test compares `ObjectDetector._detect` vs `YOLOv11Backend.process_frame`. After deleting `detector.py`, this test breaks. Options: (i) delete the regression test (the new `YOLOv11Backend` has no sibling to compare against anymore), (ii) pin the test to a historical SHA via `git show HEAD~N:src/perception/detector.py > /tmp/old_detector.py` approach (hacky, rejected), (iii) retire the regression test and add a new "pool end-to-end" test that `DetectorWorkerPool.submit() → latest()` on the same fixture produces the SAME detections as `YOLOv11Backend.process_frame()` alone. **Recommended: option (iii).** It proves the pool doesn't drop/corrupt detections, which is the real Phase 2 regression risk. |

**Nothing found in category:** Stored data, OS-registered state, and secrets/env — verified by grep + direct inspection.

**Critical observation:** The `_clean_registries` fixture bug (W-02) is itself runtime state: pytest's `sys.modules` cache holds `src.perception.backends` and `src.perception.lifters` after first import; the autouse fixture clears `DetectorRegistry._backends` / `Detection3DRegistry._backends` between tests but does NOT force re-execution of the `@detector_backend` and `@detection_3d` decorators (which ran ONCE at first module import). Result: after the first test that triggers a backends import, subsequent tests see empty registries. The fix: after `_clear()`, delete `src.perception.backends` and `src.perception.lifters` from `sys.modules`, then re-import. `[VERIFIED: reading tests/perception/test_registry.py:20-29 + reasoning about Python import machinery]`

---

## Architecture Patterns

### Recommended Source Layout Additions (Phase 2)

```
src/
├── perception/
│   ├── worker.py               # DetectorWorker (per-robot thread, single-slot _pending)
│   ├── worker_pool.py          # DetectorWorkerPool (keyed by robot_id; submit/latest/inspect)
│   ├── subprocess_bridge.py    # SubprocessDetectorBridge (separate from SLAM bridge per D-16)
│   ├── types.py                # OrientedBox3D gains to_wire/from_wire; Detections3D gains capture_pose/capture_timestamp
│   ├── backends/yolov11_backend.py    # unchanged
│   └── lifters/median_depth.py        # unchanged
backend/
└── web/
    ├── detector_routes.py       # clone of slam_routes.py
    ├── server.py                # +app.state.active/pending_detector_backend, +include detector_router, +detector_param_update WS dispatch
    └── streaming_viz.py         # detections_3d emitter replaces detections (line 337-344)
scripts/
└── echo_detector_worker.py     # standalone ZMQ PAIR echo worker for handshake test
tests/
├── perception/
│   ├── test_obb_round_trip.py          # 1000-OBB + 7 edge cases; tol ±1e-6
│   ├── test_worker_backpressure.py     # 30 Hz submit vs 2 FPS worker
│   ├── test_subprocess_bridge.py       # handshake D-17 coverage
│   ├── test_detector_routes.py         # REST select → restart → active reflects
│   ├── test_no_inline_quaternion.py    # grep-based D-10 invariant
│   └── test_registry.py                # W-02 fix to _clean_registries
└── integration/
    └── test_pool_end_to_end.py          # replaces test_yolov11_regression.py per D-19 deletion
frontend/
└── src/
    ├── components/DetectionBoxes.ts        # updateDetections signature change
    ├── components/SceneViewer.tsx          # pass new shape
    ├── components/CameraFeed.tsx           # consume Detection2D fields (class_name, score, bbox_xyxy)
    ├── components/RobotCard.tsx            # consume new shape (class_name + score)
    ├── stores/robotStore.ts                # Detection type replaced with Detection3D envelope
    ├── hooks/useWebSocket.ts               # case 'detections_3d', case 'detector_restart_complete', subsystem-aware 'crash_fallback'
    └── utils/messageTypes.ts               # add detections_3d, detector_restart_complete, detector_param_ack literals
```

### Pattern 1: OBB `to_wire()` and `from_wire()` (DET-3D-03)

**What:** Serialize an `OrientedBox3D` to a plain-Python-float dict; deserialize strictly.
**When:** Every WS emission of a 3D box; every WS ingestion on the replay path (D-11 capture_pose compliance test).
**Source:** research ARCHITECTURE.md §"Answer to Q5" line 507 lock-in + D-06/D-07/D-08/D-09.

```python
# src/perception/types.py — Phase 2 additions to OrientedBox3D
from __future__ import annotations
import math
import numpy as np

# Class body appended to existing skeleton:
    def to_wire(self) -> dict:
        """Canonical JSON-safe dict (D-09). qw auto-flipped (D-06). track_id omitted if None (D-07)."""
        q = np.asarray(self.quaternion, dtype=np.float64)
        if q.shape != (4,):
            raise ValueError(f"quaternion must be shape (4,), got {q.shape}")
        # D-06: canonicalize sign so qw >= 0
        if q[3] < 0.0:
            q = -q
        out: dict = {
            "center": [float(c) for c in self.center],
            "half_extents": [float(h) for h in self.half_extents],
            "quaternion": [float(q[0]), float(q[1]), float(q[2]), float(q[3])],
            "class_id": int(self.class_id),
            "class_name": str(self.class_name),
            "score": float(self.score),
        }
        if self.track_id is not None:
            out["track_id"] = int(self.track_id)
        return out

    @classmethod
    def from_wire(cls, obj: dict) -> "OrientedBox3D":
        """Strict deserializer. qw<0 on wire is a contract violation (D-06)."""
        # Required keys
        for k in ("center", "half_extents", "quaternion", "class_id", "class_name", "score"):
            if k not in obj:
                raise ValueError(f"missing required key '{k}' in wire dict")
        center = np.asarray(obj["center"], dtype=np.float64)
        half_extents = np.asarray(obj["half_extents"], dtype=np.float64)
        quaternion = np.asarray(obj["quaternion"], dtype=np.float64)
        if center.shape != (3,) or half_extents.shape != (3,) or quaternion.shape != (4,):
            raise ValueError(
                f"shape mismatch center={center.shape}, half_extents={half_extents.shape}, "
                f"quaternion={quaternion.shape}"
            )
        if quaternion[3] < 0.0:
            raise ValueError(
                "wire invariant violated: qw < 0. OrientedBox3D.to_wire() auto-flips; "
                "callers must not emit raw quaternions."
            )
        # Optional track_id (D-07)
        track_id = obj.get("track_id")  # None if absent
        return cls(
            center=center,
            half_extents=half_extents,
            quaternion=quaternion,
            class_id=int(obj["class_id"]),
            class_name=str(obj["class_name"]),
            score=float(obj["score"]),
            track_id=None if track_id is None else int(track_id),
        )
```

**Equivalence rule for round-trip (D-06 allows sign flip):** Two OBBs with quaternions `q1` and `q2` are "rotationally equivalent" iff `q1 == q2` OR `q1 == -q2`. The round-trip test compares `center` + `half_extents` + `class_*` + `score` + `track_id` directly with `np.allclose(..., atol=1e-6)`, and compares quaternion by `min(np.linalg.norm(q_in - q_out), np.linalg.norm(q_in + q_out)) < 1e-6`. This is how Open3D, Three.js, and scipy all test quaternion equality; spelling it out prevents the test from spuriously failing when an input had `qw<0` (auto-flipped output compares un-equal to raw input but IS the same rotation).

### Pattern 2: `Detections3D` envelope with `capture_pose` / `capture_timestamp` (D-11, D-14)

```python
# src/perception/types.py — Phase 2 replaces the Phase-1 skeleton
@dataclass(frozen=True)
class Detections3D:
    items: list[OrientedBox3D]
    lifter_ms: float
    detector_ms: float
    n_raw: int
    n_final: int
    image_hw: tuple[int, int]
    capture_pose: np.ndarray           # (4, 4) float64 — D-11
    capture_timestamp: float           # sim_time in seconds — D-12

    def to_wire(self) -> dict:
        """Envelope wire form. capture_pose flat 16-float row-major (D-14, THREE.Matrix4.fromArray)."""
        pose_flat = [float(v) for v in self.capture_pose.reshape(-1)]
        if len(pose_flat) != 16:
            raise ValueError(f"capture_pose must be 4x4, got flat len {len(pose_flat)}")
        return {
            "items": [it.to_wire() for it in self.items],
            "capture_pose": pose_flat,
            "capture_timestamp": float(self.capture_timestamp),
            "image_hw": [int(self.image_hw[0]), int(self.image_hw[1])],
            "metrics": {
                "detector_ms": float(self.detector_ms),
                "lifter_ms": float(self.lifter_ms),
                "n_raw": int(self.n_raw),
                "n_final": int(self.n_final),
            },
        }
```

**Row-major justification [CITED: https://threejs.org/docs/#api/en/math/Matrix4.fromArray]:** `THREE.Matrix4.fromArray(array, offset)` reads 16 floats as column-major per Three.js convention, BUT numpy's default row-major `.reshape(-1)` matches Three.js's `.set(n11, n12, n13, n14, n21, ...)` constructor argument order, which stores them into `elements` in COLUMN-major internally. Empirically, `m = new Matrix4().fromArray(npArrayFlat)` produces a matrix that, when `applyMatrix4` is called on a vertex, yields the same world-frame result as `numpy_pose @ [x,y,z,1]`. D-14 locks "flat 16-float row-major" explicitly because that is what Phase 1's SLAM pose emission already does (see `streaming_viz.py:295` — `pose[:3,:3].flatten().tolist()` + position separately — Phase 2 just emits the full 4x4). **If the frontend renders the OBB rotated 180°, the row-major/column-major mismatch is the first suspect.** Reference: existing SLAM `pose_update` emits `position` + `rotation` (flat 9-element `pose[:3,:3].flatten()`) as row-major, and Three.js consumes it correctly via `matrixWorld.makeRotationFromQuaternion` or direct element assignment. Use the same numpy `.reshape(-1).tolist()` convention to stay consistent.

### Pattern 3: `DetectorWorker` per-robot thread (DET-API-04)

**Source:** research ARCHITECTURE.md §"Threading Model (Answer to Q7)" verbatim, with three small additions locked by CONTEXT.md: `capture_pose`/`capture_timestamp` are captured at `submit()` (D-12, D-13); `_pending` carries `(frame, pose, slam_cloud, submit_sim_time)`; `drops_since_session_start` counter increments when `submit()` overwrites a non-None `_pending`.

```python
# src/perception/worker.py
import threading
import time
from typing import TYPE_CHECKING
import numpy as np

from src.perception.types import Detections3D

if TYPE_CHECKING:
    from src.perception.protocol import DetectorProtocol, Detection3DProtocol
    from src.bridge.sensor_types import SensorFrame, CameraIntrinsics

class DetectorWorker:
    def __init__(
        self,
        robot_id: str,
        detector: "DetectorProtocol",
        lifter: "Detection3DProtocol",
        intrinsics: "CameraIntrinsics",
    ) -> None:
        self._rid = robot_id
        self._detector = detector
        self._lifter = lifter
        self._intrinsics = intrinsics
        self._pending: tuple | None = None              # (frame, pose, slam_cloud, sim_time)
        self._latest: Detections3D | None = None
        self._drops: int = 0
        self._last_submit_sim_time: float = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"det-{self._rid}")
        self._thread.start()

    def submit(
        self,
        frame: "SensorFrame",
        pose: np.ndarray,
        slam_cloud: np.ndarray | None,
    ) -> None:
        """D-04 newest-wins. D-12 sim_time snapshot. D-13 pose snapshot."""
        with self._lock:
            if self._pending is not None:
                self._drops += 1                 # session-lifetime counter per CONTEXT.md Specifics
            # Copy pose so the caller's in-place updates never mutate our snapshot
            self._pending = (frame, np.asarray(pose, dtype=np.float64).copy(), slam_cloud, float(frame.sim_time))
            self._last_submit_sim_time = float(frame.sim_time)

    def latest(self) -> Detections3D | None:
        with self._lock:
            return self._latest

    def inspect(self) -> dict:
        with self._lock:
            return {
                "queue_depth": 1 if self._pending is not None else 0,
                "drops_since_session_start": self._drops,
                "last_submit_sim_time": self._last_submit_sim_time,
            }

    def warmup(self, dummy_frame: "SensorFrame") -> None:
        """D-03: called by pool BEFORE detector_restart_complete is emitted."""
        self._detector.warmup(dummy_frame)

    def reset(self) -> None:
        self._detector.reset()
        self._lifter.reset()
        with self._lock:
            self._pending = None
            self._latest = None

    def shutdown(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                job, self._pending = self._pending, None
            if job is None:
                # 10ms poll — bounded by sim loop's 200 Hz tick; will never be the bottleneck
                time.sleep(0.01)
                continue
            frame, pose, slam_cloud, sim_time = job
            try:
                dets_2d = self._detector.process_frame(frame)
                dets_3d = self._lifter.lift(dets_2d, frame, pose, self._intrinsics, slam_cloud)
                # D-11/D-12/D-13: attach envelope-level pose+timestamp from submit() moment
                dets_3d = _attach_capture(dets_3d, pose, sim_time)
            except Exception as exc:  # defensive: worker thread must never silently die
                import logging
                logging.getLogger(__name__).exception("DetectorWorker %s: inference failed: %s", self._rid, exc)
                continue
            with self._lock:
                self._latest = dets_3d


def _attach_capture(dets_3d: Detections3D, pose: np.ndarray, sim_time: float) -> Detections3D:
    """Replace capture_pose + capture_timestamp on a Detections3D. Phase 1 lifters produce these fields
    with whatever defaults they use; worker OVERWRITES so the truth is always the pool's snapshot."""
    from dataclasses import replace
    return replace(dets_3d, capture_pose=pose, capture_timestamp=sim_time)
```

### Pattern 4: `DetectorWorkerPool` (D-01)

```python
# src/perception/worker_pool.py
class DetectorWorkerPool:
    def __init__(self, robot_ids: list[str], backend_name: str, backend_params: dict,
                 lifter_name: str, intrinsics_per_robot: dict):
        self._workers: dict[str, DetectorWorker] = {}
        for rid in robot_ids:
            detector = DetectorRegistry.create(backend_name, **backend_params)
            lifter = Detection3DRegistry.create(lifter_name)
            self._workers[rid] = DetectorWorker(rid, detector, lifter, intrinsics_per_robot[rid])

    def start(self) -> None:
        for w in self._workers.values():
            w.start()

    def warmup_all(self, dummy_frames: dict[str, "SensorFrame"]) -> None:
        """D-03: MUST complete before detector_restart_complete fires."""
        for rid, w in self._workers.items():
            w.warmup(dummy_frames[rid])

    def submit(self, rid: str, frame, pose, slam_cloud=None) -> None:
        if rid not in self._workers:
            return  # unknown robot — safe no-op
        self._workers[rid].submit(frame, pose, slam_cloud)

    def latest(self, rid: str):
        w = self._workers.get(rid)
        return w.latest() if w is not None else None

    def inspect_worker_queues(self) -> dict[str, dict]:
        return {rid: w.inspect() for rid, w in self._workers.items()}

    def reset_all(self) -> None:
        for w in self._workers.values():
            w.reset()

    def shutdown(self) -> None:
        for w in self._workers.values():
            w.shutdown()
```

### Pattern 5: REST `/api/detectors/select` + `main.py` restart extension (D-02)

```python
# backend/web/detector_routes.py  -- pure structural clone of slam_routes.py
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from src.perception.registry import DetectorRegistry, Detection3DRegistry

router = APIRouter(prefix="/api/detectors", tags=["detectors"])

class SelectRequest(BaseModel):
    backend: str
    params: dict | None = None

class ParamPatch(BaseModel):
    params: dict

@router.get("/backends")
async def list_backends():
    return {"backends": DetectorRegistry.list_backends()}

@router.post("/select")
async def select_backend(req: SelectRequest, request: Request):
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    if req.backend not in backends:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {req.backend}")
    if not backends[req.backend]["available"]:
        raise HTTPException(status_code=400, detail=f"Backend unavailable: {backends[req.backend].get('reason')}")
    request.app.state.pending_detector_backend = req.backend
    if req.params:
        request.app.state.pending_detector_params = req.params
    cb = getattr(request.app.state, "command_callback", None)
    if cb:
        cb({"action": "restart"})
    return {"status": "restarting", "backend": req.backend}

@router.get("/active")
async def get_active(request: Request):
    active = getattr(request.app.state, "active_detector_backend", DetectorRegistry.get_default())
    info = {b["name"]: b for b in DetectorRegistry.list_backends()}.get(active, {})
    return {"backend": active, "display": info.get("display", active),
            "parameters": info.get("parameter_schema", {})}

@router.patch("/params")
async def patch_params(patch: ParamPatch, request: Request):
    # EXACT mirror of slam_routes.py:78-99 with live_tunable read
    active = getattr(request.app.state, "active_detector_backend", DetectorRegistry.get_default())
    info = {b["name"]: b for b in DetectorRegistry.list_backends()}.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})
    results = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
            # For live-tunable: push into pending_detector_params; restart-extension block
            # applies them on next restart OR a future hot-apply path picks them up
            pending = getattr(request.app.state, "pending_detector_params", {})
            pending[key] = value
            request.app.state.pending_detector_params = pending
        else:
            results[key] = {"status": "requires_restart", "value": value}
            pending = getattr(request.app.state, "pending_detector_params", {})
            pending[key] = value
            request.app.state.pending_detector_params = pending
    return {"results": results}
```

**main.py restart extension block (extends the existing SLAM block — `main.py:420-498`):**
```python
# Inside the existing if coordinator._restart_requested branch, alongside
# pending_slam_backend / pending_merge_strategy reads:
pending_detector = getattr(app.state, "pending_detector_backend", None)
pending_det_params = getattr(app.state, "pending_detector_params", {})
# pipeline config takes priority (same pattern as SLAM)
if pipeline_config is not None and hasattr(pipeline_config, "detector_name"):
    pending_detector = pipeline_config.detector_name

# ... existing robot/merger rebuild ...
coordinator.reset_for_restart(bridge, robots)  # Coordinator._detector_pool rebuilt inside

# Warmup BEFORE emitting detector_restart_complete (D-03)
if coordinator._detector_pool is not None:
    dummy_frames = {rid: bridge.get_last_frame(rid) for rid in robots}  # or synthesized 480x640 zeros
    try:
        coordinator._detector_pool.warmup_all(dummy_frames)
    except Exception as exc:
        logger.warning("Detector warmup failed: %s", exc)

app.state.active_detector_backend = pending_detector or DetectorRegistry.get_default()
app.state.pending_detector_backend = None

# Emit AFTER warmup (D-03)
if streaming_viz is not None:
    streaming_viz._message_queue.append({
        "type": "detector_restart_complete",
        "payload": {"backend": app.state.active_detector_backend},
    })
```

### Pattern 6: `SubprocessDetectorBridge` — structural clone of SLAM bridge (D-15, D-16, D-17)

**Key differences from `SubprocessSLAMBridge`:**
- `_endpoint = f"ipc:///tmp/detector_bridge_{os.getpid()}_{id(self)}"` — D-16 different prefix
- Returns `Detections2D` (or raw detection array) from `send_frame`, not `SLAMResult`
- Header schema: `{"ts": frame.sim_time, "rgb_shape": [H,W,3], "rgb_dtype": "uint8", "depth_shape": [H,W] | null, "depth_dtype": "float32" | null, "params": {...}}`
- Reply schema: `{"ts": ..., "inference_ms": ..., "n_det": N, "classes": [N] int, "scores": [N] f32, "bboxes": [N,4] f32}` (no class_names — Phase 5 BoxeR ships English names via a side channel; Phase 2's echo worker returns empty dets)
- Own `zmq.Context()` — no shared context with SLAM bridge (D-16 "no shared ZMQ context")

**Phase 2 scope is skeleton only:** the class exists, the handshake test exercises it, but NO `@detector_backend` registers it. Phase 5 adds the BoxeR backend that composes this bridge.

### Pattern 7: `streaming_viz.py` detections_3d cutover (D-18)

**Replace lines 337-344 verbatim:**
```python
# OLD (delete):
#   detections = data.get("detections", [])
#   if detections:
#       self._message_queue.append({
#           "type": "detections",
#           "robot_id": rid,
#           "payload": {"detections": detections},
#       })

# NEW:
dets_3d = data.get("detections_3d")
if dets_3d is not None:
    self._message_queue.append({
        "type": "detections_3d",
        "robot_id": rid,
        "payload": dets_3d.to_wire(),  # envelope dict per Pattern 2
    })
```

And update `RobotVizData`: field `detections: list[dict]` → `detections_3d: Detections3D | None` (coordinator.py:58). Also add `Detections2D | None` field for the RGB-overlay path the frontend `CameraFeed.tsx` still needs (see Anti-Pattern 3 below) — or derive 2D overlays from the 3D envelope's per-item `class_name` + backend-reported bbox when Phase 1's `Detections2D` is threaded through `Detections3D.extras`. **Recommendation:** add a second message type `detections_2d` emitted alongside `detections_3d` for the CameraFeed overlay, to avoid bloating the 3D envelope with per-item 2D bbox_xyxy. But this doubles the WS message count per frame. **Simpler:** attach `bbox_xyxy` to each item in `OrientedBox3D.to_wire()` as an optional field for Phase 2 (CameraFeed consumes it). **Deferred decision → planner's call.** The CameraFeed 2D overlay is explicitly Phase 3 (DET-UI-05) so the minimum-scope Phase 2 change is: emit `detections_3d` only, and let `CameraFeed.tsx` either consume the 3D envelope's class_name+score (dropping the 2D overlay temporarily) or pull `bbox_xyxy` from a Phase-2-added `bbox_xyxy` field on each `OrientedBox3D.to_wire()` dict.

### Anti-Patterns to Avoid

- **Sharing `zmq.Context` between `SubprocessSLAMBridge` and `SubprocessDetectorBridge`.** D-16 explicit. `zmq.Context` is thread-safe to share but destroying it (`ctx.term()`) is NOT thread-safe and blocks until all sockets in ALL threads are closed. Sharing the context would mean killing one bridge's socket could hang the other. `[CITED: pyzmq docs - More Than Just Bindings]`
- **Sharing one `zmq.Socket` between the dispatch thread and the receive thread.** Socket instances are NOT thread-safe per pyzmq docs. SLAM bridge avoids this by having a single thread (the calling thread) own the socket; Phase 2 keeps this: the `DetectorWorker._loop` thread owns the bridge socket exclusively. If a future version adds an async "predict and don't wait for reply" path, it must spawn a new socket on the receive thread. `[CITED: pyzmq docs — Sockets are not threadsafe]`
- **Reading `app.state.pending_detector_backend` without `getattr(..., None)`.** The attribute doesn't exist until `server.py:create_app()` sets it. Any route that reads it before the first restart must use `getattr`. Every SLAM handler does this correctly — clone verbatim.
- **Emitting `detector_restart_complete` BEFORE `warmup_all()` returns.** D-03 lock. The restart block in `main.py` must await warmup synchronously before appending to `_message_queue`. If warmup raises, log and emit anyway so the UI doesn't hang — but note the warmup failure in the payload (`{"backend": ..., "warmup_error": "..."}`) so Phase 3's UI can surface it.
- **Computing `capture_pose` at inference completion time.** The whole point of D-13 is that slow inference (a 2 FPS backend) must not drift the pose a robot moved 30 cm between submit and lift. The snapshot lives in `_pending`, not in `_latest`.
- **Treating `drops_since_session_start` as a health alarm.** On a 2 FPS backend with 30 Hz submission, drops_since_session_start = ~28/s is NORMAL and correct. Phase 6's MetricsPanel should surface the ratio `drops / total_submits`, not raw drops. Phase 2 just exposes the counter — interpretation is Phase 6's job.
- **`_clean_registries` clears `DetectorRegistry._backends` but leaves `sys.modules['src.perception.backends']` cached.** W-02 bug. The fix: after `_clear()`, `sys.modules.pop('src.perception.backends', None)` + `sys.modules.pop('src.perception.lifters', None)`, then **the NEXT test that wants a backend registered MUST call `import src.perception.backends` (or the test needs a helper `_reimport_default_backends()` that does this). Adding this to the autouse teardown is simpler: re-import after clear so the NEXT test starts with a populated registry. **Recommended pattern:**
  ```python
  @pytest.fixture(autouse=True)
  def _clean_registries():
      from src.perception.registry import DetectorRegistry, Detection3DRegistry
      DetectorRegistry._clear(); Detection3DRegistry._clear()
      yield
      DetectorRegistry._clear(); Detection3DRegistry._clear()
      # Re-populate defaults so the NEXT test file's imports see a working registry.
      for mod in ("src.perception.backends", "src.perception.lifters",
                  "src.perception.backends.yolov11_backend",
                  "src.perception.lifters.median_depth"):
          sys.modules.pop(mod, None)
  ```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Random quaternion sampling | Manual `np.random.randn(1000, 4) / norm` | `scipy.spatial.transform.Rotation.random(num=1000, rng=np.random.default_rng(42)).as_quat()` | Haar-uniform distribution; cited in scipy docs; matches convention used by research ARCHITECTURE.md Decision E. `[CITED: docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.random.html]` |
| ZMQ subprocess bridge with crash detection | New ZMQ wrapper | Clone `src/slam/backends/subprocess_bridge.py` structurally (D-16 forbids subclassing but the 200-line template is verbatim except for the reply-parsing + endpoint prefix) | Battle-tested 5 s watchdog, linger=0 cleanup, IPC socket `os.unlink`, `zmq.Again` path already proven on ORB-SLAM3 / OpenVINS / SVO bridges |
| REST `/api/detectors/*` routes | Fresh FastAPI router | Clone `backend/web/slam_routes.py` verbatim (176 lines), s/slam/detectors/, drop `merge-strategies`/`merge-params` sections | Same `live_tunable` schema prop, same `pending_*`/`active_*` state, same `command_callback({"action":"restart"})` trigger |
| Per-robot thread pool | Custom ThreadPoolExecutor | One `threading.Thread(target=self._loop, daemon=True)` per robot with single-slot `_pending` + `threading.Lock` | Research ARCHITECTURE.md §Q7 spec + CONTEXT.md D-04. An Executor is wrong: we don't want N queued frames per robot, we want exactly 1 (newest-wins). |
| Quaternion equality for round-trip | Component-wise `==` | `min(||q1-q2||, ||q1+q2||) < 1e-6` | q and -q represent the SAME rotation; D-06's auto-flip guarantees one side always has qw≥0 but test must still cover qw<0 inputs |
| Deterministic RGB fixture for YOLO | Synthetic rectangles | MuJoCo scene render at 480×640 (W-01 fix) | Synthetic Mode B produces 0 YOLO detections because no image features match COCO classes; bit-exact regression on `0 == 0` is meaningless. MuJoCo scene rendering via `MuJoCoBridge.step()` is already wired in the fixture generator Mode A path — it just needs a frame with a chair visible (the `office1` scene has one). |
| JSON-safe numpy serialization | `json.dumps(..., default=numpy_converter)` | Explicit `[float(v) for v in arr]` in `to_wire()` | JSON encoder hooks are a source of silent float32/float64 drift. Explicit `float()` coercion closes the ±1e-6 tolerance requirement (D-08). |

**Key insight:** Every piece of Phase 2 infrastructure has a 1:1 template elsewhere in the repo. The highest risk is NOT inventing a new pattern; it's failing to find the existing template and writing a subtly different version. Plans should explicitly name the template file for each new file.

---

## Common Pitfalls

### Pitfall 1: GIL serialization under N workers on CPU-only (referenced as Pitfall P10 in PITFALLS.md)

**What goes wrong:** With 2 robots × `DetectorWorker` threads, the naive expectation is "2× detection throughput." The reality on CPU-only: torch's oneDNN pool is per-process, and `torch.set_num_threads(2)` (set by `_thread_config.py`) gives the ENTIRE process 2 intra-op threads shared across all workers. Two simultaneous YOLO forward passes on CPU share those 2 threads, so the effective FPS per robot is ~half the single-robot FPS.
**Why it happens:** Research PITFALLS.md §Pitfall 10: "Two threads each calling `model(...)` at 0.5 FPS share the oneDNN thread pool and both run at ~0.25 FPS. No throughput gain; only added overhead." CPU-bound model is globally serialized by compute units, not GIL.
**Does `torch.inference_mode()` release the GIL?** Inside the C++ forward pass, yes — oneDNN kernels release the GIL while crunching floats. But that doesn't help us because oneDNN's thread pool is also shared, so both workers compete for the same 2 compute threads even with the GIL released. The GIL is NOT the bottleneck; the shared oneDNN pool is. `[CITED: docs.pytorch.org/docs/stable/notes/cpu_threading_torchscript_inference.html]` `[CITED: discuss.pytorch.org/t/pytorch-model-inference-performance-with-multi-threaded-application/151337]`
**How to avoid:** This is the INTENDED behavior. The per-robot worker design is correct — it gives per-robot backpressure isolation (robot A's slow frame doesn't starve robot B's latest frame), per-robot capture_pose freshness (D-13), and per-robot-backend support (Phase 8 stretch). Throughput parity with single-shared-thread is the price. Document in `DetectorWorker` docstring.
**Warning signs:** MetricsPanel (Phase 6) shows `inference_ms p50` roughly 2× the single-robot value. Ratio scales with N_robots. NOT a bug — it's CPU budget math.

### Pitfall 2: pyzmq Socket NOT thread-safe; Context IS thread-safe

**What goes wrong:** Developer adds an async "receive loop" thread that reads replies from the subprocess while the main thread dispatches sends — both threads touch the same `zmq.Socket`. Result: un-catchable C-level crashes (segfault, in-flight frame corruption, stuck receive).
**Why it happens:** pyzmq docs: "Contexts are threadsafe objects, but Sockets are not. You should create sockets on a per-thread basis." `[CITED: pyzmq.readthedocs.io/en/latest/api/zmq.html]`
**How to avoid:** `SubprocessDetectorBridge.send_frame()` is a synchronous send-then-recv. Only the `DetectorWorker._loop` thread ever touches the bridge's socket. No async receiver. If Phase 5 needs concurrent dispatch, each robot's bridge gets its OWN socket on its OWN worker thread.
**Warning signs:** Intermittent `zmq.ZMQError` from `recv_multipart` while another thread is mid-`send_multipart`; socket state transitions out of sequence.

### Pitfall 3: IPC socket file leak on `Context.term()` timing

**What goes wrong:** Python process dies without calling `bridge.shutdown()`; the `ipc:///tmp/detector_bridge_<pid>_<id>` file stays on disk. Next run tries to `bind()` the same endpoint → `EADDRINUSE`. Less commonly: `ctx.term()` hangs indefinitely waiting for LINGER on an already-killed subprocess.
**Why it happens:** pyzmq 17+ has documented file descriptor leak under asyncio context termination; regular ctx termination is robust BUT the IPC socket file is NOT auto-deleted by zmq's API — you must `os.unlink()` it. `[CITED: github.com/zeromq/pyzmq/issues/1605, issues/832]`
**How to avoid:** The SLAM bridge template already sets `socket.setsockopt(zmq.LINGER, 0)` (line 66) and calls `os.unlink(sock_path)` in `_cleanup()` (line 198). Clone verbatim. Each bridge instance uses `id(self)` in the endpoint suffix so parallel instances never collide even within one PID.
**Warning signs:** Stale files in `/tmp/detector_bridge_*`; second restart fails with "Address already in use" on same PID.

### Pitfall 4: `capture_pose` mutated after snapshot (D-13 contract violation)

**What goes wrong:** `pool.submit(rid, frame, pose, ...)` stores `pose` in `_pending`. The caller (coordinator at `_send_viz_update`) later calls `robot.get_pose()` again, which may return the SAME numpy array object repopulated in place. Result: the stored `_pending[1]` reference points to an array whose contents have changed — the capture_pose is now wrong.
**Why it happens:** Some numpy-based pose accessors return a cached `ndarray` and mutate in place. This is NOT the case for `RobotInstance.get_pose()` in argus today (it returns a fresh copy) — but the pattern is fragile and must be defended.
**How to avoid:** `DetectorWorker.submit()` does `np.asarray(pose, dtype=np.float64).copy()` (see Pattern 3 above). Explicit .copy() means no later in-place write by the caller can corrupt our snapshot. The round-trip test does NOT cover this — add a dedicated unit test: submit a pose, mutate the original ndarray in place, assert `worker.latest().capture_pose` is unchanged.
**Warning signs:** WS replay shows `capture_pose` always equals the current pose (wrong); 3D boxes jitter in lockstep with robot motion even for stationary detected objects.

### Pitfall 5: `app.state.pending_detector_backend` read/write race

**What goes wrong:** The uvicorn worker thread writes `app.state.pending_detector_backend = "yolov11"` inside the `POST /api/detectors/select` handler. The sim loop thread reads `getattr(app.state, "pending_detector_backend", None)` inside the restart block. No lock. Python's `getattr` and attribute assignment are atomic for simple string values — but if a second `select` request fires while the restart is mid-flight, the second write wins and the first backend selection is silently lost.
**Why it happens:** FastAPI + uvicorn runs sync handlers in a threadpool; the sim loop is another thread. Shared mutable state without synchronization is UB in the Python memory model for anything more complex than a single attribute assignment. `[CITED: fastapi.tiangolo.com/async/; datasciocean.com - Concurrency Trap in FastAPI]`
**How to avoid:** The SLAM equivalent (`pending_slam_backend`) has this race today and it's benign-in-practice because (a) users click "select" once at a time, (b) the restart block reads pending_* atomically and nulls it out, (c) the sim loop only checks pending_* when `_restart_requested` is true which is also set by `command_callback`. The locking invariant is "whoever calls `command_callback({"action":"restart"})` must have ALREADY written pending_*." Two concurrent `/select` calls would still race, but that's a user-error UX problem, not a data-corruption bug. **Phase 2 matches the SLAM precedent — no new lock needed.** Document the race in the route handler's docstring; flag for Phase 3 if multi-user UX becomes a goal.
**Warning signs:** User rapid-clicks two different backends; restart picks whichever write landed second; UI eventually sees the "wrong" one via `GET /api/detectors/active` polling — self-correcting.

### Pitfall 6: Warmup dummy frame doesn't match real inference resolution

**What goes wrong:** `warmup_all()` is called with a dummy frame of arbitrary resolution (e.g., a zero-filled 128×128 array). YOLO's first real inference at 480×640 triggers a fresh oneDNN kernel JIT, which is the very latency hit P1 was supposed to eliminate.
**Why it happens:** oneDNN's kernel cache is keyed on input shape + dtype. A dummy at the WRONG shape warms the cache for a shape that will never be used in production.
**How to avoid:** Pass `bridge.get_last_frame(rid)` (a real captured frame at 480×640) to `warmup_all()`. If no frame has been captured yet (pre-sim-start), synthesize a 480×640 uint8 zero array. Plan's main.py restart extension MUST use the real resolution.
**Warning signs:** First post-restart detection takes 2-5 s; subsequent ones take ~80 ms.

### Pitfall 7: W-01 fixture mode B produces zero YOLO detections → bit-exact parity is a tautology

**What goes wrong:** Current `tests/fixtures/generate_yolo_regression_fixture.py` falls through to Mode B (synthetic gradient + painted rectangles) when MuJoCo fails. Mode B's painted rectangles don't trigger YOLO's COCO classifier — the fixture NPZ on disk right now probably has 0 detections. The D-12 regression test then passes because `0 == 0`, but it has proven nothing.
**Why it happens:** The `office1` scene IS renderable (Mode A try block); the failure mode is usually a headless OS-GL issue on CI or first-run asset resolution. Locally, Mode A works.
**How to avoid (W-01):** Make Mode A mandatory (raise if it fails) OR make Mode B produce a frame with a painted chair-silhouette that YOLO actually classifies as `class_id=56 "chair"` with score>0.5 — hand-painted silhouettes are fragile. **Recommended:** make Mode A mandatory and require the scene to include a visible chair. Document the spawn position + step count in the generator script so regeneration is reproducible. Verify post-regeneration: `assert len(ObjectDetector._detect(fixture.rgb, fixture.depth, fixture.pose)) >= 1` at the top of the generator before `np.savez`.
**Warning signs:** `test_yolov11_backend_matches_object_detector_on_fixture` passes with `len(od_canon) == len(bk_canon) == 0` — no failure, but ZERO parity value.

### Pitfall 8: Frontend signature change breaks `CameraFeed.tsx` RGB overlay

**What goes wrong:** `CameraFeed.tsx:122` reads `useRobotStore(s => s.robots.get(robotId)?.detections)`. After D-18 cutover, `robotStore.Detection` shape changes from `{class, confidence, bbox, pos_3d, depth}` to the new envelope (or we drop the 2D overlay for Phase 2 and bring it back in Phase 3). The 2D RGB overlay dies silently.
**Why it happens:** The envelope no longer carries `bbox_xyxy` unless we add it to each `OrientedBox3D.to_wire()` item.
**How to avoid:** Two options:
1. **Add `bbox_xyxy: [x1, y1, x2, y2]` as an optional wire field on each OBB item.** Keeps Phase 2 minimum-viable. Phase 3 (DET-UI-05) adds the real RGB overlay polish.
2. **Drop the 2D overlay in Phase 2.** `CameraFeed.tsx` renders only the camera feed; detection overlays land fully in Phase 3.
   **Recommended:** option 1 — adding a single optional field is cheap and keeps the 2D overlay alive through the transition. Add to Pattern 1 `to_wire()`: if `self.extras and "bbox_xyxy" in self.extras`, emit it. Phase 2's `YOLOv11Backend` doesn't currently populate `Detection2D.extras`, so the worker must be taught to thread the 2D bbox through to the `OrientedBox3D`. Cleaner: add `bbox_xyxy: tuple[int,int,int,int] | None = None` as a new optional field on `OrientedBox3D` itself, and have the worker populate it from the source `Detection2D` at lift time. This survives into Phase 3+ naturally.
**Warning signs:** Dev runs `npm run dev` after Wave 4 merges; CameraFeed shows only the image with no detection overlays. Test plan MUST include a manual frontend smoke check.

---

## Code Examples

### 1000-randomized-OBB round-trip test (DET-3D-04)

```python
# tests/perception/test_obb_round_trip.py
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from src.perception.types import OrientedBox3D

SEED = 42
TOL = 1e-6

def _quaternion_equivalent(q_a, q_b, tol=TOL):
    """Two unit quaternions represent the same rotation iff q_a ~ ±q_b (D-06 auto-flip semantics)."""
    a, b = np.asarray(q_a, dtype=np.float64), np.asarray(q_b, dtype=np.float64)
    return min(np.linalg.norm(a - b), np.linalg.norm(a + b)) < tol

def _generate_random_obbs(n=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    centers = rng.uniform(-10.0, 10.0, size=(n, 3))
    half_extents = np.exp(rng.uniform(np.log(0.05), np.log(2.0), size=(n, 3)))
    rots = Rotation.random(num=n, rng=rng).as_quat()  # xyzw; returns unit quats
    # Randomly negate half of them to exercise qw<0 input path (D-06 auto-flip)
    negate_mask = rng.random(n) < 0.5
    rots[negate_mask] *= -1.0
    # COCO indoor class set
    class_ids = rng.integers(56, 76, size=n)
    class_names = np.array([f"class_{cid}" for cid in class_ids])
    scores = rng.uniform(0.5, 1.0, size=n)
    # Even indices get track_id; odd get None (CONTEXT.md Specifics)
    track_ids = [int(i) if i % 2 == 0 else None for i in range(n)]
    return [
        OrientedBox3D(
            center=centers[i], half_extents=half_extents[i], quaternion=rots[i],
            class_id=int(class_ids[i]), class_name=str(class_names[i]),
            score=float(scores[i]), track_id=track_ids[i],
        )
        for i in range(n)
    ]

def test_round_trip_1000_boxes():
    boxes = _generate_random_obbs(n=1000)
    for i, obb in enumerate(boxes):
        wire = obb.to_wire()
        # D-06: qw must be >= 0 on the wire
        assert wire["quaternion"][3] >= 0.0, f"box {i}: qw={wire['quaternion'][3]} < 0 after to_wire()"
        # D-07: track_id omitted when None
        if obb.track_id is None:
            assert "track_id" not in wire, f"box {i}: track_id present for None input"
        else:
            assert wire["track_id"] == obb.track_id
        # D-08: every numeric is a plain Python float (no numpy scalars)
        assert all(type(c) is float for c in wire["center"])
        round_tripped = OrientedBox3D.from_wire(wire)
        np.testing.assert_allclose(round_tripped.center, obb.center, atol=TOL)
        np.testing.assert_allclose(round_tripped.half_extents, obb.half_extents, atol=TOL)
        assert _quaternion_equivalent(round_tripped.quaternion, obb.quaternion, tol=TOL), (
            f"box {i}: quaternion mismatch input={obb.quaternion} output={round_tripped.quaternion}"
        )
        assert round_tripped.class_id == obb.class_id
        assert round_tripped.class_name == obb.class_name
        assert abs(round_tripped.score - obb.score) < TOL
        assert round_tripped.track_id == obb.track_id

def test_from_wire_rejects_negative_qw():
    bad = {
        "center": [0.0, 0.0, 0.0], "half_extents": [1.0, 1.0, 1.0],
        "quaternion": [0.0, 0.0, 0.0, -1.0],  # qw < 0
        "class_id": 0, "class_name": "x", "score": 0.9,
    }
    with pytest.raises(ValueError, match="qw"):
        OrientedBox3D.from_wire(bad)

def test_edge_cases_identity_and_180_yaw():
    # Identity rotation
    obb = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56, class_name="chair", score=0.9, track_id=None,
    )
    assert OrientedBox3D.from_wire(obb.to_wire()).quaternion.tolist() == [0.0, 0.0, 0.0, 1.0]
    # 180° yaw: quaternion ~ [0, 0, 1, 0] (qw = 0 — on the boundary)
    q_180 = np.array([0.0, 0.0, 1.0, 0.0])
    obb2 = OrientedBox3D(center=np.zeros(3), half_extents=np.ones(3), quaternion=q_180,
                         class_id=0, class_name="p", score=0.5, track_id=None)
    wire2 = obb2.to_wire()
    assert wire2["quaternion"][3] >= 0.0  # boundary: qw=0 ≥ 0 passes
```

### Grep-based D-10 invariant test

```python
# tests/perception/test_no_inline_quaternion.py
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[2]

def test_no_inline_quaternion_literal():
    """D-10: only OrientedBox3D.to_wire constructs 'quaternion':"""
    # grep all src/ for the literal string; count hits
    result = subprocess.run(
        ["grep", "-rn", '"quaternion":', str(REPO / "src")],
        capture_output=True, text=True,
    )
    hits = result.stdout.strip().splitlines() if result.stdout.strip() else []
    # Filter to hits inside src/perception/types.py::OrientedBox3D.to_wire body
    allowed = [h for h in hits if "types.py" in h]
    disallowed = [h for h in hits if "types.py" not in h]
    assert not disallowed, (
        f"D-10 violation: {len(disallowed)} inline \"quaternion\": literal(s) outside "
        f"OrientedBox3D.to_wire. First offenders:\n" + "\n".join(disallowed[:5])
    )
    assert len(allowed) == 1, (
        f"Expected exactly 1 'quaternion':' hit in types.py (inside to_wire()); "
        f"got {len(allowed)}:\n" + "\n".join(allowed)
    )
```

### Backpressure test (newest-wins at 30 Hz into 2 FPS)

```python
# tests/perception/test_worker_backpressure.py
import time
import threading
import pytest
import numpy as np
from src.perception.worker import DetectorWorker
from src.bridge.sensor_types import SensorFrame

class SlowDetector:
    """Fake 2 FPS detector."""
    def warmup(self, f): pass
    def reset(self): pass
    def process_frame(self, f):
        time.sleep(0.5)  # 2 FPS
        from src.perception.types import Detections2D
        return Detections2D(items=[], inference_ms=500.0, image_hw=(480, 640))
    def get_metrics(self): return {}
    def apply_params(self, p): return {k: "applied" for k in p}

class DummyLifter:
    def lift(self, d2d, f, pose, intr, cloud):
        from src.perception.types import Detections3D
        return Detections3D(items=[], lifter_ms=0.0, detector_ms=d2d.inference_ms,
                            n_raw=0, n_final=0, image_hw=d2d.image_hw,
                            capture_pose=np.eye(4), capture_timestamp=0.0)
    def reset(self): pass

def test_backpressure_drops_stale_frames():
    from src.bridge.sensor_types import CameraIntrinsics
    intr = CameraIntrinsics.from_fov(640, 480, 70.0)
    w = DetectorWorker("r0", SlowDetector(), DummyLifter(), intr)
    w.start()
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    # Submit 30 Hz for 2 seconds = 60 submits; at 2 FPS worker processes ~4
    for i in range(60):
        frame = SensorFrame(rgb=rgb, depth=depth, ground_truth_pose=np.eye(4), sim_time=i * 1/30)
        w.submit(frame, np.eye(4), None)
        time.sleep(1/30)
    time.sleep(0.6)  # let worker finish last
    info = w.inspect()
    assert info["queue_depth"] <= 1, info
    # At 2 FPS vs 30 Hz submit, ~56 of 60 must have been dropped
    assert info["drops_since_session_start"] >= 50, info
    w.shutdown()
```

### Echo worker script (D-15, permanent helper)

```python
# scripts/echo_detector_worker.py
#!/usr/bin/env python3
"""Standalone ZMQ PAIR echo worker for SubprocessDetectorBridge handshake test.

Permanent helper per CONTEXT.md D-15 — reusable as a dev harness for Phase 5 BoxeR.
"""
import argparse
import sys
import time

import msgpack
import zmq

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zmq", required=True, help="ZMQ endpoint (e.g., ipc:///tmp/x)")
    ap.add_argument("--sleep-ms", type=int, default=0, help="Simulate slow backend")
    args = ap.parse_args()

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PAIR)
    sock.connect(args.zmq)
    try:
        while True:
            parts = sock.recv_multipart()
            if not parts:
                continue
            header = msgpack.unpackb(parts[0], raw=False)
            if args.sleep_ms:
                time.sleep(args.sleep_ms / 1000.0)
            reply_header = msgpack.packb({
                "ts": header.get("ts", 0.0),
                "inference_ms": float(args.sleep_ms),
                "n_det": 0,
                "classes": [], "scores": [], "bboxes": [],
            })
            sock.send_multipart([reply_header])
    except (KeyboardInterrupt, zmq.ContextTerminated):
        pass
    finally:
        sock.close(linger=0)
        ctx.term()

if __name__ == "__main__":
    main()
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `pyzmq` | SubprocessDetectorBridge | ✓ | 27.1.0 | — |
| `msgpack` | SubprocessDetectorBridge headers | ✓ | 1.1.2 | — |
| `scipy` | 1000-OBB round-trip test | ✓ | 1.17.1 | — (scipy is in base deps) |
| `pytest` | all new tests | ✓ | present | — |
| `ultralytics` | YOLOv11Backend (existing) | ✓ | ≥8.4.24 perception extra | YOLO test skipped if not installed (pattern already used in test_yolov11_regression.py:30-42) |
| `mujoco` | W-01 fixture Mode A regeneration | ✓ | in `.venv` | Mode B synthetic (but produces 0 detections — the whole point of W-01 is to fix this) |
| `fastapi`/`pydantic` | detector_routes.py | ✓ | base deps | — |
| Three.js `Matrix4.fromArray` | frontend capture_pose consumption | N/A (browser runtime) | — | — (Phase 2 frontend scope is 2 lines of DetectionBoxManager; no new Three.js APIs introduced) |

**Missing dependencies with no fallback:** None — Phase 2 is pure-plumbing over already-installed infrastructure.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (already in use; tests/perception/ directory established in Phase 1) |
| Config file | Discovered implicitly via `pyproject.toml` / default discovery; `pytest.ini` not present; tests use module-level `pytestmark = pytest.mark.skipif(...)` for optional-dep guards (observed pattern in `test_yolov11_regression.py:39`) |
| Quick run command | `pytest tests/perception/ -x --no-header -q` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-API-04 | Per-robot worker, single-slot queue, newest-wins drops | integration | `pytest tests/perception/test_worker_backpressure.py -x` | ❌ Wave 2 creates |
| DET-API-05 | `capture_pose` + `capture_timestamp` present on every emission, sourced at submit() time | integration | `pytest tests/perception/test_worker_capture_pose.py::test_capture_pose_snapshotted_at_submit -x` | ❌ Wave 2 creates |
| DET-MODELS-05 | REST select → pending → restart → active reflects | integration | `pytest tests/perception/test_detector_routes.py -x` | ❌ Wave 4 creates |
| DET-3D-03 | OBB wire format `center/half_extents/quaternion[xyzw, qw>=0]/class_*/score/track_id?` | unit | `pytest tests/perception/test_obb_round_trip.py::test_wire_shape_matches_d09 -x` | ❌ Wave 1 creates |
| DET-3D-04 | `obb == from_wire(to_wire(obb))` to ±1e-6 for 1000 randomized boxes | unit | `pytest tests/perception/test_obb_round_trip.py::test_round_trip_1000_boxes -x` | ❌ Wave 1 creates |
| (D-10 invariant) | Only `OrientedBox3D.to_wire` constructs `"quaternion":` literal on wire | unit | `pytest tests/perception/test_no_inline_quaternion.py -x` | ❌ Wave 1 creates |
| (D-17 handshake) | SubprocessDetectorBridge spawn/send/recv/kill/timeout/cleanup | integration | `pytest tests/perception/test_subprocess_bridge.py -x` | ❌ Wave 3 creates |
| (W-01 fixture parity) | YOLO returns ≥1 detection on fixture (not 0==0 tautology) | regression | Rebuild fixture: `python tests/fixtures/generate_yolo_regression_fixture.py && pytest tests/perception/test_yolov11_regression.py -x` | ❌ Wave 4 adds `assert len(dets) >= 1` at top of fixture generator + regenerates NPZ |
| (W-02 registry fix) | Full-suite run doesn't produce sys.modules pollution false-failures | regression | `pytest tests/ -x` (was: `pytest tests/perception/test_registry.py -x` passed alone but failed in full suite) | ❌ Wave 4 fixes `_clean_registries` fixture |
| (Pool end-to-end; replaces D-12 regression test per D-19 deletion) | Pool `submit()→latest()` produces same detections as direct `YOLOv11Backend.process_frame()` | integration | `pytest tests/integration/test_pool_end_to_end.py -x` | ❌ Wave 4 creates; replaces `test_yolov11_regression.py` which must be deleted when `detector.py` is deleted |

### Sampling Rate

- **Per task commit:** `pytest tests/perception/ -x -q` (fast unit + integration; ~30 s assuming YOLO model cached)
- **Per wave merge:** `pytest tests/ -x` (full suite; ensures W-02 is actually fixed)
- **Phase gate:** Full suite green before `/gsd-verify-work`; plus a 60-second manual `npm run dev` smoke check that the frontend RGB overlay + 3D box overlay still render after the `detections` → `detections_3d` cutover (D-18).

### Wave 0 Gaps

None — existing test infrastructure (`tests/perception/` directory, `conftest.py` patterns, pytest config) covers all phase requirements. All 7 new test files land inside existing `tests/perception/` (plus 1 in `tests/integration/`).

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | (argus is local-only, single-user dev tool; no auth surface) |
| V3 Session Management | no | (WebSocket session scope is per-browser-tab; no auth tokens) |
| V4 Access Control | no | (localhost-only uvicorn; no RBAC model) |
| V5 Input Validation | **yes** | `OrientedBox3D.from_wire()` validates shapes + qw sign + required keys; `SelectRequest`/`ParamPatch` use pydantic which rejects malformed bodies; `msgpack.unpackb(raw=False, strict_map_key=True)` on subprocess bridge ingress |
| V6 Cryptography | no | (no secrets on the wire) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed WebSocket JSON from client | Tampering | `_dispatch_ws_message` already catches `JSONDecodeError` (`server.py:191`); `detector_param_update` handler must validate `param in schema_props` before apply (mirror of SLAM handler `server.py:132-151`) |
| Malformed msgpack from subprocess worker | Tampering | `msgpack.unpackb(..., raw=False, strict_map_key=True)` on bridge ingress (research PITFALLS.md §Security Mistakes, line 634). SLAM bridge uses `raw=True` — Phase 2 can upgrade to `raw=False, strict_map_key=True` for detector bridge since we control both ends. |
| IPC socket file squat/symlink attack in `/tmp` | Tampering | `ipc:///tmp/detector_bridge_{pid}_{id}` with `pid + id(self)` uniqueness + `os.unlink` cleanup. PID uniqueness means another user's process cannot pre-create the path; `id(self)` ensures in-process uniqueness. Not a hardened defense, but adequate for localhost-only dev tool. |
| REST `POST /api/detectors/select` with arbitrary backend string | Tampering | Handler validates `req.backend in backends` BEFORE writing to app.state (D-02 clone). Invalid name → 404. |
| Subprocess worker exposed beyond localhost | Information disclosure | `ipc://` is filesystem-scoped (file perms, not network); subprocess bridge cannot be reached from outside the host by construction. |

**Unchanged from Phase 1's threat model** — Phase 2 adds no new external attack surface; new routes are still localhost-only.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Shared single `ObjectDetector._run_loop` thread draining all robots | Per-robot `DetectorWorker` thread with single-slot newest-wins queue | Phase 2 (this phase) | Per-robot backpressure isolation; per-robot backend support (Phase 8 stretch); correct `capture_pose` freshness under slow backends |
| `detections` WS payload: `{class, confidence, bbox, pos_3d, depth}` (flat list) | `detections_3d` envelope: `{items: [...], capture_pose, capture_timestamp, image_hw, metrics}` | Phase 2 (D-18) | Frontend can back-project in server-frame without re-reading intrinsics; captures stale-pose-on-slow-detector bug |
| Frontend derives 3D box size from `bbox_px × depth / focal` with hardcoded 70° FOV | Frontend renders `(center, half_extents, quaternion)` verbatim | Phase 2 adds the shape; Phase 4 deletes the legacy derivation | Honest geometry; unlocks real oriented boxes in Phase 4 |
| Inline `"quaternion":` construction in WS emitters | Single call site: `OrientedBox3D.to_wire()` | Phase 2 (D-10, grep invariant) | Prevents two backends diverging on quaternion order; enforced by test |
| ZMQ PAIR socket shared between SLAM + detector subsystems | Separate `SubprocessDetectorBridge` class + endpoint | Phase 2 (D-16) | Blast-radius isolation; one subsystem crash doesn't take the other down |

**Deprecated/outdated after Phase 2:**
- `src/perception/detector.py::ObjectDetector` — deleted (D-19)
- `src/perception/detection_3d.py::project_detections_to_3d` — deleted (D-19)
- `frontend/src/components/DetectionBoxes.ts` FOV + intrinsic-derivation code paths (lines 81-90) — replaced in-place (full deletion is Phase 4 DET-3D-05)
- `"detections"` WS message type literal — removed from `frontend/src/utils/messageTypes.ts`

---

## Thread-Safety Map (specific open-question answer)

Open question 1 answered in detail:

| Object | Thread-safe to share? | Source | Phase 2 usage |
|--------|----------------------|--------|---------------|
| `zmq.Context` | **YES** across threads; **NO** during `ctx.term()` | pyzmq docs | Each `SubprocessDetectorBridge` instance owns its own Context; never shared across bridge instances (D-16) |
| `zmq.Socket` | **NO** — per-thread ownership required | pyzmq docs | Each bridge's socket is owned exclusively by the calling thread (the DetectorWorker thread). No separate receiver thread. |
| `send_multipart` / `recv_multipart` | Must run on owning thread | pyzmq docs | Called inside `SubprocessDetectorBridge.send_frame` — called from worker thread only |
| `msgpack.packb` / `unpackb` | Pure function, thread-safe | msgpack docs | Called inside bridge send/recv on worker thread |
| `torch.Tensor` read-only | Thread-safe for concurrent reads | torch docs | Model parameters are frozen via `requires_grad_(False)` in `TorchBackendMixin`; each worker has its own model instance (pool constructs N instances) |
| `torch.inference_mode()` context | Per-thread state | torch docs | Entered inside `DetectorWorker._loop` on that thread |
| oneDNN intra-op thread pool | Process-global, shared | torch docs | Intentional — see Pitfall 1. Not a correctness issue; a throughput-math issue. |
| `threading.Lock` (worker `_lock`) | Per-instance, protects `_pending` + `_latest` | stdlib | Used for every `submit`/`latest`/`inspect` call |
| `app.state` attribute access | Atomic for simple assignment; no lock across read-modify-write | CPython + FastAPI conventions | Handler assigns `pending_detector_backend = X`; sim loop reads + nulls out. Race exists if two /select calls fire simultaneously — matches SLAM precedent; accepted (Pitfall 5). |

**Per-worker model instance question:** Phase 2 constructs ONE `YOLOv11Backend` instance per worker (not a shared model). Memory cost: ~60 MB per instance (YOLOv11-nano weights) × N_robots = 120 MB for 2 robots. Acceptable. Rationale: (a) thread-safety is moot because only one thread reads each instance; (b) `reset()` state (`self._timings` deque) is per-robot, not global; (c) per-robot `apply_params()` (if ever needed per robot in future) requires instance separation. The SLAM pool does the same — one `ICPBackend` per robot.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `[ASSUMED]` `RobotInstance.get_pose()` returns a fresh ndarray copy, not a cached array mutated in-place | Pitfall 4 | If wrong, `capture_pose` snapshot is corrupted. Mitigation already specified: worker does `.copy()` defensively. **Low risk — defensively handled regardless.** |
| A2 | `[ASSUMED]` MuJoCo `office1` scene contains a visible chair at the default spawn position + 10 settle steps that YOLOv11 classifies with score≥0.5 | Pitfall 7, W-01 | If wrong, W-01 fix requires selecting a different scene or modifying spawn/step count. The Phase 1 fixture generator uses 10 settle steps; a chair IS present in `data/scenes/scene_office1` per the scene mount in `backend/web/server.py:79`. **Low-to-medium risk — planner should verify at fixture regeneration time.** |
| A3 | `[ASSUMED]` pyzmq 27.1's `LINGER=0` + `close()` + `ctx.term()` pattern from SLAM bridge is still the correct cleanup on current pyzmq | Anti-Patterns, SubprocessDetectorBridge | `[VERIFIED: pyzmq 27.1 docs]` confirm LINGER=0 semantics unchanged. **No risk.** |
| A4 | `[ASSUMED]` Three.js `Matrix4.fromArray(flat16)` consuming a numpy `.reshape(-1).tolist()` row-major array renders correctly given the rest of argus uses this convention | Pattern 2, D-14 | If wrong, 3D boxes render transposed/mirrored. **Low risk — SLAM pose emission already uses this exact convention (`pose[:3,:3].flatten().tolist()`) and SLAM boxes render correctly.** Phase 2 re-uses that flatten. |
| A5 | `[ASSUMED]` `command_callback({"action":"restart"})` is idempotent across 2 concurrent subsystem triggers (e.g., user switches SLAM backend AND detector backend within 100ms) | Pattern 5, restart block | The SLAM code path reads `pending_slam_backend` AND `pending_merger` AND `pending_pipeline_config` in one restart; adding `pending_detector_backend` to the same read sequence is consistent. Two back-to-back restarts are serialized by `_restart_lock`. **Low risk — existing pattern.** |
| A6 | `[ASSUMED]` The W-02 `_clean_registries` fix (re-popping sys.modules after clear) does not break `test_registry_module_does_not_import_heavy_deps` which EXPLICITLY checks that importing `src.perception.registry` does NOT pull torch/ultralytics into sys.modules | W-02, test_registry.py:55-73 | The registry module itself does not import heavy deps (Pitfall P9 contract). Re-popping `src.perception.backends` then re-importing WILL pull ultralytics via `yolov11_backend.py:148`'s lazy `from ultralytics import YOLO`. Wait — the `yolov11_backend` lazy import happens inside `YOLOv11Backend.__init__`, NOT at module top. Module-top imports in `yolov11_backend.py:22-35` pull numpy, protocol, registry, types — none of which are heavy. **`_assert_indoor_classes_drift_guard()` at module top ALSO attempts `from src.perception.detector import ObjectDetector`** (line 63) which transitively pulls torch + ultralytics IF detector.py is still present. After D-19 deletion of `detector.py`, this guard short-circuits (ImportError → skip). **Before deletion (waves 1-3), re-popping + re-importing backends WILL pull torch — but only if `src.perception.detector` is already in sys.modules, which it may or may not be depending on test order.** Safest: re-pop in `_clean_registries` should be ordered LAST in the teardown so the next test starts with a clean slate, and should NOT re-import — let the next test's explicit `import src.perception.backends` line (if any) trigger registration. **Recommended refinement:** `_clean_registries` clears + yields + clears + pops sys.modules entries without re-importing; tests that need registration re-trigger it explicitly. **Medium risk — W-02 fix needs a follow-up verification test: full-suite pass.** |
| A7 | `[ASSUMED]` `bridge.get_last_frame(rid)` exists on `MultiRobotBridge`; if not, restart warmup needs a synthesized frame | Pattern 5 main.py restart | The bridge API surface isn't specified in the files read. **Medium risk — planner should verify; synthesized 480×640 zero-frame is a valid fallback for warmup (worst case: oneDNN caches a zero-frame kernel that's close-enough to the real-frame kernel on the next real call).** |

**Items needing user confirmation before locking:** A2 (W-01 fixture scene content), A7 (`bridge.get_last_frame` API existence). A6 is a verification item for the planner, not a user-decision item.

---

## Open Questions

1. **CameraFeed 2D RGB bbox overlay during Phase 2.**
   - What we know: D-18 cuts over `"detections"` → `"detections_3d"` immediately; the 2D bbox overlay in `CameraFeed.tsx:122` currently consumes `{bbox, class, confidence}` from the legacy shape.
   - What's unclear: should Phase 2 preserve the 2D overlay by adding an optional `bbox_xyxy` field to each `OrientedBox3D.to_wire()` item, or let the overlay go dark until Phase 3 (DET-UI-05)?
   - Recommendation: **add `bbox_xyxy: tuple[int,int,int,int] | None` to `OrientedBox3D` dataclass + optional wire emission.** Lowest-regression path; Phase 3 can then polish the overlay without a second cutover. Phase 2 worker threads populate it from the source `Detection2D.bbox_xyxy` at lift time.

2. **`pending_detector_params` live-tunable vs restart-required handling on PATCH.**
   - What we know: SLAM's `PATCH /api/slam/params` reads `live_tunable` from schema, applies-immediately when true, buffers for next restart when false. Phase 2 clones this.
   - What's unclear: `YOLOv11Backend.PARAMETER_SCHEMA` has `live_tunable: True` on all three params (confidence, min_bbox_size_px, class_filter) — so there's no `requires_restart` path to test in Phase 2. Does the test suite need a synthetic backend with a `requires_restart` param to exercise that branch?
   - Recommendation: yes — add a mock backend in `tests/perception/test_detector_routes.py` with one `live_tunable: False` param; exercise both branches. Keeps the live-tunable/restart-required semantics locked before Phase 5 ships a second real backend.

3. **Does the restart block use the pool's prior-backend as a warm-start for the new pool's first warmup?**
   - What we know: D-03 says warmup runs before `detector_restart_complete` fires. Dummy frame source is the last captured real frame.
   - What's unclear: when `main.py`'s restart block runs, has the bridge captured a frame yet? On the FIRST ever startup (not a restart), there's no prior frame — warmup on a zero-frame is the fallback.
   - Recommendation: `warmup_all` accepts either a dict of real frames OR a "synthesize zero frame" flag. On restart-after-activity: real frames. On first startup: synthesized 480×640 zeros. Explicit in the pool API, not magic.

4. **Phase 6 MetricsPanel coupling — does Phase 2 need to emit the drop counter as a WS metric right now?**
   - What we know: `inspect_worker_queues()` is exposed but Phase 2's WS messages don't include it. Phase 6 (DET-METRICS-01) formalizes the MetricsPanel surface.
   - What's unclear: should Phase 2 wire the inspect output into the `STATS` WS message (`streaming_viz._update_stats`) as a backend-metrics subsection, or wait for Phase 6?
   - Recommendation: **wait for Phase 6.** Phase 2's success criterion #3 says "verified via `inspect_worker_queues()` and logged queue-drop counter" — testing via the method call is sufficient; WS exposure is Phase 6's scope.

---

## Wave Plan Recommendation

**Wave 1 — OBB Wire Format (no worker deps, landable standalone)**
- Task 1.1: Extend `src/perception/types.py::OrientedBox3D` with `to_wire()` + `from_wire()` + optional `bbox_xyxy` field. Extend `Detections3D` with `capture_pose` + `capture_timestamp` + `to_wire()`.
- Task 1.2: `tests/perception/test_obb_round_trip.py` — 1000-OBB + 7 edge cases + negative-qw rejection.
- Task 1.3: `tests/perception/test_no_inline_quaternion.py` — grep invariant D-10.
- Files: 1 modified (`types.py`), 2 new tests.

**Wave 2 — Worker + Pool (depends Wave 1's Detections3D envelope)**
- Task 2.1: `src/perception/worker.py::DetectorWorker`.
- Task 2.2: `src/perception/worker_pool.py::DetectorWorkerPool`.
- Task 2.3: `tests/perception/test_worker_backpressure.py` + `test_worker_capture_pose.py`.
- Files: 2 new, 2 new tests. No conflict with Wave 3 (different directories).

**Wave 3 — Subprocess Bridge + Echo Worker (parallel to Wave 2)**
- Task 3.1: `src/perception/subprocess_bridge.py::SubprocessDetectorBridge` (clone of `src/slam/backends/subprocess_bridge.py` with D-16 endpoint + Phase 2 reply schema).
- Task 3.2: `scripts/echo_detector_worker.py`.
- Task 3.3: `tests/perception/test_subprocess_bridge.py` — D-17 coverage.
- Files: 2 new scripts, 1 new test. Parallel-safe with Wave 2 (separate directory tree; no shared file edits).

**Wave 4 — Integration Cutover (single-committed sequence; tight ordering required)**
- Task 4.1: `backend/web/detector_routes.py` + `backend/web/server.py` wiring (app.state init + `include_router` + `detector_param_update` WS dispatch).
- Task 4.2: `backend/web/message_types.py` + `backend/web/streaming_viz.py` (emitter swap).
- Task 4.3: `src/main.py` restart block extension (detector warmup + `detector_restart_complete` emission).
- Task 4.4: `src/coordination/coordinator.py` — `ObjectDetector` → `DetectorWorkerPool` rewire.
- Task 4.5: Delete `src/perception/detector.py` + `src/perception/detection_3d.py` (D-19).
- Task 4.6: Frontend — `frontend/src/utils/messageTypes.ts` (new literals) + `frontend/src/hooks/useWebSocket.ts` (new cases, subsystem-aware crash_fallback) + `frontend/src/stores/robotStore.ts` (Detection type replaced) + `frontend/src/components/DetectionBoxes.ts` (updateDetections signature) + `frontend/src/components/SceneViewer.tsx` (pass new shape) + `frontend/src/components/CameraFeed.tsx` + `frontend/src/components/RobotCard.tsx`.
- Task 4.7: W-01 fixture regeneration — update `tests/fixtures/generate_yolo_regression_fixture.py` to assert ≥1 detection; rebuild `yolo_regression_scene_01.npz`.
- Task 4.8: W-02 registry fixture fix — update `tests/perception/test_registry.py::_clean_registries`.
- Task 4.9: Delete `tests/perception/test_yolov11_regression.py` (ObjectDetector gone); replace with `tests/integration/test_pool_end_to_end.py` proving pool.submit() → latest() produces same dets as YOLOv11Backend.process_frame().
- Task 4.10: `tests/perception/test_detector_routes.py` — REST round-trip.
- Files: ~15 modified, 2 deleted, 2 new tests. **High merge-conflict wave — must land as one sequence.**

**Wave dependencies:** 1 before 2, 1 before 3, 2 and 3 parallel, everything before 4.

**Estimated plan count:** 4 waves × ~3 plans each = ~10-12 plans. Wave 4 is the densest at ~4-5 plans because of the cutover breadth.

---

## Sources

### Primary (HIGH confidence)

- In-tree files read verbatim (HIGH confidence, 2026-04-14):
  - `src/slam/backends/subprocess_bridge.py` — template for SubprocessDetectorBridge (200 lines)
  - `src/slam/registry.py` — template pattern for registries
  - `backend/web/slam_routes.py` — template for detector_routes.py (176 lines)
  - `src/main.py:1-100, 420-529` — thread_config import pattern, restart extension block
  - `src/perception/protocol.py` — locked DetectorProtocol/Detection3DProtocol/TorchBackendMixin
  - `src/perception/types.py` — OrientedBox3D skeleton + Detections3D Phase 1 shape
  - `src/perception/registry.py` — DetectorRegistry/Detection3DRegistry with CAPABILITIES validation
  - `src/perception/backends/yolov11_backend.py` — production YOLOv11Backend
  - `src/perception/lifters/median_depth.py` — production MedianDepthLifter
  - `src/_thread_config.py` — process-global thread budget
  - `src/coordination/coordinator.py:1-170, 620-700` — ObjectDetector ownership + viz update hot path
  - `backend/web/server.py` — app.state scaffolding + WS dispatch
  - `backend/web/streaming_viz.py:284-360` — legacy `detections` emitter
  - `backend/web/message_types.py` — WS constants module
  - `frontend/src/components/DetectionBoxes.ts` — legacy DetectionBoxManager
  - `frontend/src/components/CameraFeed.tsx` — 2D RGB overlay consumer
  - `frontend/src/stores/robotStore.ts` — Detection type + store
  - `frontend/src/hooks/useWebSocket.ts:129-177` — current WS case dispatch
  - `frontend/src/utils/messageTypes.ts` — WSMessage union type
  - `src/exploration/exploration_loop.py:200-232` — existing crash_fallback SLAM emitter
  - `src/perception/detector.py` (to-be-deleted) + `src/perception/detection_3d.py` (to-be-deleted)
  - `tests/fixtures/generate_yolo_regression_fixture.py` + `yolo_regression_scene_01.npz`
  - `tests/perception/test_yolov11_regression.py` + `test_registry.py` + `test_protocol_contracts.py`
  - `pyproject.toml` — pinned deps (scipy ≥1.15, pyzmq ≥26, msgpack ≥1.0, numpy ≥1.26)
  - `.planning/config.json` — nyquist_validation enabled
- Locked context: `.planning/phases/02-per-robot-worker-and-wire-plumbing/02-CONTEXT.md` (D-01..D-19)
- Locked context: `.planning/phases/01-detector-api-foundation/01-CONTEXT.md` (D-01..D-14 carry-over invariants)
- Research: `.planning/research/ARCHITECTURE.md` §Answer to Q5, §Answer to Q7 (Threading Model, Coordinator Orchestration), §Subprocess Protocol, §Anti-Patterns
- Research: `.planning/research/PITFALLS.md` P5, P8, P10, P13, P19 (OBB parameterization, stale pose, GIL serialization, WS payload budget, module-scope thread set)
- Research: `.planning/research/STACK.md` — no new deps needed for Phase 2

### Secondary (MEDIUM confidence — docs cross-referenced with installed versions)

- [pyzmq 27.x documentation — zmq module](https://pyzmq.readthedocs.io/en/latest/api/zmq.html) — Context thread-safety semantics; Socket NOT thread-safe; `LINGER` and `close()` behavior
- [pyzmq — More Than Just Bindings (threading)](https://pyzmq.readthedocs.io/en/v17.1.0/morethanbindings.html) — per-thread socket creation rule
- [PyTorch 2.10 docs — CPU threading and TorchScript inference](https://docs.pytorch.org/docs/stable/notes/cpu_threading_torchscript_inference.html) — oneDNN intra-op pool is process-global; `torch.set_num_threads` sets intra-op, `torch.set_num_interop_threads` sets inter-op
- [torch.inference_mode documentation](https://docs.pytorch.org/docs/stable/generated/torch.autograd.grad_mode.inference_mode.html) — disables autograd view-tracking; faster than `no_grad` by avoiding version counter bumps; releases GIL inside C++ kernels but does not remove the shared oneDNN thread-pool bottleneck
- [scipy.spatial.transform.Rotation.random](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.random.html) — Haar-uniform sampling; `rng` kwarg accepts `np.random.default_rng(seed)` for determinism (scipy ≥1.15)
- [FastAPI — Concurrency and async/await](https://fastapi.tiangolo.com/async/) — sync handlers run in threadpool; `app.state` is shared mutable state; racing writes must be synchronized externally if read-modify-write is needed

### Tertiary (flagged but verified in-tree)

- [pyzmq issue #832 (2020)](https://github.com/zeromq/pyzmq/issues/832) — asyncio IPC LINGER flush corner case (NOT applicable to our sync bridge; informational only)
- [pyzmq issue #1605 (2021)](https://github.com/zeromq/pyzmq/issues/1605) — asyncio fd leak (NOT applicable to our sync bridge)

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — all deps pre-installed and version-verified in `.venv`; no new pins needed
- Architecture: **HIGH** — every component has a 1:1 in-tree template (SLAM bridge, SLAM routes, SLAM restart block); CONTEXT.md D-01..D-19 lock the design; research ARCHITECTURE.md Q5+Q7 already specified the worker threading model verbatim
- Pitfalls: **HIGH** — `PITFALLS.md` catalog already identified P5/P8/P10/P13/P19; Phase 2 consumes the listed mitigations; new pitfalls surfaced (warmup dummy-frame resolution mismatch, W-01 tautology, W-02 sys.modules pollution, CameraFeed signature break) are specific to this phase's execution

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (pyzmq/scipy/torch pins stable at this cadence; if torch/ultralytics bumps a major version before Phase 2 lands, re-verify `torch.inference_mode` + oneDNN behavior)
