"""Bounded, hypothetical local route forecasts on the current observed map.

Forecasts rank proposals, never authorize execution or certify future sensing.
The guard and waypoint runner are isolated copies. Real motion is rechecked
with fresh estimates, including after a recovery. No simulator state is used.
"""
import copy
from dataclasses import dataclass
import math

import numpy as np

from src.control.motion_clearance import _approach
from src.locomotion.command_filter import filter_gait_command
from src.locomotion.gait_params import GaitParams


@dataclass
class RoutePreview:
    admissible: bool
    reason: str
    translation_m: float
    steps: int


class _Forecast:
    def __init__(self, guard, state):
        self.guard = copy.copy(guard)
        self.guard._poses = guard._poses.copy()
        self.state = dict(state)
        self.pose = np.array(state['pose'], copy=True)
        self.yaw = math.atan2(self.pose[1, 0], self.pose[0, 0])
        self.velocity = np.zeros(2)
        if self.guard._poses:
            then, xy, _ = self.guard._poses[0]
            if state['sim_time'] > then:
                self.velocity = (self.pose[:2, 3] - xy) / (state['sim_time'] - then)
        self.dt = min(.1, guard.config.motion_pose_max_gap_s / 2)
        self.active_yaw, self.restart = guard._active_yaw, guard._restart_remaining

    def check(self, linear, angular):
        self.state['pose'] = self.pose
        return self.guard.filter(linear, angular, **self.state)

    def advance(self, decision):
        vx, vy, omega, self.active_yaw, self.restart = filter_gait_command(
            *decision.linear, decision.angular, self.dt, self.active_yaw, self.restart, GaitParams())
        target = np.array([[math.cos(self.yaw), -math.sin(self.yaw)],
                           [math.sin(self.yaw), math.cos(self.yaw)]]) @ [vx, vy]
        self.velocity = _approach(self.velocity, target, self.guard.config.motion_braking_mps2 * self.dt)
        self.yaw += omega * self.dt
        self.pose = self.pose.copy()
        self.pose[:2, 3] += self.velocity * self.dt
        self.pose[:2, :2] = [[math.cos(self.yaw), -math.sin(self.yaw)],
                            [math.sin(self.yaw), math.cos(self.yaw)]]
        self.state['pose'] = self.pose
        self.state['sim_time'] += self.dt
        if self.state['observation_time'] is not None:
            self.state['observation_time'] += self.dt


def preview_route(guard, runner, state, *, horizon_s=4., progress_m=.15):
    """Require modeled navigation translation, including turns and stopping.

    Use the shared gait restart/yaw response and the guard's acceleration
    parameter for a nominal forecast. This is not a calibrated body simulator.
    Each hypothetical command checks both guard response envelopes and its
    complete stop tail. Observation time advances only in this frozen-map
    forecast; the initial check retains the real observation age.
    """
    forecast = _Forecast(guard, state)
    runner = copy.deepcopy(runner)
    translated = 0.
    anchor = forecast.pose[:2, 3].copy()
    for index in range(math.ceil(horizon_s / forecast.dt)):
        linear, angular = runner.get_velocity(forecast.pose)
        decision = forecast.check(linear, angular)
        if decision.scale == 0:
            return RoutePreview(False, decision.reason, translated, index + 1)
        if translated >= progress_m:
            return RoutePreview(True, 'predicted_translation', translated, index + 1)
        if runner.is_complete:
            return RoutePreview(translated >= progress_m, 'route_complete', translated, index + 1)
        forecast.advance(decision)
        if np.linalg.norm(decision.linear) > .01:
            translated = float(np.linalg.norm(forecast.pose[:2, 3] - anchor))
        else:
            anchor = forecast.pose[:2, 3].copy()
            translated = 0.
    return RoutePreview(False, 'preview_horizon', translated, index + 1)


def preview_recovery_endpoint(guard, command, state):
    """Forecast a directed primitive and its standing interval, or reject it.

    Return a detached guard/state for route ranking only. Observed progress,
    live clearance, and the existing recovery deadline remain authoritative.
    """
    forecast = _Forecast(guard, state)
    config = guard.config
    origin, yaw = forecast.pose[:2, 3].copy(), forecast.yaw
    reached = False
    idle_time = 0.
    duration = config.recovery_motion_timeout_s + max(config.blocked_retry_s, config.motion_settling_s)
    for index in range(math.ceil(duration / forecast.dt) + 1):
        delta = forecast.pose[:2, 3] - origin
        angle = math.atan2(math.sin(forecast.yaw-yaw), math.cos(forecast.yaw-yaw))
        distance = float(delta @ np.array([math.cos(yaw), math.sin(yaw)]) * np.sign(command[0]))
        reached |= (distance >= config.recovery_distance_m if abs(command[0]) > .01
                    else angle * np.sign(command[2]) >= config.recovery_angle_rad)
        if not reached and index * forecast.dt >= config.recovery_motion_timeout_s:
            return None, 'predicted_no_progress'
        linear, angular = (np.zeros(2), 0.) if reached else (np.array(command[:2]), command[2])
        decision = forecast.check(linear, angular)
        if decision.scale == 0:
            return None, decision.reason
        forecast.advance(decision)
        if reached:
            idle_time += forecast.dt
            if idle_time >= max(config.blocked_retry_s, config.motion_settling_s):
                return (forecast.guard, forecast.state), 'predicted_endpoint'
    return None, 'preview_horizon'
