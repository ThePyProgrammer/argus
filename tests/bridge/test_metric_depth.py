"""Protect metric renderer output from content-dependent reinterpretation."""

from types import SimpleNamespace

import numpy as np
import pytest

from src.bridge.depth import clean_metric_depth
from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.sim_bridge import MuJoCoBridge


def test_close_distances_remain_metric_and_input_is_unchanged():
    original = np.array([[.05, .25], [.75, 1.0]], dtype=np.float32)
    cleaned = clean_metric_depth(original, 50)
    assert np.array_equal(cleaned, original)
    assert not np.shares_memory(cleaned, original)


def test_far_and_invalid_depth_does_not_create_a_surface_at_the_range_limit():
    values = np.array([[0, -1, np.nan, np.inf, 20, 21, 49.5]], dtype=np.float32)
    assert np.array_equal(clean_metric_depth(values, 50), [[0, 0, 0, 0, 20, 0, 0]])


@pytest.mark.parametrize("depth", [np.zeros((2, 2, 3)), np.zeros((2, 2), dtype=np.uint8)])
def test_non_metric_image_is_rejected(depth):
    with pytest.raises(ValueError):
        clean_metric_depth(depth, 50)


@pytest.mark.parametrize("bridge_class", [MuJoCoBridge, MultiRobotBridge])
def test_both_capture_paths_preserve_sub_meter_depth(bridge_class):
    class Renderer:
        is_depth = False

        def update_scene(self, *args, **kwargs):
            pass

        def enable_depth_rendering(self):
            self.is_depth = True

        def disable_depth_rendering(self):
            self.is_depth = False

        def render(self):
            return np.full((2, 2), .5, dtype=np.float32) if self.is_depth else np.zeros((2, 2, 3), dtype=np.uint8)

    bridge = bridge_class.__new__(bridge_class)
    renderer = Renderer()
    bridge._model = SimpleNamespace(stat=SimpleNamespace(extent=1), vis=SimpleNamespace(map=SimpleNamespace(zfar=50)))
    bridge._data = SimpleNamespace(cam_xpos=np.array([[1., 2., .5]]), cam_xmat=np.eye(3).reshape(1, 9))
    bridge._step_count, bridge._dt = 3, .01
    if bridge_class is MuJoCoBridge:
        bridge._renderer, bridge._cam_id = renderer, 0
        bridge._body_from_camera = np.eye(4)
        frame = bridge._capture_frame()
    else:
        bridge._renderers, bridge._cam_ids = {"robot_a": renderer}, {"robot_a": 0}
        bridge._camera_mounts = {"robot_a": np.eye(4)}
        frame = bridge._capture_frame("robot_a")
    assert np.all(frame.depth == .5)
    assert frame.sim_time == pytest.approx(.03)
    assert np.array_equal(frame.ground_truth_pose[:3, 3], [1, 2, .5])
