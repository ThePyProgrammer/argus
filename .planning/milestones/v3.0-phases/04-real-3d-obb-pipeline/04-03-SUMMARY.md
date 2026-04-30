---
phase: 04
plan: 03
subsystem: perception.lifters
tags:
  - migration
  - wave-1
  - invariant
  - det-3d-06
dependency_graph:
  requires:
    - "04-02 (src/perception/geometry.py — unproject_pixel_to_world entrypoint)"
    - "04-02 (test_geometry.py::test_legacy_parity_with_median_depth_intrinsics bit-parity gate)"
  provides:
    - "MedianDepthLifter that delegates all pinhole math to geometry.unproject_pixel_to_world"
    - "Perception-package-wide grep invariants (_LEGACY_FOV_DEG absent, FOV math confined to geometry.py)"
  affects:
    - "src/perception/lifters/median_depth.py (project_center_median_depth signature gains intrinsics positional arg)"
    - "Any future lifter that composes MedianDepthLifter (e.g., Plan 04 PointClusterLifter fallback)"
tech_stack:
  added: []
  patterns:
    - "Delegation to single-entrypoint geometry module instead of inline pinhole math"
    - "Exact-token grep invariants (not substrings) to dodge false positives (Pitfall 9)"
key_files:
  created: []
  modified:
    - src/perception/lifters/median_depth.py
    - tests/perception/test_median_depth_lifter.py
    - tests/perception/test_geometry.py
decisions:
  - "Migration is signature-additive: intrinsics is a REQUIRED positional arg after pose (TypeError on omission). Two in-tree tests (test_project_center_median_depth_parity_on_identity_pose, test_legacy_parity_with_median_depth_intrinsics) were updated to pass CameraIntrinsics.from_fov(640, 480, 70.0) for bit-parity with the pre-migration 70° default."
  - "import math removed from median_depth.py — delegation to geometry.py means no stdlib math needed anywhere in the file."
  - "Grep invariant tests skip lines starting with comment/docstring delimiters (#, \"\"\", ''', \", ') to avoid false positives from narrative mentions of the forbidden tokens."
metrics:
  duration_min: 2
  completed_date: "2026-04-14"
  tasks_completed: 2
  files_changed: 3
  tests_added: 5
  commits: 3
---

# Phase 4 Plan 03: median_depth migration to geometry.unproject — _LEGACY_FOV_DEG deleted

## One-liner

MedianDepthLifter now delegates all pinhole math to `src.perception.geometry.unproject_pixel_to_world`, consuming the `intrinsics` arg that `Detection3DProtocol.lift` has been threading since Phase 1; the `_LEGACY_FOV_DEG = 70.0` constant is deleted, and three perception-package-wide grep invariants lock the single-entrypoint rule (DET-3D-06).

## What Shipped

**Task 1 — Migrate project_center_median_depth to consume intrinsics (TDD)**
- RED commit `9006438`: added `test_project_center_median_depth_takes_intrinsics_arg` and `test_lift_consumes_intrinsics_not_legacy_fov`; both fail on pre-migration signature.
- GREEN commit `f1c1ba0`:
  - Deleted `_LEGACY_FOV_DEG = 70.0` (line 43) and `import math`.
  - Added `from src.perception.geometry import unproject_pixel_to_world`.
  - `project_center_median_depth` gains `intrinsics: CameraIntrinsics` as REQUIRED positional arg after `pose`; body replaces 6 lines of inline FOV math (`fov_rad`, `f`, `cam_x`, `cam_y`, `cam_pt`, `world_pt`) with a single call to `unproject_pixel_to_world(float(cx_px), float(cy_px), d, intrinsics, pose)`.
  - `MedianDepthLifter.lift` forwards `intrinsics` through to the projection function.
  - Module-level + `lift()` docstrings rewritten to reflect Phase 4 migration (Phase 1 "IGNORED intrinsics" contract text removed).
  - Two in-tree tests updated to pass `CameraIntrinsics.from_fov(640, 480, 70.0)` to preserve bit-parity:
    - `test_project_center_median_depth_parity_on_identity_pose` in `test_median_depth_lifter.py`
    - `test_legacy_parity_with_median_depth_intrinsics` in `test_geometry.py`

**Task 2 — Perception-package-wide grep invariants (DET-3D-06)**
- Commit `94281f5`: three tests appended to `tests/perception/test_geometry.py`:
  - `test_legacy_fov_deg_absent_post_migration` — walks `src/perception/**/*.py`, asserts exact token `_LEGACY_FOV_DEG` absent from every file.
  - `test_no_math_tan_or_radians_in_perception_lifters` — regex `math\.(tan|radians)\s*\(` absent from executable code in every `src/perception/lifters/**/*.py`.
  - `test_geometry_is_only_perception_module_with_executable_fov_math` — same regex confined to `geometry.py` (or zero files) across the whole perception package.

## Dependency Graph

**Requires:**
- `04-02` — `src/perception/geometry.py` (unproject_pixel_to_world + unproject_pixels_batched) must exist and be unit-tested. Consumed via `from src.perception.geometry import unproject_pixel_to_world`.
- `04-02` — `test_geometry.py::test_legacy_parity_with_median_depth_intrinsics` bit-parity gate. The updated parity test now passes `intrinsics=CameraIntrinsics.from_fov(640, 480, 70.0)` as the parity baseline.

**Provides:**
- Clean slate for `PointClusterLifter` (Plan 04): it can compose `MedianDepthLifter` as fallback (D-07) without inheriting any hardcoded FOV assumption.
- DET-3D-06 guarantee: `grep -rn "_LEGACY_FOV_DEG" src/perception/` returns zero hits; `grep -rn "math\.(tan|radians)" src/perception/lifters/` returns zero hits.

