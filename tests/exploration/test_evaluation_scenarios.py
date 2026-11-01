"""Independent geometry and initial-condition checks for benchmark fixtures."""

from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from src.bridge.platforms.go2 import Go2Platform
from src.exploration.evaluation.scenarios import (
    DEFAULTS,
    SCENARIO_DIR,
    Obstacle,
    Rectangle,
    SpawnPose,
    list_scenarios,
    load_scenario,
)


@pytest.fixture(scope="module")
def scenarios():
    return {name: load_scenario(name) for name in list_scenarios()}


def _pose(robot_id, x, y, **kwargs):
    return SpawnPose(robot_id, x, y, kwargs.get("z", .3), kwargs.get("yaw_rad", 0.0))


def _copy_fixture(tmp_path: Path, name="connected_rooms"):
    for suffix in ("json", "xml"):
        shutil.copyfile(SCENARIO_DIR / f"{name}.{suffix}", tmp_path / f"{name}.{suffix}")
    return tmp_path / f"{name}.json", tmp_path / f"{name}.xml"


@pytest.mark.parametrize("name,expected_area", [
    # Clear corridor arms: 11.2*1.6 + 7.2*1.6 minus shared 1.6*1.6 junction.
    ("branching_corridor", 26.88),
    # Clear interior: 11.2*7.2 minus six disjoint 1.8*1.8 inflated columns.
    ("cluttered_room", 61.20),
    # Clear interior minus 5.6*1 vertical walls and 9.6*1 horizontal walls,
    # restoring the 1*1 intersection counted twice.
    ("connected_rooms", 66.44),
])
def test_reference_area_matches_hand_calculation_at_two_resolutions(scenarios, name, expected_area):
    scenario = scenarios[name]
    for resolution in (.10, .05):
        mask = scenario.reference_mask(resolution)
        assert mask.dtype == np.bool_
        assert not mask.flags.writeable
        assert mask.sum() * resolution**2 == pytest.approx(expected_area, abs=1e-8)
        summary = scenario.reference_metadata(resolution)
        assert summary["area_m2"] == pytest.approx(expected_area)
        assert summary["cell_count"] == round(expected_area / resolution**2)


def test_doors_connect_all_four_rooms_and_preserve_clearance(scenarios):
    scene = scenarios["connected_rooms"]
    mask = scene.reference_mask()
    for x, y in ((-3, -2), (-3, 2), (3, -2), (3, 2), (0, -2), (0, 2), (-3, 0), (3, 0)):
        assert scene.is_clear(x, y)
        assert mask[scene._cell(x, y, .1)]
    # Door opening is 1.6 m; after .4 m clearance on each side it is .8 m.
    assert scene.is_clear(0, 1.61)
    assert not scene.is_clear(0, 1.59)
    assert not scene.is_clear(-5.6, -2)  # Exactly touching an outer wall.
    assert not scene.is_clear(0, 0)  # Central wall crossing.


def test_disconnected_clear_spawn_is_rejected(scenarios):
    original = scenarios["connected_rooms"]
    scene = replace(original, obstacles=(Obstacle("obstacle_divider", Rectangle(-.1, -4, .1, 4)),),
                    component_anchor=(-3, 0))
    assert scene.is_clear(3, 0)
    assert scene.reference_mask().sum() == 3672  # 5.1 m * 7.2 m / .01 m2.
    with pytest.raises(ValueError, match="reference component"):
        scene.validate_spawn_pair((_pose("robot_a", -3, 0), _pose("robot_b", 3, 0)))


def test_empty_reference_fails_before_an_episode(scenarios):
    scene = replace(scenarios["cluttered_room"], bounds=Rectangle(-.2, -.2, .2, .2),
                    obstacles=(), component_anchor=(0, 0))
    with pytest.raises(ValueError, match="anchor"):
        scene.reference_mask()


