"""Action mode spaces and decoding helpers for Go2 locomotion benchmarks."""

from collections.abc import Sequence
from typing import Final

import numpy as np
from gymnasium import spaces

from src.locomotion.gait_controller import TrotGaitController


ACTION_MODE_VELOCITY = "velocity_command"
ACTION_MODE_JOINT_POSITION = "joint_position"
ACTION_MODE_RESIDUAL_BASELINE = "residual_baseline"

_VELOCITY_LOW = np.array([-1.0, -1.0, -3.0], dtype=np.float32)
_VELOCITY_HIGH = np.array([1.0, 1.0, 3.0], dtype=np.float32)
_JOINT_LOW = np.array([-1.0472, -1.5708, -2.7227] * 4, dtype=np.float32)
_JOINT_HIGH = np.array([1.0472, 4.5379, -0.83776] * 4, dtype=np.float32)
_RESIDUAL_LOW = np.full(12, -0.25, dtype=np.float32)
_RESIDUAL_HIGH = np.full(12, 0.25, dtype=np.float32)
_ACTION_MODES: Final[tuple[str, ...]] = (
    ACTION_MODE_JOINT_POSITION,
    ACTION_MODE_RESIDUAL_BASELINE,
    ACTION_MODE_VELOCITY,
)


def available_action_modes() -> list[str]:
    """Return sorted action mode names supported by the benchmark wrapper."""
    return sorted(_ACTION_MODES)


def build_action_space(mode: str) -> spaces.Box:
    """Build the Gymnasium action space for an action mode.

    Args:
        mode: One of ``velocity_command``, ``joint_position``, or
            ``residual_baseline``.

    Raises:
        ValueError: If *mode* is not registered.
    """
    if mode == ACTION_MODE_VELOCITY:
        return spaces.Box(low=_VELOCITY_LOW.copy(), high=_VELOCITY_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_JOINT_POSITION:
        return spaces.Box(low=_JOINT_LOW.copy(), high=_JOINT_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_RESIDUAL_BASELINE:
        return spaces.Box(low=_RESIDUAL_LOW.copy(), high=_RESIDUAL_HIGH.copy(), dtype=np.float32)
    raise _unknown_mode_error(mode)


def decode_action(
    action: Sequence[float] | np.ndarray,
    mode: str,
    gait: TrotGaitController,
    dt: float,
    previous_command: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Decode one mode-specific action into a finite 12-joint control vector.

    The returned vector is safe for a caller to write to MuJoCo ``data.ctrl``.
    This helper does not mutate MuJoCo state.
    """
    if mode == ACTION_MODE_VELOCITY:
        command = _as_bounded_vector(action, _VELOCITY_LOW, _VELOCITY_HIGH)
        decoded = gait.compute(
            float(command[0]),
            float(command[1]),
            float(command[2]),
            dt,
        )
        return _ensure_decoded_control(decoded)

    if mode == ACTION_MODE_JOINT_POSITION:
        return _as_bounded_vector(action, _JOINT_LOW, _JOINT_HIGH)

    if mode == ACTION_MODE_RESIDUAL_BASELINE:
        residual = _as_finite_vector(action, (12,))
        command = _as_finite_vector(previous_command, (3,))
        clipped_residual = np.clip(residual, -0.25, 0.25)
        baseline = gait.compute(
            float(command[0]),
            float(command[1]),
            float(command[2]),
            dt,
        )
        return _ensure_decoded_control(baseline + clipped_residual)

    raise _unknown_mode_error(mode)


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


def _unknown_mode_error(mode: str) -> ValueError:
    return ValueError(f"Unknown action mode '{mode}'. Available: {available_action_modes()}")
