# Phase 08: locomotion-controller-seam-cleanup - Pattern Map

**Mapped:** 2026-05-02
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/bridge/multi_bridge.py` | service / bridge | batch + indexed control I/O | `src/bridge/sim_bridge.py` + `src/locomotion/controller_dispatch.py` | role-match + flow-match |
| `src/locomotion/controllers.py` | registry / model | transform + metadata discovery | `src/locomotion/controllers.py` existing placeholder registry sections | exact |
| `src/locomotion/controller_dispatch.py` | utility | transform + indexed control I/O | `src/locomotion/controller_dispatch.py` existing dispatch/apply helpers | exact |
| `docs/locomotion-benchmark.md` | documentation | static docs + matrix contract | `docs/locomotion-benchmark.md` existing controller-family matrix | exact |
| `tests/bridge/test_multi_bridge.py` | test | batch + fake runtime control I/O | `tests/locomotion/test_controller_dispatch.py` no-mutation tests + existing bridge fake tests | flow-match |
| `tests/bridge/test_multi_bridge_platform_selection.py` | test | platform boundary / request-response selection | `tests/bridge/test_multi_bridge_platform_selection.py` existing platform-selection tests | exact |
| `tests/locomotion/test_locomotion_controller_registry.py` | test | registry metadata discovery | `tests/locomotion/test_locomotion_controller_registry.py` residual placeholder tests | exact |
| `tests/test_locomotion_benchmark_docs.py` | test | file I/O + docs guard | `tests/test_locomotion_benchmark_docs.py` residual docs/registry guard | exact |
| `tests/locomotion/test_controller_dispatch.py` | test | transform + indexed control I/O | `tests/locomotion/test_controller_dispatch.py` existing mutation guard tests | exact |

## Pattern Assignments

### `src/bridge/multi_bridge.py` (service / bridge, batch + indexed control I/O)

**Analog:** `src/bridge/sim_bridge.py` and `src/locomotion/controller_dispatch.py`

**Imports pattern** (`src/bridge/sim_bridge.py` lines 16-24):
```python
from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix, IMUReading
from src.locomotion.controller_dispatch import (
    apply_controller_target,
    command_from_velocity,
    compute_controller_action,
)
from src.locomotion.controllers import ControllerRegistry, LocomotionCommand
from src.locomotion.xml_patcher import patch_actuators_to_position_with_floor
```

Use the `apply_controller_target` import in `multi_bridge.py`; if the implementation chooses Go2 registry unification, also copy the `ControllerRegistry`, `command_from_velocity`, and `compute_controller_action` seam style from the single bridge.

**Registered-controller construction pattern** (`src/bridge/sim_bridge.py` lines 57-58):
```python
# Registered analytical controller for locomotion
self._controller = ControllerRegistry.create("analytical_trot")
```

Apply only if the planner chooses Go2 practical unification. For non-Go2 platforms, preserve platform-local controller construction.

**Current platform-boundary construction to preserve or deliberately replace** (`src/bridge/multi_bridge.py` lines 43-56):
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
```

**Core control-application pattern to copy** (`src/locomotion/controller_dispatch.py` lines 62-94):
```python
def apply_controller_target(
    data: Any,
    target: Sequence[float] | np.ndarray,
    ctrl_indices: Sequence[int] | None = None,
) -> np.ndarray:
    """Validate and apply one Go2 controller target to a control sink.

    With ``ctrl_indices is None``, the full target is written to ``data.ctrl[:]``.
    With indices supplied, exactly twelve actuator indices are required and each
    target element is written to the paired actuator slot. All validation is done
    before the first ``data.ctrl`` mutation.
    """

    validated = validate_controller_target(target)
    if ctrl_indices is not None and len(ctrl_indices) != validated.shape[0]:
        raise ValueError(
            f"ctrl_indices must contain exactly {validated.shape[0]} entries, "
            f"got {len(ctrl_indices)}."
        )

    if ctrl_indices is None:
        data.ctrl[:] = validated
    else:
        indices = [int(idx) for idx in ctrl_indices]
        if len(set(indices)) != len(indices):
            raise ValueError("ctrl_indices must not contain duplicates.")
        ctrl_size = int(data.ctrl.shape[0])
        bad_indices = [idx for idx in indices if idx < 0 or idx >= ctrl_size]
        if bad_indices:
            raise ValueError(f"ctrl_indices out of range for data.ctrl size {ctrl_size}: {bad_indices}")
        for i, act_id in enumerate(indices):
            data.ctrl[act_id] = validated[i]
    return validated
```

