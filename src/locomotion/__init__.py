"""Locomotion module for Unitree Go2 quadruped.

Provides an XML patcher to convert torque actuators to position-controlled
servos, a tunable gait parameter dataclass, a Raibert-style trot gait
controller, and a Gymnasium-style benchmark environment boundary.
"""

from __future__ import annotations

from typing import Any

__all__ = ["ArgusGo2Env", "ArgusGo2EnvConfig"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig

        exports = {
            "ArgusGo2Env": ArgusGo2Env,
            "ArgusGo2EnvConfig": ArgusGo2EnvConfig,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