@pytest.mark.parametrize("resolution", [0, -1, float("nan"), float("inf"), True, .3, .00001, 1e-323, 100])
def test_invalid_reference_resolution_is_rejected(scenarios, resolution):
    with pytest.raises(ValueError):
        scenarios["cluttered_room"].reference_mask(resolution)


@pytest.mark.parametrize("seed", [True, -1, 2**32, 1.5, float("nan"), "101"])
def test_invalid_seed_is_rejected(scenarios, seed):
    with pytest.raises(ValueError, match="Seed"):
        scenarios["connected_rooms"].sample(seed)


def test_samples_are_paired_reproducible_and_do_not_change_denominator(scenarios):
    for scene in scenarios.values():
        before = scene.reference_metadata()
        resolved = []
        for seed in (0, 2**32 - 1, 101, 102, 103, *range(1001, 1011)):
            first = scene.sample(seed)
            assert first == scene.sample(seed)
            scene.validate_spawn_pair(first.spawn_poses)
            encoded = json.dumps(first.to_dict(), allow_nan=False, sort_keys=True)
            assert json.loads(encoded)["seed"] == seed
            assert first.scenario_sha256 == scene.scenario_sha256
            resolved.append(first.spawn_poses)
        assert len(set(resolved)) > 1  # The seed changes actual initial conditions.
        assert before == scene.reference_metadata()


def test_sampling_does_not_consume_global_numpy_rng(scenarios):
    original_state = np.random.get_state()
    try:
        np.random.seed(45)
        expected = np.random.random(4)
        np.random.seed(45)
        scenarios["connected_rooms"].sample(101)
        assert np.array_equal(np.random.random(4), expected)
    finally:
        np.random.set_state(original_state)


@pytest.mark.parametrize("poses", [
    (_pose("robot_a", -3, -2), _pose("robot_b", -3, -2)),
    (_pose("robot_a", -3, -2), _pose("robot_b", -2.5, -2.5)),
    (_pose("robot_a", 0, 0), _pose("robot_b", 3, 2)),
    (_pose("robot_a", -7, -2), _pose("robot_b", 3, 2)),
    (_pose("robot_a", float("nan"), -2), _pose("robot_b", 3, 2)),
    (_pose("robot_a", -3, -2, z=.8), _pose("robot_b", 3, 2)),
    (_pose("robot_b", -3, -2), _pose("robot_a", 3, 2)),
])
def test_invalid_spawn_pairs_are_rejected(scenarios, poses):
    with pytest.raises(ValueError):
        scenarios["connected_rooms"].validate_spawn_pair(poses)


@pytest.mark.parametrize("change", [
    {"schema_version": 2}, {"schema_version": True}, {"scenario_id": "wrong"},
    {"spawn_pool": [[0, 0], [3, 2]]}, {"spawn_pool": [[-3, -2], [-3, -2]]},
    {"spawn_pool": [[-3, -2], [-3.1, -2.1]]},
    {"headings_deg": []}, {"headings_deg": [float("nan")]},
    {"bounds": [-6, -4, -6, 4]}, {"wall_height_m": .1},
    {"source": ""}, {"extra_unknown_key": 1},
])
def test_invalid_metadata_fails_on_load(tmp_path, change):
    meta_path, _ = _copy_fixture(tmp_path)
    payload = json.loads(meta_path.read_text())
    payload.update(change)
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenario("connected_rooms", scenario_dir=tmp_path)


@pytest.mark.parametrize("change", ["move", "rotate", "noncolliding", "extra_geom", "dynamic"])
def test_mjcf_geometry_must_match_the_independent_reference(tmp_path, change):
    _, xml_path = _copy_fixture(tmp_path)
    root = ET.fromstring(xml_path.read_text())
    world = root.find("worldbody")
    wall = world.find("geom[@name='obstacle_vertical_middle']")
    if change == "move":
        wall.set("pos", "1 0 1")
    elif change == "rotate":
        wall.set("euler", "0 0 .2")
    elif change == "noncolliding":
        wall.set("contype", "0")
    elif change == "extra_geom":
        ET.SubElement(world, "geom", name="hidden_obstacle", type="box", size=".1 .1 .1")
    else:
        body = ET.SubElement(world, "body", name="loose_prop", pos="0 0 1")
        ET.SubElement(body, "freejoint")
        ET.SubElement(body, "geom", type="box", size=".1 .1 .1")
    xml_path.write_text(ET.tostring(root, encoding="unicode"), encoding="utf-8")
    with pytest.raises(ValueError, match="geometry|metadata"):
        load_scenario("connected_rooms", scenario_dir=tmp_path)


