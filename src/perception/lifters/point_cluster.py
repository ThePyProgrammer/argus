"""PCA-OBB lifter per DET-3D-01.

Default 3D lifter for Phase 4. Unprojects the bbox depth frustum through
src.perception.geometry, filters with MAD + DBSCAN, fits an oriented box via
Open3D's robust PCA routine, and emits an OrientedBox3D with a scipy-derived
xyzw quaternion. Delegates to MedianDepthLifter when the valid-depth pixel
count falls below 50 (D-07).

Pitfall 1: uses `get_oriented_bounding_box(robust=True)` — the correct
Open3D PointCloud method name (CONTEXT D-01 wording is wrong; research
Open Question #1 resolved against CONTEXT). The Pitfall-1 grep invariant
locks the wrong-name variant to zero occurrences in this file.
Pitfall 2: divides Open3D `.extent` by 2 before assigning to
OrientedBox3D.half_extents (Open3D exposes FULL side lengths).
Pitfall 3: unprojects to WORLD frame before PCA (so OBB rotation is
world-frame, not camera-frame).
Pitfall 4: when DBSCAN labels every point noise, returns None (SKIP, not
fallback — the D-07 fallback is pixel-count-gated, not DBSCAN-outcome-gated).
Pitfall 5: random-subsamples above _MAX_POINTS = 2000 to bound DBSCAN runtime.
Pitfall 7: scipy Rotation.as_quat() default is scalar_first=False → xyzw,
matching OrientedBox3D's xyzw convention; to_wire() auto-flips qw<0.
"""
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

logger = logging.getLogger(__name__)

_FALLBACK_PIXEL_FLOOR = 50   # D-07 — below this, delegate to MedianDepthLifter
_MAX_POINTS = 2000           # Safeguard DBSCAN runtime; random-subsample above this
_MAD_K = 2.5                 # Drop depth values beyond 2.5 * MAD from median
_IDENTITY_QUAT_XYZW = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)


