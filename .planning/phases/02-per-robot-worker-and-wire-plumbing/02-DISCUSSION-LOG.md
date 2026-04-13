# Phase 2: per-robot-worker-and-wire-plumbing - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-13
**Phase:** 02-per-robot-worker-and-wire-plumbing
**Areas discussed:** Worker pool lifecycle + restart, OBB wire format details, capture_pose + capture_timestamp, Subprocess skeleton + legacy cutover

---

## Worker Pool Lifecycle + Restart

### Q: Where does DetectorWorkerPool live?

| Option | Description | Selected |
|--------|-------------|----------|
| Coordinator attr | `self._detector_pool`; mirrors current `self._detector: ObjectDetector`. Dies with coordinator restart. | ✓ |
| app.state (FastAPI-level) | Persists across coordinator restarts; pool swaps backends independently. | |
| Module-level singleton | `src/perception/worker_pool.py::POOL`. Hidden global state. | |

**User's choice:** Coordinator attr
**Notes:** Consistent with SLAM; pool lifecycle tied to coordinator restart already covers Phase 2 needs.

---

### Q: How does POST /api/detectors/select trigger backend swap?

| Option | Description | Selected |
|--------|-------------|----------|
| Full coordinator restart | Exact SLAM pattern: pending_detector_backend → command_cb({"action":"restart"}) → main.py rebuilds. | ✓ |
| Surgical pool.swap_backend() | Pool kills workers + constructs new backend without coordinator restart. | |
| Hybrid (full for family cross, swap within) | Two codepaths. | |

**User's choice:** Full coordinator restart
**Notes:** Mirrors SLAM; reuses restart overlay; low-risk.

---

### Q: When does `detector_restart_complete` WS message fire?

| Option | Description | Selected |
|--------|-------------|----------|
| After pool rebuilt + warmup() succeeds | UI overlay stays through warmup; locks DET-UI-04 at protocol layer. | ✓ |
| After pool rebuilt only | Warmup lazy; first frame slow; UI reports ready early. | |
| Two messages (restart_complete + warmup_complete) | Split signal; finer frontend states. | |

**User's choice:** After pool rebuilt + warmup() succeeds
**Notes:** Prevents first-frame stall visible to user; DET-UI-04 satisfied structurally.

---

## OBB Wire Format Details

### Q: How should OrientedBox3D.to_wire() enforce qw >= 0?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-flip in to_wire | qw<0 → negate entire quaternion. Wire invariant held silently. from_wire asserts qw>=0. | ✓ |
| Raise ValueError | Strict; caller must normalize. | |
| Warn + flip | Log on every flip. | |

**User's choice:** Auto-flip in to_wire
**Notes:** Backend authors don't need to know about qw invariant; to_wire is the enforcement point.

---

### Q: Default `track_id` when no tracker is active?

| Option | Description | Selected |
|--------|-------------|----------|
| Omit key entirely | Present only when set. Frontend reads absence as untracked. | ✓ |
| `track_id: null` always | Key always present, value None. | |
| `track_id: -1` sentinel | Non-null sentinel. | |

**User's choice:** Omit key entirely
**Notes:** Null-free wire schema; clean "tracker attached or not" semantics.

---

### Q: How is detections_3d encoded over the WebSocket?

| Option | Description | Selected |
|--------|-------------|----------|
| JSON (plain floats) | Matches rest of WS; double precision meets ±1e-6; 10-20 dets/robot tiny. | ✓ |
| msgpack binary | Smaller; faster parse; requires frontend msgpack. | |
| JSON with base64 float arrays | Compact; loses human-readability. | |

**User's choice:** JSON (plain floats)
**Notes:** Consistency with SLAM/stats messages; revisit only if profiling demands it.

---

### Q: OrientedBox3D.to_wire() dict key order / shape?

| Option | Description | Selected |
|--------|-------------|----------|
| Flat dict in research-doc order | `{center, half_extents, quaternion, class_id, class_name, score, track_id?}`. | ✓ |
| Nested geometry + metadata sub-dicts | Two-level access on frontend. | |

**User's choice:** Flat dict
**Notes:** Mirrors research ARCHITECTURE.md line 507 exactly.

---

## capture_pose + capture_timestamp

### Q: Where do capture_pose + capture_timestamp live?

| Option | Description | Selected |
|--------|-------------|----------|
| Detections3D envelope, not per-box | Envelope-level fields; single per-frame copy. | ✓ |
| Per-box on every OrientedBox3D | Wasteful but simpler box-by-box dispatch. | |
| On Detections2D AND Detections3D | Available at both stages; more bookkeeping. | |

**User's choice:** Detections3D envelope
**Notes:** Semantically correct — one frame produces N boxes sharing one pose.

