"""Capture failed planning inputs and probe actual frontier cells after the run."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sys

import numpy as np
from scipy.ndimage import label

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.exploration.evaluation.episode import ExplorationEpisode
from src.exploration.evaluation.scenarios import list_scenarios
from src.exploration.frontier_detector import FrontierDetector
from src.exploration.occupancy_grid import CELL_OCCUPIED, OccupancyGrid2D
from src.exploration.path_planner import PathPlanner


def inspect_attempt(attempt: dict, directory: Path) -> dict:
    grid = attempt["grid"]
    start, goal = attempt["start"], attempt["goal"]
    planner = PathPlanner()
    costs = planner._get_inflation_cost(grid)
    start_cell, goal_cell = grid.world_to_grid(start[:2]), grid.world_to_grid(goal[:2])
    passable = (grid.grid != CELL_OCCUPIED) & (costs < 1e5)
    components, _ = label(passable, structure=np.ones((3, 3), dtype=int))
    # Match the current A* rule: the start may itself be occupied/inflated,
    # but every destination cell of a move must be passable.
    sr, sc = start_cell
    neighbors = [(r, c) for r in range(max(0, sr - 1), min(grid.height, sr + 2))
                 for c in range(max(0, sc - 1), min(grid.width, sc + 2)) if passable[r, c]]
    reachable = np.isin(components, [components[cell] for cell in neighbors]) & passable
    clusters = FrontierDetector(resolution=grid.resolution, min_cluster_size=attempt["min_cluster_size"]).detect(
        np.empty((0, 3)), grid_2d=grid)
    frontier = np.zeros(grid.grid.shape, dtype=bool)
    selected_cluster = np.zeros(grid.grid.shape, dtype=bool)
    for cluster in clusters:
        frontier[cluster.voxels[:, 0], cluster.voxels[:, 1]] = True
        if np.allclose(cluster.centroid, goal):
            selected_cluster[cluster.voxels[:, 0], cluster.voxels[:, 1]] = True
    candidates = np.argwhere(selected_cluster & reachable)
    alternatives = sorted((tuple(cell) for cell in candidates), key=lambda cell: (
        float(np.linalg.norm(grid.grid_to_world(*cell) - start[:2])), *cell))
    alternative, path = None, None
    for cell in alternatives:
        target = np.r_[grid.grid_to_world(*cell), 0.]
        path = planner.plan(start, target, grid)
        if path is not None:
            alternative = target
            break
    result = {
        "robot_id": attempt["robot_id"], "sim_time": attempt["sim_time"],
        "original_path_found": attempt["path_found"],
        "grid_shape": list(grid.grid.shape), "resolution_m": grid.resolution,
        "start_world": start.tolist(), "goal_world": goal.tolist(),
        "body_world": attempt["body"].tolist(), "camera_world": attempt["camera"].tolist(),
        "start_cell": list(start_cell), "goal_cell": list(goal_cell),
        "start_occupancy": int(grid.grid[start_cell]), "goal_occupancy": int(grid.grid[goal_cell]),
        "start_inflation_cost": float(costs[start_cell]), "goal_inflation_cost": float(costs[goal_cell]),
        "start_passable_neighbors": len([cell for cell in neighbors if cell != start_cell]),
        "frontier_clusters": len(clusters), "frontier_cells": int(frontier.sum()),
        "selected_cluster_cells": int(selected_cluster.sum()),
        "goal_is_frontier_cell": bool(frontier[goal_cell]),
        "reachable_frontier_cells": int((frontier & reachable).sum()),
        "reachable_selected_cluster_cells": len(alternatives),
        "alternative_goal_world": None if alternative is None else alternative.tolist(),
        "alternative_path_waypoints": 0 if path is None else len(path),
    }
    if "occupied_voxels" in attempt:
        voxels = attempt["occupied_voxels"]
        # Projection marks voxel centers using round, while queries use floor.
        voxel_cells = np.round((voxels[:, :2] - grid.origin) / grid.resolution).astype(int)
        heights = voxels[(voxel_cells[:, 0] == goal_cell[1]) & (voxel_cells[:, 1] == goal_cell[0]), 2]
        bins, counts = np.unique(np.round(voxels[:, 2] / grid.resolution).astype(int), return_counts=True)
        result.update(goal_column_voxel_heights_m=heights.tolist(),
                      voxel_height_bins=[{"bin": int(b), "count": int(c)} for b, c in zip(bins, counts)],
                      goal_reference_clear=attempt["goal_reference_clear"])
    directory.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(directory / "planning.npz", grid=grid.grid, origin=grid.origin,
                        resolution=grid.resolution, start=start, goal=goal, costs=costs,
                        frontier=frontier, selected_cluster=selected_cluster, reachable=reachable,
                        alternative_path=np.empty((0, 3)) if path is None else np.asarray(path),
                        occupied_voxels=attempt.get("occupied_voxels", np.empty((0, 3))))
    (directory / "diagnosis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    _overlay(directory / "planning.svg", grid, costs, frontier, start_cell, goal_cell, path, attempt["robot_id"])
    return result


def _overlay(path, grid, costs, frontier, start, goal, route, robot_id):
    width, height = grid.width, grid.height
    # Row increases with world Y. Flip only the map group, preserving readable labels.
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -10 {width+4} {height+22}" width="900">',
             f'<rect x="-2" y="-10" width="{width+4}" height="{height+22}" fill="white"/>',
             f'<text x="0" y="-5" font-size="3">{escape(robot_id)}: captured planning grid</text>',
             f'<g transform="translate(0 {height}) scale(1 -1)">']
    colors = np.full(grid.grid.shape, "#f4f4f4", dtype="U7")
    colors[grid.grid == 0] = "#d9e3eb"
    colors[costs >= 1e5] = "#efb97f"
    colors[grid.grid == CELL_OCCUPIED] = "#333333"
    colors[frontier] = "#3388dd"
    for row in range(height):
        col = 0
        while col < width:
            end = col + 1
            while end < width and colors[row, end] == colors[row, col]:
                end += 1
            parts.append(f'<rect x="{col}" y="{row}" width="{end-col}" height="1" fill="{colors[row,col]}"/>')
            col = end
    if route is not None:
        points = " ".join(f"{(p[0]-grid.origin[0])/grid.resolution},{(p[1]-grid.origin[1])/grid.resolution}" for p in route)
        parts.append(f'<polyline points="{points}" fill="none" stroke="#9224b5" stroke-width=".7"/>')
    for cell, color in ((start, "#15943e"), (goal, "#e52929")):
        parts.append(f'<circle cx="{cell[1]+.5}" cy="{cell[0]+.5}" r="1.3" fill="{color}" stroke="white" stroke-width=".3"/>')
    parts.extend(['</g>', f'<text x="0" y="{height+5}" font-size="2.3">Green: start | Red: selected target | Purple: alternative route</text>',
                  f'<text x="0" y="{height+9}" font-size="2.3">Black: occupied | Orange: inflation | Blue: frontier | Pale: unknown</text>', '</svg>'])
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=list_scenarios(), default="branching_corridor")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--horizon", type=float, default=.35)
    parser.add_argument("--output-root", type=Path, default=Path("outputs/exploration-planning"))
    args = parser.parse_args()
    captured = []
    with ExplorationEpisode.from_scenario(args.scenario, args.seed, horizon_s=args.horizon) as episode:
        for rid, robot in episode.coordinator.robots.items():
            original = robot.exploration._path_planner.plan
            def capture(start, goal, grid, *, rid=rid, original=original, robot=robot):
                result = original(start, goal, grid)
                captured.append({"robot_id": rid, "sim_time": episode.bridge.get_frame(rid).sim_time,
                                 "path_found": result is not None, "start": start.copy(), "goal": goal.copy(),
                                 "body": episode.bridge.get_body_position(rid),
                                 "camera": episode.bridge.get_frame(rid).ground_truth_pose[:3, 3].copy(),
                                 "min_cluster_size": robot.exploration.config.min_cluster_size,
                                 "occupied_voxels": robot.octomap.get_occupied_voxels().copy(),
                                 "goal_reference_clear": episode.reference.check_spawn(float(goal[0]), float(goal[1])).accepted,
                                 "grid": OccupancyGrid2D(grid.grid.copy(), grid.resolution, grid.origin.copy(), grid.width, grid.height)})
                return result
            robot.exploration._path_planner.plan = capture
        while episode.inspect()["state"] == "running":
            episode.advance()
        result = episode.inspect()["result"]
    directory = args.output_root / f"{args.scenario}-seed-{args.seed}"
    reports = [inspect_attempt(attempt, directory / f"attempt-{index:03d}-{attempt['robot_id']}")
               for index, attempt in enumerate(captured)]
    directory.mkdir(parents=True, exist_ok=True)
    summary = {"episode_result": result, "attempts": reports}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"termination": result["termination_reason"], "attempts": reports}, indent=2))


if __name__ == "__main__":
    main()
