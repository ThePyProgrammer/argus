"""Locomotion module for Unitree Go2 quadruped.

Provides an XML patcher to convert torque actuators to position-controlled
servos, a tunable gait parameter dataclass, and a Raibert-style trot gait
controller that produces 12 joint position targets from velocity commands.
"""
