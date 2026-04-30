"""Tests for strict Go2 foot mapping and contact/terrain locomotion metrics."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.locomotion.metrics import (
    FOOT_GEOM_NAMES,
    Go2FootMapping,
    LocomotionMetricsCollector,
    terrain_height_at,
)
from src.locomotion.scenarios import ScenarioSample


_GO2_XML = Path(__file__).resolve().parents[2] / "models" / "unitree_go2" / "go2.xml"
_ZERO12 = np.zeros(12, dtype=np.float64)


def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
    try:
        import mujoco  # noqa: F401
    except ImportError:
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")


class _FakeMujoco:
    class mjtObj:
        mjOBJ_GEOM = object()

    def __init__(self, names_to_ids: dict[str, int]) -> None:
        self.names_to_ids = names_to_ids

    def mj_name2id(self, _model, _obj_type, name: str) -> int:
        return self.names_to_ids.get(name, -1)


def _sample(scenario_id: str, terrain_parameters: dict[str, object]) -> ScenarioSample:
    return ScenarioSample(
        scenario_id=scenario_id,
        spawn_pose=(0.0, 0.0, 0.30, 0.0),
        terrain_parameters=terrain_parameters,
        command_schedule=(),
        disturbance_schedule=(),
    )


def _record_contact_step(
    collector: LocomotionMetricsCollector,
    *,
    foot_positions_world: dict[str, tuple[float, float, float]],
    foot_contacts: dict[str, bool],
    terrain_height_m: float | dict[str, float] = 0.0,
    scenario_failed: bool | None = None,
    dt: float = 0.1,
):
    return collector.record_step(
        desired_command=(0.0, 0.0, 0.0),
        measured_base_velocity=(0.0, 0.0, 0.0),
        roll_rad=0.0,
        pitch_rad=0.0,
        base_height_m=0.30,
        base_xy_position=(0.0, 0.0),
        action_target=_ZERO12,
        previous_action_target=_ZERO12,
        previous_previous_action_target=_ZERO12,
        joint_qpos=_ZERO12,
        joint_qvel=_ZERO12,
        dt=dt,
        foot_positions_world={name: np.asarray(pos, dtype=np.float64) for name, pos in foot_positions_world.items()},
        foot_contacts=foot_contacts,
        terrain_height_m=terrain_height_m,
        scenario_failed=scenario_failed,
    )


def test_resolves_go2_foot_geom_mapping():
    _skip_if_mujoco_python_unsupported()
    import mujoco

    model = mujoco.MjModel.from_xml_path(str(_GO2_XML))

    mapping = Go2FootMapping.from_mujoco_model(model)

    assert tuple(mapping.foot_geom_ids) == FOOT_GEOM_NAMES
    assert set(mapping.foot_geom_ids) == {"FL", "FR", "RL", "RR"}
    assert len(set(mapping.foot_geom_ids.values())) == 4
    for name, geom_id in mapping.foot_geom_ids.items():
        assert geom_id == mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)


def test_missing_required_foot_name_raises(monkeypatch):
    fake = _FakeMujoco({"FL": 1, "FR": 2, "RL": 3})
    monkeypatch.setitem(sys.modules, "mujoco", fake)

    with pytest.raises(ValueError, match="Missing required Go2 foot geom 'RR'"):
        Go2FootMapping.from_mujoco_model(SimpleNamespace())


def test_duplicate_foot_geom_id_raises(monkeypatch):
    fake = _FakeMujoco({"FL": 4, "FR": 4, "RL": 6, "RR": 7})
    monkeypatch.setitem(sys.modules, "mujoco", fake)

    with pytest.raises(ValueError, match="Duplicate Go2 foot geom ids"):
        Go2FootMapping.from_mujoco_model(SimpleNamespace())


def test_no_substring_heuristic_fallback(monkeypatch):
    fake = _FakeMujoco({"front_left_foot": 1, "FR": 2, "RL": 3, "RR": 4})
    monkeypatch.setitem(sys.modules, "mujoco", fake)

    with pytest.raises(ValueError, match="FL"):
        Go2FootMapping.from_mujoco_model(SimpleNamespace())


def test_records_contact_slip_clearance_and_duty_factor():
    collector = LocomotionMetricsCollector()
    first_positions = {
        "FL": (0.0, 0.0, 0.05),
        "FR": (0.0, 0.1, 0.06),
        "RL": (-0.2, 0.0, 0.20),
        "RR": (-0.2, 0.1, 0.21),
    }
    second_positions = {
        "FL": (0.02, 0.0, 0.04),
        "FR": (0.0, 0.1, 0.08),
        "RL": (-0.2, 0.0, 0.22),
        "RR": (-0.18, 0.1, 0.04),
    }

    first = _record_contact_step(
        collector,
        foot_positions_world=first_positions,
        foot_contacts={"FL": True, "FR": False, "RL": False, "RR": False},
        terrain_height_m=0.01,
        scenario_failed=False,
    )
    second = _record_contact_step(
        collector,
        foot_positions_world=second_positions,
        foot_contacts={"FL": True, "FR": False, "RL": False, "RR": True},
        terrain_height_m=0.01,
        scenario_failed=False,
    )

    assert first.contact_terrain["contact_transition"]["FL"] == "touchdown"
    assert second.contact_terrain["per_foot_contact"] == {
        "FL": True,
        "FR": False,
        "RL": False,
        "RR": True,
    }
    assert second.contact_terrain["contact_transition"]["RR"] == "touchdown"
    assert second.contact_terrain["foot_xy_velocity_when_contact"]["FL"] == pytest.approx(0.2)
    assert second.contact_terrain["foot_xy_velocity_when_contact"]["FR"] == 0.0
    assert second.contact_terrain["foot_clearance_m"]["FL"] == pytest.approx(0.03)

    summary = collector.episode_summary().contact_terrain
    assert summary["duty_factor"] == pytest.approx({"FL": 1.0, "FR": 0.0, "RL": 0.0, "RR": 0.5})
    assert summary["slip_mean_m_per_s"]["FL"] == pytest.approx(0.1)
    assert summary["slip_max_m_per_s"]["FL"] == pytest.approx(0.2)
    assert summary["clearance_min_m"]["FR"] == pytest.approx(0.05)
    assert summary["clearance_max_m"]["RL"] == pytest.approx(0.21)
    assert summary["gait_symmetry_contact_balance"] == pytest.approx(1.0)
    assert summary["scenario_success"] is True


def test_terrain_height_helper_returns_zero_for_plane_scenarios():
    for scenario_id in ("flat_ground", "low_friction", "push_disturbance"):
        sample = _sample(scenario_id, {"terrain_kind": "plane"})
        assert terrain_height_at(sample, 1.25, -3.5) == 0.0
    assert terrain_height_at(None, 1.0, 2.0) == 0.0


def test_terrain_height_helper_derives_slope_height_from_parameters():
    slope = 0.2
    sample = _sample("slope", {"terrain_kind": "slope", "slope_radians": slope})

    height = terrain_height_at(sample, 2.0, 1.0)

    assert height == pytest.approx(math.tan(slope) * 2.0 - 0.04)
    assert height != 0.0


def test_terrain_height_helper_samples_rough_heightfield_data():
    sample = _sample(
        "rough_heightfield",
        {
            "terrain_kind": "heightfield",
            "heightfield_size": 3,
            "heightfield_extent_x": 2.0,
            "heightfield_extent_y": 2.0,
            "heightfield_data": (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
        },
    )

    assert terrain_height_at(sample, 0.0, 0.0) == pytest.approx(0.4)
    assert terrain_height_at(sample, 2.0, 2.0) == pytest.approx(0.8)
    assert terrain_height_at(sample, 0.0, 0.0) != 0.0
