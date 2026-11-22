"""Executable route alternatives on frozen maps; truth never enters previews."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from src.control.motion_clearance import MotionClearanceGuard
from src.control.waypoint_runner import WaypointRunner
from src.exploration.config import ExplorationConfig
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.exploration.route_preview import preview_route, preview_recovery_endpoint
from tests.control.test_motion_clearance import room, pose
from tests.exploration.test_bounded_recovery import fixture


def settled(guard, grid, body, radius):
    for i in range(103):
        state = dict(pose=body, sim_time=i*.01, observation_time=i*.01, grid=grid,
                     radius=radius, calibration_valid=True, tracking_ok=True)
        guard.filter(np.zeros(2), 0., **state)
    return dict(state, sim_time=1.03, observation_time=1.03)


def test_frozen_rejected_turn_selects_later_executable_reverse_route(monkeypatch):
    root = Path(__file__).parents[1] / 'fixtures' / 'executable_routes'
    config = ExplorationConfig(**json.loads((root/'source.json').read_text())['config'])
    with np.load(root/'clutter101-terminal.npz', allow_pickle=False) as data:
        cells = data['grid'].copy()
        grid = OccupancyGrid2D(cells, float(data['resolution']), data['origin'], cells.shape[1], cells.shape[0])
        body, radius = data['pose'].copy(), float(data['radius'])
    loop, _, _ = fixture(monkeypatch, grid)
    from src.exploration.path_planner import PathPlanner
    from src.exploration.frontier_detector import FrontierDetector
    loop._config = config
    loop._motion_guard = MotionClearanceGuard(config)
    loop._execution_radius = radius
    loop._path_planner = PathPlanner(allow_unknown=False, clearance_radius=radius)
    loop._frontier_detector = FrontierDetector(grid.resolution, min_cluster_size=5)
    state = settled(loop._motion_guard, grid, body, radius)
    loop._evaluate_frontiers(body[:3, 3], body, None, guard_state=state)
    checks = loop.measurement_state['navigation']['route_checks']
    assert checks[0]['reason'] == 'obstacle_clearance'
    assert any(row['admissible'] and row['reverse'] for row in checks)
    assert len(checks) <= 2 * config.planning_candidate_limit
    runner = loop._current_waypoint_runner
    assert runner is not None
    linear, angular = runner.get_velocity(body)
    assert linear[0] < 0
    assert loop._motion_guard.preview(linear, angular, **state).scale > 0
    assert loop._blocked.state == 'navigating'


@pytest.mark.parametrize('heading', [0., .8, -2.])
def test_reverse_runner_aligns_rear_and_moves_toward_goal(heading):
    body = pose(yaw=heading)
    target = np.r_[-2*body[:2, 0], 0.]
    runner = WaypointRunner([target], reverse=True, heading_tolerance_rad=.25)
    linear, angular = runner.get_velocity(body)
    assert linear[0] < 0 and abs(angular) < 1e-10
    assert np.dot(body[:2, :2] @ linear, target[:2]) > 0


def test_forecast_isolation_includes_runner_pose_gait_and_settling_history():
    guard = MotionClearanceGuard(ExplorationConfig())
    state = settled(guard, room(), pose(), .4)
    runner = WaypointRunner([np.array([2., 0., 0.])], heading_tolerance_rad=.25)
    before = copy.deepcopy(guard.__dict__)
    original_last = guard.last
    result = preview_route(guard, runner, state)
    assert result.admissible and result.translation_m >= .15 and result.steps <= 54
    assert runner.current_waypoint_index == 0
    assert guard.last is original_last
    for name in ('_active_yaw', '_restart_remaining', '_idle_elapsed'):
        assert getattr(guard, name) == before[name]
    for actual, previous in zip(guard._poses, before['_poses']):
        assert actual[0] == previous[0] and actual[2] == previous[2]
        np.testing.assert_array_equal(actual[1], previous[1])
    np.testing.assert_array_equal(state['pose'], pose())
    assert state['sim_time'] == 1.03


@pytest.mark.parametrize('change,reason', [
    ({'observation_time': 0.}, 'stale_observation'),
    ({'tracking_ok': False}, 'tracking_lost'),
    ({'calibration_valid': False}, 'missing_geometry_calibration'),
])
def test_preview_preserves_live_input_rejections(change, reason):
    guard = MotionClearanceGuard(ExplorationConfig())
    state = settled(guard, room(), pose(), .4)
    result = preview_route(guard, WaypointRunner([np.array([2., 0., 0.])]), dict(state, **change))
    assert not result.admissible and result.reason == reason and result.steps == 1


def test_clear_first_command_is_not_enough_when_translation_crosses_unknown():
    guard = MotionClearanceGuard(ExplorationConfig())
    grid = room()
    grid.grid[:, 68:] = -1
    state = settled(guard, grid, pose(), .4)
    runner = WaypointRunner([np.array([2., 0., 0.])], heading_tolerance_rad=.25)
    assert guard.preview(*runner.get_velocity(pose()), **state).scale > 0
    result = preview_route(guard, runner, state, progress_m=.5)
    assert not result.admissible
    assert result.reason in {'unknown_center_route', 'stopping_unknown_center_route', 'preview_horizon'}


def test_recovery_endpoint_can_enable_checked_navigation():
    guard = MotionClearanceGuard(ExplorationConfig())
    state = settled(guard, room((0, 1.)), pose(), .75)
    runner = WaypointRunner([np.array([0., 2., 0.])], heading_tolerance_rad=.25)
    assert not preview_route(guard, runner, state).admissible
    endpoint, reason = preview_recovery_endpoint(guard, (-.6, 0., 0.), state)
    assert reason == 'predicted_endpoint'
    forecast_guard, forecast_state = endpoint
    assert forecast_state['pose'][0, 3] < -.1
    assert preview_route(forecast_guard, runner, forecast_state).admissible
    # A new obstacle after selection still overrides the forecast.
    state['grid'] = room((0, -.7))
    assert guard.filter(np.array([-.6, 0.]), 0., **state).scale == 0


def test_nearby_frontier_requires_translation_before_arrival(monkeypatch):
    loop, body, _ = fixture(monkeypatch, room())
    state = settled(loop._motion_guard, room(), body, .4)
    path = [np.array([0., 0., 0.]), np.array([.35, 0., 0.])]
    old_runner = WaypointRunner(path, arrival_threshold=.3, heading_tolerance_rad=.25)
    old = preview_route(loop._motion_guard, old_runner, state)
    assert not old.admissible and old.reason == 'route_complete'
    runner = loop._executable_runner(path, state)
    assert runner is not None
    assert preview_route(loop._motion_guard, runner, state).admissible
    assert runner.get_velocity(pose(.15))[0][0] > 0
    runner.get_velocity(pose(.34))
    assert runner.is_complete
