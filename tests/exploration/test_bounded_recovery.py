"""Blocked navigation fixtures use estimated poses and the real clearance guard."""
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.exploration.config import ExplorationConfig
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.frontier_detector import FrontierCluster
from src.slam.protocol import SLAMResult, TrackingStatus
from tests.control.test_motion_clearance import room, pose
from tests.exploration.test_motion_clearance_integration import frame
from tests.exploration.test_exploration_loop import MockBridge, MockSLAM, MockOctoMap


def fixture(monkeypatch, grid, *, planning_blocked=False, goal=(2., 0.)):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap(),
                           ExplorationConfig(ground_filter=False))
    body = pose()
    monkeypatch.setattr(loop, "planning_grid", lambda *a: grid)
    monkeypatch.setattr(loop._slam, "process_frame", lambda f: SLAMResult(
        body.copy(), np.empty((0, 3)), np.empty((0, 3)), tracking_status=TrackingStatus.OK))
    # Fresh observed map, independent of the deliberately wrong simulator pose.
    original = loop._update_slam
    def observe(f):
        loop._last_observation_time = f.sim_time
        return original(f)
    monkeypatch.setattr(loop, "_update_slam", observe)
    cluster = FrontierCluster(np.array([*goal, 0.]), 1,
                              np.array([grid.world_to_grid(np.array(goal))]))
    monkeypatch.setattr(loop.frontier_detector, "detect", lambda *a, **kw: [cluster])
    plan = MagicMock(side_effect=lambda start, goal, grid: None if planning_blocked else list(np.linspace(start, goal, 21)))
    monkeypatch.setattr(loop._path_planner, "plan", plan)
    return loop, body, plan


def tick(loop, i):
    return loop.step_once(frame(i * .05), i + 30)


def test_true_trap_stays_stopped_and_finishes_with_reason(monkeypatch):
    loop, _, plan = fixture(monkeypatch, room((0, .7)), planning_blocked=True)
    states = []
    for i in range(220):
        linear, angular, metrics = tick(loop, i)
        assert not linear.any() and angular == 0
        states.append(loop.measurement_state["navigation"]["state"])
    diagnostic = loop.measurement_state["navigation"]
    assert {"blocked", "replanning", "failed"} <= set(states)
    assert diagnostic["reason"] == "no_safe_recovery"
    assert metrics.terminated
    assert plan.call_count <= 3
    assert diagnostic["recovery_attempts"] <= 2


def test_repeated_execution_rejection_has_bounded_planning(monkeypatch):
    loop, _, plan = fixture(monkeypatch, room((0, .95)), goal=(0., 2.))
    for i in range(240):
        tick(loop, i)
    diagnostic = loop.measurement_state["navigation"]
    assert diagnostic["state"] == "failed"
    assert diagnostic["execution_rejections"] > 0
    assert plan.call_count <= 6
    assert diagnostic["replan_attempts"] <= 4


def test_recoverable_planning_blockage_requires_observed_motion(monkeypatch):
    loop, body, plan = fixture(monkeypatch, room(), planning_blocked=True)
    # A temporary route failure is recoverable by a checked retreat and replan.
    moved = False
    for i in range(180):
        linear, angular, _ = tick(loop, i)
        diagnostic = loop.measurement_state["navigation"]
        if diagnostic["state"] == "recovering" and linear[0] < 0:
            assert loop.measurement_state["motion_clearance"]["stopping_clear"]
            body[0, 3] += linear[0] * .05
            moved = True
        if moved and diagnostic["recovery_outcome"] == "progress":
            plan.side_effect = lambda start, goal, grid: list(np.linspace(start, goal, 21))
        if diagnostic["state"] == "navigating" and moved:
            body[0, 3] += linear[0] * .05
        if diagnostic["reason"] == "navigation_progress":
            break
    assert moved
    assert diagnostic["state"] == "navigating"
    assert diagnostic["reason"] == "navigation_progress"


def test_accepted_recovery_without_pose_progress_is_not_success(monkeypatch):
    loop, _, _ = fixture(monkeypatch, room(), planning_blocked=True)
    for i in range(240):
        tick(loop, i)
    diagnostic = loop.measurement_state["navigation"]
    assert diagnostic["state"] == "failed"
    assert diagnostic["recovery_outcome"] == "no_progress"


def test_failed_robot_does_not_stop_productive_teammate(monkeypatch):
    trapped, _, _ = fixture(monkeypatch, room((0, .7)), planning_blocked=True)
    moving, body, _ = fixture(monkeypatch, room())
    for i in range(120):
        tick(trapped, i)
        linear, _, metrics = tick(moving, i)
        body[0, 3] += linear[0] * .01
    assert trapped.measurement_state["navigation"]["state"] == "failed"
    assert moving.measurement_state["navigation"]["state"] == "navigating"
    assert not metrics.terminated and linear[0] > 0


def test_recovery_rechecks_changed_obstacles_and_never_reuses_preview(monkeypatch):
    grid = room()
    loop, _, _ = fixture(monkeypatch, grid, planning_blocked=True)
    for i in range(100):
        linear, _, _ = tick(loop, i)
        if loop.measurement_state["recovering"]:
            assert linear[0] < 0
            break
    else:
        pytest.fail("No checked recovery started")
    grid.grid[:] = room((0, -.7)).grid  # Newly observed obstruction behind robot.
    linear, angular, _ = tick(loop, i + 1)
    assert not linear.any() and angular == 0
    assert loop.measurement_state["navigation"]["recovery_outcome"] == "execution_rejected"
    assert loop.measurement_state["navigation"]["state"] == "blocked"


