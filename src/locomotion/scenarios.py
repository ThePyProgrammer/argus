"""Named locomotion scenarios and deterministic reset sampling."""

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from src.locomotion.xml_patcher import patch_actuators_to_position


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    display_name: str
    terrain_kind: str
    randomizes_terrain: bool = False
    has_disturbance: bool = False


@dataclass(frozen=True)
class ScenarioSample:
    scenario_id: str
    spawn_pose: tuple[float, float, float, float]
    terrain_parameters: dict[str, float | int | str | tuple[float, ...]]
    command_schedule: tuple[dict[str, float], ...]
    disturbance_schedule: tuple[dict[str, float], ...]


SCENARIOS: dict[str, ScenarioSpec] = {
    "flat_ground": ScenarioSpec(
        scenario_id="flat_ground",
        display_name="Flat Ground",
        terrain_kind="plane",
    ),
    "low_friction": ScenarioSpec(
        scenario_id="low_friction",
        display_name="Low Friction",
        terrain_kind="plane",
    ),
    "slope": ScenarioSpec(
        scenario_id="slope",
        display_name="Slope",
        terrain_kind="slope",
        randomizes_terrain=True,
    ),
    "rough_heightfield": ScenarioSpec(
        scenario_id="rough_heightfield",
        display_name="Rough Heightfield",
        terrain_kind="heightfield",
        randomizes_terrain=True,
    ),
    "push_disturbance": ScenarioSpec(
        scenario_id="push_disturbance",
        display_name="Push Disturbance",
        terrain_kind="plane",
        has_disturbance=True,
    ),
}


def list_scenarios() -> list[str]:
    """Return the available named scenario ids in deterministic order."""
    return sorted(SCENARIOS.keys())


def build_scenario_xml(model_dir: str, sample: ScenarioSample) -> tuple[str, dict[str, bytes]]:
    """Return MJCF XML string plus mesh asset bytes for the sampled scenario."""
    model_path = Path(model_dir)
    go2_xml_path = model_path / "go2.xml"
    if not go2_xml_path.exists():
        raise FileNotFoundError(f"Go2 model not found: {go2_xml_path}")

    patched_xml = patch_actuators_to_position(str(go2_xml_path))
    root = ET.fromstring(patched_xml)
    compiler = root.find("compiler")
    if compiler is not None:
        compiler.attrib.pop("meshdir", None)
        compiler.attrib.pop("texturedir", None)

    asset = root.find("asset")
    if asset is None:
        asset = ET.SubElement(root, "asset")
    worldbody = root.find("worldbody")
    if worldbody is None:
        worldbody = ET.SubElement(root, "worldbody")

    terrain_kind = str(sample.terrain_parameters.get("terrain_kind", "plane"))
    assets = _load_asset_bytes(model_path / "assets")
    if terrain_kind == "plane":
        _upsert_benchmark_floor(worldbody, sample)
    elif terrain_kind == "slope":
        _remove_existing_floor(worldbody)
        _add_slope_marker(worldbody, sample)
    elif terrain_kind == "heightfield":
        _remove_existing_floor(worldbody)
        _add_rough_heightfield(asset, worldbody, sample, assets)
    else:
        raise ValueError(f"Unknown terrain_kind: {terrain_kind}")
    _ensure_light(worldbody)
    _ensure_visual_settings(root)

    return ET.tostring(root, encoding="unicode"), assets


def sample_scenario(
    scenario_id: str,
    rng: np.random.Generator,
    heightfield_size: int = 16,
) -> ScenarioSample:
    """Sample reset-time metadata for a named locomotion scenario.

    Args:
        scenario_id: Fixed catalog key. Arbitrary model/XML paths are not accepted.
        rng: NumPy generator, normally ``ArgusGo2Env.np_random`` after reset seeding.
        heightfield_size: Requested rough heightfield grid size; clipped to ``[4, 64]``.

    Raises:
        ValueError: If ``scenario_id`` is not a fixed catalog key.
    """
    if scenario_id not in SCENARIOS:
        raise ValueError(
            f"Unknown locomotion scenario '{scenario_id}'. Available: {list_scenarios()}"
        )

    spawn_pose = _sample_spawn_pose(rng)
    command_schedule = _sample_command_schedule(rng)
    terrain_parameters = _sample_terrain_parameters(scenario_id, rng, heightfield_size)
    disturbance_schedule = _sample_disturbance_schedule(scenario_id, rng)

    return ScenarioSample(
        scenario_id=scenario_id,
        spawn_pose=spawn_pose,
        terrain_parameters=terrain_parameters,
        command_schedule=command_schedule,
        disturbance_schedule=disturbance_schedule,
    )


def _remove_existing_floor(worldbody: ET.Element) -> None:
    for geom in worldbody.findall("geom"):
        if geom.get("type") == "plane" or geom.get("name") in {"floor", "benchmark_floor"}:
            worldbody.remove(geom)


def _upsert_benchmark_floor(worldbody: ET.Element, sample: ScenarioSample) -> None:
    friction = float(sample.terrain_parameters.get("friction_coefficient", 1.0))
    _remove_existing_floor(worldbody)
    ET.SubElement(
        worldbody,
        "geom",
        name="benchmark_floor",
        type="plane",
        size="50 50 0.05",
        condim="6",
        friction=f"{friction:g} 0.005 0.0001",
    )


