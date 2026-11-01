"""Analytical timelines and real rendered visibility, without planner inputs."""

from dataclasses import replace
import json

import mujoco
import numpy as np
import pytest

from src.bridge.depth import clean_metric_depth
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.metrics.exploration_coverage import (
    CameraCalibration, CoverageCollector, CoverageConfig, DepthObservation, visible_reference_cells,
)
from src.metrics.exploration_reference import ReferenceConfig, build_reference_grid


def scene(extra="", *, camera_pos="0 0 3", camera_angles="0 0 0"):
    return mujoco.MjModel.from_xml_string(
        '<mujoco><compiler angle="degree"/><worldbody>'
        '<geom name="floor" type="plane" size="5 5 .1"/>'
        f'<camera name="camera" pos="{camera_pos}" euler="{camera_angles}" fovy="70"/>'
        f'{extra}</worldbody></mujoco>'
    )


@pytest.fixture
def reference():
    return build_reference_grid(scene(), ReferenceConfig(
        (-1, -1, 1, 1), (0, 0), resolution_m=.25, clearance_half_extent_m=.01))


def observation(time=0, *, depth=3., x=0., z=3., angle=0.):
    pose = np.eye(4)
    pose[:3, 3] = [x, 0, z]
    a = np.deg2rad(angle)
    pose[:3, :3] = [[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]]
    intrinsics = CameraIntrinsics.from_fov(64, 48)
    cal = CameraCalibration(**vars(intrinsics))
    image = None if depth is None else np.full((48, 64), depth, dtype=np.float32)
    return DepthObservation(time, pose, image, cal)


def rendered(model, time=0):
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, height=48, width=64) as renderer:
        renderer.update_scene(data, camera="camera")
        renderer.enable_depth_rendering()
        raw = renderer.render().copy()
    pose = np.eye(4)
    pose[:3, :3], pose[:3, 3] = data.cam_xmat[0].reshape(3, 3), data.cam_xpos[0]
    depth = clean_metric_depth(raw, model.vis.map.zfar * model.stat.extent)
    return DepthObservation(time, pose, depth, CameraCalibration(**vars(CameraIntrinsics.from_fov(64, 48))))


def test_rendered_floor_fully_visible(reference):
    assert np.array_equal(visible_reference_cells(reference, rendered(scene())), reference.mask)


def test_rendered_sub_meter_scene():
    model = scene(camera_pos="0 0 .5")
    ref = build_reference_grid(model, ReferenceConfig((-.2, -.2, .2, .2), (0, 0),
                               resolution_m=.05, clearance_half_extent_m=.01))
    obs = rendered(model)
    assert obs.depth.max() == pytest.approx(.5)
    assert np.array_equal(visible_reference_cells(ref, obs), ref.mask)


@pytest.mark.parametrize("occluder", [
    '<geom name="shelf" type="box" size=".25 .25 .1" pos="0 0 1.5"/>',
    '<body name="other_robot" pos="0 0 1.5"><freejoint/>'
    '<geom type="box" size=".25 .25 .1"/></body>',
])
def test_rendered_occluders_hide_reachable_floor(reference, occluder):
    # R is fixed before robot insertion. The visibility collector sees only depth.
    visible = visible_reference_cells(reference, rendered(scene(occluder)))
    assert visible.sum() > 0
    assert not visible[3:5, 3:5].any()
    assert visible.sum() < reference.mask.sum()


def test_oblique_render_matches_floor_despite_pixel_depth_gradient(reference):
    obs = rendered(scene(camera_pos="0 -1.5 3", camera_angles="25 0 0"))
    visible = visible_reference_cells(reference, obs)
    assert visible.sum() == reference.mask.sum()
    # Axial depth varies over the image; using Euclidean ray length is incorrect.
    assert obs.depth.max() - obs.depth.min() > 1
    cal = obs.calibration
    rows, cols = np.indices(obs.depth.shape)
    factor = np.sqrt(1 + ((cols + .5 - cal.cx) / cal.fx)**2 + ((rows + .5 - cal.cy) / cal.fy)**2)
    wrong = replace(obs, depth=obs.depth * factor)
    assert visible_reference_cells(reference, wrong).sum() < visible.sum() / 4


