"""Offline controlled pose/floor/map comparisons on identical recorded scans.

Truth changes only diagnostic branches, never live commands. These comparisons
condition on recorded accepted clouds: they do not rerun depth preprocessing,
estimate unseen surfaces, or prove physical obstacle occupancy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from scripts.pose_map_archive import read_scans
from src.exploration.floor_filter import FloorFilter, FloorTracker


def distribution(values):
    values = np.asarray(values, dtype=float)
    return {"samples": int(values.size), "median": float(np.median(values)) if values.size else None,
            "p95": float(np.quantile(values, .95)) if values.size else None,
            "max": float(values.max()) if values.size else None}


def corrected_points(points, estimated, truth):
    correction = truth @ np.linalg.inv(estimated)
    return points @ correction[:3, :3].T + correction[:3, 3]


def classification(mask, actual):
    floor = np.abs(actual[:, 2]) <= .002
    low = (actual[:, 2] > .004) & (actual[:, 2] <= .04)
    high = actual[:, 2] > .04
    return {"floor_samples": int(floor.sum()), "missed_floor": int((floor & ~mask).sum()),
            "low_obstacle_samples": int(low.sum()), "removed_low_obstacle": int((low & mask).sum()),
            "raised_samples": int(high.sum()), "removed_raised": int((high & mask).sum())}


class RetainedMap:
    """Keep replay-owned immutable points through historical plane cleanup."""
    def __init__(self):
        self.rows = []

    def insert(self, points, actual, mask, plane=None, tolerance=.015):
        if plane is not None:
            normal, offset = plane
            for row in self.rows:
                row[2] &= np.abs(row[0] @ normal - offset) > tolerance
        self.rows.append([points, actual, ~mask.copy()])

    def retained(self):
        if not self.rows:
            return np.empty((0, 3)), np.empty((0, 3))
        return tuple(np.concatenate([r[i][r[2]] for r in self.rows]) for i in (0, 1))


def voxel_keys(points, resolution):
    # Fixed world lattice for all branches: a cloud-dependent voxel origin
    # would confound placement error with a different discretization phase.
    return np.unique(np.floor(points / resolution).astype(np.int64), axis=0)


def compare_map(mapped, actual, reference, resolution, reference_tree, reference_keys):
    keys = voxel_keys(mapped, resolution)
    a, b = set(map(tuple, keys)), set(map(tuple, reference_keys))
    distances = (reference_tree.query(mapped, workers=1)[0]
                 if len(mapped) and reference_tree is not None else np.empty(0))
    return {"retained_samples": len(mapped),
            "retained_true_floor_samples": int((np.abs(actual[:, 2]) <= .002).sum()),
            "paired_placement_error_m": distribution(np.linalg.norm(mapped - actual, axis=1)),
            "nearest_reference_surface_m": distribution(distances),
            "reference_surface_available": bool(len(reference)),
            "fixed_lattice": {"resolution_m": resolution, "occupied": len(a),
                "reference_occupied": len(b), "extra": len(a-b), "missing": len(b-a),
                "iou": len(a & b) / len(a | b) if a | b else None}}


def replay(scans, config=FloorFilter(), resolution=.1, placement_budget_m=.05):
    trackers = {key: FloorTracker(config) for key in ("estimated", "known")}
    maps = {key: RetainedMap() for key in ("estimated", "known", "estimated_oracle_floor", "known_oracle_floor")}
    frames = []
    for scan in scans:
        # Branches share immutable geometry but retain independent masks. Own
        # this copy so a streaming caller may reuse its input buffer safely.
        points, estimated, truth = scan["points"].copy(), scan["estimated"], scan["truth"]
        actual = corrected_points(points, estimated, truth)
        row = {"time_s": scan["time_s"], "points": len(points),
            "camera_translation_error_m": float(np.linalg.norm(estimated[:3, 3]-truth[:3, 3])),
            "camera_rotation_error_deg": float(np.rad2deg(Rotation.from_matrix(estimated[:3, :3].T @ truth[:3, :3]).magnitude())),
            "observation_placement_m": distribution(np.linalg.norm(points-actual, axis=1))}
        row["placement_samples_above_budget"] = int((np.linalg.norm(points-actual, axis=1) > placement_budget_m).sum())
        for key, cloud, camera in (("estimated", points, estimated), ("known", actual, truth)):
            tracker = trackers[key]
            acquiring = tracker.plane is None
            mask = tracker.mask(cloud, camera[:3, 3])
            row[key] = classification(mask, actual)
            if key == "estimated":
                row["recorded_mask_disagreements"] = int((mask != scan["mask"]).sum())
            plane = tracker.plane if acquiring or tracker.reacquired else None
            maps[key].insert(cloud, actual, mask, plane, config.distance_tolerance_m)
        oracle = np.abs(actual[:, 2]) <= .002
        maps["estimated_oracle_floor"].insert(points, actual, oracle)
        maps["known_oracle_floor"].insert(actual, actual, oracle)
        frames.append(row)
    reference, _ = maps["known_oracle_floor"].retained()
    reference_tree = cKDTree(reference) if len(reference) else None
    reference_keys = voxel_keys(reference, resolution)
    return {"frames": frames, "placement_budget_m": placement_budget_m,
            "placement_samples_above_budget": sum(r["placement_samples_above_budget"] for r in frames),
            "recorded_mask_disagreements": sum(r["recorded_mask_disagreements"] for r in frames),
            "maps": {key: compare_map(*value.retained(), reference, resolution, reference_tree, reference_keys)
                     for key, value in maps.items()}}


def summarize_existing(directory):
    """Score historical body poses separately from registration acceptance."""
    diagnosis = json.loads((directory / "diagnosis.json").read_text())
    floor = json.loads((directory / "floor.json").read_text())
    budget = diagnosis["episode"]["result"]["provenance"]["exploration_config"]["clearance_margin_m"]
    robots = {}
    for rid in diagnosis["initial"]:
        rows = [r for r in diagnosis["poses"] if r["robot"] == rid]
        errors = np.array([np.asarray(r["estimated_body_pose"])[:3, 3] - np.asarray(r["true_body_pose"])[:3, 3] for r in rows])
        angles = [np.rad2deg(Rotation.from_matrix(np.asarray(r["estimated_body_pose"])[:3, :3].T @ np.asarray(r["true_body_pose"])[:3, :3]).magnitude()) for r in rows]
        floors = [r for r in floor["frames"] if r["robot"] == rid]
        robots[rid] = {"body_planar_error_m": distribution(np.linalg.norm(errors[:, :2], axis=1)),
            "planar_budget_m": budget,
            "planar_frames_above_budget": int((np.linalg.norm(errors[:, :2], axis=1) > budget).sum()),
            "body_vertical_error_m": distribution(np.abs(errors[:, 2])), "body_attitude_error_deg": distribution(angles),
            "registration_rejected_frames": sum(not r["registration"].get("accepted", False) for r in rows),
            "peak_missed_floor_samples": max((r["missed_floor_points"] for r in floors), default=None),
            "peak_removed_above_4cm": max((r["removed_points_above_4cm"] for r in floors), default=None)}
    return robots


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"scope": "offline diagnostic comparison; recorded accepted clouds; flat floor labels; no live control changes",
              "pose_and_tracking": summarize_existing(args.attempt), "replay": None}
    root = Path(__file__).resolve().parents[1]
    report["source_sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("scripts/replay_pose_map.py", "scripts/pose_map_archive.py", "src/exploration/floor_filter.py")}
    diagnosis = json.loads((args.attempt / "diagnosis.json").read_text())
    result = diagnosis["episode"]["result"]
    config = result["provenance"]["exploration_config"]
    report["episode"] = {key: result[key] for key in ("elapsed_s", "termination_reason", "coverage", "contact_measurements", "reliability", "navigation")}
    report["guard_decisions"] = {rid: dict(Counter(c["motion_clearance"][rid]["reason"]
        for c in diagnosis["episode"]["commands"])) for rid in diagnosis["initial"]}
    report["reported_guard_clearance_m"] = {rid: distribution([
        c["motion_clearance"][rid]["clearance_m"] for c in diagnosis["episode"]["commands"]
        if c["motion_clearance"][rid]["clearance_m"] is not None]) for rid in diagnosis["initial"]}
    report["guard_clearance_scope"] = "Reported model margins only; absent values do not establish physical clearance."
    report["diagnostic_budgets"] = {
        "pose_and_observation_placement_m": config["clearance_margin_m"],
        "floor_inlier_band_m": config["floor_distance_tolerance_m"],
        "oracle_floor_band_m": .002, "low_obstacle_band_m": [.004, .04],
        "removed_samples_above_4cm_budget": 0,
        "interpretation": "Reporting thresholds fixed from existing planning margin and floor settings, not tracking-acceptance gates or certified uncertainty allowances. Pose and map errors can add; the same margin cannot cover both independently."}
    directory = args.attempt / "scans"
    if directory.exists():
        raw = (directory / "manifest.json").read_bytes()
        manifest = json.loads(raw)
        report.update(archive_complete=manifest["complete"], archive_manifest_sha256=hashlib.sha256(raw).hexdigest())
        report["replay"] = {rid: replay(read_scans(directory, rid), FloorFilter(**meta["floor_config"]), meta["map_resolution_m"], config["clearance_margin_m"])
                            for rid, meta in manifest["robots"].items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "pose_and_tracking": report["pose_and_tracking"],
                      "scan_replay_available": report["replay"] is not None}, indent=2))


if __name__ == "__main__":
    main()
