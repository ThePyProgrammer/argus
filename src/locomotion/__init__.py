"""Locomotion module for Unitree Go2 quadruped.

Provides an XML patcher to convert torque actuators to position-controlled
servos, a tunable gait parameter dataclass, and a Raibert-style trot gait
controller that produces 12 joint position targets from velocity commands.
"""

from src.locomotion.gait_params import GaitParams
from src.locomotion.xml_patcher import patch_actuators_to_position

# TrotGaitController imported lazily after it is created in Task 2.
# For now, provide the name in __all__ so the module interface is clear.
__all__ = [
    "GaitParams",
    "patch_actuators_to_position",
    "TrotGaitController",
]


def __getattr__(name: str):
    if name == "TrotGaitController":
        from src.locomotion.gait_controller import TrotGaitController
        return TrotGaitController
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
