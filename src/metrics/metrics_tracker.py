"""Per-robot SLAM metrics accumulation with ring buffers and ICP baseline.

Collects ms_per_frame, tracking_status, and drift metrics (ATE/RPE)
per robot in bounded deques. Provides a stats payload for WebSocket
transport and baseline snapshot for cross-session comparison.
"""

from collections import deque
import time


class MetricsTracker:
    """Accumulates per-robot SLAM metrics in ring buffers.

    Args:
        history_size: Maximum number of entries per metric ring buffer.
    """

    def __init__(self, history_size: int = 60) -> None:
        self._history_size = history_size
        self._per_robot: dict[str, dict] = {}
        self._frame_counts: dict[str, int] = {}
        self._baseline: dict | None = None

    def _ensure_robot(self, robot_id: str) -> dict:
        """Initialize robot entry if missing, return it."""
        if robot_id not in self._per_robot:
            self._per_robot[robot_id] = {
                "ms_per_frame": 0.0,
                "tracking_status": "ok",
                "drift_history": deque(maxlen=self._history_size),
                "ms_history": deque(maxlen=self._history_size),
            }
            self._frame_counts[robot_id] = 0
        return self._per_robot[robot_id]

    def record_frame(
        self,
        robot_id: str,
        slam_result_metrics: dict,
        tracking_status: str,
    ) -> None:
        """Record per-frame metrics from a SLAM result.

        Args:
            robot_id: Robot identifier.
            slam_result_metrics: Dict from SLAMResult.metrics
                (expects "processing_time_ms" key).
            tracking_status: Current tracking state string.
        """
        entry = self._ensure_robot(robot_id)
        ms = slam_result_metrics.get("processing_time_ms", 0.0)
        entry["ms_per_frame"] = ms
        entry["tracking_status"] = tracking_status
        entry["ms_history"].append(ms)
        self._frame_counts[robot_id] = self._frame_counts.get(robot_id, 0) + 1

    def record_drift(
        self,
        robot_id: str,
        ate_rmse: float,
        ate_mean: float,
        rpe_rmse: float,
        rpe_mean: float,
    ) -> None:
        """Append drift metrics to the robot's ring buffer.

        Args:
            robot_id: Robot identifier.
            ate_rmse: Absolute Trajectory Error RMSE.
            ate_mean: Absolute Trajectory Error mean.
            rpe_rmse: Relative Pose Error RMSE.
            rpe_mean: Relative Pose Error mean.
        """
        entry = self._ensure_robot(robot_id)
        entry["drift_history"].append({
            "ate_rmse": ate_rmse,
            "ate_mean": ate_mean,
            "rpe_rmse": rpe_rmse,
            "rpe_mean": rpe_mean,
            "timestamp": time.monotonic(),
        })

    def get_robot_metrics(self, robot_id: str) -> dict:
        """Return current metrics snapshot for a robot.

        Returns dict with keys: ate_rmse, ate_mean, rpe_rmse, rpe_mean,
        ms_per_frame, tracking_status. Drift values default to 0.0 if
        no drift has been recorded yet.
        """
        entry = self._ensure_robot(robot_id)
        drift = entry["drift_history"]
        if drift:
            latest = drift[-1]
            return {
                "ate_rmse": latest["ate_rmse"],
                "ate_mean": latest["ate_mean"],
                "rpe_rmse": latest["rpe_rmse"],
                "rpe_mean": latest["rpe_mean"],
                "ms_per_frame": entry["ms_per_frame"],
                "tracking_status": entry["tracking_status"],
            }
        return {
            "ate_rmse": 0.0,
            "ate_mean": 0.0,
            "rpe_rmse": 0.0,
            "rpe_mean": 0.0,
            "ms_per_frame": entry["ms_per_frame"],
            "tracking_status": entry["tracking_status"],
        }

    def get_histories(self) -> dict:
        """Return per-robot metric history arrays.

        Returns dict keyed by robot_id, each containing:
            ate_rmse, rpe_rmse, ms_per_frame, timestamps (all lists).
        """
        result: dict[str, dict] = {}
        for robot_id, entry in self._per_robot.items():
            drift = entry["drift_history"]
            result[robot_id] = {
                "ate_rmse": [d["ate_rmse"] for d in drift],
                "rpe_rmse": [d["rpe_rmse"] for d in drift],
                "ms_per_frame": list(entry["ms_history"]),
                "timestamps": [d["timestamp"] for d in drift],
            }
        return result

    def capture_baseline(self) -> None:
        """Snapshot current per-robot metrics as baseline.

        The baseline is None if no robots have recorded any metrics.
        """
        if not self._per_robot:
            self._baseline = None
            return
        baseline: dict[str, dict] = {}
        for robot_id in self._per_robot:
            baseline[robot_id] = self.get_robot_metrics(robot_id)
        self._baseline = baseline if baseline else None

    @property
    def baseline(self) -> dict | None:
        """The last captured baseline, or None."""
        return self._baseline

    def get_stats_payload(self) -> dict:
        """Build the slam_metrics portion of the stats WebSocket message.

        Returns dict with keys: slam_metrics, baseline, metric_history.
        """
        slam_metrics: dict[str, dict] = {}
        for robot_id in self._per_robot:
            slam_metrics[robot_id] = self.get_robot_metrics(robot_id)
        return {
            "slam_metrics": slam_metrics,
            "baseline": self._baseline,
            "metric_history": self.get_histories(),
        }

    def reset(self) -> None:
        """Clear all per-robot data and frame counts.

        Baseline is intentionally preserved across sessions for comparison.
        """
        self._per_robot.clear()
        self._frame_counts.clear()
