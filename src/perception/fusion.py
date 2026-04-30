"""DetectionFusionManager: cross-robot detection fusion (DET-STRETCH-02).

Consumes per-robot tracked Detections3D, groups same-class detections
across robots within cluster_radius (default 0.5 m), produces fused
detections with shared fused_track_id and contributing robot_ids.

Per CONTEXT D-07: centralized, called once per coordinator stats tick
by WebStreamingViz._update_stats. Per CONTEXT D-08: class-gated
nearest-neighbor clustering. Per D-09: fused_detections WS key format.

Module-scope: stdlib + numpy only. No torch.
"""
from __future__ import annotations

import logging
from itertools import count
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.perception.types import Detections3D

_LOGGER = logging.getLogger(__name__)


class DetectionFusionManager:
    """Cross-robot detection fusion via class-gated nearest-neighbor clustering."""

    def __init__(self, cluster_radius: float = 0.5) -> None:
        self._cluster_radius = cluster_radius
        self._id_gen = count(start=0)

    def fuse(
        self,
        per_robot_detections: dict[str, Detections3D],
        sim_time: float,
    ) -> list[dict]:
        """Produce fused detection dicts from all robots' latest tracked outputs.

        Algorithm (D-08):
        1. Collect all OrientedBox3D from all robots with their robot_id.
        2. Group by class_name.
        3. Within each class: cluster by world-frame center distance.
           Two detections from DIFFERENT robots within cluster_radius are merged.
        4. Per cluster: highest-confidence detection is the representative OBB.
        5. Return list of fused entries per D-09 wire format.
        """
        # Step 1: collect all boxes with robot attribution
        all_boxes: list[tuple[str, object]] = []  # (robot_id, OrientedBox3D)
        for rid, dets in per_robot_detections.items():
            if dets is None:
                continue
            for box in dets.items:
                all_boxes.append((rid, box))

        if not all_boxes:
            return []

        # Step 2: group by class_name
        class_groups: dict[str, list[tuple[str, object]]] = {}
        for rid, box in all_boxes:
            class_groups.setdefault(box.class_name, []).append((rid, box))

        fused: list[dict] = []

        for cls, group in class_groups.items():
            # Step 3: cluster by center distance (greedy single-linkage)
            centers = np.array(
                [np.asarray(box.center, dtype=np.float64) for _, box in group],
                dtype=np.float64,
            )
            used = [False] * len(group)

            for i in range(len(group)):
                if used[i]:
                    continue
                cluster_indices = [i]
                cluster_rids = {group[i][0]}
                used[i] = True

                # Find all within radius from different robots
                for j in range(i + 1, len(group)):
                    if used[j]:
                        continue
                    if group[j][0] in cluster_rids and len(cluster_rids) == 1:
                        # Same robot, same class -- could be distinct objects
                        # Only fuse across robots per D-08
                        dist = float(np.linalg.norm(centers[i] - centers[j]))
                        if dist <= self._cluster_radius:
                            # Same robot, very close -- treat as same object
                            cluster_indices.append(j)
                            used[j] = True
                        continue
                    dist = float(np.linalg.norm(centers[i] - centers[j]))
                    if dist <= self._cluster_radius:
                        cluster_indices.append(j)
                        cluster_rids.add(group[j][0])
                        used[j] = True

                # Step 4: representative = highest confidence
                best_idx = max(cluster_indices, key=lambda k: group[k][1].score)
                best_rid, best_box = group[best_idx]
                contributing_rids = sorted(
                    set(group[k][0] for k in cluster_indices)
                )
                source_track_ids = [
                    group[k][1].track_id
                    for k in cluster_indices
                    if group[k][1].track_id is not None
                ]

                entry = best_box.to_wire()
                entry.update({
                    "fused_track_id": next(self._id_gen),
                    "class_name": cls,
                    "score": float(best_box.score),
                    "robot_ids": contributing_rids,
                    "source_track_ids": source_track_ids,
                })
                fused.append(entry)

        return fused

    def reset(self) -> None:
        """Reset fused_track_id counter."""
        self._id_gen = count(start=0)
