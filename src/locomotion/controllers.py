"""Locomotion controller protocol, registry, and baseline adapters.

Phase 2 keeps controller selection behind a lightweight protocol/registry seam.
The analytical trot remains the default deterministic comparator; future residual,
direct-policy, MPC, and WBC families are discoverable but unavailable until their
required training/model-based-control infrastructure exists.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class LocomotionCommand:
    """Typed velocity command consumed by locomotion controllers."""

    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ControllerResult:
    """Validated controller action plus reproducibility metadata."""

    action: np.ndarray
    metadata: dict[str, Any]


@runtime_checkable
class LocomotionController(Protocol):
    """Pure action-mapper contract for locomotion controller instances."""

    CAPABILITIES: dict[str, Any]
    PARAMETER_SCHEMA: dict[str, Any]

    def reset(self, seed: int | None = None) -> None:
        """Reset any controller-local state for deterministic episode boundaries."""
        ...

    def compute(
        self,
        observation: dict[str, Any],
        command: LocomotionCommand,
        dt: float,
    ) -> ControllerResult:
        """Map observation, command, and dt into a 12-joint position target."""
        ...

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """Return whether this controller can be constructed in this environment."""
        ...


class UnavailableControllerError(RuntimeError):
    """Raised when a discoverable controller family is not yet runnable."""


def validate_controller_target(action: Any) -> np.ndarray:
    """Return a float64 `(12,)` action target or raise before downstream sinks.

    Controller outputs cross a trust boundary before bridge or environment control
    application. Keep the check deliberately narrow: exact Go2 joint target shape
    and finite numeric values.
    """

    target = np.asarray(action, dtype=np.float64)
    if target.shape != CONTROLLER_TARGET_SHAPE:
        raise ValueError(
            f"Controller target must have shape {CONTROLLER_TARGET_SHAPE}, got {target.shape}."
        )
    if not np.all(np.isfinite(target)):
        raise ValueError("Controller target must contain only finite values.")
    return target


def _stable_parameter_hash(parameter_summary: dict[str, Any]) -> str:
    payload = json.dumps(parameter_summary, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def controller_metadata(
    controller_id: str,
    display_name: str,
    capabilities: dict[str, Any],
    parameter_summary: dict[str, Any],
    available: bool,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build reproducible controller metadata for registry listings and results."""

    metadata: dict[str, Any] = {
        "controller_id": controller_id,
        "display_name": display_name,
        "family": capabilities["family"],
        "action_mode": capabilities["action_mode"],
        "deterministic": capabilities["deterministic"],
        "parameter_hash": _stable_parameter_hash(parameter_summary),
        "parameter_summary": dict(parameter_summary),
        "capabilities": dict(capabilities),
        "available": bool(available),
    }
    if reason:
        metadata["reason"] = reason
    return metadata


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


def _load_class(class_path: str) -> type | None:
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.debug("Cannot load locomotion controller %s: %s", class_path, exc)
        return None


def _probe_availability(klass: type) -> tuple[bool, str | None]:
    probe = getattr(klass, "available", None)
    if probe is None:
        return True, None
    try:
        result = probe()
    except Exception as exc:  # defensive: registry listing must not crash on bad probes
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


