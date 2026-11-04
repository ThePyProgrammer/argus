"""Observed floor evidence survives camera bobbing without erasing raised objects."""

import numpy as np

from src.exploration.floor_filter import FloorFilter, FloorTracker
from src.slam.octomap_builder import OctoMapBuilder


def floor_patch():
    x, y = np.meshgrid(np.linspace(-1, 1, 24), np.linspace(-1, 1, 24))
    return np.c_[x.ravel(), y.ravel(), np.zeros(x.size)]


def test_established_floor_survives_gait_height_changes_and_narrow_support():
    tracker = FloorTracker()
    broad = floor_patch()
    assert tracker.mask(broad, np.array([0, 0, .32])).all()
    strip = np.c_[np.linspace(.2, 1, 50), np.zeros(50), np.zeros(50)]
    obstacle = strip + [0, 0, .06]
    for height in (.277, .26, .32, .38):
        points = np.vstack((strip, obstacle))
        before = points.copy()
        mask = tracker.mask(points, np.array([0, 0, height]))
        assert mask[:50].all() and not mask[50:].any()
        np.testing.assert_array_equal(points, before)


def test_sparse_or_raised_initial_view_cannot_establish_a_floor():
    tracker = FloorTracker()
    broad = floor_patch()
    for points in (broad[:10], broad + [0, 0, .06]):
        assert not tracker.mask(points, np.array([0, 0, .32])).any()
        assert tracker.plane is None
    assert tracker.mask(broad, np.array([0, 0, .32])).all()


def test_dominant_raised_plane_cannot_replace_tracked_floor():
    tracker = FloorTracker()
    broad = floor_patch()
    tracker.mask(broad, np.array([0, 0, .32]))
    for _ in range(5):
        mask = tracker.mask(np.vstack((broad[:8], broad + [0, 0, .06])), np.array([0, 0, .28]))
        assert mask[:8].all() and not mask[8:].any()
    assert tracker.plane[1] == 0


def test_floor_history_is_per_robot_and_has_no_global_height_oracle():
    first, second = FloorTracker(), FloorTracker()
    shifted = floor_patch() + [3, -2, .17]
    assert first.mask(shifted, np.array([3, -2, .49])).all()
    assert first.mask(shifted[:10], np.array([3, -2, .43])).all()
    assert not second.mask(shifted[:10], np.array([3, -2, .43])).any()
    normal, _ = first.plane
    normal[:] = 0
    assert np.linalg.norm(first.plane[0]) == 1  # Detached calibration result.


def test_late_floor_acquisition_removes_raw_floor_but_preserves_shared_voxel_obstacle():
    builder = OctoMapBuilder(.1)
    points = np.array([[.01, .01, 0], [.01, .01, .06]])
    builder.insert_scan(points, np.array([0, 0, .32]))
    builder.get_occupied_voxels()  # Prime the cache before reclassification.
    assert builder.remove_plane_inliers(np.array([0., 0., 1.]), 0., .015) == 1
    reference = OctoMapBuilder(.1)
    reference.insert_scan(points[1:], np.array([0, 0, .32]))
    np.testing.assert_array_equal(builder.get_occupied_voxels(), reference.get_occupied_voxels())
    assert builder.num_occupied == 1


def test_stateless_detector_still_rejects_unverified_low_camera_view():
    # History solves this ambiguity; the bootstrap calibration is not widened.
    assert not FloorFilter().mask(floor_patch(), np.array([0, 0, .26])).any()


def test_fresh_broad_floor_recovers_from_attitude_drift_without_erasing_raised_plane():
    tracker = FloorTracker()
    tracker.mask(floor_patch(), np.array([0, 0, .32]))
    shifted = floor_patch() + [2, 0, 0]
    shifted[:, 2] = -np.tan(np.deg2rad(2)) * shifted[:, 0]
    # Adjacent surfaces, each with locally planar depth support.
    raised = shifted + [0, 3, .06]
    mask = tracker.mask(np.vstack((shifted, raised)), np.array([0, 0, .32]))
    assert mask[:len(shifted)].all()
    assert not mask[len(shifted):].any()
    assert tracker.reacquired
    tracker.mask(shifted[:10], np.array([0, 0, .26]))
    assert not tracker.reacquired  # One observation's event, not persistent state.


def test_camera_height_change_cannot_promote_a_competing_raised_plane():
    tracker = FloorTracker()
    floor = floor_patch()
    tracker.mask(floor, np.array([0, 0, .32]))
    raised = floor + [0, 0, .06]
    # Height calibration alone would accept this plane during a high stance.
    assert FloorFilter().mask(raised, np.array([0, 0, .38])).all()
    for _ in range(3):
        assert not tracker.mask(raised, np.array([0, 0, .38])).any()
        assert not tracker.reacquired
    assert tracker.plane[1] == 0


def test_gait_dip_cannot_replace_strong_floor_with_a_weaker_tilted_obstacle():
    tracker = FloorTracker()
    floor = floor_patch()
    tracker.mask(floor, np.array([0, 0, .32]))
    x, y = np.meshgrid(np.linspace(2, 4, 12), np.linspace(-1, 1, 12))
    obstacle = np.c_[x.ravel(), y.ravel(), -.01 + np.tan(np.deg2rad(2)) * x.ravel()]
    points = np.vstack((floor, obstacle, [[np.nan, 0, 0]]))
    origin = np.array([0, 0, .279])
    # The actual floor is just outside bootstrap calibration. A tilted raised
    # surface intersects its band at the camera and becomes a false proposal.
    fresh = FloorFilter().mask(points, origin)
    assert not fresh[:len(floor)].all()
    assert fresh[len(floor):-1].any()
    for _ in range(3):
        mask = tracker.mask(points, origin)
        assert mask[:len(floor)].all()
        assert not mask[len(floor):].any()
        assert not tracker.reacquired


def test_rendered_initial_plane_does_not_tilt_into_distant_low_obstacles():
    from src.exploration.evaluation.episode import ExplorationEpisode
    from src.slam.slam_pipeline import SLAMPipeline

    with ExplorationEpisode.from_scenario("connected_rooms", 101, horizon_s=.1) as episode:
        frame = episode.bridge.get_frame("robot_a")
        pipeline = SLAMPipeline(episode.bridge.camera_intrinsics("robot_a"), cloud_config_key="1")
        pipeline.process_frame(frame)
        tracker = FloorTracker()
        tracker.mask(pipeline.last_frame_cloud, frame.ground_truth_pose[:3, 3])
        assert tracker.plane is not None
        # Test extrapolation without fitting another plane. A biased initial
        # calibration used to classify points at a distant wall base as floor.
        floor = np.c_[np.full(20, 6.), np.linspace(-1, 1, 20), np.zeros(20)]
        raised = floor + [0, 0, .05]
        mask = tracker.mask(np.vstack((floor, raised)), np.array([5, 0, .27]))
        assert mask[:20].all()
        assert not mask[20:].any()
