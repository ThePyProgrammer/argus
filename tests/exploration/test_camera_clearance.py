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
    assert radius == pytest.approx(.6738235655335818)
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


def test_segment_clearance_is_checked_between_points_inside_a_passable_cell():
    room = grid([[100, 0], [0, 0]], resolution=1.)
    planner = PathPlanner(clearance_radius=.6)
    start, end = np.array([1.01, .01, 0.]), np.array([1.01, .99, 0.])
    assert planner._get_inflation_cost(room)[0, 1] < 1e5
    # Both endpoints are outside the exclusion disk. The middle passes only
    # 0.51 m from its center, despite staying in one passable grid cell.
    assert np.linalg.norm(start[:2] - [.5, .5]) > .6
    assert np.linalg.norm(end[:2] - [.5, .5]) > .6
    assert not planner.path_is_clear([start, end], room)


@pytest.mark.parametrize("value", [-.1, float("nan"), float("inf")])
def test_invalid_clearance_is_rejected(value):
    with pytest.raises(ValueError):
        PathPlanner(clearance_radius=value)
    with pytest.raises(ValueError):
        ExplorationConfig(camera_standoff_m=value).planning_radius(.4, .1)


@pytest.mark.parametrize("resolution", [.05, .1])
def test_corner_segments_use_one_raster_allowance(resolution):
    cells = np.zeros((70, 70), np.int8)
    cells[35, 35] = 100
    room = grid(cells, resolution)
    radius = ExplorationConfig().planning_radius(np.linalg.norm([.4, 0, .05]), resolution)
    planner = PathPlanner(clearance_radius=radius)
    corner = room.grid_to_world(35, 35)
    for distance, clear in ((radius + .05, False), (np.sqrt(2) * (radius + .01), True)):
        start = np.r_[corner + [-distance, 0], 0]
        end = np.r_[corner + [0, distance], 0]
        # Endpoints are clear; the diagonal segment passes distance/sqrt(2)
        # from the corner's occupied-cell center.
        assert np.linalg.norm(start[:2] - corner) > radius
        assert planner.path_is_clear([start, end], room) == clear


@pytest.mark.parametrize("resolution", [.05, .1])
def test_safe_segment_in_touched_inflated_cell_is_not_double_inflated(resolution):
    cells = np.zeros((70, 70), np.int8)
    cells[35, 35] = 100
    room = grid(cells, resolution)
    radius = ExplorationConfig().planning_radius(np.linalg.norm([.4, 0, .05]), resolution)
    planner = PathPlanner(clearance_radius=radius)
    costs = planner._get_inflation_cost(room)
    obstacle = room.grid_to_world(35, 35)
    examples = 0
    for angle in np.linspace(0, 2 * np.pi, 101):
        direction = np.array([np.cos(angle), np.sin(angle)])
        start = np.r_[obstacle + direction * (radius + .001), 0]
        end = np.r_[obstacle + direction * (radius + .002), 0]
        if costs[room.world_to_grid(start)] >= 1e5:
            examples += 1
            assert planner.path_is_clear([start, end], room)
    assert examples > 0  # Previously rejected despite exact clearance > radius.


@pytest.mark.parametrize("resolution", [.05, .1])
def test_narrow_corridor_reachability_planning_and_segment_checks_agree(resolution):
    radius = ExplorationConfig().planning_radius(np.linalg.norm([.4, 0, .05]), resolution)
    for half_gap_cells, clear in ((int(np.ceil(radius / resolution)), True),
                                  (int(np.floor(radius / resolution)), False)):
        cells = np.zeros((2 * half_gap_cells + 11, 50), np.int8)
        cells[5, :] = cells[5 + 2 * half_gap_cells, :] = 100
        room = grid(cells, resolution)
        middle = 5 + half_gap_cells
        start = np.r_[room.grid_to_world(middle, 5), 0]
        end = np.r_[room.grid_to_world(middle, 44), 0]
        planner = PathPlanner(clearance_radius=radius)
        assert planner.path_is_clear([start, end], room) == clear
        assert bool(planner.reachable_mask(start, room)[middle, 44]) == clear
        path = planner.plan(start, end, room)
        assert (path is not None) == clear
        if clear:
            assert planner.path_is_clear(path, room)
            # Adding a second half-cell diagonal would incorrectly close this gap.
            assert half_gap_cells * resolution < radius + resolution / np.sqrt(2)


def test_reusing_cells_at_another_resolution_rebuilds_metric_inflation():
    cells = np.zeros((30, 30), np.int8)
    cells[15, 15] = 100
    fine, coarse = grid(cells, .05), grid(cells, .1)
    planner = PathPlanner(clearance_radius=.6)
    assert planner._get_inflation_cost(fine)[15, 23] >= 1e5
    assert planner._get_inflation_cost(coarse)[15, 23] < 1e5
