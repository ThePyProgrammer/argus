from dataclasses import replace

import numpy as np
import pytest

from src.control.motion_clearance import MotionClearanceGuard, project_motion
from src.exploration.config import ExplorationConfig
from src.exploration.occupancy_grid import OccupancyGrid2D


def room(wall=None, resolution=.05):
    cells = np.zeros((120, 120), dtype=np.int8)
    origin = np.array([-3., -3.])
    if wall is not None:
        axis, coordinate = wall
        index = int(np.floor((coordinate+3)/resolution))
        if axis == 0:
            cells[:, index] = 100
        else:
            cells[index, :] = 100
    return OccupancyGrid2D(cells, resolution, origin, 120, 120)


def pose(x=0., y=0., yaw=0.):
    p = np.eye(4)
    p[:2, 3] = [x, y]
    p[:2, :2] = [[np.cos(yaw), -np.sin(yaw)], [np.sin(yaw), np.cos(yaw)]]
    return p


def evaluate(guard, grid, linear=(0., 0.), angular=0., time=.05, body=None, **changes):
    args = dict(pose=pose() if body is None else body, sim_time=time, observation_time=time,
                grid=grid, radius=.4, calibration_valid=True, tracking_ok=True)
    args.update(changes)
    return guard.filter(np.array(linear), angular, **args)


def primed(grid, previous=None):
    guard = MotionClearanceGuard(ExplorationConfig())
    first = evaluate(guard, grid, time=0., body=previous)
    assert first.reason == "initial_velocity_observation"
    return guard


def test_clear_motion_is_allowed_with_a_complete_stopping_tail():
    grid = room()
    result = evaluate(primed(grid), grid, (.8, 0.))
    assert result.scale == 1 and result.stopping_clear
    assert result.path[-1, 0] > .5  # Not just the next 10 ms or .3 s command window.


@pytest.mark.parametrize("resolution", [.05, .1])
@pytest.mark.parametrize("sign", [-1, 1])
def test_forward_bootstrap_and_reverse_slow_before_wall(resolution, sign):
    grid = room((0, sign * 1.0), resolution)
    result = evaluate(primed(grid), grid, (sign * .8, 0.))
    assert 0 < result.scale < 1
    assert result.stopping_clear
    assert result.linear[0] * sign > 0


def test_near_wall_rejects_motion_without_shrinking_geometry():
    grid = room((0, .45))
    result = evaluate(primed(grid), grid, (.8, 0.))
    assert not result.linear.any()
    assert result.reason == "stopping_obstacle_clearance"
    assert not result.stopping_clear


def test_explicit_idle_does_not_erase_measured_momentum():
    grid = room((1, .65))
    result = evaluate(primed(grid, pose(y=-.04)), grid)
    assert not result.linear.any()
    assert not result.stopping_clear
    assert result.reason == "stopping_obstacle_clearance"
    assert result.path[-1, 1] > .3


@pytest.mark.parametrize("yaw", [-1., 1.])
def test_pure_rotation_uses_complete_body_camera_circle(yaw):
    grid = room((0, .9))
    assert evaluate(primed(grid), grid, angular=yaw).angular == yaw
    blocked = room((0, .35))
    result = evaluate(primed(blocked), blocked, angular=yaw)
    assert result.angular == 0 and not result.stopping_clear


@pytest.mark.parametrize("changes,reason", [
    ({"calibration_valid": False}, "missing_geometry_calibration"),
    ({"observation_time": -.2}, "stale_observation"),
    ({"tracking_ok": False}, "tracking_lost"),
    ({"sim_time": .5}, "stale_pose"),
    ({"sim_time": 0.}, "stale_pose"),
    ({"radius": float("nan")}, "invalid_state"),
])
def test_missing_or_stale_inputs_fail_closed(changes, reason):
    grid = room()
    result = evaluate(primed(grid), grid, (.8, 0), **changes)
    assert result.reason == reason and not result.linear.any()


def test_unknown_cells_are_not_assumed_free_for_center_travel():
    grid = room()
    grid.grid[:, 62:] = -1
    result = evaluate(primed(grid), grid, (.8, 0.))
    assert result.scale < 1
    assert result.reason in ("unknown_center_route", "slowed")
    assert result.path[:, 0].max() < .10


def test_yaw_reversal_preserves_delayed_initial_turn_and_first_motion_is_immediate():
    cfg = ExplorationConfig()
    args = dict(position=[0., 0.], yaw=0., velocity=[.8, 0.], yaw_rate=-1.,
                linear=np.array([.8, 0.]), angular=1., config=cfg, control_dt=.01,
                immediate_response=True)
    reversal, _ = project_motion(**args, active_yaw=-1.)
    assert reversal[2, 1] < 0
    args['yaw_rate'] = 1.
    first, _ = project_motion(**args, active_yaw=None)
    assert first[2, 1] > 0


