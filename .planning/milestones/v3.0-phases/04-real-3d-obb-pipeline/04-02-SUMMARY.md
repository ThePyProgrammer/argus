---
phase: 04-real-3d-obb-pipeline
plan: 02
subsystem: perception
tags: [geometry, unprojection, pinhole, numpy, tdd, wave-0]

# Dependency graph
requires:
  - phase: 01-detector-api-foundation
    provides: CameraIntrinsics dataclass + SensorFrame shape (src/bridge/sensor_types.py)
  - phase: 01-detector-api-foundation
    provides: MedianDepthLifter.project_center_median_depth legacy math reference
provides:
  - src/perception/geometry.py — single stateless projection entrypoint (DET-3D-06)
  - unproject_pixel_to_world(u, v, depth, intrinsics, pose) -> (3,)
  - unproject_pixels_batched(uvs, depths, intrinsics, pose) -> (N, 3)
  - 7-test contract locking Pitfall 8 sign flip + Pitfall 10 import isolation
affects:
  - 04-03 (median_depth migration — can now delete _LEGACY_FOV_DEG with bit-parity guarantee)
  - 04-04 (PointClusterLifter — consumes batched unprojection on bbox frustums)
  - DET-3D-06

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stateless pure-function geometry module (no classes, no module state)"
    - "Contract-first TDD: test file committed RED before implementation"
    - "Import-isolation invariant enforced by sys.modules assertion test"

key-files:
  created:
    - src/perception/geometry.py
    - tests/perception/test_geometry.py
  modified: []

key-decisions:
  - "Preserved camera-frame sign flip [cam_x, -cam_y, -depth] verbatim from median_depth.py:97 (MuJoCo OpenCV-optical convention — Pitfall 8)"
  - "Module intentionally imports only numpy + CameraIntrinsics; no cloud_config, no heavy deps, no helper privates"
  - "Tuple intrinsics explicitly rejected via attribute access (intrinsics.fx) — locked by Test 7"

patterns-established:
  - "src/perception/geometry.py is the ONLY projection module in perception (DET-3D-06 invariant)"
  - "Test-locked bit-parity with legacy path before migrating consumers (Plan 04-03 can cut over safely)"

requirements-completed: [DET-3D-06]

# Metrics
duration: ~5min
completed: 2026-04-14
---

# Phase 04 Plan 02: geometry.py single projection entrypoint — Summary

**Stateless pinhole unprojection module (`unproject_pixel_to_world` + `unproject_pixels_batched`) plus a 7-test contract locking the MuJoCo sign-flip convention and import-isolation invariant, committed TDD-style (RED then GREEN) so Plan 04-03 can migrate median_depth.py with bit-parity.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-14T09:40:00Z (approximate)
- **Completed:** 2026-04-14T09:46:27Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files created:** 2 (geometry.py 56 LOC, test_geometry.py 142 LOC)

## Accomplishments

- Created `src/perception/geometry.py` — the single projection entrypoint per DET-3D-06, implementing both `unproject_pixel_to_world` and `unproject_pixels_batched` as stateless pure functions consuming `CameraIntrinsics`.
- Created `tests/perception/test_geometry.py` with 7 tests locking the D-05/D-06 contract:
  1. Center-pixel identity-pose sign convention (Pitfall 8: `(cx, cy, 2.0) -> (0, 0, -2)`)
  2. Batched vs single-pixel parity at ±1e-9 over 16 random pixels
  3. Pose rotation (90° about Z) + translation application
  4. Bit-parity with legacy `median_depth.project_center_median_depth` at ±1e-9 (locks migration path for Plan 04-03)
  5. Grep invariant: `_LEGACY_FOV_DEG` absent from geometry.py executable code
  6. Pitfall 10: importing geometry does not pull `src.bridge.cloud_config` into `sys.modules`
  7. Type enforcement: tuple `intrinsics` raises TypeError/AttributeError
- RED state committed separately from GREEN (Task 1 = failing test, Task 2 = passing implementation).

## Task Commits

1. **Task 1: Write test_geometry.py (RED)** — `ebe8b8b` (test)
2. **Task 2: Implement src/perception/geometry.py (GREEN)** — `5a917c5` (feat)

Both tasks committed with `--no-verify` per worktree parallel-executor protocol.

## Files Created/Modified

