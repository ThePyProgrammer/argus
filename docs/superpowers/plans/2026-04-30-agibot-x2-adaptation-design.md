# AGIBOT X2 Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adapt Argus so MuJoCo multi-robot simulation can run either existing Unitree Go2 robots or 2-5 AGIBOT X2 robots behind a platform abstraction, with X2 locomotion hidden behind a replaceable walking-policy boundary and platform state visible in the backend/UI.

**Architecture:** Add a `src.bridge.platforms` layer below `MultiRobotBridge`. The bridge keeps shared MuJoCo orchestration, rendering, stepping, pose extraction, and command routing; `Go2Platform` preserves the current quadruped model/gait behavior; `AgibotX2Platform` owns X2 asset validation, actuator/sensor mapping, controller IO, fall detection, and runtime health. Coordinator/backend/frontend consume generic platform metadata and runtime status instead of robot-specific conditionals.

**Tech Stack:** Python 3.10, MuJoCo, NumPy, pytest, FastAPI/WebSocket, React 18, Zustand, Three.js, Vitest.

---

## Scope Check

This plan is one vertical implementation because the backend/UI work is contract plumbing for the same platform state produced by the bridge. It does not include hardware, AimDK_X2, ROS 2 PC2 deployment, Isaac Lab, policy training, or raw-joint swarm control.

The repo does not currently contain AGIBOT X2 assets. The implementation must support this state explicitly:

- Unit tests use generated XML fixtures and fake controller weights.
- Runtime X2 startup fails loudly when `models/agibot_x2/x2_ultra.xml` is missing.
- Asset smoke tests are skipped unless `ARGUS_X2_ENABLE_ASSET_SMOKE=1` is set and licensed X2 assets are present.
- The milestone is not complete until the non-skipped X2 smoke tests pass with real X2 assets and a real walking controller/policy.

## File Structure

### New backend/simulation files

- Create `src/bridge/platforms/__init__.py` — registers built-in robot platforms.
- Create `src/bridge/platforms/types.py` — shared enums/dataclasses for commands, metadata, controller health, robot state, and runtime status.
- Create `src/bridge/platforms/base.py` — `RobotPlatform` and `RobotController` protocols.
- Create `src/bridge/platforms/registry.py` — small platform registry matching existing SLAM/perception registry style.
- Create `src/bridge/platforms/go2.py` — Go2 metadata, actuator names, standing pose, gait-controller adapter, and fall-state mapping.
- Create `src/bridge/platforms/agibot_x2.py` — X2 metadata, XML asset validation, actuator discovery, neutral pose discovery, controller creation, fall detection, and runtime status.
- Create `src/locomotion/x2_controller.py` — replaceable X2 walking-controller boundary with stand-safe fallback and NPZ policy adapter for IO validation.
- Create `src/bridge/collision_state.py` — pure collision/near-miss summary helper for N robots.

### Existing backend/simulation files to modify

- Modify `src/bridge/multi_robot_config.py:11-38` — add `platform`, `platform_config`, and spawn-height handling.
- Modify `src/bridge/scene_builder.py:1-300` — add generic `build_multi_robot_scene()` while keeping Go2 wrappers working.
- Modify `src/bridge/multi_bridge.py:1-502` — route model/control/status behavior through `RobotPlatform`.
- Modify `src/coordination/spawn.py:33-85` — accept platform spawn height.
- Modify `src/coordination/coordinator.py:46-80, 359-417, 477-589, 706-860` — include runtime status in viz data, skip disabled robots, and handle generic commands.
- Modify `backend/web/server.py:27-96, 211-239` — include platform metadata in app state and robot-list handshake.
- Modify `backend/web/streaming_viz.py:198-225, 489-552` — emit platform/runtime/failure/controller fields in stats.
- Modify `src/main.py:69-157, 241-277, 322-390, 466-478` — add `--platform`, create platform-specific config, and preserve platform on restart.

### Frontend files to modify

- Modify `frontend/src/utils/messageTypes.ts:1-75` — add platform metadata and runtime status types.
- Modify `frontend/src/stores/robotStore.ts:7-64, 75-141` — store platform metadata and runtime state per robot.
- Modify `frontend/src/hooks/useWebSocket.ts:81-116` — ingest robot-list metadata and runtime status from stats.
- Modify `frontend/src/components/RobotCard.tsx:20-121` — display platform, runtime state, fall reason, controller health, and collision/near-miss summary.
- Modify `frontend/src/components/RobotMarker.ts:1-200` — scale fallback markers from platform footprint and avoid Go2-only marker assumptions.
- Modify `frontend/src/components/SceneViewer.tsx:135-139` — pass platform metadata to marker updates.

### New tests

- Create `tests/bridge/platforms/test_platform_types.py`
- Create `tests/bridge/platforms/test_platform_registry.py`
- Create `tests/bridge/platforms/test_go2_platform.py`
- Create `tests/bridge/platforms/test_x2_controller.py`
- Create `tests/bridge/platforms/test_agibot_x2_platform.py`
- Create `tests/bridge/test_collision_state.py`
- Create `tests/bridge/test_multi_bridge_platform_selection.py`
- Create `tests/web/test_platform_metadata_stream.py`
- Create `frontend/src/stores/__tests__/robotStore.platformState.test.ts`
- Create `frontend/src/components/__tests__/RobotCard.platformState.test.tsx`
- Create `frontend/src/components/__tests__/RobotMarker.platformMetadata.test.ts`
- Create `tests/bridge/platforms/test_agibot_x2_asset_smoke.py`

---

### Task 1: Platform data contracts

**Files:**
- Create: `src/bridge/platforms/__init__.py`
- Create: `src/bridge/platforms/types.py`
- Create: `src/bridge/platforms/base.py`
- Test: `tests/bridge/platforms/test_platform_types.py`

- [ ] **Step 1: Write the failing platform type tests**

Create `tests/bridge/platforms/test_platform_types.py`:

```python
import numpy as np

from src.bridge.platforms.types import (
    CommandTracking,
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
)


def test_robot_command_wire_shape_is_json_safe():
    cmd = RobotCommand.velocity([0.3, -0.1], yaw_rate=0.2)

    assert cmd.to_wire() == {
        "mode": "velocity",
        "linear": [0.3, -0.1],
        "yaw_rate": 0.2,
        "waypoint": None,
    }


def test_runtime_status_wire_contains_failure_and_controller_health():
    status = RobotRuntimeStatus(
        state=RobotRuntimeState.FALLEN,
        fall_reason=FallReason.ROLL_PITCH_THRESHOLD,
        last_command=RobotCommand.stop(),
        command_tracking=CommandTracking(linear_error=0.2, yaw_error=0.1),
        controller_health=ControllerHealth(
            policy_loaded=True,
            action_shape_valid=True,
            nan_guard_ok=False,
            actuator_clamp_count=3,
            message="invalid policy output",
        ),
        collision_count=1,
        near_miss_count=2,
    )

    payload = status.to_wire()

    assert payload["state"] == "fallen"
    assert payload["fall_reason"] == "roll_pitch_threshold"
    assert payload["last_command"]["mode"] == "stop"
    assert payload["command_tracking"]["linear_error"] == 0.2
    assert payload["controller_health"]["nan_guard_ok"] is False
    assert payload["collision_count"] == 1
    assert payload["near_miss_count"] == 2
    assert payload["disabled"] is True


def test_platform_metadata_wire_contains_footprint_and_command_modes():
    metadata = RobotPlatformMetadata(
        name="agibot_x2",
        display_name="AGIBOT X2 Ultra",
        model_dir="models/agibot_x2",
        model_xml="x2_ultra.xml",
        actuator_count=31,
        command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
        footprint_radius=0.33,
        dimensions=(0.46, 0.21, 1.31),
        max_linear_speed=0.8,
        max_yaw_rate=1.0,
        marker_asset=None,
        spawn_height=0.85,
    )

    assert metadata.to_wire() == {
        "name": "agibot_x2",
        "display_name": "AGIBOT X2 Ultra",
        "model_dir": "models/agibot_x2",
        "model_xml": "x2_ultra.xml",
        "actuator_count": 31,
        "command_modes": ["velocity", "stand", "stop", "recover", "waypoint"],
        "footprint_radius": 0.33,
        "dimensions": [0.46, 0.21, 1.31],
        "max_linear_speed": 0.8,
        "max_yaw_rate": 1.0,
        "marker_asset": None,
        "spawn_height": 0.85,
    }


def test_robot_command_rejects_wrong_linear_shape():
    try:
        RobotCommand.velocity(np.array([1.0, 2.0, 3.0]), yaw_rate=0.0)
    except ValueError as exc:
        assert "linear command must have shape (2,)" in str(exc)
    else:
        raise AssertionError("RobotCommand.velocity accepted a 3-element linear command")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/platforms/test_platform_types.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.bridge.platforms'`.

- [ ] **Step 3: Add platform dataclasses and protocols**

Create `src/bridge/platforms/__init__.py`:

```python
"""Robot platform implementations for MuJoCo-backed Argus simulation."""
```

Create `src/bridge/platforms/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import numpy as np

CommandMode = Literal["velocity", "stand", "stop", "recover", "waypoint"]


class RobotRuntimeState(str, Enum):
    STANDING = "standing"
    WALKING = "walking"
    FALLEN = "fallen"
    RECOVERING = "recovering"
    DISABLED = "disabled"


class FallReason(str, Enum):
    NONE = "none"
    BASE_HEIGHT = "base_height"
    ROLL_PITCH_THRESHOLD = "roll_pitch_threshold"
    BAD_CONTACT = "bad_contact"
    ACTUATOR_SATURATION = "actuator_saturation"
    TIMEOUT = "timeout"
    CONTROLLER_INVALID_OUTPUT = "controller_invalid_output"


@dataclass(frozen=True)
class RobotCommand:
    linear: np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float64))
    yaw_rate: float = 0.0
    mode: CommandMode = "velocity"
    waypoint: tuple[float, float, float] | None = None

    @classmethod
    def velocity(cls, linear, yaw_rate: float) -> "RobotCommand":
        arr = np.asarray(linear, dtype=np.float64)
        if arr.shape != (2,):
            raise ValueError(f"linear command must have shape (2,), got {arr.shape}")
        return cls(linear=arr, yaw_rate=float(yaw_rate), mode="velocity")

    @classmethod
    def stand(cls) -> "RobotCommand":
        return cls(mode="stand")

    @classmethod
    def stop(cls) -> "RobotCommand":
        return cls(mode="stop")

    @classmethod
    def recover(cls) -> "RobotCommand":
        return cls(mode="recover")

    @classmethod
    def waypoint_command(cls, target) -> "RobotCommand":
        arr = np.asarray(target, dtype=np.float64).reshape(-1)
        if arr.shape not in {(2,), (3,)}:
            raise ValueError(f"waypoint command must have shape (2,) or (3,), got {arr.shape}")
        z = float(arr[2]) if arr.shape == (3,) else 0.0
        return cls(mode="waypoint", waypoint=(float(arr[0]), float(arr[1]), z))

    def to_wire(self) -> dict:
        return {
            "mode": self.mode,
            "linear": [float(self.linear[0]), float(self.linear[1])],
            "yaw_rate": float(self.yaw_rate),
            "waypoint": list(self.waypoint) if self.waypoint is not None else None,
        }


@dataclass(frozen=True)
class CommandTracking:
    linear_error: float = 0.0
    yaw_error: float = 0.0
    waypoint_error: float | None = None
    timed_out: bool = False

    def to_wire(self) -> dict:
        return {
            "linear_error": float(self.linear_error),
            "yaw_error": float(self.yaw_error),
            "waypoint_error": None if self.waypoint_error is None else float(self.waypoint_error),
            "timed_out": bool(self.timed_out),
        }


@dataclass(frozen=True)
class ControllerHealth:
    policy_loaded: bool = True
    action_shape_valid: bool = True
    nan_guard_ok: bool = True
    actuator_clamp_count: int = 0
    message: str = "ok"

    def to_wire(self) -> dict:
        return {
            "policy_loaded": bool(self.policy_loaded),
            "action_shape_valid": bool(self.action_shape_valid),
            "nan_guard_ok": bool(self.nan_guard_ok),
            "actuator_clamp_count": int(self.actuator_clamp_count),
            "message": self.message,
        }


@dataclass(frozen=True)
class RobotPlatformMetadata:
    name: str
    display_name: str
    model_dir: str
    model_xml: str
    actuator_count: int
    command_modes: tuple[CommandMode, ...]
    footprint_radius: float
    dimensions: tuple[float, float, float]
    max_linear_speed: float
    max_yaw_rate: float
    marker_asset: str | None
    spawn_height: float

    def to_wire(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "model_dir": self.model_dir,
            "model_xml": self.model_xml,
            "actuator_count": int(self.actuator_count),
            "command_modes": list(self.command_modes),
            "footprint_radius": float(self.footprint_radius),
            "dimensions": [float(v) for v in self.dimensions],
            "max_linear_speed": float(self.max_linear_speed),
            "max_yaw_rate": float(self.max_yaw_rate),
            "marker_asset": self.marker_asset,
            "spawn_height": float(self.spawn_height),
        }


@dataclass(frozen=True)
class RobotState:
    base_pose: np.ndarray
    base_velocity: np.ndarray
    joint_positions: np.ndarray
    joint_velocities: np.ndarray
    orientation_quat: np.ndarray
    contacts: tuple[str, ...]
    sim_time: float
    fallen: bool = False
    fall_reason: FallReason = FallReason.NONE


@dataclass(frozen=True)
class RobotRuntimeStatus:
    state: RobotRuntimeState = RobotRuntimeState.STANDING
    fall_reason: FallReason = FallReason.NONE
    last_command: RobotCommand = field(default_factory=RobotCommand.stand)
    command_tracking: CommandTracking = field(default_factory=CommandTracking)
    controller_health: ControllerHealth = field(default_factory=ControllerHealth)
    collision_count: int = 0
    near_miss_count: int = 0

    @property
    def disabled(self) -> bool:
        return self.state in {RobotRuntimeState.FALLEN, RobotRuntimeState.DISABLED}

    def to_wire(self) -> dict:
        return {
            "state": self.state.value,
            "fall_reason": self.fall_reason.value,
            "last_command": self.last_command.to_wire(),
            "command_tracking": self.command_tracking.to_wire(),
            "controller_health": self.controller_health.to_wire(),
            "collision_count": int(self.collision_count),
            "near_miss_count": int(self.near_miss_count),
            "disabled": self.disabled,
        }
```

