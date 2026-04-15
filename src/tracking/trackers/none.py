"""NoneTracker: passthrough that stamps monotonic track_ids (D-13).

Phase 7 scaffold — NOT a real tracker. Each frame's detections receive
incrementing track_ids from a session-lifetime counter; IDs are NOT stable
across frames (produces_stable_ids: False). For stable IDs, use
tracker_bytetrack (Phase 8 DET-STRETCH-01).

Invariants:
  - Never mutates OrientedBox3D geometry (Phase 2 D-03 wire-format contract).
  - Never mutates capture_pose / capture_timestamp (Phase 2 D-11).
  - Module-scope: stdlib only (itertools, dataclasses) — no numpy/torch.
"""
from __future__ import annotations

from dataclasses import replace
from itertools import count
from typing import TYPE_CHECKING

from src.tracking.registry import tracker

if TYPE_CHECKING:
    from src.perception.types import Detections3D


@tracker(name="none", display="Passthrough (no tracking)")
class NoneTracker:
    """Session-lifetime monotonic-counter passthrough tracker."""

    CAPABILITIES = {
        "framework": "stub",
        "produces_stable_ids": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """Always available — pure-stdlib implementation."""
        return True, None

    def __init__(self) -> None:
        self._counter = count(start=0)

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        """Stamp monotonic track_id on each box; geometry preserved byte-identical."""
        new_items = [
            replace(box, track_id=next(self._counter))
            for box in detections_3d.items
        ]
        return replace(detections_3d, items=new_items)

    def reset(self) -> None:
        """Reset the session counter to zero."""
        self._counter = count(start=0)
