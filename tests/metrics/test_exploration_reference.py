"""Reference extraction checks independent of the production SAT implementation."""

from dataclasses import replace
import json
import math
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from src.exploration.evaluation.scenarios import load_scenario, list_scenarios
from src.metrics.exploration_reference import ReferenceConfig, build_reference_grid


def _model(obstacles="", *, floor=None, transform="", prefix="", suffix=""):
    floor = floor if floor is not None else '<geom name="floor" type="box" size="4 4 .1" pos="0 0 -.1"/>'
    geometry = floor + obstacles
    if transform:
        geometry = f'<body {transform}>{geometry}</body>'
    return mujoco.MjModel.from_xml_string(
        f'<mujoco><compiler angle="radian"/>{prefix}<worldbody>{geometry}</worldbody>{suffix}</mujoco>'
    )


def _config(**kwargs):
    return ReferenceConfig(**{"bounds": (-3, -3, 3, 3), "component_anchor": (-2, -2),
                             "clearance_half_extent_m": .1, **kwargs})


@pytest.mark.parametrize("scenario_id", list_scenarios())
@pytest.mark.parametrize("resolution", [.1, .05])
def test_compiled_mask_matches_independent_analytical_fixtures(scenario_id, resolution):
    scenario = load_scenario(scenario_id)
    b = scenario.bounds
    config = ReferenceConfig((b.x_min, b.y_min, b.x_max, b.y_max),
                             scenario.component_anchor, resolution_m=resolution)
    reference = build_reference_grid(mujoco.MjModel.from_xml_string(scenario.mjcf_xml), config)
    assert np.array_equal(reference.mask, scenario.reference_mask(resolution))
    assert reference.metadata()["area_m2"] == pytest.approx(scenario.reference_metadata(resolution)["area_m2"])
    for x, y in scenario.spawn_pool:
        assert reference.check_spawn(x, y).accepted


def test_rotated_box_does_not_block_its_entire_world_aabb():
    model = _model('<geom name="wall" type="box" size=".9 .1 1" pos="0 0 1" euler="0 0 .7853981633974483"/>')
    reference = build_reference_grid(model, _config())
    assert reference.check_spawn(.7, -.7).accepted  # Inside AABB, outside rotated box + footprint.
    assert not reference.check_spawn(.4, .4).accepted
    assert reference.check_spawn(.4, .4).reason == "blocked"


@pytest.mark.parametrize("angles", ["0 0 .7", ".35 .55 .7", "1.5707963267948966 0 .4"])
def test_prism_clearance_agrees_with_mujoco_box_distance(angles):
    obstacle = f'<geom name="obstacle" type="box" size=".8 .25 .5" pos="0 0 .55" euler="{angles}"/>'
    config = _config(resolution_m=.25, clearance_half_extent_m=.2)
    reference = build_reference_grid(_model(obstacle), config)
    probe = ('<body name="probe" pos="0 0 .3"><freejoint/>'
             '<geom name="probe_geom" type="box" size=".2 .2 .3"/></body>')
    distance_model = _model(obstacle + probe)
    data = mujoco.MjData(distance_model)
    obstacle_id = mujoco.mj_name2id(distance_model, mujoco.mjtObj.mjOBJ_GEOM, "obstacle")
    probe_id = mujoco.mj_name2id(distance_model, mujoco.mjtObj.mjOBJ_GEOM, "probe_geom")
    for row in range(2, 22):
        for col in range(2, 22):
            data.qpos[:3] = [-3+(col+.5)*.25, -3+(row+.5)*.25, .3]
            mujoco.mj_forward(distance_model, data)
            # Only separation matters here. A near-contact bound avoids inaccurate
            # large positive distances in older MuJoCo convex collision pipelines.
            distance = mujoco.mj_geomDistance(distance_model, data, obstacle_id, probe_id, .001, None)
            assert bool(reference.free_mask[row, col]) == (distance > 1e-10), (angles, row, col, distance)
            touching = any({int(c.geom1), int(c.geom2)} == {obstacle_id, probe_id} and c.dist <= 1e-10
                           for c in data.contact)
            assert bool(reference.free_mask[row, col]) == (not touching)


