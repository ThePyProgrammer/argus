---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 10
subsystem: coordinator
tags: [coordinator, streaming-viz, detector-pool, detections-3d, wire-protocol, d-18-cutover]

# Dependency graph
requires:
  - phase: 02-per-robot-worker-and-wire-plumbing
    provides: "Plan 02-01 Detections3D envelope + to_wire(); Plan 02-04 DetectorWorkerPool.submit/latest/shutdown; Plan 02-08 DETECTIONS_3D literal + router; Plan 02-09 main.py restart block attaches coordinator._detector_pool"
provides:
  - "Coordinator hot-loop rewired to DetectorWorkerPool — ObjectDetector usage removed from coordinator.py"
  - "RobotVizData.detections_3d: Detections3D | None (envelope) replaces detections: list[dict]"
  - "WS emitter emits DETECTIONS_3D envelope via Detections3D.to_wire(); legacy 'detections' message cut over (D-18)"
  - "Coordinator.detector property surfaces the pool (or None) — single detection surface"
  - "Coordinator.reset_for_restart shuts down prior pool before main.py attaches a new one"
affects: [02-11 (frontend envelope consumer), 02-12 (detector.py deletion + final fixups), phase-3, phase-6 MetricsPanel]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-18 immediate cutover — no dual-emit, no env flag, legacy 'detections' message deleted in same commit as new emitter"
    - "Envelope-level serialization — streaming_viz delegates to Detections3D.to_wire(); never constructs quaternion dicts inline (preserves D-10 grep invariant)"
    - "Coordinator as pool consumer, never constructor — main.py owns construction/warmup; coordinator owns reference + shutdown-before-reattach"

key-files:
  created: []
  modified:
    - "src/coordination/coordinator.py"
    - "backend/web/streaming_viz.py"
    - "src/mcp/server.py"

key-decisions:
  - "coordinator.detector property now returns the DetectorWorkerPool (not ObjectDetector). This preserves the old attribute name for call sites that read it polymorphically but changes the returned API. MCP server was the only such call site and was migrated in this plan."
  - "reset_for_restart calls _detector_pool.shutdown() BEFORE main.py attaches a new pool. Without this, old worker threads would leak across restarts. pool.shutdown is bounded at 2s per worker (DetectorWorkerPool contract from Plan 02-04)."
  - "DetectorWorkerPool import is lazy (TYPE_CHECKING only) — coordinator module stays torch-free per P9. Detections3D is module-scope (types.py is torch-free)."
  - "streaming_viz skips emission when detections_3d is None (pool not yet warm OR just rotated). Prior legacy path skipped on empty list — semantically equivalent."

patterns-established:
  - "Per-robot envelope wire format: streaming_viz emits {type: DETECTIONS_3D, robot_id, payload: to_wire()} per tick. Payload includes capture_pose + capture_timestamp so downstream consumers (Phase 3 frontend, Phase 6 MetricsPanel) see pose-at-capture."
  - "Coordinator treats _detector_pool as a black box — never constructs, never warms, only forwards submits and shuts down before handoff."

requirements-completed: [DET-API-04, DET-API-05, DET-3D-03]

# Metrics
duration: 22 min
completed: 2026-04-14
---

# Phase 2 Plan 10: Coordinator + streaming_viz Rewire Summary

**Coordinator hot-loop and WS emitter cut over from ObjectDetector + legacy `detections` list to DetectorWorkerPool + `DETECTIONS_3D` envelope in a single atomic rewire, closing the Phase 2 D-18 immediate-cutover contract.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-04-14T02:47:00Z
- **Completed:** 2026-04-14T03:09:00Z
- **Tasks:** 2
- **Files modified:** 3 (coordinator.py, streaming_viz.py, mcp/server.py)

## Accomplishments

