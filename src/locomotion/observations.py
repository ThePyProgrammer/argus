"""Observation helpers for the Argus Go2 Gymnasium environment."""

from typing import Any

import numpy as np
from gymnasium import spaces

_QPOS_SHAPE = (19,)
_QVEL_SHAPE = (18,)
_COMMAND_SHAPE = (3,)
_PREVIOUS_ACTION_SHAPE = (12,)


def build_observation_space() -> spaces.Dict:
    """Build the state-only Phase 1 observation space."""
    return spaces.Dict(
        {
            "qpos": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_QPOS_SHAPE,
                dtype=np.float32,
            ),
            "qvel": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_QVEL_SHAPE,
                dtype=np.float32,
            ),
            "command": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_COMMAND_SHAPE,
                dtype=np.float32,
            ),
            "previous_action": spaces.Box(
                low=-np.inf,
                high=np.inf,
                shape=_PREVIOUS_ACTION_SHAPE,
                dtype=np.float32,
            ),
        }
    )


def _copy_or_zero(source: Any, shape: tuple[int, ...]) -> np.ndarray:
    values = np.zeros(shape, dtype=np.float32)
    if source is None:
        return values

    array = np.asarray(source, dtype=np.float32).reshape(-1)
    copy_count = min(values.size, array.size)
    values[:copy_count] = array[:copy_count]
    return values


def extract_observation(
    data: Any,
    command: np.ndarray,
    previous_action: np.ndarray,
) -> dict[str, np.ndarray]:
    """Extract a state-only observation from optional MuJoCo data."""
    return {
        "qpos": _copy_or_zero(None if data is None else data.qpos, _QPOS_SHAPE),
        "qvel": _copy_or_zero(None if data is None else data.qvel, _QVEL_SHAPE),
        "command": np.asarray(command, dtype=np.float32).reshape(_COMMAND_SHAPE).copy(),
        "previous_action": np.asarray(
            previous_action,
            dtype=np.float32,
        ).reshape(_PREVIOUS_ACTION_SHAPE).copy(),
    }
