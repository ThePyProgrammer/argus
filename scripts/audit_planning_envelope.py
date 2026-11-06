"""Export the offline Go2 envelope certificate and a top-view geometry overlay.

No physics stepping, sensors, SLAM, exploration, or coverage collection occurs.
Use validate_exploration.py separately for fresh live validation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from itertools import product
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mujoco
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

from src.exploration.config import ExplorationConfig
from src.exploration.evaluation.episode import _benchmark_model
from src.exploration.evaluation.geometry_audit import audit_go2_envelope
from src.exploration.evaluation.scenarios import load_scenario
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams


def projected_outline(model, data, geom):
    """Sampled silhouettes for illustration only; the certificate is analytic."""
    kind, size = model.geom_type[geom], model.geom_size[geom]
    rotation = data.geom_xmat[geom].reshape(3, 3)
    center = data.geom_xpos[geom]
    angle = np.linspace(0, 2 * np.pi, 96, endpoint=False)
    circle = size[0] * np.c_[np.cos(angle), np.sin(angle)]
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        local = np.array(list(product((-1, 1), repeat=3))) * size
        points = (local @ rotation.T + center)[:, :2]
    elif kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        local = np.vstack([np.c_[circle, np.full(len(circle), z)] for z in (-size[1], size[1])])
        points = (local @ rotation.T + center)[:, :2]
    elif kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        points = circle + center[:2]
    elif kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        points = np.vstack([circle + (center + z * rotation[:, 2])[:2] for z in (-size[1], size[1])])
    else:
        raise ValueError("Unsupported collision shape in illustration")
    return points[ConvexHull(points).vertices]


def overlay(model, report, output):
    data = mujoco.MjData(model)
    gait = TrotGaitController()
    base, cam = model.body("robot_a_base").id, model.camera("robot_a_cam").id
    panels = [("Standing", (0., 0., 0.), 0., (0., 0., 0.)),
              ("Walking / phase 0.25", (.8, 0., 0.), .25, (.2, -.2, .3)),
              ("Turning / phase 0.75", (.8, 0., 1.), .75, (-.2, .2, -.4))]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="470" viewBox="0 0 1080 470">',
           '<rect width="1080" height="470" fill="white"/>',
           '<g font-family="sans-serif" font-size="15" fill="#172331">',
           '<text x="20" y="25">Go2 collision geometry relative to the navigation body origin (metres)</text>']
    poses = []
    for index, (title, command, phase, attitude) in enumerate(panels):
        gait._phase = (phase - gait._params.frequency * .01) % 1
        gait._active_yaw = None
        data.qpos[:3] = [0, 0, .3]
        data.qpos[3:7] = np.roll(Rotation.from_euler("xyz", attitude).as_quat(), 1)
        data.qpos[7:] = gait.compute(*command, .01)
        mujoco.mj_forward(model, data)
        cx, cy, scale = 180 + 360 * index, 220, 205
        svg.append(f'<text x="{cx}" y="55" text-anchor="middle">{title}</text>')
        for radius, color, dash in ((report["planning_radius_m"]["0.1"], "#999", "5 4"),
                                     (report["body_camera_envelope_m"], "#087d52", ""),
                                     (.35, "#c3550a", "3 4")):
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{radius*scale:.3f}" fill="none" stroke="{color}" stroke-dasharray="{dash}"/>')
        outlines = []
        for row in report["geometries"]:
            points = projected_outline(model, data, row["geom_id"]) - data.xpos[base, :2]
            outlines.extend(points)
            pixels = " ".join(f'{cx+scale*x:.3f},{cy-scale*y:.3f}' for x, y in points)
            svg.append(f'<polygon points="{pixels}" fill="#397db5" fill-opacity=".25" stroke="#245782" stroke-width=".7"/>')
        camera_xy = data.cam_xpos[cam, :2] - data.xpos[base, :2]
        svg.append(f'<circle cx="{cx+scale*camera_xy[0]:.3f}" cy="{cy-scale*camera_xy[1]:.3f}" r="{.15*scale}" fill="none" stroke="#9452a0"/>')
        svg.append(f'<path d="M {cx-4} {cy} h 8 M {cx} {cy-4} v 8" stroke="#000"/>')
        poses.append({"label": title, "body_rpy": attitude, "joint_angles": data.qpos[7:].tolist(),
                      "sampled_collision_xy_radius_m": float(np.linalg.norm(outlines, axis=1).max())})
    svg.extend(['<text x="20" y="395">Green: 0.5531 m body/camera envelope. Orange: nominal 0.35 m radius.</text>',
                '<text x="20" y="418">Grey: 0.6738 m planning radius at 0.10 m resolution. Purple: camera + 0.15 m stand-off.</text>',
                '<text x="20" y="441">Blue: sampled collision silhouettes. Continuous containment uses enclosing spheres, not this sampling.</text>',
                '</g></svg>'])
    (output / "envelope.svg").write_text("\n".join(svg), encoding="utf-8")
    return poses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New artifact directory")
    parser.add_argument("--replay", type=Path, help="Optional saved gait replay.json for sampled joint-range comparison")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    model = _benchmark_model(load_scenario("connected_rooms"), {"robot_a": (0., 0., .3)})
    report = audit_go2_envelope(model)
    report["exploration_config"] = asdict(ExplorationConfig())
    report["gait_params"] = asdict(GaitParams())
    report["illustrated_poses"] = overlay(model, report, args.output)
    report["full_knee_range_certificate"] = audit_go2_envelope(model, calf_range=(-2.7227, -.83776))
    root = Path(__file__).resolve().parents[1]
    sources = ["models/unitree_go2/go2.xml", "src/locomotion/gait_controller.py",
               "src/locomotion/gait_params.py", "src/locomotion/xml_patcher.py",
               "src/bridge/platforms/go2.py", "src/bridge/scene_builder.py",
               "src/exploration/config.py", "src/exploration/evaluation/episode.py",
               "src/exploration/evaluation/geometry_audit.py", "scripts/audit_planning_envelope.py"]
    report["source_sha256"] = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sources}
    if args.replay:
        saved = json.loads(args.replay.read_text(encoding="utf-8"))
        joints = np.asarray([row["joint_angles"] for row in saved["frames"]])
        calves = joints[:, 2::3]
        report["recorded_replay"] = {
            "path": str(args.replay), "sha256": hashlib.sha256(args.replay.read_bytes()).hexdigest(),
            "scope": "recorded frame samples only, not every physics step",
            "calf_min_rad": float(calves.min()), "calf_max_rad": float(calves.max()),
            "within_declared_range": bool(np.all(calves >= report["calf_range_rad"][0])
                                          and np.all(calves <= report["calf_range_rad"][1]))}
    (args.output / "audit.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("contained", "collision_radius_bound_m", "body_camera_envelope_m",
                                            "containment_slack_m", "planning_radius_m")}, indent=2))
    if not report["contained"]:
        raise SystemExit("Envelope not certified; see retained audit.json")


if __name__ == "__main__":
    main()
