#!/usr/bin/env python3
"""SimWorld gym API discovery script.

Connects to a running SimWorld UE5 instance via the gym interface, prints
observation/action space details, measures step rate, and writes findings
to docs/simworld_discovery.md.

Requirements:
  - SimWorld UE5 packaged binary running with UnrealCV server on port 9000
  - ``pip install simworld_gym`` (from SimWorld-Robotics/simworld_gym/SimWorldGym)

If SimWorld is not available, run with ``--source-only`` to document findings
from source code reading alone (no runtime needed).

Usage:
    python scripts/discover_simworld.py               # full runtime discovery
    python scripts/discover_simworld.py --source-only  # source-code-only mode
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Constants discovered from SimWorld-Robotics source code reading
# ---------------------------------------------------------------------------
# Env registration IDs (from simworld_gym/__init__.py):
#   - "simworld_gym/SimpleWorld"  -> SimpleEnv (single-agent)
#   - "simworld_gym/BufferWorld"  -> BufferEnv (multi-agent, async buffer)
#   - "simworld_gym/TrafficWorld" -> TrafficEnv
#
# Uses legacy ``gym`` package (NOT gymnasium).
# Action space: Discrete(6) from action_config.json
#   0: MOVE_FORWARD, 1: MOVE_BACKWARD, 2: MOVE_LEFT, 3: MOVE_RIGHT
#   4: TURN_RIGHT (90 deg), 5: TURN_LEFT (-90 deg)
#   100: TERMINATE (special)
# Movement params: speed=5000, duration=0.1s per step
# Rotation params: duration=0.1s, angle=+/-90 degrees
#
# Observation types (constructor param ``observation_type``):
#   "ground_truth" -> Dict{relative_target_location(3,), relative_target_orientation(1,)}
#   "rgb"          -> Dict{rgb: Box(0,255, (H,W,3), uint8)}
#   "depth"        -> Dict{depth: Box(0,255, (H,W,1), uint8)}
#   "rgbd"         -> Dict{rgb: ..., depth: ...}
#   "all"          -> Dict{rgb: ..., depth: ..., object_mask: Box(0,255,(H,W,3),uint8)}
#
# Default resolution: (320, 240) i.e. W=320, H=240
# Camera FOV: 120 degrees (set in agent_controller._generate_agent)
#
# Depth format WARNING:
#   unrealcv_basic._decode_npy() applies log-normalization + gamma + JET colormap
#   -> returns (H, W, 3) uint8 visualization, NOT raw metric depth.
#   Raw depth is available as npy before _decode_npy, but the gym pipeline
#   always calls _decode_npy. Bridge must patch or bypass this for metric depth.
#
# Ground-truth pose:
#   info["agent"]["agent_location"] = np.array([x, y, z]) in Unreal units (cm)
#   info["agent"]["agent_rotation"] = cardinal direction string (e.g. "North")
#   Raw rotation [roll, pitch, yaw] in degrees is on agent_controller._agent_rotation
#   Full 6-DOF pose must be assembled from location + yaw.
#
# Step timing:
#   Each movement action does: time.sleep(performing_time + 0.05) then polls
#   agent availability. performing_time = duration from action_config (0.1s).
#   So minimum wall-clock per step ~ 0.15s + polling latency -> ~5-6 Hz theoretical max.
#
# Multi-agent (BufferWorld):
#   Uses ActionBuffer with async per-agent availability flags.
#   observation returns per-agent arrays indexed by agent_indexes.

GO_NOGO_THRESHOLD_HZ = 5.0

ENV_ID = "simworld_gym/SimpleWorld"
OBSERVATION_TYPE = "rgbd"
DEFAULT_RESOLUTION = (320, 240)


def write_discovery_doc(
    doc_path: str,
    runtime_results: dict | None = None,
) -> None:
    """Write discovery findings to markdown."""
    lines: list[str] = []
    lines.append("# SimWorld Gym API Discovery")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')}")
    lines.append("**Source:** SimWorld-Robotics GitHub (SCAI-JHU/SimWorld-Robotics)")
    lines.append("**Method:** Source code reading + runtime discovery (if available)")
    lines.append("")

    # -- Environment ID --
    lines.append("## Environment IDs")
    lines.append("")
    lines.append("Registered in `simworld_gym/__init__.py`:")
    lines.append("")
    lines.append("| ID | Entry Point | Notes |")
    lines.append("|---|---|---|")
    lines.append("| `simworld_gym/SimpleWorld` | `SimpleEnv` | Single-agent, synchronous stepping |")
    lines.append("| `simworld_gym/BufferWorld` | `BufferEnv` | Multi-agent, async action buffer |")
    lines.append("| `simworld_gym/TrafficWorld` | `TrafficEnv` | Traffic simulation variant |")
    lines.append("")
    lines.append("**Important:** Uses legacy `gym` package, NOT `gymnasium`. Import as `import gym`.")
    lines.append("")

    # -- Observation Space --
    lines.append("## Observation Space")
    lines.append("")
    lines.append("Controlled by `observation_type` constructor parameter:")
    lines.append("")
    lines.append("| Type | Keys | Shapes | Dtypes |")
    lines.append("|---|---|---|---|")
    lines.append("| `ground_truth` | `relative_target_location`, `relative_target_orientation` | (3,), (1,) | float64 |")
    lines.append("| `rgb` | `rgb` | (H, W, 3) | uint8 |")
    lines.append("| `depth` | `depth` | (H, W, 1) | uint8 |")
    lines.append("| `rgbd` | `rgb`, `depth` | (H, W, 3), (H, W, 1) | uint8 |")
    lines.append("| `all` | `rgb`, `depth`, `object_mask` | (H, W, 3), (H, W, 1), (H, W, 3) | uint8 |")
    lines.append("")
    lines.append(f"Default resolution: W={DEFAULT_RESOLUTION[0]}, H={DEFAULT_RESOLUTION[1]}.")
    lines.append("")
    lines.append("### Depth Format Warning")
    lines.append("")
    lines.append("The depth image is **NOT raw metric depth**. The `_decode_npy()` method in")
    lines.append("`unrealcv_basic.py` applies:")
    lines.append("1. Log normalization: `depth_log = np.log(raw_depth + eps)`")
    lines.append("2. Min-max scaling to [0, 1]")
    lines.append("3. Gamma correction (gamma=0.5)")
    lines.append("4. Scale to uint8 [0, 255]")
    lines.append("5. OpenCV JET colormap -> (H, W, 3) uint8")
    lines.append("")
    lines.append("**For SLAM, we need raw metric depth.** The bridge must intercept the npy")
    lines.append("response BEFORE `_decode_npy()` is called, or patch the method to return")
    lines.append("raw float32 values. The raw npy from UnrealCV contains float32 depth in")
    lines.append("Unreal units (likely centimeters, needs verification at runtime).")
    lines.append("")

    # -- Action Space --
    lines.append("## Action Space")
    lines.append("")
    lines.append("Type: `Discrete(6)` (from `action_config.json`)")
    lines.append("")
    lines.append("| Index | Meaning | Type | Parameters |")
    lines.append("|---|---|---|---|")
    lines.append("| 0 | MOVE_FORWARD | Move_Speed | speed=5000, duration=0.1s, dir=0 |")
    lines.append("| 1 | MOVE_BACKWARD | Move_Speed | speed=5000, duration=0.1s, dir=1 |")
    lines.append("| 2 | MOVE_LEFT | Move_Speed | speed=5000, duration=0.1s, dir=2 |")
    lines.append("| 3 | MOVE_RIGHT | Move_Speed | speed=5000, duration=0.1s, dir=3 |")
    lines.append("| 4 | TURN_RIGHT | Rotate_Angle | duration=0.1s, angle=90 deg |")
    lines.append("| 5 | TURN_LEFT | Rotate_Angle | duration=0.1s, angle=-90 deg |")
    lines.append("| 100 | TERMINATE | Special | Ends episode |")
    lines.append("")
    lines.append("**Note:** Action -1 triggers subtask evaluation (internal to SimpleEnv).")
    lines.append("For our bridge, use actions 0-5 only.")
    lines.append("")

    # -- Ground Truth Pose --
    lines.append("## Ground-Truth Pose")
    lines.append("")
    lines.append("Available in the `info` dict returned by `step()` and `reset()`:")
    lines.append("")
    lines.append("```python")
    lines.append('info["agent"]["agent_location"]  # np.array([x, y, z]) in Unreal units (cm)')
    lines.append('info["agent"]["agent_rotation"]  # cardinal direction string: "North", "South", etc.')
    lines.append("```")
    lines.append("")
    lines.append("Raw rotation `[roll, pitch, yaw]` in degrees is stored internally on")
    lines.append("`agent_controller._agent_rotation` but is NOT directly exposed in info.")
    lines.append("The info dict only has the discretized cardinal direction.")
    lines.append("")
    lines.append("**For full 6-DOF ground-truth pose**, the bridge needs to either:")
    lines.append("1. Subclass SimpleEnv to expose raw rotation in info, OR")
    lines.append("2. Access `env.agent_controller._agent_rotation` directly (fragile).")
    lines.append("")
    lines.append("Position is straightforward: `info['agent']['agent_location']` gives (x, y, z).")
    lines.append("")

    # -- Camera Intrinsics --
    lines.append("## Camera Intrinsics")
    lines.append("")
    lines.append("Not directly exposed in observations or info dict.")
    lines.append("")
    lines.append("From source code (`agent_controller._generate_agent`):")
    lines.append(f"- **FOV:** 120 degrees (hardcoded)")
    lines.append(f"- **Resolution:** {DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]} (default, configurable)")
    lines.append("")
    lines.append("Computed intrinsics (assuming symmetric horizontal FOV):")
    w, h = DEFAULT_RESOLUTION
    fov_deg = 120.0
    fx = w / (2.0 * np.tan(np.radians(fov_deg / 2.0)))
    fy = fx  # square pixels assumed
    cx, cy = w / 2.0, h / 2.0
    lines.append(f"- **fx = fy:** {fx:.2f} pixels")
    lines.append(f"- **cx:** {cx:.1f}, **cy:** {cy:.1f}")
    lines.append("")
    lines.append("These must be verified at runtime by checking depth-to-3D reprojection quality.")
    lines.append("")

    # -- Step Rate --
    lines.append("## Step Rate")
    lines.append("")
    if runtime_results and "step_rate" in runtime_results:
        sr = runtime_results["step_rate"]
        lines.append(f"**Measured (runtime, {sr['num_steps']} steps):**")
        lines.append(f"- Mean: {sr['mean_hz']:.1f} Hz")
        lines.append(f"- Min: {sr['min_hz']:.1f} Hz")
        lines.append(f"- Max: {sr['max_hz']:.1f} Hz")
        lines.append(f"- Median: {sr['median_hz']:.1f} Hz")
    else:
        lines.append("**Estimated from source code (no runtime available):**")
        lines.append("")
        lines.append("Each discrete movement action takes:")
        lines.append("- `performing_time` = duration from config = 0.1s")
        lines.append("- `time.sleep(performing_time + 0.05)` = 0.15s minimum")
        lines.append("- Availability polling loop with 0.05s sleep intervals")
        lines.append("- Image capture overhead (UnrealCV PNG/npy request)")
        lines.append("")
        lines.append("**Estimated range: 3-6 Hz** depending on UE5 rendering load.")
        lines.append("The 0.15s mandatory sleep alone limits to ~6.7 Hz theoretical max.")
    lines.append("")

    # -- Go/No-Go --
    lines.append("## Go/No-Go Determination")
    lines.append("")
    lines.append(f"Criterion: step rate >= {GO_NOGO_THRESHOLD_HZ} Hz for real-time SLAM.")
    lines.append("")
    if runtime_results and "step_rate" in runtime_results:
        mean_hz = runtime_results["step_rate"]["mean_hz"]
        if mean_hz >= GO_NOGO_THRESHOLD_HZ:
            lines.append(f"**GO** -- measured {mean_hz:.1f} Hz >= {GO_NOGO_THRESHOLD_HZ} Hz threshold.")
        else:
            lines.append(f"**NO-GO: batch mode required** -- measured {mean_hz:.1f} Hz < {GO_NOGO_THRESHOLD_HZ} Hz threshold.")
            lines.append("Consider reducing resolution, disabling rendering effects, or processing frames offline.")
    else:
        lines.append("**CONDITIONAL GO** -- source code analysis suggests 3-6 Hz is likely.")
        lines.append("This is borderline for the 5 Hz threshold. Recommendations:")
        lines.append("1. Measure at runtime before committing to real-time SLAM")
        lines.append("2. If below 5 Hz, reduce resolution from 320x240 to 160x120")
        lines.append("3. If still below 5 Hz, switch to batch/offline processing per CONTEXT.md")
        lines.append("4. The mandatory `time.sleep(0.15)` per step is the main bottleneck --")
        lines.append("   consider patching SimpleEnv.step() to reduce or remove the sleep")
    lines.append("")

    # -- Surprises / Deviations --
    lines.append("## Surprises and Deviations from Research Assumptions")
    lines.append("")
    lines.append("1. **Legacy gym, not gymnasium:** SimWorld uses `import gym` (OpenAI gym),")
    lines.append("   not `import gymnasium`. Our bridge must handle this compatibility.")
    lines.append("   The `step()` return signature matches gymnasium (5 values), but")
    lines.append("   registration and spaces use old gym API.")
    lines.append("")
    lines.append("2. **Depth is NOT metric:** The default pipeline returns colorized uint8,")
    lines.append("   not raw float32 meters. This is a critical blocker for depth-based SLAM.")
    lines.append("   Raw npy is available from UnrealCV but the gym wrapper destroys it.")
    lines.append("")
    lines.append("3. **Ground-truth rotation is discretized:** Info dict only has cardinal")
    lines.append("   direction strings, not continuous rotation. Raw rotation must be extracted")
    lines.append("   from internal state or the env must be subclassed.")
    lines.append("")
    lines.append("4. **Discrete action space only:** Continuous velocity control is not")
    lines.append("   implemented (raises NotImplementedError). The robot moves in fixed")
    lines.append("   increments with 90-degree turns.")
    lines.append("")
    lines.append("5. **Reset requires task_path and config JSONs:** SimpleEnv.reset()")
    lines.append("   expects `options={'task_path': ..., 'world_json': ..., 'agent_json': ...}`.")
    lines.append("   Cannot simply call `env.reset()` without configuration files.")
    lines.append("")
    lines.append("6. **Camera FOV is very wide (120 deg):** This causes significant barrel")
    lines.append("   distortion in depth-to-3D conversion. Intrinsics computation must account")
    lines.append("   for this wide angle.")
    lines.append("")

    os.makedirs(os.path.dirname(doc_path), exist_ok=True)
    Path(doc_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Discovery document written to {doc_path}")


def run_runtime_discovery(env_id: str, obs_type: str, resolution: tuple, num_steps: int = 50) -> dict:
    """Run live discovery against a SimWorld instance."""
    import gym  # noqa: F811 -- SimWorld uses legacy gym

    results: dict = {}

    print(f"Creating environment: {env_id}")
    env = gym.make(
        env_id,
        observation_type=obs_type,
        resolution=resolution,
    )

    print("\n=== Observation Space ===")
    print(f"Type: {type(env.observation_space)}")
    if hasattr(env.observation_space, "spaces"):
        for key, space in env.observation_space.spaces.items():
            print(f"  {key}: shape={space.shape}, dtype={space.dtype}")

    print(f"\n=== Action Space ===")
    print(f"Type: {env.action_space}")
    print(f"Sample: {env.action_space.sample()}")

    print("\n=== Reset ===")
    obs, info = env.reset()
    print(f"Observation type: {type(obs)}")
    if isinstance(obs, dict):
        for key, value in obs.items():
            if hasattr(value, "shape"):
                print(f"  {key}: shape={value.shape}, dtype={value.dtype}")
            else:
                print(f"  {key}: type={type(value)}, value={value}")

    print(f"\nInfo keys: {list(info.keys())}")
    for key, value in info.items():
        print(f"  {key}: {type(value)} = {value}")

    # -- Step rate measurement --
    print(f"\n=== Step Rate ({num_steps} steps) ===")
    times = []
    for i in range(num_steps):
        action = env.action_space.sample()
        t0 = time.monotonic()
        obs, reward, terminated, truncated, info = env.step(action)
        dt = time.monotonic() - t0
        times.append(dt)
        if terminated or truncated:
            obs, info = env.reset()

    times_arr = np.array(times)
    hz = 1.0 / times_arr
    results["step_rate"] = {
        "num_steps": num_steps,
        "mean_hz": float(np.mean(hz)),
        "min_hz": float(np.min(hz)),
        "max_hz": float(np.max(hz)),
        "median_hz": float(np.median(hz)),
    }

    print(f"Mean: {results['step_rate']['mean_hz']:.1f} Hz")
    print(f"Min:  {results['step_rate']['min_hz']:.1f} Hz")
    print(f"Max:  {results['step_rate']['max_hz']:.1f} Hz")

    # -- Go/No-Go --
    mean_hz = results["step_rate"]["mean_hz"]
    if mean_hz >= GO_NOGO_THRESHOLD_HZ:
        print(f"\n>>> GO -- {mean_hz:.1f} Hz >= {GO_NOGO_THRESHOLD_HZ} Hz")
    else:
        print(f"\n>>> NO-GO: batch mode required -- {mean_hz:.1f} Hz < {GO_NOGO_THRESHOLD_HZ} Hz")

    env.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover SimWorld gym API")
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Document source code findings only (no runtime needed)",
    )
    parser.add_argument("--steps", type=int, default=50, help="Number of steps for rate measurement")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    doc_path = str(project_root / "docs" / "simworld_discovery.md")

    runtime_results = None
    if not args.source_only:
        try:
            runtime_results = run_runtime_discovery(
                ENV_ID, OBSERVATION_TYPE, DEFAULT_RESOLUTION, args.steps
            )
        except Exception as e:
            print(f"\nRuntime discovery failed: {e}")
            print("Falling back to source-only mode.\n")

    write_discovery_doc(doc_path, runtime_results)
    print("\nDiscovery complete.")


if __name__ == "__main__":
    main()