- **Coordinator rewire:** `self._detector: ObjectDetector | None` replaced with `self._detector_pool: DetectorWorkerPool | None`; `__init__` no longer imports or constructs ObjectDetector. Main.py (Plan 02-09) now owns pool attachment post-reset.
- **Envelope field:** `RobotVizData.detections: list[dict]` removed; `detections_3d: Detections3D | None` added. Dict-style compatibility helpers (`__getitem__`, `get`, `__contains__`) preserved for downstream consumers.
- **Hot-loop cutover:** `_send_viz_update` replaces 15-line dict-building loop with `pool.submit(rid, frames[rid], pose, slam_cloud=None)` + `pool.latest(rid)`. Full SensorFrame passed (not rgb/depth split), matching Plan 02-04 API.
- **reset_for_restart:** prior `_detector_pool.shutdown()` guarded by try/except so main.py can attach a fresh pool cleanly — worker threads bounded 2s join per Plan 02-04.
- **WS emitter swap:** `backend/web/streaming_viz.py:337-344` legacy `"detections"` emission replaced with `DETECTIONS_3D` envelope via `Detections3D.to_wire()`. Payload is the full D-09 + D-14 flat-float dict (items + capture_pose + capture_timestamp + image_hw + metrics).
- **D-10 invariant preserved:** streaming_viz never constructs the `"quaternion":` literal inline — delegation to `to_wire()` keeps the grep check green.

## Task Commits

1. **Task 1: Rewire coordinator.py from ObjectDetector to DetectorWorkerPool** — `321315c` (feat)
2. **Task 2: Swap streaming_viz emitter to DETECTIONS_3D envelope** — `133ecd1` (feat)

## Files Created/Modified

- `src/coordination/coordinator.py` — RobotVizData.detections_3d field; `_detector_pool` attribute (no pool construction); `detector` property returns pool; `reset_for_restart` shuts down prior pool; `_send_viz_update` uses pool.submit/latest + assigns detections_3d on envelope.
- `backend/web/streaming_viz.py` — imports DETECTIONS_3D + Detections3D; emits envelope via `to_wire()`; legacy "detections" emission deleted (D-18).
- `src/mcp/server.py` — `get_detections` tool migrated from per-Detection dict list to envelope `to_wire()` output (Rule 3 blocking fix; see Deviations).

## Decisions Made

- **`Coordinator.detector` property kept but re-pointed at `_detector_pool`:** Plan spec said "remove or return None". Chose to return the pool so external polymorphic call sites (MCP) keep reading `.detector` without attribute-rename churn. Updated MCP in the same commit to use the pool API.
- **MCP `get_detections` returns envelope `to_wire()` instead of per-detection dict list:** MCP was the last external consumer of the legacy 2D-detection wire shape. Returning `to_wire()` gives MCP clients the Phase 2 3D schema directly; empty-list fallback preserved when pool is None.
- **Lazy DetectorWorkerPool import:** Module-scope import would pull worker_pool.py → workers with torch-potential code paths even though worker_pool.py itself is torch-free. TYPE_CHECKING-only reference keeps coordinator module torch-free per P9 (belt-and-suspenders).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migrated MCP `get_detections` tool to the new pool/envelope API**

- **Found during:** Task 1 (Coordinator rewire)
- **Issue:** `src/mcp/server.py:110-111` read `_coordinator.detector.get_detections(rid)` and iterated per-detection `d.class_name/d.confidence/d.bbox/d.center_3d`. After this plan, `coordinator.detector` returns the pool, which exposes `latest(rid) -> Detections3D | None` (envelope), not `get_detections()` (per-detection list). Leaving MCP unchanged would raise `AttributeError` on every `get_detections` tool call.
- **Fix:** Replaced per-Detection dict construction with `pool.latest(rid).to_wire()` (envelope-level). Empty-list fallback preserved when pool is None (matches existing `test_get_detections_no_detector` expectation).
- **Files modified:** `src/mcp/server.py`
- **Verification:** `tests/mcp/test_mcp_server.py` green (17/17 passed); `test_get_detections_no_detector` still passes because `pool is None` branch returns `json.dumps([])` unchanged.
- **Committed in:** 321315c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** MCP migration was required for Plan 10 to leave the codebase in a consistent state. Without it, the MCP `get_detections` tool would crash on first invocation post-Plan-10. Zero scope creep — only updates the single call site exposed by the new `detector` property.