def test_rendered_wall_hides_floor_behind_it():
    wall = '<geom name="wall" type="box" size=".35 .05 .5" pos="0 0 .5"/>'
    model = scene(wall, camera_pos="0 -2 2", camera_angles="45 0 0")
    ref = build_reference_grid(model, ReferenceConfig((-1, -1, 1, 1), (0, -.8),
                               resolution_m=.25, clearance_half_extent_m=.01))
    clear = visible_reference_cells(ref, rendered(scene(camera_pos="0 -2 2", camera_angles="45 0 0")))
    blocked = visible_reference_cells(ref, rendered(model))
    assert clear[5:7, 3:5].all()
    assert not blocked[5:7, 3:5].any()
    assert blocked[:2].any()


@pytest.mark.parametrize("depth", [None, 0., -1., np.nan, np.inf, 21., 2.5, 3.5])
def test_missing_invalid_out_of_range_or_nonfloor_depth_adds_nothing(reference, depth):
    assert not visible_reference_cells(reference, observation(depth=depth)).any()


def test_out_of_view_behind_camera_and_range(reference):
    for obs in (observation(x=100), observation(angle=180), observation(z=-3)):
        assert not visible_reference_cells(reference, obs).any()
    assert not visible_reference_cells(reference, observation(), CoverageConfig(max_depth_m=2)).any()


def test_pixel_support_is_conservative_at_depth_edges(reference):
    obs = observation()
    depth = obs.depth.copy()
    # Center cell (x=.125, y=.125) projects to (33.43,22.57), using columns 32/33 and rows 22/23.
    depth[22, 32] = 1
    visible = visible_reference_cells(reference, replace(obs, depth=depth))
    assert not visible[4, 4]
    assert visible.sum() > 0


def test_capture_snapshots_survive_frame_reuse(reference):
    pose = observation().world_from_camera.copy()
    depth = np.full((48, 64), 3., dtype=np.float32)
    intrinsics = CameraIntrinsics.from_fov(64, 48)
    frame = SensorFrame(np.zeros((48, 64, 3), np.uint8), depth, pose, 12.)
    captured = DepthObservation.from_frame(frame, intrinsics)
    frame.ground_truth_pose[:] = 0
    frame.depth[:] = 0
    intrinsics.fx = 1
    assert visible_reference_cells(reference, captured).sum() == reference.mask.sum()
    assert captured.sim_time == 12
    with pytest.raises(ValueError):
        captured.depth.setflags(write=True)
    with pytest.raises(ValueError):
        captured.world_from_camera.setflags(write=True)


@pytest.mark.parametrize("field,value", [
    ("depth", np.zeros((48, 64), np.uint8)), ("depth", np.zeros((48, 64, 3))),
    ("world_from_camera", np.zeros((4, 4))), ("world_from_camera", np.diag([-1., 1, 1, 1])),
    ("sim_time", np.nan),
])
def test_invalid_sensor_contract_is_rejected(field, value):
    with pytest.raises(ValueError):
        replace(observation(), **{field: value})


def collector(reference, **kwargs):
    return CoverageCollector(reference, ("a", "b"), start_sim_time=10,
                             config=CoverageConfig(horizon_s=10, **kwargs))


def test_fixed_horizon_integral_overlap_and_absorbing_failure(reference, tmp_path):
    metrics = collector(reference)
    first_view = observation(12, x=-2)
    mask = visible_reference_cells(reference, first_view)
    assert 0 < mask.sum() < reference.mask.sum()
    step = metrics.observe_batch(12, {"a": first_view})
    assert step["overlap"] == 0
    step = metrics.observe_batch(14, {"a": observation(14, x=-2), "b": observation(14)})
    assert step["coverage"] == 1
    assert step["overlap"] == pytest.approx(mask.sum() / reference.mask.sum())
    result = metrics.finalize("algorithm_error")
    fraction = mask.sum() / reference.mask.sum()
    assert result["normalized_auc"] == pytest.approx(fraction * .8 + (1 - fraction) * .6)
    assert result["time_to_threshold_s"] == 4
    assert result["capped_time_s"] == 4
    assert result["elapsed_s"] == 4
    assert result["threshold_success"]
    json.dumps(result, allow_nan=False)
    with pytest.raises(ValueError):
        metrics.observe_batch(15, {"a": observation(15)})
    with pytest.raises(ValueError):
        metrics.finalize("algorithm_error")
    path = tmp_path / "observations.npz"
    metrics.write_observations(path)
    with np.load(path, allow_pickle=False) as saved:
        first = saved["first_seen_s"][:, saved["reference_mask"]].min(axis=0)
        assert np.maximum(0, 10 - first).mean() / 10 == pytest.approx(result["normalized_auc"])
        assert list(saved["robot_ids"]) == ["a", "b"]


