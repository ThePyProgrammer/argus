"""D-12 regression test: YOLOv11Backend bbox+count parity with ObjectDetector._detect.

Per CONTEXT.md D-12 and Pitfall P16: the new DetectorProtocol-driven YOLOv11Backend
must produce the SAME 2D detections as the pre-refactor ObjectDetector._detect
on a frozen RGB+depth fixture. This proves the abstraction layer introduces zero
behavioural regression.

Tolerance (D-12 locked):
- count: exact match
- class_id set: exact match
- bbox_xyxy: exact match (0-pixel delta). If the CI runner surfaces NMS flakes
  on repeated runs, relax to +/-2 pixels with an explicit comment — this is the
  CONTEXT.md-sanctioned relaxation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "yolo_regression_scene_01.npz"
BBOX_TOL = 0  # D-12: bit-exact. Raise to 2 only with documented CI flake evidence.


def _ultralytics_available() -> bool:
    try:
        import ultralytics  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _ultralytics_available(),
    reason="ultralytics + torch required for D-12 regression test",
)


@pytest.fixture(scope="module")
def fixture_frame():
    assert FIXTURE.exists(), (
        f"Missing fixture: {FIXTURE}. "
        f"Run: python tests/fixtures/generate_yolo_regression_fixture.py"
    )
    data = np.load(FIXTURE)
    rgb = data["rgb"]
    depth = data["depth"]
    pose = data["pose"]
    sim_time = float(data["sim_time"])
    frame = SensorFrame(rgb=rgb, depth=depth, ground_truth_pose=pose, sim_time=sim_time)
    return frame, rgb, depth, pose


def test_fixture_npz_structure_is_stable():
    """Canary — fails loudly if someone regenerates the fixture with wrong shape."""
    data = np.load(FIXTURE)
    assert data["rgb"].shape == (480, 640, 3), data["rgb"].shape
    assert data["rgb"].dtype == np.uint8
    assert data["depth"].shape == (480, 640), data["depth"].shape
    assert data["depth"].dtype == np.float32
    assert data["pose"].shape == (4, 4)
    assert data["pose"].dtype == np.float64


def _run_object_detector(rgb, depth, pose):
    """Exercise the pre-refactor code path: ObjectDetector._detect."""
    from ultralytics import YOLO
    from src.perception.detector import ObjectDetector

    od = ObjectDetector(confidence=0.5, device="cpu", max_fps=2.0)
    od._model = YOLO("yolo11n.pt")
    od._model.to("cpu")
    return od._detect(rgb, depth, pose)


def _run_yolov11_backend(frame: SensorFrame):
    """Exercise the new code path: YOLOv11Backend.process_frame."""
    import src.perception.backends  # noqa: F401 -- triggers @detector_backend registration
    from src.perception.backends.yolov11_backend import YOLOv11Backend

    backend = YOLOv11Backend(model_name="yolo11n.pt", confidence=0.5, device="cpu")
    backend.warmup(frame)
    return backend.process_frame(frame)


def _canonicalize_obj(dets):
    """(class_id, bbox_xyxy, class_name) tuples, sorted. Drops confidence so NMS
    float noise between the two call paths cannot fail the compare."""
    return sorted(
        (d.class_id, tuple(d.bbox), d.class_name)
        for d in dets
    )


def _canonicalize_backend(dets2d):
    return sorted(
        (d.class_id, d.bbox_xyxy, d.class_name)
        for d in dets2d.items
    )


def test_yolov11_backend_matches_object_detector_on_fixture(fixture_frame):
    """CONTEXT.md D-12: bit-exact 2D parity on the frozen fixture."""
    frame, rgb, depth, pose = fixture_frame

    od_dets = _run_object_detector(rgb, depth, pose)
    backend_dets = _run_yolov11_backend(frame)

    od_canon = _canonicalize_obj(od_dets)
    bk_canon = _canonicalize_backend(backend_dets)

    assert len(od_canon) == len(bk_canon), (
        f"Detection count diverged: ObjectDetector={len(od_canon)}, "
        f"YOLOv11Backend={len(bk_canon)}.\n"
        f"OD: {od_canon}\nBackend: {bk_canon}"
    )

    od_ids = sorted(t[0] for t in od_canon)
    bk_ids = sorted(t[0] for t in bk_canon)
    assert od_ids == bk_ids, f"class_id multisets diverged: OD={od_ids} vs BK={bk_ids}"

    for od_tup, bk_tup in zip(od_canon, bk_canon):
        od_cls, od_bbox, od_name = od_tup
        bk_cls, bk_bbox, bk_name = bk_tup
        assert od_cls == bk_cls, (od_tup, bk_tup)
        assert od_name == bk_name, (od_tup, bk_tup)
        deltas = [abs(a - b) for a, b in zip(od_bbox, bk_bbox)]
        max_delta = max(deltas) if deltas else 0
        assert max_delta <= BBOX_TOL, (
            f"bbox parity failed for class {od_cls}: "
            f"OD={od_bbox} vs BK={bk_bbox} (max delta={max_delta} px > tol={BBOX_TOL})"
        )


def test_yolov11_backend_returns_empty_on_empty_classes(fixture_frame):
    """With class_filter=[] (no classes allowed), backend must return 0 detections."""
    frame, rgb, depth, pose = fixture_frame

    import src.perception.backends  # noqa: F401
    from src.perception.backends.yolov11_backend import YOLOv11Backend

    backend = YOLOv11Backend(class_filter=[])
    backend.warmup(frame)
    out = backend.process_frame(frame)
    assert len(out.items) == 0
