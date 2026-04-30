"""Wave 0 tests for locomotion controller registry contracts.

Covers D-01, D-03, D-05, D-06, D-07, and D-08 from Phase 2 context:
registry discovery, default analytical baseline, unavailable future-controller seams,
capability metadata, deterministic unknown-id errors, and lightweight imports.
"""

from __future__ import annotations

import sys

import pytest

HEAVY_DEPS = ("torch", "ultralytics", "transformers", "mujoco", "gymnasium", "rospy", "rclpy")
REQUIRED_CAPABILITY_KEYS = (
    "family",
    "action_mode",
    "deterministic",
    "observation_expectation",
    "command_limits",
    "cpu_latency_hint_ms",
    "sim_supported",
    "hardware_supported",
    "model_requirements",
    "multi_robot_supported",
    "reproducibility",
)
REQUIRED_CONTROLLER_IDS = {"analytical_trot", "residual_policy", "direct_policy", "mpc", "wbc"}
PLACEHOLDER_IDS = {
    "residual_policy",
    "direct_policy",
    "mpc",
    "wbc",
}


def _entry_by_name(entries: list[dict], name: str) -> dict:
    for entry in entries:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"Missing controller registry entry: {name}; got {entries!r}")


def _assert_required_capabilities(entry: dict) -> None:
    caps = entry["capabilities"]
    missing = sorted(key for key in REQUIRED_CAPABILITY_KEYS if key not in caps)
    assert missing == [], f"{entry['name']} missing capability keys: {missing}"
    assert "parameter_schema" in entry
    assert isinstance(entry["parameter_schema"], dict)


def test_controller_registry_import_does_not_import_heavy_dependencies():
    """Registry import must stay lightweight; future controllers are lazy seams only."""
    pre_heavy = {dep: dep in sys.modules for dep in HEAVY_DEPS}
    sys.modules.pop("src.locomotion.controllers", None)
    pre = set(sys.modules)

    import src.locomotion.controllers  # noqa: F401

    delta = set(sys.modules) - pre
    for dep in HEAVY_DEPS:
        newly_added = dep in delta and not pre_heavy[dep]
        assert not newly_added, (
            f"Importing src.locomotion.controllers pulled {dep} into sys.modules; "
            "controller registry discovery must use lazy, dependency-light seams."
        )


def test_controller_registry_default_is_analytical_trot():
    from src.locomotion.controllers import ControllerRegistry

    assert ControllerRegistry.get_default() == "analytical_trot"


def test_controller_registry_unknown_id_lists_available_controllers():
    from src.locomotion.controllers import ControllerRegistry

    with pytest.raises(ValueError) as exc_info:
        ControllerRegistry.create("does_not_exist")

    message = str(exc_info.value)
    assert "Unknown locomotion controller" in message
    assert "Available:" in message
    for controller_id in REQUIRED_CONTROLLER_IDS:
        assert controller_id in message


def test_controller_registry_lists_required_controller_families():
    from src.locomotion.controllers import ControllerRegistry

    entries = ControllerRegistry.list_controllers()
    names = {entry["name"] for entry in entries}

    assert REQUIRED_CONTROLLER_IDS.issubset(names)


def test_controller_registry_entries_expose_capabilities_and_parameter_schema():
    from src.locomotion.controllers import ControllerRegistry

    for entry in ControllerRegistry.list_controllers():
        _assert_required_capabilities(entry)


def test_controller_registry_analytical_metadata_contains_required_fields():
    from src.locomotion.controllers import ControllerRegistry

    entry = _entry_by_name(ControllerRegistry.list_controllers(), "analytical_trot")

    assert entry["available"] is True
    for key in (
        "controller_id",
        "display_name",
        "family",
        "action_mode",
        "deterministic",
        "parameter_hash",
        "parameter_summary",
        "capabilities",
        "available",
    ):
        assert key in entry, f"analytical_trot metadata missing {key}"
    assert entry["controller_id"] == "analytical_trot"
    assert entry["display_name"]
    assert entry["capabilities"]["family"] == entry["family"]


@pytest.mark.parametrize("controller_id", sorted(PLACEHOLDER_IDS))
def test_controller_registry_placeholder_controllers_are_discoverable_but_unavailable(controller_id: str):
    from src.locomotion.controllers import ControllerRegistry, UnavailableControllerError

    entry = _entry_by_name(ControllerRegistry.list_controllers(), controller_id)

    assert entry["available"] is False
    assert entry.get("reason")
    with pytest.raises(UnavailableControllerError) as exc_info:
        ControllerRegistry.create(controller_id)

    message = str(exc_info.value)
    assert f"Controller '{controller_id}' is unavailable" in message
    assert entry["reason"] in message