Create `src/bridge/platforms/base.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from src.bridge.platforms.types import (
    ControllerHealth,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeStatus,
    RobotState,
)


@runtime_checkable
class RobotController(Protocol):
    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray: ...
    def health(self) -> ControllerHealth: ...
    def reset(self) -> None: ...


@runtime_checkable
class RobotPlatform(Protocol):
    @property
    def metadata(self) -> RobotPlatformMetadata: ...
    def model_xml_path(self) -> Path: ...
    def read_model_xml(self) -> str: ...
    def actuator_names(self) -> tuple[str, ...]: ...
    def initial_joint_qpos(self) -> np.ndarray: ...
    def root_body_name(self) -> str: ...
    def camera_spec(self, robot_id: str) -> dict[str, str]: ...
    def make_controller(self, robot_id: str) -> RobotController: ...
    def extract_state(self, model: Any, data: Any, qpos_start: int, sim_time: float) -> RobotState: ...
    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus: ...
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/bridge/platforms/test_platform_types.py -v
```

Expected: PASS for all four tests.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/platforms/__init__.py src/bridge/platforms/types.py src/bridge/platforms/base.py tests/bridge/platforms/test_platform_types.py
git commit -m "feat: add robot platform data contracts"
```

---

### Task 2: Platform registry

**Files:**
- Create: `src/bridge/platforms/registry.py`
- Modify: `src/bridge/platforms/__init__.py`
- Test: `tests/bridge/platforms/test_platform_registry.py`

- [ ] **Step 1: Write the failing registry tests**

Create `tests/bridge/platforms/test_platform_registry.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.bridge.platforms.base import RobotController
from src.bridge.platforms.registry import (
    clear_platform_registry,
    create_platform,
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


def setup_function():
    clear_platform_registry()


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


def test_unknown_platform_message_names_known_platforms():
    register_platform("dummy", _Platform)

    try:
        create_platform("missing")
    except ValueError as exc:
        assert "Unknown robot platform 'missing'" in str(exc)
        assert "dummy" in str(exc)
    else:
        raise AssertionError("unknown platform was created")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/platforms/test_platform_registry.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.bridge.platforms.registry'`.

- [ ] **Step 3: Add the registry implementation**

Create `src/bridge/platforms/registry.py`:

```python
from __future__ import annotations

from collections.abc import Callable

from src.bridge.platforms.base import RobotPlatform

_PlatformFactory = Callable[..., RobotPlatform]
_REGISTRY: dict[str, _PlatformFactory] = {}


def register_platform(name: str, factory: _PlatformFactory) -> None:
    key = name.strip().lower()
    if not key:
        raise ValueError("platform name must not be empty")
    if key in _REGISTRY:
        raise ValueError(f"Robot platform '{key}' is already registered")
    _REGISTRY[key] = factory


def create_platform(name: str, **kwargs) -> RobotPlatform:
    key = name.strip().lower()
    try:
        factory = _REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(list_platforms()) or "none"
        raise ValueError(f"Unknown robot platform '{name}'. Known platforms: {known}") from exc
    return factory(**kwargs)


def list_platforms() -> list[str]:
    return sorted(_REGISTRY)


def clear_platform_registry() -> None:
    _REGISTRY.clear()
```

Modify `src/bridge/platforms/__init__.py`:

```python
"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.registry import create_platform, list_platforms, register_platform

__all__ = ["create_platform", "list_platforms", "register_platform"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/bridge/platforms/test_platform_registry.py -v
```

Expected: PASS for all four tests.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/platforms/__init__.py src/bridge/platforms/registry.py tests/bridge/platforms/test_platform_registry.py
git commit -m "feat: add robot platform registry"
```

---

### Task 3: Go2 platform wrapper

**Files:**
- Create: `src/bridge/platforms/go2.py`
- Modify: `src/bridge/platforms/__init__.py`
- Test: `tests/bridge/platforms/test_go2_platform.py`

- [ ] **Step 1: Write the failing Go2 platform tests**

Create `tests/bridge/platforms/test_go2_platform.py`:

```python
import numpy as np

from src.bridge.platforms import create_platform, list_platforms
from src.bridge.platforms.go2 import GO2_ACTUATOR_NAMES, Go2Platform
from src.bridge.platforms.types import RobotCommand, RobotRuntimeState


def test_go2_registered_by_package_import():
    assert "go2" in list_platforms()
    assert create_platform("go2").metadata.name == "go2"


def test_go2_metadata_preserves_current_defaults():
    platform = Go2Platform()

    assert platform.metadata.model_dir == "models/unitree_go2"
    assert platform.metadata.model_xml == "go2.xml"
    assert platform.metadata.actuator_count == 12
    assert platform.metadata.spawn_height == 0.3
    assert platform.metadata.marker_asset == "/go2.glb"
    assert platform.actuator_names() == GO2_ACTUATOR_NAMES


def test_go2_velocity_controller_returns_twelve_targets():
    platform = Go2Platform()
    controller = platform.make_controller("robot_a")
    state = platform.extract_state(
        model=None,
        data=None,
        qpos_start=0,
        sim_time=0.0,
    )

    ctrl = controller.compute(RobotCommand.velocity([0.1, 0.0], 0.0), state, dt=0.02)

    assert ctrl.shape == (12,)
    assert np.isfinite(ctrl).all()
    assert controller.health().policy_loaded is True


def test_go2_runtime_status_maps_moving_command_to_walking():
    platform = Go2Platform()
    controller = platform.make_controller("robot_a")
    state = platform.extract_state(None, None, 0, 0.0)
    command = RobotCommand.velocity([0.2, 0.0], 0.1)

    status = platform.runtime_status("robot_a", state, command, controller.health())

    assert status.state == RobotRuntimeState.WALKING
    assert status.disabled is False
    assert status.to_wire()["last_command"]["mode"] == "velocity"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/platforms/test_go2_platform.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.bridge.platforms.go2'`.

- [ ] **Step 3: Add the Go2 platform wrapper**

Create `src/bridge/platforms/go2.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.platforms.types import (
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)
from src.bridge.sensor_types import STANDING_QPOS, quat_to_rotation_matrix
from src.locomotion.gait_controller import TrotGaitController

GO2_ACTUATOR_NAMES = (
    "FL_hip", "FL_thigh", "FL_calf",
    "FR_hip", "FR_thigh", "FR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
)


class Go2VelocityController:
    def __init__(self) -> None:
        self._gait = TrotGaitController()
        self._health = ControllerHealth(policy_loaded=True)

    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray:
        if command.mode in {"stand", "stop", "recover"}:
            return STANDING_QPOS.copy()
        vx = float(command.linear[0])
        vy = float(command.linear[1])
        return self._gait.compute(vx, vy, float(command.yaw_rate), float(dt))

    def health(self) -> ControllerHealth:
        return self._health

    def reset(self) -> None:
        self._gait = TrotGaitController()


class Go2Platform:
    def __init__(self, model_dir: str = "models/unitree_go2") -> None:
        self._metadata = RobotPlatformMetadata(
            name="go2",
            display_name="Unitree Go2",
            model_dir=model_dir,
            model_xml="go2.xml",
            actuator_count=12,
            command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
            footprint_radius=0.35,
            dimensions=(0.7, 0.35, 0.45),
            max_linear_speed=1.0,
            max_yaw_rate=3.0,
            marker_asset="/go2.glb",
            spawn_height=0.3,
        )

    @property
    def metadata(self) -> RobotPlatformMetadata:
        return self._metadata

    def model_xml_path(self) -> Path:
        return Path(self._metadata.model_dir) / self._metadata.model_xml

    def read_model_xml(self) -> str:
        return self.model_xml_path().read_text()

    def actuator_names(self) -> tuple[str, ...]:
        return GO2_ACTUATOR_NAMES

    def initial_joint_qpos(self) -> np.ndarray:
        return STANDING_QPOS.copy()

    def root_body_name(self) -> str:
        return "base"

    def camera_spec(self, robot_id: str) -> dict[str, str]:
        return {
            "name": f"{robot_id}_cam",
            "pos": "0.4 0 0.05",
            "xyaxes": "0 -1 0 0 0 1",
            "fovy": "70",
        }

    def make_controller(self, robot_id: str) -> Go2VelocityController:
        return Go2VelocityController()

    def extract_state(self, model: Any, data: Any, qpos_start: int, sim_time: float) -> RobotState:
        if data is None:
            pose = np.eye(4, dtype=np.float64)
            pose[:3, 3] = [0.0, 0.0, self.metadata.spawn_height]
            return RobotState(
                base_pose=pose,
                base_velocity=np.zeros(3, dtype=np.float64),
                joint_positions=STANDING_QPOS.copy(),
                joint_velocities=np.zeros(12, dtype=np.float64),
                orientation_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                contacts=(),
                sim_time=float(sim_time),
            )

        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = data.qpos[qpos_start:qpos_start + 3]
        quat = data.qpos[qpos_start + 3:qpos_start + 7]
        pose[:3, :3] = quat_to_rotation_matrix(quat)
        joint_positions = data.qpos[qpos_start + 7:qpos_start + 19].copy()
        joint_velocities = data.qvel[qpos_start + 6:qpos_start + 18].copy() if len(data.qvel) >= qpos_start + 18 else np.zeros(12)
        base_velocity = data.qvel[qpos_start:qpos_start + 3].copy() if len(data.qvel) >= qpos_start + 3 else np.zeros(3)
        fallen = pose[2, 3] < 0.16
        reason = FallReason.BASE_HEIGHT if fallen else FallReason.NONE
        return RobotState(
            base_pose=pose,
            base_velocity=base_velocity,
            joint_positions=joint_positions,
            joint_velocities=joint_velocities,
            orientation_quat=quat.copy(),
            contacts=(),
            sim_time=float(sim_time),
            fallen=fallen,
            fall_reason=reason,
        )

    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus:
        if state.fallen:
            runtime_state = RobotRuntimeState.FALLEN
            fall_reason = state.fall_reason
        elif last_command.mode == "recover":
            runtime_state = RobotRuntimeState.RECOVERING
            fall_reason = FallReason.NONE
        elif last_command.mode in {"stand", "stop"}:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        elif np.linalg.norm(last_command.linear) > 0.01 or abs(last_command.yaw_rate) > 0.01:
            runtime_state = RobotRuntimeState.WALKING
            fall_reason = FallReason.NONE
        else:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        return RobotRuntimeStatus(
            state=runtime_state,
            fall_reason=fall_reason,
            last_command=last_command,
            controller_health=controller_health,
            collision_count=collision_count,
            near_miss_count=near_miss_count,
        )
```

Modify `src/bridge/platforms/__init__.py`:

```python
"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.go2 import Go2Platform
from src.bridge.platforms.registry import create_platform, list_platforms, register_platform

try:
    register_platform("go2", Go2Platform)
except ValueError:
    pass

__all__ = ["Go2Platform", "create_platform", "list_platforms", "register_platform"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/bridge/platforms/test_go2_platform.py -v
```

Expected: PASS for all four tests.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/platforms/__init__.py src/bridge/platforms/go2.py tests/bridge/platforms/test_go2_platform.py
git commit -m "feat: wrap Go2 behavior as robot platform"
```

---

### Task 4: X2 walking-controller boundary

**Files:**
- Create: `src/locomotion/x2_controller.py`
- Test: `tests/bridge/platforms/test_x2_controller.py`

- [ ] **Step 1: Write failing controller-boundary tests**

Create `tests/bridge/platforms/test_x2_controller.py`:

```python
import numpy as np

from src.bridge.platforms.types import RobotCommand, RobotState
from src.locomotion.x2_controller import X2PolicyController


def _state(actuator_count: int) -> RobotState:
    pose = np.eye(4)
    pose[:3, 3] = [0.0, 0.0, 0.85]
    return RobotState(
        base_pose=pose,
        base_velocity=np.array([0.1, 0.0, 0.0]),
        joint_positions=np.zeros(actuator_count),
        joint_velocities=np.zeros(actuator_count),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        contacts=("left_foot", "right_foot"),
        sim_time=0.0,
    )


def test_stand_command_returns_default_pose_without_policy():
    controller = X2PolicyController(
        actuator_count=4,
        default_qpos=np.array([0.1, 0.2, 0.3, 0.4]),
    )

    action = controller.compute(RobotCommand.stand(), _state(4), dt=0.02)

    np.testing.assert_allclose(action, [0.1, 0.2, 0.3, 0.4])
    assert controller.health().policy_loaded is False
    assert controller.health().action_shape_valid is True


def test_policy_output_shape_and_clamp_count(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.ones((obs_dim, 4), dtype=np.float64),
        bias=np.array([0.0, 0.0, 0.0, 3.0], dtype=np.float64),
        lower=np.array([-1.0, -1.0, -1.0, -1.0], dtype=np.float64),
        upper=np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64),
        default_qpos=np.zeros(4, dtype=np.float64),
    )
    controller = X2PolicyController(actuator_count=4, policy_path=policy_path)

    action = controller.compute(RobotCommand.velocity([0.2, 0.1], 0.3), _state(4), dt=0.02)

    assert action.shape == (4,)
    assert np.isfinite(action).all()
    assert action[-1] == 1.0
    assert controller.health().policy_loaded is True
    assert controller.health().actuator_clamp_count == 4