---

### Q: Source of `capture_timestamp`?

| Option | Description | Selected |
|--------|-------------|----------|
| frame.sim_time at submit() | SensorFrame already carries it; Phase 6 freshness = sim_now - capture_timestamp. | ✓ |
| time.monotonic() at submit | Wall clock. | |
| Both sim_time + wall_time | Two fields. | |

**User's choice:** frame.sim_time at DetectorWorker.submit()
**Notes:** Matches DET-METRICS-01 freshness semantics.

---

### Q: When is `capture_pose` captured relative to inference?

| Option | Description | Selected |
|--------|-------------|----------|
| At pool.submit() — snapshot current pose | Coordinator reads robot.get_pose(); worker stores. No pose drift during inference. | ✓ |
| At lift-time | Pose drifts during inference latency; defeats DET-API-05. | |
| Both on payload | capture_pose + lift_pose. | |

**User's choice:** At pool.submit() — snapshot current pose
**Notes:** Locks DET-API-05 semantics; no stale-pose trap.

---

### Q: Wire serialization for capture_pose (4x4)?

| Option | Description | Selected |
|--------|-------------|----------|
| Flat 16-float list, row-major | Matches THREE.Matrix4.fromArray(); JSON-compact. | ✓ |
| Nested 4x4 list | Human-readable; needs flattening on frontend. | |
| Decomposed: position[3] + quaternion[4] | Saves 9 floats; imposes rigid-body interpretation. | |

**User's choice:** Flat 16-float list, row-major
**Notes:** Frontend Three.js consumes directly; no reshape step.

---

## Subprocess Skeleton + Legacy Cutover

### Q: How is the dummy echo worker implemented for the handshake test?

| Option | Description | Selected |
|--------|-------------|----------|
| scripts/echo_detector_worker.py standalone | Permanent helper; reusable for Phase 5 BoxeR dev. | ✓ |
| Inline fixture subprocess in test file | Inline Python-c string. | |
| tests/fixtures/echo_detector_worker.py | Test-only. | |

**User's choice:** scripts/echo_detector_worker.py standalone
**Notes:** Reusable as Phase 5 dev harness; easier to debug.

---

### Q: Should legacy `"detections"` WS message coexist with new `"detections_3d"`?

| Option | Description | Selected |
|--------|-------------|----------|
| Cut over — replace immediately | Phase 2 emits only detections_3d. Frontend DetectionBoxManager updated same phase. | ✓ |
| Coexist one release | Dual-emit; safer for external consumers. | |
| Gate via env flag | Rollback lever. | |

**User's choice:** Cut over — replace immediately
**Notes:** Single-app, no external consumers; dead code buildup has no upside.

---

### Q: What happens to src/perception/detector.py::ObjectDetector at end of Phase 2?

| Option | Description | Selected |
|--------|-------------|----------|
| Delete class + file | Clean slate; INDOOR_CLASSES lives only in YOLOv11Backend; detection_3d.py shim also removed. | ✓ |
| Leave file with NotImplementedError stub | Catches lingering imports. | |
| Keep file, mark deprecated | Dangerous — invites reuse. | |

**User's choice:** Delete class + file
**Notes:** Phase 1 runtime-assert guard on INDOOR_CLASSES drift still applies across the single remaining call site.

---

### Q: Does SubprocessDetectorBridge get its own ZMQ endpoint pattern?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — ipc:///tmp/detector_bridge_<pid>_<id> | Blast-radius isolation from SLAM. | ✓ |
| Share SLAM bridge endpoint pattern | Couples failure domains. | |

**User's choice:** Yes — own endpoint pattern
**Notes:** Locks research ARCHITECTURE.md anti-pattern rejection.

---

## Claude's Discretion

- `DetectorWorkerPool` class surface (method names, signatures)
- Per-worker backpressure `drops_since_last_poll` counter reset semantics
- `crash_fallback` WS message `subsystem` field addition pattern
- Live-tunable vs restart-required split for PATCH `/api/detectors/params`
- `OrientedBox3D.from_wire()` input validation strictness
- 1000-randomized-OBB round-trip test RNG seed

## Deferred Ideas

- Surgical `pool.swap_backend()` without full coordinator restart — deferred to Phase 7 (pipeline-editor DET-PIPELINE-05)
- Per-robot backend dispatch — Phase 8 stretch (DET-STRETCH-04)
- `"detections"` legacy dual-emit — rejected
- msgpack binary WS encoding — deferred past Phase 5 profiling
- Crash-fallback auto-switch to YOLO — Phase 5 (DET-MODELS-06)
- Frontend `detectorStore` (Zustand) — Phase 3 (DET-UI-06)