**Direct-write anti-pattern to replace** (`src/bridge/multi_bridge.py` lines 225-231):
```python
ctrl = self._controllers[robot_id].compute(command, state, self._dt)
if ctrl.shape != (len(self._ctrl_indices[robot_id]),):
    raise RuntimeError(
        f"Controller for {robot_id} returned {ctrl.shape}, expected {(len(self._ctrl_indices[robot_id]),)}"
    )
for i, act_id in enumerate(self._ctrl_indices[robot_id]):
    self._data.ctrl[act_id] = ctrl[i]
```

Replace the shape-only check and loop with shared pre-mutation validation. If non-Go2 actuator counts cannot use the 12-target helper, extract a helper with the same all-validation-before-mutation shape and test it explicitly.

**Single-robot dispatch seam pattern** (`src/bridge/sim_bridge.py` lines 166-172 and 214-228):
```python
if action is not None:
    apply_controller_target(self._data, action)
else:
    # Convert velocity command to joint targets through the registered controller seam
    ctrl = self._velocity_to_ctrl()
    apply_controller_target(self._data, ctrl)
```

```python
def _velocity_command(self) -> LocomotionCommand:
    """Build a typed command from buffered bridge velocities."""
    return command_from_velocity(self._linear_vel, self._angular_vel)

def _velocity_to_ctrl(self) -> np.ndarray:
    """Convert buffered velocity to validated joint position targets.

    Uses the registered analytical_trot controller seam for proper trot gait
    with position-controlled actuators, producing actual locomotion via
    diagonal pair alternation and differential stride turning.
    """
    dt = self._dt  # self._dt already includes sim_steps_per_frame
    command = self._velocity_command()
    result = compute_controller_action(self._controller, {}, command, dt)
    return result.action
```

**Error handling pattern** (`src/bridge/multi_bridge.py` lines 210-211 and 327-330):
```python
if self._model is None:
    raise RuntimeError("Bridge not started -- call start() first")
```

```python
def set_command(self, robot_id: str, command: RobotCommand) -> None:
    if robot_id not in self._commands:
        raise KeyError(f"Unknown robot_id: {robot_id}")
    self._commands[robot_id] = command
```

Keep deterministic `RuntimeError`/`KeyError` style. Do not silently clip or partially apply invalid controller output.

---

### `src/locomotion/controllers.py` (registry / model, transform + metadata discovery)

**Analog:** existing `src/locomotion/controllers.py` registry and placeholder sections

**Imports/constants pattern** (`src/locomotion/controllers.py` lines 11-25 and 54-69):
```python
import hashlib
import importlib
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams

logger = logging.getLogger(__name__)

CONTROLLER_TARGET_SHAPE = (12,)
```

```python
RESIDUAL_POLICY_UNAVAILABLE_REASON = (
    "Residual policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
DIRECT_POLICY_UNAVAILABLE_REASON = (
    "Direct policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
MPC_UNAVAILABLE_REASON = (
    "MPC controllers require dynamics/contact solver infrastructure and are deferred "
    "until a future model-based-control milestone."
)
WBC_UNAVAILABLE_REASON = (
    "WBC controllers require torque/whole-body-control infrastructure and are deferred "
    "until a future model-based-control milestone."
)
```

**Capability schema pattern** (`src/locomotion/controllers.py` lines 27-52):
```python
_CONTROLLER_REQUIRED_KEYS = (
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
_CONTROLLER_TYPED_KEYS: dict[str, type | tuple[type, ...]] = {
    "family": str,
    "action_mode": str,
    "deterministic": bool,
    "observation_expectation": str,
    "command_limits": dict,
    "cpu_latency_hint_ms": (int, float),
    "sim_supported": bool,
    "hardware_supported": bool,
    "model_requirements": dict,
    "multi_robot_supported": bool,
    "reproducibility": dict,
}
```

If adding an explicit WBC deferred vocabulary field, update required/typed keys only if every registered controller receives the field. Otherwise keep it inside `model_requirements` or `reproducibility` to avoid broad registry churn.

