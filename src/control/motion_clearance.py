"""Observed-map velocity gate with a modeled stopping tail.

Inputs are estimated body poses, observed occupancy, and fixed calibration.
This is a development motion model, not a bound on arbitrary localization or
actuator errors. Every decision reports why a command was accepted or stopped.
"""
from collections import deque
from dataclasses import dataclass, field
import math

import numpy as np
from scipy.spatial import cKDTree

from src.exploration.occupancy_grid import CELL_OCCUPIED, CELL_UNKNOWN
from src.locomotion.command_filter import filter_gait_command
from src.locomotion.gait_params import GaitParams


@dataclass
class ClearanceDecision:
    linear: np.ndarray
    angular: float
    reason: str
    scale: float = 0.
    clearance_m: float | None = None
    stopping_clear: bool = False
    path: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))


def _approach(value, target, maximum_change):
    delta = target - value
    length = float(np.linalg.norm(delta))
    return target.copy() if length <= maximum_change else value + delta * maximum_change / length


def project_motion(position, yaw, velocity, yaw_rate, linear, angular, *,
                   active_yaw, config, control_dt, immediate_response=False, restart_wait=0., settled=False):
    """Predict commanded motion, delayed response, and a coast/braking tail.

    Active gait yaw follows the same 8 rad/s/s slew as the default Go2 gait.
    First motion initializes at requested yaw. Interrupted motion includes the
    gait's standing interval before restart, using the same command filter.
    Explicit idle leaves measured physical velocity to coast and brake.
    The circular all-joint envelope handles rotation at every intermediate angle.
    """
    params = GaitParams()
    idle = np.linalg.norm(linear) <= .01 and abs(angular) <= .01
    hold = 0. if idle else config.motion_horizon_s
    speed = max(float(np.linalg.norm(velocity)), float(np.linalg.norm(linear)))
    rate = params.command_yaw_acceleration
    settling = 0. if idle and settled else config.motion_settling_s
    duration = hold + max(settling, config.motion_reaction_s + max(
        speed / config.motion_braking_mps2, max(abs(yaw_rate), abs(angular)) / rate))
    dt = min(.02, max(.001, control_dt))
    count = max(1, math.ceil(duration / dt))
    dt = max(duration, dt) / count
    xy, vel = np.array(position, dtype=float), np.array(velocity, dtype=float)
    filtered = active_yaw
    points, times = [xy.copy()], [0.]
    for i in range(count):
        t = i * dt
        if t < hold:
            vx, vy, target_yaw, filtered, restart_wait = filter_gait_command(
                *linear, angular, dt, filtered, restart_wait, params)
            target = np.array([[math.cos(yaw), -math.sin(yaw)],
                               [math.sin(yaw), math.cos(yaw)]]) @ [vx, vy]
            # Pose differences capture initial lateral drift and residual motion.
            if immediate_response:
                vel = target.copy()
            elif t < config.motion_reaction_s:
                target = vel
            vel = _approach(vel, target, config.motion_braking_mps2 * dt)
            yaw_rate += float(np.clip(target_yaw - yaw_rate, -rate * dt, rate * dt))
        elif t >= hold + config.motion_reaction_s:
            vel = _approach(vel, np.zeros(2), config.motion_braking_mps2 * dt)
            yaw_rate += float(np.clip(-yaw_rate, -rate * dt, rate * dt))
        yaw += yaw_rate * dt
        xy += vel * dt
        points.append(xy.copy())
        times.append((i + 1) * dt)
    return np.asarray(points), np.asarray(times)


