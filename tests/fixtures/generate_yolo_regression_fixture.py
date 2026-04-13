"""Deterministic generator for tests/fixtures/yolo_regression_scene_01.npz.

Produces a committed NPZ fixture consumed by tests/perception/test_yolov11_regression.py
to prove bit-exact parity between ObjectDetector._detect and YOLOv11Backend.process_frame
(CONTEXT.md D-12).

Usage:
    python tests/fixtures/generate_yolo_regression_fixture.py

The script is idempotent — re-running produces a bit-identical NPZ. Commit the
output NPZ to git alongside this script.

Two modes:
  A (preferred) — render from the MuJoCo office scene (data/scenes/office*.xml).
                  Uses MuJoCoBridge with a fixed seed + spawn position + step count.
  B (fallback)  — synthetic gradient + painted rectangles. Used when Mode A fails
                  (missing scene asset, MuJoCo init error, OS-level GL unavailable).

Either mode produces a valid D-12 fixture because the test compares the OUTPUT of
two code paths on the SAME input — it does not require the fixture to contain
ground-truth annotations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


FIXTURE_PATH = Path(__file__).parent / "yolo_regression_scene_01.npz"


def _generate_mode_a() -> dict[str, np.ndarray] | None:
    """Try to render from the real MuJoCo office scene.

    Returns a dict of NPZ arrays on success, or None if Mode A is unavailable
    (letting the caller fall through to Mode B).
    """
    try:
        # Lazy imports — Mode B must not require MuJoCo.
        from src.bridge.env_config import MuJoCoEnvConfig
        from src.bridge.sim_bridge import MuJoCoBridge
    except Exception as exc:
        print(f"[fixture] Mode A unavailable (import error): {exc}", file=sys.stderr)
        return None

    try:
        config = MuJoCoEnvConfig()
        bridge = MuJoCoBridge(config)
        bridge.start()
        frame = None
        for _ in range(10):  # let the physics settle
            frame = bridge.step()
        bridge.stop()
        if frame is None or frame.depth is None:
            print("[fixture] Mode A produced None frame; falling back to Mode B", file=sys.stderr)
            return None
        if frame.rgb.shape != (480, 640, 3):
            print(f"[fixture] Mode A frame.rgb wrong shape {frame.rgb.shape}; Mode B instead", file=sys.stderr)
            return None
        print("[fixture] mode=A (MuJoCo office scene)", file=sys.stderr)
        return {
            "rgb": frame.rgb.astype(np.uint8),
            "depth": frame.depth.astype(np.float32),
            "pose": frame.ground_truth_pose.astype(np.float64),
            "sim_time": np.array(frame.sim_time, dtype=np.float64),
        }
    except Exception as exc:
        print(f"[fixture] Mode A runtime error: {exc!r}; falling back to Mode B", file=sys.stderr)
        return None


def _generate_mode_b() -> dict[str, np.ndarray]:
    """Synthetic deterministic scene. Zero randomness — bit-identical on every run."""
    H, W = 480, 640
    ys, xs = np.mgrid[0:H, 0:W]
    base = ((xs + ys) // 4 % 256).astype(np.uint8)
    rgb = np.stack([base, base, base], axis=-1)
    rgb[120:200, 150:230] = 100    # gray block
    rgb[280:360, 300:380] = 180    # lighter gray
    rgb[50:110, 500:600] = 200     # bright block
    depth = np.full((H, W), 2.0, dtype=np.float32)
    pose = np.eye(4, dtype=np.float64)
    sim_time = np.array(0.0, dtype=np.float64)
    print("[fixture] mode=B (synthetic deterministic)", file=sys.stderr)
    return {"rgb": rgb, "depth": depth, "pose": pose, "sim_time": sim_time}


def main() -> None:
    data = _generate_mode_a()
    if data is None:
        data = _generate_mode_b()
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(FIXTURE_PATH, **data)
    print(f"[fixture] wrote {FIXTURE_PATH} "
          f"(rgb={data['rgb'].shape} depth={data['depth'].shape})", file=sys.stderr)


if __name__ == "__main__":
    main()