**Affects:**
- `src/perception/lifters/median_depth.py` — `project_center_median_depth` signature change (additive; new required positional arg). Callers must pass intrinsics explicitly. Only in-tree callers were the two parity tests; both updated in this plan.

## Key Decisions

1. **Signature change is additive, not renamed** — `project_center_median_depth(bbox_xyxy, depth, pose, intrinsics, depth_near_m=..., depth_far_m=...)`. Omitting `intrinsics` raises `TypeError`. This is the clearest upgrade path (no silent behavior shift on old call sites; they all fail loud).

2. **Bit-parity via matched intrinsics** — the legacy 70° FOV with 480×640 is recoverable by `CameraIntrinsics.from_fov(640, 480, 70.0)`. The bit-parity gate in Plan 04-02 (`test_legacy_parity_with_median_depth_intrinsics`) is preserved by updating in-tree parity tests to pass that specific intrinsics. No drift in world-frame centers.

3. **import math removed entirely** — once FOV math is gone, `math` has no in-file use. Cleaner than leaving a stale import.

4. **Grep tests use exact-token / anchored-regex matching** — Pitfall 9 says substring matches on `70` or `fov` would false-positive. Tests match the literal `_LEGACY_FOV_DEG` identifier and the regex `math\.(tan|radians)\s*\(` (function-call pattern), which only appears in executable code.

5. **Grep tests walk `src/perception/**/*.py` not `src/**/*.py`** — per D-06 the invariant is scoped to the perception package; other packages (e.g., `src/bridge/sensor_types.py::CameraIntrinsics.from_fov`) are the RIGHT place for FOV derivation and must not be flagged.

## Deviations from Plan

None — plan executed exactly as written. Two minor extensions already scoped by the plan's own "Action" steps:
- Step 10 of Task 1 Action instructed identifying in-tree callers of `project_center_median_depth` via grep; the two identified callers (in-tree parity tests) were updated to pass `CameraIntrinsics.from_fov(640, 480, 70.0)`.
- `import math` was removed from `median_depth.py` per Action step 2 (no remaining references after FOV math replacement).

## Verification

Plan-scope pytest suite (24/24 passing):

```
$ python -m pytest tests/perception/test_median_depth_lifter.py tests/perception/test_geometry.py -q
........................  24 passed in 0.05s
```

Acceptance criteria:

| Criterion | Command | Result |
|-----------|---------|--------|
| `_LEGACY_FOV_DEG` absent from lifter | `grep -c "_LEGACY_FOV_DEG" src/perception/lifters/median_depth.py` | `0` |
| `_LEGACY_FOV_DEG` absent package-wide | `grep -rn "_LEGACY_FOV_DEG" src/perception/` | zero hits |
| `math.tan`/`math.radians` absent from lifter | `grep -c "math.radians\|math.tan" src/perception/lifters/median_depth.py` | `0` |
| geometry import present | `grep -c "from src.perception.geometry import unproject_pixel_to_world" src/perception/lifters/median_depth.py` | `1` |
| `project_center_median_depth` references | `grep -c "project_center_median_depth" src/perception/lifters/median_depth.py` | `4` (def + 1 call + 2 docstring refs) |
| DET-3D-02 protection | `Detection3DRegistry.list_backends()` contains `median_depth` | OK |
| Bit-parity gate | `test_legacy_parity_with_median_depth_intrinsics` | PASS |
| New tests | `test_project_center_median_depth_takes_intrinsics_arg`, `test_lift_consumes_intrinsics_not_legacy_fov`, `test_legacy_fov_deg_absent_post_migration`, `test_no_math_tan_or_radians_in_perception_lifters`, `test_geometry_is_only_perception_module_with_executable_fov_math` | all PASS |

## Commits

- `9006438` test(04-03): add failing tests for intrinsics-consuming median_depth lifter (RED)
- `f1c1ba0` feat(04-03): migrate median_depth lifter to geometry.unproject — delete _LEGACY_FOV_DEG (GREEN)
- `94281f5` test(04-03): add perception-package-wide grep invariants for DET-3D-06

## Known Stubs

None. Migration is complete and all tests pass.

## Threat Flags

None. Plan's threat register items (T-04-08 Tampering, T-04-09 Information Disclosure, T-04-10 DoS) were all scoped to this migration and addressed:

- **T-04-08 (bit-parity tampering):** Plan 04-02's parity test was updated to pass matching intrinsics — bit-parity locked.
- **T-04-09 (intrinsics drift):** D-04 plumbing unchanged; `Detection3DProtocol.lift(..., intrinsics, ...)` remains the single source. Migration just starts CONSUMING what was always threaded.
- **T-04-10 (grep false positives):** tests match exact tokens / anchored regex, not substrings; `CameraIntrinsics.from_fov` calls outside perception package are not flagged (scope limited to `src/perception/**`).

## Self-Check: PASSED

Files verified to exist:

- `src/perception/lifters/median_depth.py` — FOUND (243 lines, min_lines requirement: 200)
- `tests/perception/test_median_depth_lifter.py` — FOUND (min_lines requirement: 60; contains `test_lift_consumes_intrinsics_not_legacy_fov`)
- `tests/perception/test_geometry.py` — FOUND (min_lines requirement: 100; contains `test_legacy_fov_deg_absent_post_migration`)

Commits verified in git log:

- `9006438` — FOUND
- `f1c1ba0` — FOUND
- `94281f5` — FOUND
