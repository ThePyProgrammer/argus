from __future__ import annotations

import numpy as np


def compute_collision_summaries(
    positions: dict[str, np.ndarray],
    footprint_radius: float,
    near_miss_margin: float = 0.25,
) -> dict[str, dict[str, int]]:
    summaries = {
        rid: {"collision_count": 0, "near_miss_count": 0}
        for rid in positions
    }
    ids = list(positions)
    collision_distance = 2.0 * float(footprint_radius)
    near_miss_distance = collision_distance + float(near_miss_margin)

    for i, rid_a in enumerate(ids):
        for rid_b in ids[i + 1:]:
            a = np.asarray(positions[rid_a], dtype=np.float64)[:2]
            b = np.asarray(positions[rid_b], dtype=np.float64)[:2]
            distance = float(np.linalg.norm(a - b))
            if distance < collision_distance:
                summaries[rid_a]["collision_count"] += 1
                summaries[rid_b]["collision_count"] += 1
            elif distance < near_miss_distance:
                summaries[rid_a]["near_miss_count"] += 1
                summaries[rid_b]["near_miss_count"] += 1
    return summaries