def test_larger_reaction_delay_increases_stopping_distance():
    args = dict(position=[0., 0.], yaw=0., velocity=[.8, 0.], yaw_rate=0.,
                linear=np.zeros(2), angular=0., active_yaw=1., control_dt=.01)
    short, _ = project_motion(**args, config=ExplorationConfig())
    long, _ = project_motion(**args, config=replace(ExplorationConfig(), motion_reaction_s=.3))
    assert long[-1, 0] - short[-1, 0] == pytest.approx(.16, abs=.01)


def test_corner_between_two_safe_endpoints_is_not_tunneled():
    grid = room()
    grid.grid[68, 68] = 100  # Diagonal obstacle in projected travel.
    result = evaluate(primed(grid, pose(yaw=np.pi/4)), grid, (.8, 0.), body=pose(yaw=np.pi/4))
    assert result.scale < 1


def test_unsupported_sideways_motion_is_explicitly_stopped():
    grid = room()
    result = evaluate(primed(grid), grid, (0., .8))
    assert result.reason == "unsupported_lateral_command"
    assert not result.linear.any()


def test_pose_jump_outside_declared_model_stops():
    grid = room()
    result = evaluate(primed(grid), grid, (.8, 0.), body=pose(x=1.))
    assert result.reason == "motion_model_exceeded"


@pytest.mark.parametrize("name", ["motion_horizon_s", "motion_reaction_s", "motion_braking_mps2", "motion_settling_s"])
def test_invalid_motion_model_parameters_are_rejected(name):
    with pytest.raises(ValueError):
        MotionClearanceGuard(replace(ExplorationConfig(), **{name:0.}))


def test_guard_tracks_the_executed_gaits_restart_and_yaw_state():
    from src.locomotion.gait_controller import TrotGaitController
    guard, gait, grid = MotionClearanceGuard(ExplorationConfig()), TrotGaitController(), room()
    schedule = [(0., 0.)] + [(0., -1.)] * 5 + [(0., 0.)] + [(.8, 1.)] * 20
    for index, (speed, yaw) in enumerate(schedule):
        decision = evaluate(guard, grid, (speed, 0.), yaw, time=index*.01)
        gait.compute(*decision.linear, decision.angular, .01)
        if gait._active_yaw is None:
            assert guard._active_yaw is None
        else:
            assert guard._active_yaw == pytest.approx(gait._active_yaw)
        assert guard._restart_remaining == pytest.approx(gait._restart_remaining)


def test_projection_includes_restart_standing_time_without_erasing_momentum():
    args = dict(position=[0., 0.], yaw=0., velocity=[0., 0.], yaw_rate=0.,
                linear=np.array([.8, 0.]), angular=0., active_yaw=None,
                config=ExplorationConfig(), control_dt=.01, immediate_response=True)
    waiting, times = project_motion(**args, restart_wait=.08)
    first, _ = project_motion(**args)
    assert np.allclose(waiting[times <= .08], 0.)
    assert first[5, 0] > 0.
    args.update(velocity=[.4, 0.], immediate_response=False)
    coasting, times = project_motion(**args, restart_wait=.08)
    assert coasting[5, 0] > .01


def test_idle_projection_keeps_posture_settling_after_translation_brakes():
    config = ExplorationConfig()
    path, times = project_motion([0., 0.], 0., [.1, 0.], 0., np.zeros(2), 0.,
                                 active_yaw=None, config=config, control_dt=.01)
    assert times[-1] >= config.motion_settling_s
    # Do not shorten the safety horizon just because the velocity model has
    # stopped: real leg repositioning can still translate the body.
    np.testing.assert_allclose(path[-1], path[-20])


def test_settled_idle_does_not_repeat_a_posture_transition_but_restart_checks_it():
    grid = room((0, .55))
    guard = MotionClearanceGuard(ExplorationConfig())
    for index in range(110):
        decision = evaluate(guard, grid, time=index*.01)
        if index == 1:
            assert decision.reason == "stopping_obstacle_clearance"
    assert decision.stopping_clear
    assert decision.reason == "clear"
    # Do not turn the idle exemption into permission to move inside the
    # required transition envelope, even after a long stationary observation.
    restart = evaluate(guard, grid, angular=1., time=1.10)
    assert restart.angular == 0.
    assert restart.reason == "obstacle_clearance"
    assert restart.stopping_clear


def test_idle_history_does_not_hide_current_measured_momentum():
    grid = room((0, .7))
    guard = MotionClearanceGuard(ExplorationConfig())
    for index in range(110):
        evaluate(guard, grid, time=index*.01)
    moving = evaluate(guard, grid, time=1.10, body=pose(x=.10))
    assert not moving.stopping_clear


def test_stale_frames_cannot_accumulate_a_settled_idle_exemption():
    grid = room((0, .55))
    guard = primed(grid)
    for _ in range(150):
        assert evaluate(guard, grid, time=0.).reason == "stale_pose"
    assert not evaluate(guard, grid, time=.01).stopping_clear
