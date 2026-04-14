# Phase 4: real-3d-obb-pipeline — Research

**Researched:** 2026-04-14
**Domain:** 3D oriented bounding box fitting via PCA on depth-frustum point clusters, single-source geometry consolidation, hot-swap lifter ref replacement
**Confidence:** HIGH

## Summary

Phase 4 replaces the Phase 1/2 placeholder `MedianDepthLifter` (identity-quaternion boxes) with a real `PointClusterLifter` that unprojects a bbox depth frustum, rejects background with DBSCAN, and fits an oriented 3D box via Open3D's PCA-on-convex-hull routine. The oriented box rotation is converted to the xyzw quaternion format already locked on the wire since Phase 2. The phase also (a) consolidates all pinhole projection math into a new `src/perception/geometry.py` so the `_LEGACY_FOV_DEG = 70.0` at `median_depth.py:43` is deleted, (b) replaces the Phase 3 `/lifter-select` restart flow with a new `/lifter-hotswap` endpoint that atomic-ref-swaps the pool's per-worker lifter instance (no warmup, no restart), and (c) ships a MuJoCo GT fixture `scene_rotated_chair.xml` whose test asserts yaw < ±15° and center < 0.15 m against `mj_data.body("chair").xpos/xquat`.

Every upstream contract the phase needs already exists: `CameraIntrinsics` is a first-class dataclass (`src/bridge/sensor_types.py:68`), `Detection3DProtocol.lift(frame, detection_2d, pose, intrinsics, slam_cloud)` already takes intrinsics as a separate positional argument (`src/perception/protocol.py:127`), `DetectorWorker._intrinsics` is already per-worker-owned (`src/perception/worker.py:116`), and the frontend OBB renderer (`DetectionBoxes.ts:102-103`) already applies wire quaternions verbatim with no back-projection. SC#2 is therefore **already passing on main** — Phase 4's SC#2 work is grep-invariant protection, not deletion. The wire format (xyzw, qw>=0) is locked by Phase 1 D-10 and Phase 2 SC#4.

**Primary recommendation:** ship Phase 4 as a 4-wave sequence — (Wave 0) stand up `geometry.py` + DBSCAN dep + MuJoCo chair fixture; (Wave 1) migrate `MedianDepthLifter` onto `geometry.py` and delete `_LEGACY_FOV_DEG`; (Wave 2) implement `PointClusterLifter` with `MedianDepthLifter` composition fallback; (Wave 3) swap the REST surface from `/lifter-select` to `/lifter-hotswap` with `DetectorWorkerPool.swap_lifter()` under a pool-level lock, redirect the frontend, and ship the MuJoCo integration test.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (OBB fitter):** Open3D `compute_oriented_bounding_box(robust=True)` — per CONTEXT wording. **See Open Question #1 below — the actual Open3D API is `get_oriented_bounding_box(robust=True)`.** [VERIFIED: open3d.org 0.18/0.19 docs + multiple search results]. Treat CONTEXT's `compute_*` as a shorthand; plan writes `get_oriented_bounding_box(robust=True)`. Convert the returned `OrientedBoundingBox.R` (3×3) via `scipy.spatial.transform.Rotation.from_matrix(R).as_quat()` (xyzw by default) before constructing `OrientedBox3D`. `OrientedBox3D.to_wire()` auto-flips qw<0 per Phase 1 D-10.
- **D-02 (DBSCAN):** sklearn `DBSCAN(eps=0.05, min_samples=10).fit_predict(points_xyz)`. Add `scikit-learn>=1.4.0` to `perception` extra in `pyproject.toml` [CITED: https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html]. Noise label is `-1`; cluster labels are non-negative ints.
- **D-03 (Rotation DOF):** FULL 3D OBB rotation (not yaw-only). Overrides DET-3D-01's "yaw-only, gravity-aligned" wording. Verifier MUST check this override is surfaced in VERIFICATION.md.
- **D-04 (Intrinsics source):** SensorFrame gains an `intrinsics` field. **See Open Question #2 below — `CameraIntrinsics` is already plumbed as a separate argument through `Detection3DProtocol.lift` and `DetectorWorker`; adding it to `SensorFrame` is either a redundancy or a scope creep.** Planner resolves.
- **D-05 (geometry.py API):** Both `unproject_pixel_to_world(u, v, depth, intrinsics, pose) -> (3,)` and `unproject_pixels_batched(uvs, depths, intrinsics, pose) -> (N,3)`. Stateless functions — no class wrapper.
- **D-06 (single projection entrypoint):** `src/perception/geometry.py` is the only projection module. Grep invariant `grep -rn "fov\|FOV\|focal" src/perception/` returns ONLY docstring hits in `geometry.py`. `_LEGACY_FOV_DEG = 70.0` deleted from `median_depth.py:43`.
- **D-07 (Fallback shape):** `PointClusterLifter.__init__` holds `self._fallback = MedianDepthLifter(...)` via composition. When valid depth pixels < 50, delegates to `self._fallback.lift(...)` and stamps `outputs_oriented=False` semantics on the returned envelope.
- **D-08 (Wire signaling):** `outputs_oriented` is envelope-level (capability on the lifter class), NOT per-box. Fallback box retains identity quaternion `[0, 0, 0, 1]`; no per-item flag.
- **D-09 (HOT-SWAP, supersedes Phase 3 D-09):** Switching lifter does NOT restart workers. New `POST /api/detectors/lifter-hotswap {lifter, params?}`. The Phase 3 `POST /api/detectors/lifter-select` route is REMOVED.
- **D-10 (Hot-swap atomicity):** `DetectorWorkerPool.swap_lifter(new_lifter_name, new_params)` acquires a pool lock, constructs a fresh lifter per worker via `Detection3DRegistry.create`, replaces `worker._lifter` on each worker, then releases. Workers reading the ref during inference see either old-or-new (never a torn half-constructed lifter). Lock duration ≪ 1 ms.
- **D-11 (MuJoCo GT fixture):** `tests/perception/fixtures/scene_rotated_chair.xml` places body `chair` at known non-zero yaw. Test renders one RGBD frame, runs YOLOv11 → PointClusterLifter, asserts yaw error < ±15°, center error < 0.15 m, `outputs_oriented=True` in envelope, and OBB round-trip ±1e-6.

### Claude's Discretion

- Exact DBSCAN cluster tiebreak when ≥2 clusters share max size (recommendation below: largest by point count; ties broken by closest-to-bbox-center).
- Point count cap before DBSCAN (recommendation below: 2000 random-sampled points if bbox frustum > 2000 valid pixels — protects 33 ms budget).
- MAD filter bandwidth for pre-DBSCAN depth outlier rejection (recommendation below: depth within 2.5 × MAD of median).
- Exact shape of `CameraIntrinsics` argument to `geometry.py` (reuse the existing `CameraIntrinsics` dataclass; do NOT introduce a separate tuple form — one type to grep).
- DBSCAN algorithm kwarg (recommendation: `algorithm='kd_tree'` — empirically fastest for 3D data per sklearn docs).
- Test scene lighting and chair mesh source for `scene_rotated_chair.xml` (recommendation: MuJoCo primitive boxes parented to a body, no mesh dependency — keeps fixture lightweight and CI-friendly).

### Deferred Ideas (OUT OF SCOPE)

- Multi-frame OBB tracking / smoothing — Phase 6
- Lifter parameter UI panel — Phase 7
- Per-class lifter dispatch — Phase 8 stretch
- DBSCAN replacement with HDBSCAN/OPTICS — only if SC#1 gates fail
- GPU-accelerated Open3D OBB — only if 33 ms budget regresses
- Yaw-only constraint — REJECTED per D-03
- Per-box `outputs_oriented` flag — REJECTED per D-08

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DET-3D-01 | `PointClusterLifter` default — MAD + DBSCAN + Open3D robust PCA-OBB (yaw-only wording AMENDED per D-03 to full-3D) | Pattern Template 1 below; SC#1 MuJoCo GT gate ±15° / 0.15 m |
| DET-3D-02 | `MedianDepthLifter` kept as legacy, `outputs_oriented=False` | Already registered `@detection_3d("median_depth", ...)` — Phase 4 does NOT change registration; composition in `PointClusterLifter._fallback` reuses it |
| DET-3D-05 | Frontend renders from wire, no focal-length back-projection | Already PASS on main (`DetectionBoxes.ts:87-116` uses raw quaternion + half_extents); Phase 4 adds grep-invariant test to lock the invariant |
| DET-3D-06 | Single projection path in `src/perception/geometry.py` | New module per D-05; deletes `_LEGACY_FOV_DEG = 70.0` at `median_depth.py:43` |
| DET-3D-07 | Fallback to `MedianDepthLifter` at < 50 valid depth pixels | D-07 composition; unit test in `tests/perception/test_point_cluster_lifter.py` |