**Validation pattern** (`src/locomotion/controllers.py` lines 169-198):
```python
def _validate_capabilities(name: str, klass: type) -> None:
    caps = getattr(klass, "CAPABILITIES", None)
    if not isinstance(caps, dict):
        raise ValueError(
            f"Locomotion controller '{name}' missing CAPABILITIES dict on {klass.__qualname__}."
        )
    missing = sorted(key for key in _CONTROLLER_REQUIRED_KEYS if key not in caps)
    if missing:
        raise ValueError(
            f"Locomotion controller '{name}' ({klass.__qualname__}) missing CAPABILITIES keys: "
            f"{missing}. Required: {list(_CONTROLLER_REQUIRED_KEYS)}."
        )
    for key, expected_type in _CONTROLLER_TYPED_KEYS.items():
        value = caps[key]
        if not isinstance(value, expected_type):
            expected_name = (
                " | ".join(t.__name__ for t in expected_type)
                if isinstance(expected_type, tuple)
                else expected_type.__name__
            )
            raise ValueError(
                f"Locomotion controller '{name}' CAPABILITIES['{key}'] must be "
                f"{expected_name}, got {type(value).__name__} ({value!r})."
            )
    schema = getattr(klass, "PARAMETER_SCHEMA", None)
    if not isinstance(schema, dict):
        raise ValueError(
            f"Locomotion controller '{name}' missing PARAMETER_SCHEMA dict on {klass.__qualname__}."
        )
```

**Placeholder metadata pattern** (`src/locomotion/controllers.py` lines 376-393):
```python
def _placeholder_capabilities(family: str, action_mode: str) -> dict[str, Any]:
    return {
        "family": family,
        "action_mode": action_mode,
        "deterministic": False,
        "observation_expectation": "Deferred placeholder; observation contract will be defined with the controller family.",
        "command_limits": _velocity_command_limits(),
        "cpu_latency_hint_ms": 0.0,
        "sim_supported": False,
        "hardware_supported": False,
        "model_requirements": {"requires_model_artifact": True, "artifacts": []},
        "multi_robot_supported": False,
        "reproducibility": {
            "stateful": True,
            "reset_reinitializes_state": True,
            "seed_used": True,
            "deferred": True,
        },
    }
```

**Unavailable-controller pattern** (`src/locomotion/controllers.py` lines 446-464):
```python
class _UnavailableControllerBase:
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "description": "Unavailable placeholder; no runtime parameters are accepted in this milestone.",
    }
    UNAVAILABLE_REASON = "Controller family is unavailable."

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnavailableControllerError(self.UNAVAILABLE_REASON)

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return False, cls.UNAVAILABLE_REASON

    @classmethod
    def parameter_summary(cls) -> dict[str, Any]:
        return {"placeholder": True, "reason": cls.UNAVAILABLE_REASON}
```

**WBC line to change** (`src/locomotion/controllers.py` lines 485-488):
```python
@locomotion_controller(name="wbc", display="Whole-Body Control")
class WBCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("wbc", "torque_or_joint_position")
    UNAVAILABLE_REASON = WBC_UNAVAILABLE_REASON
```

Do not add `torque_or_joint_position` to the v4.0 env action-mode catalog. Prefer explicit deferred vocabulary in WBC capabilities/docs/tests, while keeping `available=False`.

---

### `src/locomotion/controller_dispatch.py` (utility, transform + indexed control I/O)

**Analog:** existing `src/locomotion/controller_dispatch.py`

**Imports pattern** (`src/locomotion/controller_dispatch.py` lines 9-21):
```python
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from src.locomotion.controllers import (
    ControllerResult,
    LocomotionCommand,
    LocomotionController,
    validate_controller_target,
)
```

**Command adapter pattern** (`src/locomotion/controller_dispatch.py` lines 24-42):
```python
def command_from_velocity(
    linear: Sequence[float] | np.ndarray,
    angular: float,
    metadata: dict[str, Any] | None = None,
) -> LocomotionCommand:
    """Build a typed command from bridge velocity buffers.

    Short linear velocity arrays preserve the current bridge semantics:
    missing ``vx`` and ``vy`` entries default independently to ``0.0``.
    """

    vx = float(linear[0]) if len(linear) > 0 else 0.0
    vy = float(linear[1]) if len(linear) > 1 else 0.0
    return LocomotionCommand(
        vx=vx,
        vy=vy,
        yaw_rate=float(angular),
        metadata=None if metadata is None else dict(metadata),
    )
```

**Compute/validate pattern** (`src/locomotion/controller_dispatch.py` lines 45-59):
```python
def compute_controller_action(
    controller: LocomotionController,
    observation: dict[str, Any],
    command: LocomotionCommand,
    dt: float,
) -> ControllerResult:
    """Call a controller and return a copied, validated result.

    Validation happens at the controller-to-dispatch trust boundary before any
    caller can write the target to physics controls.
    """

    result = controller.compute(observation, command, dt)
    validated = validate_controller_target(result.action)
    return ControllerResult(action=validated, metadata=dict(result.metadata))
```

