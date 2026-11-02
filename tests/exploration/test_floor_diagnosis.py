"""Simulator pose correction labels samples without changing filter inputs."""

import numpy as np
from scipy.spatial.transform import Rotation

from scripts.diagnose_exploration_floor import floor_support


def test_floor_diagnostic_undoes_pose_error_and_preserves_inputs():
    truth = np.eye(4)
    truth[:3, 3] = [2, -1, .32]
    estimate = np.eye(4)
    estimate[:3, :3] = Rotation.from_euler("xyz", [.1, -.2, .3]).as_matrix()
    estimate[:3, 3] = [10, 3, -4]
    actual = np.array([[2., -1, 0], [2.5, -1, 0], [2, -1, .06]])
    camera = actual - truth[:3, 3]
    points = camera @ estimate[:3, :3].T + estimate[:3, 3]
    mask = np.array([True, False, True])
    before = points.copy()
    recovered, counts = floor_support(points, mask, estimate, truth)
    np.testing.assert_allclose(recovered, actual, atol=1e-14)
    assert counts == {"points": 3, "true_floor_points": 2, "missed_floor_points": 1,
                      "removed_points_above_4cm": 1}
    np.testing.assert_array_equal(points, before)
    np.testing.assert_array_equal(mask, [True, False, True])