class ControllerRegistry:
    """Central registry for locomotion controller backends."""

    _controllers: dict[str, dict[str, Any]] = {}
    _default: str = "analytical_trot"

    @classmethod
    def register(cls, name: str, display: str, class_path: str, klass: type) -> None:
        """Register a controller class and validate its benchmark capabilities."""

        _validate_capabilities(name, klass)
        cls._controllers[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered locomotion controller: %s (%s)", name, class_path)

    @classmethod
    def list_controllers(cls) -> list[dict[str, Any]]:
        """List controllers with availability, capabilities, schema, and metadata."""

        result: list[dict[str, Any]] = []
        for name, info in list(cls._controllers.items()):
            entry: dict[str, Any] = {"name": name, "display": info["display"]}
            klass = _load_class(info["class_path"])
            if klass is None:
                reason = f"Cannot load {info['class_path']}"
                entry.update(
                    {
                        "available": False,
                        "reason": reason,
                        "capabilities": {},
                        "parameter_schema": {},
                    }
                )
            else:
                available, reason = _probe_availability(klass)
                capabilities = dict(getattr(klass, "CAPABILITIES", {}))
                parameter_schema = dict(getattr(klass, "PARAMETER_SCHEMA", {}))
                parameter_summary = cls._parameter_summary(klass)
                entry.update(
                    {
                        "available": available,
                        "capabilities": capabilities,
                        "parameter_schema": parameter_schema,
                    }
                )
                if not available:
                    entry["reason"] = reason or f"{klass.__qualname__}.available() reported unavailable"
                entry.update(
                    controller_metadata(
                        name,
                        info["display"],
                        capabilities,
                        parameter_summary,
                        available,
                        entry.get("reason"),
                    )
                )
            result.append(entry)
        return result

    @classmethod
    def create(cls, name: str | None = None, **kwargs: Any) -> LocomotionController:
        """Instantiate an available controller by id.

        Unknown ids are deterministic errors and never fall back to the default.
        Unavailable entries raise before constructor execution.
        """

        if name is None:
            name = cls._default
        if name not in cls._controllers:
            raise ValueError(
                f"Unknown locomotion controller '{name}'. Available: {list(cls._controllers.keys())}"
            )
        info = cls._controllers[name]
        klass = _load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load locomotion controller class: {info['class_path']}")
        available, reason = _probe_availability(klass)
        if not available:
            raise UnavailableControllerError(
                f"Controller '{name}' is unavailable: "
                f"{reason or f'{klass.__qualname__}.available() reported unavailable'}"
            )
        return klass(**kwargs)

    @classmethod
    def get_default(cls) -> str:
        return cls._default

    @classmethod
    def _parameter_summary(cls, klass: type) -> dict[str, Any]:
        if hasattr(klass, "parameter_summary"):
            summary = klass.parameter_summary()
            if isinstance(summary, dict):
                return dict(summary)
        return {}

    @classmethod
    def _clear(cls) -> None:
        """Test helper for registry isolation."""

        cls._controllers.clear()


def locomotion_controller(name: str, display: str):
    """Decorator for registering locomotion controller classes."""

    def decorator(klass: type) -> type:
        ControllerRegistry.register(
            name=name,
            display=display,
            class_path=f"{klass.__module__}.{klass.__qualname__}",
            klass=klass,
        )
        return klass

    return decorator


def _velocity_command_limits() -> dict[str, dict[str, float]]:
    return {
        "vx": {"min": -1.0, "max": 1.0, "unit": "m/s"},
        "vy": {"min": -1.0, "max": 1.0, "unit": "m/s"},
        "yaw_rate": {"min": -3.0, "max": 3.0, "unit": "rad/s"},
    }


def _analytical_capabilities() -> dict[str, Any]:
    return {
        "family": "analytical",
        "action_mode": "joint_position",
        "deterministic": True,
        "observation_expectation": "Observation dict accepted but not required by analytical trot baseline.",
        "command_limits": _velocity_command_limits(),
        "cpu_latency_hint_ms": 1.0,
        "sim_supported": True,
        "hardware_supported": False,
        "model_requirements": {"requires_model_artifact": False, "artifacts": []},
        "multi_robot_supported": True,
        "reproducibility": {
            "stateful": True,
            "reset_reinitializes_gait": True,
            "seed_used": False,
        },
    }


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


@locomotion_controller(name="analytical_trot", display="Analytical Trot")
class AnalyticalTrotController:
    """Adapter that delegates exactly to the existing analytical trot gait."""

    CAPABILITIES = _analytical_capabilities()
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
        "description": "Uses default GaitParams unless constructed directly with params.",
    }

    def __init__(self, params: GaitParams | None = None) -> None:
        self._params = params or GaitParams()
        self._gait = TrotGaitController(self._params)
        self._metadata = controller_metadata(
            "analytical_trot",
            "Analytical Trot",
            self.CAPABILITIES,
            self.parameter_summary(),
            True,
        )

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None

    @classmethod
    def parameter_summary(cls) -> dict[str, Any]:
        return {"gait_params": asdict(GaitParams())}

    def reset(self, seed: int | None = None) -> None:
        del seed
        self._gait = TrotGaitController(self._params)

    def compute(
        self,
        observation: dict[str, Any],
        command: LocomotionCommand,
        dt: float,
    ) -> ControllerResult:
        del observation
        target = self._gait.compute(command.vx, command.vy, command.yaw_rate, dt)
        return ControllerResult(
            action=validate_controller_target(target),
            metadata=dict(self._metadata),
        )


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


@locomotion_controller(name="residual_policy", display="Residual Policy")
class ResidualPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("residual_policy", "residual_baseline")
    UNAVAILABLE_REASON = RESIDUAL_POLICY_UNAVAILABLE_REASON


@locomotion_controller(name="direct_policy", display="Direct Policy")
class DirectPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("direct_policy", "joint_position")
    UNAVAILABLE_REASON = DIRECT_POLICY_UNAVAILABLE_REASON


@locomotion_controller(name="mpc", display="Model Predictive Control")
class MPCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("mpc", "joint_position")
    UNAVAILABLE_REASON = MPC_UNAVAILABLE_REASON


@locomotion_controller(name="wbc", display="Whole-Body Control")
class WBCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("wbc", "undefined_deferred")
    CAPABILITIES["model_requirements"]["action_contract"] = "undefined_deferred"
    CAPABILITIES["model_requirements"]["env_action_mode"] = None
    UNAVAILABLE_REASON = WBC_UNAVAILABLE_REASON