## Project Constraints (from CLAUDE.md)

None — `/home/prannayag/pragnition/robotics/argus/CLAUDE.md` does not exist. Project-level conventions are encoded in per-phase CONTEXT.md files and the `desloppify` skill (code-health scanning — not authority over phase planning).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| open3d | >=0.18.0 (already pinned in pyproject.toml dependencies) | `get_oriented_bounding_box(robust=True)` PCA-OBB fit | Already a top-level dep; `robust=True` mode degrades gracefully on small/degenerate clusters; widely used for depth-camera pipelines [VERIFIED: pyproject.toml:8] |
| scikit-learn | >=1.4.0 (NEW — add to `perception` extra) | DBSCAN cluster rejection on 3D points | Exact fit for D-02; `fit_predict` returns integer labels with `-1 = noise`; `kd_tree` algorithm is sub-linear for 3D [VERIFIED: npm/pypi index shows 1.8.0 current, 1.4.0 released Jan 2024 — safe floor] |
| scipy | >=1.15.0 (already pinned) | `Rotation.from_matrix(R).as_quat()` — xyzw scalar-last default matches wire format | Project already uses scipy.spatial.transform.Rotation (see `tests/conftest.py:53`). `as_quat(scalar_first=False)` is default and matches `OrientedBox3D.quaternion` xyzw convention [VERIFIED: scipy 1.17 docs + project usage] |
| numpy | >=1.26.0 (already pinned) | Point array math, MAD filter | Baseline dep |
| mujoco | >=3.0.0 (already pinned) | GT fixture rendering + `data.body("chair").xpos/xquat` | Already a top-level dep; `data.body(name).xpos` is the MuJoCo 3.x named-access API for body world-frame position, `.xquat` for orientation (wxyz in MuJoCo convention) [CITED: mujoco.readthedocs.io/en/stable/python.html] |

**Version verification (2026-04-14):**
```bash
pip index versions scikit-learn   # -> 1.8.0 latest; 1.4.0 floor is safe (Jan 2024)
pip index versions scipy          # -> 1.17.1 latest; 1.15.0 floor already in pyproject
pip index versions mujoco         # -> 3.6.0 latest; 3.0.0 floor already in pyproject
# open3d: not available on this network but pinned in project to >=0.18.0 (0.19.0 current upstream)
```

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0.0 (already in dev extra) | All unit + integration tests | Standard |
| msgpack / pyzmq | already pinned | Unrelated — subprocess bridge, not Phase 4 | N/A |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Open3D `get_oriented_bounding_box(robust=True)` | Open3D `get_minimal_oriented_bounding_box(robust=True)` | Smaller-volume fit via edge-aligned search; more expensive; unnecessary for indoor-furniture scale — rejected |
| sklearn DBSCAN | HDBSCAN | Better when cluster densities vary; adds dep; over-engineering for indoor depth frustums — defer per CONTEXT |
| scipy `Rotation.from_matrix` | Hand-rolled R→quat | Hand-rolled is sign-buggy; scipy already in deps — no contest |
| MuJoCo chair mesh | Primitive-box chair geom | Mesh requires assets; primitive is self-contained, reproducible, and sufficient for YOLO "chair" classification (YOLOv11 classifies by silhouette; a box-chair parented body still triggers the `chair` class at reasonable confidence). Recommendation: use primitives. |

**Installation (additive delta):**
```toml
# pyproject.toml — extend existing perception extra
[project.optional-dependencies]
perception = [
    "torch>=2.10.0",
    "transformers>=5.3.0",
    "ultralytics>=8.4.24",
    "scikit-learn>=1.4.0",   # NEW — Phase 4 DBSCAN
]
```

## Architecture Patterns

### Recommended Project Structure

```
src/perception/
├── geometry.py                   # NEW — unproject_pixel_to_world + unproject_pixels_batched
├── lifters/
│   ├── median_depth.py           # MODIFIED — drop _LEGACY_FOV_DEG, use geometry.unproject_pixel_to_world
│   ├── point_cluster.py          # NEW — PointClusterLifter(@detection_3d) + MAD filter + DBSCAN + Open3D OBB
│   └── __init__.py               # MODIFIED — import both so @detection_3d side-effect registration fires
└── worker_pool.py                # MODIFIED — add swap_lifter(name, params)
backend/web/
└── detector_routes.py            # MODIFIED — REMOVE /lifter-select; ADD /lifter-hotswap
frontend/src/components/
└── DetectorSection.tsx           # MODIFIED — onConfirmLifterSwitch posts to /lifter-hotswap (see also: drop ConfirmModal restart language, drop setRestartSubsystem('lifter'), drop pollForLifterRestart)
frontend/src/stores/
└── detectorStore.ts              # UNCHANGED — restartSubsystem discriminator remains for detector path; lifter path no longer uses it
tests/perception/
├── fixtures/
│   └── scene_rotated_chair.xml   # NEW — MuJoCo body "chair" at known yaw
├── test_geometry.py              # NEW — unit test unproject round-trip
├── test_point_cluster_lifter.py  # NEW — unit + MuJoCo integration
├── test_lifter_hotswap.py        # NEW — concurrency test (hot-swap under 30 Hz submit)
└── test_median_depth_lifter.py   # MODIFIED — drop tests for _LEGACY_FOV_DEG constant
```

### Pattern Template 1: `PointClusterLifter.lift()`