def test_recoverable_observed_space_blockage_with_real_planner(monkeypatch):
    from src.exploration.path_planner import PathPlanner
    grid = room()
    # Known-free islands separated by unseen center space. Observing the gap
    # can restore a route without removing an obstacle or shrinking the body.
    grid.grid[:, 65:75] = -1
    loop, _, _ = fixture(monkeypatch, grid)
    loop._path_planner = PathPlanner(allow_unknown=False)
    tick(loop, 0)
    assert loop.measurement_state["navigation"]["state"] == "blocked"
    assert loop.measurement_state["navigation"]["reason"] == "no_reachable_route"
    for i in range(1, 10):
        assert not tick(loop, i)[0].any()
    grid.grid[:, 65:75] = 0  # Fresh observations supply free space, not map repair.
    for i in range(10, 25):
        linear, _, _ = tick(loop, i)
    assert loop.measurement_state["navigation"]["state"] == "navigating"
    assert linear[0] > 0


def test_blocked_start_can_replan_after_fresh_free_space_observations(monkeypatch):
    from src.exploration.path_planner import PathPlanner
    grid = room()
    grid.grid[58:63, 58:63] = -1
    loop, _, _ = fixture(monkeypatch, grid)
    loop._path_planner = PathPlanner(allow_unknown=False)
    tick(loop, 0)
    assert loop.measurement_state["navigation"]["reason"] == "blocked_start"
    for i in range(1, 10):
        linear, angular, _ = tick(loop, i)
        assert not linear.any() and angular == 0
    grid.grid[58:63, 58:63] = 0  # Observe the initial unknown center neighborhood.
    for i in range(10, 25):
        linear, _, _ = tick(loop, i)
    assert loop.measurement_state["navigation"]["state"] == "navigating"
    assert linear[0] > 0


def test_unknown_cells_are_not_a_shortcut_in_exploration_routes():
    from src.exploration.path_planner import PathPlanner
    grid = room()
    grid.grid[:, 65:75] = -1
    planner = PathPlanner(allow_unknown=False)
    assert planner.plan(np.array([0., 0.]), np.array([2., 0.]), grid) is None
    assert not planner.path_is_clear([np.array([0., 0.]), np.array([2., 0.])], grid)


def test_preview_preserves_pose_and_gait_history():
    from src.control.motion_clearance import MotionClearanceGuard
    from tests.control.test_motion_clearance import evaluate
    guard = MotionClearanceGuard(ExplorationConfig())
    grid = room()
    evaluate(guard, grid, time=0.)
    original = guard.last
    args = dict(pose=pose(), sim_time=.05, observation_time=.05, grid=grid,
                radius=.75, calibration_valid=True, tracking_ok=True)
    for command in [(-.2, 0.), (.2, 0.)]:
        assert guard.preview(np.array(command), 0., **args).scale > 0
    assert guard.last is original and len(guard._poses) == 1
    assert guard._active_yaw is None and guard._idle_elapsed == 0.
    assert guard.filter(np.array([-.2, 0.]), 0., **args).scale > 0


def test_blocked_deadline_counts_waiting_and_recovery_time(monkeypatch):
    loop, _, _ = fixture(monkeypatch, room(), planning_blocked=True)
    loop.config.blocked_timeout_s = 3.5
    for i in range(70):
        _, _, metrics = tick(loop, i)
        assert not metrics.terminated
    _, _, metrics = tick(loop, 70)
    assert metrics.terminated
    assert loop.measurement_state["navigation"]["reason"] == "blocked_timeout"


@pytest.mark.parametrize("command,wrong_pose", [
    ((-.6, 0., 0.), pose(.2, 0.)),
    ((-.6, 0., 0.), pose(0., .2)),
    ((0., 0., .5), pose(yaw=-.5)),
])
def test_wrong_way_recovery_motion_is_not_progress(command, wrong_pose):
    from src.exploration.blocked_navigation import BlockedNavigation
    state = BlockedNavigation(ExplorationConfig())
    state.block("fixture_blocked", 0.)
    state.start_recovery(command, pose(), 1.)
    state.observe(wrong_pose, 2.5)
    assert state.state == "blocked" and state.recovery_outcome == "no_progress"


def test_turning_drift_cannot_reset_budget_or_count_toward_later_walking():
    from src.exploration.blocked_navigation import BlockedNavigation
    state = BlockedNavigation(ExplorationConfig())
    state.block("fixture_blocked", 0.)
    state.replans = 2
    state.installed(pose())
    state.observe(pose(.20, yaw=.5), 1., navigation_translation=False)
    assert state.since == 0. and state.replans == 2
    state.observe(pose(.21, yaw=.5), 1.1, navigation_translation=True)
    assert state.since == 0. and state.reason == "route_installed"
    state.observe(pose(.36, yaw=.5), 2., navigation_translation=True)
    assert state.since is None and state.replans == 0
    assert state.reason == "navigation_progress"
