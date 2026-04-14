"""SC#1 MuJoCo GT integration test — rotated chair yaw + center error gates.

Loads tests/perception/fixtures/scene_rotated_chair.xml, renders one RGBD
frame, runs the full YOLOv11 -> PointClusterLifter pipeline, and asserts
the OBB is within +/-15 degrees yaw and 0.15m center of the MuJoCo
body('chair') ground truth.

Skips cleanly when the perception extra is not installed -- CI on a bare
Python env sees a row of 'skipped' rather than a false-fail (Assumptions
A4 mitigation, threat T-04-29).

Per Plan 04-07 acceptance criteria:
- ``test_rotated_chair_yaw_and_center_within_tolerance`` -- SC#1 +/-15 / 0.15m gate.
- ``test_obb_to_wire_from_wire_roundtrip`` -- Phase 2 D-04 round-trip regression guard.
- ``test_fallback_does_not_fire_on_dense_chair_frustum`` -- positive PointCluster path
  assertion (returned OBB has NON-identity quaternion -> Open3D PCA OBB ran, not
  the MedianDepthLifter fallback).

Quaternion convention conversion (Pitfall 7): MuJoCo ``data.body('chair').xquat``
is WXYZ; ``OrientedBox3D.quaternion`` is XYZW. The yaw-error helper extracts the
Z-axis Euler angle from each quaternion in its own native ordering and normalizes
the difference to ``[-pi, pi]`` before comparing against the +/-15 degree gate.
"""
from __future__ import annotations

import math

import numpy as np
import pytest


def _build_pose_from_mujoco_camera(data, model, camera_name: str) -> np.ndarray:
    """Return a 4x4 camera-to-world pose from ``data.cam_xpos`` + ``cam_xmat``."""
    import mujoco
    cam_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, camera_name)
    if cam_id < 0:
        raise RuntimeError(f"camera {camera_name!r} not found in model")
    pose = np.eye(4)
    pose[:3, :3] = data.cam_xmat[cam_id].reshape(3, 3)
    pose[:3, 3] = data.cam_xpos[cam_id]
    return pose


@pytest.fixture
def mujoco_scene():
    """Load the rotated-chair fixture; skip cleanly when MuJoCo is not installed."""
    pytest.importorskip("mujoco")
    import mujoco
    model = mujoco.MjModel.from_xml_path(
        "tests/perception/fixtures/scene_rotated_chair.xml"
    )
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


@pytest.fixture
def sensor_frame_from_scene(mujoco_scene):
    """Render one RGBD frame from the fixture via MuJoCo Renderer."""
    pytest.importorskip("mujoco")
    import mujoco
    from src.bridge.sensor_types import SensorFrame

    model, data = mujoco_scene
    renderer = mujoco.Renderer(model, height=480, width=640)
    renderer.update_scene(data, camera="robot_cam")
    rgb = renderer.render()                          # (H, W, 3) uint8
    renderer.enable_depth_rendering()
    renderer.update_scene(data, camera="robot_cam")
    depth = renderer.render().astype(np.float32)     # (H, W) float32 meters
    renderer.disable_depth_rendering()
    frame = SensorFrame(
        rgb=rgb,
        depth=depth,
        ground_truth_pose=_build_pose_from_mujoco_camera(data, model, "robot_cam"),
        sim_time=0.0,
    )
    return frame


def _pipeline_detect_and_lift(frame, pose):
    """Run YOLOv11 + PointClusterLifter end-to-end; return Detections3D.

    Skips with an informative message (per Assumptions A4) when YOLO does not
    detect a chair at >= 0.25 confidence on the compound-primitive fixture.
    """
    pytest.importorskip("ultralytics")
    pytest.importorskip("open3d")
    pytest.importorskip("sklearn.cluster")
    import src.perception.backends  # noqa: F401  (registers yolov11)
    import src.perception.lifters  # noqa: F401  (registers point_cluster)
    from src.bridge.sensor_types import CameraIntrinsics
    from src.perception.registry import Detection3DRegistry, DetectorRegistry
    from src.perception.types import Detections2D

    detector = DetectorRegistry.create("yolov11")
    detector.warmup(frame)
    dets_2d = detector.process_frame(frame)

    chair_items = [
        d for d in dets_2d.items
        if "chair" in d.class_name.lower() and d.score >= 0.25
    ]
    if not chair_items:
        pytest.skip(
            "YOLOv11 did not detect 'chair' at conf>=0.25 on the compound-primitive "
            "fixture. Mitigation: switch fixture to a mesh chair or relax the "
            "detection confidence threshold (04-RESEARCH Assumptions A4 / "
            "threat T-04-30)."
        )

    chair_dets_2d = Detections2D(
        items=chair_items,
        inference_ms=dets_2d.inference_ms,
        image_hw=dets_2d.image_hw,
    )

    lifter = Detection3DRegistry.create("point_cluster")
    intrinsics = CameraIntrinsics.from_fov(640, 480, 70.0)
    dets_3d = lifter.lift(chair_dets_2d, frame, pose, intrinsics, None)
    return dets_3d


