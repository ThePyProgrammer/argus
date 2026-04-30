# Phase 2: controller-plugin-baseline - Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/locomotion/controllers.py` | service / model / registry | request-response + transform | `src/perception/registry.py` + `src/perception/protocol.py` + `src/locomotion/gait_controller.py` | exact composite |
| `src/locomotion/controller_dispatch.py` | utility | transform + request-response | `src/locomotion/actions.py` + `src/bridge/sim_bridge.py` + `src/bridge/multi_bridge.py` | exact composite |
| `src/locomotion/env.py` | service / environment | request-response + transform | `src/locomotion/env.py` existing reset/step/info path | exact self-modification |
| `src/bridge/sim_bridge.py` | service / bridge | request-response + transform | `src/bridge/sim_bridge.py` existing velocity-to-control path | exact self-modification |
| `src/bridge/multi_bridge.py` | service / bridge | request-response + transform | `src/bridge/multi_bridge.py` existing per-robot gait path | exact self-modification |
| `tests/locomotion/test_locomotion_controller_registry.py` | test | request-response | `tests/perception/test_registry.py` | exact |
| `tests/locomotion/test_locomotion_controller_protocol.py` | test | transform | `tests/locomotion/test_gait_controller.py` + `tests/perception/test_protocol_contracts.py` style | role-match |
| `tests/locomotion/test_controller_dispatch.py` | test | transform | `tests/locomotion/test_argus_go2_env_action_modes.py` | exact |
| Existing test extensions: `tests/locomotion/test_argus_go2_env_contract.py`, `tests/bridge/test_sim_bridge.py`, `tests/bridge/test_multi_bridge.py` | test | request-response + transform | same files' existing contract tests | exact self-modification |

## Pattern Assignments

### `src/locomotion/controllers.py` (service/model/registry, request-response + transform)

**Analogs:** `src/perception/registry.py`, `src/perception/protocol.py`, `src/locomotion/gait_controller.py`, `src/locomotion/gait_params.py`

**Imports pattern** — keep registry lightweight; use stdlib + NumPy + local locomotion imports only. Do not import MuJoCo, Gymnasium, torch, RL/MPC libraries, or bridge modules at registry import time.

Source: `src/perception/registry.py` lines 30-38:
```python
from __future__ import annotations

import importlib
import logging
from typing import Any

from src.perception.types import DetectorInput

logger = logging.getLogger(__name__)
```

Source: `src/perception/protocol.py` lines 27-35:
```python
from __future__ import annotations

import contextlib
from typing import Protocol, runtime_checkable

import numpy as np

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import Detections2D, Detections3D, DetectorInput
```

Source: `src/locomotion/gait_params.py` lines 4-8:
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class GaitParams:
```

**Protocol pattern** — define a runtime-checkable structural protocol with class-level capability/schema metadata and lifecycle methods. Mirror the perception protocol style, but shape methods around `reset(seed)` and `compute(observation, command, dt)`.

Source: `src/perception/protocol.py` lines 38-55:
```python
@runtime_checkable
class DetectorProtocol(Protocol):
    """Contract for every 2D object detector backend.

    MANDATORY `CAPABILITIES` keys (enforced by DetectorRegistry.register in Plan 03):
      framework: str                 -- "ultralytics" | "transformers" | "onnxruntime" | "subprocess"
      license: str                   -- SPDX string, e.g. "AGPL-3.0" | "Apache-2.0" | "CC-BY-NC-4.0"
      cpu_latency_hint_ms: int       -- p50 hint, replaced by live metrics in Phase 6
      outputs_3d_natively: bool      -- if True, DetectorWorker (Phase 2) bypasses lifter
      input_type: DetectorInput      -- RGB_ONLY | RGBD | RGB_TEXT_PROMPT

    A backend missing any of these keys MUST fail registration at import time.
    """

    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def process_frame(self, frame: SensorFrame) -> Detections2D:
```

Source: `src/perception/protocol.py` lines 65-80 and 98-109:
```python
    def reset(self) -> None:
        """Clear any accumulated state (rolling metrics, trackers, etc.)."""
        ...

    def warmup(self, dummy_frame: SensorFrame) -> None:
        """Run one inference on a representative frame to eliminate first-call stall.
```

```python
    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """Probe whether this backend can run in the current environment (D-05).

        Returns (True, None) when dependencies are satisfied.
        Returns (False, "<install hint>") when not -- the registry surfaces the
        hint verbatim. Examples:
          (False, "pip install ultralytics>=8.4.24")
          (False, "run scripts/setup_boxer_subprocess.sh")
        The registry NEVER invents hint text.
        """
        ...
```

**Capability validation pattern** — copy mandatory-key validation and deterministic errors. Adapt required keys to controller metadata: `family`, `action_mode`, `deterministic`, `observation_expectation`, `command_limits`, `cpu_latency_hint_ms`, `sim_supported`, `hardware_supported`, `model_requirements`, `multi_robot_supported`, and reproducibility fields.

Source: `src/perception/registry.py` lines 41-60:
```python
_DETECTOR_REQUIRED_KEYS = (
    "framework",
    "license",
    "cpu_latency_hint_ms",
    "outputs_3d_natively",
    "input_type",
)
_DETECTOR_TYPED_KEYS: dict[str, type] = {
    "input_type": DetectorInput,
}

_DETECTION_3D_REQUIRED_KEYS = (
    "requires_depth",
    "requires_point_cloud",
    "outputs_oriented",
    "license",
)
_DETECTION_3D_TYPED_KEYS: dict[str, type] = {}
```

Source: `src/perception/registry.py` lines 63-94:
```python
def _validate_capabilities(
    name: str,
    klass: type,
    required_keys: tuple[str, ...],
    typed_keys: dict[str, type],
    kind: str,
) -> None:
    """Enforce D-06 mandatory-key contract at register() time.

    Raises ValueError with a deterministic sorted message if any key is missing
    or has the wrong type.
    """
    caps = getattr(klass, "CAPABILITIES", None)
    if not isinstance(caps, dict):
        raise ValueError(
            f"{kind} '{name}' missing CAPABILITIES dict on {klass.__qualname__}. "
            f"Per CONTEXT.md D-06, every backend must declare CAPABILITIES."
        )
    missing = sorted(k for k in required_keys if k not in caps)
    if missing:
        raise ValueError(
            f"{kind} '{name}' ({klass.__qualname__}) missing CAPABILITIES keys: "
            f"{missing}. Required: {list(required_keys)}."
        )
    for key, expected_type in typed_keys.items():
        value = caps[key]
        if not isinstance(value, expected_type):
            raise ValueError(
                f"{kind} '{name}' CAPABILITIES['{key}'] must be "
                f"{expected_type.__name__}, got {type(value).__name__} ({value!r})."
            )
```

**Lazy loading and availability pattern** — copy this exactly for controller registry class paths and placeholder availability probes. Placeholder controllers must return `(False, reason)` from `available()` and `ControllerRegistry.create()` must fail before constructing them.

Source: `src/perception/registry.py` lines 96-132:
```python
def _load_class(class_path: str) -> type | None:
    """Lazily import and return a class from its dotted path.

    Returns None if the module or class cannot be found. Callers use None
    to decide whether the backend is importable in the current environment.
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.debug("Cannot load %s: %s", class_path, exc)
        return None


