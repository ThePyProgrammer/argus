"""Real Go2 physics: calf clearance must improve without stopping locomotion."""

from dataclasses import replace
from types import SimpleNamespace

import mujoco
import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.exploration.evaluation.episode import _benchmark_model
from src.exploration.evaluation.scenarios import load_scenario
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams


@pytest.fixture
def walk(monkeypatch):
    # Exercise the actual bridge controller/physics cadence without rendering,
    # SLAM, planning, or coverage. No consumer receives these placeholder frames.
    monkeypatch.setattr(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(MultiRobotBridge, "_capture_frame", lambda *a: None)
    scene = load_scenario("branching_corridor")
    positions = {"robot_a": (0., -2.5, .3)}

    def run(speed, yaw, params=GaitParams()):
        config = MultiRobotConfig(robot_ids=("robot_a",), spawn_positions=positions,
                                  spawn_headings={"robot_a": 0.}, launch_viewer=False)
        bridge = MultiRobotBridge(config, model_factory=lambda: _benchmark_model(scene, positions))
        try:
            bridge.start()
            bridge._controllers["robot_a"]._gait = TrotGaitController(params)
            model, data = bridge.mj_model, bridge.mj_data
            floor = model.geom("floor").id
            feet = {model.geom("robot_a_" + leg).id for leg in ("FL", "FR", "RL", "RR")}
            start = bridge.get_body_position("robot_a")
            contacts, minimum_height = 0, float(start[2])
            for _ in range(round(2. / bridge.frame_dt)):
                bridge.set_velocity("robot_a", np.array([speed, 0.]), yaw)
                bridge.step()
                minimum_height = min(minimum_height, bridge.get_body_position("robot_a")[2])
                for contact in data.contact:
                    a, b = int(contact.geom1), int(contact.geom2)
                    if contact.dist <= 0 and floor in (a, b) and not ({a, b} & feet):
                        contacts += 1
            return contacts, bridge.get_body_position("robot_a") - start, minimum_height, bridge.get_body_yaw("robot_a")
        finally:
            bridge.stop()

    return run


@pytest.mark.parametrize("speed", [.4, .8])
def test_bounded_lift_removes_calf_contacts_without_disabling_forward_motion(walk, speed):
    # A very low lift bound reproduces the previous unrestricted targets.
    old = walk(speed, 0., replace(GaitParams(), swing_thigh_min=-10.))
    new = walk(speed, 0.)
    assert old[0] > 0  # Establish that this fixture reproduces the defect.
    assert new[0] == 0
    assert new[1][0] > .25
    assert new[1][0] >= .9 * old[1][0]
    assert new[2] > .2


@pytest.mark.parametrize("speed,yaw", [(.24, 0.), (.4, -1.), (.4, 1.), (.8, -1.), (.8, 1.),
                                      (.4, -.5), (.4, .5), (.8, -.5), (.8, .5)])
def test_supported_exploration_commands_keep_clearance_and_make_progress(walk, speed, yaw):
    contacts, displacement, height, heading = walk(speed, yaw)
    assert contacts == 0
    assert np.linalg.norm(displacement[:2]) > .2
    assert height > .2
    if yaw:
        assert heading * yaw > .1


@pytest.mark.parametrize("yaw", [-1., 0., 1.])
def test_lift_limit_preserves_continuity_at_swing_stance_boundaries(yaw):
    gait = TrotGaitController()
    for leg in range(4):
        for before, after in ((.5 - 1e-8, .5), (1 - 1e-8, 0.)):
            np.testing.assert_allclose(
                gait._leg_targets(leg, before, .8, 0., yaw, .8),
                gait._leg_targets(leg, after, .8, 0., yaw, .8), atol=1e-6, rtol=0)
