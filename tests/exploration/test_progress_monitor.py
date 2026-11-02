"""Mobility checks must be independent of sensor frequency and gait bobbing."""

import math

import numpy as np
import pytest

from src.exploration.exploration_loop import StuckRecovery
from src.exploration.progress_monitor import ProgressMonitor


def pose(x=0., y=0., z=0., yaw=0.):
    result = np.eye(4)
    result[:3, 3] = [x, y, z]
    c, s = math.cos(yaw), math.sin(yaw)
    result[:2, :2] = [[c, -s], [s, c]]
    return result


@pytest.mark.parametrize("dt", [.01, .05, .2])
def test_slow_continuous_walking_does_not_trigger_recovery(dt):
    monitor = ProgressMonitor(2., .05, .1)
    for t in np.arange(0, 8 + dt / 2, dt):
        # Only 1 mm per frame at 100 Hz, but adequate net progress.
        assert not monitor.update(pose(x=.1 * t), t, np.array([.4, 0]), 0.)


@pytest.mark.parametrize("dt", [.01, .05, .2])
def test_blocked_robot_triggers_at_two_seconds_despite_vertical_motion(dt):
    monitor = ProgressMonitor(2., .05, .1)
    for t in np.arange(0, 2, dt):
        assert not monitor.update(pose(z=.05 * math.sin(t * 10)), t, np.array([.4, 0]), 0.)
    assert monitor.update(pose(), 2., np.array([.4, 0]), 0.)


def test_idle_and_mode_changes_get_fresh_windows():
    monitor = ProgressMonitor(2., .05, .1)
    for t in range(10):
        assert not monitor.update(pose(), t, np.zeros(2), 0.)
    assert not monitor.update(pose(), 10., np.array([.4, 0]), 0.)
    assert not monitor.update(pose(), 11.9, np.array([.4, 0]), 0.)
    assert not monitor.update(pose(), 12., np.zeros(2), 1.)
    assert monitor.update(pose(), 14., np.zeros(2), 1.)
    monitor.reset()  # Recovery completion starts a new observation window.
    assert not monitor.update(pose(), 16., np.array([.4, 0]), 0.)
    assert not monitor.update(pose(), 17.9, np.array([.4, 0]), 0.)


def test_turning_progress_wraps_yaw_but_does_not_mask_blocked_translation():
    rotating = ProgressMonitor(2., .05, .1)
    walking = ProgressMonitor(2., .05, .1)
    for t in np.arange(0, 2, .01):
        p = pose(yaw=3.1 + .4 * t)
        assert not rotating.update(p, t, np.zeros(2), 1.)
        assert not walking.update(p, t, np.array([.4, 0]), 1.)
    assert not rotating.update(pose(yaw=3.9), 2., np.zeros(2), 1.)
    assert walking.update(pose(yaw=3.9), 2., np.array([.4, 0]), 1.)


def test_small_oscillations_do_not_accumulate_into_progress():
    monitor = ProgressMonitor(2., .05, .1)
    for t in np.arange(0, 2, .01):
        assert not monitor.update(pose(x=.01 * math.sin(20 * t)), t, np.array([.4, 0]), 0.)
    assert monitor.update(pose(), 2., np.array([.4, 0]), 0.)


@pytest.mark.parametrize("dt", [.01, .05, .2, 2.])
def test_recovery_displacement_and_turn_are_bounded_at_all_cadences(dt):
    recovery = StuckRecovery(reverse_duration_s=.25, turn_angle=1.7,
                             angular_speed=1.5, reverse_speed=1.,
                             rng=np.random.default_rng(101))
    recovery.trigger()
    distance, angle = 0., 0.
    for _ in range(500):
        command = recovery.step(dt)
        if command is None:
            break
        vx, _, omega = command
        distance += vx * dt
        angle += omega * dt
        assert abs(vx) <= 1.
        assert abs(omega) <= 1.5
    assert not recovery.is_active
    assert distance == pytest.approx(-.25)
    assert abs(angle) == pytest.approx(1.7)


@pytest.mark.parametrize("value", [0., -1., float("nan"), float("inf")])
def test_invalid_time_parameters_are_rejected(value):
    with pytest.raises(ValueError):
        ProgressMonitor(value, .05, .1)
    with pytest.raises(ValueError):
        StuckRecovery(reverse_duration_s=value)
    with pytest.raises(ValueError):
        StuckRecovery().step(value)