```python
# src/perception/lifters/point_cluster.py (NEW — target ~180 LOC)
from __future__ import annotations
import logging
import time
from typing import Any

import numpy as np
from scipy.spatial.transform import Rotation

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.geometry import unproject_pixels_batched
from src.perception.lifters.median_depth import MedianDepthLifter
from src.perception.registry import detection_3d
from src.perception.types import Detections2D, Detections3D, OrientedBox3D

_FALLBACK_PIXEL_FLOOR = 50   # D-07 — below this, delegate to MedianDepthLifter
_MAX_POINTS = 2000           # Safeguard DBSCAN runtime; random-subsample above this
_MAD_K = 2.5                 # Drop depth values beyond 2.5 * MAD from median

_IDENTITY_QUAT = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)


@detection_3d(name="point_cluster", display="Point Cluster (PCA-OBB)")
class PointClusterLifter:
    CAPABILITIES: dict = {
        "requires_depth": True,
        "requires_point_cloud": False,          # slam_cloud acceptable but unused (Open Question #3)
        "outputs_oriented": True,               # D-08 envelope-level capability
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "depth_near_m":    {"type": "number", "default": 0.1,  "minimum": 0.01, "maximum": 1.0,  "live_tunable": True},
            "depth_far_m":     {"type": "number", "default": 15.0, "minimum": 1.0,  "maximum": 50.0, "live_tunable": True},
            "dbscan_eps_m":    {"type": "number", "default": 0.05, "minimum": 0.01, "maximum": 0.5,  "live_tunable": True},
            "dbscan_min_samples": {"type": "integer", "default": 10, "minimum": 3,  "maximum": 50,  "live_tunable": True},
        },
    }

    def __init__(self,
                 depth_near_m: float = 0.1, depth_far_m: float = 15.0,
                 dbscan_eps_m: float = 0.05, dbscan_min_samples: int = 10) -> None:
        self.depth_near_m = depth_near_m
        self.depth_far_m = depth_far_m
        self.dbscan_eps_m = dbscan_eps_m
        self.dbscan_min_samples = dbscan_min_samples
        # D-07 composition — same defaults as standalone MedianDepthLifter
        self._fallback = MedianDepthLifter(depth_near_m=depth_near_m, depth_far_m=depth_far_m)
        self._last_ms = 0.0
        self._last_n_raw = 0
        self._last_n_final = 0

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        try:
            import open3d  # noqa: F401
            import sklearn.cluster  # noqa: F401
        except ImportError as exc:
            return False, f"pip install open3d scikit-learn  (import failed: {exc})"
        return True, None

    def lift(self, detections_2d: Detections2D, frame: SensorFrame,
             pose: np.ndarray, intrinsics: CameraIntrinsics,
             slam_cloud: np.ndarray | None) -> Detections3D:
        t0 = time.perf_counter()
        items: list[OrientedBox3D] = []
        n_raw = len(detections_2d.items)
        depth = frame.depth
        # Fallback path 1 — no depth channel at all
        if depth is None or depth.ndim != 2:
            return self._fallback.lift(detections_2d, frame, pose, intrinsics, slam_cloud)

        for det in detections_2d.items:
            obb = self._fit_one(det, depth, pose, intrinsics)
            if obb is None:
                continue                                     # silently drop degenerate boxes
            items.append(obb)
        self._last_ms = (time.perf_counter() - t0) * 1000.0
        self._last_n_raw = n_raw
        self._last_n_final = len(items)
        return Detections3D(
            items=items, lifter_ms=self._last_ms, detector_ms=detections_2d.inference_ms,
            n_raw=n_raw, n_final=len(items), image_hw=detections_2d.image_hw,
        )

    def _fit_one(self, det, depth, pose, intrinsics) -> OrientedBox3D | None:
        from sklearn.cluster import DBSCAN
        import open3d as o3d

        x1, y1, x2, y2 = det.bbox_xyxy
        h_img, w_img = depth.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img, x2), min(h_img, y2)
        if x2 <= x1 or y2 <= y1:
            return None
        roi = depth[y1:y2, x1:x2]
        valid_mask = (roi > self.depth_near_m) & (roi < self.depth_far_m)
        n_valid = int(valid_mask.sum())

        # D-07 — fewer than 50 valid depth pixels → delegate to MedianDepthLifter.
        # Call _fallback.lift on a single-detection Detections2D to preserve contract.
        if n_valid < _FALLBACK_PIXEL_FLOOR:
            tiny = Detections2D(items=[det], inference_ms=0.0, image_hw=(h_img, w_img))
            fb = self._fallback.lift(tiny, SensorFrame(
                rgb=np.zeros((h_img, w_img, 3), np.uint8),
                depth=depth, ground_truth_pose=pose, sim_time=0.0,
            ), pose, intrinsics, None)
            return fb.items[0] if fb.items else None

        # Build (u, v, d) arrays of valid pixels.
        vs, us = np.nonzero(valid_mask)
        us = us + x1
        vs = vs + y1
        ds = roi[valid_mask]

        # MAD outlier filter in depth — drop pixels > _MAD_K * MAD from median.
        d_med = np.median(ds)
        mad = np.median(np.abs(ds - d_med)) + 1e-9
        keep = np.abs(ds - d_med) < _MAD_K * mad
        us, vs, ds = us[keep], vs[keep], ds[keep]
        if us.size < _FALLBACK_PIXEL_FLOOR:
            tiny = Detections2D(items=[det], inference_ms=0.0, image_hw=(h_img, w_img))
            fb = self._fallback.lift(tiny, ..., None)   # same fallback shape as above
            return fb.items[0] if fb.items else None

        # Subsample for DBSCAN runtime safety.
        if us.size > _MAX_POINTS:
            rng = np.random.default_rng(0)
            idx = rng.choice(us.size, size=_MAX_POINTS, replace=False)
            us, vs, ds = us[idx], vs[idx], ds[idx]

        # Unproject to world via single geometry entrypoint.
        uvs = np.stack([us, vs], axis=1).astype(np.float64)
        world_pts = unproject_pixels_batched(uvs, ds.astype(np.float64), intrinsics, pose)
        # world_pts shape: (N, 3)

        # DBSCAN cluster rejection.
        labels = DBSCAN(eps=self.dbscan_eps_m,
                        min_samples=self.dbscan_min_samples,
                        algorithm="kd_tree").fit_predict(world_pts)
        # Discretion tiebreak — largest cluster wins; ignore noise label (-1).
        unique, counts = np.unique(labels[labels >= 0], return_counts=True)
        if unique.size == 0:
            return None
        best_label = unique[int(np.argmax(counts))]
        cluster = world_pts[labels == best_label]
        if cluster.shape[0] < self.dbscan_min_samples:
            return None

        # Open3D PCA-OBB with robust=True (D-01).
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(cluster))
        try:
            o_obb = pcd.get_oriented_bounding_box(robust=True)
        except Exception:
            return None
        R = np.asarray(o_obb.R, dtype=np.float64)         # (3,3)
        center = np.asarray(o_obb.center, dtype=np.float64)   # (3,)
        extent = np.asarray(o_obb.extent, dtype=np.float64)   # (3,) full lengths
        # Convert to xyzw; OrientedBox3D.to_wire() will auto-flip qw<0 per D-10.
        quat_xyzw = Rotation.from_matrix(R).as_quat()     # default scalar_first=False → xyzw

        return OrientedBox3D(
            center=center,
            half_extents=extent / 2.0,                      # HALF extents per OrientedBox3D contract
            quaternion=quat_xyzw.astype(np.float64),
            class_id=det.class_id,
            class_name=det.class_name,
            score=det.score,
            track_id=None,
            bbox_xyxy=det.bbox_xyxy,
        )

    def reset(self) -> None:
        self._fallback.reset()
        self._last_ms = 0.0; self._last_n_raw = 0; self._last_n_final = 0

    def get_metrics(self) -> dict:
        return {"last_lifter_ms": self._last_ms, "n_raw": self._last_n_raw, "n_final": self._last_n_final}

    def apply_params(self, params: dict) -> dict:
        status: dict[str, str] = {}
        for k, v in params.items():
            if k in ("depth_near_m", "depth_far_m", "dbscan_eps_m"):
                setattr(self, k, float(v)); status[k] = "applied"
            elif k == "dbscan_min_samples":
                self.dbscan_min_samples = int(v); status[k] = "applied"
            else:
                status[k] = "unknown_parameter"
        # Keep the fallback's depth bounds in sync.
        self._fallback.depth_near_m = self.depth_near_m
        self._fallback.depth_far_m = self.depth_far_m
        return status
```

**Key shape invariants:**

- Open3D `OrientedBoundingBox.extent` is FULL side lengths, not half-extents — divide by 2 before assigning to `OrientedBox3D.half_extents` [VERIFIED: open3d docs].
- scipy `Rotation.as_quat()` default is `scalar_first=False` → xyzw — matches wire format [VERIFIED: scipy.spatial.transform docs; `tests/conftest.py:53` uses the same path].
- `OrientedBox3D.to_wire()` auto-flips qw<0 — PointClusterLifter does NOT need to canonicalize.

### Pattern Template 2: `src/perception/geometry.py` (NEW)

```python
# src/perception/geometry.py (NEW — target ~60 LOC)
"""Single projection entrypoint per DET-3D-06 / CONTEXT D-05, D-06.

Stateless pinhole unprojection. No FOV constants; callers pass CameraIntrinsics.
Per D-06, this module MUST be the only place in src/perception/ that mentions
focal length / FOV in executable code. Docstrings may reference these concepts.
"""
from __future__ import annotations
import numpy as np
from src.bridge.sensor_types import CameraIntrinsics


def unproject_pixel_to_world(u: float, v: float, depth: float,
                             intrinsics: CameraIntrinsics,
                             pose: np.ndarray) -> np.ndarray:
    """Unproject one pixel (u, v, depth_m) into the world frame.

    Convention matches the legacy median_depth.py sign flip for MuJoCo camera
    frame (OpenCV optical: +x right, +y DOWN, +z INTO scene). The cam frame
    point is (cam_x, -cam_y, -depth) before applying the pose R * p + t.
    Tests in tests/perception/test_geometry.py lock this convention.
    """
    fx, fy, cx, cy = intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy
    cam_x = (u - cx) * depth / fx
    cam_y = (v - cy) * depth / fy
    cam_pt = np.array([cam_x, -cam_y, -depth], dtype=np.float64)
    return pose[:3, :3] @ cam_pt + pose[:3, 3]


def unproject_pixels_batched(uvs: np.ndarray, depths: np.ndarray,
                             intrinsics: CameraIntrinsics,
                             pose: np.ndarray) -> np.ndarray:
    """Vectorized unprojection. uvs: (N, 2) float; depths: (N,) float. Returns (N, 3)."""
    fx, fy, cx, cy = intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy
    u, v = uvs[:, 0], uvs[:, 1]
    cam_x = (u - cx) * depths / fx
    cam_y = (v - cy) * depths / fy
    cam_pts = np.stack([cam_x, -cam_y, -depths], axis=1)                      # (N, 3)
    world_pts = cam_pts @ pose[:3, :3].T + pose[:3, 3]                         # (N, 3)
    return world_pts
```

### Pattern Template 3: `DetectorWorkerPool.swap_lifter()` (MODIFICATION)

```python
# src/perception/worker_pool.py — add AFTER existing methods
def swap_lifter(self, new_lifter_name: str, new_lifter_params: dict | None = None) -> None:
    """Hot-swap the lifter on every worker atomically (D-09 / D-10).

    Per D-10:
      - construct a FRESH lifter per worker via Detection3DRegistry.create (so
        per-worker-instance separation is preserved);
      - hold a pool-scoped Lock during the ref swap (≪ 1 ms);
      - workers reading `self._lifter` inside their _loop will see either the
        old or the new ref — never a torn state — because Python reference
        assignment is atomic under the GIL.

    Intentionally does NOT call warmup — lifters are stateless geometry + small
    constructor state; first call on the new lifter completes within budget.
    """
    from src.perception.registry import Detection3DRegistry
    import src.perception.lifters  # noqa: F401  — side-effect registration

    lifter_kwargs = dict(new_lifter_params or {})
    # Validate name before touching any worker (fail loudly, no partial swap).
    new_lifters = {rid: Detection3DRegistry.create(new_lifter_name, **lifter_kwargs)
                   for rid in self._workers}
    with self._swap_lock:              # NEW — self._swap_lock = threading.Lock() in __init__
        for rid, w in self._workers.items():
            w._lifter = new_lifters[rid]   # direct attribute write — GIL makes this atomic
        self.lifter_name = new_lifter_name
        self._lifter_params = lifter_kwargs
```

