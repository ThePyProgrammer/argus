"""Tests for drift metrics computation (SLAM-04).

Unit tests using synthetic pose trajectories -- no SimWorld or SLAM required.
Currently stubbed as pending implementation.
"""

import pytest


@pytest.mark.unit
@pytest.mark.skip(reason="pending implementation")
def test_ate_rpe(sample_poses):
    """SLAM-04: ATE and RPE computed from SLAM vs ground-truth pose trajectories.

    Verifies:
    - Drift metrics function accepts two lists of (4, 4) poses and timestamps
    - Returns dict with ate_rmse, ate_mean, rpe_rmse, rpe_mean keys
    - All returned values are non-negative floats
    - Identical trajectories produce zero (or near-zero) error
    - Different trajectories produce non-zero error
    """
    assert False, "pending"
