"""Ground-truth pose collection from SensorFrames.

Accumulates ground-truth poses and timestamps from sensor frames
for later comparison with SLAM estimates via drift metrics.
"""

import numpy as np

from src.bridge.sensor_types import SensorFrame


class GroundTruthCollector:
    """Collects ground-truth poses and timestamps from SensorFrames.

    Usage:
        collector = GroundTruthCollector()
        for frame in frames:
            collector.record(frame)
        # Later: compute_drift_metrics(slam_poses, collector.poses, collector.timestamps)
    """

    def __init__(self):
        self._poses: list[np.ndarray] = []
        self._timestamps: list[float] = []

    def record(self, frame: SensorFrame) -> None:
        """Record ground-truth pose and timestamp from a SensorFrame."""
        self._poses.append(frame.ground_truth_pose.copy())
        self._timestamps.append(frame.sim_time)

    @property
    def poses(self) -> list[np.ndarray]:
        """List of recorded (4, 4) ground-truth poses."""
        return list(self._poses)

    @property
    def timestamps(self) -> list[float]:
        """List of recorded timestamps in seconds."""
        return list(self._timestamps)

    def __len__(self) -> int:
        return len(self._poses)