**Concurrency note:** Python's GIL guarantees that a single attribute assignment (`w._lifter = new`) is atomic. A worker thread reading `self._lifter` inside `_loop` will see either the old or the new object, never a half-constructed one. The pool-level `_swap_lock` exists only to serialize concurrent calls to `swap_lifter` itself (e.g., two simultaneous REST calls) — it is NOT needed for read-side safety [VERIFIED: CPython semantics, standard pattern for immutable-ref hot-swap].

### Pattern Template 4: `POST /api/detectors/lifter-hotswap` route

```python
# backend/web/detector_routes.py — REPLACE the /lifter-select block
@router.post("/lifter-hotswap")
async def lifter_hotswap(req: LifterSelectRequest, request: Request):
    """Atomic lifter ref swap — no restart, no warmup (D-09, D-10)."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry

    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    if req.lifter not in lifters:
        raise HTTPException(status_code=404, detail=f"Unknown lifter: {req.lifter}")
    if not lifters[req.lifter]["available"]:
        raise HTTPException(status_code=400,
                            detail=f"Lifter unavailable: {lifters[req.lifter].get('reason', 'unknown')}")

    pool = getattr(request.app.state, "detector_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Detector pool not initialized")
    pool.swap_lifter(req.lifter, req.params or {})

    # Update state so GET /active-lifter reflects the new lifter.
    request.app.state.active_lifter = req.lifter
    if req.params:
        request.app.state.pending_lifter_params = req.params
    return {"status": "swapped", "lifter": req.lifter}
```

**Open question on `app.state.detector_pool`:** Today `coordinator._detector_pool` is set in `src/main.py:551` but not mirrored to `app.state.detector_pool`. The hot-swap route needs direct access to the pool. Planner MUST decide between (a) setting `app.state.detector_pool = detector_pool` inside the restart block, or (b) going through `command_callback({"action": "lifter_hotswap", ...})` like the detector-select does. Recommendation: (a) — simpler, one-write one-read, avoids the restart-trigger machinery for a non-restart operation. Document this in VERIFICATION.md.

### Pattern Template 5: `DetectorSection.tsx::onConfirmLifterSwitch` redirect

```typescript
// frontend/src/components/DetectorSection.tsx — REPLACE body of onConfirmLifterSwitch (lines 175-224)
const onConfirmLifterSwitch = useCallback(async () => {
  if (!pendingLifter) return;
  setSwitching(true);
  const picked = useDetectorStore.getState().lifters.find((l) => l.name === pendingLifter);
  const pickedDisplay = picked?.display ?? pendingLifter;
  const params = useDetectorStore.getState().stagedLifterParams;
  const body: Record<string, unknown> = { lifter: pendingLifter };
  if (Object.keys(params).length > 0) body.params = params;
  try {
    const res = await fetch('/api/detectors/lifter-hotswap', {     // D-09 — new route
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setShowLifterModal(false);
    setSwitching(false);
    if (!res.ok) {
      useDetectorStore.getState().setError(
        `Failed to swap lifter to ${pickedDisplay}. The previous lifter is still active.`,
      );
      return;
    }
    useDetectorStore.getState().clearStagedLifterParams();
    // D-09: hot-swap returns 200 immediately — no overlay, no polling. Just refetch state.
    fetchDetectorState();
  } catch {
    setShowLifterModal(false);
    setSwitching(false);
    useDetectorStore.getState().setError(
      `Failed to swap lifter to ${pickedDisplay}. The previous lifter is still active.`,
    );
  }
  setPendingLifter(null);
}, [pendingLifter]);
```

**Deletions required in `DetectorSection.tsx`:**
- `useDetectorStore.getState().setRestarting(true)` / `setRestartSubsystem('lifter')` — delete the lifter-path usages at lines 185-186, 207, 220.
- `pollForLifterRestart(pendingLifter)` — delete the call at line 212 and the function body (no more polling for lifter).
- `ConfirmModal` copy for lifter switch: change from "This will restart the current session." to "This will hot-swap the lifter (no restart)."

**SceneViewer / RestartOverlay:** The lifter branch of the restart overlay discriminator is dead code after Phase 4. The 'lifter' discriminant value in `restartSubsystem: 'detector' | 'lifter' | null` can remain in the type union (no harm) or be pruned (type-clean); Claude's discretion.

### Anti-Patterns to Avoid

