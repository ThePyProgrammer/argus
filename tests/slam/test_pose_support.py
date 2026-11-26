"""Registration acceptance must not authorize an unsupported pose/map chain."""
import json

import numpy as np
import pytest

from src.slam.pose_support import PoseChainSupport, navigation_support_error


def test_rejected_frame_can_recover_but_accepted_rank_loss_cannot():
    support = PoseChainSupport()
    support.update(0., accepted=True, rank=0, seeded=True)
    assert navigation_support_error(support.snapshot(), 0., .2) is None
    support.update(.1, accepted=False, rank=0)
    assert not support.supported
    support.update(.2, accepted=True, rank=6)
    assert support.supported
    support.update(.3, accepted=True, rank=5)
    assert navigation_support_error(support.snapshot(), .3, .2) == 'pose_history_unobservable'
    for time, accepted, rank in [(.4, True, 6), (.5, False, 0), (.6, True, 0)]:
        support.update(time, accepted=accepted, rank=rank, seeded=rank == 0)
        assert not support.supported
        assert support.first_loss_s == .3
    evidence = support.snapshot()
    assert evidence['translation_bound_m'] is None
    assert evidence['attitude_bound_rad'] is None
    assert evidence['historical_map_bound_m'] is None
    json.dumps(evidence, allow_nan=False)


@pytest.mark.parametrize('timestamp', [float('nan'), float('inf'), None, True, 0.])
def test_malformed_time_cannot_hide_accepted_rank_loss(timestamp):
    support = PoseChainSupport()
    support.update(0., accepted=True, rank=0, seeded=True)
    support.update(timestamp, accepted=True, rank=3)
    assert navigation_support_error(support.snapshot(), 1., .2) == 'pose_history_unobservable'
    support.update(1., accepted=True, rank=6)
    assert not support.supported
    json.dumps(support.snapshot(), allow_nan=False)


@pytest.mark.parametrize('change,now,reason', [
    ({'version': 'future'}, 1., 'pose_support_unavailable'),
    ({'observed_at_s': None}, 1., 'pose_support_invalid'),
    ({'observed_at_s': True}, 1., 'pose_support_invalid'),
    ({}, 1.21, 'pose_support_stale'),
    ({}, .9, 'pose_support_stale'),
    ({'state': 'unavailable'}, 1., 'pose_support_unavailable'),
    ({'state': 'invalid'}, 1., 'pose_support_invalid'),
    ({'observable_rank': 5}, 1., 'pose_support_invalid'),
    ({'map_insertion_allowed': False}, 1., 'pose_support_invalid'),
    ({'first_loss_s': .1}, 1., 'pose_support_invalid'),
])
def test_consumer_rejects_missing_stale_and_inconsistent_evidence(change, now, reason):
    support = PoseChainSupport()
    support.update(1., accepted=True, rank=6)
    assert navigation_support_error({**support.snapshot(), **change}, now, .2) == reason
    assert navigation_support_error(None, now, .2) == 'pose_support_unavailable'


def test_accepted_inaccurate_plane_motion_stops_map_insertion(monkeypatch):
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    from src.slam.backends.icp_backend import ICPBackend
    from src.slam.protocol import TrackingStatus
    from src.slam.surface_odometry import SurfaceAlignment

    intrinsics = CameraIntrinsics.from_fov(96, 72)
    backend = ICPBackend(intrinsics, cloud_config_key='1')
    rgb = np.zeros((72, 96, 3), dtype=np.uint8)
    depth = np.ones((72, 96), dtype=np.float32)
    backend.process_frame(SensorFrame(rgb, depth, np.eye(4), 0.))
    original = backend.get_global_cloud()[0].copy()
    # Sliding parallel to an infinite wall leaves depth identical. A high-fit,
    # zero-residual accepted alignment therefore misses this true translation.
    truth = np.eye(4)
    truth[0, 3] = .2
    result = backend.process_frame(SensorFrame(rgb, depth, truth, .1))
    assert result.tracking_status == TrackingStatus.OK
    assert result.metrics['accepted']
    assert result.metrics['observable_rank'] == 3
    assert result.metrics['fitness'] > .99
    assert abs(result.pose[0, 3] - truth[0, 3]) > .19
    assert result.metrics['pose_map_support']['state'] == 'unobservable_motion'
    assert len(result.points) == 0
    np.testing.assert_array_equal(backend.get_global_cloud()[0], original)
    # A subsequently well-conditioned relative increment cannot repair the
    # already missing translation, including across periodic map downsampling.
    monkeypatch.setattr('src.slam.slam_pipeline.align_surfaces', lambda *a, **k:
        SurfaceAlignment(np.eye(4), 1., 0., 6, 500))
    for step in range(2, 32):
        result = backend.process_frame(SensorFrame(rgb, depth, truth, step * .1))
        assert result.tracking_status == TrackingStatus.OK
        assert not len(result.points)
        assert result.metrics['pose_map_support']['state'] == 'unobservable_history'
    np.testing.assert_array_equal(backend.get_global_cloud()[0], original)
    backend.reset()
    seeded = backend.process_frame(SensorFrame(rgb, depth, np.eye(4), 0.))
    assert len(seeded.points) > 0
    assert seeded.metrics['pose_map_support']['state'] == 'seeded'
