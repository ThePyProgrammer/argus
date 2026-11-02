"""Body/camera clearance must survive goal selection, corners, and smoothing."""

import numpy as np
import pytest

from src.exploration.config import ExplorationConfig
from src.exploration.occupancy_grid import OccupancyGrid2D
from src.exploration.path_planner import PathPlanner


def grid(cells, resolution=.1):
    cells = np.asarray(cells, dtype=np.int8)
    return OccupancyGrid2D(cells, resolution, np.zeros(2), cells.shape[1], cells.shape[0])


def test_envelope_contains_camera_standoff_at_every_heading_and_body_tilt():
    config = ExplorationConfig()
    offset = np.array([.4, 0., .05])
    radius = config.planning_radius(np.linalg.norm(offset), .1)
    assert radius == pytest.approx(.7445342436522365)
    for yaw in np.linspace(-np.pi, np.pi, 25):
        camera_xy = .4 * np.array([np.cos(yaw), np.sin(yaw)])
        assert np.linalg.norm(camera_xy) + config.camera_standoff_m < radius
    # The offset's full norm also bounds horizontal reach during body tilt.
    assert radius >= np.linalg.norm(offset) + config.camera_standoff_m + config.clearance_margin_m
    assert config.planning_radius(0., .1) >= config.footprint_radius_m


def test_near_column_goal_is_rejected_and_radius_change_invalidates_cached_cost():
    cells = np.zeros((40, 40), np.int8)
    cells[:, 20] = 100
    room = grid(cells)
    start, near, far = np.array([.55, 1.55, 0]), np.array([1.65, 1.55, 0]), np.array([1.05, 2.05, 0])
    planner = PathPlanner()
    assert planner.plan(start, near, room) is not None
    before = planner._get_inflation_cost(room)
    planner.set_clearance_radius(ExplorationConfig().planning_radius(np.linalg.norm([.4, 0, .05]), .1))
    after = planner._get_inflation_cost(room)
    assert after is not before
    assert not planner.reachable_mask(start, room)[room.world_to_grid(near)]
    assert planner.plan(start, near, room) is None
    path = planner.plan(start, far, room)
    assert path is not None and planner.path_is_clear(path, room)
    assert planner.plan(near, near, room) is None  # No start==goal bypass.


def test_diagonal_gap_is_not_reachable_or_plannable():
    room = grid([[0, 100], [100, 0]], resolution=1.)
    start, goal = np.array([.5, .5, 0]), np.array([1.5, 1.5, 0])
    planner = PathPlanner()
    assert not planner.reachable_mask(start, room)[1, 1]
    assert planner.plan(start, goal, room) is None
    assert not planner.path_is_clear([start, goal], room)


def test_smoothing_cannot_cut_through_obstacle_or_clearance_zone(monkeypatch):
    cells = np.zeros((40, 40), np.int8)
    cells[10:30, 20] = 100
    room = grid(cells)
    start, goal = np.array([.55, 2.05, 0]), np.array([3.55, 2.05, 0])
    planner = PathPlanner(clearance_radius=.5)
    # Deliberately bad smoother: endpoints are clear but the segment crosses a wall.
    monkeypatch.setattr("src.exploration.path_smoother.smooth_path", lambda path, **kw: [path[0], path[-1]])
    path = planner.plan(start, goal, room)
    assert path is not None and len(path) > 2
    assert planner.path_is_clear(path, room)
    np.testing.assert_allclose(path[0], start)
    np.testing.assert_allclose(path[-1], goal)


def test_segment_boundary_and_out_of_bounds_are_not_clamped_clear():
    room = grid([[0, 100], [0, 0]], resolution=1.)
    planner = PathPlanner()
    assert not planner.path_is_clear([np.array([1., .1, 0]), np.array([1., .9, 0])], room)
    assert not planner.path_is_clear([np.array([-.1, .5, 0]), np.array([.5, .5, 0])], room)


@pytest.mark.parametrize("value", [-.1, float("nan"), float("inf")])
def test_invalid_clearance_is_rejected(value):
    with pytest.raises(ValueError):
        PathPlanner(clearance_radius=value)
    with pytest.raises(ValueError):
        ExplorationConfig(camera_standoff_m=value).planning_radius(.4, .1)
