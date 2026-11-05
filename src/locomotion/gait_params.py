"""Tunable gait parameters for the Unitree Go2 trot gait controller."""


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

    swing_thigh_min: float = 0.60
    """Limit extra thigh reduction during lift to preserve Go2 knee clearance.

    A stride may itself request a lower angle; in that case no additional
    thigh reduction is applied. This preserves the phase-boundary targets.
    Calibrated on level-floor development runs, not a terrain safety bound.
    """

    swing_thigh_turn_margin: float = 0.05
    """Extra knee-clearance angle, reaching this margin at 1 rad/s of turning."""

    stride_length: float = 0.4
    """Max forward stride per step at full speed (joint-angle scale)."""

    lateral_stride: float = 0.08
    """Max lateral stride per step at full speed (meters)."""

    max_speed: float = 1.0
    """Velocity cap in m/s."""

    command_yaw_acceleration: float = 8.0
    """Maximum yaw-command change during an active gait, in rad/s per second.

    Initial motion starts at the requested yaw; explicit idle still returns
    the standing pose immediately and clears the yaw-transition state.
    """

    standing_hip: float = 0.0
    """Standing hip abduction angle (radians)."""

    standing_thigh: float = 0.9
    """Standing thigh angle (radians) -- from go2.xml keyframe."""

    standing_calf: float = -1.8
    """Standing calf angle (radians) -- from go2.xml keyframe."""
