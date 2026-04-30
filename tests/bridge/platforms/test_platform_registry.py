from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from src.bridge import platforms
from src.bridge.platforms import registry
from src.bridge.platforms.base import RobotController
from src.bridge.platforms.registry import (
    clear_platform_registry,
    create_platform,
    ensure_platform_registered,
    get_platform_factory,
    list_platforms,
    register_platform,
)
from src.bridge.platforms.types import (
    ControllerHealth,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeStatus,
    RobotState,
)


class _Controller:
    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray:
        return np.zeros(1)

    def health(self) -> ControllerHealth:
        return ControllerHealth()

    def reset(self) -> None:
        pass


@dataclass
class _Platform:
    suffix: str = "default"

    @property
    def metadata(self) -> RobotPlatformMetadata:
        return RobotPlatformMetadata(
            name="dummy",
            display_name=f"Dummy {self.suffix}",
            model_dir="models/dummy",
            model_xml="dummy.xml",
            actuator_count=1,
            command_modes=("velocity", "stand", "stop"),
            footprint_radius=0.1,
            dimensions=(0.2, 0.2, 0.2),
            max_linear_speed=1.0,
            max_yaw_rate=1.0,
            marker_asset=None,
            spawn_height=0.1,
        )

    def model_xml_path(self) -> Path:
        return Path("models/dummy/dummy.xml")

    def read_model_xml(self) -> str:
        return "<mujoco/>"

    def actuator_names(self) -> tuple[str, ...]:
        return ("motor",)

    def initial_joint_qpos(self) -> np.ndarray:
        return np.zeros(1)

    def root_body_name(self) -> str:
        return "base"

    def camera_spec(self, robot_id: str) -> dict[str, str]:
        return {"name": f"{robot_id}_cam", "pos": "0 0 0", "xyaxes": "0 -1 0 0 0 1", "fovy": "70"}

    def make_controller(self, robot_id: str) -> RobotController:
        return _Controller()

    def extract_state(self, model, data, qpos_start: int, sim_time: float) -> RobotState:
        return RobotState(np.eye(4), np.zeros(3), np.zeros(1), np.zeros(1), np.array([1, 0, 0, 0]), (), sim_time)

    def runtime_status(self, robot_id, state, last_command, controller_health, collision_count=0, near_miss_count=0):
        return RobotRuntimeStatus(last_command=last_command, controller_health=controller_health)


@pytest.fixture(autouse=True)
def isolated_platform_registry():
    clear_platform_registry()
    yield
    clear_platform_registry()


def test_package_namespace_exports_registry_functions():
    assert platforms.clear_platform_registry is registry.clear_platform_registry
    assert platforms.create_platform is registry.create_platform
    assert platforms.list_platforms is registry.list_platforms
    assert platforms.register_platform is registry.register_platform



def test_register_and_create_platform():
    register_platform("dummy", _Platform)

    platform = create_platform("dummy", suffix="custom")

    assert platform.metadata.name == "dummy"
    assert platform.metadata.display_name == "Dummy custom"


def test_list_platforms_is_sorted():
    register_platform("zeta", _Platform)
    register_platform("alpha", _Platform)

    assert list_platforms() == ["alpha", "zeta"]


def test_duplicate_registration_is_rejected():
    register_platform("dummy", _Platform)

    try:
        register_platform("dummy", _Platform)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate platform registration was accepted")


def test_get_platform_factory_returns_registered_factory_or_none():
    assert get_platform_factory("dummy") is None

    register_platform("dummy", _Platform)

    assert get_platform_factory("dummy") is _Platform


def test_ensure_platform_registered_is_idempotent_for_same_factory():
    ensure_platform_registered("dummy", _Platform)
    ensure_platform_registered("dummy", _Platform)

    assert list_platforms() == ["dummy"]
    assert create_platform("dummy").metadata.name == "dummy"


def test_ensure_platform_registered_rejects_conflicting_factory():
    class _ConflictingPlatform(_Platform):
        pass

    ensure_platform_registered("dummy", _Platform)

    try:
        ensure_platform_registered("dummy", _ConflictingPlatform)
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("conflicting platform registration was accepted")


def test_unknown_platform_message_names_known_platforms():
    register_platform("dummy", _Platform)

    try:
        create_platform("missing")
    except ValueError as exc:
        assert "Unknown robot platform 'missing'" in str(exc)
        assert "dummy" in str(exc)
    else:
        raise AssertionError("unknown platform was created")