## Issues Encountered

- **Pre-existing test isolation bug in `tests/perception/test_registry.py`:** When run after `test_protocol_contracts.py`, `test_register_accepts_full_capabilities` fails with `DetectorInput` class-identity error. Root cause: `test_perception_types_import_does_not_load_heavy_deps` deletes `src.perception.types` from `sys.modules` and re-imports, invalidating `DetectorInput` identity for any module that imported it at module scope. Already documented in `deferred-items.md` (Plan 02-01). Not caused by this plan; all target tests green in isolation and in the plan's verification suite. Out of scope per SCOPE BOUNDARY.
- **YOLOv11 backend retains `from src.perception.detector import ObjectDetector` inside a guarded drift-check:** Plan verification statement ("`grep -rn 'from src.perception.detector' src/` returns no hits") is satisfied by the coordinator-side removal. The YOLOv11 backend guard is try/except-wrapped and will be cleaned up by Plan 02-12 when `src/perception/detector.py` is deleted. Left in place — removing now would delete a drift-guard that still protects against INDOOR_CLASSES desync until Plan 12.

## Verification Results

Plan verification suite — all green:

```
tests/perception/test_no_inline_quaternion.py  ......... passed (1/1)
tests/perception/test_obb_round_trip.py ................ passed
tests/perception/test_worker_backpressure.py ........... passed
tests/perception/test_worker_pool.py ................... passed
tests/perception/test_worker_capture_pose.py ........... passed
tests/perception/test_detector_routes.py ............... passed
tests/coordination/ ..................................... passed
tests/mcp/ .............................................. passed
116 passed, 4 skipped
```

- `python -c "import src.coordination.coordinator; import backend.web.streaming_viz"` → both succeed.
- D-10 grep invariant: `tests/perception/test_no_inline_quaternion.py` green — no new inline `"quaternion":` literal introduced.
- Coordinator.detector now returns the pool; MCP consumer migrated; no stale `_detector` or `.detections` (as list) references remain in coordinator.py (only unrelated `frontier_detector` references).

## User Setup Required

None — no external service configuration.

## Next Phase Readiness

- **Plan 02-11 (frontend envelope consumer) is unblocked.** WS now emits `{"type": "detections_3d", "robot_id": rid, "payload": {items, capture_pose (16 floats), capture_timestamp, image_hw, metrics}}`. Frontend needs to:
  - Handle new `detections_3d` message type in `frontend/src/hooks/useWebSocket.ts`.
  - Replace `robotStore.updateDetections(rid, payload.detections)` with envelope-aware store slice (`detections_3d` keyed by rid).
  - Update `CameraFeed.tsx`, `RobotCard.tsx`, `SceneViewer.tsx` — all currently read `.detections` (legacy 2D shape); these will render nothing after Plan 10 lands on main until Plan 11 ships.
- **Plan 02-12 (deletions)** can now safely delete `src/perception/detector.py` (coordinator no longer imports it; only the YOLOv11 guarded drift-check remains, which is also scheduled for removal).
- **Phase 6 MetricsPanel** can now read `capture_timestamp` from the wire envelope for freshness metrics (D-11/D-12/D-13 wiring is live end-to-end from sensor → pool → envelope → WS).

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Completed: 2026-04-14*

## Self-Check: PASSED

- `src/coordination/coordinator.py` exists and contains `self._detector_pool` + `detections_3d` field. ✓
- `backend/web/streaming_viz.py` exists and imports `DETECTIONS_3D` + calls `to_wire()`. ✓
- Commit `321315c` (Task 1) found in `git log`. ✓
- Commit `133ecd1` (Task 2) found in `git log`. ✓
- Plan verification suite passes (116 passed, 4 skipped). ✓
- D-10 invariant test green. ✓