def test_invalid_policy_output_uses_safe_default(tmp_path):
    policy_path = tmp_path / "policy.npz"
    obs_dim = 3 + 3 + 4 + 4
    np.savez(
        policy_path,
        weights=np.full((obs_dim, 4), np.nan, dtype=np.float64),
        bias=np.zeros(4, dtype=np.float64),
        lower=np.full(4, -1.0, dtype=np.float64),
        upper=np.full(4, 1.0, dtype=np.float64),
        default_qpos=np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64),
    )
    controller = X2PolicyController(actuator_count=4, policy_path=policy_path)

    action = controller.compute(RobotCommand.velocity([0.2, 0.0], 0.0), _state(4), dt=0.02)

    np.testing.assert_allclose(action, [0.4, 0.3, 0.2, 0.1])
    assert controller.health().nan_guard_ok is False
    assert controller.health().message == "controller_invalid_output"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/platforms/test_x2_controller.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.locomotion.x2_controller'`.

- [ ] **Step 3: Add the X2 controller boundary**

Create `src/locomotion/x2_controller.py`:

```python
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.bridge.platforms.types import ControllerHealth, RobotCommand, RobotState


class X2PolicyController:
    def __init__(
        self,
        actuator_count: int,
        policy_path: str | Path | None = None,
        default_qpos: np.ndarray | None = None,
    ) -> None:
        self._actuator_count = int(actuator_count)
        self._default_qpos = self._coerce_vector(
            np.zeros(self._actuator_count, dtype=np.float64) if default_qpos is None else default_qpos,
            "default_qpos",
        )
        self._weights: np.ndarray | None = None
        self._bias: np.ndarray | None = None
        self._lower = np.full(self._actuator_count, -np.inf, dtype=np.float64)
        self._upper = np.full(self._actuator_count, np.inf, dtype=np.float64)
        self._health = ControllerHealth(policy_loaded=False)
        if policy_path is not None:
            self._load_policy(Path(policy_path))

    def _coerce_vector(self, value, name: str) -> np.ndarray:
        arr = np.asarray(value, dtype=np.float64).reshape(-1)
        if arr.shape != (self._actuator_count,):
            raise ValueError(f"{name} must have shape ({self._actuator_count},), got {arr.shape}")
        return arr.copy()

    def _load_policy(self, path: Path) -> None:
        data = np.load(path)
        self._weights = np.asarray(data["weights"], dtype=np.float64)
        self._bias = self._coerce_vector(data["bias"], "bias")
        self._lower = self._coerce_vector(data.get("lower", self._lower), "lower")
        self._upper = self._coerce_vector(data.get("upper", self._upper), "upper")
        self._default_qpos = self._coerce_vector(data.get("default_qpos", self._default_qpos), "default_qpos")
        if self._weights.ndim != 2 or self._weights.shape[1] != self._actuator_count:
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=False,
                message="invalid_policy_weight_shape",
            )
            raise ValueError(
                f"weights must have shape (obs_dim, {self._actuator_count}), got {self._weights.shape}"
            )
        self._health = ControllerHealth(policy_loaded=True)

    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray:
        if command.mode in {"stand", "stop", "recover"} or self._weights is None or self._bias is None:
            return self._default_qpos.copy()

        obs = self._observation(command, state)
        if obs.shape[0] != self._weights.shape[0]:
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=False,
                message="observation_shape_mismatch",
            )
            return self._default_qpos.copy()

        raw = obs @ self._weights + self._bias
        if raw.shape != (self._actuator_count,):
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=False,
                message="action_shape_mismatch",
            )
            return self._default_qpos.copy()
        if not np.isfinite(raw).all():
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=True,
                nan_guard_ok=False,
                message="controller_invalid_output",
            )
            return self._default_qpos.copy()

        clipped = np.clip(raw, self._lower, self._upper)
        clamp_count = int(np.count_nonzero(np.abs(clipped - raw) > 1e-12))
        self._health = ControllerHealth(
            policy_loaded=True,
            action_shape_valid=True,
            nan_guard_ok=True,
            actuator_clamp_count=clamp_count,
            message="ok",
        )
        return clipped.astype(np.float64)

    def _observation(self, command: RobotCommand, state: RobotState) -> np.ndarray:
        command_vec = np.array([command.linear[0], command.linear[1], command.yaw_rate], dtype=np.float64)
        return np.concatenate([
            command_vec,
            np.asarray(state.base_velocity, dtype=np.float64).reshape(3),
            np.asarray(state.joint_positions, dtype=np.float64).reshape(-1),
            np.asarray(state.joint_velocities, dtype=np.float64).reshape(-1),
        ])

    def health(self) -> ControllerHealth:
        return self._health

    def reset(self) -> None:
        self._health = ControllerHealth(policy_loaded=self._weights is not None)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/bridge/platforms/test_x2_controller.py -v
```

Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add src/locomotion/x2_controller.py tests/bridge/platforms/test_x2_controller.py
git commit -m "feat: add X2 walking controller boundary"
```

---

### Task 5: AGIBOT X2 platform

**Files:**
- Create: `src/bridge/platforms/agibot_x2.py`
- Modify: `src/bridge/platforms/__init__.py`
- Test: `tests/bridge/platforms/test_agibot_x2_platform.py`

- [ ] **Step 1: Write failing X2 platform tests**

Create `tests/bridge/platforms/test_agibot_x2_platform.py`:

```python
from pathlib import Path

import numpy as np

from src.bridge.platforms import create_platform, list_platforms
from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.types import FallReason, RobotCommand, RobotRuntimeState


X2_FIXTURE_XML = """
<mujoco model="x2_fixture">
  <worldbody>
    <body name="pelvis" pos="0 0 0.85">
      <freejoint/>
      <body name="torso"/>
    </body>
  </worldbody>
  <actuator>
    <position name="left_hip_pitch" joint="left_hip_pitch"/>
    <position name="right_hip_pitch" joint="right_hip_pitch"/>
    <position name="left_knee" joint="left_knee"/>
  </actuator>
  <keyframe>
    <key name="home" qpos="0 0 0.85 1 0 0 0 0.1 0.2 0.3"/>
  </keyframe>
</mujoco>
"""


def _write_fixture_model(tmp_path: Path) -> Path:
    model_dir = tmp_path / "agibot_x2"
    model_dir.mkdir()
    (model_dir / "x2_ultra.xml").write_text(X2_FIXTURE_XML)
    return model_dir


def test_x2_registered_by_package_import():
    assert "agibot_x2" in list_platforms()
    assert create_platform("agibot_x2").metadata.name == "agibot_x2"


def test_x2_metadata_matches_design_contract():
    platform = AgibotX2Platform()

    assert platform.metadata.display_name == "AGIBOT X2 Ultra"
    assert platform.metadata.actuator_count == 31
    assert platform.metadata.command_modes == ("velocity", "stand", "stop", "recover", "waypoint")
    assert platform.metadata.max_linear_speed == 0.8
    assert platform.metadata.spawn_height == 0.85


def test_x2_parses_actuator_names_from_xml(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)

    assert platform.actuator_names() == ("left_hip_pitch", "right_hip_pitch", "left_knee")
    np.testing.assert_allclose(platform.initial_joint_qpos(), [0.1, 0.2, 0.3])
    assert platform.root_body_name() == "pelvis"


def test_x2_missing_asset_fails_with_clear_path(tmp_path):
    platform = AgibotX2Platform(model_dir=str(tmp_path / "missing"))

    try:
        platform.read_model_xml()
    except FileNotFoundError as exc:
        assert "x2_ultra.xml" in str(exc)
        assert "models/agibot_x2" not in str(exc)
    else:
        raise AssertionError("missing X2 asset did not raise FileNotFoundError")


def test_x2_runtime_status_detects_base_height_fall(tmp_path):
    model_dir = _write_fixture_model(tmp_path)
    platform = AgibotX2Platform(model_dir=str(model_dir), expected_actuator_count=3)
    pose = np.eye(4)
    pose[:3, 3] = [0.0, 0.0, 0.2]
    state = platform._state_from_arrays(
        base_pose=pose,
        base_velocity=np.zeros(3),
        joint_positions=np.zeros(3),
        joint_velocities=np.zeros(3),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        sim_time=0.0,
    )
    controller = platform.make_controller("robot_a")

    status = platform.runtime_status(
        "robot_a",
        state,
        RobotCommand.velocity([0.2, 0.0], 0.0),
        controller.health(),
    )

    assert status.state == RobotRuntimeState.FALLEN
    assert status.fall_reason == FallReason.BASE_HEIGHT
    assert status.disabled is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/platforms/test_agibot_x2_platform.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.bridge.platforms.agibot_x2'`.

- [ ] **Step 3: Add the X2 platform implementation**

Create `src/bridge/platforms/agibot_x2.py`:

```python
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.platforms.types import (
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)
from src.bridge.sensor_types import quat_to_rotation_matrix
from src.locomotion.x2_controller import X2PolicyController


class AgibotX2Platform:
    def __init__(
        self,
        model_dir: str = "models/agibot_x2",
        model_xml: str = "x2_ultra.xml",
        controller_path: str | None = None,
        expected_actuator_count: int = 31,
    ) -> None:
        self._controller_path = controller_path
        self._expected_actuator_count = int(expected_actuator_count)
        self._metadata = RobotPlatformMetadata(
            name="agibot_x2",
            display_name="AGIBOT X2 Ultra",
            model_dir=model_dir,
            model_xml=model_xml,
            actuator_count=self._expected_actuator_count,
            command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
            footprint_radius=0.33,
            dimensions=(0.46, 0.21, 1.31),
            max_linear_speed=0.8,
            max_yaw_rate=1.0,
            marker_asset=None,
            spawn_height=0.85,
        )

    @property
    def metadata(self) -> RobotPlatformMetadata:
        return self._metadata

    def model_xml_path(self) -> Path:
        return Path(self._metadata.model_dir) / self._metadata.model_xml

    def read_model_xml(self) -> str:
        path = self.model_xml_path()
        if not path.exists():
            raise FileNotFoundError(f"AGIBOT X2 MuJoCo model not found: {path}")
        return path.read_text()

    def _root(self) -> ET.Element:
        return ET.fromstring(self.read_model_xml())

    def actuator_names(self) -> tuple[str, ...]:
        root = self._root()
        actuator = root.find("actuator")
        if actuator is None:
            raise ValueError(f"X2 model has no <actuator> section: {self.model_xml_path()}")
        names = []
        for index, child in enumerate(list(actuator)):
            names.append(child.attrib.get("name", f"actuator_{index}"))
        if len(names) != self._expected_actuator_count:
            raise ValueError(
                f"X2 actuator count mismatch for {self.model_xml_path()}: "
                f"expected {self._expected_actuator_count}, found {len(names)}"
            )
        return tuple(names)

    def initial_joint_qpos(self) -> np.ndarray:
        root = self._root()
        actuator_count = len(self.actuator_names())
        keyframe = root.find("keyframe")
        if keyframe is not None:
            for key in keyframe.findall("key"):
                qpos_attr = key.attrib.get("qpos")
                if qpos_attr:
                    qpos = np.fromstring(qpos_attr, sep=" ", dtype=np.float64)
                    if qpos.size >= 7 + actuator_count:
                        return qpos[7:7 + actuator_count].copy()
        return np.zeros(actuator_count, dtype=np.float64)

    def root_body_name(self) -> str:
        root = self._root()
        worldbody = root.find("worldbody")
        if worldbody is None:
            raise ValueError(f"X2 model has no <worldbody>: {self.model_xml_path()}")
        body = worldbody.find("body")
        if body is None:
            raise ValueError(f"X2 model has no root <body>: {self.model_xml_path()}")
        name = body.attrib.get("name")
        if not name:
            raise ValueError(f"X2 root body is unnamed: {self.model_xml_path()}")
        return name

    def camera_spec(self, robot_id: str) -> dict[str, str]:
        return {
            "name": f"{robot_id}_cam",
            "pos": "0.16 0 0.28",
            "xyaxes": "0 -1 0 0 0 1",
            "fovy": "70",
        }

    def make_controller(self, robot_id: str) -> X2PolicyController:
        return X2PolicyController(
            actuator_count=len(self.actuator_names()),
            policy_path=self._controller_path,
            default_qpos=self.initial_joint_qpos(),
        )

    def extract_state(self, model: Any, data: Any, qpos_start: int, sim_time: float) -> RobotState:
        actuator_count = len(self.actuator_names())
        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = data.qpos[qpos_start:qpos_start + 3]
        quat = data.qpos[qpos_start + 3:qpos_start + 7].copy()
        pose[:3, :3] = quat_to_rotation_matrix(quat)
        joint_positions = data.qpos[qpos_start + 7:qpos_start + 7 + actuator_count].copy()
        qvel_start = qpos_start + 6
        joint_velocities = data.qvel[qvel_start:qvel_start + actuator_count].copy()
        base_velocity = data.qvel[qpos_start:qpos_start + 3].copy()
        return self._state_from_arrays(
            base_pose=pose,
            base_velocity=base_velocity,
            joint_positions=joint_positions,
            joint_velocities=joint_velocities,
            orientation_quat=quat,
            sim_time=sim_time,
        )

    def _state_from_arrays(
        self,
        base_pose: np.ndarray,
        base_velocity: np.ndarray,
        joint_positions: np.ndarray,
        joint_velocities: np.ndarray,
        orientation_quat: np.ndarray,
        sim_time: float,
    ) -> RobotState:
        fall_reason = self._fall_reason(base_pose, orientation_quat)
        return RobotState(
            base_pose=np.asarray(base_pose, dtype=np.float64),
            base_velocity=np.asarray(base_velocity, dtype=np.float64),
            joint_positions=np.asarray(joint_positions, dtype=np.float64),
            joint_velocities=np.asarray(joint_velocities, dtype=np.float64),
            orientation_quat=np.asarray(orientation_quat, dtype=np.float64),
            contacts=(),
            sim_time=float(sim_time),
            fallen=fall_reason is not FallReason.NONE,
            fall_reason=fall_reason,
        )

    def _fall_reason(self, base_pose: np.ndarray, quat: np.ndarray) -> FallReason:
        if float(base_pose[2, 3]) < 0.45:
            return FallReason.BASE_HEIGHT
        roll, pitch = self._roll_pitch(quat)
        if abs(roll) > 0.75 or abs(pitch) > 0.75:
            return FallReason.ROLL_PITCH_THRESHOLD
        return FallReason.NONE

    def _roll_pitch(self, quat: np.ndarray) -> tuple[float, float]:
        w, x, y, z = [float(v) for v in quat]
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2.0 * (w * y - z * x)
        pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
        return roll, pitch

    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus:
        if state.fallen:
            runtime_state = RobotRuntimeState.FALLEN
            fall_reason = state.fall_reason
        elif not controller_health.nan_guard_ok:
            runtime_state = RobotRuntimeState.DISABLED
            fall_reason = FallReason.CONTROLLER_INVALID_OUTPUT
        elif last_command.mode == "recover":
            runtime_state = RobotRuntimeState.RECOVERING
            fall_reason = FallReason.NONE
        elif last_command.mode in {"stand", "stop"}:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        elif np.linalg.norm(last_command.linear) > 0.01 or abs(last_command.yaw_rate) > 0.01:
            runtime_state = RobotRuntimeState.WALKING
            fall_reason = FallReason.NONE
        else:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        return RobotRuntimeStatus(
            state=runtime_state,
            fall_reason=fall_reason,
            last_command=last_command,
            controller_health=controller_health,
            collision_count=collision_count,
            near_miss_count=near_miss_count,
        )
```