def test_stationary_repeat_and_team_union_do_not_inflate_coverage(reference):
    metrics = collector(reference)
    metrics.observe_batch(10, {"a": observation(10)})
    metrics.observe_batch(11, {"a": observation(11), "b": observation(11)})
    metrics.observe_batch(12, {"a": observation(12)})
    assert metrics.snapshot()["observed_cells"] == reference.mask.sum()
    assert metrics.snapshot()["overlap"] == 1
    result = metrics.finalize("no_frontiers")
    assert result["normalized_auc"] == 1
    assert result["time_to_threshold_s"] == 0


def test_empty_union_is_an_explicit_failure(reference):
    metrics = collector(reference)
    metrics.observe_batch(11, {"a": observation(11, depth=None)})
    metrics.advance(20)
    result = metrics.finalize("horizon")
    assert result["normalized_auc"] == result["overlap"] == result["coverage"] == 0
    assert result["zero_observation"]
    assert not result["threshold_success"]
    assert result["time_to_threshold_s"] is None
    assert result["capped_time_s"] == 10
    assert result["missing_depth_frames"] == {"a": 1, "b": 0}


def test_no_frontiers_does_not_imply_complete_coverage(reference):
    metrics = collector(reference)
    metrics.observe_batch(12, {"a": observation(12, x=-2)})
    result = metrics.finalize("no_frontiers")
    assert 0 < result["coverage"] < .9
    assert not result["threshold_success"]
    assert result["normalized_auc"] == pytest.approx(.8 * result["coverage"])


def test_horizon_observations_contribute_zero_auc(reference):
    metrics = collector(reference)
    with pytest.raises(ValueError):
        metrics.finalize("horizon")
    metrics.observe_batch(20, {"a": observation(20)})
    result = metrics.finalize("horizon")
    assert result["coverage"] == 1
    assert result["normalized_auc"] == 0
    assert result["time_to_threshold_s"] == 10


def test_horizon_tolerates_floating_point_tick_roundoff(reference):
    metrics = CoverageCollector(reference, ("a",), start_sim_time=0,
                                config=CoverageConfig(horizon_s=.35))
    timestamp = 35 * .01
    metrics.observe_batch(timestamp, {"a": observation(timestamp)})
    assert metrics.finalize("horizon")["elapsed_s"] == .35


def test_one_failed_robot_freezes_while_survivor_continues(reference):
    metrics = collector(reference)
    metrics.observe_batch(11, {"a": observation(11, x=-2)})
    metrics.stop_robot("a", 12)
    with pytest.raises(ValueError):
        metrics.observe_batch(13, {"a": observation(13)})
    metrics.observe_batch(14, {"b": observation(14)})
    assert metrics.snapshot()["coverage"] == 1
    assert metrics.finalize("all_robots_failed")["stopped_robots"] == {"a": 2}


@pytest.mark.parametrize("time,frames", [
    (9, {"a": observation(9)}), (21, {"a": observation(21)}),
    (12, {"a": observation(11)}), (12, {"a": observation(12), "unknown": observation(12)}),
])
def test_bad_batches_do_not_partially_mutate_metrics(reference, time, frames):
    metrics = collector(reference)
    before = metrics.snapshot()
    with pytest.raises(ValueError):
        metrics.observe_batch(time, frames)
    assert before == metrics.snapshot()


def test_duplicate_frames_rejected_and_output_arrays_are_detached(reference):
    metrics = collector(reference)
    metrics.observe_batch(12, {"a": observation(12)})
    before = metrics.snapshot()
    with pytest.raises(ValueError):
        metrics.observe_batch(12, {"b": observation(12), "a": observation(12)})
    assert metrics.snapshot() == before
    with pytest.raises(ValueError):
        metrics.first_observation_times().setflags(write=True)
    before["sensor_frames"]["a"] = 100
    assert metrics.snapshot()["sensor_frames"]["a"] == 1


@pytest.mark.parametrize("values", [
    {"horizon_s": 0}, {"threshold": 0}, {"threshold": 1.1}, {"min_depth_m": 21},
    {"depth_absolute_tolerance_m": -1}, {"horizon_s": np.inf}, {"threshold": True},
])
def test_invalid_coverage_config(values):
    with pytest.raises(ValueError):
        CoverageConfig(**values)
