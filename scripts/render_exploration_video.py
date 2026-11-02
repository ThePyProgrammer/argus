"""Render a measured episode as a verified physics replay with recorded coverage.

Requires the optional imageio-ffmpeg package for H.264 output. Perception and
planning are not rerun. Joint animation is reconstructed from saved commands;
every replayed body position must match the recording before video rendering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import mujoco
import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import RobotCommand
from src.exploration.evaluation.episode import _benchmark_model
from src.exploration.evaluation.scenarios import DEFAULTS, load_scenario


WIDTH, HEIGHT = 1600, 900
VIEW_W, VIEW_H = 1080, 720
COLORS = ((241, 172, 66), (67, 169, 255))  # BGR
INK, MUTED, GREEN = (239, 237, 232), (161, 150, 134), (155, 220, 91)


class ReplayBridge(MultiRobotBridge):
    def _capture_frame(self, robot_id):
        # Keep the production controller/physics ticks, without sensor rendering.
        return None


def validate_history(history):
    """Require measured, uniformly timed states and commands before each step."""
    trajectory, commands, steps = (history[k] for k in ("trajectory", "commands", "steps"))
    if len(trajectory) < 2 or len(steps) != len(trajectory):
        raise ValueError("A measured episode with aligned coverage and trajectory is required")
    dt = history["result"]["frame_dt"]
    times = np.array([row["elapsed_s"] for row in trajectory])
    if not np.isfinite(dt) or dt <= 0 or not np.allclose(
        times, np.arange(len(times)) * dt, atol=1e-9, rtol=0
    ):
        raise ValueError("Trajectory timestamps do not match the recorded frame interval")
    if len(commands) not in (len(times) - 1, len(times)):
        raise ValueError("Missing or extra command records")
    if not np.allclose([row["elapsed_s"] for row in steps], times, atol=1e-9, rtol=0):
        raise ValueError("Coverage timestamps do not match the trajectory")
    if not np.allclose([row["elapsed_s"] for row in commands], times[:len(commands)],
                       atol=1e-9, rtol=0):
        raise ValueError("Command timestamps do not precede their physics intervals")
    coverage = np.array([row["coverage"] for row in steps])
    if not np.all(np.isfinite(coverage)) or np.any((coverage < 0) | (coverage > 1)):
        raise ValueError("Invalid coverage samples")
    if not math.isclose(times[-1], history["result"]["elapsed_s"], abs_tol=1e-9):
        raise ValueError("Result duration does not match the last trajectory state")
    return times


def frame_indices(times, fps, speed):
    """Use the latest recorded state at each video time, including the last state."""
    if not np.isfinite(speed) or speed <= 0 or fps <= 0:
        raise ValueError("Playback speed and frame rate must be positive")
    samples = np.minimum(np.arange(math.ceil(times[-1] * fps / speed) + 1) * speed / fps,
                         times[-1])
    return np.searchsorted(times, samples + 1e-10, side="right") - 1


def replay(history, bridge, tolerance_m=1e-7):
    """Return reconstructed joint states, rejecting divergent body trajectories."""
    trajectory = history["trajectory"]
    states, max_error = [], 0.0
    for index, recorded in enumerate(trajectory):
        if index:
            for rid, command in history["commands"][index - 1]["commands"].items():
                bridge.set_command(rid, RobotCommand(**command))
            bridge.step()
        for rid, expected in recorded["positions"].items():
            error = float(np.linalg.norm(bridge.get_body_position(rid) - expected))
            if not math.isfinite(error) or error > tolerance_m:
                raise ValueError(f"Replay diverged at {recorded['elapsed_s']:.2f}s: {rid}, {error:g}m")
            max_error = max(max_error, error)
        states.append((bridge.mj_data.qpos.copy(), bridge.mj_data.qvel.copy()))
    # A final stop record belongs to the terminal decision, not a new interval.
    return states, max_error


def label(image, text, x, y, size=.65, color=INK, thickness=1):
    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, color,
                thickness, cv2.LINE_AA)


def top_camera(model, bounds):
    model.vis.global_.offwidth = VIEW_W
    model.vis.global_.offheight = VIEW_H
    # Free cameras take projection settings from model.vis.global_, not MjvCamera.
    model.vis.global_.orthographic = 1
    model.vis.global_.fovy = max(bounds.y_max - bounds.y_min + 1,
                                 (bounds.x_max - bounds.x_min + 1) * VIEW_H / VIEW_W)
    camera = mujoco.MjvCamera()
    camera.azimuth, camera.elevation, camera.distance = 90, -90, 20
    camera.lookat[:] = [(bounds.x_min + bounds.x_max) / 2,
                        (bounds.y_min + bounds.y_max) / 2, 0]
    return camera


def top_view(renderer, bridge, camera, history, index, robot_ids):
    renderer.update_scene(bridge.mj_data, camera=camera)
    scene, model = renderer.scene, bridge.mj_model
    for geom in scene.geoms[:scene.ngeom]:
        if geom.objtype != mujoco.mjtObj.mjOBJ_GEOM or geom.objid < 0:
            continue
        body_name = model.body(model.geom_bodyid[geom.objid]).name
        for rid, color in zip(robot_ids, COLORS):
            if body_name.startswith(rid + "_"):
                geom.rgba[:] = [*(np.array(color[::-1]) / 255), 1]
    for rid, color in zip(robot_ids, COLORS):
        points = np.array([row["positions"][rid] for row in history["trajectory"][:index + 1]])
        points[:, 2] = .015
        # Thin the trail in distance, preserving its current endpoint.
        kept = [points[0]]
        for point in points[1:]:
            if np.linalg.norm(point - kept[-1]) >= .04:
                kept.append(point)
        kept.append(points[-1])
        for start, end in zip(kept, kept[1:]):
            if scene.ngeom >= scene.maxgeom:
                raise RuntimeError("Too many trajectory segments for the renderer")
            if np.linalg.norm(end - start) < 1e-8:
                continue
            geom = scene.geoms[scene.ngeom]
            mujoco.mjv_initGeom(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, np.zeros(3),
                               np.zeros(3), np.eye(3).ravel(),
                               np.array([*(np.array(color[::-1]) / 255), 1], dtype=np.float32))
            mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_CAPSULE, .018, start, end)
            scene.ngeom += 1
    return cv2.cvtColor(renderer.render(), cv2.COLOR_RGB2BGR)


def compose(view, history, times, index, speed):
    result, step = history["result"], history["steps"][index]
    sample = result["provenance"]["sample"]
    elapsed, coverage = times[index], step["coverage"]
    frame = np.full((HEIGHT, WIDTH, 3), (26, 23, 19), dtype=np.uint8)
    label(frame, "ARGUS / MULTI-ROBOT EXPLORATION", 32, 42, .85, thickness=2)
    title = sample["scenario_id"].replace("_", " ").title()
    label(frame, f"{title}  /  seed {sample['seed']}  /  {speed:g}x playback", 32, 77, .6, MUTED)
    frame[108:108 + VIEW_H, 24:24 + VIEW_W] = view
    x = 1140
    label(frame, "RECORDED FLOOR COVERAGE", x, 137, .6, MUTED)
    label(frame, f"{100 * coverage:.1f}%", x, 211, 1.85, GREEN, 3)
    label(frame, f"{step['observed_cells']:,} reference cells observed", x, 251, .57)
    label(frame, f"Simulation time   {elapsed:05.2f} / {times[-1]:.2f} s", x, 292, .57)
    left, right, top, bottom = x + 35, 1558, 347, 568
    def chart_point(t, c):
        return (round(left + (right - left) * t / times[-1]),
                round(bottom - (bottom - top) * c))
    for value in (0, .5, 1):
        y = chart_point(0, value)[1]
        cv2.line(frame, (left, y), (right, y), (62, 54, 44), 1)
        label(frame, f"{int(value * 100)}", x - 5, y + 5, .4, MUTED)
    threshold = result["coverage"]["config"]["threshold"]
    target_y = chart_point(0, threshold)[1]
    for dash in range(left, right, 12):
        cv2.line(frame, (dash, target_y), (min(dash + 6, right), target_y), MUTED, 1)
    label(frame, f"{threshold:.0%} target", right - 111, target_y - 8, .45, MUTED)
    points = np.array([chart_point(times[i], row["coverage"])
                       for i, row in enumerate(history["steps"][:index + 1])], np.int32)
    if len(points) > 1:
        cv2.polylines(frame, [points], False, GREEN, 2, cv2.LINE_AA)
    cursor = chart_point(elapsed, coverage)
    cv2.line(frame, (cursor[0], top), (cursor[0], bottom), (90, 85, 70), 1)
    cv2.circle(frame, cursor, 5, GREEN, -1, cv2.LINE_AA)
    label(frame, "0 s", left - 8, bottom + 25, .45, MUTED)
    label(frame, f"{times[-1]:.2f} s", right - 49, bottom + 25, .45, MUTED)
    for i, rid in enumerate(history["trajectory"][0]["positions"]):
        y = 659 + i * 42
        cv2.circle(frame, (x + 8, y - 7), 7, COLORS[i], -1, cv2.LINE_AA)
        label(frame, rid.replace("_", " ").title() + " + traveled path", x + 28, y, .57)
    terminal = index == len(times) - 1
    status = "Exploring"
    if terminal:
        status = result["termination_reason"].replace("_", " ").capitalize()
        if any("SLAM tracking lost" in e.get("message", "") for e in history["events"]):
            status = "Stopped: SLAM tracking lost"
    label(frame, status, x, 777, .62, (117, 181, 255) if terminal else INK)
    label(frame, "Top view / command replay with verified body positions", 32, 860, .55, MUTED)
    label(frame, "Coverage: saved measurements", 1140, 860, .5, MUTED)
    return frame


def render(input_path, output, *, fps=25, speed=.5):
    import imageio_ffmpeg

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    history = payload.get("episode", payload)
    times = validate_history(history)
    indices = frame_indices(times, fps, speed)
    sample = history["result"]["provenance"]["sample"]
    scene = load_scenario(sample["scenario_id"])
    if scene.scenario_sha256 != sample["scenario_sha256"]:
        raise ValueError("The recorded scenario differs from the current fixture")
    positions = {p["robot_id"]: (p["x"], p["y"], p["z"]) for p in sample["spawn_poses"]}
    headings = {p["robot_id"]: p["yaw_rad"] for p in sample["spawn_poses"]}
    if len(positions) != 2:
        raise ValueError("This layout supports two robots")
    config = MultiRobotConfig(spawn_positions=positions, spawn_headings=headings,
                              robot_ids=tuple(positions), launch_viewer=False,
                              sim_steps_per_frame=DEFAULTS.sim_steps_per_frame)
    bridge = ReplayBridge(config, model_factory=lambda: _benchmark_model(scene, positions))
    renderer = None
    partial = output.with_name(output.stem + ".partial.mp4")
    preview = output.with_suffix(".png")
    report_path = output.with_suffix(".json")
    for path in (output, partial, preview, report_path):
        if path.exists():
            raise FileExistsError(f"Choose a new output name: {path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        bridge.start()
        if not math.isclose(bridge.frame_dt, history["result"]["frame_dt"], abs_tol=1e-12):
            raise ValueError("Current bridge cadence differs from the recording")
        states, max_error = replay(history, bridge)
        print(f"Verified {len(states)} body states; maximum error {max_error:.3g} m", flush=True)
        model, data = bridge.mj_model, bridge.mj_data
        camera = top_camera(model, scene.bounds)
        renderer = mujoco.Renderer(model, width=VIEW_W, height=VIEW_H)
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
                   "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
                   "-s", f"{WIDTH}x{HEIGHT}", "-r", str(fps), "-i", "pipe:0", "-an",
                   "-vcodec", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(partial)]
        total_frames = 0
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            try:
                for number, index in enumerate(indices):
                    data.qpos[:], data.qvel[:] = states[index]
                    mujoco.mj_forward(model, data)
                    view = top_view(renderer, bridge, camera, history, index, tuple(positions))
                    frame = compose(view, history, times, index, speed)
                    repeats = 1 + (fps if number == 0 else 0) + (3 * fps if number == len(indices) - 1 else 0)
                    for _ in range(repeats):
                        encoder.stdin.write(frame.tobytes())
                    total_frames += repeats
                    if number % 100 == 0:
                        print(f"Rendered {number + 1}/{len(indices)} motion frames", flush=True)
                if not cv2.imwrite(str(preview), frame):
                    raise RuntimeError("Failed to save the video preview")
            finally:
                encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError("FFmpeg failed to encode the video")
        partial.replace(output)
        report = {"input": str(input_path), "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                  "output": str(output), "scenario": sample["scenario_id"], "seed": sample["seed"],
                  "fps": fps, "playback_speed": speed, "video_frames": total_frames,
                  "video_duration_s": total_frames / fps, "simulated_duration_s": float(times[-1]),
                  "hold_start_s": 1, "hold_end_s": 3, "verified_body_samples": len(states),
                  "max_body_position_error_m": max_error, "position_tolerance_m": 1e-7,
                  "final_coverage": history["steps"][-1]["coverage"],
                  "termination_reason": history["result"]["termination_reason"],
                  "scope": "Physics command replay; joint animation reconstructed; body positions checked at every recorded state. Coverage copied from recorded measurements. No perception or planning rerun, no spatial coverage mask inferred."}
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        if renderer is not None:
            renderer.close()
        bridge.stop()
        if partial.exists():
            partial.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Contact diagnosis or measured smoke export")
    parser.add_argument("--output", type=Path, required=True, help="New MP4 path")
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--speed", type=float, default=.5, help="Simulated seconds per video second")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".mp4":
        parser.error("--output must end in .mp4")
    render(args.input, args.output, fps=args.fps, speed=args.speed)


if __name__ == "__main__":
    main()