def _probe_availability(klass: type) -> tuple[bool, str | None]:
    """Call @classmethod available() per CONTEXT.md D-05.

    If the backend class doesn't expose available() (legacy / third-party),
    default to (True, None) -- we've already imported it successfully.
    """
    probe = getattr(klass, "available", None)
    if probe is None:
        return True, None
    try:
        result = probe()
    except Exception as exc:  # defensive: a misbehaving probe must not crash the registry
        logger.warning("available() probe failed for %s: %s", klass.__qualname__, exc)
        return False, f"available() probe raised: {exc}"
    if not (isinstance(result, tuple) and len(result) == 2):
        logger.warning(
            "available() for %s must return (bool, str | None); got %r",
            klass.__qualname__,
            result,
        )
        return False, f"available() returned malformed result: {result!r}"
    return bool(result[0]), (None if result[1] is None else str(result[1]))
```

**Registry listing/create pattern** — copy list/create shape, but add the unavailable-at-create guard. `list_controllers()` should include `name`, `display`, `available`, `reason` when unavailable, copied `capabilities`, and copied `parameter_schema`.

Source: `src/perception/registry.py` lines 155-199:
```python
    @classmethod
    def list_backends(cls) -> list[dict]:
        """List all registered detectors with availability + capability metadata.

        Plan 05-05 D-04: honors any ``set_available`` override (session-scoped,
        used by the pool's crash handler to mark a crashed backend unavailable
        until the process restarts). The override ONLY applies when the class
        loads successfully — if the dotted class path cannot be resolved, we
        still surface ``available=False`` with a "Cannot load ..." reason,
        because evaluating the override on a missing class would be bogus.
        """
        result: list[dict] = []
        for name, info in list(cls._backends.items()):
            entry: dict[str, Any] = {"name": name, "display": info["display"]}
            klass = _load_class(info["class_path"])
            if klass is None:
                entry["available"] = False
                entry["reason"] = f"Cannot load {info['class_path']}"
                entry["capabilities"] = {}
                entry["parameter_schema"] = {}
            else:
                override = info.get("_override_available")
                if override is not None:
                    available, reason = override
                    entry["available"] = bool(available)
                    if not available:
                        entry["reason"] = reason or (
                            "Marked unavailable by set_available()."
                        )
                    entry["capabilities"] = dict(getattr(klass, "CAPABILITIES", {}))
                    entry["parameter_schema"] = dict(
                        getattr(klass, "PARAMETER_SCHEMA", {})
                    )
                else:
                    available, reason = _probe_availability(klass)
                    entry["available"] = available
                    if not available:
                        entry["reason"] = reason or (
                            f"{klass.__qualname__}.available() reported unavailable"
                        )
                    entry["capabilities"] = dict(getattr(klass, "CAPABILITIES", {}))
                    entry["parameter_schema"] = dict(
                        getattr(klass, "PARAMETER_SCHEMA", {})
                    )
            result.append(entry)
        return result
