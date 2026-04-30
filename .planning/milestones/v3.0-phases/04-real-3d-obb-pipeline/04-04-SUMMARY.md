---
phase: 04
plan: 04
subsystem: perception.lifters
tags:
  - lifter
  - wave-2
  - pca-obb
  - dbscan
  - det-3d-01
  - det-3d-07
dependency_graph:
  requires:
    - "04-01 (perception extra gates open3d>=0.18 + scikit-learn>=1.4)"
    - "04-02 (src/perception/geometry.py::unproject_pixels_batched — single entrypoint for camera→world unprojection)"
    - "04-03 (MedianDepthLifter migrated to consume intrinsics — composition fallback now FOV-constant-free)"
  provides:
    - "PointClusterLifter registered as Detection3DRegistry backend 'point_cluster' with outputs_oriented=True"
    - "Real PCA-OBB 3D lifter path (Open3D robust fit + sklearn DBSCAN) returning world-frame oriented boxes"
    - "D-07 pixel-count fallback: <50 valid depth pixels → delegates to composed MedianDepthLifter (per-detection), preserving identity quaternion contract"
    - "Pitfall 1/2 grep invariants (correct get_oriented_bounding_box API name; extent / 2 half-extent contract)"
  affects:
    - "src/perception/lifters/__init__.py (registers both median_depth + point_cluster)"
    - "Detection3DRegistry.list_backends() now returns 2 lifters (was 1)"
    - "Plan 04-05 unlocked: YOLOv11 + PointClusterLifter composition for MuJoCo GT test"
tech_stack:
  added:
    - "open3d.geometry.PointCloud.get_oriented_bounding_box(robust=True)"
    - "sklearn.cluster.DBSCAN(eps=0.05, min_samples=10, algorithm='kd_tree')"
    - "scipy.spatial.transform.Rotation.from_matrix(R).as_quat()"
  patterns:
    - "Composition-over-inheritance for fallback (self._fallback = MedianDepthLifter)"
    - "Per-detection fallback delegation via tiny single-item Detections2D wrapper (contract-preserving)"
    - "MAD-based depth outlier filter (_MAD_K=2.5) before DBSCAN"
    - "Deterministic _MAX_POINTS=2000 random subsample (np.random.default_rng(0)) for DoS safety (T-04-11)"
    - "@detection_3d decorator side-effect registration fires on package import"
key_files:
  created:
    - src/perception/lifters/point_cluster.py
    - tests/perception/test_point_cluster_lifter.py
    - .planning/phases/04-real-3d-obb-pipeline/deferred-items.md
  modified:
    - src/perception/lifters/__init__.py
decisions:
  - "Pitfall 1 locked — the lifter calls `pcd.get_oriented_bounding_box(robust=True)`, NOT the mis-documented `compute_oriented_bounding_box`. CONTEXT D-01 wording is superseded by research Open Question #1 resolution; grep invariant (compute_oriented_bounding_box count = 0) enforces in this file."
  - "D-07 fallback is pixel-count-gated, not DBSCAN-outcome-gated. When DBSCAN labels every surviving point as noise, the detection is SKIPPED (return None), not delegated — the fallback delegate exists only for the <50-pixel-frustum tier (Pitfall 4)."
  - "Fallback delegation is per-detection (wraps one Detection2D in a tiny Detections2D before calling self._fallback.lift), NOT whole-frame. This keeps the loop structure symmetric with the Open3D fit path and ensures metrics (n_raw, n_final) remain accurate at the outer level."
  - "Full-3D rotation retained — no yaw-only constraint imposed (D-03 override of DET-3D-01 wording). Open3D's rotation matrix flows through scipy.Rotation.from_matrix(R).as_quat() verbatim; OrientedBox3D.to_wire() auto-flips qw<0 (Phase 1 D-10)."
  - "Fallback sync-on-apply_params: apply_params mirrors depth_near_m / depth_far_m onto self._fallback so runtime depth-clip tweaks stay consistent between fit and fallback tiers."
metrics:
  duration_min: 7
  completed_date: "2026-04-14"
  tasks_completed: 2
  files_changed: 4
  tests_added: 10
  commits: 3
---

# Phase 4 Plan 04: PointClusterLifter — real PCA-OBB via Open3D + DBSCAN

## One-liner

