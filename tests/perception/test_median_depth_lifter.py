"""Unit tests for MedianDepthLifter and ObjectDetector delegation.

Covers:
- Registration under 'median_depth' (CONTEXT.md D-07 + Plan 04 Task 2).
- Detection3DProtocol conformance (CONTEXT.md D-04).
- CAPABILITIES locked values (research Decision F — outputs_oriented=False).
- Lift output shape: OrientedBox3D with identity quaternion, default half-extents.
- slam_cloud argument is accepted (D-04) but ignored by this lifter.
- ObjectDetector._detect delegates the 2D→3D step to project_center_median_depth
  (CONTEXT.md D-13, Pitfall P3).
"""

from __future__ import annotations

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.protocol import Detection3DProtocol
from src.perception.types import (
    Detection2D,
    Detections2D,
    Detections3D,
    OrientedBox3D,
)


@pytest.fixture
def lifter():
    # Import inside fixture so lifters/__init__.py side-effect fires here
    import src.perception.lifters  # noqa: F401
    from src.perception.lifters.median_depth import MedianDepthLifter
    return MedianDepthLifter()


@pytest.fixture
def synthetic_frame():
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = np.eye(4)
    frame = SensorFrame(rgb=rgb, depth=depth, ground_truth_pose=pose, sim_time=0.0)
    intrinsics = CameraIntrinsics.from_fov(640, 480, 70.0)
    return frame, pose, intrinsics


def _make_det(bbox, class_id=56, class_name="chair", score=0.9):
    return Detection2D(class_id=class_id, class_name=class_name, score=score, bbox_xyxy=bbox)


def test_lifter_registered_under_median_depth():
    import src.perception.lifters  # noqa: F401 -- triggers registration
    from src.perception.registry import Detection3DRegistry

    names = [e["name"] for e in Detection3DRegistry.list_backends()]
    assert "median_depth" in names, f"MedianDepthLifter not registered: {names}"


def test_lifter_satisfies_detection_3d_protocol(lifter):
    assert isinstance(lifter, Detection3DProtocol), (
        "MedianDepthLifter must satisfy @runtime_checkable Detection3DProtocol"
    )


def test_capabilities_locked():
    from src.perception.lifters.median_depth import MedianDepthLifter

    caps = MedianDepthLifter.CAPABILITIES
    assert caps["outputs_oriented"] is False  # research Decision F
    assert caps["requires_depth"] is True
    assert caps["requires_point_cloud"] is False
    assert caps["license"] == "MIT"
    # Exactly these 4 keys (no extras in Phase 1)
    assert set(caps.keys()) == {"outputs_oriented", "requires_depth", "requires_point_cloud", "license"}


def test_available_returns_true_none():
    from src.perception.lifters.median_depth import MedianDepthLifter

    assert MedianDepthLifter.available() == (True, None)


def test_lift_identity_pose_center_depth(lifter, synthetic_frame):
    frame, pose, intr = synthetic_frame
    det = _make_det((300, 220, 340, 260))
    d2d = Detections2D(items=[det], inference_ms=10.0, image_hw=(480, 640))

    d3d = lifter.lift(d2d, frame, pose, intr, slam_cloud=None)

    assert isinstance(d3d, Detections3D)
    assert len(d3d.items) == 1
    assert d3d.n_raw == 1 and d3d.n_final == 1
    assert d3d.image_hw == (480, 640)

    obb = d3d.items[0]
    assert isinstance(obb, OrientedBox3D)
    # Center pixel = (320, 240) = principal point → cam_x=0, cam_y=0, depth=2
    # Sign-flip + identity pose → world = [0, 0, -2]
    assert np.allclose(obb.center, [0.0, 0.0, -2.0], atol=1e-6), obb.center
    # Identity quaternion xyzw
    assert np.allclose(obb.quaternion, [0.0, 0.0, 0.0, 1.0])
    # Default half-extents
    assert np.allclose(obb.half_extents, [0.25, 0.25, 0.25])
    # Class metadata forwarded
    assert obb.class_id == 56 and obb.class_name == "chair" and obb.score == 0.9
    assert obb.track_id is None


