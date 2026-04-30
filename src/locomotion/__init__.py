"""Locomotion module for Unitree Go2 quadruped.

Provides an XML patcher to convert torque actuators to position-controlled
servos, a tunable gait parameter dataclass, a Raibert-style trot gait
controller, and a Gymnasium-style benchmark environment boundary.
"""

from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
