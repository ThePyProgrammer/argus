"""Perception data types: 2D + 3D detection dataclasses and input-mode enum.

This module is the bottom of the perception module stack per CONTEXT.md
"Known tricky bits" (Pitfall P9: types.py -> protocol.py -> registry.py -> backends/).
It imports ONLY stdlib + numpy. Importing this module must NOT pull torch,
ultralytics, or transformers into sys.modules -- tests/perception/test_protocol_contracts.py
enforces this invariant.

Phase 1 scope:
- Detection2D / Detections2D per CONTEXT.md D-03 (extras dict optional)
- OrientedBox3D SKELETON per CONTEXT.md "Claude's Discretion": fields only,
  no to_wire / from_wire / __eq__ tolerance -- those ship in Phase 2 with the
  canonical wire format work (research/ARCHITECTURE.md Decision E).
- Detections3D wrapper so Detection3DProtocol.lift(...) has a concrete return type.
- DetectorInput enum per CONTEXT.md "Claude's Discretion" (Enum picked over Literal
  for type-safe registration-time capability checking in Plan 03's registry).
"""

from __future__ import annotations

from dataclasses import dataclass
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

    Per CONTEXT.md D-03:
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


@dataclass(frozen=True)
class OrientedBox3D:
    """Oriented 3D bounding box -- SKELETON ONLY in Phase 1.

    Per CONTEXT.md "Known tricky bits": `to_wire()` / `from_wire()` + the
    round-trip test + the canonical quaternion-hemisphere enforcement
    (`qw >= 0`) land in Phase 2 alongside the OBB wire format work
    (DET-3D-03 / DET-3D-04). Phase 1 ships fields only.

    Conventions (locked by research/ARCHITECTURE.md Decision E):
    - `center` shape (3,) float64, world frame, meters.
    - `half_extents` shape (3,) float64, along LOCAL (pre-rotation) axes, meters.
    - `quaternion` shape (4,) float64, **xyzw** order (scipy / Three.js
      convention -- NOT ROS's wxyz). Canonicalization (qw >= 0) is Phase 2.
    """

    center: np.ndarray          # shape (3,) float64, world frame meters
    half_extents: np.ndarray    # shape (3,) float64, meters along local axes
    quaternion: np.ndarray      # shape (4,) float64, xyzw
    class_id: int
    class_name: str
    score: float
    track_id: int | None = None


@dataclass(frozen=True)
class Detections3D:
    """Container for one lifter call's output.

    `detector_ms` is forwarded from the upstream Detections2D so the
    MetricsPanel (Phase 6) can show the 2D + 3D split without re-plumbing.
    `n_raw` vs `n_final` exposes the lifter's filter counts (e.g.,
    DET-3D-07 fallback cases in Phase 4).
    """

    items: list[OrientedBox3D]
    lifter_ms: float
    detector_ms: float
    n_raw: int
    n_final: int
    image_hw: tuple[int, int]
