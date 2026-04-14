"""Deterministic generator for tests/fixtures/yolo_regression_scene_01.npz.

Produces a committed NPZ fixture consumed by
tests/integration/test_pool_end_to_end.py to prove DetectorWorkerPool
dataflow preserves detection parity with a direct YOLOv11Backend +
MedianDepthLifter call (Plan 02-12 replacement for the retired D-12
regression test; see Phase 1 01-VERIFICATION.md §W-01 for the parity
rationale).

Usage:
    uv run --active python tests/fixtures/generate_yolo_regression_fixture.py

The script is idempotent — re-running produces a bit-identical NPZ.
The resulting NPZ is committed via git-lfs (``.gitattributes`` tracks
``tests/fixtures/*.npz``).

W-01 FIX (Plan 02-12): the generator ASSERTS ``len(detections) >= 1``
BEFORE writing the NPZ. The former Mode A (MuJoCo office-scene render)
produced zero YOLO detections at 480x640 and the former Mode B
(synthetic rectangles) likewise produced zero — a 0==0 parity tautology
that passed the D-12 regression vacuously. Any future regression that
makes the scene undetectable now fails LOUDLY at generation time.

Mode selection (single mode, documented W-01 fix):

  **Mode A' — ultralytics bus.jpg deterministically resized to 480x640.**

  Rationale:
  1. MuJoCo's go2 scene (models/unitree_go2/scene.xml via the default
     MuJoCoEnvConfig) renders an empty office with the robot's front
     camera pointed at mostly-untextured walls. YOLOv11 returns zero
     detections at every tested resolution (320x240, 640x480, 1280x960)
     with the confidence=0.5 threshold carried forward from the legacy
     ObjectDetector — no COCO-class object is in view.
  2. ``ultralytics/assets/bus.jpg`` ships with the ultralytics pip
     package, is YOLO's de facto demo scene, and produces stable
     detections (4 persons at conf > 0.6 post-resize). It is
     deterministic across ultralytics versions (the file hash is locked
     by the package release) and was COPIED into the repo as
     ``tests/fixtures/yolo_regression_source_bus.jpg`` so generation
     works even without ultralytics installed.
  3. This satisfies the plan's "Mode A' synthetic scene with a chair
     image overlay or a different scene choice" escape valve
     (02-12-PLAN.md Task 4 step 2).

  The resize uses cv2.INTER_AREA which is deterministic across OpenCV
  versions for downscaling.

NPZ schema (locked — consumed by test_pool_end_to_end.py):
    rgb   : (480, 640, 3)  uint8
    depth : (480, 640)     float32   (uniform 2.0 m — sufficient for
                                      MedianDepthLifter.project_center
                                      _median_depth on every bbox)
    pose  : (4, 4)         float64   (identity — camera at world origin)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


FIXTURE_PATH = Path(__file__).parent / "yolo_regression_scene_01.npz"
SOURCE_IMAGE = Path(__file__).parent / "yolo_regression_source_bus.jpg"


def _generate_frame() -> dict[str, np.ndarray]:
    """Produce the deterministic (rgb, depth, pose, sim_time) payload.

    See module docstring for Mode A' rationale.
    """
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "opencv-python-headless is required to regenerate the W-01 fixture. "
            "Install the base deps: `uv pip install -e .`"
        ) from exc

    if not SOURCE_IMAGE.exists():  # pragma: no cover
        raise RuntimeError(
            f"Missing source image: {SOURCE_IMAGE}. This file ships in the repo "
            f"(copied from ultralytics/assets/bus.jpg). Restore it from git."
        )

    img_bgr = cv2.imread(str(SOURCE_IMAGE))
    if img_bgr is None:
        raise RuntimeError(f"cv2.imread returned None for {SOURCE_IMAGE}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(img_rgb, (640, 480), interpolation=cv2.INTER_AREA).astype(np.uint8)

    depth = np.full((480, 640), 2.0, dtype=np.float32)
    pose = np.eye(4, dtype=np.float64)
    sim_time = np.array(0.0, dtype=np.float64)

    print("[fixture] mode=A' (ultralytics bus.jpg resized to 480x640 via INTER_AREA)",
          file=sys.stderr)
    return {"rgb": rgb, "depth": depth, "pose": pose, "sim_time": sim_time}


def _verify_yolo_detects_objects(rgb: np.ndarray, depth: np.ndarray) -> None:
    """W-01 acceptance gate: the generated frame MUST produce >=1 YOLO detection.

    Failing loudly here prevents the fixture from silently regressing to a
    0==0 parity tautology (the exact bug W-01 records in Phase 1 VERIFICATION.md).
    """
    import src.perception.backends  # noqa: F401 — triggers @detector_backend
    from src.bridge.sensor_types import SensorFrame
    from src.perception.registry import DetectorRegistry

    det = DetectorRegistry.create("yolov11")
    frame = SensorFrame(
        rgb=rgb, depth=depth, ground_truth_pose=np.eye(4), sim_time=0.0
    )
    d2d = det.process_frame(frame)
    if len(d2d.items) < 1:
        raise RuntimeError(
            "W-01 violation: fixture produces 0 YOLO detections. "
            "tests/integration/test_pool_end_to_end.py would be a 0==0 tautology. "
            "Inspect the fixture image or drop the confidence threshold."
        )
    print(
        f"[W-01] Fixture verification OK: {len(d2d.items)} YOLO detection(s) — "
        + ", ".join(
            f"{d.class_name}@{d.bbox_xyxy}(conf={d.score:.2f})"
            for d in d2d.items
        ),
        file=sys.stderr,
    )


def main() -> None:
    data = _generate_frame()
    _verify_yolo_detects_objects(data["rgb"], data["depth"])
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(FIXTURE_PATH, **data)
    print(
        f"[fixture] wrote {FIXTURE_PATH} "
        f"(rgb={data['rgb'].shape} depth={data['depth'].shape})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
