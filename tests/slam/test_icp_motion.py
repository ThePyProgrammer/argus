"""Known camera motion against independently ray-cast room surfaces."""

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.slam_pipeline import SLAMPipeline


def room_frame(pose, intrinsics, time, seed_pose):
    """Analytical exit distances from an enclosing box, in camera-axis metres."""
    v, u = np.indices((intrinsics.height, intrinsics.width))
    directions = np.stack(((u - intrinsics.cx) / intrinsics.fx,
                           -(v - intrinsics.cy) / intrinsics.fy, -np.ones_like(u)), axis=-1)
    rays = directions @ pose[:3, :3].T
    origin = pose[:3, 3]
    lower, upper = np.array([-1.5, -1., -4.]), np.array([2., 1., 1.])
    with np.errstate(divide="ignore", invalid="ignore"):
        distances = (np.where(rays > 0, upper, lower) - origin) / rays
    depth = np.min(np.where(distances > 0, distances, np.inf), axis=-1).astype(np.float32)
    return SensorFrame(np.zeros((*depth.shape, 3), dtype=np.uint8), depth, seed_pose, time)


@pytest.mark.parametrize("motion", ["stationary", "translation", "rotation", "combined"])
@pytest.mark.parametrize("mounted", [False, True])
def test_tracks_room_motion_without_live_ground_truth(motion, mounted):
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    errors = []
    angles = []
    mount = np.eye(4)
    if mounted:
        mount[:3, :3] = Rotation.from_rotvec([0., 0., .2]).as_matrix()
        mount[:3, 3] = [.4, 0., .05]
    for step in range(41):
        fraction = step / 40
        pose = np.eye(4)
        if motion in {"translation", "combined"}:
            pose[:3, 3] = fraction * np.array([.20, .10, -.10])
        if motion in {"rotation", "combined"}:
            pose[:3, :3] = Rotation.from_rotvec(fraction * np.array([.06, -.08, .04])).as_matrix()
        # Only the first frame supplies the true initial pose. Later truth is
        # deliberately wrong so a simulator-pose fallback cannot pass.
        camera_pose = pose @ mount
        seed = camera_pose.copy()
        if step:
            seed[:3, 3] = [20., -30., 40.]
        frame = room_frame(camera_pose, intrinsics, step * .01, seed)
        frame.body_from_camera = mount if mounted else None
        estimate = frame.body_pose_from_camera(pipeline.process_frame(frame))
        errors.append(np.linalg.norm(estimate[:3, 3] - pose[:3, 3]))
        angles.append(Rotation.from_matrix(estimate[:3, :3].T @ pose[:3, :3]).magnitude())
    assert max(errors) < .02
    assert max(angles) < np.deg2rad(1.)


@pytest.mark.parametrize("turn", [-.3, .3])
@pytest.mark.parametrize("offset", [[.4, 0., .05], [-.3, .1, .1]])
def test_offset_camera_turn_does_not_translate_stationary_body(turn, offset):
    """A calibrated camera moves on an arc when the robot turns in place."""
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    mount = np.eye(4)
    # MuJoCo camera axes: right, up, backward. Robot forward is body X.
    mount[:3, :3] = [[0., 0., -1.], [-1., 0., 0.], [0., 1., 0.]]
    mount[:3, 3] = offset
    v, u = np.indices((intrinsics.height, intrinsics.width))
    rays = np.stack(((u - intrinsics.cx) / intrinsics.fx,
                     -(v - intrinsics.cy) / intrinsics.fy, -np.ones_like(u)), axis=-1)
    errors = []
    for step in range(41):
        body = np.eye(4)
        body[2, 3] = .3
        body[:3, :3] = Rotation.from_rotvec([0., 0., turn * step / 40]).as_matrix()
        camera = body @ mount
        world_rays = rays @ camera[:3, :3].T
        # Independent rendering of an infinite wall at world X=2.
        depth = ((2. - camera[0, 3]) / world_rays[..., 0]).astype(np.float32)
        seed = camera.copy()
        if step:
            seed = np.eye(4)
            seed[:3, 3] = 100.
        frame = SensorFrame(np.zeros((*depth.shape, 3), dtype=np.uint8), depth,
                            seed, step * .01, body_from_camera=mount)
        estimate = frame.body_pose_from_camera(pipeline.process_frame(frame))
        assert pipeline.tracking_ok
        errors.append(np.linalg.norm(estimate[:3, 3] - body[:3, 3]))
        angle = Rotation.from_matrix(estimate[:3, :3].T @ body[:3, :3]).magnitude()
        assert angle < np.deg2rad(1.)
    assert max(errors) < .01


