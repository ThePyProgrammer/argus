"""Capture contact geometry, pose errors, first routes, and initial floor occlusion.

Reference geometry and true body poses are diagnostic outputs only. They never
enter the coordinator, local map, planner, or velocity controller.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mujoco
import numpy as np

from src.exploration.evaluation.episode import ExplorationEpisode
from src.exploration.evaluation.scenarios import list_scenarios
from src.metrics.exploration_coverage import (
    DepthObservation, _floor_points, visible_reference_cells,
)
from scripts.diagnose_exploration_planning import inspect_frontier_state


def initial_visibility(episode, rid, output):
    frame = episode.bridge.get_frame(rid)
    cal = episode.bridge.camera_intrinsics(rid)
    pose = frame.ground_truth_pose
    points = _floor_points(episode.reference)
    camera = (points - pose[:3, 3]) @ pose[:3, :3]
    axial = -camera[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        u = cal.fx * camera[:, 0] / axial + cal.cx
        v = cal.cy - cal.fy * camera[:, 1] / axial
    inside = ((axial > 0) & (u >= .5) & (u < cal.width - .5)
              & (v >= .5) & (v < cal.height - .5))
    hits = {}
    for point in points[inside]:
        direction = point - pose[:3, 3]
        direction /= np.linalg.norm(direction)
        hit = np.array([-1], dtype=np.int32)
        mujoco.mj_ray(episode.bridge.mj_model, episode.bridge.mj_data,
                      pose[:3, 3], direction, None, 1, -1, hit)
        name = episode.bridge.mj_model.geom(int(hit[0])).name if hit[0] >= 0 else "none"
        hits[name] = hits.get(name, 0) + 1
    np.savez_compressed(output / f"{rid}-initial.npz", depth=frame.depth, rgb=frame.rgb,
                        camera_pose=pose, reference_points=points)
    return {"camera_pose": pose.tolist(), "intrinsics": vars(cal),
            "reference_centers_in_fov": int(inside.sum()), "ray_hits": hits,
            "visible_reference_cells": int(visible_reference_cells(
                episode.reference, DepthObservation.from_frame(frame, cal)).sum())}


@contextmanager
def _recorded_episode(scenario, seed, horizon, output, report):
    """Preserve raw measurements and partial traces even on infrastructure errors."""
    episode = ExplorationEpisode.from_scenario(scenario, seed, horizon_s=horizon)
    try:
        with episode:
            yield episode
    finally:
        report["episode"] = episode.inspect(include_history=True)
        report["reliability_events"] = episode.reliability.events() if episode.reliability is not None else []
        (output / "diagnosis.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")


def diagnose(scenario: str, seed: int, horizon: float, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    report = {"initial": {}, "first_contacts": [], "poses": [], "first_plans": []}
    seen_contacts = set()
    with _recorded_episode(scenario, seed, horizon, output, report) as episode:
        model = episode.bridge.mj_model
        ids = episode.bridge.robot_ids
        feet = {f"{rid}_{leg}" for rid in ids for leg in ("FL", "FR", "RL", "RR")}

        def record_contacts(frames):
            capture(frames)
            for contact in episode.bridge.mj_data.contact:
                a, b = int(contact.geom1), int(contact.geom2)
                if contact.dist > 0 or (a, b) in seen_contacts:
                    continue
                names = [model.geom(g).name for g in (a, b)]
                bodies = [model.body(int(model.geom_bodyid[g])).name for g in (a, b)]
                owners = [next((rid for rid in ids if name.startswith(rid + "_")), None) for name in bodies]
                if owners[0] == owners[1]:
                    continue
                if "floor" in names and any(name in feet for name in names):
                    continue
                seen_contacts.add((a, b))
                report["first_contacts"].append({
                    "time_s": next(iter(frames.values())).sim_time,
                    "geom_ids": [a, b], "geom_names": names, "body_names": bodies,
                    "penetration_m": float(-contact.dist), "point": contact.pos.tolist(),
                })

        capture = episode._capture
        episode._capture = record_contacts
        for rid, robot in episode.coordinator.robots.items():
            report["initial"][rid] = initial_visibility(episode, rid, output)
            original = robot.exploration._path_planner.plan

            def plan(start, goal, grid, _rid=rid, _original=original):
                path = _original(start, goal, grid)
                if path is not None and not any(p["robot"] == _rid for p in report["first_plans"]):
                    report["first_plans"].append({"robot": _rid,
                        "time_s": episode.bridge.get_frame(_rid).sim_time,
                        "start": start.tolist(), "goal": goal.tolist(),
                        "path": [p.tolist() for p in path]})
                    np.savez_compressed(output / f"{_rid}-first-plan.npz", grid=grid.grid,
                                        origin=grid.origin, resolution=grid.resolution)
                return path

            robot.exploration._path_planner.plan = plan

        while episode.inspect()["state"] == "running":
            # Save truth before advancing, so comparisons match the SLAM input
            # time, not the next physics frame returned by advance().
            frames = {rid: episode.bridge.get_frame(rid) for rid in ids}
            bodies = {rid: episode.bridge._extract_pose(rid) for rid in ids}
            episode.advance()
            for rid, robot in episode.coordinator.robots.items():
                camera = robot.get_pose()
                body = frames[rid].body_pose_from_camera(camera)
                truth = frames[rid].ground_truth_pose
                yaw = lambda p: float(np.arctan2(p[1, 0], p[0, 0]))
                report["poses"].append({"robot": rid, "time_s": frames[rid].sim_time,
                    "registration": dict(getattr(getattr(robot.slam, "_pipeline", None), "registration_metrics", {})),
                    "camera_translation_error_m": float(np.linalg.norm(camera[:3, 3] - truth[:3, 3])),
                    "estimated_body_pose": body.tolist(), "true_body_pose": bodies[rid].tolist(),
                    "camera_x_heading_rad": yaw(camera), "estimated_body_yaw_rad": yaw(body),
                    "true_body_yaw_rad": yaw(bodies[rid])})
        # Terminal diagnostics run after the last control decision. They do not
        # supply simulator truth or reference geometry to navigation.
        report["final_planning"] = {}
        final_poses = {row["robot"]: np.asarray(row["estimated_body_pose"])
                       for row in report["poses"][-len(ids):]}
        for rid, robot in episode.coordinator.robots.items():
            exploration = robot.exploration
            occupied = robot.octomap.get_occupied_voxels()
            report["final_planning"][rid] = inspect_frontier_state(
                exploration.planning_grid(occupied), final_poses[rid][:3, 3], output / f"{rid}-final-planning",
                min_cluster_size=exploration._config.min_cluster_size, planner=exploration._path_planner,
                occupied_voxels=occupied, observed_floor_xy=exploration.observed_floor_xy)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), default="branching_corridor")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--horizon", type=float, default=.4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose(args.scenario, args.seed, args.horizon, args.output)
    print(json.dumps({"output": str(args.output), "first_contacts": report["first_contacts"],
                      "result": report["episode"]["result"]}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