**Combined dispatch pattern** (`src/locomotion/controller_dispatch.py` lines 97-111):
```python
def dispatch_controller(
    controller: LocomotionController,
    observation: dict[str, Any],
    command: LocomotionCommand,
    dt: float,
    data: Any | None = None,
    ctrl_indices: Sequence[int] | None = None,
) -> ControllerResult:
    """Compute a validated controller action and optionally apply it to ``data.ctrl``."""

    result = compute_controller_action(controller, observation, command, dt)
    if data is not None:
        applied = apply_controller_target(data, result.action, ctrl_indices=ctrl_indices)
        return ControllerResult(action=applied, metadata=dict(result.metadata))
    return result
```

Only modify this file if the multi-bridge needs a generic indexed helper for non-12-actuator platform targets. If so, preserve the same API style, exact validation-before-mutation invariant, and `ValueError` failure mode.

---

### `docs/locomotion-benchmark.md` (documentation, static docs + matrix contract)

**Analog:** existing controller-family matrix in `docs/locomotion-benchmark.md`

**Action-mode contract pattern** (`docs/locomotion-benchmark.md` lines 37-43):
```markdown
The environment-supported action modes are listed below. argus eval-locomotion currently runs `velocity_command`; `joint_position` and `residual_baseline` are env-supported seams that fail fast in evaluation until explicit action sources exist.

| Action mode | Use |
|-------------|-----|
| `velocity_command` | Three-value planar velocity command routed through the selected controller. This is the default benchmark/evaluator mode for `analytical_trot`. |
| `joint_position` | 12-value direct joint-position env seam for controller families that own joint target generation; not currently evaluator-runnable without an explicit action source. |
| `residual_baseline` | 12-value residual-over-baseline env seam for future residual-policy work; not currently evaluator-runnable without a trained residual policy/action source. |
```

Do not add WBC-only torque wording to this env-supported action-mode table unless the environment actually supports it.

**Controller-family boundary pattern** (`docs/locomotion-benchmark.md` lines 112-124):
```markdown
## Controller-family boundary matrix

The matrix is intentionally hard-edged. If a family is unavailable or deferred, do not describe it as supported just because there is a seam. v4.0 does not ship trained RL policies, MPC, WBC, ROS/hardware behavior, torque-control locomotion, or perception-conditioned locomotion.

| Controller family | Status now | Argus hook/seam | Why supported/deferred | Prerequisite to unlock | R&D rationale link |
|-------------------|------------|-----------------|------------------------|------------------------|--------------------|
| analytical gait | supported now | Controller id `analytical_trot`; `argus eval-locomotion`; default `velocity_command` action mode | Existing deterministic Raibert-style analytical trot produces Go2 joint-position targets through MuJoCo position actuators. | Keep regression and metrics gates green before changing baseline behavior. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| residual RL | registered placeholder unavailable | Controller id `residual_policy`; residual-over-baseline seam via `residual_baseline` action mode | Placeholder exists so the benchmark boundary is stable, but no trained residual policy artifact ships in v4.0. | Train/evaluate residual policy artifacts and define promotion criteria against the analytical baseline. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| direct RL | registered placeholder unavailable | Controller id `direct_policy`; joint-position action seam | Placeholder exists, but v4.0 has no trained direct policy and no training pipeline in scope. | Add training/evaluation infrastructure, policy artifacts, and reproducibility gates. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| MPC | registered placeholder unavailable | Controller id `mpc`; model-based controller seam | Requires dynamics/contact solver infrastructure not implemented in v4.0. | Add model-based-control infrastructure, contact assumptions, and benchmark evidence. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| WBC | registered placeholder unavailable | Controller id `wbc`; whole-body-control seam | Requires torque/whole-body-control infrastructure not implemented in v4.0. | Add torque/control allocation assumptions, state/contact estimation, and benchmark evidence. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| ROS/hardware | deferred/no runnable v4.0 implementation | Future adapter boundary only; no runnable controller id | v4.0 is simulation-only and CPU-first; ROS 2 and hardware deployment are out of scope. | Define hardware/ROS architecture, timing, state estimation, safety, and deployment gates. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| perception-conditioned locomotion | deferred/no runnable v4.0 implementation | Future perception-to-control integration seam only; no runnable controller id | Current benchmark isolates locomotion control from perception-conditioned policy behavior. | Define perception-conditioned observations, latency handling, safety behavior, and benchmark scenarios. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
```

Update the WBC row to include the exact deferred/undefined contract vocabulary selected in `controllers.py`.