def test_lift_skips_detection_with_no_valid_depth(lifter):
    # All-zero depth → all pixels filtered out by depth_near_m > 0.1
    depth = np.zeros((480, 640), dtype=np.float32)
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = np.eye(4)
    frame = SensorFrame(rgb=rgb, depth=depth, ground_truth_pose=pose, sim_time=0.0)
    intr = CameraIntrinsics.from_fov(640, 480, 70.0)
    d2d = Detections2D(items=[_make_det((100, 100, 200, 200))], inference_ms=1.0, image_hw=(480, 640))

    d3d = lifter.lift(d2d, frame, pose, intr, slam_cloud=None)

    assert d3d.n_raw == 1
    assert d3d.n_final == 0
    assert d3d.items == []


def test_lift_ignores_slam_cloud(lifter, synthetic_frame):
    frame, pose, intr = synthetic_frame
    d2d = Detections2D(items=[_make_det((300, 220, 340, 260))], inference_ms=1.0, image_hw=(480, 640))

    d_none = lifter.lift(d2d, frame, pose, intr, slam_cloud=None)
    d_with = lifter.lift(d2d, frame, pose, intr, slam_cloud=np.random.randn(1000, 3))

    assert len(d_none.items) == len(d_with.items) == 1
    assert np.allclose(d_none.items[0].center, d_with.items[0].center)


def test_lift_handles_none_depth_frame(lifter):
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = np.eye(4)
    frame = SensorFrame(rgb=rgb, depth=None, ground_truth_pose=pose, sim_time=0.0)
    intr = CameraIntrinsics.from_fov(640, 480, 70.0)
    d2d = Detections2D(items=[_make_det((100, 100, 200, 200))], inference_ms=1.0, image_hw=(480, 640))

    d3d = lifter.lift(d2d, frame, pose, intr, slam_cloud=None)

    assert d3d.items == []
    assert d3d.n_final == 0
    assert d3d.n_raw == 1


def test_apply_params_live_tunable(lifter):
    status = lifter.apply_params({
        "depth_near_m": 0.3,
        "depth_far_m": 20.0,
        "default_half_extent_m": 0.5,
    })
    assert status == {
        "depth_near_m": "applied",
        "depth_far_m": "applied",
        "default_half_extent_m": "applied",
    }
    assert lifter.depth_near_m == 0.3
    assert lifter.depth_far_m == 20.0
    assert lifter.default_half_extent_m == 0.5


def test_apply_params_rejects_unknown_key(lifter):
    status = lifter.apply_params({"bogus": 42})
    assert status == {"bogus": "unknown_parameter"}


def test_get_metrics_reports_last_call(lifter, synthetic_frame):
    frame, pose, intr = synthetic_frame
    d2d = Detections2D(items=[_make_det((300, 220, 340, 260))], inference_ms=10.0, image_hw=(480, 640))

    lifter.lift(d2d, frame, pose, intr, slam_cloud=None)

    metrics = lifter.get_metrics()
    assert metrics["n_raw"] == 1
    assert metrics["n_final"] == 1
    assert metrics["last_lifter_ms"] >= 0.0


def test_project_center_median_depth_parity_on_identity_pose():
    """Parity guard: project_center_median_depth MUST match the pre-refactor
    detector.py:221-236 output. The Plan 05 regression test compares YOLO bboxes,
    but coordinator.py:637-654 reads det.center_3d — that field comes from this
    exact function after Task 3's rewire. If this math changes, downstream breaks.
    """
    from src.perception.lifters.median_depth import project_center_median_depth

    depth = np.full((480, 640), 2.5, dtype=np.float32)
    pose = np.eye(4)
    result = project_center_median_depth((100, 100, 200, 200), depth, pose)

    assert result is not None
    world_pt, median_d = result
    assert world_pt.shape == (3,)
    assert median_d == pytest.approx(2.5, abs=1e-6)
    # cx_px = 150, cy_px = 150; principal = (320, 240); f = 480 / (2*tan(35deg))
    import math
    f = 480 / (2.0 * math.tan(math.radians(70.0) / 2.0))
    expected_cam_x = (150 - 320) * 2.5 / f
    expected_cam_y = (150 - 240) * 2.5 / f
    expected_world = np.array([expected_cam_x, -expected_cam_y, -2.5])
    assert np.allclose(world_pt, expected_world, atol=1e-6), (world_pt, expected_world)


def test_detector_py_no_longer_has_inline_fov_math():
    """Task 3 invariant: detector.py must delegate, not inline projection math."""
    src = open("src/perception/detector.py").read()
    assert "math.radians(70" not in src, "inline 70° FOV still present in detector.py"
    assert "_math.radians(70" not in src, "inline 70° FOV still present in detector.py"
    assert "project_center_median_depth" in src, "detector.py does not delegate to MedianDepthLifter"