def test_scene_and_metadata_hashes_track_input_changes(tmp_path):
    meta_path, xml_path = _copy_fixture(tmp_path)
    first = load_scenario("connected_rooms", scenario_dir=tmp_path)
    xml_path.write_text(xml_path.read_text() + "\n", encoding="utf-8")
    second = load_scenario("connected_rooms", scenario_dir=tmp_path)
    assert first.scene_sha256 != second.scene_sha256
    assert first.scenario_sha256 != second.scenario_sha256
    assert first.metadata_sha256 == second.metadata_sha256
    payload = json.loads(meta_path.read_text())
    payload["description"] += " Revised provenance."
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    third = load_scenario("connected_rooms", scenario_dir=tmp_path)
    assert second.metadata_sha256 != third.metadata_sha256
    assert second.scenario_sha256 != third.scenario_sha256
    assert second.scene_sha256 == third.scene_sha256


def test_unknown_scenario_cannot_escape_asset_directory():
    with pytest.raises(ValueError, match="Unknown exploration scenario"):
        load_scenario("../../other")


def test_clearance_envelope_contains_rotating_go2_body():
    metadata = Go2Platform().metadata
    assert DEFAULTS.clearance_half_extent_m >= math.hypot(metadata.dimensions[0]/2, metadata.dimensions[1]/2)
    assert DEFAULTS.clearance_height_m >= metadata.dimensions[2]
    assert DEFAULTS.spawn_height_m == metadata.spawn_height


@pytest.mark.parametrize("name", list_scenarios())
def test_all_spawn_headings_can_see_floor_through_the_go2_camera(scenarios, name):
    """Ray intersections use compiled geometry and the actual platform camera spec.

    This checks initial camera visibility without starting physics or a renderer.
    Pixel-depth agreement and moving-robot occlusion belong to the next collector.
    """
    scene = scenarios[name]
    root = ET.fromstring(scene.mjcf_xml)
    world = root.find("worldbody")
    camera_names = []
    for location_index, (x, y) in enumerate(scene.spawn_pool):
        for heading_index, yaw in enumerate(scene.headings_rad):
            probe_name = f"probe_{location_index}_{heading_index}"
            body = ET.SubElement(world, "body", name=probe_name, pos=f"{x} {y} {DEFAULTS.spawn_height_m}",
                                 quat=f"{math.cos(yaw/2)} 0 0 {math.sin(yaw/2)}")
            spec = Go2Platform().camera_spec(probe_name)
            ET.SubElement(body, "camera", **spec)
            camera_names.append(spec["name"])
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
    for camera_name in camera_names:
        camera_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, camera_name)
        rotation = data.cam_xmat[camera_id].reshape(3, 3)
        tan_half_fovy = math.tan(math.radians(model.cam_fovy[camera_id]) / 2)
        hits_floor = False
        for u in (-.4, 0, .4):
            direction = rotation @ np.array([u * tan_half_fovy, -.95 * tan_half_fovy, -1.0])
            direction /= np.linalg.norm(direction)
            hit_id = np.array([-1], dtype=np.int32)
            distance = mujoco.mj_ray(model, data, data.cam_xpos[camera_id], direction, None, 1, -1, hit_id)
            hits_floor |= distance > 0 and hit_id[0] == floor_id
        assert hits_floor, f"No initial floor visibility from {name}/{camera_name}"
