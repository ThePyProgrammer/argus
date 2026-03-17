"""ATE and RPE drift metrics computation using the evo library.

Compares SLAM-estimated poses against ground-truth poses to quantify
trajectory drift. Returns Absolute Trajectory Error (ATE) and Relative
Pose Error (RPE) statistics.
"""

import numpy as np
from evo.core import metrics, sync
from evo.core.trajectory import PoseTrajectory3D


def compute_drift_metrics(
    slam_poses: list[np.ndarray],
    gt_poses: list[np.ndarray],
    timestamps: list[float],
) -> dict:
    """Compute ATE and RPE between SLAM and ground-truth trajectories.

    Args:
        slam_poses: List of (4, 4) homogeneous transforms from SLAM.
        gt_poses: List of (4, 4) homogeneous transforms from ground truth.
        timestamps: List of float timestamps (seconds), same length as poses.

    Returns:
        Dict with keys: ate_rmse, ate_mean, rpe_rmse, rpe_mean.
    """
    # Truncate to shortest common length
    min_len = min(len(slam_poses), len(gt_poses), len(timestamps))
    if min_len < 2:
        raise ValueError(f"Need at least 2 poses, got {min_len}")

    slam_poses = slam_poses[:min_len]
    gt_poses = gt_poses[:min_len]
    ts = np.array(timestamps[:min_len])

    slam_traj = PoseTrajectory3D(
        poses_se3=slam_poses,
        timestamps=ts,
    )
    gt_traj = PoseTrajectory3D(
        poses_se3=gt_poses,
        timestamps=ts,
    )

    # Sync trajectories by timestamp
    gt_synced, slam_synced = sync.associate_trajectories(gt_traj, slam_traj)

    # ATE (Absolute Trajectory Error)
    ate_metric = metrics.APE(metrics.PoseRelation.translation_part)
    ate_metric.process_data((gt_synced, slam_synced))

    # RPE (Relative Pose Error)
    rpe_metric = metrics.RPE(metrics.PoseRelation.translation_part)
    rpe_metric.process_data((gt_synced, slam_synced))

    return {
        "ate_rmse": ate_metric.get_statistic(metrics.StatisticsType.rmse),
        "ate_mean": ate_metric.get_statistic(metrics.StatisticsType.mean),
        "rpe_rmse": rpe_metric.get_statistic(metrics.StatisticsType.rmse),
        "rpe_mean": rpe_metric.get_statistic(metrics.StatisticsType.mean),
    }
