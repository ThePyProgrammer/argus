"""Replay saved camera motion in a static fixture to isolate depth odometry.

Uses poses from diagnose_exploration_contacts.py to place a diagnostic camera.
Only its initial pose enters SLAM; subsequent simulator poses score estimates.
Robot geometry is omitted. This is not a closed-loop navigation evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

from src.bridge.depth import clean_metric_depth
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.exploration.evaluation.scenarios import load_scenario
from src.slam.slam_pipeline import SLAMPipeline


def diagnose(input_path: Path, robot_id: str, output: Path, limit: int | None = None) -> dict:
    raw = input_path.read_bytes()
    saved = json.loads(raw)
    sample = saved["episode"]["result"]["provenance"]["sample"]
    rows = [row for row in saved["poses"] if row["robot"] == robot_id]
    if limit is not None:
        if limit <= 0:
            raise ValueError("Frame limit must be positive")
        rows = rows[:limit]
    if not rows:
        raise ValueError(f"No poses for {robot_id}")
    initial = saved["initial"][robot_id]
    intrinsics = CameraIntrinsics(**initial["intrinsics"])
    mount = np.linalg.inv(np.asarray(rows[0]["true_body_pose"])) @ np.asarray(initial["camera_pose"])
    camera_from_body = np.linalg.inv(mount)
    scene = load_scenario(sample["scenario_id"])
    xml = ET.fromstring(scene.mjcf_xml)
    fovy = np.rad2deg(2 * np.arctan(intrinsics.height / (2 * intrinsics.fy)))
    ET.SubElement(xml.find("worldbody"), "camera", name="odometry_probe", fovy=str(fovy))
    model = mujoco.MjModel.from_xml_string(ET.tostring(xml, encoding="unicode"))
    data = mujoco.MjData(model)
    camera_id = model.camera("odometry_probe").id
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    frames = []
    with mujoco.Renderer(model, height=intrinsics.height, width=intrinsics.width) as renderer:
        for index, row in enumerate(rows):
            body_truth = np.asarray(row["true_body_pose"])
            camera_truth = body_truth @ mount
            model.cam_pos[camera_id] = camera_truth[:3, 3]
            quat = Rotation.from_matrix(camera_truth[:3, :3]).as_quat()
            model.cam_quat[camera_id] = quat[[3, 0, 1, 2]]
            mujoco.mj_forward(model, data)
            renderer.update_scene(data, camera=camera_id)
            renderer.enable_depth_rendering()
            depth = renderer.render().copy()
            renderer.disable_depth_rendering()
            depth = clean_metric_depth(depth, float(model.vis.map.zfar * model.stat.extent))
            seed = camera_truth.copy() if index == 0 else np.eye(4)
            if index:
                seed[:3, 3] = [100., -100., 100.]  # Detect accidental live truth assistance.
            frame = SensorFrame(np.zeros((*depth.shape, 3), dtype=np.uint8), depth, seed, row["time_s"])
            estimate = pipeline.process_frame(frame)
            body = estimate @ camera_from_body
            frames.append({
                "time_s": row["time_s"],
                "body_planar_error_m": float(np.linalg.norm((body[:3, 3] - body_truth[:3, 3])[:2])),
                "camera_translation_error_m": float(np.linalg.norm(estimate[:3, 3] - camera_truth[:3, 3])),
                "orientation_error_deg": float(np.rad2deg(Rotation.from_matrix(estimate[:3, :3].T @ camera_truth[:3, :3]).magnitude())),
                "tracking_ok": pipeline.tracking_ok,
                "registration": dict(pipeline.registration_metrics),
            })
            if index % 100 == 0:
                print(f"{robot_id}: {index + 1}/{len(rows)} frames", flush=True)
    summary = {
        "scenario": sample["scenario_id"], "robot": robot_id, "seed": sample["seed"],
        "frames": len(frames), "final": frames[-1],
        "max_body_planar_error_m": max(row["body_planar_error_m"] for row in frames),
        "rejected_frames": sum(not row["tracking_ok"] for row in frames),
        "partially_observed_updates": sum(row["tracking_ok"] and 0 < row["registration"]["observable_rank"] < 6 for row in frames),
    }
    source_root = Path(__file__).resolve().parents[1]
    report = {"summary": summary, "input_sha256": hashlib.sha256(raw).hexdigest(),
              "fixture_sha256": hashlib.sha256(scene.mjcf_xml.encode()).hexdigest(),
              "camera_intrinsics": vars(intrinsics), "cloud_config_key": "1",
              "scope": "static-scene camera replay; initial pose seed only; not closed-loop navigation",
              "source_sha256": {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest()
                                for name in ("src/slam/slam_pipeline.py", "src/slam/surface_odometry.py")},
              "frames": frames}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--robot", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(diagnose(args.input, args.robot, args.output, args.limit), indent=2))


if __name__ == "__main__":
    main()
