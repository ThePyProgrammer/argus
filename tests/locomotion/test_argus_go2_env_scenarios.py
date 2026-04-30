"""Scenario catalog tests for the Argus Go2 locomotion environment."""

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.scenarios import SCENARIOS, build_scenario_xml, list_scenarios, sample_scenario


REQUIRED_SCENARIOS = {
    "flat_ground",
    "low_friction",
    "slope",
    "rough_heightfield",
    "push_disturbance",
}
MODEL_DIR = Path(__file__).parent.parent.parent / "models" / "unitree_go2"
GO2_XML = MODEL_DIR / "go2.xml"


def test_scenario_catalog_contains_required_named_scenarios():
    """LOC-ENV-02 requires the five benchmark scenarios by stable name."""
    assert REQUIRED_SCENARIOS.issubset(SCENARIOS.keys())
    assert REQUIRED_SCENARIOS.issubset(set(list_scenarios()))
    assert list_scenarios() == sorted(list_scenarios())


def test_required_scenario_specs_have_expected_capability_flags():
    assert SCENARIOS["flat_ground"].terrain_kind == "plane"
    assert SCENARIOS["low_friction"].terrain_kind == "plane"
    assert SCENARIOS["slope"].terrain_kind == "slope"
    assert SCENARIOS["rough_heightfield"].terrain_kind == "heightfield"
    assert SCENARIOS["rough_heightfield"].randomizes_terrain is True
    assert SCENARIOS["push_disturbance"].has_disturbance is True


def test_unknown_scenario_raises_with_available_names():
    rng = np.random.default_rng(123)

    with pytest.raises(ValueError) as excinfo:
        sample_scenario("does_not_exist", rng)

    message = str(excinfo.value)
    assert "does_not_exist" in message
    assert "Available:" in message
    for scenario_id in REQUIRED_SCENARIOS:
        assert scenario_id in message


@pytest.mark.parametrize("scenario_id", sorted(REQUIRED_SCENARIOS))
def test_sample_scenario_returns_serializable_metadata_for_required_names(scenario_id):
    sample = sample_scenario(scenario_id, np.random.default_rng(123))

    assert sample.scenario_id == scenario_id
    assert len(sample.spawn_pose) == 4
    assert isinstance(sample.terrain_parameters, dict)
    assert len(sample.command_schedule) == 2
    assert isinstance(sample.command_schedule[0], dict)
    assert isinstance(sample.disturbance_schedule, tuple)


def test_direct_sampler_applies_flat_ground_defaults():
    sample = sample_scenario("flat_ground", np.random.default_rng(123))

    assert sample.terrain_parameters["friction_coefficient"] == 1.0
    assert sample.terrain_parameters["slope_radians"] == 0.0
    assert sample.terrain_parameters["heightfield_size"] == 0
    assert sample.disturbance_schedule == ()


def test_direct_sampler_applies_low_friction_defaults():
    sample = sample_scenario("low_friction", np.random.default_rng(123))

    assert sample.terrain_parameters["friction_coefficient"] == 0.35
    assert sample.terrain_parameters["slope_radians"] == 0.0
    assert sample.terrain_parameters["heightfield_size"] == 0
    assert sample.disturbance_schedule == ()


@pytest.mark.parametrize("scenario_id", sorted(REQUIRED_SCENARIOS))
def test_env_reset_selects_scenario_by_config_name(scenario_id):
    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id=scenario_id))
    try:
        _obs, info = env.reset(seed=123)
    finally:
        env.close()

    assert info["seed"] == 123
    assert info["scenario_id"] == scenario_id
    assert isinstance(info["sampled_parameters"], dict)
    assert {"terrain_kind", "friction_coefficient", "slope_radians", "heightfield_size"}.issubset(
        info["sampled_parameters"],
    )
    assert "command_schedule" in info
    assert "disturbance_schedule" in info


def test_env_info_returns_defensive_metadata_copies():
    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id="push_disturbance"))
    try:
        _obs, reset_info = env.reset(seed=123)
        reset_info["sampled_parameters"]["friction_coefficient"] = 999.0
        reset_info["command_schedule"][0]["vx"] = 999.0
        reset_info["disturbance_schedule"][0]["force_x"] = 999.0
        _obs, _reward, _terminated, _truncated, step_info = env.step(
            np.array([0.1, 0.0, 0.0], dtype=np.float32),
        )
    finally:
        env.close()

    assert step_info["sampled_parameters"]["friction_coefficient"] == 1.0
    assert step_info["command_schedule"][0]["vx"] == 0.0
    assert step_info["disturbance_schedule"][0]["force_x"] != 999.0


