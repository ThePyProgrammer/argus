"""Check physical stop paths against the predictor's declared drift allowance."""
from types import SimpleNamespace

import mujoco
import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.control.motion_clearance import project_motion
from src.exploration.config import ExplorationConfig


@pytest.mark.parametrize("walking_s", [.94, 1.01, 1.08, 1.13, 1.21])
@pytest.mark.parametrize("yaw_command", [-1., 0., 1.])
@pytest.mark.parametrize("speed", [-.8, -.4, 0., .2, .8])
def test_physical_stopping_path_fits_declared_projection(monkeypatch, walking_s, yaw_command, speed):
    monkeypatch.setattr(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(MultiRobotBridge, "_capture_frame", lambda *a: None)
    bridge = MultiRobotBridge(MultiRobotConfig(
        robot_ids=("robot_a",), spawn_positions={"robot_a": (0., 0., .3)},
        spawn_headings={"robot_a": 0.}, launch_viewer=False))
    try:
        bridge.start()
        positions, yaws = [], []
        for _ in range(round(walking_s / bridge.frame_dt)):
            bridge.set_velocity("robot_a", np.array([speed, 0.]), yaw_command)
            bridge.step()
            positions.append(bridge.get_body_position("robot_a")[:2])
            yaws.append(bridge.get_body_yaw("robot_a"))
        # Exact poses are a unit-test oracle; estimate velocity over the same
        # 100 ms history used in production, including variation within a stride.
        velocity = (positions[-1] - positions[-11]) / .1
        delta_yaw = yaws[-1] - yaws[-11]
        yaw_rate = np.arctan2(np.sin(delta_yaw), np.cos(delta_yaw)) / .1
        config = ExplorationConfig()
        path, times = project_motion(positions[-1], yaws[-1], velocity, yaw_rate,
                                     np.zeros(2), 0., active_yaw=yaw_command,
                                     config=config, control_dt=bridge.frame_dt)
        a, segments = path[:-1], np.diff(path, axis=0)
        lengths = np.linalg.norm(segments, axis=1)
        allowance = config.motion_drift_mps * times[1:] + lengths
        excess = []
        bridge.set_velocity("robot_a", np.zeros(2), 0.)
        for _ in range(round(1. / bridge.frame_dt)):
            bridge.step()
            position = bridge.get_body_position("robot_a")[:2]
            fractions = np.clip(np.sum((position-a)*segments, axis=1) /
                                np.maximum(lengths**2, 1e-20), 0., 1.)
            distances = np.linalg.norm(position - (a + fractions[:, None]*segments), axis=1)
            excess.append(float(np.min(distances-allowance)))
        assert max(excess) <= 1e-9, (walking_s, yaw_command, speed, max(excess))
    finally:
        bridge.stop()
