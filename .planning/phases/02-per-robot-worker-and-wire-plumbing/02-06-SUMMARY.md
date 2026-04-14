---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 06
subsystem: perception
tags: [perception, subprocess, zmq, msgpack, ipc, bridge]

requires:
  - phase: 01-detector-api-foundation
    provides: "Detections2D/3D types and detector protocol contract (imported by Phase 5 BoxeR backend, NOT by this skeleton)."
provides:
  - "SubprocessDetectorBridge class skeleton — ZMQ PAIR + msgpack multipart transport over ipc:///tmp/detector_bridge_<pid>_<id>"
  - "Locked transport invariants: HANG_TIMEOUT_MS=5000, LINGER=0, hardened msgpack ingress (raw=False, strict_map_key=True)"
  - "D-17 reply schema skeleton: raw dict {ts, inference_ms, n_det, classes, scores, bboxes} returned to caller"
  - "Cleanup contract: _kill_process → close socket → term context → os.unlink IPC file (Pitfall 3 defended)"
affects:
  - 02-07-echo-worker-and-handshake-test
  - phase-5-det-models-boxer-backend

tech-stack:
  added: []
  patterns:
    - "Structural clone (not inheritance) for subsystem-isolated subprocess bridges"
    - "Hardened msgpack ingress when both bridge ends are owned by the project"

key-files:
  created:
    - "src/perception/subprocess_bridge.py"
    - "tests/perception/test_subprocess_bridge_skeleton.py"
  modified: []

key-decisions:
  - "Cloned src/slam/backends/subprocess_bridge.py structurally into src/perception/subprocess_bridge.py as a separate class per D-16 — no inheritance, no composition, no shared zmq.Context. Blast-radius isolation: a bug in one bridge cannot squat the other's socket file or hang its context teardown."
  - "Used ipc:///tmp/detector_bridge_<pid>_<id(self)> endpoint prefix (D-16). pid+id(self) uniqueness survives fork'd pytest processes and prevents in-process collisions between multiple bridge instances (verified by the two-instances-different-endpoints test)."
  - "Hardened msgpack ingress: msgpack.unpackb(raw=False, strict_map_key=True) — tighter than the SLAM bridge's raw=True legacy. Safe here because Phase 2 owns both ends of the detector bridge protocol; SLAM bridge must interop with existing C++ binaries that send bytes keys (T-02-12 mitigation)."
  - "Reply type is a raw dict[str, Any]. Phase 5 BoxeR backend parses classes/scores/bboxes into concrete detection dataclasses — transport layer is detection-type-agnostic (Plan 02-06 deliberately imports neither torch nor ultralytics nor src.perception.types)."
  - "send_frame returns None on every failure path (hang, crash, ZMQ error, unexpected exception), all funneled through _kill_process. Bridge can never be left in a half-alive state (T-02-14 mitigation)."

patterns-established:
  - "Subsystem-isolated subprocess bridges: each subsystem (SLAM, perception) owns its own SubprocessXBridge class with its own endpoint namespace — structural clone, not OOP hierarchy"
  - "Phase-scoped msgpack hardening: tighten ingress (raw=False, strict_map_key=True) when both ends are project-owned; relax when interoping with external binaries"
  - "Cleanup-on-any-failure: every exception path in transport layer goes through _kill_process → _cleanup → os.unlink, so no leaked /tmp sockets regardless of failure mode"

requirements-completed: [DET-MODELS-05]

duration: 8 min
completed: 2026-04-14
---

# Phase 02 Plan 06: SubprocessDetectorBridge Skeleton Summary

**Standalone SubprocessDetectorBridge class — ZMQ PAIR + msgpack multipart transport over ipc:///tmp/detector_bridge_<pid>_<id>, hardened msgpack ingress, and the D-17 reply schema locked ready for Plan 02-07's handshake test.**

## Performance

- **Tasks:** 1 (TDD RED + GREEN)
- **Files created:** 2 (1 source, 1 test)
- **Files modified:** 0
- **Test result:** 17/17 passing
- **Source module:** 264 lines (exceeds must_haves min_lines=180)

## Accomplishments

