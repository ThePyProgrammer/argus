from __future__ import annotations

from pathlib import Path

import numpy as np

from src.bridge.platforms.types import ControllerHealth, RobotCommand, RobotState

_SAFE_DEFAULT_MODES = frozenset(("stand", "stop", "recover"))


class X2PolicyController:
    def __init__(
        self,
        actuator_count: int,
        policy_path: str | Path | None = None,
        default_qpos: np.ndarray | None = None,
    ) -> None:
        self.actuator_count = int(actuator_count)
        if self.actuator_count <= 0:
            raise ValueError("actuator_count must be positive")

        self.default_qpos = self._qpos_or_raise(
            np.zeros(self.actuator_count, dtype=np.float64) if default_qpos is None else default_qpos,
            "default_qpos",
        )
        self.weights: np.ndarray | None = None
        self.bias: np.ndarray | None = None
        self.lower = np.full(self.actuator_count, -np.inf, dtype=np.float64)
        self.upper = np.full(self.actuator_count, np.inf, dtype=np.float64)
        self._policy_loaded = False
        self._health = ControllerHealth(policy_loaded=False)

        if policy_path is not None:
            self._load_policy(Path(policy_path))

    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray:
        _ = dt
        if command.mode in _SAFE_DEFAULT_MODES or not self._policy_loaded:
            self._health = ControllerHealth(policy_loaded=self._policy_loaded)
            return self.default_qpos.copy()

        obs = np.concatenate(
            (
                np.asarray(command.linear, dtype=np.float64),
                np.array([command.yaw_rate], dtype=np.float64),
                np.asarray(state.base_velocity, dtype=np.float64),
                np.asarray(state.joint_positions, dtype=np.float64),
                np.asarray(state.joint_velocities, dtype=np.float64),
            )
        )
        if self.weights is None or self.bias is None or obs.shape != (self.weights.shape[0],):
            self._health = ControllerHealth(
                policy_loaded=self._policy_loaded,
                action_shape_valid=False,
                message="observation_shape_mismatch",
            )
            return self.default_qpos.copy()

        raw = obs @ self.weights + self.bias
        if raw.shape != (self.actuator_count,):
            self._health = ControllerHealth(
                policy_loaded=self._policy_loaded,
                action_shape_valid=False,
                message="action_shape_mismatch",
            )
            return self.default_qpos.copy()
        if not np.isfinite(raw).all():
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=True,
                nan_guard_ok=False,
                message="controller_invalid_output",
            )
            return self.default_qpos.copy()

        clipped = np.clip(raw, self.lower, self.upper).astype(np.float64, copy=False)
        if not np.isfinite(clipped).all():
            self._health = ControllerHealth(
                policy_loaded=True,
                action_shape_valid=True,
                nan_guard_ok=False,
                message="controller_invalid_output",
            )
            return self.default_qpos.copy()

        clipped_count = int(np.count_nonzero(clipped != raw))
        self._health = ControllerHealth(
            policy_loaded=True,
            action_shape_valid=True,
            nan_guard_ok=True,
            actuator_clamp_count=clipped_count,
            message="ok",
        )
        return clipped.copy()

    def health(self) -> ControllerHealth:
        return self._health

    def reset(self) -> None:
        self._health = ControllerHealth(policy_loaded=self._policy_loaded)

    def _load_policy(self, policy_path: Path) -> None:
        with np.load(policy_path) as policy:
            weights = np.asarray(policy["weights"], dtype=np.float64)
            bias = np.asarray(policy["bias"], dtype=np.float64)
            if "default_qpos" in policy:
                self.default_qpos = self._qpos_or_raise(policy["default_qpos"], "default_qpos")
            self.lower = self._bounds_or_raise(policy["lower"], "lower") if "lower" in policy else self.lower
            self.upper = self._bounds_or_raise(policy["upper"], "upper") if "upper" in policy else self.upper

        if np.any(self.lower > self.upper):
            raise ValueError("lower bounds must be less than or equal to upper bounds")

        if weights.ndim != 2 or weights.shape[1] != self.actuator_count:
            self._policy_loaded = False
            self._health = ControllerHealth(
                policy_loaded=False,
                action_shape_valid=False,
                message="action_shape_mismatch",
            )
            raise ValueError(
                f"weights must be 2D with second dimension {self.actuator_count}, got {weights.shape}"
            )
        if bias.shape != (self.actuator_count,):
            self._policy_loaded = False
            self._health = ControllerHealth(
                policy_loaded=False,
                action_shape_valid=False,
                message="action_shape_mismatch",
            )
            raise ValueError(f"bias must have shape ({self.actuator_count},), got {bias.shape}")

        self.weights = weights
        self.bias = bias
        self._policy_loaded = True
        self._health = ControllerHealth(policy_loaded=True)

    def _qpos_or_raise(self, value: np.ndarray, label: str) -> np.ndarray:
        arr = np.asarray(value, dtype=np.float64)
        if arr.shape != (self.actuator_count,):
            raise ValueError(f"{label} must have shape ({self.actuator_count},), got {arr.shape}")
        if not np.isfinite(arr).all():
            raise ValueError(f"{label} must contain only finite values")
        return arr.copy()

    def _bounds_or_raise(self, value: np.ndarray, label: str) -> np.ndarray:
        arr = np.asarray(value, dtype=np.float64)
        if arr.shape != (self.actuator_count,):
            raise ValueError(f"{label} must have shape ({self.actuator_count},), got {arr.shape}")
        if not np.isfinite(arr).all():
            raise ValueError(f"{label} must contain only finite values")
        return arr.copy()
