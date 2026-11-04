"""Capture floor-classification errors in the flat development fixtures.

Simulator poses label diagnostic samples only. The original filter runs first,
and its returned mask is passed to control unchanged.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from scripts.diagnose_exploration_contacts import diagnose
from src.exploration.evaluation.episode import ExplorationEpisode
from src.exploration.evaluation.scenarios import list_scenarios
from src.exploration.floor_filter import FloorFilter, FloorTracker


def floor_support(points, mask, estimated_camera, true_camera):
    """Label flat-floor samples within 2 mm after undoing estimated pose error."""
    correction = true_camera @ np.linalg.inv(estimated_camera)
    actual = points @ correction[:3, :3].T + correction[:3, 3]
    floor = np.abs(actual[:, 2]) <= .002
    return actual, {
        "points": len(points), "true_floor_points": int(floor.sum()),
        "missed_floor_points": int((floor & ~mask).sum()),
        "removed_points_above_4cm": int(((actual[:, 2] > .04) & mask).sum()),
    }


def diagnose_floor(scenario: str, seed: int, horizon: float, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    sources = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted((ROOT / "src").rglob("*.py"))}
    manifest = dict(revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    source_sha256=sources, scenario=scenario, seed=seed, horizon_s=horizon,
                    omp_num_threads=os.environ.get("OMP_NUM_THREADS"),
                    versions={p: importlib.metadata.version(p) for p in ("numpy", "scipy", "mujoco", "open3d")})
    (output / "run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    rows, worst = [], {}
    active = None
    original_advance, original_mask = ExplorationEpisode.advance, FloorTracker.mask

    def advance(episode):
        nonlocal active
        active = episode
        state = original_advance(episode)
        if len(episode._commands) % 100 == 0 or state["state"] != "running":
            print(json.dumps({"elapsed_s": state["elapsed_s"], "state": state["state"]}), flush=True)
        return state

    def observe(filter_, points, origin):
        mask = original_mask(filter_, points, origin)
        rid, robot = next((rid, robot) for rid, robot in active.coordinator.robots.items()
                          if robot.exploration._floor_filter is filter_)
        frame = active.bridge.get_frame(rid)
        estimated = robot.get_pose()
        np.testing.assert_allclose(origin, estimated[:3, 3], atol=1e-12, rtol=0)
        actual, counts = floor_support(points, mask, estimated, frame.ground_truth_pose)
        row = {"robot": rid, "time_s": frame.sim_time, **counts}
        row["floor_reacquired"] = filter_.reacquired
        plane = filter_.plane
        row["floor_plane_after"] = None if plane is None else {
            "normal": plane[0].tolist(), "offset": plane[1]}
        rows.append(row)
        missed = counts["missed_floor_points"]
        if missed >= 40 and missed > worst.get(rid, 0):
            names = [f"{rid}-worst-floor.npz"]
            if rid not in worst:
                names.append(f"{rid}-first-floor.npz")
            for name in names:
                np.savez_compressed(output / name, points=points, sensor_origin=origin, floor_mask=mask,
                                    actual_points=actual, estimated_camera=estimated,
                                    true_camera=frame.ground_truth_pose, sim_time=frame.sim_time)
            worst[rid] = missed
        return mask

    try:
        with patch.object(ExplorationEpisode, "advance", advance), patch.object(FloorTracker, "mask", observe):
            report = diagnose(scenario, seed, horizon, output)
    finally:
        manifest["source_unchanged"] = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
                                           for p, h in sources.items())
        (output / "run.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (output / "floor.json").write_text(json.dumps({"config": asdict(FloorFilter()), "frames": rows}, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), default="cluttered_room")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--horizon", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose_floor(args.scenario, args.seed, args.horizon, args.output)
    print(json.dumps(report["episode"]["result"], indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