def test_rotated_chair_yaw_and_center_within_tolerance(
    mujoco_scene, sensor_frame_from_scene
):
    """SC#1 gate: yaw error < +/-15 degrees AND center error < 0.15m vs MuJoCo GT."""
    from scipy.spatial.transform import Rotation
    model, data = mujoco_scene
    frame = sensor_frame_from_scene

    dets_3d = _pipeline_detect_and_lift(frame, frame.ground_truth_pose)
    assert len(dets_3d.items) >= 1, (
        "expected at least one OBB item after lifter.lift on the rotated-chair fixture"
    )

    chair_xpos = np.asarray(data.body("chair").xpos)
    chair_xquat = np.asarray(data.body("chair").xquat)  # MuJoCo wxyz
    w, x, y, z = chair_xquat
    gt_quat_xyzw = np.array([x, y, z, w])               # convert to scipy xyzw
    yaw_gt = Rotation.from_quat(gt_quat_xyzw).as_euler("zyx")[0]

    # Pick the OBB closest to the GT body position (tolerates spurious side detections)
    best = min(
        dets_3d.items,
        key=lambda it: float(np.linalg.norm(np.asarray(it.center) - chair_xpos)),
    )
    center_err = float(np.linalg.norm(np.asarray(best.center) - chair_xpos))
    yaw_pred = Rotation.from_quat(np.asarray(best.quaternion)).as_euler("zyx")[0]
    # Normalize signed yaw difference to [-pi, pi] before taking abs.
    yaw_err_rad = abs(((yaw_pred - yaw_gt) + np.pi) % (2 * np.pi) - np.pi)
    yaw_err_deg = math.degrees(yaw_err_rad)

    assert center_err < 0.15, (
        f"SC#1 center-error gate failed: {center_err:.3f}m (expected < 0.15m). "
        f"pred_center={best.center}, gt_xpos={chair_xpos}"
    )
    assert yaw_err_deg < 15.0, (
        f"SC#1 yaw-error gate failed: {yaw_err_deg:.2f} deg (expected < 15 deg). "
        f"pred_yaw_rad={yaw_pred:.4f}, gt_yaw_rad={yaw_gt:.4f}"
    )

    # D-08 envelope-level capability check.
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    info = {l["name"]: l for l in Detection3DRegistry.list_backends()}["point_cluster"]
    assert info["capabilities"]["outputs_oriented"] is True


def test_obb_to_wire_from_wire_roundtrip(mujoco_scene, sensor_frame_from_scene):
    """Phase 2 D-04 regression guard -- round-trip each Phase-4 OBB."""
    from src.perception.types import OrientedBox3D
    dets_3d = _pipeline_detect_and_lift(
        sensor_frame_from_scene, sensor_frame_from_scene.ground_truth_pose,
    )
    for obb in dets_3d.items:
        wire = obb.to_wire()
        recovered = OrientedBox3D.from_wire(wire)
        np.testing.assert_allclose(obb.center, recovered.center, atol=1e-6)
        np.testing.assert_allclose(obb.half_extents, recovered.half_extents, atol=1e-6)
        # to_wire() auto-flips qw<0 (Phase 1 D-10). Compare against the signed wire form.
        expected_quat = (
            obb.quaternion if obb.quaternion[-1] >= 0 else -obb.quaternion
        )
        np.testing.assert_allclose(recovered.quaternion, expected_quat, atol=1e-6)


def test_fallback_does_not_fire_on_dense_chair_frustum(
    mujoco_scene, sensor_frame_from_scene
):
    """Positive PointCluster path: returned OBB has NON-identity quaternion
    (proves the Open3D PCA-OBB ran, not the MedianDepthLifter fallback)."""
    dets_3d = _pipeline_detect_and_lift(
        sensor_frame_from_scene, sensor_frame_from_scene.ground_truth_pose,
    )
    assert len(dets_3d.items) >= 1
    identity = np.array([0.0, 0.0, 0.0, 1.0])
    any_non_identity = any(
        not np.allclose(np.asarray(it.quaternion), identity, atol=1e-9)
        for it in dets_3d.items
    )
    assert any_non_identity, (
        "every returned OBB had identity quaternion -- the MedianDepthLifter "
        "fallback path triggered when it shouldn't on a dense chair frustum"
    )
