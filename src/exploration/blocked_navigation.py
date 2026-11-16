"""Finite per-robot retry policy; all movement remains an execution-guard proposal."""
import math

import numpy as np


class BlockedNavigation:
    def __init__(self, config):
        self.config = config
        for name in ("blocked_timeout_s", "blocked_retry_s", "recovery_motion_timeout_s",
                     "recovery_distance_m", "recovery_angle_rad", "navigation_resume_distance_m"):
            if not math.isfinite(getattr(config, name)) or getattr(config, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("blocked_max_replans", "blocked_max_recoveries", "planning_candidate_limit"):
            value = getattr(config, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.state = "navigating"
        self.reason = "bootstrap"
        self.since = None
        self.ready_at = 0.
        self.replans = 0
        self.recoveries = 0
        self.execution_rejections = 0
        self.recovery_outcome = None
        self.command = None
        self.motion_start = None
        self.motion_pose = None
        self.navigation_anchor = None
        self.last_recovery_replans = 0

    def snapshot(self):
        return dict(state=self.state, reason=self.reason, blocked_since_s=self.since,
                    replan_attempts=self.replans, recovery_attempts=self.recoveries,
                    execution_rejections=self.execution_rejections,
                    recovery_outcome=self.recovery_outcome)

    def block(self, reason, now):
        if self.state == "failed":
            return
        if self.since is None:
            self.since = now
        self.state, self.reason = "blocked", reason
        self.ready_at = now + max(self.config.blocked_retry_s, self.config.motion_settling_s)
        self.command = None
        self.navigation_anchor = None

    def fail(self, reason):
        self.state, self.reason = "failed", reason
        self.command = None

    def installed(self, pose):
        self.state, self.reason = "navigating", "route_installed"
        self.navigation_anchor = pose[:2, 3].copy()

    def observe(self, pose, now):
        if self.state == "failed":
            return
        # Only translation on a successfully installed navigation route resets
        # the budget. Recovery travel, a new goal, or turning cannot do so.
        if (self.state == "navigating" and self.since is not None
                and self.navigation_anchor is not None
                and np.linalg.norm(pose[:2, 3] - self.navigation_anchor) >= self.config.navigation_resume_distance_m):
            self.since = None
            self.replans = self.recoveries = self.last_recovery_replans = 0
            self.reason = "navigation_progress"
        if self.since is not None and now - self.since >= self.config.blocked_timeout_s:
            if self.state == "recovering":
                self.recovery_outcome = "timeout"
            self.fail("blocked_timeout")
        if self.state == "recovering":
            distance = np.linalg.norm(pose[:2, 3] - self.motion_pose[:2, 3])
            yaw = math.atan2(pose[1, 0], pose[0, 0])
            start_yaw = math.atan2(self.motion_pose[1, 0], self.motion_pose[0, 0])
            angle = abs(math.atan2(math.sin(yaw-start_yaw), math.cos(yaw-start_yaw)))
            translating = abs(self.command[0]) > .01
            progress = (distance >= self.config.recovery_distance_m if translating
                        else angle >= self.config.recovery_angle_rad)
            if progress or now - self.motion_start >= self.config.recovery_motion_timeout_s:
                self.recovery_outcome = "progress" if progress else "no_progress"
                self.block("recovery_" + self.recovery_outcome, now)

    def next_action(self, now):
        if self.state != "blocked" or now + 1e-9 < self.ready_at:
            return None
        if self.replans < self.config.blocked_max_replans and self.replans - self.last_recovery_replans < 2:
            self.replans += 1
            self.state, self.reason = "replanning", "retry_route"
            return "replan"
        if self.recoveries >= self.config.blocked_max_recoveries:
            self.fail("retry_budget_exhausted")
            return None
        self.recoveries += 1
        self.last_recovery_replans = self.replans
        return "recover"

    def start_recovery(self, command, pose, now):
        self.command = command
        self.motion_pose = pose.copy()
        self.motion_start = now
        self.state, self.reason = "recovering", "checked_motion"