---

### `tests/bridge/test_multi_bridge.py` (test, batch + fake runtime control I/O)

**Analog:** existing bridge fake tests plus dispatch mutation guards

**Imports pattern** (`tests/bridge/test_multi_bridge.py` lines 7-24):
```python
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.go2 import Go2Platform
import src.bridge.scene_builder as scene_builder
from src.bridge.scene_builder import (
    build_multi_robot_scene,
    build_two_robot_office_scene,
    build_two_robot_scene,
)
from src.bridge.sensor_types import SensorFrame
```

**Fake platform/controller pattern** (`tests/bridge/test_multi_bridge_platform_selection.py` lines 48-89):
```python
class _FakeAgibotLikePlatform:
    metadata = types.SimpleNamespace(
        name="fake_agibot",
        model_dir="models/fake_agibot",
        actuator_count=1,
        footprint_radius=0.3,
    )

    def root_body_name(self):
        return "pelvis"

    def actuator_names(self):
        return ["hip"]

    def initial_joint_qpos(self):
        return np.array([0.0])

    def make_controller(self, robot_id):
        return _FakeController()

    def extract_state(self, model, data, qpos_start, sim_time):
        return _fake_state(sim_time)

    def runtime_status(self, robot_id, state, command, health, **kwargs):
        return RobotRuntimeStatus(
            state=RobotRuntimeState.STANDING,
            last_command=command,
            controller_health=health,
            **kwargs,
        )
```

```python
class _FakeController:
    def __init__(self):
        self.commands = []

    def compute(self, command, state, dt):
        self.commands.append(command)
        return np.array([0.0])

    def health(self):
        return ControllerHealth()
```

For the new no-mutation regression, adapt this pattern to a 12-actuator fake platform/controller so `apply_controller_target(..., ctrl_indices=...)` can validate the indexed multi-robot sink.

**Bridge step fake-runtime pattern** (`tests/bridge/test_multi_bridge_platform_selection.py` lines 170-199):
```python
def test_step_records_stop_as_last_command_when_robot_was_disabled(monkeypatch):
    controller = _FakeController()
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2", robot_ids=("robot_a",), sim_steps_per_frame=1))
    bridge._platform = _FakeAgibotLikePlatform()
    bridge._controllers = {"robot_a": controller}
    bridge._model = types.SimpleNamespace(opt=types.SimpleNamespace(timestep=0.002))
    bridge._data = types.SimpleNamespace(qpos=np.zeros(3), ctrl=np.zeros(1))
    bridge._dt = 0.02
    bridge._qpos_starts = {"robot_a": 0}
    bridge._ctrl_indices = {"robot_a": [0]}
    bridge._viewer_handle = None
    bridge._commands = {"robot_a": RobotCommand.velocity([0.7, 0.0], 0.2)}
    bridge._runtime_status = {
        "robot_a": RobotRuntimeStatus(
            state=RobotRuntimeState.DISABLED,
            last_command=RobotCommand.velocity([0.7, 0.0], 0.2),
        )
    }

    monkeypatch.setitem(sys.modules, "mujoco", types.SimpleNamespace(mj_step=lambda model, data: None))
    monkeypatch.setattr(
        MultiRobotBridge,
        "_capture_frame",
        lambda self, robot_id: types.SimpleNamespace(robot_id=robot_id),
    )

    bridge.step()

    assert controller.commands[-1].mode == "stop"
    assert bridge.get_runtime_status("robot_a").last_command.mode == "stop"
```

**No-mutation assertion pattern** (`tests/locomotion/test_controller_dispatch.py` lines 109-120 and 141-150):
```python
def test_apply_controller_target_rejects_invalid_without_mutating_ctrl(bad_target: np.ndarray) -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError):
        apply_controller_target(
            fake_data,
            bad_target,
            ctrl_indices=[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        )

    np.testing.assert_allclose(fake_data.ctrl, before)
```

```python
with pytest.raises(ValueError, match=message):
    apply_controller_target(fake_data, np.arange(12, dtype=np.float64), ctrl_indices=bad_indices)

np.testing.assert_allclose(fake_data.ctrl, before)
```

Bridge-level tests should assert both the exception and unchanged `bridge._data.ctrl`.

---

### `tests/bridge/test_multi_bridge_platform_selection.py` (test, platform boundary / request-response selection)

**Analog:** existing platform-selection tests

**Imports and platform type pattern** (`tests/bridge/test_multi_bridge_platform_selection.py` lines 1-15):
```python
import sys
import types

import numpy as np

import src.bridge.multi_bridge as multi_bridge_module
from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import (
    ControllerHealth,
    RobotCommand,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)
```

