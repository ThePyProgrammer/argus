"""Raibert-style analytical trot gait controller for Unitree Go2.

Produces 12 joint position targets from (vx, vy, omega) velocity commands.
Designed for position-controlled actuators (see xml_patcher.py).

The trot gait alternates diagonal leg pairs: FL+RR swing together while
FR+RL provide stance support, then they swap.

Turning uses differential stride: one side takes longer strides than the
other, creating a yaw torque through asymmetric ground reaction forces.
"""

from __future__ import annotations

import numpy as np

from src.locomotion.gait_params import GaitParams


class TrotGaitController:
    """Velocity-commanded trot gait for Unitree Go2.

    Produces 12 joint position targets given (vx, vy, omega) velocity
    command.  Designed for position-controlled actuators.

    Leg ordering matches go2.xml actuator order:
        FL (0), FR (1), RL (2), RR (3)
    Each leg has 3 joints at indices ``[leg*3, leg*3+1, leg*3+2]``
    corresponding to ``[hip, thigh, calf]``.
    """

    # Diagonal pairs for trot gait
    PAIR_A = [0, 3]  # FL, RR -- in phase
    PAIR_B = [1, 2]  # FR, RL -- anti-phase (offset by 0.5)

    def __init__(self, params: GaitParams | None = None) -> None:
        self._params = params or GaitParams()
        self._phase: float = 0.0  # 0.0 to 1.0

    def compute(
        self, vx: float, vy: float, omega: float, dt: float,
    ) -> np.ndarray:
        """Compute 12 joint position targets for one timestep.

        Args:
            vx: Forward velocity command (m/s, positive = forward).
            vy: Lateral velocity command (m/s, positive = left).
            omega: Yaw rate command (rad/s, positive = turn left).
            dt: Time since last call (seconds).

        Returns:
            (12,) array of joint position targets in actuator order.
        """
        p = self._params

        # Clamp speed
        speed = min(float(np.sqrt(vx ** 2 + vy ** 2)), p.max_speed)

        # Advance gait phase only when moving
        if speed > 0.01 or abs(omega) > 0.01:
            self._phase = (self._phase + p.frequency * dt) % 1.0

        ctrl = np.zeros(12)

        for leg_idx in range(4):
            # Determine phase offset for this leg
            if leg_idx in self.PAIR_A:
                leg_phase = self._phase
            else:
                leg_phase = (self._phase + 0.5) % 1.0

            hip, thigh, calf = self._leg_targets(
                leg_idx, leg_phase, vx, vy, omega, speed,
            )

            base = leg_idx * 3
            ctrl[base] = hip
            ctrl[base + 1] = thigh
            ctrl[base + 2] = calf

        return ctrl

    def _leg_targets(
        self, leg_idx: int, phase: float,
        vx: float, vy: float, omega: float, speed: float,
    ) -> tuple[float, float, float]:
        """Compute hip, thigh, calf targets for one leg.

        Go2 thigh joint convention: increasing angle = leg sweeps backward.
        For forward locomotion the stance leg must sweep from small angle
        (leg in front) to large angle (leg behind), propelling the body
        forward.  The swing leg reverses this to reposition.

        Turning uses differential stride length: for a left turn (positive
        omega), right-side legs take longer forward strides while left-side
        legs take shorter (or reversed) strides.
        """
        p = self._params
        is_swing = phase < 0.5  # first half = swing, second half = stance

        # Velocity scaling factor (0 to 1)
        v_scale = min(speed / p.max_speed, 1.0) if p.max_speed > 0 else 0.0

        # Determine leg properties
        is_left = leg_idx in [0, 2]  # FL=0, RL=2 are left legs

        # Hip abduction: lateral movement + turning assist
        hip = p.standing_hip
        hip += 0.1 * vy * (1.0 if is_left else -1.0)
        hip += 0.15 * omega * (1.0 if is_left else -1.0)

        # Differential stride for turning.
        # For positive omega (turn left): right legs push forward more,
        # left legs push forward less (or backward).
        turn_stride = omega * 0.8  # turn coupling strength
        if is_left:
            stride_mult = v_scale - turn_stride
        else:
            stride_mult = v_scale + turn_stride

        half_stride = p.stride_length * stride_mult

        if is_swing:
            # SWING: lift foot off ground and reposition.
            swing_progress = phase / 0.5  # 0 to 1 within swing

            # Parabolic foot lift at mid-swing
            lift = p.swing_height * 4.0 * swing_progress * (1.0 - swing_progress)

            # Thigh: decrease angle = lift upper leg forward/up
            thigh = p.standing_thigh - lift * 3.0

            # Calf: tuck MORE (more negative) for ground clearance
            calf = p.standing_calf - lift * 2.0

            # Move leg from back to front position
            stride_offset = half_stride * (1.0 - 2.0 * swing_progress)
            thigh += stride_offset

        else:
            # STANCE: foot on ground, sweep leg backward to push body.
            stance_progress = (phase - 0.5) / 0.5  # 0 to 1 within stance

            # Thigh sweeps from front (-half_stride) to back (+half_stride)
            sweep = half_stride * (2.0 * stance_progress - 1.0)
            thigh = p.standing_thigh + sweep
            calf = p.standing_calf

        return hip, thigh, calf