@detection_3d(name="point_cluster", display="Point Cluster (PCA-OBB)")
class PointClusterLifter:
    """Real 3D oriented-box lifter (PCA via Open3D robust OBB + sklearn DBSCAN).

    Composes MedianDepthLifter as `self._fallback` per D-07: when the bbox
    depth frustum has fewer than 50 valid pixels (after near/far clipping
    and MAD filter), the detection is delegated to the fallback lifter,
    which emits an identity-quaternion OrientedBox3D with default
    half-extents. The envelope-level `outputs_oriented=True` capability
    still applies — frontend renders the identity quat as axis-aligned.
    """

    CAPABILITIES: dict = {
        "requires_depth": True,
        "requires_point_cloud": False,          # slam_cloud accepted but unused (research Open Q #3)
        "outputs_oriented": True,               # D-08 envelope-level capability
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "depth_near_m": {
                "type": "number",
                "default": 0.1,
                "minimum": 0.01,
                "maximum": 1.0,
                "live_tunable": True,
                "description": "Near clip for valid depth pixels (meters)",
            },
            "depth_far_m": {
                "type": "number",
                "default": 15.0,
                "minimum": 1.0,
                "maximum": 50.0,
                "live_tunable": True,
                "description": "Far clip for valid depth pixels (meters)",
            },
            "dbscan_eps_m": {
                "type": "number",
                "default": 0.05,
                "minimum": 0.01,
                "maximum": 0.5,
                "live_tunable": True,
                "description": "DBSCAN neighborhood radius (meters)",
            },
            "dbscan_min_samples": {
                "type": "integer",
                "default": 10,
                "minimum": 3,
                "maximum": 50,
                "live_tunable": True,
                "description": "DBSCAN min samples for a core point",
            },
        },
    }

    def __init__(
        self,
        depth_near_m: float = 0.1,
        depth_far_m: float = 15.0,
        dbscan_eps_m: float = 0.05,
        dbscan_min_samples: int = 10,
    ) -> None:
        self.depth_near_m = float(depth_near_m)
        self.depth_far_m = float(depth_far_m)
        self.dbscan_eps_m = float(dbscan_eps_m)
        self.dbscan_min_samples = int(dbscan_min_samples)
        # D-07 composition — same depth bounds as the outer lifter
        self._fallback = MedianDepthLifter(
            depth_near_m=self.depth_near_m, depth_far_m=self.depth_far_m,
        )
        self._last_ms = 0.0
        self._last_n_raw = 0
        self._last_n_final = 0

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        try:
            import open3d  # noqa: F401
            import sklearn.cluster  # noqa: F401
        except ImportError as exc:
            return False, f"pip install -e '.[perception]'  (import failed: {exc})"
        return True, None

    def lift(
        self,
        detections_2d: Detections2D,
        frame: SensorFrame,
        pose: np.ndarray,
        intrinsics: CameraIntrinsics,
        slam_cloud: np.ndarray | None,
    ) -> Detections3D:
        t0 = time.perf_counter()
        items: list[OrientedBox3D] = []
        n_raw = len(detections_2d.items)
        depth = frame.depth
        # Fallback path 1 — no depth channel at all. Delegate the entire call.
        if depth is None or depth.ndim != 2:
            return self._fallback.lift(
                detections_2d, frame, pose, intrinsics, slam_cloud,
            )

        for det in detections_2d.items:
            obb = self._fit_one(det, depth, pose, intrinsics, frame)
            if obb is None:
                continue                                     # silently drop degenerate boxes
            items.append(obb)
        self._last_ms = (time.perf_counter() - t0) * 1000.0
        self._last_n_raw = n_raw
        self._last_n_final = len(items)
        return Detections3D(
            items=items,
            lifter_ms=self._last_ms,
            detector_ms=detections_2d.inference_ms,
            n_raw=n_raw,
            n_final=len(items),
            image_hw=detections_2d.image_hw,
        )

    def _fit_one(
        self,
        det,
        depth: np.ndarray,
        pose: np.ndarray,
        intrinsics: CameraIntrinsics,
        frame: SensorFrame,
    ) -> OrientedBox3D | None:
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

        # D-07 pixel-count gate → delegate to fallback (MedianDepthLifter).
        if n_valid < _FALLBACK_PIXEL_FLOOR:
            return self._fallback_single(det, frame, pose, intrinsics, h_img, w_img)

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
            return self._fallback_single(det, frame, pose, intrinsics, h_img, w_img)

        # Subsample for DBSCAN + OBB safety (Pitfall 5).
        if us.size > _MAX_POINTS:
            rng = np.random.default_rng(0)
            idx = rng.choice(us.size, size=_MAX_POINTS, replace=False)
            us, vs, ds = us[idx], vs[idx], ds[idx]

        # Unproject to WORLD frame via the single geometry entrypoint (Pitfall 3).
        uvs = np.stack([us.astype(np.float64), vs.astype(np.float64)], axis=1)
        world_pts = unproject_pixels_batched(
            uvs, ds.astype(np.float64), intrinsics, pose,
        )

        # DBSCAN cluster rejection on world-frame points.
        labels = DBSCAN(
            eps=self.dbscan_eps_m,
            min_samples=self.dbscan_min_samples,
            algorithm="kd_tree",
        ).fit_predict(world_pts)

        # Pitfall 4: all-noise → skip the detection (no fallback at this tier).
        unique, counts = np.unique(labels[labels >= 0], return_counts=True)
        if unique.size == 0:
            return None
        best_label = unique[int(np.argmax(counts))]   # Open Q #5: first-wins tiebreak
        cluster = world_pts[labels == best_label]
        if cluster.shape[0] < self.dbscan_min_samples:
            return None

        # Open3D robust PCA OBB (Pitfall 1: correct API name!).
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(cluster))
        try:
            o_obb = pcd.get_oriented_bounding_box(robust=True)
        except Exception as exc:
            logger.debug(
                "Open3D OBB fit failed for det %s: %s",
                getattr(det, "class_name", "?"),
                exc,
            )
            return None

        R = np.asarray(o_obb.R, dtype=np.float64)          # (3,3) rotation matrix
        center = np.asarray(o_obb.center, dtype=np.float64)  # (3,)
        extent = np.asarray(o_obb.extent, dtype=np.float64)  # (3,) FULL side lengths (Pitfall 2)
        quat_xyzw = Rotation.from_matrix(R).as_quat()        # default scalar_first=False → xyzw

        return OrientedBox3D(
            center=center,
            half_extents=extent / 2.0,                        # Pitfall 2 — HALF per OrientedBox3D contract
            quaternion=quat_xyzw.astype(np.float64),
            class_id=det.class_id,
            class_name=det.class_name,
            score=det.score,
            track_id=None,
            bbox_xyxy=det.bbox_xyxy,
        )

    def _fallback_single(
        self,
        det,
        frame: SensorFrame,
        pose: np.ndarray,
        intrinsics: CameraIntrinsics,
        h_img: int,
        w_img: int,
    ) -> OrientedBox3D | None:
        """Delegate one detection to MedianDepthLifter (D-07)."""
        tiny = Detections2D(
            items=[det], inference_ms=0.0, image_hw=(h_img, w_img),
        )
        fb = self._fallback.lift(tiny, frame, pose, intrinsics, None)
        return fb.items[0] if fb.items else None

    def reset(self) -> None:
        self._fallback.reset()
        self._last_ms = 0.0
        self._last_n_raw = 0
        self._last_n_final = 0

    def get_metrics(self) -> dict:
        return {
            "last_lifter_ms": self._last_ms,
            "n_raw": self._last_n_raw,
            "n_final": self._last_n_final,
        }

    def apply_params(self, params: dict) -> dict:
        status: dict[str, str] = {}
        for k, v in params.items():
            if k in ("depth_near_m", "depth_far_m", "dbscan_eps_m"):
                setattr(self, k, float(v))
                status[k] = "applied"
            elif k == "dbscan_min_samples":
                self.dbscan_min_samples = int(v)
                status[k] = "applied"
            else:
                status[k] = "unknown_parameter"
        # Keep fallback depth bounds in sync with the outer lifter.
        self._fallback.depth_near_m = self.depth_near_m
        self._fallback.depth_far_m = self.depth_far_m
        return status