- **Hand-rolling R→quaternion conversion.** scipy is already a dep; sign conventions are a footgun (see [scipy/scipy#19649](https://github.com/scipy/scipy/issues/19649) — people have gotten this wrong historically). Use `Rotation.from_matrix(R).as_quat()`.
- **Using `compute_oriented_bounding_box(...)` name** (CONTEXT D-01 wording). The actual Open3D API is `get_oriented_bounding_box(robust=True)` — the `compute_*` name does not exist in Open3D 0.18+ [VERIFIED: open3d.org 0.18/0.19 docs]. Plans write the correct name.
- **Calling `warmup()` in `swap_lifter`.** Lifters have no heavy model; adding warmup defeats the whole point of D-09 hot-swap. Hot-swap is immediate.
- **Releasing the `_swap_lock` before all workers have been updated.** Half-swapped state (robot_a has new lifter, robot_b still has old) is observable by consumers reading `pool.inspect_worker_queues` / `pool.lifter_name`. Hold until every `w._lifter = ...` has completed.
- **Adding an `intrinsics` field to `SensorFrame`.** Despite D-04 wording, `Detection3DProtocol.lift(..., intrinsics, ...)` ALREADY takes intrinsics as a separate positional argument (`src/perception/protocol.py:127-134`), and `DetectorWorker._intrinsics` is already per-worker owned. Adding an `intrinsics` field to SensorFrame duplicates state and risks drift. See Open Question #2.
- **Using `algorithm="brute"` for DBSCAN.** O(N²) on 2000 points = ~4M distance ops; use `algorithm="kd_tree"` (sub-linear for 3D).
- **Computing OBB on world-frame points vs camera-frame.** Fitting in camera frame means the orientation is relative to the camera pose — correct for per-frame OBBs but wrong for persistence. OrientedBox3D.center/quaternion are WORLD-FRAME per Phase 1 D-10. Unproject to world BEFORE DBSCAN + OBB fit (what Template 1 does).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rotation matrix → quaternion | Hand-rolled trace-based conversion | `scipy.spatial.transform.Rotation.from_matrix(R).as_quat()` | Sign-bug-prone; scipy is already a dep; xyzw default matches wire |
| OBB from point cloud | Hand-rolled PCA + axis-aligned extents | `open3d.geometry.PointCloud.get_oriented_bounding_box(robust=True)` | Open3D handles degenerate clusters, convex hull, PCA alignment |
| 3D point clustering | Hand-rolled distance-threshold BFS | `sklearn.cluster.DBSCAN` | Noise label, kd_tree acceleration, battle-tested |
| Pinhole unprojection | Scattered per-module FOV math (current state) | `src/perception/geometry.py::unproject_pixel_to_world` | D-06 invariant: single projection entrypoint |
| MuJoCo body GT access | Manual `mj_name2id + mjData.xpos indexing` | `data.body("chair").xpos` + `.xquat` (named access API) | MuJoCo 3.x built-in; no id bookkeeping |
| Lock-free ref swap | Custom lockless algorithm / atomic.compare_exchange | `threading.Lock` + direct attribute assignment (GIL gives atomicity) | CPython semantics already guarantee ref-assignment atomicity; Lock only serializes swappers |

**Key insight:** The phase's most-stared-at pieces (OBB fit, clustering, R→quat) all have battle-tested library implementations in deps the project already uses. The custom code Phase 4 writes is entirely GLUE + GEOMETRY CONSOLIDATION — about 200 LOC of new code sitting on top of ~0 LOC of hand-rolled math.

## Runtime State Inventory

Phase 4 is primarily code creation + refactor. Runtime-state surfaces to audit:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — no persistent datastore keyed by lifter name. Detection history (Phase 6 `/api/detections/export`) does not yet exist. | None |
| Live service config | `app.state.active_lifter` (in-memory, FastAPI app state) — Phase 4 writes `point_cluster` to this on first hot-swap. `app.state.pending_lifter` / `pending_lifter_params` — Phase 4 continues to write these for `apply_params` live-tunable path. | Code edit: update `main.py` restart block & the new hot-swap route to maintain `app.state` consistency. |
| OS-registered state | None — no systemd / Task Scheduler / launchd / pm2 entries for lifters. | None |
| Secrets / env vars | None — lifters have no credentials. | None |
| Build artifacts / installed packages | `scikit-learn` NEW installed dep (perception extra). `open3d` already installed. No egg-info / compiled binaries to rebuild. | `pip install -e '.[perception]'` after pyproject edit. |

## Common Pitfalls

### Pitfall 1: Open3D API naming mismatch
**What goes wrong:** CONTEXT D-01 specifies `compute_oriented_bounding_box(robust=True)` but this method does not exist in Open3D 0.18+.
**Why it happens:** Different API names exist in older Open3D versions / external docs / training data.
**How to avoid:** Use `get_oriented_bounding_box(robust=True)` per the actual 0.18+ API [VERIFIED: open3d.org docs].
**Warning signs:** `AttributeError: 'PointCloud' object has no attribute 'compute_oriented_bounding_box'` at first run.

### Pitfall 2: `OrientedBoundingBox.extent` vs half_extents
**What goes wrong:** Open3D returns FULL side lengths in `.extent`. Assigning directly to `OrientedBox3D.half_extents` yields boxes rendered at DOUBLE size in Three.js.
**Why it happens:** Naming ambiguity — "extent" vs "half-extent" not universal.
**How to avoid:** Always divide by 2: `half_extents=extent / 2.0`. Regression test: fit an OBB on a synthetic unit-cube cluster and assert `half_extents ≈ [0.5, 0.5, 0.5]`.
**Warning signs:** OBBs in the 3D viewer visibly twice the size of the underlying depth cluster.

### Pitfall 3: Camera-frame vs world-frame OBB fit
**What goes wrong:** Fitting the OBB in camera frame before applying the pose produces rotations that change when the robot rotates (even if the object is stationary).
**Why it happens:** `OrientedBox3D.quaternion` is a WORLD-FRAME rotation per Phase 1 D-10.
**How to avoid:** Unproject pixels to WORLD frame via `geometry.unproject_pixels_batched` FIRST, then fit the OBB on world points.
**Warning signs:** A stationary chair's OBB yaw drifts as the robot walks around it.

### Pitfall 4: DBSCAN returns all-noise
**What goes wrong:** When eps is too tight or the depth frustum is sparse/noisy, every point is labeled -1 (noise) and no cluster is found.
**Why it happens:** Indoor depth noise is ~1–3 cm at 1–3 m range; eps=0.05 is close to the floor.
**How to avoid:** After `labels = DBSCAN(...).fit_predict(...)`, check `unique = np.unique(labels[labels >= 0])`; if empty, return None (lifter skips this detection) — do NOT fall back to MedianDepth here (per D-07, fallback is pixel-count-gated, not DBSCAN-outcome-gated). Document in docstring.
**Warning signs:** `n_final` << `n_raw` in the metrics payload with otherwise-valid depth; jitter in detection persistence across frames.

### Pitfall 5: DBSCAN OOM on giant bboxes
**What goes wrong:** A 640×480 bbox covering half the image = 150,000 pixels. sklearn DBSCAN is O(n²) worst-case memory.
**Why it happens:** No caller-side cap on bbox size.
**How to avoid:** Random-subsample to `_MAX_POINTS = 2000` points BEFORE calling DBSCAN (Pattern Template 1). Deterministic `np.random.default_rng(0)` for reproducibility.
**Warning signs:** RSS spike on large-object detections; wall-clock > 200 ms / detection.

### Pitfall 6: Hot-swap race with ongoing inference
**What goes wrong:** A worker thread in the middle of `self._lifter.lift(...)` has a reference to the OLD lifter. Mid-call swap does NOT interrupt the in-flight lift — the old lifter finishes, the NEXT submit uses the new lifter. This is correct behavior but subtle.
**Why it happens:** Python attribute assignment is atomic under GIL, but method dispatch captures the ref at call time.
**How to avoid:** Document explicitly in the docstring. Design tests to assert that the first lift AFTER `swap_lifter` uses the new lifter (not that the in-flight lift is aborted).
**Warning signs:** A log message "n_final=4 (median_depth)" arriving after the hot-swap — valid, not a bug.

### Pitfall 7: MuJoCo quaternion convention mismatch
**What goes wrong:** MuJoCo `mjData.xquat` is WXYZ (scalar-first). scipy `as_quat()` default is XYZW (scalar-last). Comparing them raw silently gives wrong yaw errors.
**Why it happens:** Two libraries, two conventions.
**How to avoid:** In the integration test, convert either side to a common form before comparing. Recommend: take both quaternions, compute the body-frame yaw angle via `Rotation.from_quat(...).as_euler('zyx')[0]`, and compare yaws. For scipy: `Rotation.from_quat(detection_quat_xyzw)`; for MuJoCo: `Rotation.from_quat([x, y, z, w]) where [w, x, y, z] = mj_data.body("chair").xquat`.
**Warning signs:** Test fails at ±90° / ±180° yaw consistently — sign/ordering bug.

### Pitfall 8: MuJoCo camera frame vs Open3D convention in `geometry.py`
**What goes wrong:** The sign flip `[cam_x, -cam_y, -depth]` at `median_depth.py:97` is specific to MuJoCo's camera convention (+x right, +y up, +z back). Open3D's convention is (+x right, +y down, +z forward). If `geometry.py` is authored against Open3D convention, points reproject at the wrong location.
**Why it happens:** Camera-frame conventions are a classic footgun.
**How to avoid:** Preserve the `median_depth.py:97` sign flip VERBATIM in `geometry.unproject_pixel_to_world`. Add a round-trip test: `unproject(cx_px, cy_px, d, intrinsics, identity_pose)` with `cx_px=cx, cy_px=cy, d=2.0` should yield `(0, 0, -2)` (camera looking along -Z).
**Warning signs:** MuJoCo GT test yields center_error ~0.5 m instead of ~0.05 m — sign bug in y or z axis.

### Pitfall 9: Grep invariant false positives on `70`
**What goes wrong:** SC#3 says "grep for `70` returns no hits in perception modules", but `70` is a common integer that appears in thread counts, test params, docstrings.
**Why it happens:** SC wording is shorthand for "no hardcoded FOV constant".
**How to avoid:** The real invariant is `grep -rn "fov\|FOV\|focal\|70.0" src/perception/` returns no hits in executable code. Encode this more carefully in the automated test: grep for specifically `_LEGACY_FOV_DEG` AND `fov_rad = math.radians` — both should return zero hits outside `geometry.py` docstrings.
**Warning signs:** The grep test fails on a legitimate unrelated `70` in a PARAMETER_SCHEMA default. Fix the test, not the code.

### Pitfall 10: `CLOUD_CONFIGS` is SLAM state, not perception state
**What goes wrong:** SC#3 says "`CLOUD_CONFIGS` returns no hits in perception modules". This is already true (`src/bridge/cloud_config.py` is bridge/SLAM, not perception). The risk is someone adds a cloud-config dependency during Phase 4.
**Why it happens:** MuJoCo→world camera convention is already encoded in `_capture_frame` + `cloud_config.py`, but `MuJoCoBridge._capture_frame` currently produces poses using `cam_xmat` directly.
**How to avoid:** Phase 4 `geometry.py` MUST NOT import `src.bridge.cloud_config`. Add a grep invariant test: `grep -rn "cloud_config\|CLOUD_CONFIGS" src/perception/` returns empty.
**Warning signs:** A plan to "reuse the SLAM axis flips" — red flag; perception owns its own convention via the sign flip in `geometry.py`.

## Code Examples

### Example 1: Open3D OBB from numpy points + R→quat conversion

```python
# Source: open3d.org/docs/release/python_api/open3d.geometry.PointCloud.html
#         scipy.spatial.transform.Rotation.as_quat docs
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

# points: (N, 3) float64 in world frame
points = np.asarray([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                     [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], dtype=np.float64)

pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
obb = pcd.get_oriented_bounding_box(robust=True)

# Extract parts.
center = np.asarray(obb.center)      # (3,)
R      = np.asarray(obb.R)           # (3, 3)
extent = np.asarray(obb.extent)      # (3,) FULL side lengths, not half

# Convert R → xyzw quaternion.
quat_xyzw = Rotation.from_matrix(R).as_quat()    # default scalar_first=False
# Alternatively: Rotation.from_matrix(R).as_quat(scalar_first=False)

print(center, extent / 2.0, quat_xyzw)   # HALF extents feed OrientedBox3D
```

### Example 2: sklearn DBSCAN on 3D points

```python
# Source: scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html
import numpy as np
from sklearn.cluster import DBSCAN

# world_pts: (N, 3) in meters
world_pts = np.random.rand(500, 3) * 0.2    # tight cluster
labels = DBSCAN(eps=0.05, min_samples=10, algorithm="kd_tree").fit_predict(world_pts)
# labels: (N,) int; -1 = noise; 0, 1, ... = cluster id

# Largest cluster (D-02 tiebreak).
valid = labels[labels >= 0]
unique, counts = np.unique(valid, return_counts=True)
best_label = unique[np.argmax(counts)]
cluster_pts = world_pts[labels == best_label]
```

### Example 3: MuJoCo body GT in test fixture

```python
# Source: mujoco.readthedocs.io/en/stable/python.html
import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

model = mujoco.MjModel.from_xml_path("tests/perception/fixtures/scene_rotated_chair.xml")
data = mujoco.MjData(model)
mujoco.mj_forward(model, data)

chair_xpos  = data.body("chair").xpos        # (3,) world-frame position
chair_xquat = data.body("chair").xquat       # (4,) WXYZ in MuJoCo convention

# Convert to XYZW (matches our wire format).
w, x, y, z = chair_xquat
chair_quat_xyzw = np.array([x, y, z, w])

# Yaw angle for the ±15° gate.
yaw_gt = Rotation.from_quat(chair_quat_xyzw).as_euler('zyx')[0]   # radians
```

### Example 4: Unit test for `DetectorWorkerPool.swap_lifter` under load

```python
# tests/perception/test_lifter_hotswap.py (NEW — ~100 LOC)
import threading, time
import numpy as np
import pytest
from src.perception.worker_pool import DetectorWorkerPool
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame

def test_hotswap_under_30hz_submit(monkeypatch):
    """Hot-swap during sustained 30 Hz submit: no dropped frames, no crashes, and
    first lift after swap uses the new lifter."""
    # ... construct pool with yolov11 + median_depth, warmup, start ...
    pool = _make_pool(["r0"])
    pool.warmup_all({"r0": _dummy_frame()})
    pool.start()

    stop = threading.Event()
    def submitter():
        while not stop.is_set():
            pool.submit("r0", _dummy_frame(), np.eye(4), None)
            time.sleep(1 / 30.0)
    t = threading.Thread(target=submitter, daemon=True); t.start()

    time.sleep(0.5)       # let some frames process
    pool.swap_lifter("point_cluster", {})
    time.sleep(0.5)
    stop.set(); t.join(timeout=2.0)

    # Assertion: after a brief settle, the pool's lifter_name is the new one.
    assert pool.lifter_name == "point_cluster"
    # Assertion: the latest() envelope came from the new lifter (check
    # outputs_oriented via the detector registry info). The OBB quaternion
    # should no longer be the fallback identity for a successful detection.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Client-side focal-length back-projection (legacy DetectionBoxes.ts) | Server-owned OBB wire format, dumb renderer | Phase 2 D-18 cutover (2026-04-14) | Already shipped; SC#2 effectively already PASS |
| Hardcoded 70° FOV in `median_depth.py:43` | `CameraIntrinsics` passed through `Detection3DProtocol.lift` + new `geometry.py` | Phase 4 (this phase) | `_LEGACY_FOV_DEG` deleted; grep invariant locks single entrypoint |
| `/lifter-select` triggers coordinator restart (Phase 3 D-09) | `/lifter-hotswap` atomic ref swap (no restart) | Phase 4 D-09 supersedes Phase 3 D-09 | One route removed, one added; frontend redirect; restart-overlay stays for detector path only |
| Median-depth identity-quaternion boxes | PCA-OBB with real rotation | Phase 4 DET-3D-01 | Rotated chair OBB actually reflects orientation; enables SC#1 gate |
| scipy `as_quat()` deprecated default behavior (pre-1.14) | Explicit `scalar_first=False` default documented | scipy 1.14+ (2024) | scipy is pinned >=1.15 so we're on the explicit-default side; xyzw is documented default |

**Deprecated / outdated:**
- Client-side 3D geometry reconstruction from bbox + focal length (deleted in Phase 2; SC#2 asserts it stays deleted).
- `_LEGACY_FOV_DEG = 70.0` at `median_depth.py:43` (deleted in Phase 4).
- `POST /api/detectors/lifter-select` (removed in Phase 4; `/lifter-hotswap` replaces).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `algorithm="kd_tree"` is fastest for 3D DBSCAN at N<=2000 | Pattern Template 1, Standard Stack | If `brute` or `ball_tree` is faster on our point distributions, we lose 5–15 ms / detection. Mitigation: measure once in test_point_cluster_lifter.py and document; `algorithm="auto"` is a safe fallback. |
| A2 | `_MAX_POINTS = 2000` subsample cap keeps OBB fit within 33 ms | Pattern Template 1 | If actual clusters are 3000+ points, the cap introduces noise in the PCA fit. Mitigation: surface the cap as a param; if SC#1 gates fail, bump to 5000 and re-measure. |
| A3 | `_MAD_K = 2.5` is a sensible outlier threshold for indoor depth | Pattern Template 1 | Too strict → drops valid points, too loose → background pollution in DBSCAN. Mitigation: expose as a param; default is literature-standard for robust stats. |
| A4 | MuJoCo chair-as-box geom triggers YOLOv11 `chair` class at >0.25 confidence | Fixture design | If YOLO doesn't recognize a textureless box as a chair, SC#1 never fires. Mitigation: make the "chair" body a compound geom (seat + back + 4 legs as 6 boxes) — closer to chair silhouette; add a color/texture if needed. Tests should skip if confidence < threshold, not fail. |
| A5 | Open3D `OrientedBoundingBox.R` columns are sorted principal-axes largest-to-smallest | R→quat conversion | If axis order is nondeterministic, the quaternion depends on cluster shape, producing inconsistent orientations across frames. Mitigation: spec-first check — write a test that fits OBB on a known 2:1:0.5 cluster and asserts extent ordering. If Open3D does not sort, we sort explicitly. |
| A6 | `threading.Lock` + direct attribute write is sufficient for hot-swap atomicity under CPython GIL | Pattern Template 3, Pitfall 6 | GIL semantics are documented but subtle; Python 3.13+ free-threaded mode breaks this assumption. Mitigation: `pyproject.toml` pins `requires-python = ">=3.10,<3.13"` so GIL is guaranteed in our runtime. |
| A7 | `app.state.detector_pool` is the right exposure point for the hot-swap route | Pattern Template 4 | Alternative is `command_callback` — if chosen, route implementation differs substantially. Planner decides; documented in Open Question below. |

## Open Questions

1. **Open3D API name: `compute_oriented_bounding_box` vs `get_oriented_bounding_box`**
   - What we know: CONTEXT D-01 says `compute_oriented_bounding_box(robust=True)`. Open3D 0.18+ docs name it `get_oriented_bounding_box(robust=True)`. Both verified [VERIFIED: open3d.org 0.18.0 and 0.19.0 docs; two independent searches].
   - What's unclear: Whether CONTEXT intended the actual API name or a generic shorthand.
   - **RESOLVED:** Plan and implementation MUST use `get_oriented_bounding_box(robust=True)`. CONTEXT `compute_*` is a wording error in the user decision; surfacing this correction in VERIFICATION.md (alongside the D-03 full-3D override) is a planner deliverable.

2. **D-04 SensorFrame `intrinsics` field vs existing intrinsics plumbing**
   - What we know: `Detection3DProtocol.lift(..., pose, intrinsics, slam_cloud)` already passes `CameraIntrinsics` as a separate positional arg (`src/perception/protocol.py:127-134`). `DetectorWorker` already stores per-worker `_intrinsics` (`src/perception/worker.py:116`). `DetectorWorkerPool.__init__` already takes `intrinsics_per_robot` (`src/perception/worker_pool.py:113`). `main.py:641` already computes `CameraIntrinsics.from_fov(w, h)` at startup. Adding a SensorFrame field would be duplicate state.
   - What's unclear: Whether D-04's author knew about the existing plumbing.
   - **RESOLVED:** Do NOT add `intrinsics` to `SensorFrame`. The planner SHOULD treat D-04 as "populate intrinsics at capture time and make it available to the lifter", which is already satisfied by the worker/pool plumbing. Document this in VERIFICATION.md as a "D-04 interpretation — existing plumbing satisfies intent". If the user wants intrinsics on SensorFrame specifically (e.g., for future SLAM backends that take SensorFrame), that's a separate architectural decision — defer to Phase 6+.

3. **`slam_cloud=None` acceptability for PointClusterLifter**
   - What we know: `Detection3DProtocol.lift(...)` requires `slam_cloud` as a positional arg (Phase 1 D-04); `MedianDepthLifter` already ignores it (`src/perception/lifters/median_depth.py:184`). PointClusterLifter works from `frame.depth` + `bbox` — no SLAM cloud needed.
   - What's unclear: None — `CAPABILITIES["requires_point_cloud"] = False` already signals this explicitly.
   - **RESOLVED:** PointClusterLifter sets `CAPABILITIES["requires_point_cloud"] = False` (Pattern Template 1). The lift method accepts `slam_cloud` positionally and ignores it. Docstring notes "slam_cloud=None acceptable — not used; reserved for future lifters".

4. **Hot-swap route exposure: `app.state.detector_pool` vs `command_callback`**
   - What we know: Today `coordinator._detector_pool` is set at `main.py:551` but not mirrored to FastAPI `app.state`. The detector-select route uses `command_callback({"action": "restart"})` to trigger pool rebuild in the main loop.
   - What's unclear: Which exposure pattern the planner should pick.
   - **RESOLVED:** Plan MUST add `app.state.detector_pool = detector_pool` to the restart block in `main.py` (right after `coordinator._detector_pool = detector_pool` at line 551). The `/lifter-hotswap` route reads `request.app.state.detector_pool` and calls `pool.swap_lifter(...)` directly — synchronous, no command-callback detour. This is simpler, avoids spinning up the restart machinery for a non-restart operation, and matches the D-10 "≪1ms atomic swap" goal.

5. **DBSCAN tiebreak when clusters are same size**
   - What we know: D-02 says "largest cluster wins". Rarely, two clusters have identical point counts.
   - What's unclear: Secondary tiebreak.
   - **RESOLVED:** Implement the primary rule (largest by point count via `argmax`; numpy `argmax` returns the FIRST occurrence on ties — deterministic). If the planner wants a richer tiebreak, use "closest centroid to the unprojected bbox-center pixel". For MVP, `np.argmax(counts)` is sufficient and matches research.

6. **Chair MuJoCo fixture: primitive geoms vs mesh**
   - What we know: YOLO classifies by silhouette; a plain box might not register as "chair". A 6-primitive compound (seat + back + 4 legs) is closer. A mesh-based chair is most accurate but adds asset dependency.
   - What's unclear: Which fixture strategy satisfies SC#1 deterministically.
   - **RESOLVED:** Use a compound-primitive chair (seat box + back box + 4 leg boxes, all parented to body `chair`). Keeps the fixture self-contained (no mesh assets), sufficient silhouette for YOLO. If YOLO confidence is < 0.25 on the compound, add a light-brown rgba to match furniture training data. If that STILL fails (gate A4), fall back to a mesh chair. Document the decision tree in the test file's docstring.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10–3.12 | Runtime | ✓ (assumed — pyproject.toml requires) | Per pyproject | — |
| numpy >=1.26 | geometry + lifter | ✓ | 2.4.4 on system shell | — |
| scipy >=1.15 | R→quat conversion | ✓ | 1.17.1 on system shell | — |
| open3d >=0.18 | OBB fit | ✗ (not installed in current shell) | pinned in pyproject | Install via `pip install -e '.[perception]'` — already a top-level dep |
| scikit-learn >=1.4.0 | DBSCAN | ✗ (NEW dep) | Latest 1.8.0 (verified via `pip index versions`) | Install after pyproject edit |
| mujoco >=3.0.0 | GT fixture | ✗ (not installed in current shell) | pinned in pyproject; 3.6.0 latest | Install via `pip install -e '.[perception]'` (or add to baseline perception extra) |
| ultralytics >=8.4.24 | YOLOv11 for integration test | ✗ (not installed) | Already pinned in perception extra | Install via perception extra |
| pytest >=8.0.0 | Test runner | ✓ (dev extra) | — | — |
| Node.js + npm | Frontend tsc check | ✓ (Phase 3 verified) | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** open3d, scikit-learn, mujoco, ultralytics — all installed via `pip install -e '.[perception]'` once pyproject is updated to include `scikit-learn>=1.4.0` in the perception extra. Note that Phase 3 verification already noted a pre-existing dev-env gap for torch/ultralytics/msgpack — that gap blocks the integration test but NOT geometry.py / point_cluster unit tests that can mock Detection2D input without a live detector. Planner should structure Wave 3 such that unit tests pass without the full perception extra installed; only the MuJoCo-driven integration test requires the full stack.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ (dev extra) |
| Config file | `pytest.ini` (testpaths=tests, timeout=30) |
| Quick run command | `pytest tests/perception/test_geometry.py tests/perception/test_point_cluster_lifter.py -x -q` |
| Full suite command | `pytest tests/perception/ -x -q` |
| Frontend typecheck | `cd frontend && npx tsc --noEmit` |
| Frontend test | `cd frontend && npm test` (Vitest; Phase 3 shipped the runner) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DET-3D-01 | PointClusterLifter produces real OBB within ±15° yaw / 0.15 m center on MuJoCo chair | integration | `pytest tests/perception/test_point_cluster_lifter.py::test_mujoco_chair_yaw_and_center_gates -x` | ❌ Wave 3 (needs fixture XML + full perception extra installed) |
| DET-3D-01 | PointClusterLifter fit on synthetic cluster returns correct half_extents + rotation | unit | `pytest tests/perception/test_point_cluster_lifter.py::test_fit_synthetic_rotated_cluster -x` | ❌ Wave 2 |
| DET-3D-01 | DBSCAN rejects background points in a bbox frustum | unit | `pytest tests/perception/test_point_cluster_lifter.py::test_dbscan_rejects_background -x` | ❌ Wave 2 |
| DET-3D-02 | MedianDepthLifter remains registered with `outputs_oriented=False` | unit | `pytest tests/perception/test_median_depth_lifter.py::test_median_depth_still_registered -x` | ✅ (existing test — verify not regressed) |
| DET-3D-02 | PointClusterLifter composes MedianDepthLifter as `_fallback` | unit | `pytest tests/perception/test_point_cluster_lifter.py::test_fallback_delegate_is_median_depth -x` | ❌ Wave 2 |
| DET-3D-05 | DetectionBoxes.ts renders from wire — no focal-length math (grep invariant) | smoke | `! grep -rn "fov\|FOV\|focal\|projectBox\|backProject" frontend/src/components/DetectionBoxes.ts` | ❌ Wave 3 (existing code passes; test file encodes invariant) |
| DET-3D-05 | Frontend typecheck passes after LifterDropdown redirect | smoke | `cd frontend && npx tsc --noEmit` | ✅ (existing) |
| DET-3D-06 | `_LEGACY_FOV_DEG` removed; no FOV/focal in perception executable code | unit | `pytest tests/perception/test_geometry.py::test_no_fov_constants_outside_geometry -x` | ❌ Wave 1 |
| DET-3D-06 | `unproject_pixel_to_world` + `unproject_pixels_batched` round-trip | unit | `pytest tests/perception/test_geometry.py::test_unproject_roundtrip_identity_pose -x` | ❌ Wave 0 |
| DET-3D-06 | `geometry.py` is the only perception module importing `math` for FOV | unit | `pytest tests/perception/test_geometry.py::test_grep_single_entrypoint -x` | ❌ Wave 0 |
| DET-3D-07 | Fallback fires when bbox has < 50 valid depth pixels | unit | `pytest tests/perception/test_point_cluster_lifter.py::test_fallback_below_50_pixels -x` | ❌ Wave 2 |
| DET-3D-07 | Fallback OBB has identity quaternion and `outputs_oriented=False` envelope signaling | unit | `pytest tests/perception/test_point_cluster_lifter.py::test_fallback_outputs_identity_quat -x` | ❌ Wave 2 |
| SC#5 (hot-swap) | `POST /api/detectors/lifter-hotswap` returns 200 without restart | unit | `pytest tests/perception/test_lifter_hotswap.py::test_hotswap_returns_200 -x` | ❌ Wave 3 |
| SC#5 | Back-to-back swaps under 30 Hz submit do not drop frames | concurrency | `pytest tests/perception/test_lifter_hotswap.py::test_hotswap_under_30hz_submit -x` | ❌ Wave 3 |
| SC#5 | `POST /api/detectors/lifter-select` returns 404/410 (old route removed) | unit | `pytest tests/perception/test_lifter_hotswap.py::test_lifter_select_removed -x` | ❌ Wave 3 |
| SC#4 | Bit-exact Phase 2 OBB round-trip still passes | unit | `pytest tests/perception/test_obb_round_trip.py -x` | ✅ (existing — regression gate) |

### Sampling Rate
- **Per task commit:** `pytest tests/perception/test_geometry.py tests/perception/test_point_cluster_lifter.py tests/perception/test_lifter_hotswap.py -x -q` (all Phase 4 unit tests)
- **Per wave merge:** `pytest tests/perception/ -x -q && cd frontend && npx tsc --noEmit && npm test`
- **Phase gate:** Full suite + `grep -rn "_LEGACY_FOV_DEG\|fov_rad = math.radians" src/perception/` returns empty + MuJoCo integration test green

### Wave 0 Gaps
- [ ] `tests/perception/test_geometry.py` — unit tests for `unproject_pixel_to_world`, `unproject_pixels_batched`, and grep invariants (DET-3D-06)
- [ ] `tests/perception/fixtures/scene_rotated_chair.xml` — MuJoCo XML fixture with body `chair` at known yaw (DET-3D-01, SC#1)
- [ ] `pyproject.toml` — add `scikit-learn>=1.4.0` to perception extra (D-02)
- [ ] `src/perception/geometry.py` — the module itself (D-05, D-06)

Then Wave 1 (migration):
- [ ] `src/perception/lifters/median_depth.py` — delete `_LEGACY_FOV_DEG`, route through `geometry.unproject_pixel_to_world`

Then Wave 2 (new lifter):
- [ ] `src/perception/lifters/point_cluster.py` — PointClusterLifter implementation
- [ ] `tests/perception/test_point_cluster_lifter.py` — unit tests (synthetic cluster, fallback, DBSCAN rejection)

Then Wave 3 (hot-swap + frontend + integration):
- [ ] `src/perception/worker_pool.py` — `swap_lifter` method + `_swap_lock`
- [ ] `backend/web/detector_routes.py` — remove `/lifter-select`, add `/lifter-hotswap`
- [ ] `src/main.py` — set `app.state.detector_pool = detector_pool` in restart block
- [ ] `frontend/src/components/DetectorSection.tsx` — redirect `onConfirmLifterSwitch` to hot-swap, remove restart overlay flow for lifter
- [ ] `tests/perception/test_lifter_hotswap.py` — concurrency + route tests
- [ ] MuJoCo integration test addition (in test_point_cluster_lifter.py or separate test_mujoco_chair_gt.py)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | N/A — REST endpoints are session-bound to localhost single-user C2 (same trust boundary as Phase 3) |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — single-user local tool |
| V5 Input Validation | yes | FastAPI pydantic BaseModels (`LifterSelectRequest`, `ParamPatch`). `req.lifter` MUST be validated against `Detection3DRegistry.list_backends()` before pool mutation — mirrors Phase 2 T-02-19 and Phase 3 T-03-11 |
| V6 Cryptography | no | N/A |

### Known Threat Patterns for this phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed `POST /lifter-hotswap` payload crashes FastAPI | DoS | pydantic `LifterSelectRequest` validates shape; FastAPI returns 422 automatically — inherited from Phase 3 T-03-12 |
| Unregistered lifter name in POST causes silent failure | Tampering | Validate `req.lifter ∈ Detection3DRegistry.list_backends()` BEFORE calling `pool.swap_lifter`; raise HTTPException(404) — mirrors Phase 2 T-02-19 pattern |
| Concurrent `/lifter-hotswap` calls race in `pool.swap_lifter` | Integrity | `DetectorWorkerPool._swap_lock` serializes swaps; pydantic validation is first, pool lock is second — acceptable for a single-user LAN-bound C2 (same trust boundary as detector-select) |
| Malicious MuJoCo XML fixture in test triggers RCE | Tampering | `tests/perception/fixtures/scene_rotated_chair.xml` is a committed fixture in the repo; MuJoCo's XML loader does not execute code paths; threat is limited to author-side review of committed fixtures |
| DBSCAN OOM on huge bboxes (resource exhaustion) | DoS | `_MAX_POINTS = 2000` subsample cap (Pattern Template 1) bounds memory at O(N²) ≤ O(4M) — ~30 MB distance matrix worst case; well below RSS budgets |
| Open3D crash on degenerate input (zero points, colinear points, NaN in array) | DoS | Wrap `pcd.get_oriented_bounding_box(robust=True)` in `try/except Exception: return None` (Pattern Template 1). `robust=True` already handles most degenerate cases per Open3D docs |
| Ref swap mid-frame race — torn lifter state | Integrity | CPython GIL guarantees attribute-write atomicity; `_swap_lock` serializes concurrent swappers (not readers). In-flight lift() completes with old lifter; next submit() uses new — documented in Pitfall 6 |
| MuJoCo test fixture flakiness (YOLO confidence varies by render seed) | Availability of gate | YOLOv11 is deterministic given fixed input (`torch.inference_mode()` enforced). MuJoCo render is deterministic given fixed qpos + qvel. Fixture loads at known keyframe; no stochastic motion. Test asserts `detections_2d.items != []` with class_name="chair" before computing error gates — FAIL LOUDLY on precondition, not on gate (helps debugging) |
| Frontend posts to `/lifter-hotswap` before pool initialized (e.g., during first boot) | DoS / UX | Route returns 503 `Detector pool not initialized` — frontend error banner already handles non-200 responses (DetectorSection.tsx line 202) |

## Sources

### Primary (HIGH confidence)
- Open3D 0.18.0 / 0.19.0 Python API — https://www.open3d.org/docs/release/python_api/open3d.geometry.PointCloud.html (verified both `get_oriented_bounding_box(robust=True)` and `get_minimal_oriented_bounding_box`)
- scikit-learn DBSCAN — https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html (verified signature, labels, noise=-1, kd_tree)
- scipy Rotation API — https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.as_quat.html (verified xyzw default, `scalar_first=False`)
- MuJoCo Python bindings — https://mujoco.readthedocs.io/en/stable/python.html (named-access `data.body("name").xpos/.xquat`)
- MuJoCo camera fovy — https://mujoco.readthedocs.io/en/stable/XMLreference.html#camera-fovy (vertical FOV)
- Project source files verified against HEAD:
  - `src/perception/protocol.py:127-134` — Detection3DProtocol.lift signature
  - `src/perception/types.py:87-252` — OrientedBox3D + Detections3D wire format
  - `src/perception/lifters/median_depth.py:43` — `_LEGACY_FOV_DEG = 70.0`
  - `src/perception/worker_pool.py:107-161` — DetectorWorkerPool construction
  - `src/perception/worker.py:111-281` — DetectorWorker per-worker intrinsics + _lifter ref
  - `src/bridge/sensor_types.py:68-93` — CameraIntrinsics + from_fov
  - `src/bridge/cloud_config.py` — SLAM-owned axis flips; NOT a perception dep (confirms SC#3 invariant already holds before Phase 4)
  - `frontend/src/components/DetectionBoxes.ts:87-116` — wire-driven OBB renderer, no focal math (SC#2 already PASS)
  - `frontend/src/components/DetectorSection.tsx:175-224` — current onConfirmLifterSwitch that must be redirected
  - `frontend/src/components/LifterDropdown.tsx` — unchanged by Phase 4
  - `backend/web/detector_routes.py:138-158` — current `/lifter-select` to be replaced
  - `pyproject.toml:6-16` — version pins
  - `.planning/phases/02-.../VERIFICATION.md` — Phase 2 PASS incl. D-10 quaternion lock
  - `.planning/phases/03-.../VERIFICATION.md` — Phase 3 PASS; `/lifter-select` shipped and must be removed

### Secondary (MEDIUM confidence)
- Brave/WebSearch cross-verification of Open3D OBB API name — multiple independent sources confirm `get_oriented_bounding_box` (not `compute_*`)
- scipy GitHub issues #14548 / #19649 — corroborate xyzw default and flag historical scalar-first/last ambiguity
- `pip index versions scikit-learn` / `scipy` / `mujoco` — local verification of latest versions (2026-04-14)

### Tertiary (LOW confidence)
- None — all load-bearing claims tied to primary or corroborated by multiple secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against primary docs + pyproject.toml + local pip index
- Architecture patterns: HIGH — patterns are direct extensions of existing Phase 1–3 scaffolding (worker pool, registry, lifter composition already proven)
- Pitfalls: HIGH — every pitfall grounded in a verified API convention or a CONTEXT-documented decision
- Hot-swap concurrency correctness: MEDIUM-HIGH — CPython GIL atomicity is documented behavior; risk shifts to Python 3.13+ which is excluded by pyproject's `<3.13` ceiling
- MuJoCo GT fixture practicality: MEDIUM — A4 hinges on YOLO recognizing a primitive-box chair; mitigated by fallback to compound-primitive or mesh
- Wave ordering: HIGH — forced by dependency graph (geometry → median-depth migration → point-cluster → hot-swap); no ambiguity

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (30-day estimate — stable libraries, no fast-moving surfaces involved)
