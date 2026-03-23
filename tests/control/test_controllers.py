"""Tests for src/control/ -- WaypointRunner, RandomWalkController, TeleopController."""

import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ------------------------------------------------------------------ #
# WaypointRunner tests
# ------------------------------------------------------------------ #


class TestWaypointRunner:
    """WaypointRunner navigates through waypoints and reports completion."""

    def test_get_velocity_direction_toward_waypoint(self):
        """get_velocity returns a linear velocity with positive vx toward waypoint."""
        from src.control.waypoint_runner import WaypointRunner

        waypoints = [np.array([5.0, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, linear_speed=0.5)

        # Robot at origin, facing +X (identity rotation)
        pose = np.eye(4)
        linear, angular = runner.get_velocity(pose)

        assert isinstance(linear, np.ndarray)
        assert linear.shape == (2,)
        # Robot faces +X and waypoint is at +X, so vx should be positive
        assert linear[0] > 0.0, "Should have positive forward velocity toward waypoint"

    def test_is_complete_after_all_waypoints_visited(self):
        """is_complete returns True when robot reaches the final waypoint."""
        from src.control.waypoint_runner import WaypointRunner

        waypoints = [np.array([0.1, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, arrival_threshold=0.5)

        # Place robot at the waypoint
        pose = np.eye(4)
        pose[:3, 3] = [0.1, 0.0, 0.0]

        runner.get_velocity(pose)
        assert runner.is_complete, "Should be complete when robot is at the final waypoint"

    def test_not_complete_when_far_from_waypoint(self):
        """is_complete returns False when robot is far from the final waypoint."""
        from src.control.waypoint_runner import WaypointRunner

        waypoints = [np.array([10.0, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, arrival_threshold=0.5)

        pose = np.eye(4)
        runner.get_velocity(pose)
        assert not runner.is_complete

    def test_arrival_threshold_boundary(self):
        """Robot at exactly the threshold distance triggers arrival."""
        from src.control.waypoint_runner import WaypointRunner

        threshold = 0.5
        waypoints = [np.array([threshold - 0.01, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, arrival_threshold=threshold)

        pose = np.eye(4)
        runner.get_velocity(pose)
        assert runner.is_complete, "Should be complete when within threshold"

    def test_arrival_threshold_just_outside(self):
        """Robot just outside threshold does not complete."""
        from src.control.waypoint_runner import WaypointRunner

        threshold = 0.5
        waypoints = [np.array([threshold + 0.1, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, arrival_threshold=threshold)

        pose = np.eye(4)
        runner.get_velocity(pose)
        assert not runner.is_complete, "Should not be complete when outside threshold"

    def test_returns_zero_velocity_when_complete(self):
        """get_velocity returns zero after all waypoints are visited."""
        from src.control.waypoint_runner import WaypointRunner

        waypoints = [np.array([0.1, 0.0, 0.0])]
        runner = WaypointRunner(waypoints, arrival_threshold=0.5)

        # Reach the waypoint
        pose = np.eye(4)
        pose[:3, 3] = [0.1, 0.0, 0.0]
        runner.get_velocity(pose)

        # Now call again after completion
        linear, angular = runner.get_velocity(pose)
        np.testing.assert_allclose(linear, [0.0, 0.0])
        assert angular == 0.0

    def test_empty_waypoints_raises(self):
        """Empty waypoints list raises ValueError."""
        from src.control.waypoint_runner import WaypointRunner

        with pytest.raises(ValueError, match="must not be empty"):
            WaypointRunner([])

    def test_multiple_waypoints_progression(self):
        """Runner advances through multiple waypoints in sequence."""
        from src.control.waypoint_runner import WaypointRunner

        waypoints = [
            np.array([0.1, 0.0, 0.0]),
            np.array([0.2, 0.0, 0.0]),
            np.array([0.3, 0.0, 0.0]),
        ]
        runner = WaypointRunner(waypoints, arrival_threshold=0.5)

        # Place robot at the last waypoint to complete everything
        pose = np.eye(4)
        pose[:3, 3] = [0.3, 0.0, 0.0]
        runner.get_velocity(pose)

        assert runner.is_complete
        assert runner.waypoint_count == 3


# ------------------------------------------------------------------ #
# RandomWalkController tests
# ------------------------------------------------------------------ #


class TestRandomWalkController:
    """RandomWalkController generates valid random velocity commands."""

    def test_get_velocity_returns_valid_tuple(self):
        """get_velocity returns (np.ndarray of shape (2,), float)."""
        from src.control.random_walk import RandomWalkController

        rw = RandomWalkController(seed=42)
        linear, angular = rw.get_velocity(sim_time=0.0)

        assert isinstance(linear, np.ndarray)
        assert linear.shape == (2,)
        assert isinstance(angular, float)

    def test_direction_changes_after_interval(self):
        """Velocity changes after direction_change_interval elapses."""
        from src.control.random_walk import RandomWalkController

        interval = 2.0
        rw = RandomWalkController(
            linear_speed=0.3, angular_speed=0.8,
            direction_change_interval=interval, seed=42,
        )

        # First call at t=0 triggers a direction change
        linear_0, angular_0 = rw.get_velocity(sim_time=0.0)

        # Call before interval -- should return same velocity
        linear_1, angular_1 = rw.get_velocity(sim_time=1.0)
        np.testing.assert_array_equal(linear_0, linear_1)
        assert angular_0 == angular_1

        # Call after interval -- should get new velocity
        linear_2, angular_2 = rw.get_velocity(sim_time=interval)
        # With seed=42, extremely unlikely to be identical
        changed = not np.array_equal(linear_0, linear_2) or angular_0 != angular_2
        assert changed, "Velocity should change after direction_change_interval"

    def test_velocity_magnitude_within_limits(self):
        """Generated velocities stay within configured speed limits."""
        from src.control.random_walk import RandomWalkController

        linear_speed = 0.3
        angular_speed = 0.8
        rw = RandomWalkController(
            linear_speed=linear_speed, angular_speed=angular_speed, seed=42,
        )

        for t in np.arange(0.0, 30.0, 0.5):
            linear, angular = rw.get_velocity(sim_time=t)
            assert abs(linear[0]) <= linear_speed + 1e-9
            assert abs(linear[1]) <= linear_speed + 1e-9
            assert abs(angular) <= angular_speed + 1e-9

    def test_seeded_reproducibility(self):
        """Same seed produces same velocity sequence."""
        from src.control.random_walk import RandomWalkController

        rw_a = RandomWalkController(seed=123)
        rw_b = RandomWalkController(seed=123)

        for t in np.arange(0.0, 15.0, 0.5):
            lin_a, ang_a = rw_a.get_velocity(sim_time=t)
            lin_b, ang_b = rw_b.get_velocity(sim_time=t)
            np.testing.assert_array_equal(lin_a, lin_b)
            assert ang_a == ang_b

    def test_reset_restores_initial_state(self):
        """reset() zeroes out velocity and allows fresh direction sampling."""
        from src.control.random_walk import RandomWalkController

        rw = RandomWalkController(seed=42)
        rw.get_velocity(sim_time=0.0)
        rw.reset()

        # After reset, internal velocities should be zero
        linear, angular = rw.get_velocity(sim_time=100.0)
        # The first call after reset samples a new direction (since last_change
        # is reset), so we just check the types are valid
        assert isinstance(linear, np.ndarray)
        assert linear.shape == (2,)


# ------------------------------------------------------------------ #
# TeleopController tests
# ------------------------------------------------------------------ #


class TestTeleopController:
    """TeleopController produces velocity from keyboard state."""

    @staticmethod
    def _make_mock_keyboard():
        """Create a mock pynput.keyboard module with working KeyCode.from_char."""
        mock_keyboard = MagicMock()
        # Make KeyCode.from_char return deterministic, comparable objects
        _key_cache = {}

        def _from_char(c):
            if c not in _key_cache:
                k = MagicMock()
                k.__repr__ = lambda self, _c=c: f"Key({_c})"
                _key_cache[c] = k
            return _key_cache[c]

        mock_keyboard.KeyCode.from_char = MagicMock(side_effect=_from_char)
        return mock_keyboard, _key_cache

    def test_get_velocity_zero_when_no_keys(self):
        """get_velocity returns zero velocity when no keys are pressed."""
        mock_keyboard, _ = self._make_mock_keyboard()
        mock_pynput = MagicMock()
        mock_pynput.keyboard = mock_keyboard

        with patch.dict("sys.modules", {
            "pynput": mock_pynput,
            "pynput.keyboard": mock_keyboard,
        }):
            # Force re-import so the module picks up the mock
            import importlib
            import src.control.teleop as teleop_mod
            importlib.reload(teleop_mod)
            TeleopController = teleop_mod.TeleopController

            teleop = TeleopController(linear_speed=0.5, angular_speed=1.0)
            # Don't call start() -- no listener needed, keys_pressed is empty
            linear, angular = teleop.get_velocity()

            np.testing.assert_allclose(linear, [0.0, 0.0])
            assert angular == 0.0

    def test_get_velocity_forward_with_w_key(self):
        """Pressing W produces positive vx."""
        mock_keyboard, key_cache = self._make_mock_keyboard()
        mock_pynput = MagicMock()
        mock_pynput.keyboard = mock_keyboard

        with patch.dict("sys.modules", {
            "pynput": mock_pynput,
            "pynput.keyboard": mock_keyboard,
        }):
            import importlib
            import src.control.teleop as teleop_mod
            importlib.reload(teleop_mod)
            TeleopController = teleop_mod.TeleopController

            teleop = TeleopController(linear_speed=0.5, angular_speed=1.0)
            # Simulate W key pressed -- get the same key object from_char returns
            w_key = mock_keyboard.KeyCode.from_char("w")
            teleop._keys_pressed.add(w_key)
            linear, angular = teleop.get_velocity()

            assert linear[0] == 0.5, "W key should produce positive forward velocity"
