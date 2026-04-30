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