@pytest.mark.parametrize("scenario_id", sorted(REQUIRED_SCENARIOS))
def test_build_scenario_xml_returns_parseable_xml_and_assets_for_required_scenarios(scenario_id):
    sample = sample_scenario(scenario_id, np.random.default_rng(123))

    xml, assets = build_scenario_xml(str(MODEL_DIR), sample)

    root = ET.fromstring(xml)
    assert root.tag == "mujoco"
    assert isinstance(assets, dict)
    assert all(isinstance(name, str) and isinstance(value, bytes) for name, value in assets.items())


def test_build_scenario_xml_does_not_modify_go2_xml_on_disk():
    sample = sample_scenario("rough_heightfield", np.random.default_rng(123))
    before = GO2_XML.read_text()

    _xml, _assets = build_scenario_xml(str(MODEL_DIR), sample)

    after = GO2_XML.read_text()
    assert before == after, "go2.xml was modified on disk"


def test_low_friction_scenario_xml_has_benchmark_floor_friction_starting_with_0_35():
    sample = sample_scenario("low_friction", np.random.default_rng(123))

    root = ET.fromstring(build_scenario_xml(str(MODEL_DIR), sample)[0])
    floor = root.find("./worldbody/geom[@name='benchmark_floor']")

    assert floor is not None
    assert floor.get("friction", "").startswith("0.35")


def test_slope_scenario_xml_contains_slope_named_marker():
    sample = sample_scenario("slope", np.random.default_rng(123))

    root = ET.fromstring(build_scenario_xml(str(MODEL_DIR), sample)[0])
    named_elements = [elem.get("name", "") for elem in root.iter()]

    assert any("slope" in name for name in named_elements)


def test_slope_scenario_xml_uses_slope_without_flat_benchmark_floor():
    sample = sample_scenario("slope", np.random.default_rng(123))

    root = ET.fromstring(build_scenario_xml(str(MODEL_DIR), sample)[0])

    assert root.find("./worldbody/geom[@name='slope_benchmark_marker']") is not None
    assert root.find("./worldbody/geom[@name='benchmark_floor']") is None


def test_rough_heightfield_scenario_xml_contains_bounded_heightfield_marker():
    sample = sample_scenario("rough_heightfield", np.random.default_rng(123), heightfield_size=128)

    xml, _assets = build_scenario_xml(str(MODEL_DIR), sample)
    root = ET.fromstring(xml)
    hfield = root.find("./asset/hfield[@name='rough_heightfield']")
    geom = root.find("./worldbody/geom[@hfield='rough_heightfield']")

    assert sample.terrain_parameters["heightfield_size"] <= 64
    assert hfield is not None
    assert geom is not None


def test_rough_heightfield_scenario_xml_uses_heightfield_without_flat_benchmark_floor():
    sample = sample_scenario("rough_heightfield", np.random.default_rng(123))

    root = ET.fromstring(build_scenario_xml(str(MODEL_DIR), sample)[0])

    assert root.find("./worldbody/geom[@name='rough_heightfield_geom']") is not None
    assert root.find("./worldbody/geom[@name='benchmark_floor']") is None


def test_rough_heightfield_sample_contains_nonflat_deterministic_heights():
    first = sample_scenario("rough_heightfield", np.random.default_rng(123), heightfield_size=16)
    second = sample_scenario("rough_heightfield", np.random.default_rng(123), heightfield_size=16)

    heights = np.asarray(first.terrain_parameters["heightfield_data"], dtype=np.float32)
    assert heights.shape == (first.terrain_parameters["heightfield_size"] ** 2,)
    assert np.ptp(heights) > 0.0
    np.testing.assert_allclose(
        first.terrain_parameters["heightfield_data"],
        second.terrain_parameters["heightfield_data"],
    )


def test_push_disturbance_is_runtime_metadata_not_xml_force_encoding():
    sample = sample_scenario("push_disturbance", np.random.default_rng(123))

    xml = build_scenario_xml(str(MODEL_DIR), sample)[0]

    assert sample.disturbance_schedule
    assert "force_x" not in xml
