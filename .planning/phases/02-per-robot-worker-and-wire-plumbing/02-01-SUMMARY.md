---
phase: 02-per-robot-worker-and-wire-plumbing
plan: 01
subsystem: perception
tags: [perception, wire-format, obb, serialization, quaternion, detections3d]

# Dependency graph
requires:
  - phase: 01-detector-api-foundation
    provides: OrientedBox3D + Detections3D skeletons, DetectorProtocol, median_depth lifter call sites
provides:
  - OrientedBox3D.to_wire() with D-06 auto-flip, D-07 track_id omission, D-08 plain-float
  - OrientedBox3D.from_wire() with strict validation (all required keys + shape + qw>=0)
  - OrientedBox3D.bbox_xyxy optional field (keeps CameraFeed 2D overlay alive Phase 2 cutover)
  - Detections3D.capture_pose (4x4 np.ndarray) + capture_timestamp envelope fields
  - Detections3D.to_wire() with D-14 flat 16-float row-major pose + metrics sub-dict
  - 1000-OBB round-trip test (seed 42) + 9 edge-case/shape tests locking the wire format
affects: [02-02, 02-03, 02-04, 02-05, 02-06, 02-07, 02-08, 02-09, 02-10, 02-11, 02-12]

# Tech tracking
tech-stack:
  added: [scipy.spatial.transform.Rotation (test-only, already in base deps)]
  patterns:
    - "Hemisphere-canonical quaternion wire format (qw>=0; to_wire auto-flips; from_wire rejects)"
    - "Optional-field key-omission over null sentinels (D-07: track_id, bbox_xyxy)"
    - "Flat JSON wire shapes over nested (D-09 OBB; D-14 16-float row-major pose)"
    - "Plain-python scalars on the wire (D-08 -- no numpy scalars leak, no custom JSON encoder)"

key-files:
  created:
    - tests/perception/test_obb_round_trip.py
    - .planning/phases/02-per-robot-worker-and-wire-plumbing/deferred-items.md
  modified:
    - src/perception/types.py
    - tests/perception/test_protocol_contracts.py

key-decisions:
  - "Field order on OrientedBox3D: bbox_xyxy appended AFTER track_id as the last optional field so Phase 1 keyword-arg call sites (median_depth, coordinator) keep compiling."
  - "Defaults on Detections3D.capture_pose (np.eye(4)) and capture_timestamp (0.0) are compat shims ONLY through the Wave 2 cutover -- Wave 2 DetectorWorker MUST overwrite both."
  - "Pre-existing test-ordering failure in protocol_contracts+registry pytest invocation (module reload invalidates DetectorInput identity) is out of scope for 02-01; logged in deferred-items.md."

patterns-established:
  - "Wire-format pattern: dataclass.to_wire() returns a flat dict with plain-python scalars; dataclass.from_wire(cls, obj) validates strictly (required keys, shapes, invariants) and raises ValueError with deterministic messages on violation."
  - "Canonicalization enforced at the serialization boundary (to_wire auto-flips qw<0) rather than the dataclass constructor -- keeps OrientedBox3D trivially constructible in math code while making the wire invariant a hard protocol rule."

requirements-completed: [DET-3D-03, DET-3D-04, DET-API-05]

# Metrics
duration: ~12 min
completed: 2026-04-14
---

# Phase 2 Plan 01: OBB + Detections3D Wire Format Summary

**Canonical OBB + Detections3D wire format (flat dict, qw>=0 auto-flip, optional bbox_xyxy + track_id key-omission, envelope-level capture_pose flat-16 row-major + capture_timestamp) locked by a 1000-OBB seeded round-trip test plus 9 edge/shape tests.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-04-14T02:29:13Z
- **Tasks:** 2 / 2
- **Files created:** 2 (1 test file + 1 deferred-items log)
- **Files modified:** 2 (types.py, test_protocol_contracts.py)

## Accomplishments

- OrientedBox3D ships to_wire() / from_wire() with full D-06..D-10 compliance
  (qw>=0 auto-flip, track_id key omission, plain-float enforcement, flat D-09 shape).
- OrientedBox3D gains `bbox_xyxy: tuple[int,int,int,int] | None` optional field
  (02-RESEARCH W-01 / Pitfall 8) so the frontend CameraFeed 2D overlay survives
  the Phase 2 cutover without spinning up a parallel RGB-overlay stream.
- Detections3D ships envelope-level capture_pose (4x4 np.ndarray) + capture_timestamp
  (float seconds) per D-11, D-12. to_wire() emits D-14 flat 16-float row-major pose
  + metrics sub-dict; 4x4 shape is asserted at serialization time (T-02-02 mitigation).