**Boundary assertion pattern** (`tests/bridge/test_multi_bridge_platform_selection.py` lines 18-45):
```python
def test_bridge_exposes_platform_metadata_without_starting():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    metadata = bridge.platform_metadata

    assert metadata.name == "go2"
    assert metadata.actuator_count == 12
```

```python
def test_bridge_buffers_generic_robot_command():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_command("robot_a", RobotCommand.velocity([0.4, 0.0], 0.2))

    assert bridge.get_runtime_status("robot_a").last_command.to_wire() == {
        "mode": "velocity",
        "linear": [0.4, 0.0],
        "yaw_rate": 0.2,
        "waypoint": None,
    }
```

Use this file for the explicit Go2 unification vs platform-runtime-boundary regression. If preserving `self._platform.make_controller()` for non-Go2, assert the boundary in behavior, not comments.

**Start-time fake MuJoCo pattern** (`tests/bridge/test_multi_bridge_platform_selection.py` lines 104-167):
```python
def test_start_discovers_platform_root_body_name(monkeypatch):
    body_lookups = []

    class FakeModel:
        opt = types.SimpleNamespace(timestep=0.002)
        njnt = 1
        jnt_bodyid = np.array([7])
        jnt_type = np.array([0])
        jnt_qposadr = np.array([0])

        @staticmethod
        def from_xml_string(xml_str, assets):
            return FakeModel()

    class FakeData:
        def __init__(self, model):
            self.qpos = np.zeros(8)
            self.ctrl = np.zeros(1)

    class FakeRenderer:
        def __init__(self, model, height, width):
            pass
```

Continue this monkeypatch style for any new platform-selection seam test; do not require real MuJoCo.

---

### `tests/locomotion/test_locomotion_controller_registry.py` (test, registry metadata discovery)

**Analog:** existing residual placeholder and registry metadata tests

**Imports/constants pattern** (`tests/locomotion/test_locomotion_controller_registry.py` lines 8-34):
```python
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
```

**Helper pattern** (`tests/locomotion/test_locomotion_controller_registry.py` lines 37-49):
```python
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
```

**Unavailable placeholder pattern** (`tests/locomotion/test_locomotion_controller_registry.py` lines 129-155):
```python
@pytest.mark.parametrize("controller_id", sorted(PLACEHOLDER_IDS))
def test_controller_registry_placeholder_controllers_are_discoverable_but_unavailable(controller_id: str):
    from src.locomotion.controllers import ControllerRegistry, UnavailableControllerError

    entry = _entry_by_name(ControllerRegistry.list_controllers(), controller_id)

    assert entry["available"] is False
    assert entry.get("reason")
    assert entry["parameter_summary"] == {"placeholder": True, "reason": entry["reason"]}
    with pytest.raises(UnavailableControllerError) as exc_info:
        ControllerRegistry.create(controller_id)

    message = str(exc_info.value)
    assert f"Controller '{controller_id}' is unavailable" in message
    assert entry["reason"] in message
```

```python
def test_residual_placeholder_advertises_public_residual_baseline_action_mode():
    from src.locomotion.actions import available_action_modes
    from src.locomotion.controllers import ControllerRegistry

    entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    action_mode = entries["residual_policy"]["capabilities"]["action_mode"]

    assert action_mode == "residual_baseline"
    assert action_mode in available_action_modes()
    assert entries["residual_policy"]["available"] is False
```

Add the WBC assertion beside the residual assertion. For WBC, assert either explicit deferred vocabulary not in `available_action_modes()` or an existing action mode plus a separate deferred contract flag. The key is that the test must encode the chosen contract.

---

### `tests/test_locomotion_benchmark_docs.py` (test, file I/O + docs guard)

**Analog:** existing Markdown docs guard tests

**File-path and token pattern** (`tests/test_locomotion_benchmark_docs.py` lines 3-20):
```python
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "locomotion-benchmark.md"
SMOKE_COMMAND = "uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202"
ARTIFACTS = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
FAMILIES = (
    "analytical gait",
    "residual RL",
    "direct RL",
    "MPC",
    "WBC",
    "ROS/hardware",
    "perception-conditioned locomotion",
)
```

