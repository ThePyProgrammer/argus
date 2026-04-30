---
phase: 04
slug: real-3d-obb-pipeline
status: planned
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-14
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Per-Task Verification Map filled by planner (2026-04-14).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) — Vitest already configured for frontend (Phase 3) |
| **Config file** | pytest.ini (exists) |
| **Quick run command** | `pytest tests/perception/test_geometry.py tests/perception/test_point_cluster_lifter.py tests/perception/test_lifter_hotswap.py -x -q` |
| **Full suite command** | `pytest tests/perception/ tests/integration/test_obb_mujoco_scene.py -q --timeout=120 && cd frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~30s (unit) + ~60s (MuJoCo integration single-frame, first-inference warmup) + ~15s (frontend tsc) |

---

## Sampling Rate

- **After every task commit:** run the quick-run command scoped to the task's file (examples in Per-Task Verification Map).
- **After every plan wave:** run the full suite command.
- **Before `/gsd-verify-work`:** full suite must be green INCLUDING the SC#1 ±15° / 0.15m gate.
- **Max feedback latency:** 60 seconds for unit tests; 120 seconds for integration.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 | 01 | 0 | DET-3D-01 | T-04-01 | perception extra pins `scikit-learn>=1.4.0` | dep | `python -c "import tomllib; d=tomllib.loads(open('pyproject.toml').read()); assert any('scikit-learn>=1.4.0' in e for e in d['project']['optional-dependencies']['perception'])"` | `pyproject.toml` | ⬜ pending |
| 01-T2 | 01 | 0 | DET-3D-01 | T-04-02,03 | MuJoCo fixture loads; chair body at ~30° yaw, xpos (0,0,0.45) | unit | `python -c "import mujoco, numpy as np; from scipy.spatial.transform import Rotation; m=mujoco.MjModel.from_xml_path('tests/perception/fixtures/scene_rotated_chair.xml'); d=mujoco.MjData(m); mujoco.mj_forward(m,d); b=d.body('chair'); w,x,y,z=b.xquat; yaw=Rotation.from_quat([x,y,z,w]).as_euler('zyx')[0]; assert abs(yaw-0.5236)<1e-3 and abs(b.xpos[2]-0.45)<1e-6"` | `tests/perception/fixtures/scene_rotated_chair.xml` | ⬜ pending |
| 02-T1 | 02 | 0 | DET-3D-06 | T-04-04,05,07 | 7 RED tests author sign-flip + API-shape + no-cloud_config invariants | unit | `pytest tests/perception/test_geometry.py --collect-only` | `tests/perception/test_geometry.py` | ⬜ pending |
| 02-T2 | 02 | 0 | DET-3D-06 | T-04-04,06 | `geometry.py` implements D-05 API; no heavy imports; Pitfall 8 sign flip preserved | unit | `pytest tests/perception/test_geometry.py -x -q` | `src/perception/geometry.py` | ⬜ pending |
| 03-T1 | 03 | 1 | DET-3D-06, DET-3D-02 | T-04-08,09 | median_depth.py migrated to geometry.unproject_pixel_to_world; `_LEGACY_FOV_DEG` deleted; intrinsics consumed | unit | `pytest tests/perception/test_median_depth_lifter.py tests/perception/test_geometry.py -x -q` | `src/perception/lifters/median_depth.py` | ⬜ pending |
| 03-T2 | 03 | 1 | DET-3D-06 | T-04-10 | Post-migration grep invariants across perception pkg | unit | `pytest tests/perception/test_geometry.py::test_legacy_fov_deg_absent_post_migration tests/perception/test_geometry.py::test_no_math_tan_or_radians_in_perception_lifters tests/perception/test_geometry.py::test_geometry_is_only_perception_module_with_executable_fov_math -x -q` | `tests/perception/test_geometry.py` | ⬜ pending |
| 04-T1 | 04 | 2 | DET-3D-01, DET-3D-07 | T-04-11..17 | 10+ RED unit tests: registration, synthetic cluster, fallback, DBSCAN, Open3D extent/2, all-noise skip | unit | `pytest tests/perception/test_point_cluster_lifter.py --collect-only` | `tests/perception/test_point_cluster_lifter.py` | ⬜ pending |
| 04-T2 | 04 | 2 | DET-3D-01, DET-3D-07 | T-04-11..17 | PointClusterLifter per Pattern Template 1; registered under `point_cluster`; composes MedianDepthLifter fallback | unit | `pytest tests/perception/test_point_cluster_lifter.py tests/perception/test_median_depth_lifter.py tests/perception/test_geometry.py -x -q` | `src/perception/lifters/point_cluster.py`, `src/perception/lifters/__init__.py` | ⬜ pending |
| 05-T1 | 05 | 3 | DET-3D-01 | T-04-20,22,23 | `swap_lifter` atomically rebinds every worker's `_lifter` under `_swap_lock`; 30Hz submit concurrency test green | unit + concurrency | `pytest tests/perception/test_lifter_hotswap.py::test_swap_lifter_replaces_every_workers_lifter_ref tests/perception/test_lifter_hotswap.py::test_hotswap_under_30hz_submit tests/perception/test_worker_pool.py tests/perception/test_worker_pool_lifter_params.py -x -q` | `src/perception/worker_pool.py`, `src/main.py`, `tests/perception/test_lifter_hotswap.py` | ⬜ pending |
| 05-T2 | 05 | 3 | DET-3D-01 | T-04-18,19,21,24 | `/lifter-hotswap` route (200/404/400/503) + `/lifter-select` removed (404/405) | route | `pytest tests/perception/test_lifter_routes.py tests/perception/test_lifter_hotswap.py tests/perception/test_detector_routes.py -x -q` | `backend/web/detector_routes.py`, `tests/perception/test_lifter_hotswap.py` | ⬜ pending |
| 06-T1 | 06 | 4 | DET-3D-01 | T-04-25..28 | Frontend routes lifter switch via `/lifter-hotswap`; `pollForLifterRestart` gone; restart overlay not triggered on lifter path; tsc clean | smoke | `cd frontend && npx tsc --noEmit && ! grep -q "/api/detectors/lifter-select" frontend/src/components/DetectorSection.tsx && grep -q "/api/detectors/lifter-hotswap" frontend/src/components/DetectorSection.tsx` | `frontend/src/components/DetectorSection.tsx` | ⬜ pending |
| 07-T1 | 07 | 5 | DET-3D-01 | (integration) | SC#1 ±15° yaw / 0.15m center gate on rotated chair; round-trip + non-identity quaternion asserted | integration | `pytest tests/integration/test_obb_mujoco_scene.py -x -q --timeout=120` | `tests/integration/test_obb_mujoco_scene.py` | ⬜ pending |
| 07-T2 | 07 | 5 | DET-3D-05, DET-3D-06 | T-04-31 | SC#2 DetectionBoxes.ts clean + SC#3 perception FOV locked + no cloud_config dep | smoke | `pytest tests/perception/test_no_focal_math_frontend.py -x -q` | `tests/perception/test_no_focal_math_frontend.py` | ⬜ pending |

---

## Wave 0 Requirements

- [x] `pyproject.toml` — add `scikit-learn>=1.4.0` to `perception` extra (D-02) — Plan 01 Task 1.
- [x] `tests/perception/fixtures/scene_rotated_chair.xml` — MuJoCo fixture with chair body at known yaw (D-11) — Plan 01 Task 2.
- [x] `src/perception/geometry.py` — single projection entrypoint (D-05, D-06) — Plan 02 Task 2.
- [x] `tests/perception/test_geometry.py` — unit tests for unprojection + grep invariants — Plan 02 Task 1 (RED) + Plan 03 Task 2 (post-migration extensions).

*Justification: Wave 0 ships the dependency + fixture + geometry module + tests before any consumer module changes. `PointClusterLifter` (Wave 2) requires sklearn at import time; the integration test (Wave 5) requires the MuJoCo fixture; `MedianDepthLifter` migration (Wave 1) requires `geometry.unproject_pixel_to_world`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| OBB orientation visibly changes when switching lifter via UI | SC#5 | Visual rendering, requires browser interaction | Open C2 page with rotated chair scene, switch `MedianDepth` → `PointCluster` via Lifter dropdown, confirm the OBB wireframe rotates to match the chair's orientation. |
| Hot-swap latency feels instant (no overlay) | D-09, D-10 | Perceptual latency below automated test resolution | Click "Switch Lifter", confirm NO `RestartOverlay` appears and detection continues uninterrupted. The ConfirmModal dismisses on 200 OK; next frame's OBB reflects the new lifter. |
| Open3D OBB fit produces visually-aligned box on rotated chair | SC#1 (visual) | Numerical assertion covered by ±15° / 0.15m integration test; visual gut-check still valuable | Run `pytest tests/integration/test_obb_mujoco_scene.py` locally with `rerun.io` viewer open; eyeball OBB alignment matches chair silhouette. |

*All other behaviors (geometry math, DBSCAN clustering, < 50 pixel fallback, REST routes, frontend tsc, grep invariants, concurrency race) have automated verification — see Per-Task Verification Map above.*

---

## SUMMARY Notes for VERIFICATION.md

Downstream `/gsd-verify-phase` MUST surface these two overrides in VERIFICATION.md
per 04-CONTEXT.md + 04-RESEARCH.md Open Questions:

### Override 1 — D-03: FULL-3D OBB rotation (not yaw-only, not gravity-aligned)

CONTEXT.md §D-03 intentionally OVERRIDES DET-3D-01's original "yaw-only,
gravity-aligned" wording. `PointClusterLifter` emits the FULL Open3D rotation
matrix as an xyzw quaternion via `scipy.spatial.transform.Rotation.from_matrix(R).as_quat()`.
The DET-3D-01 requirement text is amended in the Phase 4 CONTEXT scope;
gravity-alignment is dropped because it would discard real physical rotation
captured by depth clusters (tilted chairs, tables on uneven floors).

Verifier surfacing: VERIFICATION.md Phase 4 §Overrides section must cite
`04-CONTEXT.md §D-03` and `04-RESEARCH.md §Locked Decisions D-03`.

### Override 2 — D-04: SensorFrame.intrinsics field SKIPPED (existing plumbing satisfies intent)

CONTEXT.md §D-04 specifies adding an `intrinsics` field to `SensorFrame`.
04-RESEARCH.md Open Question #2 resolved this as unnecessary:

- `Detection3DProtocol.lift(frame, detection_2d, pose, intrinsics, slam_cloud)`
  already takes `CameraIntrinsics` as a separate positional argument
  (`src/perception/protocol.py:127-134`).
- `DetectorWorker._intrinsics` is already per-worker-owned
  (`src/perception/worker.py:116`).
- `DetectorWorkerPool.__init__` already accepts `intrinsics_per_robot`
  (`src/perception/worker_pool.py:113`).
- `src/main.py:641` already computes `CameraIntrinsics.from_fov(w, h)` at startup.

**No Phase 4 plan modifies `SensorFrame`.** The D-04 intent ("make intrinsics
available to the lifter at capture time") is satisfied by existing plumbing.
If a future phase needs intrinsics on `SensorFrame` specifically (e.g., for a
SLAM backend that accepts `SensorFrame` directly), that's a separate
architectural decision — deferred to Phase 6+.

Verifier surfacing: VERIFICATION.md Phase 4 §Overrides section must cite
`04-RESEARCH.md §Open Questions #2` and note the 4 existing plumbing call-sites
listed above.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (planner filled).
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every task has a dedicated pytest / tsc / python command).
- [x] Wave 0 covers all MISSING references (sklearn install, MuJoCo fixture, geometry.py, test_geometry.py).
- [x] No watch-mode flags.
- [x] Feedback latency < 60s for unit tests; < 120s for integration.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** planner (2026-04-14)
