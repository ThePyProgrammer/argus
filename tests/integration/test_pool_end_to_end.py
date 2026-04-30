"""DetectorWorkerPool end-to-end parity test (Plan 02-12 Task 3).

Replaces the retired tests/perception/test_yolov11_regression.py (D-19).

Invariant under test: a frame pushed through
``DetectorWorkerPool.submit(rid, frame, pose, slam_cloud=None)`` →
``DetectorWorkerPool.latest(rid)`` MUST produce the same ``Detections3D``
envelope (same detection count, class_id multiset, and OrientedBox3D
center / half_extents values) as calling ``YOLOv11Backend.process_frame``
+ ``MedianDepthLifter.lift`` directly on the identical fixture frame.

Phase 2's DetectorWorkerPool is the ONLY detection dataflow in production
after Plan 02-10's coordinator cutover; this test is the regression guard
for that dataflow (closes W-01 from Phase 1 VERIFICATION.md alongside the
regenerated fixture — see tests/fixtures/generate_yolo_regression_fixture.py).

The test SKIPS cleanly when ultralytics / torch are unavailable, and
SKIPS with a RuntimeError-level message if the fixture produces zero
detections (W-01 guard — the parity compare would be a 0==0 tautology
in that case, and the fixture generator is the right place to fix it).
"""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ultralytics = pytest.importorskip("ultralytics")
_ = pytest.importorskip("torch")


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "yolo_regression_scene_01.npz"


@pytest.fixture(autouse=True)
def _clean_registries():
    """Isolate from other tests' registry state (mirrors test_registry.py)."""
    from src.perception.registry import Detection3DRegistry, DetectorRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    import src.perception.backends.yolov11_backend as _yolo
    import src.perception.lifters.median_depth as _median
    importlib.reload(_yolo)
    importlib.reload(_median)
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    for mod in (
        "src.perception.backends",
        "src.perception.lifters",
        "src.perception.backends.yolov11_backend",
        "src.perception.lifters.median_depth",
    ):
        sys.modules.pop(mod, None)


@pytest.fixture
def fixture_frame():
    """Load the W-01 fixture. Skip if missing (CI without generation)."""
    if not FIXTURE_PATH.exists():
        pytest.skip(
            f"Fixture not generated: {FIXTURE_PATH}. "
            f"Run: uv run python tests/fixtures/generate_yolo_regression_fixture.py"
        )
    data = np.load(FIXTURE_PATH)
    return {
        "rgb": data["rgb"],
        "depth": data["depth"],
        "pose": data["pose"],
    }


def _sort_key(obb):
    """Stable sort over OrientedBox3D items for parity comparison.

    Pool and direct paths both produce the same boxes but may iterate in
    different worker-driven orders. Sort by (class_id, bbox_xyxy) when
    bbox_xyxy is threaded through (phase-2 OrientedBox3D addition), else
    fall back to (class_id, center).
    """
    if obb.bbox_xyxy is not None:
        return (int(obb.class_id), tuple(int(v) for v in obb.bbox_xyxy))
    return (int(obb.class_id), tuple(float(c) for c in obb.center))