Modify `src/bridge/platforms/__init__.py`:

```python
"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.platforms.registry import create_platform, list_platforms, register_platform

for _name, _platform in (("go2", Go2Platform), ("agibot_x2", AgibotX2Platform)):
    try:
        register_platform(_name, _platform)
    except ValueError:
        pass

__all__ = [
    "AgibotX2Platform",
    "Go2Platform",
    "create_platform",
    "list_platforms",
    "register_platform",
]
```

- [ ] **Step 4: Run the X2 platform tests**

Run:

```bash
pytest tests/bridge/platforms/test_agibot_x2_platform.py -v
```

Expected: PASS for all five tests.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/platforms/__init__.py src/bridge/platforms/agibot_x2.py tests/bridge/platforms/test_agibot_x2_platform.py
git commit -m "feat: add AGIBOT X2 robot platform"
```

---

### Task 6: Generic collision and near-miss state

**Files:**
- Create: `src/bridge/collision_state.py`
- Test: `tests/bridge/test_collision_state.py`

- [ ] **Step 1: Write failing collision-state tests**

Create `tests/bridge/test_collision_state.py`:

```python
import numpy as np

from src.bridge.collision_state import compute_collision_summaries


def test_separated_robots_have_zero_counts():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([5.0, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"] == {"collision_count": 0, "near_miss_count": 0}
    assert summaries["robot_b"] == {"collision_count": 0, "near_miss_count": 0}


def test_collision_counts_for_both_robots():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([0.4, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"]["collision_count"] == 1
    assert summaries["robot_b"]["collision_count"] == 1
    assert summaries["robot_a"]["near_miss_count"] == 0


def test_near_miss_counts_without_collision():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([0.8, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"]["collision_count"] == 0
    assert summaries["robot_a"]["near_miss_count"] == 1
    assert summaries["robot_b"]["near_miss_count"] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/bridge/test_collision_state.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.bridge.collision_state'`.

- [ ] **Step 3: Add the collision-state helper**

Create `src/bridge/collision_state.py`:

```python
from __future__ import annotations

import numpy as np


def compute_collision_summaries(
    positions: dict[str, np.ndarray],
    footprint_radius: float,
    near_miss_margin: float = 0.25,
) -> dict[str, dict[str, int]]:
    summaries = {
        rid: {"collision_count": 0, "near_miss_count": 0}
        for rid in positions
    }
    ids = list(positions)
    collision_distance = 2.0 * float(footprint_radius)
    near_miss_distance = collision_distance + float(near_miss_margin)

    for i, rid_a in enumerate(ids):
        for rid_b in ids[i + 1:]:
            a = np.asarray(positions[rid_a], dtype=np.float64)[:2]
            b = np.asarray(positions[rid_b], dtype=np.float64)[:2]
            distance = float(np.linalg.norm(a - b))
            if distance < collision_distance:
                summaries[rid_a]["collision_count"] += 1
                summaries[rid_b]["collision_count"] += 1
            elif distance < near_miss_distance:
                summaries[rid_a]["near_miss_count"] += 1
                summaries[rid_b]["near_miss_count"] += 1
    return summaries
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
pytest tests/bridge/test_collision_state.py -v
```

Expected: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add src/bridge/collision_state.py tests/bridge/test_collision_state.py
git commit -m "feat: compute robot collision summaries"
```

---

### Task 7: Generic scene builder and config platform selection

**Files:**
- Modify: `src/bridge/multi_robot_config.py:11-38`
- Modify: `src/bridge/scene_builder.py:46-166`
- Modify: `src/coordination/spawn.py:33-85`
- Test: `tests/bridge/test_multi_bridge.py`

- [ ] **Step 1: Add failing tests for platform config and generic scene XML**

Append to `tests/bridge/test_multi_bridge.py`:

```python
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.scene_builder import build_multi_robot_scene


def test_multi_robot_config_accepts_platform_name_and_config():
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": "models/agibot_x2"},
    )

    assert config.platform == "agibot_x2"
    assert config.platform_config == {"model_dir": "models/agibot_x2"}


@pytest.mark.skipif(not _HAS_MODEL, reason="go2.xml model file not found")
def test_build_multi_robot_scene_uses_platform_camera_and_prefixes():
    platform = Go2Platform()
    xml_str, assets = build_multi_robot_scene(
        platform=platform,
        spawn_positions={"robot_a": (0.0, 0.0, 0.3), "robot_b": (5.0, 0.0, 0.3)},
    )

    assert isinstance(xml_str, str)
    assert isinstance(assets, dict)
    assert "robot_a_base" in xml_str
    assert "robot_b_base" in xml_str
    assert "robot_a_FL_hip" in xml_str
    assert "robot_b_FR_hip" in xml_str
    assert "robot_a_cam" in xml_str
    assert "robot_b_cam" in xml_str
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest tests/bridge/test_multi_bridge.py::test_multi_robot_config_accepts_platform_name_and_config tests/bridge/test_multi_bridge.py::test_build_multi_robot_scene_uses_platform_camera_and_prefixes -v
```

Expected: first test FAILS with `TypeError: MultiRobotConfig.__init__() got an unexpected keyword argument 'platform'`; second test FAILS with `ImportError: cannot import name 'build_multi_robot_scene'`.

- [ ] **Step 3: Update multi-robot config**

Modify `src/bridge/multi_robot_config.py` so the dataclass is:

```python
@dataclass
class MultiRobotConfig:
    """Configuration for a multi-robot MuJoCo scene."""

    robot_ids: tuple[str, ...] = ("robot_a", "robot_b")
    spawn_positions: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "robot_a": (0.0, 0.0, 0.3),
            "robot_b": (5.0, 0.0, 0.3),
        }
    )
    resolution: tuple[int, int] = (320, 240)
    sim_steps_per_frame: int = 5
    model_dir: str = "models/unitree_go2"
    boot_phase_steps: int = 200
    scene: str = "flat"
    step_delay: float = 0.0
    platform: str = "go2"
    platform_config: dict = field(default_factory=dict)
```

- [ ] **Step 4: Add generic scene builder without deleting Go2 wrappers**

Modify `src/bridge/scene_builder.py`:

1. Add this import near the top:

```python
from src.bridge.platforms.base import RobotPlatform
from src.bridge.platforms.go2 import Go2Platform
```

2. Add this function above `build_two_robot_scene()`:

```python
def _collect_assets(model_path: Path) -> dict[str, bytes]:
    assets: dict[str, bytes] = {}
    asset_dir = model_path / "assets"
    if asset_dir.exists():
        for f in asset_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()
    mesh_dir = model_path / "meshes"
    if mesh_dir.exists():
        for f in mesh_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()
    return assets


def build_multi_robot_scene(
    platform: RobotPlatform,
    spawn_positions: dict[str, tuple[float, float, float]],
) -> tuple[str, dict[str, bytes]]:
    model_path = Path(platform.metadata.model_dir)
    robot_root = ET.fromstring(platform.read_model_xml())

    compiler_elem = robot_root.find("compiler")
    option_elem = robot_root.find("option")
    default_elem = robot_root.find("default")
    asset_elem = robot_root.find("asset")
    worldbody_elem = robot_root.find("worldbody")
    actuator_elem = robot_root.find("actuator")
    if worldbody_elem is None or actuator_elem is None:
        raise ValueError(f"Robot XML must contain <worldbody> and <actuator>: {platform.model_xml_path()}")

    robot_body = worldbody_elem.find("body")
    if robot_body is None:
        raise ValueError(f"Robot XML must contain a root <body>: {platform.model_xml_path()}")

    scene = ET.Element("mujoco", model=f"{platform.metadata.name}_multi_robot_scene")

    if compiler_elem is not None:
        comp = copy.deepcopy(compiler_elem)
        meshdir = comp.attrib.get("meshdir")
        if meshdir:
            comp.attrib["meshdir"] = str((model_path / meshdir).resolve())
        texturedir = comp.attrib.get("texturedir")
        if texturedir:
            comp.attrib["texturedir"] = str((model_path / texturedir).resolve())
        scene.append(comp)
    if option_elem is not None:
        scene.append(copy.deepcopy(option_elem))
    if default_elem is not None:
        scene.append(copy.deepcopy(default_elem))

    visual = ET.SubElement(scene, "visual")
    ET.SubElement(visual, "headlight", diffuse="0.6 0.6 0.6", ambient="0.3 0.3 0.3", specular="0 0 0")
    ET.SubElement(visual, "rgba", haze="0.15 0.25 0.35 1")
    ET.SubElement(visual, "global", azimuth="-130", elevation="-20")
    map_elem = ET.SubElement(visual, "map")
    map_elem.set("znear", "0.01")
    map_elem.set("zfar", "100")

    merged_asset = copy.deepcopy(asset_elem) if asset_elem is not None else ET.Element("asset")
    ET.SubElement(merged_asset, "texture", type="skybox", builtin="gradient", rgb1="0.3 0.5 0.7", rgb2="0 0 0", width="512", height="3072")
    ET.SubElement(merged_asset, "texture", type="2d", name="groundplane", builtin="checker", mark="edge", rgb1="0.2 0.3 0.4", rgb2="0.1 0.2 0.3", markrgb="0.8 0.8 0.8", width="300", height="300")
    ET.SubElement(merged_asset, "material", name="groundplane", texture="groundplane", texuniform="true", texrepeat="5 5", reflectance="0.2")
    scene.append(merged_asset)

    wb = ET.SubElement(scene, "worldbody")
    ET.SubElement(wb, "light", pos="0 0 3", dir="0 0 -1", directional="true")
    ET.SubElement(wb, "geom", name="floor", size="100 100 0.05", type="plane", material="groundplane")

    for robot_id, (sx, sy, sz) in spawn_positions.items():
        prefix = f"{robot_id}_"
        body = copy.deepcopy(robot_body)
        _prefix_element(body, prefix)
        body.attrib["pos"] = f"{sx} {sy} {sz}"
        ET.SubElement(body, "camera", **platform.camera_spec(robot_id))
        wb.append(body)

    act_section = ET.SubElement(scene, "actuator")
    for robot_id in spawn_positions:
        prefix = f"{robot_id}_"
        for motor in actuator_elem:
            new_motor = copy.deepcopy(motor)
            for attr in ("name", "joint", "tendon", "site"):
                if attr in new_motor.attrib:
                    new_motor.attrib[attr] = prefix + new_motor.attrib[attr]
            act_section.append(new_motor)

    return ET.tostring(scene, encoding="unicode"), _collect_assets(model_path)
```

3. Replace the body of `build_two_robot_scene()` with this Go2 wrapper:

```python
def build_two_robot_scene(
    model_dir: str,
    spawn_positions: dict[str, tuple[float, float, float]],
) -> str:
    platform = Go2Platform(model_dir=model_dir)
    xml_str, _assets = build_multi_robot_scene(platform, spawn_positions)
    return xml_str
```

- [ ] **Step 5: Run the focused tests to verify they pass**

Run:

```bash
pytest tests/bridge/test_multi_bridge.py::test_multi_robot_config_accepts_platform_name_and_config tests/bridge/test_multi_bridge.py::test_build_multi_robot_scene_uses_platform_camera_and_prefixes -v
```

Expected: PASS for both tests.

- [ ] **Step 6: Update spawn helper for platform spawn heights**

Modify `src/coordination/spawn.py` function signature and z assignment:

```python
def generate_spawn_positions(
    robot_ids: tuple[str, ...],
    scene: str = "office",
    spawn_height: float = 0.3,
) -> dict[str, tuple[float, float, float]]:
```

Change the flat-scene assignment:

```python
positions[rid] = (i * 5.0, 0.0, float(spawn_height))
```

Change the office-scene assignment:

```python
positions[rid] = (pos[0], pos[1], float(spawn_height))
```

- [ ] **Step 7: Run existing bridge tests**

Run:

```bash
pytest tests/bridge/test_multi_bridge.py -v
```

Expected: PASS, with model-dependent XML tests skipped if `models/unitree_go2/go2.xml` is absent.

- [ ] **Step 8: Commit**

```bash
git add src/bridge/multi_robot_config.py src/bridge/scene_builder.py src/coordination/spawn.py tests/bridge/test_multi_bridge.py
git commit -m "feat: build multi-robot scenes through platform metadata"
```

---

### Task 8: Refactor MultiRobotBridge through RobotPlatform

**Files:**
- Modify: `src/bridge/multi_bridge.py:1-502`
- Test: `tests/bridge/test_multi_bridge.py`
- Test: `tests/bridge/test_multi_bridge_platform_selection.py`

- [ ] **Step 1: Write failing bridge platform-selection tests**

Create `tests/bridge/test_multi_bridge_platform_selection.py`:

```python
import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import RobotCommand


def test_bridge_exposes_platform_metadata_without_starting():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    metadata = bridge.platform_metadata

    assert metadata.name == "go2"
    assert metadata.actuator_count == 12


def test_bridge_buffers_generic_robot_command():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_command("robot_a", RobotCommand.velocity([0.4, 0.0], 0.2))

    assert bridge.get_runtime_status("robot_a").last_command.to_wire() == {
        "mode": "velocity",
        "linear": [0.4, 0.0],
        "yaw_rate": 0.2,
        "waypoint": None,
    }


def test_set_velocity_preserves_existing_api():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_velocity("robot_a", np.array([0.1, 0.0]), 0.0)

    assert bridge.get_runtime_status("robot_a").last_command.to_wire()["linear"] == [0.1, 0.0]
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
pytest tests/bridge/test_multi_bridge_platform_selection.py -v
```

Expected: FAIL because `MultiRobotBridge` has no `platform_metadata`, `set_command`, or `get_runtime_status`.

- [ ] **Step 3: Update bridge imports and initialization**

Modify the top of `src/bridge/multi_bridge.py`:

```python
import logging
from typing import Any

import numpy as np

from src.bridge.collision_state import compute_collision_summaries
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms import create_platform
from src.bridge.platforms.types import RobotCommand, RobotRuntimeStatus
from src.bridge.scene_builder import build_multi_robot_scene, build_two_robot_office_scene
from src.bridge.sensor_types import SensorFrame, quat_to_rotation_matrix
```

Remove imports of `STANDING_QPOS`, `TrotGaitController`, and `GaitParams` from `multi_bridge.py`.

Inside `__init__`, replace platform-specific fields with:

```python
self._platform = create_platform(
    self._config.platform,
    **({"model_dir": self._config.model_dir} if self._config.platform == "go2" else {}),
    **self._config.platform_config,
)
self._qpos_starts: dict[str, int] = {}
self._ctrl_indices: dict[str, list[int]] = {}
self._cam_ids: dict[str, int] = {}
self._commands: dict[str, RobotCommand] = {
    rid: RobotCommand.stand() for rid in self._config.robot_ids
}
self._controllers = {
    rid: self._platform.make_controller(rid) for rid in self._config.robot_ids
}
self._runtime_status: dict[str, RobotRuntimeStatus] = {}
self._collision_summaries: dict[str, dict[str, int]] = {
    rid: {"collision_count": 0, "near_miss_count": 0}
    for rid in self._config.robot_ids
}
```

Keep `_renderers`, `_overview_renderer`, `_last_frames`, `_trace_positions`, and `_trace_colors`.

- [ ] **Step 4: Update scene loading in `start()`**

In `start()`, replace the XML generation block with:

```python
if self._config.scene == "office" and self._config.platform == "go2":
    xml_str, assets = build_two_robot_office_scene(
        self._platform.metadata.model_dir,
        self._config.spawn_positions,
    )
    self._model = mujoco.MjModel.from_xml_string(xml_str, assets)
else:
    xml_str, assets = build_multi_robot_scene(
        self._platform,
        self._config.spawn_positions,
    )
    self._model = mujoco.MjModel.from_xml_string(xml_str, assets)
```

Replace actuator discovery loop with:

```python
for act_name in self._platform.actuator_names():
    full_name = f"{robot_id}_{act_name}"
    act_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_ACTUATOR, full_name)
    if act_id < 0:
        raise RuntimeError(f"Actuator '{full_name}' not found in model")
    ctrl_ids.append(act_id)
self._ctrl_indices[robot_id] = ctrl_ids
```

Replace initial standing pose/control assignment with:

```python
initial_qpos = self._platform.initial_joint_qpos()
for i, robot_id in enumerate(self._config.robot_ids):
    qstart = self._qpos_starts[robot_id]
    yaw = (2 * math.pi * i) / n_robots
    self._data.qpos[qstart + 3] = math.cos(yaw / 2)
    self._data.qpos[qstart + 4] = 0.0
    self._data.qpos[qstart + 5] = 0.0
    self._data.qpos[qstart + 6] = math.sin(yaw / 2)
    self._data.qpos[qstart + 7:qstart + 7 + len(initial_qpos)] = initial_qpos
    state = self._platform.extract_state(self._model, self._data, qstart, sim_time=0.0)
    ctrl = self._controllers[robot_id].compute(RobotCommand.stand(), state, self._dt or 0.02)
    for ctrl_i, act_id in enumerate(self._ctrl_indices[robot_id]):
        self._data.ctrl[act_id] = ctrl[ctrl_i]
    self._runtime_status[robot_id] = self._platform.runtime_status(
        robot_id,
        state,
        RobotCommand.stand(),
        self._controllers[robot_id].health(),
    )
```

- [ ] **Step 5: Add generic command/status APIs**

Add these public methods below `set_velocity()`:

```python
def set_command(self, robot_id: str, command: RobotCommand) -> None:
    if robot_id not in self._commands:
        raise KeyError(f"Unknown robot_id: {robot_id}")
    self._commands[robot_id] = command

def stop_robot(self, robot_id: str) -> None:
    self.set_command(robot_id, RobotCommand.stop())

def recover_robot(self, robot_id: str) -> None:
    self._controllers[robot_id].reset()
    self.set_command(robot_id, RobotCommand.recover())

def get_runtime_status(self, robot_id: str) -> RobotRuntimeStatus:
    if robot_id in self._runtime_status:
        return self._runtime_status[robot_id]
    return self._platform.runtime_status(
        robot_id,
        self._platform.extract_state(None, None, 0, 0.0),
        self._commands[robot_id],
        self._controllers[robot_id].health(),
    )

@property
def platform_metadata(self):
    return self._platform.metadata

@property
def runtime_statuses(self) -> dict[str, RobotRuntimeStatus]:
    return dict(self._runtime_status)
```

Change `set_velocity()` body to:

```python
self.set_command(robot_id, RobotCommand.velocity(linear, angular))
```

- [ ] **Step 6: Update control application in `step()`**

Replace `_velocity_to_ctrl()` calls in `step()` with:

```python
for robot_id in self._config.robot_ids:
    status = self.get_runtime_status(robot_id)
    command = RobotCommand.stop() if status.disabled else self._commands[robot_id]
    state = self._platform.extract_state(
        self._model,
        self._data,
        self._qpos_starts[robot_id],
        self._step_count * self._dt,
    )
    ctrl = self._controllers[robot_id].compute(command, state, self._dt)
    if ctrl.shape != (len(self._ctrl_indices[robot_id]),):
        raise RuntimeError(
            f"Controller for {robot_id} returned {ctrl.shape}, expected {(len(self._ctrl_indices[robot_id]),)}"
        )
    for i, act_id in enumerate(self._ctrl_indices[robot_id]):
        self._data.ctrl[act_id] = ctrl[i]
```

After trajectory recording and before frame capture, add:

```python
positions = {
    rid: self._data.qpos[self._qpos_starts[rid]:self._qpos_starts[rid] + 3].copy()
    for rid in self._config.robot_ids
}
self._collision_summaries = compute_collision_summaries(
    positions,
    footprint_radius=self._platform.metadata.footprint_radius,
)
for rid in self._config.robot_ids:
    state = self._platform.extract_state(
        self._model,
        self._data,
        self._qpos_starts[rid],
        self._step_count * self._dt,
    )
    summary = self._collision_summaries[rid]
    status = self._platform.runtime_status(
        rid,
        state,
        self._commands[rid],
        self._controllers[rid].health(),
        collision_count=summary["collision_count"],
        near_miss_count=summary["near_miss_count"],
    )
    self._runtime_status[rid] = status
    if status.disabled:
        self._commands[rid] = RobotCommand.stop()
```

Leave `_velocity_to_ctrl()` removed from the file after all references are gone.

- [ ] **Step 7: Add last-frame alias used by restart warmup**

Add below `get_frame()`:

```python
def get_last_frame(self, robot_id: str) -> SensorFrame:
    return self.get_frame(robot_id)
```

- [ ] **Step 8: Run platform-selection tests**

Run:

```bash
pytest tests/bridge/test_multi_bridge_platform_selection.py -v
```

Expected: PASS for all three tests.

- [ ] **Step 9: Run existing multi-bridge tests**

Run:

```bash
pytest tests/bridge/test_multi_bridge.py -v
```

Expected: PASS, preserving Go2 behavior and existing XML test expectations.

- [ ] **Step 10: Commit**

```bash
git add src/bridge/multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py
git commit -m "refactor: route multi-robot bridge through platforms"
```

---

### Task 9: Coordinator generic commands and disabled-robot isolation

**Files:**
- Modify: `src/coordination/coordinator.py:46-80, 359-417, 477-589, 706-860`
- Test: `tests/coordination/test_coordinator.py`

- [ ] **Step 1: Add failing coordinator tests**

Append to `tests/coordination/test_coordinator.py`:

```python
class TestCoordinatorPlatformRuntimeState:
    def test_command_handler_forwards_velocity_command_to_bridge(self):
        from src.coordination.coordinator import Coordinator
        from src.bridge.multi_robot_config import MultiRobotConfig

        config = MultiRobotConfig(boot_phase_steps=0)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a",)
        robots = {"robot_a": MagicMock()}
        coordinator = Coordinator(mock_bridge, robots, config)

        coordinator.handle_command({
            "action": "velocity",
            "robot_id": "robot_a",
            "linear": [0.2, 0.0],
            "yaw_rate": 0.1,
        })

        args = mock_bridge.set_command.call_args[0]
        assert args[0] == "robot_a"
        assert args[1].to_wire() == {
            "mode": "velocity",
            "linear": [0.2, 0.0],
            "yaw_rate": 0.1,
            "waypoint": None,
        }

    def test_disabled_robot_gets_stop_command_in_run_loop(self):
        from src.coordination.coordinator import Coordinator
        from src.coordination.robot_instance import RobotInstance
        from src.bridge.multi_robot_config import MultiRobotConfig
        from src.bridge.platforms.types import RobotRuntimeState, RobotRuntimeStatus

        config = MultiRobotConfig(boot_phase_steps=999)
        mock_bridge = MagicMock()
        mock_bridge.robot_ids = ("robot_a",)
        frames = {"robot_a": _make_sensor_frame([0, 0, 0.3])}
        mock_bridge.start.return_value = frames
        mock_bridge.step.return_value = frames
        mock_bridge.get_runtime_status.return_value = RobotRuntimeStatus(state=RobotRuntimeState.DISABLED)

        robot = MagicMock(spec=RobotInstance)
        robot.robot_id = "robot_a"
        robot.slam = _MockSLAM()
        robot.octomap = _MockOctoMap()
        robot.spawn_transform = np.eye(4)
        robot.publisher = MagicMock()
        robot.exploration = MagicMock()
        robot.exploration.step_once.return_value = (
            np.array([1.0, 0.0]),
            0.2,
            StepMetrics(frontiers=5, coverage=0.0, terminated=False, voxels=100, rescan_triggered=False),
        )

        coordinator = Coordinator(mock_bridge, {"robot_a": robot}, config)

        with patch.object(coordinator, "_setup_subscriptions"), \
             patch.object(coordinator, "_teardown_subscriptions"), \
             patch.object(coordinator, "_merge_occupancy_maps"):
            coordinator.run(max_steps=1)

        mock_bridge.stop_robot.assert_called_once_with("robot_a")
        robot.exploration.step_once.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
pytest tests/coordination/test_coordinator.py::TestCoordinatorPlatformRuntimeState -v
```

Expected: first test FAILS because `velocity` is not handled; second test FAILS because disabled robots still call `exploration.step_once`.

- [ ] **Step 3: Add runtime fields to `RobotVizData`**

Modify `src/coordination/coordinator.py` `RobotVizData` dataclass:

```python
platform: dict | None = None
runtime_status: dict | None = None
```

Keep `tracking_status` and `body_yaw` fields after these new fields so existing positional construction remains explicit by keyword.

- [ ] **Step 4: Handle generic velocity/stop/recover commands**

Add this import near existing imports:

```python
from src.bridge.platforms.types import RobotCommand
```

In `_command_handler()`, add these branches before `send_to`:

```python
elif action == "velocity":
    robot_id = command.get("robot_id")
    if robot_id and robot_id in self._robots and hasattr(self._bridge, "set_command"):
        linear = command.get("linear", [0.0, 0.0])
        yaw_rate = command.get("yaw_rate", 0.0)
        self._bridge.set_command(robot_id, RobotCommand.velocity(linear, yaw_rate))
        logger.info("Command received: velocity %s linear=%s yaw=%.3f", robot_id, linear, yaw_rate)
elif action == "stand":
    robot_id = command.get("robot_id")
    if robot_id and robot_id in self._robots and hasattr(self._bridge, "set_command"):
        self._bridge.set_command(robot_id, RobotCommand.stand())
        logger.info("Command received: stand %s", robot_id)
elif action == "stop_robot":
    robot_id = command.get("robot_id")
    if robot_id and robot_id in self._robots and hasattr(self._bridge, "stop_robot"):
        self._bridge.stop_robot(robot_id)
        logger.info("Command received: stop_robot %s", robot_id)
elif action == "recover_robot":
    robot_id = command.get("robot_id")
    if robot_id and robot_id in self._robots and hasattr(self._bridge, "recover_robot"):
        self._bridge.recover_robot(robot_id)
        logger.info("Command received: recover_robot %s", robot_id)
```

- [ ] **Step 5: Skip disabled robots in the run loop**

Inside `run()`, just after `robot = self._robots[rid]` and `frame = frames[rid]`, add:

```python
if hasattr(self._bridge, "get_runtime_status"):
    runtime_status = self._bridge.get_runtime_status(rid)
    if getattr(runtime_status, "disabled", False):
        if hasattr(self._bridge, "stop_robot"):
            self._bridge.stop_robot(rid)
        continue
```

This preserves the simulation loop: disabled robot gets stopped, other robots continue.

- [ ] **Step 6: Include platform and runtime status in viz data**

Inside `_send_viz_update()`, before constructing `RobotVizData`, add:

```python
platform_payload = None
if hasattr(self._bridge, "platform_metadata"):
    platform_payload = self._bridge.platform_metadata.to_wire()
runtime_payload = None
if hasattr(self._bridge, "get_runtime_status"):
    runtime_payload = self._bridge.get_runtime_status(rid).to_wire()
```

Add these keyword arguments to `RobotVizData(...)`:

```python
platform=platform_payload,
runtime_status=runtime_payload,
```

- [ ] **Step 7: Run the coordinator tests**

Run:

```bash
pytest tests/coordination/test_coordinator.py::TestCoordinatorPlatformRuntimeState -v
```

Expected: PASS for both tests.

- [ ] **Step 8: Run full coordinator tests**

Run:

```bash
pytest tests/coordination/test_coordinator.py -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/coordination/coordinator.py tests/coordination/test_coordinator.py
git commit -m "feat: isolate disabled robots in coordinator"
```

---

### Task 10: Backend platform metadata and runtime status stream

**Files:**
- Modify: `backend/web/server.py:27-96, 211-239`
- Modify: `backend/web/streaming_viz.py:198-225, 489-552`
- Test: `tests/web/test_web_server.py`
- Test: `tests/web/test_platform_metadata_stream.py`

- [ ] **Step 1: Add failing WebSocket handshake test**

Append to `tests/web/test_web_server.py`:

```python
    def test_ws_connect_receives_platform_metadata_when_configured(self):
        platform_metadata = {
            "robot_a": {"name": "agibot_x2", "display_name": "AGIBOT X2 Ultra"},
            "robot_b": {"name": "agibot_x2", "display_name": "AGIBOT X2 Ultra"},
        }
        app, viz = create_app(["robot_a", "robot_b"], platform_metadata=platform_metadata)
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "robot_list"
            assert data["payload"]["robots"] == ["robot_a", "robot_b"]
            assert data["payload"]["platforms"] == platform_metadata
```

- [ ] **Step 2: Add failing streaming status test**

Create `tests/web/test_platform_metadata_stream.py`:

```python
from unittest.mock import MagicMock, patch

import numpy as np

from backend.web.streaming_viz import WebStreamingViz
from backend.web.message_types import STATS


def test_stats_payload_contains_platform_runtime_state():
    viz = WebStreamingViz(MagicMock(), ["robot_a"])
    pose = np.eye(4)
    frame = MagicMock()
    frame.rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    frame.depth = None
    robot_data = {
        "robot_a": {
            "frame": frame,
            "local_voxels": np.zeros((2, 3)),
            "pose": pose,
            "trajectory": [pose],
            "coverage_pct": 12.5,
            "platform": {"name": "agibot_x2", "display_name": "AGIBOT X2 Ultra"},
            "runtime_status": {
                "state": "walking",
                "fall_reason": "none",
                "disabled": False,
                "controller_health": {"policy_loaded": True},
                "collision_count": 0,
                "near_miss_count": 1,
            },
        }
    }

    with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
        viz.update(np.zeros((0, 3)), robot_data)

    stats = [m for m in viz.drain_pending_messages() if isinstance(m, dict) and m.get("type") == STATS][0]

    assert stats["payload"]["robots"]["robot_a"]["platform"]["name"] == "agibot_x2"
    assert stats["payload"]["robots"]["robot_a"]["runtime_status"]["state"] == "walking"
    assert stats["payload"]["robots"]["robot_a"]["runtime_status"]["near_miss_count"] == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
pytest tests/web/test_web_server.py::TestWebSocketServer::test_ws_connect_receives_platform_metadata_when_configured tests/web/test_platform_metadata_stream.py -v
```

Expected: first test FAILS with unexpected `platform_metadata` argument; second test FAILS because `platform` and `runtime_status` are not emitted in stats robots.

- [ ] **Step 4: Add platform metadata to FastAPI app state**

Modify `backend/web/server.py` `create_app()` signature:

```python
def create_app(
    robot_ids: list[str],
    command_cb: Callable[[dict[str, Any]], None] | None = None,
    slam_reset_cb: Callable[[], None] | None = None,
    mcp_endpoint: Callable | None = None,
    cloud_config_fns: dict[str, Callable] | None = None,
    platform_metadata: dict[str, dict] | None = None,
) -> tuple[FastAPI, WebStreamingViz]:
```

Inside `create_app()`, after `app.state.robot_ids = robot_ids`, add:

```python
app.state.platform_metadata = platform_metadata or {}
```

In `websocket_endpoint()`, change the robot-list send to:

```python
await websocket.send_json({
    "type": "robot_list",
    "payload": {
        "robots": state.robot_ids,
        "platforms": getattr(state, "platform_metadata", {}),
    },
})
```

- [ ] **Step 5: Emit platform/runtime fields in stats**

Modify `backend/web/streaming_viz.py` `_update_stats()` robots loop:

```python
for rid, data in robot_data.items():
    robots[rid] = {
        "coverage_pct": data.get("coverage_pct", 0.0),
        "voxel_count": len(data.get("local_voxels", [])),
        "action": data.get("runtime_status", {}).get("state", "exploring") if data.get("runtime_status") else "exploring",
        "platform": data.get("platform"),
        "runtime_status": data.get("runtime_status"),
    }
```

- [ ] **Step 6: Run backend tests**

Run:

```bash
pytest tests/web/test_web_server.py::TestWebSocketServer::test_ws_connect_receives_platform_metadata_when_configured tests/web/test_platform_metadata_stream.py -v
```

Expected: PASS for both tests.

- [ ] **Step 7: Run existing web tests**

Run:

```bash
pytest tests/web/test_web_server.py tests/web/test_streaming_viz.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/web/server.py backend/web/streaming_viz.py tests/web/test_web_server.py tests/web/test_platform_metadata_stream.py
git commit -m "feat: stream robot platform runtime state"
```

---

### Task 11: Frontend store and message contracts

**Files:**
- Modify: `frontend/src/utils/messageTypes.ts:1-75`
- Modify: `frontend/src/stores/robotStore.ts:7-64, 75-141`
- Modify: `frontend/src/hooks/useWebSocket.ts:81-116`
- Test: `frontend/src/stores/__tests__/robotStore.platformState.test.ts`

- [ ] **Step 1: Write failing frontend store tests**

Create `frontend/src/stores/__tests__/robotStore.platformState.test.ts`:

```typescript
import { beforeEach, describe, expect, it } from 'vitest';
import { useRobotStore } from '../robotStore';

function resetStore(): void {
  useRobotStore.setState({
    robots: new Map(),
    pointCloudPositions: [],
    pointCloudColors: [],
    colorMode: 'robot_tint',
    totalCoverage: 0,
    mergeCount: 0,
    elapsed: 0,
  });
}

describe('robotStore platform state', () => {
  beforeEach(() => resetStore());

  it('stores platform metadata from robot list', () => {
    useRobotStore.getState().setRobotList(['robot_a'], {
      robot_a: {
        name: 'agibot_x2',
        display_name: 'AGIBOT X2 Ultra',
        footprint_radius: 0.33,
        dimensions: [0.46, 0.21, 1.31],
        marker_asset: null,
      },
    });

    const robot = useRobotStore.getState().robots.get('robot_a')!;
    expect(robot.platform).toBe('agibot_x2');
    expect(robot.platformMetadata?.display_name).toBe('AGIBOT X2 Ultra');
    expect(robot.platformMetadata?.footprint_radius).toBe(0.33);
  });

  it('updates runtime status from stats payload', () => {
    useRobotStore.getState().setRobotList(['robot_a']);

    useRobotStore.getState().updateStats({
      total_coverage: 10,
      merge_count: 1,
      elapsed: 2,
      robots: {
        robot_a: {
          coverage_pct: 10,
          voxel_count: 20,
          action: 'fallen',
          platform: { name: 'agibot_x2', display_name: 'AGIBOT X2 Ultra' },
          runtime_status: {
            state: 'fallen',
            fall_reason: 'base_height',
            disabled: true,
            controller_health: { policy_loaded: false, message: 'ok' },
            collision_count: 1,
            near_miss_count: 2,
          },
        },
      },
    });

    const robot = useRobotStore.getState().robots.get('robot_a')!;
    expect(robot.runtimeState).toBe('fallen');
    expect(robot.fallReason).toBe('base_height');
    expect(robot.disabled).toBe(true);
    expect(robot.controllerHealth?.policy_loaded).toBe(false);
    expect(robot.collisionCount).toBe(1);
    expect(robot.nearMissCount).toBe(2);
  });
});
```

- [ ] **Step 2: Run frontend store test to verify it fails**

Run:

```bash
cd frontend && npm test -- robotStore.platformState.test.ts
```

Expected: FAIL because `setRobotList` accepts only one argument and `RobotInfo` lacks platform/runtime fields.

- [ ] **Step 3: Extend frontend message types**

Modify `frontend/src/utils/messageTypes.ts`:

```typescript
export interface PlatformMetadata {
  name: string;
  display_name: string;
  model_dir?: string;
  model_xml?: string;
  actuator_count?: number;
  command_modes?: string[];
  footprint_radius?: number;
  dimensions?: [number, number, number];
  max_linear_speed?: number;
  max_yaw_rate?: number;
  marker_asset?: string | null;
  spawn_height?: number;
}

export interface RobotRuntimeStatusPayload {
  state: 'standing' | 'walking' | 'fallen' | 'recovering' | 'disabled';
  fall_reason: string;
  disabled: boolean;
  last_command?: {
    mode: string;
    linear: number[];
    yaw_rate: number;
    waypoint: number[] | null;
  };
  command_tracking?: Record<string, unknown>;
  controller_health?: Record<string, unknown>;
  collision_count?: number;
  near_miss_count?: number;
}
```

Change `RobotListPayload` to:

```typescript
export interface RobotListPayload {
  robots: string[];
  platforms?: Record<string, PlatformMetadata>;
}
```

Change the `StatsPayload.robots` entry type to:

```typescript
{
  coverage_pct: number;
  voxel_count: number;
  action: string;
  platform?: PlatformMetadata | null;
  runtime_status?: RobotRuntimeStatusPayload | null;
}
```

- [ ] **Step 4: Extend robot store state**

Modify `frontend/src/stores/robotStore.ts` imports:

```typescript
import type {
  Detection3DEnvelope,
  Detection3DItem,
  PlatformMetadata,
  RobotRuntimeStatusPayload,
} from '../utils/messageTypes';
```

Add fields to `RobotInfo`:

```typescript
platform: string;
platformMetadata: PlatformMetadata | null;
runtimeState: string;
fallReason: string;
disabled: boolean;
controllerHealth: Record<string, unknown> | null;
collisionCount: number;
nearMissCount: number;
```

Change `setRobotList` type:

```typescript
setRobotList: (ids: string[], platforms?: Record<string, PlatformMetadata>) => void;
```

Change `updateStats` robot entry type to include:

```typescript
platform?: PlatformMetadata | null;
runtime_status?: RobotRuntimeStatusPayload | null;
```

Replace `setRobotList` implementation with:

```typescript
setRobotList: (ids: string[], platforms: Record<string, PlatformMetadata> = {}) => {
  const robots = new Map<string, RobotInfo>();
  ids.forEach((id, index) => {
    const existing = get().robots.get(id);
    const platformMetadata = platforms[id] ?? existing?.platformMetadata ?? null;
    robots.set(id, {
      id,
      colorIndex: index,
      position: existing?.position ?? [0, 0, 0],
      rotation: existing?.rotation ?? [1, 0, 0, 0, 1, 0, 0, 0, 1],
      coveragePct: existing?.coveragePct ?? 0,
      voxelCount: existing?.voxelCount ?? 0,
      action: existing?.action ?? 'idle',
      cameraUrl: existing?.cameraUrl ?? null,
      depthUrl: existing?.depthUrl ?? null,
      trajectory: existing?.trajectory ?? [],
      trajectoryAlphas: existing?.trajectoryAlphas ?? [],
      detections_3d: existing?.detections_3d ?? null,
      sceneDescription: existing?.sceneDescription ?? null,
      sceneObjects: existing?.sceneObjects ?? [],
      trackingStatus: existing?.trackingStatus ?? 'ok',
      bodyYaw: existing?.bodyYaw ?? 0,
      platform: platformMetadata?.name ?? existing?.platform ?? 'go2',
      platformMetadata,
      runtimeState: existing?.runtimeState ?? 'standing',
      fallReason: existing?.fallReason ?? 'none',
      disabled: existing?.disabled ?? false,
      controllerHealth: existing?.controllerHealth ?? null,
      collisionCount: existing?.collisionCount ?? 0,
      nearMissCount: existing?.nearMissCount ?? 0,
    });
  });
  set({ robots });
},
```

In `updateStats`, replace the per-robot `robots.set()` with:

```typescript
const runtime = robotStats.runtime_status ?? null;
const platformMetadata = robotStats.platform ?? robot.platformMetadata;
robots.set(robotId, {
  ...robot,
  coveragePct: robotStats.coverage_pct,
  voxelCount: robotStats.voxel_count,
  action: runtime?.state ?? robotStats.action,
  platform: platformMetadata?.name ?? robot.platform,
  platformMetadata,
  runtimeState: runtime?.state ?? robot.runtimeState,
  fallReason: runtime?.fall_reason ?? robot.fallReason,
  disabled: runtime?.disabled ?? robot.disabled,
  controllerHealth: runtime?.controller_health ?? robot.controllerHealth,
  collisionCount: runtime?.collision_count ?? robot.collisionCount,
  nearMissCount: runtime?.near_miss_count ?? robot.nearMissCount,
});
```

- [ ] **Step 5: Update WebSocket robot-list handling**

Modify `frontend/src/hooks/useWebSocket.ts` robot-list case:

```typescript
store.setRobotList(payload.robots, payload.platforms ?? {});
```

- [ ] **Step 6: Run frontend store tests**

Run:

```bash
cd frontend && npm test -- robotStore.platformState.test.ts
```

Expected: PASS.

- [ ] **Step 7: Run frontend type/build check**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS with Vite build output and no TypeScript errors.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/utils/messageTypes.ts frontend/src/stores/robotStore.ts frontend/src/hooks/useWebSocket.ts frontend/src/stores/__tests__/robotStore.platformState.test.ts
git commit -m "feat: store robot platform runtime state in UI"
```

---

### Task 12: RobotCard runtime-state UI

**Files:**
- Modify: `frontend/src/components/RobotCard.tsx:20-121`
- Test: `frontend/src/components/__tests__/RobotCard.platformState.test.tsx`

- [ ] **Step 1: Write failing RobotCard test**

Create `frontend/src/components/__tests__/RobotCard.platformState.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import RobotCard from '../RobotCard';
import type { RobotInfo } from '../../stores/robotStore';

function robot(overrides: Partial<RobotInfo> = {}): RobotInfo {
  return {
    id: 'robot_a',
    colorIndex: 0,
    position: [0, 0, 0],
    rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    coveragePct: 10,
    voxelCount: 20,
    action: 'fallen',
    cameraUrl: null,
    depthUrl: null,
    trajectory: [],
    trajectoryAlphas: [],
    detections_3d: null,
    sceneDescription: null,
    sceneObjects: [],
    trackingStatus: 'ok',
    bodyYaw: 0,
    platform: 'agibot_x2',
    platformMetadata: { name: 'agibot_x2', display_name: 'AGIBOT X2 Ultra' },
    runtimeState: 'fallen',
    fallReason: 'base_height',
    disabled: true,
    controllerHealth: { policy_loaded: false, message: 'ok' },
    collisionCount: 1,
    nearMissCount: 2,
    ...overrides,
  };
}

describe('RobotCard platform runtime state', () => {
  it('shows platform, runtime, fall, controller, and collision state', () => {
    render(<RobotCard robot={robot()} />);

    expect(screen.getByText('AGIBOT X2 Ultra')).toBeTruthy();
    expect(screen.getByText('fallen')).toBeTruthy();
    expect(screen.getByText('Fall: base_height')).toBeTruthy();
    expect(screen.getByText('Controller: no policy')).toBeTruthy();
    expect(screen.getByText('Collisions: 1')).toBeTruthy();
    expect(screen.getByText('Near misses: 2')).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd frontend && npm test -- RobotCard.platformState.test.tsx
```

Expected: FAIL because the new labels are not rendered.

- [ ] **Step 3: Update RobotCard display**

Modify `frontend/src/components/RobotCard.tsx` inside the card after the title/action row and before coverage:

```tsx
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginTop: '6px',
        fontSize: '11px', color: '#9ca3af',
      }}>
        <span>{robot.platformMetadata?.display_name ?? robot.platform}</span>
        <span style={{
          color: robot.disabled ? '#ff6b6b' : '#8fd18f',
          textTransform: 'capitalize',
          fontWeight: 600,
        }}>
          {robot.runtimeState}
        </span>
      </div>
      {robot.fallReason !== 'none' && (
        <div style={{ marginTop: '4px', fontSize: '11px', color: '#ffb86b' }}>
          Fall: {robot.fallReason}
        </div>
      )}
      <div style={{
        display: 'flex', justifyContent: 'space-between', marginTop: '4px',
        fontSize: '11px', color: '#aaa',
      }}>
        <span>
          Controller: {robot.controllerHealth?.policy_loaded === false ? 'no policy' : 'ok'}
        </span>
        <span>Near misses: {robot.nearMissCount}</span>
      </div>
      <div style={{ marginTop: '4px', fontSize: '11px', color: robot.collisionCount > 0 ? '#ff6b6b' : '#777' }}>
        Collisions: {robot.collisionCount}
      </div>
```

- [ ] **Step 4: Run RobotCard test**

Run:

```bash
cd frontend && npm test -- RobotCard.platformState.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Run frontend test/build checks**

Run:

```bash
cd frontend && npm test -- RobotCard.platformState.test.tsx robotStore.platformState.test.ts && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/RobotCard.tsx frontend/src/components/__tests__/RobotCard.platformState.test.tsx
git commit -m "feat: show robot runtime state in cards"
```

---

### Task 13: Platform-aware robot markers

**Files:**
- Modify: `frontend/src/components/RobotMarker.ts:1-200`
- Modify: `frontend/src/components/SceneViewer.tsx:135-139`
- Test: `frontend/src/components/__tests__/RobotMarker.platformMetadata.test.ts`

- [ ] **Step 1: Write failing marker test**

Create `frontend/src/components/__tests__/RobotMarker.platformMetadata.test.ts`:

```typescript
import * as THREE from 'three';
import { describe, expect, it } from 'vitest';
import { RobotMarkerManager } from '../RobotMarker';


describe('RobotMarkerManager platform metadata', () => {
  it('creates humanoid fallback marker scaled from platform dimensions', () => {
    const scene = new THREE.Group();
    const manager = new RobotMarkerManager(scene);

    manager.updateRobot(
      'robot_a',
      [1, 2, 0.85],
      0,
      undefined,
      'ok',
      0,
      {
        name: 'agibot_x2',
        display_name: 'AGIBOT X2 Ultra',
        footprint_radius: 0.33,
        dimensions: [0.46, 0.21, 1.31],
        marker_asset: null,
      },
    );

    const marker = scene.getObjectByName('robot-marker-robot_a')!;
    expect(marker).toBeTruthy();
    expect(marker.position.x).toBe(1);
    expect(marker.position.y).toBe(2);
    expect(marker.position.z).toBe(0.85);
    expect(marker.scale.z).toBeGreaterThan(1);

    manager.dispose();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd frontend && npm test -- RobotMarker.platformMetadata.test.ts
```

Expected: FAIL because `updateRobot` does not accept platform metadata and fallback marker is always a sphere.

- [ ] **Step 3: Update RobotMarkerManager signature and fallback creation**

Modify `frontend/src/components/RobotMarker.ts` import:

```typescript
import type { PlatformMetadata } from '../utils/messageTypes';
```

Change `pendingUpdates` type:

```typescript
private pendingUpdates: Map<string, { position: [number, number, number]; colorIndex: number; platformMetadata?: PlatformMetadata | null }> = new Map();
```

Replace `createSphereMarker()` with:

```typescript
  private createFallbackMarker(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
    platformMetadata?: PlatformMetadata | null,
  ): void {
    const color = new THREE.Color(OKABE_ITO[colorIndex % 8]);
    const material = new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.3,
    });
    const dims = platformMetadata?.dimensions;
    const radius = platformMetadata?.footprint_radius ?? 0.15;
    const height = dims?.[2] ?? radius * 2;
    const geometry = platformMetadata?.name === 'agibot_x2'
      ? new THREE.CapsuleGeometry(radius * 0.45, Math.max(0.1, height - radius), 8, 16)
      : this.fallbackGeometry;
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = `robot-marker-${robotId}`;
    mesh.position.set(position[0], position[1], position[2]);
    if (platformMetadata?.name === 'agibot_x2') {
      mesh.scale.z = Math.max(1, height);
    }
    this.scene.add(mesh);
    this.markers.set(robotId, mesh);
  }
```

Change all calls from `createSphereMarker(...)` to `createFallbackMarker(...)` and pass `update.platformMetadata` when processing pending updates.

Change `updateRobot()` signature:

```typescript
  updateRobot(
    robotId: string,
    position: [number, number, number],
    colorIndex: number,
    rotation?: number[],
    trackingStatus?: string,
    bodyYaw?: number,
    platformMetadata?: PlatformMetadata | null,
  ): void {
```

Change pending update assignment:

```typescript
this.pendingUpdates.set(robotId, { position, colorIndex, platformMetadata });
```

Change fallback creation at the end:

```typescript
this.createFallbackMarker(robotId, position, colorIndex, platformMetadata);
```

- [ ] **Step 4: Pass platform metadata from SceneViewer**

Modify `frontend/src/components/SceneViewer.tsx` marker update call:

```tsx
robotMarkerManager.updateRobot(
  id,
  robot.position,
  robot.colorIndex,
  robot.rotation,
  robot.trackingStatus,
  robot.bodyYaw,
  robot.platformMetadata,
);
```

- [ ] **Step 5: Run marker test and frontend build**

Run:

```bash
cd frontend && npm test -- RobotMarker.platformMetadata.test.ts && npm run build
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/RobotMarker.ts frontend/src/components/SceneViewer.tsx frontend/src/components/__tests__/RobotMarker.platformMetadata.test.ts
git commit -m "feat: render platform-aware robot markers"
```

---

### Task 14: CLI/platform wiring and restart preservation

**Files:**
- Modify: `src/main.py:69-157, 241-277, 322-390, 466-478`
- Test: `tests/test_main_platform_args.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_main_platform_args.py`:

```python
from unittest.mock import patch

from src.main import parse_args


def test_parse_args_accepts_platform_agibot_x2():
    with patch("sys.argv", ["argus", "--platform", "agibot_x2"]):
        args = parse_args()

    assert args.platform == "agibot_x2"


def test_parse_args_defaults_to_go2():
    with patch("sys.argv", ["argus"]):
        args = parse_args()

    assert args.platform == "go2"
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
pytest tests/test_main_platform_args.py -v
```

Expected: FAIL because `args.platform` does not exist.

- [ ] **Step 3: Add CLI platform argument**

In `src/main.py` `parse_args()`, after `--num-robots`, add:

```python
parser.add_argument(
    "--platform",
    choices=["go2", "agibot_x2"],
    default="go2",
    help="Robot platform for multi/web simulation (default: go2)",
)
parser.add_argument(
    "--x2-model-dir",
    default="models/agibot_x2",
    help="Directory containing AGIBOT X2 MuJoCo XML/assets (default: models/agibot_x2)",
)
parser.add_argument(
    "--x2-controller",
    default=None,
    help="Path to AGIBOT X2 walking-controller policy NPZ for the first MuJoCo adapter",
)
```

- [ ] **Step 4: Add helper for platform config creation**

In `src/main.py`, above `run_multi_mode()`, add:

```python
def _platform_config_from_args(args: argparse.Namespace) -> dict:
    if args.platform == "agibot_x2":
        cfg = {"model_dir": args.x2_model_dir}
        if args.x2_controller:
            cfg["controller_path"] = args.x2_controller
        return cfg
    return {}
```

- [ ] **Step 5: Wire platform into multi mode**

In `run_multi_mode()`, before spawn positions, add:

```python
platform_probe = create_platform(args.platform, **_platform_config_from_args(args))
```

Change spawn generation:

```python
spawn_positions = generate_spawn_positions(
    robot_ids,
    scene,
    spawn_height=platform_probe.metadata.spawn_height,
)
```

Change `MultiRobotConfig(...)`:

```python
config = MultiRobotConfig(
    robot_ids=robot_ids,
    spawn_positions=spawn_positions,
    boot_phase_steps=args.multi_boot_steps,
    scene=scene,
    platform=args.platform,
    platform_config=_platform_config_from_args(args),
)
```

Add import at top:

```python
from src.bridge.platforms import create_platform
```

- [ ] **Step 6: Wire platform into web mode and robot-list metadata**

In `run_web_mode()`, before spawn positions, add:

```python
platform_probe = create_platform(args.platform, **_platform_config_from_args(args))
```

Change spawn generation:

```python
spawn_positions = generate_spawn_positions(
    robot_ids,
    scene,
    spawn_height=platform_probe.metadata.spawn_height,
)
```

Change `config_kwargs`:

```python
config_kwargs = {
    "robot_ids": robot_ids,
    "spawn_positions": spawn_positions,
    "boot_phase_steps": args.multi_boot_steps,
    "scene": scene,
    "platform": args.platform,
    "platform_config": _platform_config_from_args(args),
}
```

Change `create_app(...)` call:

```python
platform_payload = {rid: platform_probe.metadata.to_wire() for rid in config.robot_ids}
app, streaming_viz = create_app(
    list(config.robot_ids),
    command_cb=coordinator.handle_command,
    slam_reset_cb=_reset_slam,
    mcp_endpoint=mcp_endpoint,
    cloud_config_fns={
        "get": get_active_config,
        "set": set_active_config,
        "configs": lambda: CLOUD_CONFIGS,
    },
    platform_metadata=platform_payload,
)
```

In restart bridge recreation, keep:

```python
bridge = MultiRobotBridge(config)
```

The same `config` instance now retains `platform` and `platform_config`.

- [ ] **Step 7: Run CLI tests**

Run:

```bash
pytest tests/test_main_platform_args.py -v
```

Expected: PASS.

- [ ] **Step 8: Run backend import smoke**

Run:

```bash
python -c "from src.main import parse_args, _platform_config_from_args; print('ok')"
```

Expected output:

```text
ok
```

- [ ] **Step 9: Commit**

```bash
git add src/main.py tests/test_main_platform_args.py
git commit -m "feat: add robot platform CLI selection"
```

---

### Task 15: X2 asset and MuJoCo smoke tests

**Files:**
- Create: `tests/bridge/platforms/test_agibot_x2_asset_smoke.py`
- Modify: `pyproject.toml` pytest marker list

- [ ] **Step 1: Add pytest marker**

Modify `pyproject.toml` `[tool.pytest.ini_options].markers` list and add:

```toml
    "x2_asset: tests requiring licensed local AGIBOT X2 MuJoCo assets",
```

- [ ] **Step 2: Write asset-gated smoke tests**

Create `tests/bridge/platforms/test_agibot_x2_asset_smoke.py`:

```python
import os
from pathlib import Path

import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.types import RobotCommand

X2_MODEL_DIR = Path("models/agibot_x2")
X2_XML = X2_MODEL_DIR / "x2_ultra.xml"
ENABLE_SMOKE = os.environ.get("ARGUS_X2_ENABLE_ASSET_SMOKE") == "1"

pytestmark = pytest.mark.x2_asset


def _require_x2_assets():
    if not ENABLE_SMOKE:
        pytest.skip("set ARGUS_X2_ENABLE_ASSET_SMOKE=1 to run X2 asset smoke tests")
    if not X2_XML.exists():
        pytest.skip(f"AGIBOT X2 MuJoCo asset missing: {X2_XML}")


def test_x2_asset_actuator_map_matches_controller_io():
    _require_x2_assets()
    platform = AgibotX2Platform(model_dir=str(X2_MODEL_DIR))

    actuator_names = platform.actuator_names()
    controller = platform.make_controller("robot_a")
    state = platform._state_from_arrays(
        base_pose=np.eye(4),
        base_velocity=np.zeros(3),
        joint_positions=platform.initial_joint_qpos(),
        joint_velocities=np.zeros(len(actuator_names)),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        sim_time=0.0,
    )
    action = controller.compute(RobotCommand.stand(), state, 0.02)

    assert len(actuator_names) == 31
    assert action.shape == (31,)
    assert np.isfinite(action).all()


def test_two_x2_robots_start_step_and_keep_independent_status():
    _require_x2_assets()
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": str(X2_MODEL_DIR)},
        robot_ids=("robot_a", "robot_b"),
        spawn_positions={"robot_a": (0.0, 0.0, 0.85), "robot_b": (2.0, 0.0, 0.85)},
        sim_steps_per_frame=1,
        boot_phase_steps=1,
    )
    bridge = MultiRobotBridge(config)

    try:
        frames = bridge.start()
        assert set(frames) == {"robot_a", "robot_b"}
        bridge.set_velocity("robot_a", np.array([0.1, 0.0]), 0.0)
        frames = bridge.step()
        assert set(frames) == {"robot_a", "robot_b"}
        assert bridge.get_runtime_status("robot_a").to_wire()["state"] in {"standing", "walking", "fallen", "disabled"}
        assert bridge.get_runtime_status("robot_b").to_wire()["state"] in {"standing", "walking", "fallen", "disabled"}
    finally:
        bridge.stop()


def test_five_x2_robots_build_unique_command_channels():
    _require_x2_assets()
    robot_ids = ("robot_a", "robot_b", "robot_c", "robot_d", "robot_e")
    config = MultiRobotConfig(
        platform="agibot_x2",
        platform_config={"model_dir": str(X2_MODEL_DIR)},
        robot_ids=robot_ids,
        spawn_positions={rid: (float(i) * 1.5, 0.0, 0.85) for i, rid in enumerate(robot_ids)},
        sim_steps_per_frame=1,
        boot_phase_steps=1,
    )
    bridge = MultiRobotBridge(config)

    assert bridge.robot_ids == robot_ids
    for rid in robot_ids:
        bridge.set_velocity(rid, np.array([0.0, 0.0]), 0.0)
        assert bridge.get_runtime_status(rid).last_command.to_wire()["mode"] == "velocity"
```

- [ ] **Step 3: Run smoke file without assets enabled**

Run:

```bash
pytest tests/bridge/platforms/test_agibot_x2_asset_smoke.py -v
```

Expected: SKIPPED all three tests with message requiring `ARGUS_X2_ENABLE_ASSET_SMOKE=1`.

- [ ] **Step 4: Run smoke file with assets enabled on an asset-equipped machine**

Run:

```bash
ARGUS_X2_ENABLE_ASSET_SMOKE=1 pytest tests/bridge/platforms/test_agibot_x2_asset_smoke.py -v
```

Expected when `models/agibot_x2/x2_ultra.xml` is absent: SKIPPED with the missing asset path. Expected when licensed assets are present and actuator mapping is valid: PASS for all three tests.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/bridge/platforms/test_agibot_x2_asset_smoke.py
git commit -m "test: add AGIBOT X2 asset smoke coverage"
```

---

### Task 16: Full validation and browser verification

**Files:**
- No new files.
- Validate: backend tests, frontend tests, frontend build, browser UI.

- [ ] **Step 1: Run backend platform and bridge tests**

Run:

```bash
pytest tests/bridge/platforms tests/bridge/test_collision_state.py tests/bridge/test_multi_bridge.py tests/bridge/test_multi_bridge_platform_selection.py -v
```

Expected: PASS except asset smoke tests are SKIPPED unless explicitly enabled.

- [ ] **Step 2: Run coordinator and web tests**

Run:

```bash
pytest tests/coordination/test_coordinator.py tests/web/test_web_server.py tests/web/test_streaming_viz.py tests/web/test_platform_metadata_stream.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend tests and build**

Run:

```bash
cd frontend && npm test -- robotStore.platformState.test.ts RobotCard.platformState.test.tsx RobotMarker.platformMetadata.test.ts && npm run build
```

Expected: PASS with Vite build output and no TypeScript errors.

- [ ] **Step 4: Run Go2 web mode smoke to verify no regression**

Run:

```bash
python -m src.main --control web --platform go2 --num-robots 2 --multi-max-steps 50 --port 8000
```

Expected:

```text
Starting Argus at http://localhost:8000
```

Browser verification:

1. Open `http://localhost:8000`.
2. Confirm robot cards show `Unitree Go2`.
3. Confirm robot cards still show coverage and voxel counts.
4. Confirm scene markers render and move or remain stable depending on controller state.
5. Send `Send To...` from a robot card and confirm no frontend error overlay appears.

- [ ] **Step 5: Run X2 startup validation without assets**

Run:

```bash
python -m src.main --control web --platform agibot_x2 --num-robots 2 --multi-max-steps 1 --port 8001
```

Expected when `models/agibot_x2/x2_ultra.xml` is absent: backend logs a clear `AGIBOT X2 MuJoCo model not found: models/agibot_x2/x2_ultra.xml` error, and no Go2-specific actuator error appears.

- [ ] **Step 6: Run X2 web smoke with licensed assets**

Run on a machine with `models/agibot_x2/x2_ultra.xml`, mesh assets, and controller path if available:

```bash
ARGUS_X2_ENABLE_ASSET_SMOKE=1 pytest tests/bridge/platforms/test_agibot_x2_asset_smoke.py -v
python -m src.main --control web --platform agibot_x2 --x2-model-dir models/agibot_x2 --x2-controller models/agibot_x2/policy.npz --num-robots 2 --multi-max-steps 200 --port 8001
```

Expected:

1. Asset smoke tests PASS.
2. Browser robot cards show `AGIBOT X2 Ultra`.
3. Robot cards show `standing`, `walking`, `fallen`, `recovering`, or `disabled` state.
4. A fallen X2 updates only that robot's state; the second robot continues streaming pose/camera/status.
5. Stats payload contains platform metadata, runtime status, fall reason, controller health, collisions, and near misses.

- [ ] **Step 7: Confirm no validation-only changes remain**

Run:

```bash
git status --short
```

Expected: no uncommitted validation-only changes remain. If validation uncovered code issues, return to the task that owns the failing component, apply the fix there, rerun that task's focused tests, and use that task's explicit commit command.

---

## Self-Review Checklist

### Spec coverage

- Platform registry loads Go2 and X2 independently: Tasks 2, 3, 5.
- Existing Go2 simulation behavior preserved: Tasks 3, 7, 8, 16.
- X2 model path validated at startup: Task 5 and Task 16.
- X2 actuator/controller IO shape validated: Tasks 4, 5, 15.
- One X2 stand/walk smoke path: Task 15, gated by local licensed assets and controller availability.
- 2-5 X2 robots spawn with unique names and command channels: Tasks 8 and 15.
- Waypoint/velocity commands avoid raw joint leakage: Tasks 4, 8, 9.
- Fall detection disables only failed robot: Tasks 5, 8, 9.
- Collision/near-miss state appears in backend state: Tasks 6, 8, 10.
- UI displays platform type and X2 runtime state: Tasks 11, 12, 13.
- Hardware/AimDK/ROS 2/Isaac/training remain out of scope: Scope Check and controller boundary tasks.

### Type and naming consistency

- Python runtime state type is `RobotRuntimeStatus`; frontend payload type is `RobotRuntimeStatusPayload`.
- Platform metadata Python dataclass is `RobotPlatformMetadata`; frontend payload type is `PlatformMetadata`.
- Backend stats key is `runtime_status`; frontend maps it into `runtimeState`, `fallReason`, `disabled`, `controllerHealth`, `collisionCount`, and `nearMissCount`.
- Platform names are exactly `go2` and `agibot_x2` across registry, CLI, backend, and frontend.
- Generic command actions are `velocity`, `stand`, `stop_robot`, and `recover_robot`; existing `send_to`, `stop`, `pause`, `resume`, `set_speed`, and `restart` remain intact.

### Final expected state

After all tasks, Argus has a platform abstraction that keeps Go2 working and gives X2 a real MuJoCo integration boundary. X2 does not pretend to have a hand-written humanoid gait: walking remains behind `X2PolicyController`, and missing assets/policies surface as configuration or controller-health state rather than silent fake success.
