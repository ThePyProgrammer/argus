"""SemanticMap: TTL-based object persistence layer (DET-STRETCH-03).

Maintains {fused_track_id: SemanticObject} from DetectionFusionManager
output. Objects persist for `ttl` seconds after last observation, then
expire and are removed.

Per CONTEXT D-10: server owns truth; frontend is a dumb renderer.
Per CONTEXT D-12: default TTL is 10.0 seconds.

Delta updates (get_delta) return active objects + expired_ids for the
frontend to add/update and remove respectively.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class SemanticObject:
    """A persistent object in the semantic map."""

    fused_track_id: int
    wire_fields: dict[str, Any]
    last_seen: float  # sim_time of last observation
    ttl: float  # seconds before expiry

    def to_wire(self) -> dict[str, Any]:
        """Serialize to WS payload dict."""
        return {
            "fused_track_id": self.fused_track_id,
            **self.wire_fields,
            "last_seen": self.last_seen,
            "ttl": self.ttl,
        }


class SemanticMap:
    """TTL-based semantic map -- server side (DET-STRETCH-03 D-10)."""

    def __init__(self, ttl: float = 10.0) -> None:
        self._ttl = ttl
        self._objects: dict[int, SemanticObject] = {}

    def update(self, fused_detections: list[dict], sim_time: float) -> None:
        """Refresh timestamps for matched fused entries; add new ones."""
        for fd in fused_detections:
            fid = fd["fused_track_id"]
            wire_fields = {k: v for k, v in fd.items() if k != "fused_track_id"}
            if fid in self._objects:
                obj = self._objects[fid]
                obj.wire_fields = wire_fields
                obj.last_seen = sim_time
            else:
                self._objects[fid] = SemanticObject(
                    fused_track_id=fid,
                    wire_fields=wire_fields,
                    last_seen=sim_time,
                    ttl=self._ttl,
                )

    def get_delta(self, sim_time: float) -> dict[str, Any]:
        """Return {active: [...], expired_ids: [...]} for WS emission.

        Pitfall 3: collect expired_ids BEFORE deleting from dict.
        """
        active = []
        expired_ids = []
        for fid, obj in self._objects.items():
            if sim_time - obj.last_seen >= obj.ttl:
                expired_ids.append(fid)
            else:
                active.append(obj.to_wire())
        # Remove expired from internal dict AFTER building response
        for fid in expired_ids:
            del self._objects[fid]
        return {"active": active, "expired_ids": expired_ids}

    def reset(self) -> None:
        """Clear all objects."""
        self._objects.clear()
