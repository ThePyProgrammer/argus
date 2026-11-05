"""Replay saved commands without navigation; inspect gait and physical contacts.

This is an offline physics replay, not a fresh exploration validation. Saved
coverage is not recomputed or claimed as coverage for changed controller motion.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mujoco
import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import RobotCommand
from src.exploration.evaluation.episode import _benchmark_model, _contacts
from src.exploration.evaluation.scenarios import load_scenario
from src.metrics.contact_metrics import PhysicsContactCollector
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams


def floor_clearance(model, data, geom: int, floor: int) -> float:
    """Primitive height above the fixture floor's top plane, excluding visuals.

    For a finite box floor this is height above its extended top plane, not
    distance to its edges. The benchmark robots remain above its footprint.
    """
    normal = data.geom_xmat[floor].reshape(3, 3)[:, 2]
    floor_origin = data.geom_xpos[floor].copy()
    if model.geom_type[floor] == mujoco.mjtGeom.mjGEOM_BOX:
        floor_origin += model.geom_size[floor, 2] * normal
    elif model.geom_type[floor] != mujoco.mjtGeom.mjGEOM_PLANE:
        raise ValueError("Replay clearance requires a plane or box floor")
    local_normal = data.geom_xmat[geom].reshape(3, 3).T @ normal
    size, kind = model.geom_size[geom], model.geom_type[geom]
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        extent = np.dot(size, np.abs(local_normal))
    elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        extent = size[1] * abs(local_normal[2]) + size[0] * np.linalg.norm(local_normal[:2])
    elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        extent = size[1] * abs(local_normal[2]) + size[0]
    elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        extent = size[0]
    else:
        raise ValueError("Unsupported leg collision primitive")
    return float(np.dot(data.geom_xpos[geom] - floor_origin, normal) - extent)


def replay(source: Path, output: Path, *, limit_s: float | None = None, params: GaitParams = GaitParams()):
    saved = json.loads(source.read_text(encoding="utf-8"))
    history = saved.get("episode", saved)
    sample = history["result"]["provenance"]["sample"]
    scene = load_scenario(sample["scenario_id"])
    positions = {p["robot_id"]: (p["x"], p["y"], p["z"]) for p in sample["spawn_poses"]}
    headings = {p["robot_id"]: p["yaw_rad"] for p in sample["spawn_poses"]}
    config = MultiRobotConfig(robot_ids=tuple(positions), spawn_positions=positions,
                              spawn_headings=headings, launch_viewer=False)
    bridge = MultiRobotBridge(config, model_factory=lambda: _benchmark_model(scene, positions))
    rows, max_error = [], 0.
    output.mkdir(parents=True, exist_ok=False)
    contacts = None
    try:
        with patch.object(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda: None)), \
                patch.object(MultiRobotBridge, "_capture_frame", lambda *a: None):
            bridge.start()
            for rid in positions:
                bridge._controllers[rid]._gait = TrotGaitController(params)
            model, data = bridge.mj_model, bridge.mj_data
            catalog = _contacts(bridge)
            contacts = PhysicsContactCollector(catalog, start_sim_time=float(data.time))
            bridge.add_physics_step_observer(contacts.observe_step)
            floor = model.geom("floor").id
            legs = {rid: [g["geom_id"] for g in catalog.geometries
                          if g["robot_id"] == rid and g["part"] == "leg"
                          and ((model.geom_contype[g["geom_id"]] & model.geom_conaffinity[floor])
                               or (model.geom_conaffinity[g["geom_id"]] & model.geom_contype[floor]))]
                    for rid in positions}
            for index, command_row in enumerate(history["commands"][:len(history["trajectory"]) - 1]):
                if limit_s is not None and command_row["elapsed_s"] >= limit_s:
                    break
                for rid, command in command_row["commands"].items():
                    bridge.set_command(rid, RobotCommand(**command))
                bridge.step()
                expected = history["trajectory"][index + 1]
                for rid in positions:
                    base = model.body(f"{rid}_base").id
                    rot = data.xmat[base].reshape(3, 3)
                    qstart = bridge._qpos_starts[rid]
                    clearances = {g: floor_clearance(model, data, g, floor)
                                  for g in legs[rid]}
                    nearest = min(clearances, key=clearances.get)
                    error = float(np.linalg.norm(bridge.get_body_position(rid) - expected["positions"][rid]))
                    max_error = max(max_error, error)
                    rows.append({
                        "elapsed_s": expected["elapsed_s"], "robot_id": rid,
                        "command": command_row["commands"][rid], "phase": bridge._controllers[rid]._gait._phase,
                        "joint_targets": data.ctrl[bridge._ctrl_indices[rid]].tolist(),
                        "joint_angles": data.qpos[qstart + 7:qstart + 19].tolist(),
                        "body_position": bridge.get_body_position(rid).tolist(),
                        "body_rpy": [float(np.arctan2(rot[2, 1], rot[2, 2])),
                                     float(np.arcsin(np.clip(-rot[2, 0], -1, 1))),
                                     float(np.arctan2(rot[1, 0], rot[0, 0]))],
                        "minimum_leg_clearance_m": clearances[nearest], "nearest_leg_geom": nearest,
                        "body_error_from_recording_m": error,
                    })
    finally:
        bridge.stop()
        if contacts is not None:
            contacts.finish()
        report = {"source": str(source), "scope": "offline command replay; no new exploration or coverage",
                  "gait_params": asdict(params),
                  "gait_source_sha256": hashlib.sha256(
                      (Path(__file__).resolve().parents[1] / "src/locomotion/gait_controller.py").read_bytes()).hexdigest(),
                  "max_body_error_from_recording_m": max_error, "frames": rows,
                  "contacts": contacts.summary() if contacts is not None else None,
                  "contact_samples": contacts.samples() if contacts is not None else None}
        (output / "replay.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New replay output directory")
    parser.add_argument("--limit", type=float)
    parser.add_argument("--yaw-acceleration", type=float, default=GaitParams().command_yaw_acceleration)
    args = parser.parse_args()
    report = replay(args.source, args.output, limit_s=args.limit, params=replace(
        GaitParams(), command_yaw_acceleration=args.yaw_acceleration))
    print(json.dumps({"max_body_error_m": report["max_body_error_from_recording_m"],
                      "non_support_contacts": [e for e in report["contacts"]["episodes"] if e["kind"] != "foot_floor"]}, indent=2))


if __name__ == "__main__":
    main()