class MotionClearanceGuard:
    def __init__(self, config):
        self.config = config
        for name in ("motion_horizon_s", "motion_reaction_s", "motion_braking_mps2",
                     "motion_settling_s", "motion_drift_mps", "motion_observation_max_age_s", "motion_pose_max_gap_s"):
            value = getattr(config, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        self._poses = deque()
        self._active_yaw = None
        self._restart_remaining = 0.
        self._idle_elapsed = 0.
        self.last = ClearanceDecision(np.zeros(2), 0., "not_observed")

    def preview(self, linear, angular, **state):
        """Evaluate a candidate without consuming observation or gait history.

        The selected proposal must still pass filter on the actual guard. This
        avoids treating multiple alternatives at one timestamp as stale poses.
        """
        import copy
        candidate = copy.copy(self)
        candidate._poses = self._poses.copy()
        return candidate.filter(linear, angular, **state)

    def _remember_command(self, linear, angular, dt):
        _, _, _, self._active_yaw, self._restart_remaining = filter_gait_command(
            *linear, angular, float(np.clip(dt, .001, 1.)), self._active_yaw,
            self._restart_remaining, GaitParams())
        self._idle_elapsed = self._idle_elapsed + dt if self._active_yaw is None else 0.

    def filter(self, linear, angular, *, pose, sim_time, observation_time, grid,
               radius, calibration_valid, tracking_ok):
        linear = np.asarray(linear, dtype=float)
        pose = np.asarray(pose, dtype=float)
        control_dt = .01
        def stop(reason):
            self._remember_command(np.zeros(2), 0., control_dt)
            if reason in {"invalid_state", "stale_pose", "missing_geometry_calibration",
                          "tracking_lost", "stale_observation", "motion_model_exceeded",
                          "initial_velocity_observation"}:
                # Invalid or repeated timestamps cannot establish a physically
                # completed settling interval. Require fresh idle history again.
                self._idle_elapsed = 0.
            self.last = ClearanceDecision(np.zeros(2), 0., reason)
            return self.last
        if (pose.shape != (4, 4) or linear.shape != (2,) or not np.isfinite(pose).all()
                or not np.isfinite(linear).all() or not math.isfinite(angular)
                or not math.isfinite(sim_time) or not math.isfinite(radius) or radius <= 0):
            return stop("invalid_state")
        xy = pose[:2, 3].copy()
        yaw = math.atan2(pose[1, 0], pose[0, 0])
        previous = self._poses[-1] if self._poses else None
        gap = sim_time - previous[0] if previous else .01
        if gap > 0:
            control_dt = gap
        if previous and gap <= 0:
            return stop("stale_pose")
        self._poses.append((sim_time, xy, yaw))
        while len(self._poses) > 2 and sim_time - self._poses[0][0] > .10:
            self._poses.popleft()
        if gap > self.config.motion_pose_max_gap_s:
            self._poses.clear()
            self._poses.append((sim_time, xy, yaw))
            return stop("stale_pose")
        if not calibration_valid:
            return stop("missing_geometry_calibration")
        if not tracking_ok:
            return stop("tracking_lost")
        if abs(linear[1]) > .001:
            return stop("unsupported_lateral_command")
        if observation_time is None or not 0 <= sim_time - observation_time <= self.config.motion_observation_max_age_s:
            return stop("stale_observation")
        if previous is None:
            return stop("initial_velocity_observation")
        time0, xy0, yaw0 = self._poses[0]
        dt = sim_time - time0
        velocity = (xy - xy0) / dt
        yaw_rate = math.atan2(math.sin(yaw - yaw0), math.cos(yaw - yaw0)) / dt
        if np.linalg.norm(velocity) > 2. or abs(yaw_rate) > 5.:
            return stop("motion_model_exceeded")
        settled = (self._idle_elapsed >= self.config.motion_settling_s
                   and np.linalg.norm(velocity) < .01 and abs(yaw_rate) < .1)
        occupied = np.argwhere(grid.grid == CELL_OCCUPIED)
        centers = grid.origin + (occupied[:, ::-1] + .5) * grid.resolution
        tree = cKDTree(centers) if len(centers) else None

        def check(points, times):
            minimum = float("inf")
            for index, (a, b) in enumerate(zip(points[:-1], points[1:])):
                delta = b - a
                length = float(np.linalg.norm(delta))
                # Between-sample allowance bounds within-step travel; drift grows
                # with prediction time. Neither is a localization-error guarantee.
                allowance = radius + self.config.motion_drift_mps * times[index + 1] + length
                if tree is not None:
                    ids = tree.query_ball_point((a + b) / 2, length / 2 + allowance)
                    if ids:
                        obstacles = centers[ids]
                        f = np.zeros(len(ids)) if length < 1e-12 else np.clip((obstacles-a) @ delta / length**2, 0, 1)
                        clearance = float(np.min(np.linalg.norm(obstacles-(a+f[:, None]*delta), axis=1))) - allowance
                        minimum = min(minimum, clearance)
                        if clearance <= 0:
                            return False, "obstacle_clearance", minimum
                # Unknown center travel is disallowed, including thin crossed
                # cells. The footprint itself is checked against known obstacles;
                # unseen space outside the center route remains an explicit limit.
                crossings = [0., 1.]
                ga, gb = (a-grid.origin)/grid.resolution, (b-grid.origin)/grid.resolution
                for axis in (0, 1):
                    d = gb[axis] - ga[axis]
                    if abs(d) > 1e-12:
                        lo, hi = sorted((ga[axis], gb[axis]))
                        crossings.extend((k-ga[axis])/d for k in range(math.ceil(lo), math.floor(hi)+1))
                crossings = np.unique(crossings)
                for f in np.r_[crossings, (crossings[:-1]+crossings[1:])/2]:
                    point = ga + f*(gb-ga)
                    for col in {math.floor(point[0]-1e-9), math.floor(point[0]+1e-9)}:
                        for row in {math.floor(point[1]-1e-9), math.floor(point[1]+1e-9)}:
                            if not (0 <= row < grid.height and 0 <= col < grid.width):
                                return False, "outside_observed_grid", None
                            if grid.grid[row, col] == CELL_UNKNOWN:
                                return False, "unknown_center_route", None
            return True, "clear", None if math.isinf(minimum) else minimum

        def project(v, omega, immediate=False):
            return project_motion(xy, yaw, velocity, yaw_rate, v, omega,
                                  active_yaw=self._active_yaw, config=self.config, control_dt=gap,
                                  immediate_response=immediate, restart_wait=self._restart_remaining,
                                  settled=settled)
        stopped, stop_times = project(np.zeros(2), 0.)
        stopping_clear, stop_reason, stop_clearance = check(stopped, stop_times)
        if not stopping_clear:
            decision = stop("stopping_" + stop_reason)
            decision.path, decision.clearance_m = stopped, stop_clearance
            return decision
        reason = "clear"
        for scale in (1., .5, .25):
            v, omega = linear * scale, angular * scale
            path, times = project(v, omega)
            clear, reason, clearance = check(path, times)
            if clear:
                # Also check immediate translation response: gradual acceleration
                # alone could underestimate how far a newly commanded robot moves.
                path, times = project(v, omega, immediate=True)
                clear, reason, clearance = check(path, times)
            if clear:
                self._remember_command(v, omega, gap)
                self.last = ClearanceDecision(v, omega, "clear" if scale == 1 else "slowed", scale,
                                              clearance, True, path)
                return self.last
        decision = stop(reason)
        decision.path, decision.clearance_m, decision.stopping_clear = stopped, stop_clearance, True
        return decision
