"""Exploration must face its route before translating through a sharp turn."""

import numpy as np
import pytest

from src.control.waypoint_runner import WaypointRunner


@pytest.mark.parametrize("angle", [-2., -.6, .6, 2.])
def test_sharp_turn_rotates_without_forward_motion_then_resumes(angle):
    goal = np.array([2 * np.cos(angle), 2 * np.sin(angle), 0.])
    runner = WaypointRunner([np.zeros(3), goal], heading_tolerance_rad=.25)
    pose = np.eye(4)
    linear, angular = runner.get_velocity(pose)
    np.testing.assert_array_equal(linear, [0, 0])
    assert np.sign(angular) == np.sign(angle)
    assert not runner.is_complete
    pose[:2, :2] = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    linear, angular = runner.get_velocity(pose)
    assert linear[0] > 0 and abs(angular) < 1e-12


def test_small_heading_corrections_still_allow_forward_motion():
    runner = WaypointRunner([np.zeros(3), np.array([2., .2, 0.])], heading_tolerance_rad=.25)
    linear, angular = runner.get_velocity(np.eye(4))
    assert linear[0] > 0 and angular > 0


def test_generic_follower_retains_its_existing_turning_policy():
    runner = WaypointRunner([np.zeros(3), np.array([0., 2., 0.])])
    linear, angular = runner.get_velocity(np.eye(4))
    assert linear[0] > 0 and angular > 0


@pytest.mark.parametrize("tolerance", [-.1, float("nan"), float("inf"), 4.])
def test_invalid_heading_tolerance_is_rejected(tolerance):
    with pytest.raises(ValueError):
        WaypointRunner([np.array([1., 0., 0.])], heading_tolerance_rad=tolerance)
