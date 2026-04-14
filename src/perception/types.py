"""Perception data types: 2D + 3D detection dataclasses and input-mode enum.

This module is the bottom of the perception module stack per CONTEXT.md
"Known tricky bits" (Pitfall P9: types.py -> protocol.py -> registry.py -> backends/).
It imports ONLY stdlib + numpy. Importing this module must NOT pull torch,
ultralytics, or transformers into sys.modules -- tests/perception/test_protocol_contracts.py
enforces this invariant.

Phase 2 scope (Plan 02-01) additions:
- OrientedBox3D gains bbox_xyxy optional field + to_wire/from_wire methods.
- Detections3D gains capture_pose + capture_timestamp + to_wire method.
- Canonical wire format locked per 02-CONTEXT.md D-06..D-14.

Phase 1 scope (frozen):
- Detection2D / Detections2D per 01-CONTEXT.md D-03 (extras dict optional)
- OrientedBox3D skeleton fields (center, half_extents, quaternion xyzw, class_*, score, track_id)
- Detections3D wrapper so Detection3DProtocol.lift(...) has a concrete return type.
- DetectorInput enum picked over Literal for type-safe capability registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class DetectorInput(Enum):
    """What kind of sensor input a detector consumes.

    The registry (Plan 03) uses this to forbid wiring an RGB_TEXT_PROMPT
    backend behind a pipeline that does not carry a text prompt field.
    Phase 5 adds OWLv2 which will register as RGB_TEXT_PROMPT.
    """

    RGB_ONLY = "rgb_only"
    RGBD = "rgbd"
    RGB_TEXT_PROMPT = "rgb_text_prompt"


@dataclass(frozen=True)
class Detection2D:
    """A single 2D object detection.

    Per 01-CONTEXT.md D-03:
    - Required fields are the four primitives used by every backend.
    - `extras` is an opt-in escape hatch for backend-specific side channels
      (segmentation mask, feature embedding, text logits). Phase 1's YOLOv11
      backend leaves it as None; Phase 5's OWLv2 / BoxeR will populate it.
    """

    class_id: int
    class_name: str
    score: float
    bbox_xyxy: tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixel coords
    extras: dict[str, Any] | None = None


@dataclass(frozen=True)
class Detections2D:
    """Container for one detector call's output.

    `image_hw` lets downstream lifters know the coordinate space of bbox_xyxy
    without re-reading the frame. `inference_ms` is the steady-state timing
    (warmup-excluded) per Pitfall P1 -- the registry's get_metrics() separates
    first-inference from steady-state.
    """

    items: list[Detection2D]
    inference_ms: float
    image_hw: tuple[int, int]  # (H, W) in pixels


# Tuple of required wire-dict keys for OrientedBox3D.from_wire validation (D-09 order).
_OBB_REQUIRED_WIRE_KEYS: tuple[str, ...] = (
    "center",
    "half_extents",
    "quaternion",
    "class_id",
    "class_name",
    "score",
)


@dataclass(frozen=True)
class OrientedBox3D:
    """Oriented 3D bounding box with canonical wire serialization (Phase 2, Plan 02-01).

    Conventions (locked by research/ARCHITECTURE.md Decision E + 02-CONTEXT.md D-06..D-10):
    - `center` shape (3,) float64, world frame, meters.
    - `half_extents` shape (3,) float64, along LOCAL (pre-rotation) axes, meters.
    - `quaternion` shape (4,) float64, xyzw order (scipy / Three.js convention -- NOT ROS wxyz).
      Hemisphere canonicalization (qw >= 0) is enforced by to_wire() (auto-flip when qw<0,
      D-06) and by from_wire() (raises ValueError if wire qw<0).
    - `track_id` optional; wire key OMITTED when None (D-07).
    - `bbox_xyxy` optional (x1, y1, x2, y2) pixel coords threaded from the source Detection2D
      so the frontend CameraFeed RGB overlay survives the Phase 2 cutover (02-RESEARCH Pitfall 8
      / W-01 recommendation). Wire key OMITTED when None.
    """

    center: np.ndarray          # shape (3,) float64, world frame meters
    half_extents: np.ndarray    # shape (3,) float64, meters along local axes
    quaternion: np.ndarray      # shape (4,) float64, xyzw
    class_id: int
    class_name: str
    score: float
    track_id: int | None = None
    bbox_xyxy: tuple[int, int, int, int] | None = None

    def to_wire(self) -> dict:
        """Serialize to a flat dict per D-09 field order with D-06 auto-flip.

        Invariants enforced:
        - qw >= 0 on the wire (auto-flip negative qw inputs per D-06).
        - track_id key omitted when None (D-07).
        - bbox_xyxy key omitted when None.
        - Every numeric is a plain Python float/int (D-08) -- no numpy scalars leak.
        """
        q = np.asarray(self.quaternion, dtype=np.float64)
        if q.shape != (4,):
            raise ValueError(f"quaternion must be shape (4,), got {q.shape}")
        if q[3] < 0.0:
            q = -q  # D-06 canonicalize: qw >= 0
        center = np.asarray(self.center, dtype=np.float64)
        if center.shape != (3,):
            raise ValueError(f"center must be shape (3,), got {center.shape}")
        half_extents = np.asarray(self.half_extents, dtype=np.float64)
        if half_extents.shape != (3,):
            raise ValueError(f"half_extents must be shape (3,), got {half_extents.shape}")
        out: dict[str, Any] = {
            "center": [float(c) for c in center],
            "half_extents": [float(h) for h in half_extents],
            "quaternion": [float(q[0]), float(q[1]), float(q[2]), float(q[3])],
            "class_id": int(self.class_id),
            "class_name": str(self.class_name),
            "score": float(self.score),
        }
        if self.track_id is not None:
            out["track_id"] = int(self.track_id)
        if self.bbox_xyxy is not None:
            out["bbox_xyxy"] = [int(v) for v in self.bbox_xyxy]
        return out

    @classmethod
    def from_wire(cls, obj: dict) -> "OrientedBox3D":
        """Deserialize a wire dict to an OrientedBox3D with strict validation.

        Rejects (raises ValueError):
        - Missing any required key (center, half_extents, quaternion xyzw, class_id, class_name, score).
        - Shape mismatches on numpy-backed fields.
        - qw < 0 (D-06 wire invariant; to_wire auto-flips so this is a protocol violation).
        """
        for k in _OBB_REQUIRED_WIRE_KEYS:
            if k not in obj:
                raise ValueError(f"missing required key '{k}' in wire dict")
        center = np.asarray(obj["center"], dtype=np.float64)
        if center.shape != (3,):
            raise ValueError(f"center must be shape (3,), got {center.shape}")
        half_extents = np.asarray(obj["half_extents"], dtype=np.float64)
        if half_extents.shape != (3,):
            raise ValueError(f"half_extents must be shape (3,), got {half_extents.shape}")
        quat = np.asarray(obj["quaternion"], dtype=np.float64)
        if quat.shape != (4,):
            raise ValueError(f"quaternion must be shape (4,), got {quat.shape}")
        if quat[3] < 0.0:
            raise ValueError(
                "wire invariant violated: qw < 0. OrientedBox3D.to_wire() auto-flips; "
                "callers must not emit raw quaternions."
            )
        raw_track_id = obj.get("track_id")
        track_id: int | None = None if raw_track_id is None else int(raw_track_id)
        raw_bbox = obj.get("bbox_xyxy")
        bbox_xyxy: tuple[int, int, int, int] | None = (
            None if raw_bbox is None else tuple(int(v) for v in raw_bbox)  # type: ignore[assignment]
        )
        if bbox_xyxy is not None and len(bbox_xyxy) != 4:
            raise ValueError(f"bbox_xyxy must have length 4, got {len(bbox_xyxy)}")
        return cls(
            center=center,
            half_extents=half_extents,
            quaternion=quat,
            class_id=int(obj["class_id"]),
            class_name=str(obj["class_name"]),
            score=float(obj["score"]),
            track_id=track_id,
            bbox_xyxy=bbox_xyxy,
        )


def _default_capture_pose() -> np.ndarray:
    """Default-factory helper: 4x4 identity pose. Phase 2 Wave 2 workers always overwrite."""
    return np.eye(4, dtype=np.float64)


@dataclass(frozen=True)
class Detections3D:
    """Container for one lifter call's output with envelope-level pose + timestamp.

    Phase 2 Plan 02-01 additions (per 02-CONTEXT.md D-11, D-12, D-13, D-14):
    - `capture_pose` (4x4 float64): camera-to-world transform at frame-capture time.
      The coordinator reads `robot.get_pose()` at pool.submit() time and threads it through
      the worker so downstream consumers always see the pose as-of capture, not lift-time.
      Envelope-level (not per-box) because a single frame produces all N boxes and they
      share the pose.
    - `capture_timestamp` (seconds): source is `SensorFrame.sim_time`. Phase 6 freshness
      metric computes `sim_now - capture_timestamp` directly.

    Phase 2 deprecation note: the defaults (identity pose, 0.0 timestamp) exist ONLY to
    keep Phase 1 construction sites (e.g., median_depth.py) compiling through the Wave 2
    cutover. Wave 2 DetectorWorker MUST overwrite both. Wave 4 removes the defaults.

    `detector_ms` is forwarded from the upstream Detections2D so the MetricsPanel
    (Phase 6) can show the 2D + 3D split without re-plumbing. `n_raw` vs `n_final`
    exposes the lifter's filter counts (e.g., DET-3D-07 fallback cases in Phase 4).
    """

    items: list[OrientedBox3D]
    lifter_ms: float
    detector_ms: float
    n_raw: int
    n_final: int
    image_hw: tuple[int, int]
    capture_pose: np.ndarray = field(default_factory=_default_capture_pose)
    capture_timestamp: float = 0.0

    def to_wire(self) -> dict:
        """Serialize the envelope to a flat JSON-safe dict per D-14.

        Shape: {items, capture_pose (flat 16-float row-major), capture_timestamp,
        image_hw, metrics: {detector_ms, lifter_ms, n_raw, n_final}}.
        """
        pose = np.asarray(self.capture_pose, dtype=np.float64)
        pose_flat = [float(v) for v in pose.reshape(-1)]
        if len(pose_flat) != 16:
            raise ValueError(
                f"capture_pose must flatten to 16 elements (4x4 row-major), got {len(pose_flat)}"
            )
        return {
            "items": [it.to_wire() for it in self.items],
            "capture_pose": pose_flat,
            "capture_timestamp": float(self.capture_timestamp),
            "image_hw": [int(self.image_hw[0]), int(self.image_hw[1])],
            "metrics": {
                "detector_ms": float(self.detector_ms),
                "lifter_ms": float(self.lifter_ms),
                "n_raw": int(self.n_raw),
                "n_final": int(self.n_final),
            },
        }
