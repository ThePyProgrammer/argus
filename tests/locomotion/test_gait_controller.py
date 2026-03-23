"""Tests for TrotGaitController -- output shape, standing pose, input clamping, phase."""

import numpy as np
import pytest

from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams


# ------------------------------------------------------------------ #
# Output shape
# ------------------------------------------------------------------ #


class TestComputeOutputShape:
    """compute() returns an array of correct shape (12 joint targets)."""

    def test_returns_12_element_array(self):
        """compute returns a numpy array of shape (12,)."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.3, vy=0.0, omega=0.0, dt=0.02)

        assert isinstance(result, np.ndarray)
        assert result.shape == (12,)

    def test_returns_12_elements_with_all_inputs_nonzero(self):
        """compute returns (12,) even with lateral and angular inputs."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.5, vy=0.2, omega=0.8, dt=0.02)

        assert result.shape == (12,)

    def test_returns_12_elements_after_many_steps(self):
        """Shape is consistent across many timesteps."""
        ctrl = TrotGaitController()
        for _ in range(100):
            result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)
        assert result.shape == (12,)


# ------------------------------------------------------------------ #
# Standing pose with zero velocity
# ------------------------------------------------------------------ #


class TestStandingPose:
    """Zero velocity input produces standing pose."""

    def test_zero_velocity_returns_standing_angles(self):
        """compute(0, 0, 0, dt) returns standing hip/thigh/calf for all 4 legs."""
        params = GaitParams()
        ctrl = TrotGaitController(params)
        result = ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)

        for leg in range(4):
            base = leg * 3
            np.testing.assert_allclose(
                result[base], params.standing_hip, atol=1e-6,
                err_msg=f"Leg {leg} hip should be standing pose",
            )
            np.testing.assert_allclose(
                result[base + 1], params.standing_thigh, atol=1e-6,
                err_msg=f"Leg {leg} thigh should be standing pose",
            )
            np.testing.assert_allclose(
                result[base + 2], params.standing_calf, atol=1e-6,
                err_msg=f"Leg {leg} calf should be standing pose",
            )

    def test_zero_velocity_does_not_advance_phase(self):
        """Phase stays at 0.0 when speed and omega are both zero."""
        ctrl = TrotGaitController()
        ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)
        assert ctrl._phase == 0.0


# ------------------------------------------------------------------ #
# Input clamping
# ------------------------------------------------------------------ #


class TestInputClamping:
    """compute() clamps dt and velocity inputs to safe ranges."""

    def test_dt_zero_gets_clamped_to_minimum(self):
        """dt=0 is clamped to 0.001, avoiding division issues."""
        ctrl = TrotGaitController()
        # Should not raise
        result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.0)
        assert result.shape == (12,)
        assert np.all(np.isfinite(result))

    def test_negative_dt_gets_clamped(self):
        """Negative dt is clamped to 0.001."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=-1.0)
        assert result.shape == (12,)
        assert np.all(np.isfinite(result))

    def test_extreme_velocity_gets_clamped(self):
        """Extreme vx/vy values are clamped to max_speed."""
        params = GaitParams(max_speed=1.0)
        ctrl = TrotGaitController(params)

        result = ctrl.compute(vx=100.0, vy=100.0, omega=0.0, dt=0.02)
        assert result.shape == (12,)
        assert np.all(np.isfinite(result))

    def test_extreme_omega_gets_clamped(self):
        """Extreme omega values are clamped to [-3.0, 3.0]."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.0, vy=0.0, omega=50.0, dt=0.02)
        assert result.shape == (12,)
        assert np.all(np.isfinite(result))

    def test_large_dt_gets_clamped(self):
        """dt > 1.0 is clamped to 1.0."""
        ctrl = TrotGaitController()
        result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=999.0)
        assert result.shape == (12,)
        # Phase should advance by at most frequency * 1.0 (the clamped dt)
        assert 0.0 <= ctrl._phase < 1.0


# ------------------------------------------------------------------ #
# Phase advancement
# ------------------------------------------------------------------ #


class TestPhaseAdvancement:
    """Phase advances correctly with nonzero velocity over multiple calls."""

    def test_phase_advances_with_forward_velocity(self):
        """Phase increases when vx > 0."""
        ctrl = TrotGaitController()
        ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)
        assert ctrl._phase > 0.0

    def test_phase_advances_with_angular_velocity_only(self):
        """Phase increases when omega > 0 even with zero linear velocity."""
        ctrl = TrotGaitController()
        ctrl.compute(vx=0.0, vy=0.0, omega=1.0, dt=0.02)
        assert ctrl._phase > 0.0

    def test_phase_wraps_around(self):
        """Phase wraps to stay within [0, 1) over many steps."""
        params = GaitParams(frequency=3.0)
        ctrl = TrotGaitController(params)

        for _ in range(200):
            ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)

        assert 0.0 <= ctrl._phase < 1.0

    def test_phase_accumulates_proportionally_to_dt(self):
        """Phase increment is proportional to frequency * dt."""
        params = GaitParams(frequency=3.0)
        ctrl = TrotGaitController(params)

        ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.1)
        expected_phase = (3.0 * 0.1) % 1.0
        np.testing.assert_allclose(ctrl._phase, expected_phase, atol=1e-9)