**Matrix content guard pattern** (`tests/test_locomotion_benchmark_docs.py` lines 58-75):
```python
def test_controller_family_matrix_required_content():
    guide = GUIDE.read_text(encoding="utf-8")

    assert "| Controller family | Status now | Argus hook/seam | Why supported/deferred | Prerequisite to unlock | R&D rationale link |" in guide
    for family in FAMILIES:
        assert family in guide
    for token in (
        "supported now",
        "registered placeholder unavailable",
        "deferred/no runnable v4.0 implementation",
        "analytical_trot",
        "residual_policy",
        "direct_policy",
        "mpc",
        "wbc",
    ):
        assert token in guide
```

**Docs/registry alignment pattern** (`tests/test_locomotion_benchmark_docs.py` lines 91-106):
```python
def test_residual_policy_documentation_matches_registry_action_mode():
    from src.locomotion.actions import available_action_modes
    from src.locomotion.controllers import ControllerRegistry

    guide = GUIDE.read_text(encoding="utf-8")
    entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    residual = entries["residual_policy"]
    action_mode = residual["capabilities"]["action_mode"]

    assert residual["available"] is False
    assert action_mode == "residual_baseline"
    assert action_mode in available_action_modes()
    assert (
        f"Controller id `residual_policy`; residual-over-baseline seam via `{action_mode}` action mode"
        in guide
    )
```

Add a WBC counterpart that reads `ControllerRegistry.list_controllers()`, selects `entries["wbc"]`, asserts unavailable/deferred vocabulary, and checks the exact WBC row text in the guide.

**Evaluator contract docs guard pattern** (`tests/test_locomotion_benchmark_docs.py` lines 110-117):
```python
def test_locomotion_benchmark_guide_states_evaluator_action_mode_contract():
    guide = GUIDE.read_text(encoding="utf-8")

    assert "argus eval-locomotion currently runs `velocity_command`" in guide
    assert "joint_position" in guide
    assert "residual_baseline" in guide
    assert "env-supported seams" in guide
    assert "fail fast" in guide
```

Keep this guard intact; WBC metadata must not weaken Phase 7 evaluator rejection semantics.

---

### `tests/locomotion/test_controller_dispatch.py` (test, transform + indexed control I/O)

**Analog:** existing dispatch tests

**Imports/fakes pattern** (`tests/locomotion/test_controller_dispatch.py` lines 3-20):
```python
from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from src.locomotion.controllers import ControllerResult, LocomotionCommand
from src.locomotion.controller_dispatch import (
    apply_controller_target,
    command_from_velocity,
    dispatch_controller,
)


class FakeData:
    def __init__(self, size: int = 12) -> None:
        self.ctrl = np.full(size, -1.0, dtype=np.float64)
```

**Indexed write pattern** (`tests/locomotion/test_controller_dispatch.py` lines 85-98):
```python
def test_apply_controller_target_writes_ctrl_indices_only() -> None:
    fake_data = FakeData(size=20)
    original = fake_data.ctrl.copy()
    target = np.arange(12, dtype=np.float64)
    ctrl_indices = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    validated = apply_controller_target(fake_data, target, ctrl_indices=ctrl_indices)

    np.testing.assert_allclose(validated, target)
    for i, act_id in enumerate(ctrl_indices):
        assert fake_data.ctrl[act_id] == target[i]
    untouched = [idx for idx in range(fake_data.ctrl.shape[0]) if idx not in ctrl_indices]
    np.testing.assert_allclose(fake_data.ctrl[untouched], original[untouched])
```

**Invalid target no-mutation pattern** (`tests/locomotion/test_controller_dispatch.py` lines 100-150):
```python
@pytest.mark.parametrize(
    "bad_target",
    [
        np.arange(3, dtype=np.float64),
        np.arange(13, dtype=np.float64),
        np.array([np.nan] + [0.0] * 11, dtype=np.float64),
        np.array([np.inf] + [0.0] * 11, dtype=np.float64),
    ],
)
def test_apply_controller_target_rejects_invalid_without_mutating_ctrl(bad_target: np.ndarray) -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError):
        apply_controller_target(
            fake_data,
            bad_target,
            ctrl_indices=[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        )

    np.testing.assert_allclose(fake_data.ctrl, before)
```

```python
@pytest.mark.parametrize(
    "bad_indices, message",
    [
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20], "out of range"),
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1], "out of range"),
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10], "duplicates"),
    ],
)
def test_apply_controller_target_rejects_bad_ctrl_indices_without_mutating_ctrl(
    bad_indices: list[int], message: str
) -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError, match=message):
        apply_controller_target(fake_data, np.arange(12, dtype=np.float64), ctrl_indices=bad_indices)

    np.testing.assert_allclose(fake_data.ctrl, before)
```

