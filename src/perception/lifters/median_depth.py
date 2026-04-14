"""Median-depth 2D→3D lifter — legacy Phase 1 default.

Per CONTEXT.md D-13 and Pitfall P3: this file is the SINGLE source of
median-depth 2D→3D projection math in Phase 1. The duplicated path that
lived at src/perception/detector.py:221-236 is removed; detector.py
delegates here via project_center_median_depth(). The diverging path at
src/perception/detection_3d.py::project_detections_to_3d is abandoned
(detection_3d.py becomes a one-phase shim; Phase 4 retires it fully).

Output contract: every detection with valid depth gets an OrientedBox3D
with identity quaternion [0, 0, 0, 1] (xyzw) and a default half-extent
of 0.25 m on each axis — median depth CANNOT recover true size or
orientation. `outputs_oriented=False` is the truth-in-advertising signal
consumed by the Phase 4 frontend to hide the lifter dropdown when a
3D-native detector is selected.

Phase 4 migration complete: all pinhole math is delegated to
src.perception.geometry.unproject_pixel_to_world using the intrinsics
threaded through Detection3DProtocol.lift (no hardcoded FOV).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import numpy as np

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.geometry import unproject_pixel_to_world
from src.perception.registry import detection_3d
from src.perception.types import (
    Detections2D,
    Detections3D,
    OrientedBox3D,
)

logger = logging.getLogger(__name__)


def project_center_median_depth(
    bbox_xyxy: tuple[int, int, int, int],
    depth: np.ndarray,
    pose: np.ndarray,
    intrinsics: CameraIntrinsics,
    depth_near_m: float = 0.1,
    depth_far_m: float = 15.0,
) -> tuple[np.ndarray, float] | None:
    """Return (world_point_3, median_depth_m) or None if no valid depth pixels.

    Plan 04-03 migration (DET-3D-06): all pinhole math now delegates to
    `src.perception.geometry.unproject_pixel_to_world`, which consumes the
    caller-supplied `intrinsics` instead of a hardcoded FOV constant. The
    camera-frame sign flip (cam_pt = [cam_x, -cam_y, -d]) is preserved
    inside `geometry.unproject_pixel_to_world` — bit-parity with the
    pre-migration code is locked by
    `tests/perception/test_geometry.py::test_legacy_parity_with_median_depth_intrinsics`.

    - Depth ROI = bbox, filtered to `depth_near_m < d < depth_far_m`.
    - Median of remaining pixels is the depth scalar.
    - Bbox CENTER pixel is unprojected using `intrinsics` via geometry.py.

    This is the ONLY median-depth projection call site in the codebase
    after Phase 1. Do not duplicate this math elsewhere (Pitfall P3).
    """
    x1, y1, x2, y2 = bbox_xyxy
    h_img, w_img = depth.shape

    # Clamp bbox indices
    x1c = max(0, min(x1, w_img - 1))
    x2c = max(0, min(x2, w_img))
    y1c = max(0, min(y1, h_img - 1))
    y2c = max(0, min(y2, h_img))
    if x2c <= x1c or y2c <= y1c:
        return None

    roi = depth[y1c:y2c, x1c:x2c]
    valid = roi[(roi > depth_near_m) & (roi < depth_far_m)]
    if valid.size == 0:
        return None
    d = float(np.median(valid))

    # Center pixel (integer, matching pre-refactor detector.py:221 behaviour)
    cx_px = (x1 + x2) // 2
    cy_px = (y1 + y2) // 2
    cx_px = min(max(cx_px, 0), w_img - 1)
    cy_px = min(max(cy_px, 0), h_img - 1)

    world_pt = unproject_pixel_to_world(
        float(cx_px), float(cy_px), d, intrinsics, pose,
    )
    return world_pt, d


@detection_3d(name="median_depth", display="Median Depth (legacy)")
class MedianDepthLifter:
    """Legacy 2D→3D lifter per research Decision F.

    - outputs_oriented = False (identity quaternion for every box).
    - Half-extents are a fixed default (median depth recovers no size info).
    - Consolidates the two pre-Phase-1 projection paths (detector.py inline
      + detection_3d.py::project_detections_to_3d) into one place (D-13).
    - Ignores slam_cloud (Phase 4 PointClusterLifter consumes it).

    This is the SINGLE source of median-depth projection math in the repo.
    Pitfall P3 is closed by (a) this file existing, and (b) detector.py
    being rewired to call project_center_median_depth() instead of inlining.
    """

    CAPABILITIES: dict = {
        "requires_depth": True,
        "requires_point_cloud": False,
        "outputs_oriented": False,
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
                "description": "Near clip for valid depth pixels (meters)",
                "live_tunable": True,
            },
            "depth_far_m": {
                "type": "number",
                "default": 15.0,
                "minimum": 1.0,
                "maximum": 50.0,
                "description": "Far clip for valid depth pixels (meters)",
                "live_tunable": True,
            },
            "default_half_extent_m": {
                "type": "number",
                "default": 0.25,
                "minimum": 0.05,
                "maximum": 2.0,
                "description": "Half-extent assigned to OrientedBox3D (median depth recovers no size)",
                "live_tunable": True,
            },
        },
    }

    def __init__(
        self,
        depth_near_m: float = 0.1,
        depth_far_m: float = 15.0,
        default_half_extent_m: float = 0.25,
    ) -> None:
        self.depth_near_m = depth_near_m
        self.depth_far_m = depth_far_m
        self.default_half_extent_m = default_half_extent_m
        self._last_ms = 0.0
        self._last_n_raw = 0
        self._last_n_final = 0

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        # numpy-only; if numpy is importable, this lifter works.
        return True, None

    def lift(
        self,
        detections_2d: Detections2D,
        frame: SensorFrame,
        pose: np.ndarray,
        intrinsics: CameraIntrinsics,
        slam_cloud: np.ndarray | None,
    ) -> Detections3D:
        """Lift 2D detections to OrientedBox3D with identity quaternion.

        `intrinsics` is consumed via src.perception.geometry.unproject_pixel_to_world
        per Phase 4 DET-3D-06; the Phase 1 hardcoded 70° FOV has been deleted.
        `slam_cloud` is received per D-04 but IGNORED (Phase 4 PointClusterLifter
        consumes it).
        """
        t0 = time.perf_counter()
        items: list[OrientedBox3D] = []
        n_raw = len(detections_2d.items)

        depth = frame.depth
        if depth is None or depth.ndim != 2:
            # No depth available; return empty Detections3D
            self._last_ms = (time.perf_counter() - t0) * 1000.0
            self._last_n_raw = n_raw
            self._last_n_final = 0
            return Detections3D(
                items=[],
                lifter_ms=self._last_ms,
                detector_ms=detections_2d.inference_ms,
                n_raw=n_raw,
                n_final=0,
                image_hw=detections_2d.image_hw,
            )

        he = self.default_half_extent_m
        half_extents = np.array([he, he, he], dtype=np.float64)
        identity_quat = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64)  # xyzw

        for det in detections_2d.items:
            result = project_center_median_depth(
                det.bbox_xyxy,
                depth,
                pose,
                intrinsics,
                depth_near_m=self.depth_near_m,
                depth_far_m=self.depth_far_m,
            )
            if result is None:
                continue
            world_pt, _median_d = result
            items.append(
                OrientedBox3D(
                    center=world_pt,
                    half_extents=half_extents.copy(),
                    quaternion=identity_quat.copy(),
                    class_id=det.class_id,
                    class_name=det.class_name,
                    score=det.score,
                    track_id=None,
                )
            )

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

    def reset(self) -> None:
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
        for key, val in params.items():
            if key == "depth_near_m":
                self.depth_near_m = float(val)
                status[key] = "applied"
            elif key == "depth_far_m":
                self.depth_far_m = float(val)
                status[key] = "applied"
            elif key == "default_half_extent_m":
                self.default_half_extent_m = float(val)
                status[key] = "applied"
            else:
                status[key] = "unknown_parameter"
        return status