- `src/perception/geometry.py` (created, 56 LOC) — two stateless unprojection helpers, sign-flip `[cam_x, -cam_y, -depth]` preserved verbatim, no heavy imports.
- `tests/perception/test_geometry.py` (created, 142 LOC) — 7 pytest tests asserting the D-05/D-06 contract.

## Decisions Made

- **Sign-flip preservation:** `[cam_x, -cam_y, -depth]` copied verbatim from `median_depth.py:97` rather than re-derived. Pitfall 8 rationale: MuJoCo's camera convention is OpenCV-optical and must not diverge from SLAM-owned poses. Changing the sign flip would break the Plan 07 MuJoCo GT integration test.
- **Dual API (single + batched):** Kept both per D-05. Single-pixel form is used by the median-depth fallback (Plan 04-03), batched form by PointClusterLifter's frustum unprojection (Plan 04-04). Sharing the math between them via a common helper was rejected to keep the module at minimum surface area.
- **No FOV constant anywhere in module:** The module does not contain `70`, `_LEGACY_FOV_DEG`, or `math.radians` — callers pass `CameraIntrinsics`, which fully parametrizes the pinhole model.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Extra `sys.modules.pop("src.bridge.cloud_config")` in Test 6**
- **Found during:** Task 1 (authoring Test 6 — `test_geometry_does_not_import_cloud_config`)
- **Issue:** The plan's Test 6 skeleton only popped `src.perception.geometry` before re-importing. If any other test (conftest, collection order) had already pulled `src.bridge.cloud_config` into `sys.modules`, Test 6 would fail for a reason orthogonal to geometry.py's own imports — a brittle test assertion.
- **Fix:** Added `sys.modules.pop("src.bridge.cloud_config", None)` immediately before the re-import, so the test reliably asserts the fresh-import invariant "importing geometry does not pull cloud_config into sys.modules" regardless of prior test-module state.
- **Files modified:** tests/perception/test_geometry.py (line in `test_geometry_does_not_import_cloud_config`).
- **Verification:** Test passes; `python -c "import sys; import src.perception.geometry; assert 'src.bridge.cloud_config' not in sys.modules"` also exits 0.
- **Committed in:** `ebe8b8b` (Task 1 commit).

---

**Total deviations:** 1 auto-fixed (1 blocking — test reliability).

**Impact on plan:** Tightens a contract test without changing its semantic. No code-under-test change.

### Acceptance-criteria note

The plan's acceptance criterion `grep -c "cloud_config" src/perception/geometry.py returns 0` is **not met literally**: the module's docstring contains one line (`"Pitfall 10: this module must NOT import src.bridge.cloud_config. That file ..."`) because the plan's own Pattern Template 2 mandates this docstring. The real invariant — "no runtime import of cloud_config" — is enforced at runtime by Test 6 (`test_geometry_does_not_import_cloud_config`) and at import time by `python -c "import src.perception.geometry; assert 'src.bridge.cloud_config' not in sys.modules"`. Following the plan's Pattern Template (authoritative) over the stricter grep wording preserves the intent.

## Issues Encountered

- None. TDD flow (RED commit → GREEN commit) ran cleanly; all 7 tests passed on first implementation attempt.

## User Setup Required

None — no external services, credentials, or configuration touched.

## Next Phase Readiness

- `geometry.unproject_pixel_to_world` is now the public API Plan 04-03 will call to replace `median_depth.py`'s inline FOV math. Test 4 (legacy parity) guarantees bit-exact behavior so the migration is a drop-in.
- `geometry.unproject_pixels_batched` is ready for Plan 04-04 (PointClusterLifter) to vectorize bbox-frustum unprojection without re-implementing the sign flip.
- Grep invariant locked: no executable `_LEGACY_FOV_DEG` inside geometry.py. Plan 04-03 will delete the constant from `median_depth.py` and tighten the grep test to cover the whole `src/perception/` tree.

## Self-Check: PASSED

- `test -f src/perception/geometry.py` — FOUND
- `test -f tests/perception/test_geometry.py` — FOUND
- `git log --oneline` contains `ebe8b8b` — FOUND
- `git log --oneline` contains `5a917c5` — FOUND
- `pytest tests/perception/test_geometry.py -x -q` — 7 passed
- `python -c "import sys; import src.perception.geometry; assert 'src.bridge.cloud_config' not in sys.modules"` — exit 0

---
*Phase: 04-real-3d-obb-pipeline*
*Completed: 2026-04-14*
