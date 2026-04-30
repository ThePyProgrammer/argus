from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Sequence

import numpy as np

CommandMode = Literal["velocity", "stand", "stop", "recover", "waypoint"]
VALID_COMMAND_MODES: frozenset[str] = frozenset(("velocity", "stand", "stop", "recover", "waypoint"))


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


def _readonly_float_array(value: Sequence[float] | np.ndarray, shape: tuple[int, ...], label: str) -> np.ndarray:
    arr = np.array(value, dtype=np.float64, copy=True)
    if arr.shape != shape:
        raise ValueError(f"{label} must have shape {shape}, got {arr.shape}")
    arr.setflags(write=False)
    return arr


def _readonly_float_vector(value: Sequence[float] | np.ndarray, label: str) -> np.ndarray:
    arr = np.array(value, dtype=np.float64, copy=True)
    if arr.ndim != 1:
        raise ValueError(f"{label} must be 1D, got shape {arr.shape}")
    arr.setflags(write=False)
    return arr


def _normalize_command_mode(mode: object) -> CommandMode:
    normalized = str(mode)
    if normalized not in VALID_COMMAND_MODES:
        raise ValueError(f"command mode must be one of {sorted(VALID_COMMAND_MODES)}, got {mode!r}")
    return normalized  # type: ignore[return-value]


