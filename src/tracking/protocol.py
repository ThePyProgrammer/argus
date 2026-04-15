"""TrackerProtocol: runtime-checkable interface for detection trackers.

Mirror of src.perception.protocol.DetectorProtocol structure. Phase 7 ships
NoneTracker (passthrough); Phase 8 ships ByteTrack. Pool integration (per-
frame coordinator pump calling tracker.track()) is Phase 8 (D-14) — Phase 7
keeps this purely a pipeline-editor surface.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.perception.types import Detections3D


@runtime_checkable
class TrackerProtocol(Protocol):
    """Runtime-checkable interface for multi-object trackers.

    Contract:
      - `track(detections_3d)` MUST stamp `track_id` on each box in the
        envelope and return a NEW envelope (immutable pass-through).
      - MUST NOT mutate geometry fields: center, half_extents, quaternion,
        class_id, class_name, score (Phase 2 D-03 wire-format invariant).
      - MUST preserve capture_pose + capture_timestamp (Phase 2 D-11).
      - `reset()` clears internal state (per session or per coordinator restart).
      - `CAPABILITIES` dict must include: framework, produces_stable_ids, license.
    """

    CAPABILITIES: dict

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        """Return a NEW Detections3D with track_ids stamped on every box."""
        ...

    def reset(self) -> None:
        """Clear internal tracker state."""
        ...