def test_rotated_square_area_converges_to_analytic_minkowski_area():
    model = _model('<geom type="box" size=".5 .5 1" pos="0 0 1" euler="0 0 .7853981633974483"/>')
    # Offset a 45-degree unit square by a square of half extent r=.1.
    blocked_area = 1 + .4 * math.sqrt(2) + .04
    expected = 5.8**2 - blocked_area
    coarse = build_reference_grid(model, _config(resolution_m=.05)).metadata()["area_m2"]
    fine = build_reference_grid(model, _config(resolution_m=.025)).metadata()["area_m2"]
    assert abs(coarse - expected) < .10
    assert abs(fine - expected) < .05
    assert abs(fine - expected) <= abs(coarse - expected) + .005


def test_nested_body_translation_and_quarter_turn_preserve_geometry():
    obstacle = '<geom name="wall" type="box" size=".6 .2 1" pos=".7 -.5 1"/>'
    base = build_reference_grid(_model(obstacle), _config())
    translated = build_reference_grid(
        _model(obstacle, transform='pos="7 -5 1.25"'),
        _config(bounds=(4, -8, 10, -2), component_anchor=(5, -7)),
    )
    rotated = build_reference_grid(
        _model(obstacle, transform='euler="0 0 1.5707963267948966"'),
        _config(component_anchor=(2, -2)),
    )
    assert np.array_equal(base.mask, translated.mask)
    assert translated.floor_height_m == pytest.approx(1.25)
    assert np.array_equal(np.rot90(base.mask, -1), rotated.mask)


@pytest.mark.parametrize("gap,connected", [(.6, False), (.8, False), (1.2, True)])
def test_narrow_door_clearance_and_connectivity(gap, connected):
    half = (3-gap/2)/2
    center = (3+gap/2)/2
    walls = ''.join(f'<geom type="box" size=".05 {half} 1" pos="0 {sign*center} 1"/>' for sign in (-1, 1))
    reference = build_reference_grid(_model(walls), _config(component_anchor=(-2, 0), clearance_half_extent_m=.4))
    assert reference.check_spawn(2, 0).accepted is connected
    assert reference.check_spawn(2, 0).reason == ("accepted" if connected else "disconnected")


def test_thin_wall_cannot_connect_free_centers_through_an_obstacle():
    model = _model('<geom type="box" size=".005 2 1" pos="0 0 1"/>')
    config = _config(bounds=(-2, -2, 2, 2), component_anchor=(-1, 0), resolution_m=1)
    reference = build_reference_grid(model, config)
    assert reference.free_mask.sum() == 16  # No cell center lies inside the thin obstacle.
    assert reference.mask.sum() == 8  # Swept-edge checking still separates the rooms.
    assert reference.check_spawn(1, 0).reason == "disconnected"
    with pytest.raises(ValueError, match="anchor"):
        build_reference_grid(model, replace(config, component_anchor=(0, 0)))


def test_finite_floor_requires_full_footprint_support():
    floor = '<geom name="floor" type="box" size=".5 .5 .1" pos="0 0 -.1"/>'
    reference = build_reference_grid(_model(floor=floor), _config(component_anchor=(0, 0), clearance_half_extent_m=.2))
    assert reference.mask.sum() == 36
    assert reference.check_spawn(.4, 0).reason == "blocked"


def test_plane_floor_uses_explicit_bounds_and_elevation():
    floor = '<geom name="floor" type="plane" size="0 0 .1" pos="0 0 1.5"/>'
    reference = build_reference_grid(_model(floor=floor), _config())
    assert reference.floor_height_m == 1.5
    assert reference.mask.sum() == 58**2
    assert reference.check_spawn(-2.9, 0).reason == "blocked"
    assert reference.check_spawn(3, 0).reason == "outside_bounds"


@pytest.mark.parametrize("bottom,clear", [(.7, True), (.6, False), (.59, False)])
def test_vertical_clearance_for_overhanging_boxes(bottom, clear):
    obstacle = f'<geom type="box" size=".5 .5 .1" pos="0 0 {bottom+.1}"/>'
    reference = build_reference_grid(_model(obstacle), _config())
    assert reference.check_spawn(0, 0).accepted is clear


def test_visual_only_geometry_is_ignored_but_one_sided_collision_masks_are_not():
    visual = '<geom name="decoration" type="sphere" size="1" pos="0 0 1" contype="0" conaffinity="0"/>'
    collider = '<geom name="wall" type="box" size=".5 .5 1" pos="0 0 1" contype="0" conaffinity="1"/>'
    reference = build_reference_grid(_model(visual + collider), _config())
    assert reference.check_spawn(0, 0).reason == "blocked"
    assert reference.check_spawn(1.5, 0).accepted


