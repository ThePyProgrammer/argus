"""Offline stationary-pose sensitivity probe on a saved terminal observed map.

This is a controlled settled-state experiment, not a replay of the live guard's
velocity/gait history. Only estimated versus diagnostic true body pose changes;
the observed map and every guard setting remain identical.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from src.control.motion_clearance import MotionClearanceGuard
from src.exploration.config import ExplorationConfig
from src.exploration.occupancy_grid import OccupancyGrid2D, CELL_OCCUPIED


def probe(attempt):
    raw = (attempt / "diagnosis.json").read_bytes()
    saved = json.loads(raw)
    episode = saved["episode"]
    config = ExplorationConfig(**episode["result"]["provenance"]["exploration_config"])
    results = {}
    for rid in saved["initial"]:
        row = next(r for r in reversed(saved["poses"]) if r["robot"] == rid)
        with np.load(attempt / f"{rid}-final-planning" / "frontiers.npz", allow_pickle=False) as data:
            cells = data["grid"].copy()
            grid = OccupancyGrid2D(cells, float(data["resolution"]), data["origin"].copy(), cells.shape[1], cells.shape[0])
        radius = episode["commands"][-1]["motion_clearance"][rid]["radius_m"]
        centers = grid.origin + (np.argwhere(cells == CELL_OCCUPIED)[:, ::-1] + .5) * grid.resolution
        results[rid] = {}
        for key in ("estimated_body_pose", "true_body_pose"):
            pose = np.asarray(row[key])
            guard = MotionClearanceGuard(config)
            for i in range(int(np.ceil(config.motion_settling_s / .01)) + 3):
                now = i * .01
                state = dict(pose=pose, sim_time=now, observation_time=now, grid=grid,
                             radius=radius, calibration_valid=True, tracking_ok=True)
                guard.filter(np.zeros(2), 0., **state)
            state.update(sim_time=now+.01, observation_time=now+.01)
            nearest = float(np.linalg.norm(centers - pose[:2, 3], axis=1).min()) if len(centers) else None
            decisions = {}
            for command in ((-.6, 0., 0.), (0., 0., .5), (0., 0., -.5), (.2, 0., 0.)):
                decision = guard.preview(np.array(command[:2]), command[2], **state)
                decisions[str(command)] = {"reason": decision.reason, "linear": decision.linear.tolist(),
                    "angular": decision.angular, "scale": decision.scale, "stopping_clear": decision.stopping_clear}
            results[rid][key] = {"nearest_occupied_center_m": nearest, "planning_radius_m": radius,
                "static_surplus_m": None if nearest is None else nearest-radius, "proposals": decisions}
    return {"scope": "hypothetical stationary settled history; fixed terminal observed map; diagnostic pose substitution only; no live commands",
            "diagnosis_sha256": hashlib.sha256(raw).hexdigest(),
            "terminal_sim_time_s": episode["result"]["elapsed_s"],
            "robots": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = probe(args.attempt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