@dataclass(frozen=True)
class RobotCommand:
    linear: Sequence[float] | np.ndarray = field(default_factory=lambda: np.zeros(2, dtype=np.float64))
    yaw_rate: float = 0.0
    mode: CommandMode = "velocity"
    waypoint: Sequence[float] | np.ndarray | None = None

    def __post_init__(self) -> None:
        mode = _normalize_command_mode(self.mode)
        linear = _readonly_float_array(self.linear, (2,), "linear command")
        waypoint: tuple[float, float, float] | None
        if self.waypoint is None:
            waypoint = None
        else:
            waypoint_arr = np.array(self.waypoint, dtype=np.float64, copy=True).reshape(-1)
            if waypoint_arr.shape != (3,):
                raise ValueError(f"waypoint command must have shape (3,), got {waypoint_arr.shape}")
            waypoint = (float(waypoint_arr[0]), float(waypoint_arr[1]), float(waypoint_arr[2]))

        if mode == "waypoint" and waypoint is None:
            raise ValueError("waypoint mode requires a 3-float waypoint")
        if mode != "waypoint" and waypoint is not None:
            raise ValueError("non-waypoint command modes must not carry a waypoint")

        object.__setattr__(self, "linear", linear)
        object.__setattr__(self, "yaw_rate", float(self.yaw_rate))
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "waypoint", waypoint)

    @classmethod
    def velocity(cls, linear: Sequence[float] | np.ndarray, yaw_rate: float) -> "RobotCommand":
        return cls(linear=linear, yaw_rate=float(yaw_rate), mode="velocity")

    @classmethod
    def stand(cls) -> "RobotCommand":
        return cls(linear=np.zeros(2, dtype=np.float64), mode="stand", waypoint=None)

    @classmethod
    def stop(cls) -> "RobotCommand":
        return cls(linear=np.zeros(2, dtype=np.float64), mode="stop", waypoint=None)

    @classmethod
    def recover(cls) -> "RobotCommand":
        return cls(linear=np.zeros(2, dtype=np.float64), mode="recover", waypoint=None)

    @classmethod
    def waypoint_command(cls, target: Sequence[float] | np.ndarray) -> "RobotCommand":
        arr = np.array(target, dtype=np.float64, copy=True).reshape(-1)
        if arr.shape not in {(2,), (3,)}:
            raise ValueError(f"waypoint command must have shape (2,) or (3,), got {arr.shape}")
        z = float(arr[2]) if arr.shape == (3,) else 0.0
        return cls(linear=np.zeros(2, dtype=np.float64), mode="waypoint", waypoint=(float(arr[0]), float(arr[1]), z))

    def to_wire(self) -> dict[str, object]:
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

    def __post_init__(self) -> None:
        waypoint_error = None if self.waypoint_error is None else float(self.waypoint_error)
        if waypoint_error is not None and waypoint_error < 0.0:
            raise ValueError("waypoint_error must be non-negative")
        object.__setattr__(self, "linear_error", float(self.linear_error))
        object.__setattr__(self, "yaw_error", float(self.yaw_error))
        object.__setattr__(self, "waypoint_error", waypoint_error)
        object.__setattr__(self, "timed_out", bool(self.timed_out))

    def to_wire(self) -> dict[str, object]:
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

    def __post_init__(self) -> None:
        actuator_clamp_count = int(self.actuator_clamp_count)
        if actuator_clamp_count < 0:
            raise ValueError("actuator_clamp_count must be non-negative")
        object.__setattr__(self, "policy_loaded", bool(self.policy_loaded))
        object.__setattr__(self, "action_shape_valid", bool(self.action_shape_valid))
        object.__setattr__(self, "nan_guard_ok", bool(self.nan_guard_ok))
        object.__setattr__(self, "actuator_clamp_count", actuator_clamp_count)
        object.__setattr__(self, "message", str(self.message))

    def to_wire(self) -> dict[str, object]:
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

    def __post_init__(self) -> None:
        command_modes = tuple(_normalize_command_mode(mode) for mode in self.command_modes)
        dimensions_arr = np.array(self.dimensions, dtype=np.float64, copy=True).reshape(-1)
        if dimensions_arr.shape != (3,):
            raise ValueError(f"dimensions must contain three floats, got shape {dimensions_arr.shape}")
        actuator_count = int(self.actuator_count)
        footprint_radius = float(self.footprint_radius)
        max_linear_speed = float(self.max_linear_speed)
        max_yaw_rate = float(self.max_yaw_rate)
        spawn_height = float(self.spawn_height)
        if actuator_count <= 0:
            raise ValueError("actuator_count must be positive")
        if footprint_radius <= 0.0:
            raise ValueError("footprint_radius must be positive")
        if max_linear_speed < 0.0:
            raise ValueError("max_linear_speed must be non-negative")
        if max_yaw_rate < 0.0:
            raise ValueError("max_yaw_rate must be non-negative")
        if spawn_height < 0.0:
            raise ValueError("spawn_height must be non-negative")
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "display_name", str(self.display_name))
        object.__setattr__(self, "model_dir", str(self.model_dir))
        object.__setattr__(self, "model_xml", str(self.model_xml))
        object.__setattr__(self, "actuator_count", actuator_count)
        object.__setattr__(self, "command_modes", command_modes)
        object.__setattr__(self, "footprint_radius", footprint_radius)
        object.__setattr__(self, "dimensions", (float(dimensions_arr[0]), float(dimensions_arr[1]), float(dimensions_arr[2])))
        object.__setattr__(self, "max_linear_speed", max_linear_speed)
        object.__setattr__(self, "max_yaw_rate", max_yaw_rate)
        object.__setattr__(self, "marker_asset", None if self.marker_asset is None else str(self.marker_asset))
        object.__setattr__(self, "spawn_height", spawn_height)

    def to_wire(self) -> dict[str, object]:
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
    base_pose: Sequence[Sequence[float]] | np.ndarray
    base_velocity: Sequence[float] | np.ndarray
    joint_positions: Sequence[float] | np.ndarray
    joint_velocities: Sequence[float] | np.ndarray
    orientation_quat: Sequence[float] | np.ndarray
    contacts: Sequence[str]
    sim_time: float
    fallen: bool = False
    fall_reason: FallReason = FallReason.NONE

    def __post_init__(self) -> None:
        base_pose = _readonly_float_array(self.base_pose, (4, 4), "base_pose")
        base_velocity = _readonly_float_array(self.base_velocity, (3,), "base_velocity")
        joint_positions = _readonly_float_vector(self.joint_positions, "joint_positions")
        joint_velocities = _readonly_float_vector(self.joint_velocities, "joint_velocities")
        orientation_quat = _readonly_float_array(self.orientation_quat, (4,), "orientation_quat")
        if joint_positions.shape != joint_velocities.shape:
            raise ValueError(
                "joint_positions and joint_velocities must have equal length, "
                f"got {joint_positions.shape[0]} and {joint_velocities.shape[0]}"
            )
        object.__setattr__(self, "base_pose", base_pose)
        object.__setattr__(self, "base_velocity", base_velocity)
        object.__setattr__(self, "joint_positions", joint_positions)
        object.__setattr__(self, "joint_velocities", joint_velocities)
        object.__setattr__(self, "orientation_quat", orientation_quat)
        object.__setattr__(self, "contacts", tuple(str(contact) for contact in self.contacts))
        object.__setattr__(self, "sim_time", float(self.sim_time))
        object.__setattr__(self, "fallen", bool(self.fallen))
        object.__setattr__(self, "fall_reason", FallReason(self.fall_reason))


@dataclass(frozen=True)
class RobotRuntimeStatus:
    state: RobotRuntimeState = RobotRuntimeState.STANDING
    fall_reason: FallReason = FallReason.NONE
    last_command: RobotCommand = field(default_factory=RobotCommand.stand)
    command_tracking: CommandTracking = field(default_factory=CommandTracking)
    controller_health: ControllerHealth = field(default_factory=ControllerHealth)
    collision_count: int = 0
    near_miss_count: int = 0

    def __post_init__(self) -> None:
        collision_count = int(self.collision_count)
        near_miss_count = int(self.near_miss_count)
        if collision_count < 0:
            raise ValueError("collision_count must be non-negative")
        if near_miss_count < 0:
            raise ValueError("near_miss_count must be non-negative")
        object.__setattr__(self, "state", RobotRuntimeState(self.state))
        object.__setattr__(self, "fall_reason", FallReason(self.fall_reason))
        object.__setattr__(self, "collision_count", collision_count)
        object.__setattr__(self, "near_miss_count", near_miss_count)

    @property
    def disabled(self) -> bool:
        return self.state in {RobotRuntimeState.FALLEN, RobotRuntimeState.DISABLED}

    def to_wire(self) -> dict[str, object]:
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