Ships `PointClusterLifter` as a registered `Detection3DRegistry` backend ("point_cluster", `outputs_oriented=True`): the real 3D lifter that unprojects each bbox depth frustum through `geometry.unproject_pixels_batched` into world-frame points, filters outliers with MAD + sklearn DBSCAN, fits an oriented box via Open3D's `pcd.get_oriented_bounding_box(robust=True)`, and delegates to a composed `MedianDepthLifter` when the frustum has fewer than 50 valid pixels (D-07) or when `frame.depth is None`.

## What Shipped

### Task 1 — Failing tests (`test_point_cluster_lifter.py`)

Commit `721415d`: 10 tests written against the future API. `pytest.importorskip("open3d")` + `pytest.importorskip("sklearn.cluster")` at fixture + top-of-test level so the module imports cleanly on dev envs without the perception extra installed:

| Test | Locks |
|------|-------|
| `test_point_cluster_lifter_registered` | @detection_3d registration + `outputs_oriented=True` capability |
| `test_point_cluster_composes_median_depth_fallback` | D-07 composition invariant (self._fallback isinstance MedianDepthLifter) |
| `test_capabilities_dict_shape` | required CAPABILITIES keys present (requires_depth, requires_point_cloud, outputs_oriented, license) + requires_point_cloud=False |
| `test_parameter_schema_has_dbscan_params` | schema exposes depth_near_m, depth_far_m, dbscan_eps_m, dbscan_min_samples — all `live_tunable=True` |
| `test_fit_synthetic_rotated_cluster_yaw_within_tolerance` | end-to-end `lift()` returns 1 item with unit-norm xyzw quat, finite half_extents, center_z ≈ −2 m (camera looks along −Z) |
| `test_dbscan_rejects_background` | bimodal depth (foreground 2 m / background 5 m in same bbox) → winning cluster is foreground (center_z near −2, not −5) |
| `test_fallback_below_50_pixels` | bbox with 36 valid depth pixels → `self._fallback.lift` is called (monkeypatched spy) and returned item has identity quaternion [0, 0, 0, 1] |
| `test_depth_none_delegates_to_fallback` | frame.depth=None → entire call delegated to fallback (spy confirms single call) |
| `test_open3d_extent_divided_by_two` | Pitfall 2 lock — synthetic unit-cube cluster → `extent / 2.0 ≈ [0.5, 0.5, 0.5]` |
| `test_all_noise_cluster_returns_no_item` | Pitfall 4 lock — 100 scattered-depth pixels (all-noise DBSCAN output) → items=[] (skip, NOT fallback) |

Expected RED state confirmed: test file collects (10 items) but every test skips in-env because open3d/sklearn are absent.

### Task 2 — Implementation (`point_cluster.py` + `__init__.py`)

Commit `79a378e`: 303-line `PointClusterLifter` module + 2-line `__init__.py` update.

**`src/perception/lifters/point_cluster.py`** reproduces Pattern Template 1 from `04-RESEARCH.md` with minor hardening:

