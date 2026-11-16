from types import SimpleNamespace

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.config import ExplorationConfig
from src.slam.protocol import SLAMResult, TrackingStatus
from tests.control.test_motion_clearance import room, pose
from tests.exploration.test_exploration_loop import MockBridge, MockOctoMap, MockSLAM


def frame(time, calibration=True):
    # Deliberately wrong truth pose: clearance must use estimated pose only.
    return SensorFrame(np.zeros((4, 4, 3)), np.ones((4, 4)), pose(99, 99), time,
                       body_from_camera=np.eye(4) if calibration else None,
                       collision_radius_m=.66 if calibration else None)


@pytest.mark.parametrize("source", ["bootstrap", "waypoint", "recovery"])
@pytest.mark.parametrize("blocked", [False, True])
def test_every_exploration_motion_path_uses_estimated_pose_and_guard(monkeypatch, source, blocked):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    grid = room((0, .70 if source != "recovery" else -.70)) if blocked else room()
    monkeypatch.setattr(loop, "planning_grid", lambda *a: grid)
    monkeypatch.setattr(loop._slam, "process_frame", lambda f: SLAMResult(
        pose=pose(), points=np.array([[0., 0., 0.]]), colors=np.zeros((1, 3)), tracking_status=TrackingStatus.OK))
    loop.step_once(frame(0.), 0)  # Establish velocity observation.
    if source == "waypoint":
        loop.set_waypoint_target([np.array([2., 0., 0.])])
    elif source == "recovery":
        loop._blocked.start_recovery((-.2, 0., 0.), pose(), .05)
    linear, angular, metrics = loop.step_once(frame(.05), 1)
    decision = loop.measurement_state["motion_clearance"]
    assert loop._path_planner._clearance_radius == pytest.approx(
        loop.config.planning_radius(0., grid.resolution, .66))
    if blocked:
        assert not linear.any() and angular == 0
        assert decision["reason"] == "stopping_obstacle_clearance"
        assert loop._current_waypoint_runner is None
        assert not loop.measurement_state["recovering"]
    else:
        assert linear[0] < 0 if source == "recovery" else linear[0] > 0
        assert decision["stopping_clear"]


def test_missing_calibration_does_not_fall_back_to_unsafe_nominal_radius(monkeypatch):
    loop = ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap())
    monkeypatch.setattr(loop, "planning_grid", lambda: room())
    linear, angular, _ = loop.step_once(frame(0., calibration=False), 0)
    assert not linear.any() and angular == 0
    assert loop.measurement_state["motion_clearance"]["reason"] == "missing_geometry_calibration"


def test_moving_teammate_is_not_stopped_by_another_robots_guard(monkeypatch):
    # Independent guards must not share pose/yaw/stopping state.
    loops = [ExplorationLoop(MockBridge(), MockSLAM(), MockOctoMap()) for _ in range(2)]
    for loop, grid in zip(loops, (room((0, .70)), room())):
        monkeypatch.setattr(loop, "planning_grid", lambda grid=grid: grid)
        monkeypatch.setattr(loop._slam, "process_frame", lambda f: SLAMResult(
            pose=pose(), points=np.array([[0., 0., 0.]]), colors=np.zeros((1, 3)), tracking_status=TrackingStatus.OK))
        loop.step_once(frame(0.), 0)
    assert not loops[0].step_once(frame(.05), 1)[0].any()
    assert loops[1].step_once(frame(.05), 1)[0][0] > 0