def _add_slope_marker(worldbody: ET.Element, sample: ScenarioSample) -> None:
    slope = float(sample.terrain_parameters.get("slope_radians", 0.0))
    ET.SubElement(
        worldbody,
        "geom",
        name="slope_benchmark_marker",
        type="box",
        size="4 4 0.05",
        pos="0 0 -0.04",
        euler=f"0 {slope:g} 0",
        rgba="0.35 0.35 0.35 1",
    )


def _add_rough_heightfield(
    asset: ET.Element,
    worldbody: ET.Element,
    sample: ScenarioSample,
    assets: dict[str, bytes],
) -> None:
    size = int(sample.terrain_parameters.get("heightfield_size", 16))
    bounded_size = int(np.clip(size, 4, 64))
    amplitude = float(sample.terrain_parameters.get("roughness_amplitude", 0.02))
    heightfield_data = sample.terrain_parameters.get("heightfield_data")
    if heightfield_data is None:
        raise ValueError("rough_heightfield sample is missing heightfield_data")
    heights = np.asarray(heightfield_data, dtype=np.float32).reshape((bounded_size, bounded_size))
    del assets
    ET.SubElement(
        asset,
        "hfield",
        name="rough_heightfield",
        nrow=str(bounded_size),
        ncol=str(bounded_size),
        size=f"5 5 {max(amplitude, 0.02):g} 0.02",
    )
    ET.SubElement(
        worldbody,
        "geom",
        name="rough_heightfield_geom",
        type="hfield",
        hfield="rough_heightfield",
        friction="1 0.005 0.0001",
    )


def _ensure_light(worldbody: ET.Element) -> None:
    if not any(child.tag == "light" for child in worldbody):
        ET.SubElement(worldbody, "light", pos="0 0 3", dir="0 0 -1", directional="true")


def _ensure_visual_settings(root: ET.Element) -> None:
    visual = root.find("visual")
    if visual is None:
        visual = ET.SubElement(root, "visual")
    map_elem = visual.find("map")
    if map_elem is None:
        map_elem = ET.SubElement(visual, "map")
    map_elem.set("znear", "0.01")
    map_elem.set("zfar", "50")
    statistic = root.find("statistic")
    if statistic is None:
        statistic = ET.SubElement(root, "statistic")
    statistic.set("extent", "2")


def _load_asset_bytes(asset_dir: Path) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    if asset_dir.exists():
        for asset_path in asset_dir.iterdir():
            if asset_path.is_file():
                assets[asset_path.name] = asset_path.read_bytes()
    return assets


def _sample_spawn_pose(rng: np.random.Generator) -> tuple[float, float, float, float]:
    return (
        float(rng.uniform(-0.05, 0.05)),
        float(rng.uniform(-0.05, 0.05)),
        0.30,
        float(rng.uniform(-0.05, 0.05)),
    )


def _sample_command_schedule(
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, float]]:
    return (
        {"time": 0.0, "vx": 0.0, "vy": 0.0, "omega": 0.0},
        {
            "time": float(rng.uniform(0.2, 0.6)),
            "vx": float(rng.uniform(0.1, 0.4)),
            "vy": float(rng.uniform(-0.1, 0.1)),
            "omega": float(rng.uniform(-0.4, 0.4)),
        },
    )


def _sample_terrain_parameters(
    scenario_id: str,
    rng: np.random.Generator,
    heightfield_size: int,
) -> dict[str, float | int | str | tuple[float, ...]]:
    if scenario_id == "low_friction":
        return {
            "terrain_kind": "plane",
            "friction_coefficient": 0.35,
            "slope_radians": 0.0,
            "heightfield_size": 0,
        }

    if scenario_id == "slope":
        return {
            "terrain_kind": "slope",
            "friction_coefficient": 1.0,
            "slope_radians": float(rng.uniform(0.0872665, 0.174533)),
            "heightfield_size": 0,
        }

    if scenario_id == "rough_heightfield":
        bounded_size = int(np.clip(heightfield_size, 4, 64))
        amplitude = float(rng.uniform(0.015, 0.05))
        heights = rng.normal(0.0, amplitude, size=(bounded_size, bounded_size)).astype(np.float32)
        heights -= np.mean(heights, dtype=np.float32)
        return {
            "terrain_kind": "heightfield",
            "friction_coefficient": 1.0,
            "slope_radians": 0.0,
            "heightfield_size": bounded_size,
            "heightfield_extent_x": 5.0,
            "heightfield_extent_y": 5.0,
            "roughness_amplitude": amplitude,
            "heightfield_data": tuple(float(value) for value in heights.ravel()),
        }

    return {
        "terrain_kind": "plane",
        "friction_coefficient": 1.0,
        "slope_radians": 0.0,
        "heightfield_size": 0,
    }


def _sample_disturbance_schedule(
    scenario_id: str,
    rng: np.random.Generator,
) -> tuple[dict[str, float], ...]:
    if scenario_id != "push_disturbance":
        return ()

    return (
        {
            "time": float(rng.uniform(0.5, 2.0)),
            "force_x": float(rng.uniform(30.0, 80.0)),
            "force_y": 0.0,
            "force_z": 0.0,
            "duration": 0.1,
        },
    )