- `SubprocessDetectorBridge` class in `src/perception/subprocess_bridge.py` — structural clone of `SubprocessSLAMBridge` with zero inheritance coupling (D-16 blast-radius isolation locked in)
- Transport invariants locked: `HANG_TIMEOUT_MS = 5000`, `LINGER = 0`, `RCVTIMEO` set before bind, `zmq.Again` path flips `_alive` to `False` and kills the subprocess
- Hardened msgpack ingress: `msgpack.unpackb(raw=False, strict_map_key=True)` — rejects non-string map keys and auto-decodes bytes values (T-02-12 mitigation)
- D-17 reply schema contract: raw dict `{ts, inference_ms, n_det, classes, scores, bboxes}` returned to caller; Phase 5 BoxeR backend will parse the detection list (transport layer stays type-agnostic)
- Cleanup-on-any-failure funnel: hang, crash, ZMQ error, or unexpected exception → `_kill_process` → close socket → `ctx.term()` → `os.unlink(ipc_path)` (T-02-15 mitigation, Pitfall 3 defended)
- Smoke-level test coverage (17 tests) proving: class separation (D-16), endpoint prefix correctness, per-instance endpoint uniqueness, `HANG_TIMEOUT_MS` constant, initial `_alive = False`, pre-start `send_frame`/`shutdown` safety, and API-surface completeness

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1 RED: Failing smoke tests for SubprocessDetectorBridge skeleton** — `5646ce3` (test)
2. **Task 1 GREEN: Implement SubprocessDetectorBridge (D-16, D-17)** — `6b8b753` (feat)

No refactor step — implementation went green on first pass with no cleanup needed.

## Files Created/Modified

- `src/perception/subprocess_bridge.py` — `SubprocessDetectorBridge` class (264 lines). Public surface: `__init__`, `alive` property, `endpoint` property, `start()`, `send_frame(rgb, depth, timestamp, params)`, `shutdown()`. Private teardown: `_kill_process()`, `_cleanup()`. Class constant: `HANG_TIMEOUT_MS = 5000`.
- `tests/perception/test_subprocess_bridge_skeleton.py` — 17 smoke tests across 5 test classes (D16ClassSeparation, EndpointPattern, ClassConstants, InitialState, APISurface). Real spawn/recv/kill/round-trip tests live in Plan 02-07 against the echo worker.

## Decisions Made

- **D-16 enforcement via structural clone, not subclass or composition** — copying `SubprocessSLAMBridge`'s shape into a sibling class rather than sharing code guarantees that a future SLAM-bridge refactor cannot silently change detector-bridge semantics, and a detector-bridge bug cannot leak into SLAM. The blast-radius isolation rationale in RESEARCH.md explicitly rejected "reuse SLAM bridge" as a pitfall; this plan locks that rejection into the codebase.
- **Endpoint pattern `ipc:///tmp/detector_bridge_<pid>_<id(self)>`** — distinct prefix from SLAM's `slam_bridge_*`. Includes `id(self)` so two bridges inside the same Python process (e.g. one per robot in Phase 5) do not collide. `pid` guards against other users' processes pre-creating the path (T-02-13 mitigation).
- **Hardened msgpack ingress (`raw=False, strict_map_key=True`)** — tighter than SLAM bridge's legacy `raw=True`. Phase 2 controls both ends of the detector bridge (the bridge here, and `scripts/echo_detector_worker.py` in Plan 02-07, and the Phase 5 BoxeR worker). We do not need the `raw=True` escape hatch that SLAM needs for legacy C++ binaries. Broad `Exception` handler still falls through to `_kill_process` so a malformed reply cannot leave the bridge hung (T-02-12 mitigation).
- **Reply type is `dict[str, Any]` — no detection-type coupling** — the transport layer deliberately does not import `src.perception.types` or `torch` or `ultralytics`. Phase 5's BoxeR backend will wrap `send_frame` and parse classes/scores/bboxes into `OrientedBox3D` items. Keeping the transport generic means Plan 02-07's echo worker can use the same bridge with a zero-detection reply, no type gymnastics.
- **`depth` is Optional** — RGB-only detectors (OWLv2, BoxeR) will pass `depth=None` and the multipart frame will have 2 parts instead of 3. Header includes `depth_shape=None, depth_dtype=None` so the worker side always sees the same header schema.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `<action>` block in Task 1 specified the full module source inline; the implementation follows it closely with two strictly additive clarifications:

