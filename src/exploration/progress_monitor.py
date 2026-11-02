"""Command-aware mobility checks using estimated poses and simulation time."""

import math

import numpy as np


class ProgressMonitor:
    """Require net planar progress within a time window while commanding motion.

    Translation commands require translation, including curved walking. Pure
    rotation commands require yaw progress. Idle commands reset the window.
    Vertical gait motion and accumulated back-and-forth jitter do not count.
    """

    def __init__(self, timeout_s: float, distance_m: float, angle_rad: float):
        for value in (timeout_s, distance_m, angle_rad):
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Progress thresholds must be finite and positive")
        self.timeout_s = timeout_s
        self.distance_m = distance_m
        self.angle_rad = angle_rad
        self.reset()

    def reset(self) -> None:
        self._anchor: np.ndarray | None = None
        self._since = 0.0
        self._mode = "idle"
        self.no_progress_steps = 0

    def update(self, pose: np.ndarray, sim_time: float,
               linear: np.ndarray, angular: float) -> bool:
        """Check the motion commanded during the interval ending at this pose."""
        mode = ("translate" if np.linalg.norm(linear) > 1e-6 else
                "rotate" if abs(angular) > 1e-6 else "idle")
        yaw = math.atan2(pose[1, 0], pose[0, 0])
        position = np.array([pose[0, 3], pose[1, 3], yaw])
        reset = self._anchor is None or mode != self._mode or mode == "idle"
        if not reset:
            if mode == "translate":
                progress = np.linalg.norm(position[:2] - self._anchor[:2])
                reset = progress >= self.distance_m
            else:
                angle = position[2] - self._anchor[2]
                progress = abs(math.atan2(math.sin(angle), math.cos(angle)))
                reset = progress >= self.angle_rad
        if reset:
            self._anchor = position
            self._since = sim_time
            self._mode = mode
            self.no_progress_steps = 0
            return False
        self.no_progress_steps += 1
        return sim_time - self._since >= self.timeout_s - 1e-9