def test_pinned_axes_ignore_dashboard_configuration(monkeypatch):
    import src.slam.depth_to_cloud as projection
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    frame = room_frame(np.eye(4), intrinsics, 0., np.eye(4))
    monkeypatch.setattr(projection, "get_active_config", lambda: "4")
    pipeline.process_frame(frame)
    pose = pipeline.process_frame(frame)
    assert pipeline.tracking_ok
    np.testing.assert_allclose(pose, np.eye(4), atol=1e-8)


@pytest.mark.parametrize("missing", [None, "zero", "far"])
def test_rejected_frame_keeps_reference_and_does_not_insert_unlocalized_points(missing):
    from src.slam.backends.icp_backend import ICPBackend
    from src.slam.protocol import TrackingStatus
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    backend = ICPBackend(intrinsics, cloud_config_key="1")
    frame = room_frame(np.eye(4), intrinsics, 0., np.eye(4))
    backend.process_frame(frame)
    original_map = backend.get_global_cloud()[0].copy()
    invalid_depth = None if missing is None else np.full(frame.depth.shape, 0. if missing == "zero" else 9., dtype=np.float32)
    poisoned_pose = np.eye(4)
    poisoned_pose[:3, 3] = 100.
    rejected = backend.process_frame(SensorFrame(frame.rgb, invalid_depth, poisoned_pose, .01))
    assert rejected.tracking_status == TrackingStatus.LOST
    assert not rejected.metrics["accepted"]
    assert rejected.metrics["fitness"] == 0.
    assert len(rejected.points) == 0
    np.testing.assert_array_equal(rejected.pose, np.eye(4))
    np.testing.assert_array_equal(backend.get_global_cloud()[0], original_map)

    recovered = backend.process_frame(frame)
    assert recovered.tracking_status == TrackingStatus.OK
    assert recovered.metrics["observable_rank"] == 6
    np.testing.assert_allclose(recovered.pose, np.eye(4), atol=1e-8)
    # Diagnostics are consumed by JSON exporters and the dashboard.
    import json
    json.dumps(recovered.metrics, allow_nan=False)


@pytest.mark.parametrize("distance", [.15, .08, .04])
def test_near_wall_keeps_dense_depth_support_for_tracking(distance):
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    rgb = np.zeros((72, 96, 3), dtype=np.uint8)
    for step in range(11):
        # Move towards a wall by 1 mm per frame. Its depth image remains dense
        # even when a fixed 3 cm voxel grid retains fewer than 100 points.
        depth = np.full((72, 96), distance - step * .001, dtype=np.float32)
        seed = np.eye(4)
        if step:
            seed[:3, 3] = 100.
        estimate = pipeline.process_frame(SensorFrame(rgb, depth, seed, step * .01))
        assert pipeline.tracking_ok
        np.testing.assert_allclose(estimate[:3, 3], [0., 0., -step * .001], atol=.001)
        if step:
            assert pipeline.registration_metrics["correspondences"] >= 100
            assert pipeline.registration_metrics["rejection_reason"] is None
            assert .03 / 8 <= pipeline.registration_metrics["registration_voxel_m"] < .03
            # Extra registration detail must not densify the navigation map.
            assert len(pipeline.last_frame_cloud) < 100


@pytest.mark.parametrize("shape", ["sparse", "line"])
def test_near_wall_refinement_cannot_manufacture_tracking_support(shape):
    intrinsics = CameraIntrinsics.from_fov(320, 240)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    rgb = np.zeros((240, 320, 3), dtype=np.uint8)
    pipeline.process_frame(SensorFrame(rgb, np.full((240, 320), .15, dtype=np.float32), np.eye(4), 0.))
    original_map = pipeline.get_cloud_points().copy()
    depth = np.zeros((240, 320), dtype=np.float32)
    if shape == "sparse":
        depth[116:124, 156:164] = .15
    else:
        depth[:, 160] = .15  # Many pixels, but only a line in 3D.
    poisoned = np.eye(4)
    poisoned[:3, 3] = 100.
    estimate = pipeline.process_frame(SensorFrame(rgb, depth, poisoned, .01))
    assert not pipeline.tracking_ok
    assert pipeline.registration_metrics["correspondences"] < 100
    assert pipeline.registration_metrics["rejection_reason"] == "insufficient_correspondences"
    assert len(pipeline.last_frame_cloud) == 0
    np.testing.assert_array_equal(estimate, np.eye(4))
    np.testing.assert_array_equal(pipeline.get_cloud_points(), original_map)
