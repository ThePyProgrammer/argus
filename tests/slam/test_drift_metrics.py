"""Tests for drift metrics computation (SLAM-04).

Unit tests using synthetic pose trajectories -- no SimWorld or SLAM required.
"""

import numpy as np
import pytest


@pytest.mark.unit
def test_ate_rpe(sample_poses):
    """SLAM-04: Identical SLAM and GT trajectories produce near-zero ATE/RPE.

    Verifies:
    - Drift metrics function accepts two lists of (4, 4) poses and timestamps
    - Returns dict with ate_rmse, ate_mean, rpe_rmse, rpe_mean keys
    - Identical trajectories produce zero (or near-zero) error
    """
    from src.metrics.drift_metrics import compute_drift_metrics

    timestamps = [float(i) for i in range(len(sample_poses))]
    result = compute_drift_metrics(
        slam_poses=sample_poses,
        gt_poses=sample_poses,
        timestamps=timestamps,
    )

    assert "ate_rmse" in result
    assert "ate_mean" in result
    assert "rpe_rmse" in result
    assert "rpe_mean" in result
    assert result["ate_rmse"] < 1e-6, f"Expected near-zero ATE RMSE, got {result['ate_rmse']}"


@pytest.mark.unit
def test_ate_rpe_with_offset(sample_poses):
    """SLAM-04: SLAM poses offset by 1m from GT produce ATE mean ~ 1.0.

    Verifies:
    - Different trajectories produce non-zero error
    - A known 1m offset yields ATE mean approximately 1.0
    """
    from src.metrics.drift_metrics import compute_drift_metrics

    # Create offset SLAM poses: shift all translations by [1, 0, 0]
    slam_poses = []
    for pose in sample_poses:
        offset_pose = pose.copy()
        offset_pose[0, 3] += 1.0  # shift x by 1 meter
        slam_poses.append(offset_pose)

    timestamps = [float(i) for i in range(len(sample_poses))]
    result = compute_drift_metrics(
        slam_poses=slam_poses,
        gt_poses=sample_poses,
        timestamps=timestamps,
    )

    assert result["ate_mean"] == pytest.approx(1.0, abs=0.1), (
        f"Expected ATE mean ~1.0 for 1m offset, got {result['ate_mean']}"
    )
