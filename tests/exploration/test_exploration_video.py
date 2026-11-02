"""Replay timing and evidence checks must hold before publishing a video."""

from types import SimpleNamespace

import numpy as np
import mujoco
import pytest

from scripts.render_exploration_video import (
    VIEW_H, VIEW_W, frame_indices, replay, top_camera, validate_history,
)


def history():
    return {
        "result": {"frame_dt": .01, "elapsed_s": .02},
        "trajectory": [{"elapsed_s": t, "positions": {"robot_a": [t, 0, 0]}}
                       for t in (0, .01, .02)],
        "steps": [{"elapsed_s": t, "coverage": .1 + t} for t in (0, .01, .02)],
        "commands": [{"elapsed_s": t, "commands": {"robot_a": {
            "mode": mode, "linear": [1, 0], "yaw_rate": 0, "waypoint": None}}}
            for t, mode in ((0, "velocity"), (.01, "velocity"), (.02, "stop"))],
    }


class FakeBridge:
    def __init__(self):
        self.mj_data = SimpleNamespace(qpos=np.zeros(3), qvel=np.zeros(3))
        self.commands = []

    def set_command(self, rid, command):
        self.commands.append(command)

    def step(self):
        self.mj_data.qpos[0] += .01

    def get_body_position(self, rid):
        return self.mj_data.qpos


def test_terminal_command_does_not_add_a_physics_interval():
    recorded, bridge = history(), FakeBridge()
    validate_history(recorded)
    states, error = replay(recorded, bridge)
    assert len(states) == 3
    assert [command.mode for command in bridge.commands] == ["velocity", "velocity"]
    assert error == 0
    np.testing.assert_array_equal(states[0][0], [0, 0, 0])
    np.testing.assert_array_equal(states[-1][0], [.02, 0, 0])


@pytest.mark.parametrize("index", [0, 1, 2])
def test_divergent_replay_is_rejected_including_initial_state(index):
    recorded = history()
    recorded["trajectory"][index]["positions"]["robot_a"][0] += .001
    with pytest.raises(ValueError, match="Replay diverged"):
        replay(recorded, FakeBridge())


@pytest.mark.parametrize("field", ["trajectory", "steps", "commands"])
def test_misaligned_timestamps_are_rejected(field):
    recorded = history()
    recorded[field][1]["elapsed_s"] += .005
    with pytest.raises(ValueError, match="timestamps"):
        validate_history(recorded)


def test_horizon_without_terminal_command_is_accepted():
    recorded = history()
    recorded["commands"].pop()
    np.testing.assert_array_equal(validate_history(recorded), [0, .01, .02])


def test_video_sampling_includes_terminal_state_without_looking_ahead():
    times = np.arange(908) * .01
    indices = frame_indices(times, fps=25, speed=.5)
    assert indices[0] == 0
    assert indices[-1] == 907
    assert len(indices) == 455
    samples = np.minimum(np.arange(len(indices)) * .5 / 25, times[-1])
    assert np.all(times[indices] <= samples + 1e-10)
    assert np.all(samples - times[indices] < .01 + 1e-10)


@pytest.mark.parametrize("speed", [0, -1, float("nan")])
def test_invalid_playback_speed_is_rejected(speed):
    with pytest.raises(ValueError, match="positive"):
        frame_indices(np.array([0, .01]), fps=25, speed=speed)


def test_top_camera_is_orthographic_and_fits_the_room():
    model = mujoco.MjModel.from_xml_string('<mujoco><worldbody><geom size="1"/></worldbody></mujoco>')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    camera = top_camera(model, SimpleNamespace(x_min=-6, x_max=6, y_min=-4, y_max=4))
    scene = mujoco.MjvScene(model, maxgeom=10)
    mujoco.mjv_updateScene(model, data, mujoco.MjvOption(), None, camera,
                          mujoco.mjtCatBit.mjCAT_ALL, scene)
    for eye in scene.camera:
        assert eye.orthographic == 1
        height = eye.frustum_top - eye.frustum_bottom
        assert height >= 9
        assert height * VIEW_W / VIEW_H >= 13
        np.testing.assert_allclose(eye.forward, [0, 0, -1], atol=1e-7)
