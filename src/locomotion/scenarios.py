"""Named locomotion scenarios and deterministic reset sampling."""

from dataclasses import dataclass

import numpy as np


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
    terrain_parameters: dict[str, float | int | str]
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
) -> dict[str, float | int | str]:
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
        return {
            "terrain_kind": "heightfield",
            "friction_coefficient": 1.0,
            "slope_radians": 0.0,
            "heightfield_size": bounded_size,
            "roughness_amplitude": float(rng.uniform(0.015, 0.05)),
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
