"""Physics-step regressions for abrupt turn/walk commands, without navigation."""

from types import SimpleNamespace
from dataclasses import replace

import mujoco
import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.exploration.evaluation.episode import _benchmark_model, _contacts
from src.exploration.evaluation.scenarios import load_scenario
from src.metrics.contact_metrics import PhysicsContactCollector
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams


def instantaneous_gait():
    return TrotGaitController(replace(GaitParams(), command_yaw_acceleration=1e9))


@pytest.fixture
def run_schedule(monkeypatch):
    monkeypatch.setattr(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(MultiRobotBridge, "_capture_frame", lambda *a: None)
    scene = load_scenario("connected_rooms")
    positions = {"robot_a": (-4.5, 2., .3)}

    def run(schedule, gait_factory=None):
        config = MultiRobotConfig(robot_ids=tuple(positions), spawn_positions=positions,
                                  spawn_headings={"robot_a": 0.}, launch_viewer=False)
        bridge = MultiRobotBridge(config, model_factory=lambda: _benchmark_model(scene, positions))
        try:
            bridge.start()
            if gait_factory is not None:
                bridge._controllers["robot_a"]._gait = gait_factory()
            contacts = PhysicsContactCollector(_contacts(bridge), start_sim_time=float(bridge.mj_data.time))
            bridge.add_physics_step_observer(contacts.observe_step)
            start = bridge.get_body_position("robot_a")
            minimum_height, maximum_tilt = start[2], 0.
            for duration, speed, yaw in schedule:
                phase_start = bridge.get_body_position("robot_a")
                for _ in range(round(duration / bridge.frame_dt)):
                    bridge.set_velocity("robot_a", np.array([speed, 0.]), yaw)
                    bridge.step()
                    minimum_height = min(minimum_height, bridge.get_body_position("robot_a")[2])
                    base = bridge.mj_model.body("robot_a_base").id
                    rot = bridge.mj_data.xmat[base].reshape(3, 3)
                    maximum_tilt = max(maximum_tilt, np.arccos(np.clip(rot[2, 2], -1, 1)))
            return {"contacts": [e for e in contacts.summary()["episodes"] if e["kind"] != "foot_floor"],
                    "displacement": bridge.get_body_position("robot_a") - start,
                    "min_height": minimum_height, "max_tilt": maximum_tilt,
                    "final_phase_displacement": bridge.get_body_position("robot_a") - phase_start,
                    "yaw": bridge.get_body_yaw("robot_a")}
        finally:
            bridge.stop()
    return run


@pytest.mark.parametrize("prefix", [
    [], [(.27, 0., 1.), (.01, 0., 0.)],
    [(1.28, 0., 1.), (.07, 0., -1.), (.27, 0., 1.), (.01, 0., 0.)],
    [(.29, .4, 0.), (.02, 0., 1.), (.01, 0., 0.), (.23, 0., -1.), (.01, 0., 0.),
     (.31, 0., 1.), (.62, 0., -1.), (.01, 0., 0.), (1.28, 0., 1.), (.07, 0., -1.),
     (.27, 0., 1.), (.01, 0., 0.)],
])
@pytest.mark.parametrize("sign", [-1., 1.])
def test_turn_to_walk_keeps_calf_clearance(run_schedule, prefix, sign):
    # Reduced candidate from the recorded turn -> walk switch at 3.21 seconds.
    schedule = [(duration, speed, yaw * sign) for duration, speed, yaw in
                prefix + [(.08, 0., -1.), (1., .78, .18)]]
    result = run_schedule(schedule)
    previous = run_schedule(schedule, instantaneous_gait)
    assert not result["contacts"], result
    assert result["min_height"] > .2
    assert result["max_tilt"] < .3
    progress = np.linalg.norm(result["final_phase_displacement"][:2])
    previous_progress = np.linalg.norm(previous["final_phase_displacement"][:2])
    assert progress > .15
    assert progress >= .9 * previous_progress


def test_reduced_sequence_reproduces_original_calf_contact(run_schedule):
    schedule = [(.27, 0., 1.), (.01, 0., 0.), (.08, 0., -1.), (1., .78, .18)]
    original = run_schedule(schedule, instantaneous_gait)
    contact, = original["contacts"]
    assert contact["kind"] == "leg_floor"
    assert .43 < contact["start_elapsed_s"] < .47
    assert contact["touch_duration_s"] > 0
    assert contact["peak_normal_force_n"] > 0
    corrected = run_schedule(schedule)
    assert not corrected["contacts"]


@pytest.mark.parametrize("yaw", [-1., 0., 1.])
def test_constant_commands_keep_existing_targets(yaw):
    gait, original = TrotGaitController(), instantaneous_gait()
    for _ in range(200):
        np.testing.assert_array_equal(gait.compute(.8, 0., yaw, .01), original.compute(.8, 0., yaw, .01))


@pytest.mark.parametrize("dt", [.005, .01, .02])
def test_yaw_slew_uses_simulated_time_and_reaches_requested_yaw(dt):
    gait = TrotGaitController()
    gait.compute(.4, 0., -1., dt)
    for step in range(round(.25 / dt) + 1):
        before = gait._active_yaw
        gait.compute(.4, 0., 1., dt)
        assert 0 <= gait._active_yaw - before <= GaitParams().command_yaw_acceleration * dt + 1e-12
        assert gait._active_yaw == pytest.approx(min(-1 + (step + 1) * 8 * dt, 1.))
    assert gait._active_yaw == 1.


def test_reversal_crossing_zero_keeps_gait_phase_but_explicit_idle_resets():
    gait = TrotGaitController()
    gait.compute(0., 0., .08, .01)
    targets = gait.compute(0., 0., -.08, .01)
    assert gait._active_yaw == 0.
    assert gait._phase == pytest.approx(.06)
    standing = np.tile([0., .9, -1.8], 4)
    assert not np.array_equal(targets, standing)
    np.testing.assert_array_equal(gait.compute(0., 0., 0., .01), standing)
    assert gait._active_yaw is None and gait._phase == 0
    gait.compute(0., 0., -1., .01)
    assert gait._active_yaw == -1.


@pytest.mark.parametrize("limit", [0, -1, np.nan, np.inf])
def test_invalid_yaw_acceleration_is_rejected(limit):
    with pytest.raises(ValueError, match="yaw acceleration"):
        TrotGaitController(replace(GaitParams(), command_yaw_acceleration=limit))


@pytest.mark.parametrize("floor", ['type="plane" size="5 5 .1"', 'type="box" size="5 5 .1" pos="0 0 -.1"'])
@pytest.mark.parametrize("shape,expected", [
    ('type="box" size=".1 .2 .3"', .7),
    ('type="box" size=".1 .2 .3" quat="1 0 1 0"', .9),
    ('type="cylinder" size=".1 .3"', .7),
    ('type="cylinder" size=".1 .3" quat="1 0 1 0"', .9),
    ('type="capsule" size=".1 .3"', .6),
    ('type="capsule" size=".1 .3" quat="1 0 1 0"', .9),
    ('type="sphere" size=".1"', .9),
])
def test_replay_clearance_uses_primitive_extent_above_floor_top(floor, shape, expected):
    from scripts.diagnose_gait_replay import floor_clearance
    model = mujoco.MjModel.from_xml_string(
        f'<mujoco><worldbody><geom {floor}/><geom pos="0 0 1" {shape}/></worldbody></mujoco>')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    assert floor_clearance(model, data, 1, 0) == pytest.approx(expected)