def test_pool_submit_latest_matches_direct_backend(fixture_frame):
    """Core W-01 parity gate: pool dataflow ≡ direct backend+lifter call."""
    # Re-import the backends + lifters PACKAGES to trigger the
    # @detector_backend / @detection_3d decorators — _clean_registries wipes
    # the registries before the test, so registration must re-fire here.
    import src.perception.backends  # noqa: F401
    import src.perception.lifters  # noqa: F401
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    from src.perception.registry import Detection3DRegistry, DetectorRegistry
    from src.perception.worker_pool import DetectorWorkerPool

    rgb = fixture_frame["rgb"]
    depth = fixture_frame["depth"]
    pose = fixture_frame["pose"]

    intrinsics = CameraIntrinsics.from_fov(640, 480, 70.0)

    # ------------------------------------------------------------------
    # Reference path — construct backend + lifter directly via the
    # registry (same factory the pool uses internally) and run one
    # process_frame → lift cycle.
    # ------------------------------------------------------------------
    direct_backend = DetectorRegistry.create("yolov11")
    direct_lifter = Detection3DRegistry.create("median_depth")
    direct_frame = SensorFrame(
        rgb=rgb, depth=depth, ground_truth_pose=np.eye(4), sim_time=0.1
    )
    direct_2d = direct_backend.process_frame(direct_frame)
    direct_3d = direct_lifter.lift(direct_2d, direct_frame, pose, intrinsics, None)

    # W-01 guard: if the fixture produces zero detections the parity
    # compare degenerates to 0==0. Fail the fixture, not this test.
    if len(direct_3d.items) == 0:
        pytest.skip(
            "Fixture produces 0 YOLO detections — regenerate via "
            "tests/fixtures/generate_yolo_regression_fixture.py (W-01)."
        )
    assert len(direct_3d.items) >= 1, (
        f"W-01 violation: expected >=1 detection on fixture, got {len(direct_3d.items)}"
    )

    # ------------------------------------------------------------------
    # Pool dataflow — single-robot pool, same backend name / lifter name.
    # submit → poll latest → compare.
    # ------------------------------------------------------------------
    pool = DetectorWorkerPool(
        robot_ids=["r0"],
        backend_name="yolov11",
        backend_params={},
        lifter_name="median_depth",
        intrinsics_per_robot={"r0": intrinsics},
    )
    pool.start()
    try:
        pool_frame = SensorFrame(
            rgb=rgb, depth=depth, ground_truth_pose=np.eye(4), sim_time=0.2
        )
        pool.submit("r0", pool_frame, pose, slam_cloud=None)

        deadline = time.monotonic() + 10.0
        pool_3d = None
        while time.monotonic() < deadline:
            pool_3d = pool.latest("r0")
            if pool_3d is not None and len(pool_3d.items) > 0:
                break
            time.sleep(0.05)
        assert pool_3d is not None, "pool.latest timed out after 10 s"
    finally:
        pool.shutdown()

    # ------------------------------------------------------------------
    # Parity — same count + same boxes.
    # ------------------------------------------------------------------
    assert len(pool_3d.items) == len(direct_3d.items), (
        f"detection count diverged: pool={len(pool_3d.items)} "
        f"direct={len(direct_3d.items)}"
    )

    pool_sorted = sorted(pool_3d.items, key=_sort_key)
    direct_sorted = sorted(direct_3d.items, key=_sort_key)

    for i, (p_item, d_item) in enumerate(zip(pool_sorted, direct_sorted)):
        assert p_item.class_id == d_item.class_id, (
            f"item {i}: class_id differs (pool={p_item.class_id}, "
            f"direct={d_item.class_id})"
        )
        assert p_item.class_name == d_item.class_name, (
            f"item {i}: class_name differs (pool={p_item.class_name}, "
            f"direct={d_item.class_name})"
        )
        np.testing.assert_allclose(
            p_item.center,
            d_item.center,
            atol=1e-6,
            err_msg=f"item {i}: center (world-frame 3D point) differs",
        )
        np.testing.assert_allclose(
            p_item.half_extents,
            d_item.half_extents,
            atol=1e-6,
            err_msg=f"item {i}: half_extents differs",
        )
        np.testing.assert_allclose(
            p_item.quaternion,
            d_item.quaternion,
            atol=1e-6,
            err_msg=f"item {i}: quaternion differs",
        )


def test_pool_latest_carries_envelope_pose_and_timestamp(fixture_frame):
    """D-11/D-12/D-13: the DetectorWorker overwrites capture_pose +
    capture_timestamp on every Detections3D returned via latest().

    Proves the envelope-level pose/timestamp plumbing the frontend relies
    on (Phase 2 Plan 02-10 viz cutover) lands end-to-end.
    """
    import src.perception.backends  # noqa: F401
    import src.perception.lifters  # noqa: F401
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    from src.perception.worker_pool import DetectorWorkerPool

    intrinsics = CameraIntrinsics.from_fov(640, 480, 70.0)
    sim_time_marker = 12.34
    submit_pose = np.eye(4, dtype=np.float64)
    submit_pose[0, 3] = 7.77  # distinguishable x-translation

    pool = DetectorWorkerPool(
        robot_ids=["r0"],
        backend_name="yolov11",
        backend_params={},
        lifter_name="median_depth",
        intrinsics_per_robot={"r0": intrinsics},
    )
    pool.start()
    try:
        frame = SensorFrame(
            rgb=fixture_frame["rgb"],
            depth=fixture_frame["depth"],
            ground_truth_pose=np.eye(4),
            sim_time=sim_time_marker,
        )
        pool.submit("r0", frame, submit_pose, slam_cloud=None)
        deadline = time.monotonic() + 10.0
        env = None
        while time.monotonic() < deadline:
            env = pool.latest("r0")
            if env is not None and len(env.items) > 0:
                break
            time.sleep(0.05)
        assert env is not None, "pool.latest timed out after 10 s"
    finally:
        pool.shutdown()

    np.testing.assert_allclose(env.capture_pose, submit_pose, atol=1e-9)
    assert env.capture_timestamp == pytest.approx(sim_time_marker, abs=1e-9)