If `controller_dispatch.py` is extended for generic platform actuator counts, clone this test structure: positive indexed write, wrong target shape, non-finite values, wrong index count, duplicate indices, out-of-range indices, and no-mutation assertions.

## Shared Patterns

### Pre-mutation controller output validation

**Source:** `src/locomotion/controller_dispatch.py` lines 62-94
**Apply to:** `src/bridge/multi_bridge.py`, `src/locomotion/controller_dispatch.py`, `tests/bridge/test_multi_bridge.py`, `tests/locomotion/test_controller_dispatch.py`

```python
validated = validate_controller_target(target)
if ctrl_indices is not None and len(ctrl_indices) != validated.shape[0]:
    raise ValueError(
        f"ctrl_indices must contain exactly {validated.shape[0]} entries, "
        f"got {len(ctrl_indices)}."
    )
```

Then validate duplicates and bounds before the first assignment to `data.ctrl`.

### Registry placeholder semantics

**Source:** `src/locomotion/controllers.py` lines 446-464 and 467-488
**Apply to:** `src/locomotion/controllers.py`, `tests/locomotion/test_locomotion_controller_registry.py`, `tests/test_locomotion_benchmark_docs.py`, `docs/locomotion-benchmark.md`

```python
class _UnavailableControllerBase:
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "description": "Unavailable placeholder; no runtime parameters are accepted in this milestone.",
    }
    UNAVAILABLE_REASON = "Controller family is unavailable."

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        raise UnavailableControllerError(self.UNAVAILABLE_REASON)

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return False, cls.UNAVAILABLE_REASON
```

WBC must remain discoverable and unavailable; only the misleading action contract vocabulary should change.

### Canonical v4.0 action-mode catalog

**Source:** `src/locomotion/actions.py` lines 12-15 and 54-63
**Apply to:** WBC metadata tests and docs guards

```python
ACTION_MODE_VELOCITY = "velocity_command"
ACTION_MODE_JOINT_POSITION = "joint_position"
ACTION_MODE_RESIDUAL_BASELINE = "residual_baseline"
```

```python
_ACTION_MODES: Final[tuple[str, ...]] = (
    ACTION_MODE_JOINT_POSITION,
    ACTION_MODE_RESIDUAL_BASELINE,
    ACTION_MODE_VELOCITY,
)


def available_action_modes() -> list[str]:
    """Return sorted action mode names supported by the benchmark wrapper."""
    return sorted(_ACTION_MODES)
```

Do not add WBC-only strings here during Phase 8 unless the env/evaluator actually implements them.

### Markdown content guard style

**Source:** `tests/test_locomotion_benchmark_docs.py` lines 91-106
**Apply to:** WBC docs/registry alignment

```python
guide = GUIDE.read_text(encoding="utf-8")
entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
residual = entries["residual_policy"]
action_mode = residual["capabilities"]["action_mode"]

assert residual["available"] is False
assert action_mode == "residual_baseline"
assert action_mode in available_action_modes()
assert (
    f"Controller id `residual_policy`; residual-over-baseline seam via `{action_mode}` action mode"
    in guide
)
```

WBC should get the same docs/registry drift guard, with assertions matching the selected deferred vocabulary.

### Fake-runtime bridge tests without MuJoCo dependency

**Source:** `tests/bridge/test_multi_bridge_platform_selection.py` lines 170-199
**Apply to:** bridge regression tests in `tests/bridge/test_multi_bridge.py` and platform boundary tests

```python
monkeypatch.setitem(sys.modules, "mujoco", types.SimpleNamespace(mj_step=lambda model, data: None))
monkeypatch.setattr(
    MultiRobotBridge,
    "_capture_frame",
    lambda self, robot_id: types.SimpleNamespace(robot_id=robot_id),
)

bridge.step()
```

Use monkeypatched `mujoco` modules and fake bridge internals for fast tests; do not make Phase 8 regressions require real MuJoCo.

## No Analog Found

None. Every Phase 8 file has an exact or strong role/flow analog in the current codebase.

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src`, `/home/prannayag/pragnition/robotics/argus/tests`, `/home/prannayag/pragnition/robotics/argus/docs`
**Files scanned:** 180+ Python/Markdown files listed via `find`; pattern grep focused on controller registry, dispatch, action modes, bridge platform seams, docs guards, and `data.ctrl` mutation.
**Pattern extraction date:** 2026-05-02
**Project instructions loaded:** `/home/prannayag/pragnition/robotics/argus/CLAUDE.md`; `.claude/skills/desloppify/SKILL.md` lightweight index
