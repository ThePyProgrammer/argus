---
phase: 04
plan: 01
subsystem: perception-scaffolding
tags:
  - dependency
  - fixture
  - wave-0
requirements:
  - DET-3D-01
dependency_graph:
  requires: []
  provides:
    - scikit-learn available under perception extra (enables DBSCAN clustering in PointClusterLifter)
    - MuJoCo GT fixture with known-yaw chair body (enables SC#1 integration test)
  affects:
    - .planning/phases/04-real-3d-obb-pipeline/04-04-PLAN.md (PointClusterLifter — consumes sklearn)
    - .planning/phases/04-real-3d-obb-pipeline/04-07-PLAN.md (MuJoCo integration test — consumes fixture)
tech_stack:
  added:
    - scikit-learn>=1.4.0 (perception extra)
  patterns:
    - MuJoCo XML fixture with compound-primitive chair (no mesh/asset dependency)
    - Camera fovy pinned to runtime CameraIntrinsics.from_fov convention
key_files:
  created:
    - tests/perception/fixtures/scene_rotated_chair.xml
  modified:
    - pyproject.toml
decisions:
  - D-02 sklearn>=1.4.0 pinned under perception extra (never top-level)
  - D-11 MuJoCo fixture uses compound primitives (no external mesh)
metrics:
  duration: 1min
  completed: 2026-04-14
  tasks: 2
  files_touched: 2
---

# Phase 4 Plan 01: Wave-0 Scaffolding (sklearn dep + chair fixture) Summary

Added `scikit-learn>=1.4.0` to the `perception` optional extra and created the self-contained `scene_rotated_chair.xml` MuJoCo fixture with a 30° yaw chair body — unblocking PointClusterLifter (Plan 04) and the SC#1 MuJoCo integration test (Plan 07).

## What Was Built

**1. Perception-extra dependency surface (`pyproject.toml`)**
- Reformatted `perception` extra as a multi-line list and appended `scikit-learn>=1.4.0` as the fourth entry
- Did NOT touch top-level `dependencies` — sklearn stays scoped to `pip install -e '.[perception]'`
- Preserved `torch`, `transformers`, `ultralytics` versions verbatim (locked by Phases 1–2)

**2. MuJoCo ground-truth fixture (`tests/perception/fixtures/scene_rotated_chair.xml`)**
- New directory `tests/perception/fixtures/` created alongside the existing perception test suite
- Self-contained scene: `floor` plane, `robot_cam` camera (pos `(0, -2.0, 0.6)`, `fovy="70"`), and `chair` body
- Chair body at `pos="0 0 0.45" euler="0 0 0.5236"` (30° yaw about +Z)
- Compound primitives (seat + backrest + 4 legs) — no `<mesh>` or `<asset>` tags
- Verified via `mujoco.MjModel.from_xml_path` + `mj_forward`:
  - `xpos == (0, 0, 0.45)` (within 1e-6)
  - Scipy-extracted yaw `== 0.5236 rad` (within 1e-3)
  - Quaternion `xquat == [0.96592567, 0, 0, 0.25881964]` (w-first MuJoCo convention)

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Add scikit-learn>=1.4.0 to perception extra | `c6cd156` | `pyproject.toml` |
| 2 | Create MuJoCo scene_rotated_chair.xml fixture (D-11) | `7851c06` | `tests/perception/fixtures/scene_rotated_chair.xml` |

## Verification Results

**Task 1 automated check (passed):**
```
>>> tomllib.loads(pyproject.toml)['project']['optional-dependencies']['perception']
['torch>=2.10.0', 'transformers>=5.3.0', 'ultralytics>=8.4.24', 'scikit-learn>=1.4.0']
```
- `grep -c 'scikit-learn>=1.4.0' pyproject.toml` → `1`
- Top-level `dependencies` confirmed free of `scikit-learn`

**Task 2 automated check (passed — executed with project .venv/bin/python):**
```
xpos=  [0.   0.   0.45]
xquat= [0.96592567 0. 0. 0.25881964]
FIXTURE OK: yaw_rad= 0.5236
```
- `grep -c 'body name="chair"'` → `1`
- `grep -c 'fovy="70"'` → `1`
- `grep -c "<mesh\|<asset"` → `0` (self-contained invariant)

**Success criteria (plan-level):**
- Plan 04 (PointClusterLifter) will be able to `import sklearn.cluster` after `pip install -e '.[perception]'` — UNBLOCKED.
- Plan 07 integration test can `MjModel.from_xml_path(...)` and read `data.body('chair').xpos / .xquat` — UNBLOCKED.

## Deviations from Plan

None — the plan was executed exactly as written. The only operational wrinkle was that the default `python` on PATH lacks the `mujoco` module; the verification was re-run via `/home/prannayag/pragnition/robotics/argus/.venv/bin/python` (the project venv). Plan XML and fixture content match the spec literally.

## Authentication Gates

None.

## Threat Register Status (plan's STRIDE table)

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|--------------------|
| T-04-01 (Tampering, pyproject.toml perception extra) | mitigate | sklearn pinned `>=1.4.0`, added ONLY to perception extra — top-level `dependencies` untouched |
| T-04-02 (Tampering, scene_rotated_chair.xml) | mitigate | Self-contained fixture (no external mesh/asset refs); committed to repo; MuJoCo loader does not execute arbitrary code |
| T-04-03 (DoS, malformed XML parse) | accept | Hand-authored fixture verified by the Task 2 automated check; test-suite scope only |

## Known Stubs

None. Both artifacts are final, load cleanly, and are consumed directly by downstream plans (04 and 07).

## Deferred Issues

None introduced by this plan. Pre-existing items in `deferred-items.md` (if any) are untouched.

## Self-Check

- FOUND: `pyproject.toml` contains `scikit-learn>=1.4.0` under `perception` extra
- FOUND: `tests/perception/fixtures/scene_rotated_chair.xml` (36 lines, parses via MuJoCo)
- FOUND commit `c6cd156` (chore(04-01): add scikit-learn>=1.4.0 to perception extra)
- FOUND commit `7851c06` (feat(04-01): add scene_rotated_chair MuJoCo fixture (D-11))

## Self-Check: PASSED