def test_unsupported_contact_geometry_and_moving_scenes_fail_explicitly():
    for geometry in (
        '<geom type="sphere" size=".5" pos="0 0 1"/>',
        '<geom type="cylinder" size=".5 1" pos="0 0 1"/>',
        '<body><freejoint/><geom type="box" size=".1 .1 .1"/></body>',
        '<body mocap="true"><geom type="box" size=".1 .1 .1"/></body>',
    ):
        with pytest.raises(ValueError, match="Unsupported|static environment"):
            build_reference_grid(_model(geometry), _config())


@pytest.mark.parametrize("floor", [
    '<geom name="wrong" type="box" size="4 4 .1"/>',
    '<geom name="floor" type="box" size="4 4 .1" contype="0" conaffinity="0"/>',
    '<geom name="floor" type="box" size="4 4 .1" euler=".2 0 0"/>',
])
def test_invalid_support_floor_is_rejected(floor):
    with pytest.raises(ValueError, match="Floor|floor"):
        build_reference_grid(_model(floor=floor), _config())


def test_disabled_contact_system_is_rejected():
    with pytest.raises(ValueError, match="disabled"):
        build_reference_grid(_model(prefix='<option><flag contact="disable"/></option>'), _config())


@pytest.mark.parametrize("kwargs", [
    {"resolution_m": 0}, {"resolution_m": float("nan")}, {"resolution_m": 1e-323},
    {"resolution_m": .0001}, {"resolution_m": .7}, {"resolution_m": True},
    {"bounds": (0, 0, 0, 1)}, {"bounds": (0, 0, float("inf"), 1)},
    {"component_anchor": (float("nan"), 0)}, {"clearance_half_extent_m": -1},
    {"clearance_height_m": 0}, {"floor_geom_name": ""}, {"robot_contype": True},
    {"robot_contype": 0, "robot_conaffinity": 0},
])
def test_invalid_config_fails_before_grid_allocation(kwargs):
    with pytest.raises(ValueError):
        _config(**kwargs)


def test_missing_or_obstructed_anchor_fails():
    model = _model('<geom type="box" size=".5 .5 1" pos="0 0 1"/>')
    for anchor in ((0, 0), (10, 10)):
        with pytest.raises(ValueError, match="anchor"):
            build_reference_grid(model, _config(component_anchor=anchor))


def test_hashes_capture_geometry_config_and_mask_and_arrays_are_snapshots():
    model = _model('<geom name="wall" type="box" size=".3 .3 1" pos="0 0 1"/>')
    first = build_reference_grid(model, _config())
    assert first.metadata() == build_reference_grid(model, _config()).metadata()
    finer = build_reference_grid(model, _config(resolution_m=.05))
    assert finer.geometry_sha256 == first.geometry_sha256
    assert finer.metadata()["reference_sha256"] != first.metadata()["reference_sha256"]
    previous = first.metadata()
    model.geom_pos[1, 0] = 1
    second = build_reference_grid(model, _config())
    assert second.geometry_sha256 != first.geometry_sha256
    assert first.metadata() == previous
    assert first.check_spawn(0, 0).reason == "blocked"
    assert second.check_spawn(0, 0).accepted
    with pytest.raises(ValueError):
        first.mask.setflags(write=True)
    with pytest.raises(ValueError):
        first.free_mask[0, 0] = True


def test_diagnostics_export_masks_metadata_and_rejected_spawns(tmp_path):
    reference = build_reference_grid(_model('<geom type="box" size=".5 .5 1" pos="0 0 1"/>'), _config())
    paths = reference.write_diagnostics(tmp_path, spawn_points=[(-2, -2), (0, 0), (8, 0)])
    data = json.loads(paths["reference.json"].read_text())
    assert [s["reason"] for s in data["spawn_checks"]] == ["accepted", "blocked", "outside_bounds"]
    with np.load(paths["reference.npz"], allow_pickle=False) as saved:
        assert np.array_equal(saved["mask"], reference.mask)
        assert np.array_equal(saved["free_mask"], reference.free_mask)
    svg = ET.fromstring(paths["reference.svg"].read_text())
    markers = svg.findall("{http://www.w3.org/2000/svg}circle")
    assert len(markers) == 3
    assert markers[0].get("fill") != markers[1].get("fill")
    assert all(0 <= float(marker.get("cx")) <= reference.mask.shape[1] * 6 for marker in markers)
    assert data["mask_sha256"] == reference.metadata()["mask_sha256"]
