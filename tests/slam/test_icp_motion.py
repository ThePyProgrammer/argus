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
def test_tracks_room_motion_without_live_ground_truth(motion):
    intrinsics = CameraIntrinsics.from_fov(96, 72)
    pipeline = SLAMPipeline(intrinsics, cloud_config_key="1")
    errors = []
    angles = []
    for step in range(41):
        fraction = step / 40
        pose = np.eye(4)
        if motion in {"translation", "combined"}:
            pose[:3, 3] = fraction * np.array([.20, .10, -.10])
        if motion in {"rotation", "combined"}:
            pose[:3, :3] = Rotation.from_rotvec(fraction * np.array([.06, -.08, .04])).as_matrix()
        # Only the first frame supplies the true initial pose. Later truth is
        # deliberately wrong so a simulator-pose fallback cannot pass.
        seed = np.eye(4)
        if step:
            seed[:3, 3] = [20., -30., 40.]
        estimate = pipeline.process_frame(room_frame(pose, intrinsics, step * .01, seed))
        errors.append(np.linalg.norm(estimate[:3, 3] - pose[:3, 3]))
        angles.append(Rotation.from_matrix(estimate[:3, :3].T @ pose[:3, :3]).magnitude())
    assert max(errors) < .02
    assert max(angles) < np.deg2rad(1.)


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