1. Module docstring expanded with explicit threading note (Pitfall 2 from success_criteria): "single thread owns socket; worker thread in Phase 5 will own this instance's socket exclusively." This is a documentation-only addition; no behavioural change.
2. Helper comments in `send_frame` and `_cleanup` annotate why hardening (`raw=False, strict_map_key=True`) and `LINGER=0` are safe here but not in the SLAM bridge. Documentation only.

Neither triggered a deviation rule because both were additive docstring/comment changes matching the plan's must_haves/truths.

**Total deviations:** 0
**Impact on plan:** None — implementation matches plan action block byte-for-byte on executable code.

## Issues Encountered

None. The `uv run pytest` invocation initially failed because pytest was not installed in the base `uv sync` — resolved by using `uv run --extra dev pytest`. This is environment-setup, not a code issue.

## Verification

Plan `<verification>` block:

- `uv run python -c "from src.perception.subprocess_bridge import SubprocessDetectorBridge; print(SubprocessDetectorBridge.HANG_TIMEOUT_MS)"` → **prints 5000** ✅
- Endpoint prefix is `ipc:///tmp/detector_bridge_` (NOT `ipc:///tmp/slam_bridge_`) ✅ (verified by `TestEndpointPattern.test_default_endpoint_has_detector_prefix` and `test_default_endpoint_does_not_collide_with_slam_prefix`)
- Plan 02-07's handshake test will exercise real spawn/send/recv/kill/cleanup against `scripts/echo_detector_worker.py` — deferred as designed

Plan `<success_criteria>`:

- [x] D-16 endpoint separation locked (separate class, separate endpoint prefix, own zmq.Context)
- [x] D-17 transport protocol skeleton ready for Plan 07 handshake test
- [x] Pitfall 2 (socket non-thread-safe) documented in class/module docstrings
- [x] Pitfall 3 (IPC file leak) defended by `os.unlink` in `_cleanup` (Plan 07 will test the cleanup path end-to-end)

Plan `must_haves/truths` — all 6 invariants satisfied:

- [x] Separate class from SubprocessSLAMBridge (not subclass), own `zmq.Context` per instance — `TestD16ClassSeparation` verifies both directions
- [x] Endpoint pattern `ipc:///tmp/detector_bridge_{os.getpid()}_{id(self)}` — `TestEndpointPattern.test_default_endpoint_includes_pid_and_id` verifies
- [x] `HANG_TIMEOUT_MS = 5000`, `LINGER = 0`, `strict_map_key=True` on `msgpack.unpackb` — `TestClassConstants` + source inspection
- [x] `send_frame(rgb, depth, timestamp, params)` returns dict on success, None on failure; `zmq.Again` → `_kill_process` → `_alive = False` — implementation matches, Plan 07 will end-to-end verify
- [x] `_cleanup()` closes socket, terminates context, `os.unlink`s the IPC file — implementation matches
- [x] Reply schema `{ts, inference_ms, n_det, classes, scores, bboxes}` with `raw=False, strict_map_key=True` — documented in module docstring; Plan 07 will round-trip verify via echo worker

## Next Phase Readiness

- Plan 02-07 (echo worker + handshake test) can now import `SubprocessDetectorBridge` from `src.perception.subprocess_bridge` and write `scripts/echo_detector_worker.py` against the D-17 reply schema
- Phase 5 DET-MODELS-03 (BoxeR backend) will compose this bridge — one instance per backend, NOT per robot
- No blockers

## Self-Check

- [x] `src/perception/subprocess_bridge.py` exists on disk (264 lines ≥ 180 min)
- [x] `tests/perception/test_subprocess_bridge_skeleton.py` exists on disk
- [x] Commit `5646ce3` present on branch (`test(02-06): add failing smoke tests`)
- [x] Commit `6b8b753` present on branch (`feat(02-06): implement SubprocessDetectorBridge skeleton`)
- [x] 17/17 smoke tests pass under `uv run --extra dev pytest`
- [x] Both plan `<verify>` one-liners succeed
- [x] No leaked `/tmp/detector_bridge_*` sockets after test run

## Self-Check: PASSED

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*