- 1000-randomized-OBB round-trip test (seed 42, scipy.spatial.transform.Rotation.random
  Haar-uniform sampling, 50% negated quaternions, alternating track_id, every-3rd
  bbox_xyxy) proves DET-3D-04's ±1e-6 tolerance. 10 total tests green in <1s.
- D-10 invariant holds: exactly one `"quaternion":` literal in src/perception/types.py,
  inside OrientedBox3D.to_wire.

## Task Commits

1. **Task 1: Extend OrientedBox3D + Detections3D with wire format methods** — `901c19e` (feat)
2. **Task 2: Write 1000-OBB round-trip + edge case + envelope round-trip tests** — `76b2db6` (test)

**Plan metadata:** final docs commit pending (SUMMARY.md atomic commit).

## Files Created / Modified

- `src/perception/types.py` — added to_wire/from_wire on OrientedBox3D, bbox_xyxy optional field, capture_pose/capture_timestamp on Detections3D with default factory, Detections3D.to_wire() with 4x4 shape assertion. Phase 1 docstring updated to mention Plan 02-01 scope.
- `tests/perception/test_obb_round_trip.py` — 10 tests (round-trip, wire shape, negative qw rejection, missing-key rejection, edge cases, track_id omission, bbox_xyxy optional, envelope round-trip, non-4x4 pose rejection, generator determinism).
- `tests/perception/test_protocol_contracts.py` — replaced two Phase-1 skeleton-locking assertions with Phase-2 field-set + to_wire/from_wire presence assertions.
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/deferred-items.md` — logged pre-existing test-ordering bug (protocol_contracts + registry in same pytest invocation).

## Decisions Made

- **bbox_xyxy appended as the last OrientedBox3D field (not inserted after score).** Inserting would shift positional-arg call sites; appending keeps Phase 1 `OrientedBox3D(center=..., half_extents=..., ..., track_id=None)` working verbatim. Median_depth lifter construction site confirmed untouched.
- **Defaults on Detections3D.capture_pose / capture_timestamp.** Plan-specified shim so Phase 1 test call sites (e.g., median_depth `test_median_depth_lifter.py`) keep compiling through the Wave 2 cutover. Wave 2 DetectorWorker must overwrite; Wave 4 can remove the defaults if desired.
- **Defensive shape assertions on center/half_extents in to_wire().** The reference snippet only validated the quaternion, but the same invariant (shape (3,)) is needed for center and half_extents. Added to to_wire and from_wire — strict-by-default. ValueError messages name the offending field for T-02-01 fail-closed semantics.
- **Generator determinism test added.** Not strictly required by the plan, but locks the fixture seed so future test output regressions are bit-exact debuggable. One extra test; small cost.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated Phase 1 contract tests that explicitly locked the skeleton state**
- **Found during:** Task 1 (initial verify run)
- **Issue:** `test_protocol_contracts.py` contained two assertions that directly contradict Plan 02-01's objective: `test_no_to_wire_on_oriented_box_3d` asserts `not hasattr(OrientedBox3D, 'to_wire')`, `test_oriented_box_3d_skeleton_contract` locked the 7-field skeleton (without bbox_xyxy), and `test_detections_3d_dataclass_contract` locked the 6-field Detections3D (without capture_pose / capture_timestamp). These would block every Phase 2 plan.
- **Fix:** Replaced the three assertions with Phase 2 equivalents: to_wire/from_wire presence check, 8-field OBB list including bbox_xyxy, 8-field Detections3D list including capture_pose + capture_timestamp. Field order preserved (new fields appended as the last optional slots, not inserted).
- **Files modified:** tests/perception/test_protocol_contracts.py
- **Verification:** `pytest tests/perception/test_protocol_contracts.py -q` → 18/18 green.
- **Committed in:** 901c19e (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added defensive shape validation to to_wire()**
- **Found during:** Task 1 implementation
- **Issue:** The reference snippet in the plan validated only quaternion shape; center and half_extents could be passed as arbitrary-shaped ndarrays and silently serialize to garbage. Same risk class as T-02-01 (tampering / malformed input).
- **Fix:** Added `if center.shape != (3,): raise ValueError` and same for half_extents inside `to_wire`, mirroring the quaternion check. Rule 2 / T-02-01 defense-in-depth.
- **Files modified:** src/perception/types.py
- **Verification:** Covered implicitly by test_round_trip_1000_boxes (all shape-(3,) inputs pass); the check is a fail-fast for future callers.
- **Committed in:** 901c19e (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking Phase-1-test mismatch, 1 defense-in-depth shape validation). **Impact:** no scope creep; both are required for the plan's success criteria (blocker) or for T-02-01 mitigation (validation).

## Issues Encountered

**Pre-existing test-ordering failure (not caused by this plan):** Running `pytest tests/perception/test_protocol_contracts.py tests/perception/test_registry.py` together yields 7 registry failures (`ValueError: CAPABILITIES['input_type'] must be DetectorInput, got DetectorInput`). Root cause: `test_perception_types_import_does_not_load_heavy_deps` deletes `src.perception.types` from `sys.modules` and re-imports it, which invalidates the `DetectorInput` class identity for any downstream test that imported `DetectorInput` at module scope. Confirmed reproducible on base commit `1a804fe` (pre-existing, not introduced by Plan 02-01). Each file runs green in isolation (18/18 + 16/16). Logged in `deferred-items.md`; recommend future cleanup via pytest fixture that restores `sys.modules` or by moving the reload test to its own subprocess. No impact on Plan 02-01 deliverables.

## Verification Gate Status

| Gate | Command | Result |
|------|---------|--------|
| Plan verify block (new tests) | `pytest tests/perception/test_obb_round_trip.py tests/perception/test_protocol_contracts.py` | **PASS** — 28/28 green |
| Plan verify block (full, including pre-existing bug) | `pytest tests/perception/test_obb_round_trip.py tests/perception/test_protocol_contracts.py tests/perception/test_registry.py` | PARTIAL — 37 pass, 7 pre-existing registry failures (same on base) |
| D-10 literal count in types.py | `grep -n '"quaternion":' src/perception/types.py \| wc -l` | **PASS** — exactly 1 |
| Import smoke | `python -c "from src.perception.types import OrientedBox3D, Detections3D; print(OrientedBox3D.to_wire, Detections3D.to_wire)"` | **PASS** — both methods importable and callable |
| DET-3D-04 (1000-box round-trip ±1e-6) | `pytest tests/perception/test_obb_round_trip.py::test_round_trip_1000_boxes -x` | **PASS** — 1000 boxes round-trip <0.25 s |

## Integration Notes for Wave 2+

- **Wave 2 DetectorWorker (02-06):** when assembling `Detections3D` post-lift, MUST populate `capture_pose` (from `pool.submit` payload) and `capture_timestamp` (from `frame.sim_time`). Default values are shim-only and fall apart for the Phase 6 freshness metric (`sim_now - capture_timestamp`).
- **Wave 2 DetectorWorker (02-06):** when threading 2D detections through the lifter, populate `OrientedBox3D.bbox_xyxy` from the source `Detection2D.bbox_xyxy` so the frontend CameraFeed overlay has the pixel box available without re-reading `Detections2D`.
- **Wave 4 streaming_viz (02-10/02-11):** wire encoding is `Detections3D.to_wire()` — single call site, no inline `"quaternion":` construction anywhere (D-10 enforced). Frontend matrix reconstruction: `THREE.Matrix4.fromArray(capture_pose)` consumes the flat-16 row-major list directly.
- **Phase 2 grep invariant (tests/perception/test_no_inline_quaternion.py — future plan scope):** types.py currently passes (1 literal inside OrientedBox3D.to_wire). Future src/ additions must not introduce more `"quaternion":` string literals.

## Threat Flags

None — no new trust boundaries introduced beyond those already in the plan's `<threat_model>`. T-02-01 (from_wire tampering) and T-02-02 (capture_pose flattening) are both mitigated with strict validation + deterministic ValueError messages as documented.

## Next Phase Readiness

- Ready for Wave 1 sibling (Plan 02-06) to land independently (no file overlap per wave spec).
- Ready for Wave 2 (02-02 coordinator submit, 02-06 DetectorWorker) which consumes `Detections3D(..., capture_pose=..., capture_timestamp=...)` as the return type.
- No blockers. Pre-existing test-ordering bug in Phase 1 tests is logged for a future hygiene pass.

## Self-Check: PASSED

- `src/perception/types.py` exists — FOUND
- `tests/perception/test_obb_round_trip.py` exists — FOUND
- `tests/perception/test_protocol_contracts.py` exists — FOUND (modified)
- `.planning/phases/02-per-robot-worker-and-wire-plumbing/deferred-items.md` exists — FOUND
- Task 1 commit `901c19e` in git log — FOUND
- Task 2 commit `76b2db6` in git log — FOUND
- 1000-box round-trip test passes (<1 s) — FOUND
- D-10 literal count in types.py == 1 — FOUND
- 18/18 test_protocol_contracts green — FOUND
- 10/10 test_obb_round_trip green — FOUND

---
*Phase: 02-per-robot-worker-and-wire-plumbing*
*Plan: 01*
*Completed: 2026-04-14*