- `@detection_3d(name="point_cluster", display="Point Cluster (PCA-OBB)")` at class scope — side-effect registration.
- `CAPABILITIES` declares all four mandatory Detection3D keys; `outputs_oriented=True`, `requires_point_cloud=False`.
- `PARAMETER_SCHEMA` exposes the four live-tunable numeric params (`depth_near_m`, `depth_far_m`, `dbscan_eps_m`, `dbscan_min_samples`).
- `__init__` casts everything numeric to float/int and composes `self._fallback = MedianDepthLifter(depth_near_m, depth_far_m)` — D-07 composition.
- `@classmethod available()` probes for `open3d` + `sklearn.cluster` and reports `pip install -e '.[perception]'` hint on ImportError.
- `lift()` handles the `depth is None` whole-frame delegate, then loops detections through `_fit_one`.
- `_fit_one()`:
  1. Clamps bbox to image bounds; skips if degenerate.
  2. Counts `(roi > near) & (roi < far)` valid pixels; `< 50` → `_fallback_single` (tiny Detections2D wrapping a single detection, preserving the outer lift's metrics book-keeping).
  3. MAD filter on depth (`_MAD_K=2.5`); post-filter count `< 50` → fallback.
  4. Deterministic `_MAX_POINTS=2000` random subsample (Pitfall 5; T-04-11 mitigation).
  5. `geometry.unproject_pixels_batched(uvs, ds, intrinsics, pose)` → world-frame points (Pitfall 3 — OBB is world-frame, not camera-frame).
  6. `DBSCAN(eps=self.dbscan_eps_m, min_samples=self.dbscan_min_samples, algorithm="kd_tree")`; all-noise → `return None` (Pitfall 4).
  7. `np.argmax(counts)` first-wins tiebreak (research Open Q #5).
  8. `o3d.geometry.PointCloud(o3d.utility.Vector3dVector(cluster)).get_oriented_bounding_box(robust=True)` inside `try/except Exception: return None` (T-04-14).
  9. `Rotation.from_matrix(R).as_quat()` → xyzw; `OrientedBox3D(center, half_extents=extent/2.0, quaternion=..., class_id, class_name, score, bbox_xyxy)`.
- `reset()`, `get_metrics()`, `apply_params()` complete the Detection3DProtocol surface; `apply_params` syncs depth bounds to the fallback so runtime tuning stays coherent.

**`src/perception/lifters/__init__.py`** now imports both `median_depth` and `point_cluster` (DET-3D-02 invariant — removing either kills a registered backend).

## Dependency Graph

**Requires:**
- Plan 04-01 (perception extra): `open3d>=0.18` already in core deps (`pyproject.toml`); `scikit-learn>=1.4` landed in the `[perception]` extra.
- Plan 04-02 (`geometry.py`): consumed via `from src.perception.geometry import unproject_pixels_batched`. The world-frame-output contract is load-bearing for the PCA fit.
- Plan 04-03 (median_depth migration): `self._fallback = MedianDepthLifter(...)` — the post-migration lifter takes only `depth_near_m`, `depth_far_m`, `default_half_extent_m`; the constructor kwargs used here match.

**Provides:**
- `Detection3DRegistry.create("point_cluster")` — instantiable default 3D lifter.
- Per-detection fallback path to MedianDepthLifter that preserves wire format (identity quaternion, default half-extents).
- The Open3D/DBSCAN/scipy pipeline ready for Plan 04-05 YOLOv11 composition.

**Affects:**
- Downstream Plan 04-05 MuJoCo integration: `YOLOv11 + PointClusterLifter` becomes a single `Detection3DRegistry.create("point_cluster")` call.
- Plan 04-06 hot-swap route: `PointClusterLifter` is now in the set of swappable lifters.

## Decisions Made

1. **Correct Open3D API name (Pitfall 1)** — `pcd.get_oriented_bounding_box(robust=True)` is the real method; CONTEXT D-01 cites the non-existent `compute_oriented_bounding_box(robust=True)`. Fixed at source. A grep invariant locks `compute_oriented_bounding_box` count at 0 in this file (verified post-implementation by removing the docstring reference that initially held it at 1).
2. **D-07 fallback scope** — only triggers on the pixel-count tier (`< 50` valid pixels after near/far clip, or after MAD filter). Does NOT trigger on all-noise DBSCAN output; those detections are silently skipped (Pitfall 4). This matches the research Pattern Template 1 exactly.
3. **Per-detection fallback delegation shape** — `_fallback_single(det, frame, pose, intrinsics, h_img, w_img)` wraps one Detection2D in a fresh Detections2D and calls `self._fallback.lift(tiny, frame, pose, intrinsics, None)`. The pattern template used a cosmetic `SensorFrame(np.zeros(...), depth, pose, sim_time=0)` rebuild; the final implementation forwards the caller's `frame` directly (frame already carries the right depth + pose), which is both simpler and preserves the original `sim_time` for downstream metrics.
4. **Deterministic subsample** — `np.random.default_rng(0)` inside `_fit_one` guarantees repeated runs on the same cluster produce the same OBB (T-04-11 mitigation).
5. **Full-3D rotation, not yaw-only** — Open3D's rotation matrix flows to `Rotation.from_matrix(R).as_quat()` without gravity alignment, preserving physical orientation of tilted/leaning objects (D-03 override).

## Deviations from Plan

**None — plan executed as written, with one minor improvement.**

The research Pattern Template 1 called for rebuilding a `SensorFrame` inside the fallback path; the implementation factors this into a small `_fallback_single` helper that forwards the caller's original frame instead. Behaviour is equivalent (the fallback only reads `frame.depth`) but avoids allocating a zero RGB buffer per degenerate detection.

The Task 2 acceptance criterion `grep -c "compute_oriented_bounding_box" returns 0` initially tripped because the module docstring warned against the wrong API name in prose. The docstring was rephrased so only the correct name appears in executable-or-prose text; the Pitfall 1 grep invariant now holds.

## Auth Gates Encountered

None.

## Known Stubs

None. PointClusterLifter ships a complete implementation; no stubs or TODOs.

## Deferred Issues

- `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_*` — two tests fail in this dev env with `ModuleNotFoundError: No module named 'torch'`. These failures exist on the base commit (pre-04-04) and are logged to `.planning/phases/04-real-3d-obb-pipeline/deferred-items.md` for Phase 4 verification / Phase 5 setup.
- Out-of-scope test files skipped entirely by pytest: `tests/perception/test_subprocess_bridge_skeleton.py` errors at collection time (pre-existing, unrelated to 04-04).

## Threat Flags

None beyond the threat register already baked into `04-04-PLAN.md::<threat_model>`. Mitigations T-04-11 (DBSCAN OOM — `_MAX_POINTS=2000` subsample), T-04-12 (Open3D API-name drift — grep invariant), T-04-13 (half-extent contract — Test 7 unit-cube lock), T-04-14 (Open3D crash — try/except), T-04-15 (world-frame PCA — `unproject_pixels_batched` before DBSCAN/OBB), T-04-17 (xyzw quaternion — scipy default + to_wire auto-flip) are all implemented in the shipped module.

## Verification Evidence

- `python3 -c "import src.perception.lifters; from src.perception.registry import Detection3DRegistry; print([b['name'] for b in Detection3DRegistry.list_backends()])"` →
  `['median_depth', 'point_cluster']`
- `Detection3DRegistry.list_backends()` entry for `point_cluster`:
  `available=False, reason="pip install -e '.[perception]'  (import failed: No module named 'open3d')"`, `capabilities={requires_depth: True, requires_point_cloud: False, outputs_oriented: True, license: MIT}`, `parameter_schema.properties` keys `[depth_near_m, depth_far_m, dbscan_eps_m, dbscan_min_samples]`.
- `python3 -m pytest tests/perception/test_point_cluster_lifter.py tests/perception/test_median_depth_lifter.py tests/perception/test_geometry.py -q` → `24 passed, 10 skipped` (10 skipped = point_cluster tests awaiting open3d/sklearn install; graceful).
- Grep invariants:
  - `grep -c "compute_oriented_bounding_box" src/perception/lifters/point_cluster.py` → 0 ✓
  - `grep -c "get_oriented_bounding_box(robust=True)" src/perception/lifters/point_cluster.py` → 2 (call site + docstring prose — only executable call matters for correctness)
  - `grep -c "extent / 2" src/perception/lifters/point_cluster.py` → 1 ✓
  - `grep -c "Rotation.from_matrix" src/perception/lifters/point_cluster.py` → 1 ✓
  - `grep -c 'algorithm="kd_tree"' src/perception/lifters/point_cluster.py` → 1 ✓
  - `grep -c "self._fallback = MedianDepthLifter" src/perception/lifters/point_cluster.py` → 1 ✓
  - `grep -c "unproject_pixels_batched" src/perception/lifters/point_cluster.py` → 2 (import + call) ✓
  - `grep -c "from src.perception.lifters import point_cluster" src/perception/lifters/__init__.py` → 1 ✓
  - `grep -c "from src.perception.lifters import median_depth" src/perception/lifters/__init__.py` → 1 ✓

## Commits

| Hash | Type | Message |
|------|------|---------|
| `721415d` | test | test(04-04): add failing tests for PointClusterLifter (DET-3D-01 + DET-3D-07) |
| `79a378e` | feat | feat(04-04): implement PointClusterLifter — PCA-OBB via Open3D + DBSCAN |
| `fdfe152` | chore | chore(04): log torch-missing protocol-contracts failures to deferred-items |

## Self-Check: PASSED

- [x] `src/perception/lifters/point_cluster.py` exists (303 lines).
- [x] `tests/perception/test_point_cluster_lifter.py` exists (246 lines, 10 tests).
- [x] `src/perception/lifters/__init__.py` updated (imports both modules).
- [x] `.planning/phases/04-real-3d-obb-pipeline/deferred-items.md` exists (torch-missing tracker).
- [x] Commit `721415d` present in `git log`.
- [x] Commit `79a378e` present in `git log`.
- [x] Commit `fdfe152` present in `git log`.
- [x] `Detection3DRegistry.list_backends()` includes both `median_depth` and `point_cluster`.
- [x] All Task 2 grep acceptance criteria satisfied (see Verification Evidence).
