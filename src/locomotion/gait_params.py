"""Tunable gait parameters for the Unitree Go2 trot gait controller."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GaitParams:
    """Tunable parameters for TrotGaitController.

    Default values are derived from the Go2 mujoco_menagerie keyframe
    and community controller experience. The standing pose uses the
    keyframe joint angles (0, 0.9, -1.8) rather than the older
    code values (0, 0.8, -1.5).
    """

    frequency: float = 3.0
    """Gait cycles per second. Moderate frequency for good stride coverage."""

    stance_height: float = -0.25
    """Target foot height relative to hip (negative = below)."""

    swing_height: float = 0.15
    """Foot lift amplitude during swing phase (joint-angle scale, not meters)."""

    stride_length: float = 0.4
    """Max forward stride per step at full speed (joint-angle scale)."""

    lateral_stride: float = 0.08
    """Max lateral stride per step at full speed (meters)."""

    max_speed: float = 1.0
    """Velocity cap in m/s."""

    standing_hip: float = 0.0
    """Standing hip abduction angle (radians)."""

    standing_thigh: float = 0.9
    """Standing thigh angle (radians) -- from go2.xml keyframe."""

    standing_calf: float = -1.8
    """Standing calf angle (radians) -- from go2.xml keyframe."""
