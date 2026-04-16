"""ByteTrackTracker: 3D center distance association with Hungarian assignment.

Phase 8 Plan 02 -- DET-STRETCH-01 foundation. Provides stable track_id
assignment using:
  - Class-gated matching (D-03): only same-class detections compete.
  - 3D Euclidean center distance cost matrix.
  - scipy.optimize.linear_sum_assignment (Hungarian) for optimal assignment.
  - Configurable track lifecycle: track_thresh, match_thresh, frame_gap.

Invariants (Phase 2 wire-format contract):
  - Never mutates OrientedBox3D geometry (center, half_extents, quaternion,
    class_id, class_name, score). T-08-01 threat mitigation.
  - Never mutates capture_pose / capture_timestamp (Phase 2 D-11).
  - Module-scope: stdlib only -- no numpy/torch (Pitfall P9).
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from src.tracking.registry import tracker

if TYPE_CHECKING:
    from src.perception.types import Detections3D, OrientedBox3D


@tracker(name="bytetrack", display="ByteTrack (3D center distance)")
class ByteTrackTracker:
    """3D center distance tracker with Hungarian assignment and class gating."""

    CAPABILITIES = {
        "framework": "bytetrack_3d",
        "produces_stable_ids": True,
        "license": "Apache-2.0",
    }
    PARAMETER_SCHEMA = {
        "track_thresh": {
            "type": "float",
            "default": 0.3,
            "min": 0.0,
            "max": 1.0,
            "description": "Minimum confidence to create a new track",
        },
        "match_thresh": {
            "type": "float",
            "default": 0.5,
            "min": 0.1,
            "max": 2.0,
            "description": "Max center distance (m) for track association",
        },
        "frame_gap": {
            "type": "int",
            "default": 30,
            "min": 1,
            "max": 300,
            "description": "Frames before a lost track is deleted",
        },
    }

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """Always available -- scipy is a project dependency."""
        return True, None

    def __init__(
        self,
        track_thresh: float = 0.3,
        match_thresh: float = 0.5,
        frame_gap: int = 30,
    ) -> None:
        self._track_thresh = track_thresh
        self._match_thresh = match_thresh
        self._frame_gap = frame_gap
        self._next_id: int = 0
        # {track_id: {"center": np.ndarray(3,), "class_name": str, "frames_since_seen": int}}
        self._tracks: dict[int, dict] = {}

    def track(self, detections_3d: "Detections3D") -> "Detections3D":
        """Assign stable track_ids via class-gated Hungarian association.

        Returns a NEW Detections3D with track_id stamped on each box.
        Geometry fields are never mutated (T-08-01).
        """
        import numpy as np  # Lazy import per Pitfall P9
        from scipy.optimize import linear_sum_assignment

        items = detections_3d.items
        if not items:
            self._age_and_prune_tracks()
            return replace(detections_3d, items=[])

        # Group detections by class_name for class-gated matching (D-03).
        class_groups: dict[str, list[tuple[int, OrientedBox3D]]] = {}
        for idx, box in enumerate(items):
            class_groups.setdefault(box.class_name, []).append((idx, box))

        # Group active tracks by class_name.
        track_by_class: dict[str, list[int]] = {}
        for tid, state in self._tracks.items():
            track_by_class.setdefault(state["class_name"], []).append(tid)

        assigned_ids: dict[int, int | None] = {}  # det_idx -> track_id or None
        matched_track_ids: set[int] = set()

        for cls, det_list in class_groups.items():
            cls_track_ids = track_by_class.get(cls, [])
            if not cls_track_ids:
                # No existing tracks for this class -- create new tracks.
                for det_idx, box in det_list:
                    if box.score >= self._track_thresh:
                        tid = self._next_id
                        self._next_id += 1
                        self._tracks[tid] = {
                            "center": np.asarray(box.center, dtype=np.float64),
                            "class_name": cls,
                            "frames_since_seen": 0,
                        }
                        assigned_ids[det_idx] = tid
                        matched_track_ids.add(tid)
                    else:
                        assigned_ids[det_idx] = None
                continue

            # Build cost matrix: Euclidean distance between det centers and track centers.
            det_centers = np.array(
                [box.center for _, box in det_list], dtype=np.float64
            )
            track_centers = np.array(
                [self._tracks[tid]["center"] for tid in cls_track_ids],
                dtype=np.float64,
            )
            # cost shape: (n_dets, n_tracks)
            cost = np.linalg.norm(
                det_centers[:, None, :] - track_centers[None, :, :], axis=2
            )

            if cost.size == 0:
                continue

            row_ind, col_ind = linear_sum_assignment(cost)

            matched_det_indices: set[int] = set()
            for r, c in zip(row_ind, col_ind):
                if cost[r, c] <= self._match_thresh:
                    det_idx, box = det_list[r]
                    tid = cls_track_ids[c]
                    self._tracks[tid]["center"] = np.asarray(
                        box.center, dtype=np.float64
                    )
                    self._tracks[tid]["frames_since_seen"] = 0
                    assigned_ids[det_idx] = tid
                    matched_track_ids.add(tid)
                    matched_det_indices.add(r)

            # Unmatched detections: create new tracks if score >= track_thresh.
            for r, (det_idx, box) in enumerate(det_list):
                if r not in matched_det_indices:
                    if box.score >= self._track_thresh:
                        tid = self._next_id
                        self._next_id += 1
                        self._tracks[tid] = {
                            "center": np.asarray(box.center, dtype=np.float64),
                            "class_name": cls,
                            "frames_since_seen": 0,
                        }
                        assigned_ids[det_idx] = tid
                        matched_track_ids.add(tid)
                    else:
                        assigned_ids[det_idx] = None

        # Age unmatched tracks, prune expired.
        self._age_and_prune_tracks(matched_track_ids)

        # Stamp track_id via dataclasses.replace (never mutate geometry -- T-08-01).
        new_items = []
        for idx, box in enumerate(items):
            tid = assigned_ids.get(idx)
            new_items.append(replace(box, track_id=tid))
        return replace(detections_3d, items=new_items)

    def _age_and_prune_tracks(
        self, matched_ids: set[int] | None = None
    ) -> None:
        """Increment frames_since_seen for unmatched tracks; delete expired."""
        matched = matched_ids or set()
        to_delete: list[int] = []
        for tid, state in self._tracks.items():
            if tid not in matched:
                state["frames_since_seen"] += 1
                if state["frames_since_seen"] > self._frame_gap:
                    to_delete.append(tid)
        for tid in to_delete:
            del self._tracks[tid]

    def reset(self) -> None:
        """Clear all internal state; next frame creates fresh track_ids from 0."""
        self._next_id = 0
        self._tracks.clear()