```

Source: `src/perception/registry.py` lines 201-218:
```python
    @classmethod
    def create(cls, name: str | None = None, **kwargs: Any) -> Any:
        """Instantiate a detector backend by name.

        Raises ValueError for unknown names, ImportError for unloadable classes.
        """
        if name is None:
            name = cls._default
        if name not in cls._backends:
            raise ValueError(
                f"Unknown detector backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )
        info = cls._backends[name]
        klass = _load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load detector class: {info['class_path']}")
        return klass(**kwargs)
```

**Decorator registration pattern** — use `@locomotion_controller(name="analytical_trot", display="Analytical Trot")` or equivalent; compute class path from module and qualname.

Source: `src/perception/registry.py` lines 331-347:
```python
def detector_backend(name: str, display: str):
    """Decorator: register a class as a DetectorProtocol backend.

    Usage::

        @detector_backend(name="yolov11", display="YOLOv11-nano")
        class YOLOv11Backend(TorchBackendMixin):
            CAPABILITIES = {...}
            ...
    """

    def decorator(klass: type) -> type:
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        DetectorRegistry.register(name, display, class_path, klass)
        return klass

    return decorator
```

**Analytical adapter pattern** — the baseline wrapper must delegate to existing gait math without reordering, clipping, or retiming beyond existing controller behavior.

Source: `src/locomotion/gait_controller.py` lines 35-41:
```python
    def __init__(self, params: GaitParams | None = None) -> None:
        self._params = params or GaitParams()
        self._phase: float = 0.0  # 0.0 to 1.0

    def compute(
        self, vx: float, vy: float, omega: float, dt: float,
    ) -> np.ndarray:
```

Source: `src/locomotion/gait_controller.py` lines 55-68:
```python
        # Input validation: clamp to safe ranges
        dt = float(np.clip(dt, 0.001, 1.0))
        vx = float(np.clip(vx, -p.max_speed, p.max_speed))
        vy = float(np.clip(vy, -p.max_speed, p.max_speed))
        omega = float(np.clip(omega, -3.0, 3.0))

        # Clamp speed
        speed = min(float(np.sqrt(vx ** 2 + vy ** 2)), p.max_speed)

        # Advance gait phase only when moving
        if speed > 0.01 or abs(omega) > 0.01:
            self._phase = (self._phase + p.frequency * dt) % 1.0

        ctrl = np.zeros(12)
```

Source: `src/locomotion/gait_controller.py` lines 70-86:
```python
        for leg_idx in range(4):
            # Determine phase offset for this leg
            if leg_idx in self.PAIR_A:
                leg_phase = self._phase
            else:
                leg_phase = (self._phase + 0.5) % 1.0

            hip, thigh, calf = self._leg_targets(
                leg_idx, leg_phase, vx, vy, omega, speed,
            )

            base = leg_idx * 3
            ctrl[base] = hip
            ctrl[base + 1] = thigh
            ctrl[base + 2] = calf

        return ctrl
```

**Dataclass configuration/result pattern** — use frozen dataclasses for command/result/capability metadata where possible, matching existing locomotion config style.

Source: `src/locomotion/gait_params.py` lines 7-17:
```python
@dataclass(frozen=True)
class GaitParams:
    """Tunable parameters for TrotGaitController.

    Default values are derived from the Go2 mujoco_menagerie keyframe
    and community controller experience. The standing pose uses the
    keyframe joint angles (0, 0.9, -1.8) rather than the older
    code values (0, 0.8, -1.5).
    """

    frequency: float = 3.0
```

---

### `src/locomotion/controller_dispatch.py` (utility, transform + request-response)

**Analogs:** `src/locomotion/actions.py`, `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`

**Imports pattern** — use NumPy and local locomotion controller models; keep MuJoCo out of helpers unless passed as opaque data objects.

Source: `src/locomotion/actions.py` lines 1-10:
```python
"""Action mode spaces and decoding helpers for Go2 locomotion benchmarks."""

from collections.abc import Sequence
from typing import Final

import numpy as np
from gymnasium import spaces

from src.locomotion.gait_controller import TrotGaitController
```

**Target validation pattern** — copy finite exact-shape validation and reuse it for all controller outputs before `data.ctrl` writes.

Source: `src/locomotion/actions.py` lines 125-148:
```python
def _as_finite_vector(action: Sequence[float] | np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """Convert *action* to a finite float64 vector with an exact shape."""
    vector = np.asarray(action, dtype=np.float64)
    if vector.shape != shape:
        raise ValueError(f"Action must have shape {shape}, got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError("Action values must be finite")
    return vector


def _as_bounded_vector(
    action: Sequence[float] | np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
) -> np.ndarray:
    vector = _as_finite_vector(action, low.shape)
    if np.any(vector < low.astype(np.float64)) or np.any(vector > high.astype(np.float64)):
        raise ValueError("Action values must be within the action space bounds")
    return vector


def _ensure_decoded_control(control: Sequence[float] | np.ndarray) -> np.ndarray:
    """Validate decoded controller output before it can reach physics controls."""
    return _as_finite_vector(control, (12,))
```

**Single-robot control application pattern** — write full 12-element target into `data.ctrl[:]`; keep stepping in the caller.

Source: `src/bridge/sim_bridge.py` lines 149-155:
```python
        if action is not None:
            self._data.ctrl[:] = action
        else:
            # Convert velocity command to joint targets for a simple walk
            ctrl = self._velocity_to_ctrl()
            self._data.ctrl[:] = ctrl
```

**Multi-robot control application pattern** — for indexed multi-robot actuators, write per-actuator values by index. The helper should accept `ctrl_indices` for multi-robot callers.

Source: `src/bridge/multi_bridge.py` lines 215-219:
```python
        # Apply velocity-to-ctrl for each robot
        for robot_id in self._config.robot_ids:
            ctrl = self._velocity_to_ctrl(robot_id)
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = ctrl[i]
```

**Velocity command extraction pattern** — preserve the current defaulting behavior when velocity arrays are short.

Source: `src/bridge/sim_bridge.py` lines 197-207:
```python
    def _velocity_to_ctrl(self) -> np.ndarray:
        """Convert buffered velocity to joint position targets.

        Uses TrotGaitController for proper trot gait with position-controlled
        actuators, producing actual locomotion via diagonal pair alternation
        and differential stride turning.
        """
        dt = self._dt  # self._dt already includes sim_steps_per_frame
        vx = float(self._linear_vel[0]) if len(self._linear_vel) > 0 else 0.0
        vy = float(self._linear_vel[1]) if len(self._linear_vel) > 1 else 0.0
        return self._gait.compute(vx, vy, self._angular_vel, dt)
```

Source: `src/bridge/multi_bridge.py` lines 447-463:
```python
    def _velocity_to_ctrl(self, robot_id: str) -> np.ndarray:
        """Convert buffered velocity to 12-element joint position targets.

        Uses TrotGaitController for proper trot gait with position-controlled
        actuators, matching MuJoCoBridge._velocity_to_ctrl() behaviour.

        Args:
            robot_id: Which robot's velocity buffer to read.

        Returns:
            (12,) float64 joint position targets.
        """
        linear, angular = self._velocities[robot_id]
        dt = self._dt  # self._dt already includes sim_steps_per_frame
        vx = float(linear[0]) if len(linear) > 0 else 0.0
        vy = float(linear[1]) if len(linear) > 1 else 0.0
        return self._gaits[robot_id].compute(vx, vy, angular, dt)
```

---

### `src/locomotion/env.py` (service/environment, request-response + transform)

**Analog:** `src/locomotion/env.py` existing reset/step/info path

**Config pattern** — add controller selection alongside existing dataclass config fields. Keep default scenario/action-mode unchanged.

Source: `src/locomotion/env.py` lines 17-25:
```python
@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    model_dir: str | None = None
    sim_steps_per_frame: int = 10
    max_episode_steps: int = 500
    render_mode: str | None = None
    heightfield_size: int = 16
```

**Validation/init pattern** — preserve config validation and action/observation space setup. Add controller creation after validation without importing MuJoCo.

Source: `src/locomotion/env.py` lines 33-58:
```python
    def __init__(self, config: ArgusGo2EnvConfig | None = None) -> None:
        self.config = config or ArgusGo2EnvConfig()
        if self.config.sim_steps_per_frame < 1:
            raise ValueError("sim_steps_per_frame must be >= 1")
        if self.config.max_episode_steps < 1:
            raise ValueError("max_episode_steps must be >= 1")
        if self.config.heightfield_size > 64:
            raise ValueError("heightfield_size must be <= 64")

        self.action_space = build_action_space(self.config.action_mode)
        self.observation_space = build_observation_space()
        self.render_mode = self.config.render_mode

        self._command = np.zeros(3, dtype=np.float32)
        self._previous_action = np.zeros(12, dtype=np.float32)
        self._step_count = 0
        self._seed: int | None = None
        self._last_seed: int | None = None
        self._scenario_sample: ScenarioSample | None = None
        self._model: Any = None
        self._data: Any = None
        self._renderer: Any = None
        self._dt = 0.002 * self.config.sim_steps_per_frame
        self._active_push: dict[str, float] | None = None
        self._gait = TrotGaitController()
```

**Reset metadata pattern** — reset per-instance state and return observation plus info. Add controller reset here and include full controller metadata in reset info.

Source: `src/locomotion/env.py` lines 59-90:
```python
    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the episode and return an observation plus reproducibility info."""
        super().reset(seed=seed)
        self._seed = seed
        self._last_seed = seed
        self._scenario_sample = sample_scenario(self.config.scenario_id, self.np_random,
                                                heightfield_size=self.config.heightfield_size)
        if self._model is not None and self._data is not None and self._is_real_mujoco_model():
            self._model = None
            self._data = None
            self._dt = 0.002 * self.config.sim_steps_per_frame
        self._step_count = 0
        first_command = self._scenario_sample.command_schedule[0]
        self._command = np.array(
            [first_command["vx"], first_command["vy"], first_command["omega"]],
            dtype=np.float32,
        )
        self._previous_action = np.zeros(12, dtype=np.float32)
        self._active_push = None
        self._gait = TrotGaitController()

        self._try_initialize_mujoco()
        self._reset_mujoco_state()

        observation = extract_observation(self._data, self._command, self._previous_action)
        return observation, self._info()
```

**Step dispatch pattern** — preserve Gymnasium five-tuple. Replace direct `decode_action(..., self._gait, ...)` for velocity-controller modes with shared dispatch while keeping direct joint/residual decoding behavior if still needed.

Source: `src/locomotion/env.py` lines 91-126:
```python
    def step(
        self,
        action: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Apply a mode-specific action and return the Gymnasium five-tuple."""
        command = self._command
        if self.config.action_mode != ACTION_MODE_VELOCITY:
            command = self._command_at_time(self._current_sim_time())
        ctrl = decode_action(
            action,
            self.config.action_mode,
            self._gait,
            self._dt,
            command,
        )
        if self.config.action_mode == ACTION_MODE_VELOCITY:
            self._command = np.asarray(action, dtype=np.float32).copy()
        else:
            self._command = command
        self._previous_action = ctrl.astype(np.float32)

        if self._data is not None:
            import mujoco

            self._data.ctrl[:] = self._previous_action
            self._apply_push_disturbance()
            for _ in range(self.config.sim_steps_per_frame):
                mujoco.mj_step(self._model, self._data)

        self._step_count += 1
        observation = extract_observation(self._data, self._command, self._previous_action)
        reward = 0.0
        terminated = False
        truncated = self._step_count >= self.config.max_episode_steps
        info = self._info()
        return observation, reward, terminated, truncated, info
```

**Info metadata pattern** — extend `_info()` rather than creating a separate metadata side channel. Full metadata belongs at reset/selection changes; compact `controller_id` and `action_mode` belong per step.

Source: `src/locomotion/env.py` lines 254-267:
```python
    def _info(self) -> dict[str, Any]:
        sample = self._scenario_sample
        return {
            "seed": self._last_seed,
            "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "step_count": self._step_count,
            "sim_time": self._current_sim_time(),
            "spawn_pose": sample.spawn_pose if sample is not None else None,
            "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
            "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
            "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
            "active_push": dict(self._active_push) if self._active_push is not None else None,
        }
```

---

### `src/bridge/sim_bridge.py` (service/bridge, request-response + transform)

**Analog:** `src/bridge/sim_bridge.py` existing velocity-to-control and lifecycle

**Imports pattern** — replace `TrotGaitController` import with controller registry/dispatch imports; preserve bridge config, sensor types, gait params, and XML patcher imports as needed.

Source: `src/bridge/sim_bridge.py` lines 10-21:
```python
import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix, IMUReading
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.xml_patcher import patch_actuators_to_position, patch_actuators_to_position_with_floor
```

**Lifecycle state pattern** — keep public lifecycle and `SensorFrame` return type unchanged. Controller instance should remain per-bridge instance and reset at start/stop boundaries as appropriate.

Source: `src/bridge/sim_bridge.py` lines 42-58:
```python
    def __init__(self, config: MuJoCoEnvConfig | None = None) -> None:
        self._config = config or MuJoCoEnvConfig()
        self._model: Any = None
        self._data: Any = None
        self._renderer: Any = None
        self._step_count: int = 0
        self._dt: float = 0.0
        self._linear_vel: np.ndarray = np.zeros(2)
        self._angular_vel: float = 0.0
        # Camera ID (added programmatically)
        self._cam_id: int = -1
        # Trot gait controller for locomotion
        self._gait = TrotGaitController()
        # IMU sensor addresses (populated in start() if sensors exist)
        self._has_imu: bool = False
        self._accel_adr: int = 0
        self._gyro_adr: int = 0
```

**Start/standing control pattern** — preserve initial standing control application; source standing targets from default registered controller through shared dispatch or direct baseline wrapper.

Source: `src/bridge/sim_bridge.py` lines 109-118:
```python
        # Set initial standing pose (skip the 7 free-joint qpos: 3 pos + 4 quat)
        if self._model.nq >= 19:  # 7 (freejoint) + 12 (actuators)
            self._data.qpos[7:19] = STANDING_QPOS

        # Settle the robot (let it land on ground)
        standing = self._gait.compute(0.0, 0.0, 0.0, 0.0)
        for _ in range(200):
            self._data.ctrl[:] = standing
            mujoco.mj_step(self._model, self._data)
```

**Step return contract pattern** — do not change method signature or return type. Only replace internal velocity-to-control branch with dispatch helper.

Source: `src/bridge/sim_bridge.py` lines 134-172:
```python
    def step(self, action: np.ndarray | None = None) -> SensorFrame:
        """Step the simulation and return a new SensorFrame.

        Args:
            action: Optional 12-element joint position target. If None,
                uses the velocity command from set_velocity().

        Returns:
            SensorFrame with RGB, depth, and ground-truth pose.
        """
        import mujoco

        if self._model is None:
            raise RuntimeError("Bridge not started -- call start() first")

        if action is not None:
            self._data.ctrl[:] = action
        else:
            # Convert velocity command to joint targets for a simple walk
            ctrl = self._velocity_to_ctrl()
            self._data.ctrl[:] = ctrl

        # Step physics multiple times per frame, collecting IMU at each sub-step
        imu_readings: list[IMUReading] = []
        sim_time_base = self._step_count * self._dt

        for i in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

            if self._has_imu:
                accel = self._data.sensordata[self._accel_adr:self._accel_adr + 3].copy()
                gyro = self._data.sensordata[self._gyro_adr:self._gyro_adr + 3].copy()
                t = sim_time_base + (i + 1) * self._model.opt.timestep
                imu_readings.append(IMUReading(accel=accel, gyro=gyro, timestamp=t))

        self._step_count += 1
        frame = self._capture_frame()
        frame.imu_readings = imu_readings
        return frame
```

**Error handling pattern** — preserve pre-start error semantics.

Source: `src/bridge/sim_bridge.py` lines 144-147:
```python
        import mujoco

        if self._model is None:
            raise RuntimeError("Bridge not started -- call start() first")
```

---

### `src/bridge/multi_bridge.py` (service/bridge, request-response + transform)

**Analog:** `src/bridge/multi_bridge.py` existing per-robot gait and control application

**Imports pattern** — replace `TrotGaitController` with registry/dispatch imports. Keep local bridge imports and NumPy.

Source: `src/bridge/multi_bridge.py` lines 9-19:
```python
import logging
from typing import Any

import numpy as np

from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.scene_builder import build_two_robot_office_scene, build_two_robot_scene
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
```

**Per-robot state isolation pattern** — create one controller instance per robot, matching current `_gaits` dict. Do not share singleton controllers across robot ids.

Source: `src/bridge/multi_bridge.py` lines 56-64:
```python
        # Velocity buffers
        self._velocities: dict[str, tuple[np.ndarray, float]] = {
            rid: (np.zeros(2), 0.0) for rid in self._config.robot_ids
        }

        # Trot gait controllers (one per robot)
        self._gaits: dict[str, TrotGaitController] = {
            rid: TrotGaitController() for rid in self._config.robot_ids
        }
```

**Start/standing per-robot application pattern** — preserve qpos/standing initialization and per-actuator ctrl write.

Source: `src/bridge/multi_bridge.py` lines 155-172:
```python
        # Set initial standing pose and heading for both robots
        import math
        n_robots = len(self._config.robot_ids)
        for i, robot_id in enumerate(self._config.robot_ids):
            qstart = self._qpos_starts[robot_id]
            # qpos layout: [x, y, z, qw, qx, qy, qz, joint1..joint12]
            # Set yaw: spread robots evenly around 360°
            yaw = (2 * math.pi * i) / n_robots
            self._data.qpos[qstart + 3] = math.cos(yaw / 2)  # qw
            self._data.qpos[qstart + 4] = 0.0                 # qx
            self._data.qpos[qstart + 5] = 0.0                 # qy
            self._data.qpos[qstart + 6] = math.sin(yaw / 2)   # qz
            self._data.qpos[qstart + 7 : qstart + 19] = STANDING_QPOS
            # Set ctrl to standing via gait controller (zero velocity = standing)
            standing = self._gaits[robot_id].compute(0.0, 0.0, 0.0, 0.0)
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = standing[i]
```

**Step return contract pattern** — keep `step() -> dict[str, SensorFrame]`; only replace velocity-to-control internals.

Source: `src/bridge/multi_bridge.py` lines 204-224:
```python
    def step(self) -> dict[str, SensorFrame]:
        """Step the simulation and return SensorFrames for both robots.

        Returns:
            Dict mapping robot_id to SensorFrame.
        """
        import mujoco

        if self._model is None:
            raise RuntimeError("Bridge not started -- call start() first")

        # Apply velocity-to-ctrl for each robot
        for robot_id in self._config.robot_ids:
            ctrl = self._velocity_to_ctrl(robot_id)
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = ctrl[i]

        # Step physics
        for _ in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)
```

**Frame capture return pattern** — preserve final dict capture shape.

Source: `src/bridge/multi_bridge.py` lines 270-275:
```python
        # Capture frames
        frames = {}
        for robot_id in self._config.robot_ids:
            frames[robot_id] = self._capture_frame(robot_id)
        self._last_frames = frames
        return frames
```

---

### `tests/locomotion/test_locomotion_controller_registry.py` (test, request-response)

**Analog:** `tests/perception/test_registry.py`

**Imports/test isolation pattern** — use autouse fixture to clear registries before/after each test and pop any decorator-registered modules if needed.

Source: `tests/perception/test_registry.py` lines 41-68:
```python
@pytest.fixture(autouse=True)
def _clean_registries():
    """Isolate tests -- clear both registries before and after each test.

    W-02 fix (Plan 02-12): after teardown, pop sys.modules entries for the
    backends + lifters packages so the next test's explicit import re-triggers
    @detector_backend and @detection_3d decorator registration. Without this,
    @detector_backend runs once at first module import; later _clear() wipes
    the registry but sys.modules keeps the module cached, so re-importing is
    a no-op and subsequent tests see an empty registry.
```

```python
    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
```

**Lightweight import test pattern** — assert registry import does not pull heavy deps.

Source: `tests/perception/test_registry.py` lines 116-134:
```python
def test_registry_module_does_not_import_heavy_deps():
    """Pitfall P9: registry import must not pull torch / ultralytics / transformers."""
    # Record pre-state; registry may already be loaded from the autouse fixture.
    pre_heavy = {fw: fw in sys.modules for fw in HEAVY_DEPS}
    # Re-import registry fresh to measure the delta.
    for mod in list(sys.modules):
        if mod.startswith("src.perception.registry"):
            del sys.modules[mod]
    pre = set(sys.modules.keys())
    import src.perception.registry  # noqa: F401

    post = set(sys.modules.keys())
    delta = post - pre
    for fw in HEAVY_DEPS:
        newly_added = fw in delta and not pre_heavy[fw]
        assert not newly_added, (
            f"Importing src.perception.registry pulled {fw} into sys.modules. "
            f"Pitfall P9: heavy deps must be reached via lazy class-path loading only."
        )
```

**Default registry test pattern** — adapt to `ControllerRegistry.get_default() == "analytical_trot"`.

Source: `tests/perception/test_registry.py` lines 137-146:
```python
def test_detector_registry_default_is_yolov11():
    from src.perception.registry import DetectorRegistry

    assert DetectorRegistry.get_default() == "yolov11"


def test_detection_3d_registry_default_is_median_depth():
    from src.perception.registry import Detection3DRegistry

    assert Detection3DRegistry.get_default() == "median_depth"
```

**Capability validation tests** — copy missing/wrong/accepted patterns.

Source: `tests/perception/test_registry.py` lines 149-181:
```python
def test_register_rejects_missing_capabilities_dict():
    from src.perception.registry import DetectorRegistry

    class NoCaps:
        pass

    with pytest.raises(ValueError, match="CAPABILITIES"):
        DetectorRegistry.register("bad", "Bad", "x.NoCaps", NoCaps)


def test_register_lists_all_missing_keys_in_sorted_order():
    from src.perception.registry import DetectorRegistry

    class Partial:
        CAPABILITIES = {"framework": "ultralytics", "license": "MIT"}

    with pytest.raises(ValueError) as exc_info:
        DetectorRegistry.register("partial", "Partial", "x.Partial", Partial)
    msg = str(exc_info.value)
    # All three missing keys named
    for key in ("cpu_latency_hint_ms", "outputs_3d_natively", "input_type"):
        assert key in msg, f"expected {key} in error message: {msg}"


def test_register_rejects_wrong_input_type_type():
    from src.perception.registry import DetectorRegistry

    class WrongType:
        CAPABILITIES = _full_det_caps(input_type="rgb_only")  # string, not enum

    with pytest.raises(ValueError, match="input_type") as exc_info:
        DetectorRegistry.register("wrong", "Wrong", "x.WrongType", WrongType)
    assert "DetectorInput" in str(exc_info.value)
```

**Availability/unavailable placeholder tests** — copy available-probe and unloadable-class patterns; add create-time unavailable assertion for residual/direct/MPC/WBC placeholders.

Source: `tests/perception/test_registry.py` lines 201-221:
```python
def test_list_backends_uses_available_probe():
    """D-05: registry must call klass.available() and surface the returned reason verbatim."""
    from src.perception.registry import DetectorRegistry

    class Probed:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

        @classmethod
        def available(cls):
            return False, "pip install special>=1.2.3"

    # Expose the class on the test module so importlib can resolve the dotted path.
    current_module = sys.modules[__name__]
    current_module.Probed = Probed  # type: ignore[attr-defined]
    DetectorRegistry.register("probed", "Probed", f"{__name__}.Probed", Probed)

    listed = DetectorRegistry.list_backends()
    assert len(listed) == 1
    assert listed[0]["available"] is False
    assert listed[0]["reason"] == "pip install special>=1.2.3"
```

Source: `tests/perception/test_registry.py` lines 239-253:
```python
def test_list_backends_handles_unloadable_class_path():
    from src.perception.registry import DetectorRegistry

    class Loadable:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    DetectorRegistry.register(
        "ghost", "Ghost", "does.not.exist.Module.Backend", Loadable
    )
    listed = DetectorRegistry.list_backends()
    entry = listed[0]
    assert entry["available"] is False
    assert "Cannot load" in entry["reason"]
```

**Decorator and independence pattern** — use class-definition decorator registration tests for analytical baseline and placeholders.

Source: `tests/perception/test_registry.py` lines 275-285:
```python
def test_detector_backend_decorator_registers_at_class_definition():
    from src.perception.registry import DetectorRegistry, detector_backend

    @detector_backend(name="decorated", display="Decorated")
    class Decorated:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    listed = DetectorRegistry.list_backends()
    names = [e["name"] for e in listed]
    assert "decorated" in names
```

---

### `tests/locomotion/test_locomotion_controller_protocol.py` (test, transform)

**Analogs:** `tests/locomotion/test_gait_controller.py`, `src/perception/protocol.py`

**Output shape and finite target pattern** — copy gait tests for `(12,)` and finite output. Apply to `AnalyticalTrotController.compute(...)` result action.

Source: `tests/locomotion/test_gait_controller.py` lines 15-38:
```python
class TestComputeOutputShape:
    """compute() returns an array of correct shape (12 joint targets)."""

    def test_returns_12_element_array(self):
        """compute returns a numpy array of shape (12,)."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.3, vy=0.0, omega=0.0, dt=0.02)

        assert isinstance(result, np.ndarray)
        assert result.shape == (12,)

    def test_returns_12_elements_with_all_inputs_nonzero(self):
        """compute returns (12,) even with lateral and angular inputs."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.5, vy=0.2, omega=0.8, dt=0.02)

        assert result.shape == (12,)

    def test_returns_12_elements_after_many_steps(self):
        """Shape is consistent across many timesteps."""
        ctrl = TrotGaitController()
        for _ in range(100):
            result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)
        assert result.shape == (12,)
```

**Standing pose / reset behavior pattern** — assert zero command produces standing values and reset isolates phase state.

Source: `tests/locomotion/test_gait_controller.py` lines 49-74:
```python
    def test_zero_velocity_returns_standing_angles(self):
        """compute(0, 0, 0, dt) returns standing hip/thigh/calf for all 4 legs."""
        params = GaitParams()
        ctrl = TrotGaitController(params)
        result = ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)

        for leg in range(4):
            base = leg * 3
            np.testing.assert_allclose(
                result[base], params.standing_hip, atol=1e-6,
                err_msg=f"Leg {leg} hip should be standing pose",
            )
            np.testing.assert_allclose(
                result[base + 1], params.standing_thigh, atol=1e-6,
                err_msg=f"Leg {leg} thigh should be standing pose",
            )
            np.testing.assert_allclose(
                result[base + 2], params.standing_calf, atol=1e-6,
                err_msg=f"Leg {leg} calf should be standing pose",
            )

    def test_zero_velocity_does_not_advance_phase(self):
        """Phase stays at 0.0 when speed and omega are both zero."""
        ctrl = TrotGaitController()
        ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)
        assert ctrl._phase == 0.0
```

**Behavior-equivalence pattern** — compare controller adapter output directly to a fresh `TrotGaitController().compute(...)` result.

Source: `tests/locomotion/test_argus_go2_env_action_modes.py` lines 211-220:
```python
def test_velocity_command_decode_uses_trot_gait_controller():
    """Velocity action decodes through TrotGaitController into finite joint targets."""
    gait = TrotGaitController()
    action = np.array([0.3, 0.1, 0.2], dtype=np.float32)

    decoded = decode_action(action, ACTION_MODE_VELOCITY, gait, DT, PREVIOUS_COMMAND)

    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))
```

Source: `tests/locomotion/test_argus_go2_env_action_modes.py` lines 249-258:
```python
    baseline = TrotGaitController().compute(
        float(PREVIOUS_COMMAND[0]),
        float(PREVIOUS_COMMAND[1]),
        float(PREVIOUS_COMMAND[2]),
        DT,
    )
    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))
    np.testing.assert_allclose(decoded, baseline + residual)
```

---

### `tests/locomotion/test_controller_dispatch.py` (test, transform)

**Analog:** `tests/locomotion/test_argus_go2_env_action_modes.py`

**Invalid target rejection pattern** — use parameterized shape/NaN tests; assert state/control sink is unchanged where applicable.

Source: `tests/locomotion/test_argus_go2_env_action_modes.py` lines 97-126:
```python
@pytest.mark.parametrize(
    ("mode", "bad_action", "message"),
    [
        (ACTION_MODE_VELOCITY, np.zeros(12, dtype=np.float32), "shape"),
        (ACTION_MODE_JOINT_POSITION, np.zeros(3, dtype=np.float32), "shape"),
        (ACTION_MODE_RESIDUAL_BASELINE, np.zeros(3, dtype=np.float32), "shape"),
        (ACTION_MODE_VELOCITY, np.array([np.nan, 0.0, 0.0], dtype=np.float32), "finite"),
        (
            ACTION_MODE_JOINT_POSITION,
            np.array([np.nan, 0.9, -1.8] * 4, dtype=np.float32),
            "finite",
        ),
        (ACTION_MODE_RESIDUAL_BASELINE, np.full(12, np.nan, dtype=np.float32), "finite"),
    ],
)
def test_env_rejects_invalid_actions_before_state_advances(mode, bad_action, message):
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode=mode))
    try:
        observation, _info = env.reset(seed=123)
        command_before = observation["command"].copy()
        previous_action_before = observation["previous_action"].copy()

        with pytest.raises(ValueError, match=message):
            env.step(bad_action)

        assert env.step_count == 0
        np.testing.assert_allclose(env._command, command_before)
        np.testing.assert_allclose(env._previous_action, previous_action_before)
    finally:
        env.close()
```

**Decode/dispatch finite-output pattern** — assert output shape, dtype, finite values.

Source: `tests/locomotion/test_argus_go2_env_action_modes.py` lines 223-233:
```python
def test_joint_position_decode_passes_through_caller_values():
    """Joint-position actions are validated and returned unchanged."""
    gait = TrotGaitController()
    action = np.array([0.0, 0.9, -1.8] * 4, dtype=np.float32)

    decoded = decode_action(action, ACTION_MODE_JOINT_POSITION, gait, DT, PREVIOUS_COMMAND)

    assert decoded.shape == (12,)
    assert decoded.dtype == np.float64
    assert np.all(np.isfinite(decoded))
    np.testing.assert_allclose(decoded, action)
```

**Unknown mode/error message pattern** — use deterministic messages listing available choices.

Source: `tests/locomotion/test_argus_go2_env_action_modes.py` lines 325-330:
```python
def test_unknown_action_mode_lists_available_modes():
    """Unknown action mode errors include available mode choices."""
    gait = TrotGaitController()

    with pytest.raises(ValueError, match="Available:"):
        decode_action(np.zeros(3, dtype=np.float32), "unknown_mode", gait, DT, PREVIOUS_COMMAND)
```

---

### Existing test extensions (test, request-response + transform)

**Analogs:** `tests/locomotion/test_argus_go2_env_contract.py`, `tests/bridge/test_sim_bridge.py`, `tests/bridge/test_multi_bridge.py`

**Env metadata tests** — extend existing reset/step info assertions with controller metadata. Reset should assert full metadata; step should assert compact controller attribution.

Source: `tests/locomotion/test_argus_go2_env_contract.py` lines 100-118:
```python
def test_reset_returns_observation_and_info():
    """reset(seed=...) returns a Gymnasium two-tuple and reproducibility info."""
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    try:
        obs, info = env.reset(seed=123)
    finally:
        env.close()

    assert isinstance(obs, dict)
    assert info["seed"] == 123
    assert info["scenario_id"] == "flat_ground"
    assert info["action_mode"] == "velocity_command"
    assert "sampled_parameters" in info
    assert "command_schedule" in info
    assert "disturbance_schedule" in info
    assert info["step_count"] == 0
    assert "sim_time" in info
```

Source: `tests/locomotion/test_argus_go2_env_contract.py` lines 120-139:
```python
def test_step_returns_gymnasium_five_tuple():
    """step(action) returns observation, reward, terminated, truncated, info."""
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    try:
        env.reset(seed=123)
        result = env.step(np.array([0.0, 0.0, 0.0], dtype=np.float32))
    finally:
        env.close()

    assert len(result) == 5
    obs, reward, terminated, truncated, info = result
    assert isinstance(obs, dict)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert info["seed"] == 123
    assert info["scenario_id"] == "flat_ground"
    assert info["action_mode"] == "velocity_command"
    assert info["step_count"] == 1
```

**Env fake-data/control-write test** — extend this mocked test to assert dispatch helper output is written before stepping and MuJoCo stepping remains env-owned.

Source: `tests/locomotion/test_argus_go2_env_contract.py` lines 226-243:
```python
def test_step_decodes_action_writes_ctrl_and_calls_mj_step_configured_count():
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode="joint_position", sim_steps_per_frame=3))
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    env._scenario_sample = None
    expected_ctrl = np.linspace(-0.1, 0.1, 12, dtype=np.float64)
    mj_step = MagicMock(side_effect=lambda _model, data: setattr(data, "time", data.time + 0.002))

    with patch("src.locomotion.env.decode_action", return_value=expected_ctrl) as decode_action_mock:
        with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
            obs, _reward, _terminated, _truncated, info = env.step(np.array([0.0] * 12, dtype=np.float32))

    decode_action_mock.assert_called_once()
    np.testing.assert_allclose(fake_data.ctrl.copy(), expected_ctrl)
    assert mj_step.call_count == env.config.sim_steps_per_frame
    assert info["sim_time"] == pytest.approx(fake_data.time)
    np.testing.assert_allclose(obs["qpos"], fake_data.qpos.astype(np.float32))
```

**Single bridge public contract tests** — extend unit tests without requiring MuJoCo by checking constructor/startless step and velocity buffering remain stable.

Source: `tests/bridge/test_sim_bridge.py` lines 21-51:
```python
class TestMuJoCoBridgeUnit:
    """Unit tests using mocked MuJoCo."""

    def test_import(self):
        """MuJoCoBridge can be imported."""
        assert MuJoCoBridge is not None

    def test_init_default_config(self):
        """Bridge initialises with default MuJoCoEnvConfig."""
        bridge = MuJoCoBridge()
        assert not bridge.is_running
        assert bridge.step_count == 0

    def test_init_custom_config(self):
        """Bridge accepts a custom config."""
        config = MuJoCoEnvConfig(model_path="custom/path.xml", target_step_hz=5.0)
        bridge = MuJoCoBridge(config)
        assert not bridge.is_running

    def test_step_without_start_raises(self):
        """Calling step() before start() raises RuntimeError."""
        bridge = MuJoCoBridge()
        with pytest.raises(RuntimeError, match="not started"):
            bridge.step()

    def test_set_velocity_buffers(self):
        """set_velocity stores the velocity command for next step."""
        bridge = MuJoCoBridge()
        bridge.set_velocity(np.array([1.0, 0.5]), 0.3)
        assert np.allclose(bridge._linear_vel, [1.0, 0.5])
        assert bridge._angular_vel == pytest.approx(0.3)
```

**Multi-bridge independence tests** — extend these to prove each robot has an independent controller instance and command/phase state does not leak.

Source: `tests/bridge/test_multi_bridge.py` lines 76-99:
```python
def test_mock_multi_bridge_start_returns_both_frames(mock_multi_bridge):
    """MockMultiRobotBridge.start() returns dict with both robot keys as SensorFrames."""
    frames = mock_multi_bridge.start()
    assert isinstance(frames, dict)
    assert "robot_a" in frames
    assert "robot_b" in frames
    assert isinstance(frames["robot_a"], SensorFrame)
    assert isinstance(frames["robot_b"], SensorFrame)


def test_mock_multi_bridge_independent_velocity(mock_multi_bridge):
    """Setting velocity only for robot_a moves it while robot_b stays put."""
    mock_multi_bridge.start()
    initial_b_pos = mock_multi_bridge._positions["robot_b"].copy()

    mock_multi_bridge.set_velocity("robot_a", np.array([1.0, 0.0]), 0.0)
    frames = mock_multi_bridge.step()

    # robot_a should have moved in x
    assert frames["robot_a"].ground_truth_pose[0, 3] > 0.0
    # robot_b should NOT have moved
    np.testing.assert_array_almost_equal(
        frames["robot_b"].ground_truth_pose[:3, 3], initial_b_pos
    )
```

Source: `tests/bridge/test_multi_bridge.py` lines 112-125:
```python
def test_mock_multi_bridge_step_count(mock_multi_bridge):
    """Step count increments correctly."""
    mock_multi_bridge.start()
    assert mock_multi_bridge.step_count == 0
    mock_multi_bridge.step()
    assert mock_multi_bridge.step_count == 1
    mock_multi_bridge.step()
    assert mock_multi_bridge.step_count == 2


def test_mock_multi_bridge_properties(mock_multi_bridge):
    """robot_ids and is_running properties work correctly."""
    assert mock_multi_bridge.robot_ids == ("robot_a", "robot_b")
    assert mock_multi_bridge.is_running is True
```

## Shared Patterns

### Lightweight plugin registries

**Source:** `src/perception/registry.py`
**Apply to:** `src/locomotion/controllers.py`, controller registry tests

Use class-path strings, `importlib`, and `available()` probes. Do not import heavy optional controller families just to list choices.

Source lines 13-15:
```python
Pitfall P9: this module imports ONLY stdlib + src.perception.types.DetectorInput.
Heavy deps (torch, ultralytics, transformers) are reached via lazy class-path
loading inside list_backends() / create() only.
```

Source lines 96-108:
```python
def _load_class(class_path: str) -> type | None:
    """Lazily import and return a class from its dotted path.

    Returns None if the module or class cannot be found. Callers use None
    to decide whether the backend is importable in the current environment.
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.debug("Cannot load %s: %s", class_path, exc)
        return None
```

### Deterministic registry errors

**Source:** `src/perception/registry.py`
**Apply to:** `ControllerRegistry.register()`, `ControllerRegistry.create()`, unavailable placeholder selection

Source lines 81-86:
```python
    missing = sorted(k for k in required_keys if k not in caps)
    if missing:
        raise ValueError(
            f"{kind} '{name}' ({klass.__qualname__}) missing CAPABILITIES keys: "
            f"{missing}. Required: {list(required_keys)}."
        )
```

Source lines 207-218:
```python
        if name is None:
            name = cls._default
        if name not in cls._backends:
            raise ValueError(
                f"Unknown detector backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )
        info = cls._backends[name]
        klass = _load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load detector class: {info['class_path']}")
        return klass(**kwargs)
```

### Target validation before physics controls

**Source:** `src/locomotion/actions.py`
**Apply to:** `ControllerResult` validation, `controller_dispatch.py`, bridge/env control application

Source lines 125-148:
```python
def _as_finite_vector(action: Sequence[float] | np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """Convert *action* to a finite float64 vector with an exact shape."""
    vector = np.asarray(action, dtype=np.float64)
    if vector.shape != shape:
        raise ValueError(f"Action must have shape {shape}, got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError("Action values must be finite")
    return vector
```

### Bridge API preservation

**Source:** `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`
**Apply to:** all bridge modifications

Single-robot bridge must keep `step(action: np.ndarray | None = None) -> SensorFrame`.

Source: `src/bridge/sim_bridge.py` lines 134-142:
```python
    def step(self, action: np.ndarray | None = None) -> SensorFrame:
        """Step the simulation and return a new SensorFrame.

        Args:
            action: Optional 12-element joint position target. If None,
                uses the velocity command from set_velocity().

        Returns:
            SensorFrame with RGB, depth, and ground-truth pose.
```

Multi-robot bridge must keep `step() -> dict[str, SensorFrame]`.

Source: `src/bridge/multi_bridge.py` lines 204-209:
```python
    def step(self) -> dict[str, SensorFrame]:
        """Step the simulation and return SensorFrames for both robots.

        Returns:
            Dict mapping robot_id to SensorFrame.
        """
```

### Per-instance controller state

**Source:** `src/bridge/multi_bridge.py`, `src/locomotion/gait_controller.py`
**Apply to:** `ArgusGo2Env`, `MuJoCoBridge`, `MultiRobotBridge`, controller protocol tests

Source: `src/bridge/multi_bridge.py` lines 61-64:
```python
        # Trot gait controllers (one per robot)
        self._gaits: dict[str, TrotGaitController] = {
            rid: TrotGaitController() for rid in self._config.robot_ids
        }
```

Source: `src/locomotion/gait_controller.py` lines 35-37:
```python
    def __init__(self, params: GaitParams | None = None) -> None:
        self._params = params or GaitParams()
        self._phase: float = 0.0  # 0.0 to 1.0
```

### Gymnasium metadata/info surface

**Source:** `src/locomotion/env.py`
**Apply to:** controller metadata integration in reset/step info

Source lines 88-90:
```python
        observation = extract_observation(self._data, self._command, self._previous_action)
        return observation, self._info()
```

Source lines 120-126:
```python
        self._step_count += 1
        observation = extract_observation(self._data, self._command, self._previous_action)
        reward = 0.0
        terminated = False
        truncated = self._step_count >= self.config.max_episode_steps
        info = self._info()
        return observation, reward, terminated, truncated, info
```

## No Analog Found

No planned file lacks an analog. Exact names for `src/locomotion/controllers.py` versus a `src/locomotion/controllers/` package and whether dispatch lives in a separate `controller_dispatch.py` remain planner choices, but the role/data-flow patterns all have strong local analogs.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | — | — | All expected files map to existing registry, locomotion, bridge, env, or test patterns. |

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src`, `/home/prannayag/pragnition/robotics/argus/tests`, project `.claude/skills`
**Files scanned:** 100+ source/test files listed; 14 files read in detail for extraction
**Primary analog files read:** `src/perception/registry.py`, `src/perception/protocol.py`, `src/slam/registry.py`, `src/locomotion/gait_controller.py`, `src/locomotion/gait_params.py`, `src/locomotion/actions.py`, `src/locomotion/env.py`, `src/bridge/sim_bridge.py`, `src/bridge/multi_bridge.py`, `tests/perception/test_registry.py`, `tests/locomotion/test_gait_controller.py`, `tests/locomotion/test_argus_go2_env_contract.py`, `tests/locomotion/test_argus_go2_env_action_modes.py`, `tests/bridge/test_sim_bridge.py`, `tests/bridge/test_multi_bridge.py`
**Pattern extraction date:** 2026-04-30
