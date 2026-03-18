"""Scripted waypoint follower for SimWorld robot navigation.

Drives the robot through a sequence of 3D waypoints using proportional
control, producing velocity commands compatible with
SimWorldGymBridge.set_velocity().
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


class WaypointRunner:
    """Navigate a robot through a list of 3D waypoints.

    The runner computes velocity commands to drive toward the current
    waypoint. When the robot is within ``arrival_threshold`` of the
    waypoint, it advances to the next one.

    Usage::

        waypoints = [
            np.array([5.0, 0.0, 0.0]),
            np.array([5.0, 5.0, 0.0]),
            np.array([0.0, 5.0, 0.0]),
        ]
        runner = WaypointRunner(waypoints, linear_speed=0.5)

        while not runner.is_complete:
            linear, angular = runner.get_velocity(current_pose)
            bridge.set_velocity(linear, angular)
            frame = bridge.step()
            current_pose = frame.ground_truth_pose

    Note:
        Because SimWorld uses a Discrete(6) action space, the bridge
        maps these continuous velocities to the nearest discrete action.
        Navigation will be coarse (grid-like movement with 90-degree turns).
    """

    def __init__(
        self,
        waypoints: list[np.ndarray],
        linear_speed: float = 0.5,
        angular_speed: float = 1.0,
        arrival_threshold: float = 0.5,
    ) -> None:
        """Initialize the waypoint runner.

        Args:
            waypoints: List of (3,) xyz position arrays in meters.
            linear_speed: Speed for linear movement.
            angular_speed: Speed for angular rotation.
            arrival_threshold: Distance (meters) at which a waypoint is
                considered reached.
        """
        if not waypoints:
            raise ValueError("waypoints list must not be empty")

        self._waypoints = [np.asarray(w, dtype=np.float64) for w in waypoints]
        self._linear_speed = linear_speed
        self._angular_speed = angular_speed
        self._arrival_threshold = arrival_threshold
        self._current_index = 0

    def get_velocity(
        self,
        current_pose: np.ndarray,
        depth: np.ndarray | None = None,
    ) -> tuple[np.ndarray, float]:
        """Compute velocity command to drive toward the current waypoint.

        When depth is provided, performs reactive obstacle avoidance:
        if the center strip of the depth image shows an obstacle within
        0.4m, the robot stops forward motion and steers away from the
        closer side.

        Args:
            current_pose: (4, 4) homogeneous transform of the robot.
            depth: Optional (H, W) float32 depth image in meters. 0 = invalid.

        Returns:
            Tuple of (linear_vel as np.ndarray([vx, vy]), angular_vel as float).
        """
        if self.is_complete:
            return np.zeros(2), 0.0

        # Reactive depth avoidance — check center strip for close obstacles
        if depth is not None:
            avoidance = self._check_depth_avoidance(depth)
            if avoidance is not None:
                return avoidance

        # Extract current position and heading from pose
        position = current_pose[:3, 3]
        target = self._waypoints[self._current_index]

        # Direction to target in world frame (XY plane)
        delta = target[:2] - position[:2]
        distance = np.linalg.norm(delta)

        # Check arrival -- only advance to next waypoint if close enough,
        # but don't skip the LAST waypoint (always drive toward it)
        if distance < self._arrival_threshold and self._current_index < len(self._waypoints) - 1:
            logger.info(
                "Reached waypoint %d/%d (dist=%.3f m)",
                self._current_index + 1,
                len(self._waypoints),
                distance,
            )
            self._current_index += 1
            # Recompute for the new waypoint
            target = self._waypoints[self._current_index]
            delta = target[:2] - position[:2]
            distance = np.linalg.norm(delta)

        # Only mark complete when very close to the final waypoint
        if self._current_index == len(self._waypoints) - 1 and distance < 0.1:
            logger.info("Reached final waypoint (dist=%.3f m)", distance)
            self._current_index = len(self._waypoints)
            return np.zeros(2), 0.0

        # Compute desired heading angle toward waypoint
        desired_yaw = math.atan2(delta[1], delta[0])

        # Extract current heading from rotation matrix (yaw from forward vector)
        forward = current_pose[:2, 0]  # first column of rotation = local X axis
        current_yaw = math.atan2(forward[1], forward[0])

        # Angular error (wrapped to [-pi, pi])
        angle_error = desired_yaw - current_yaw
        angle_error = (angle_error + math.pi) % (2 * math.pi) - math.pi

        # Proportional control
        angular_vel = np.clip(angle_error * 2.0, -self._angular_speed, self._angular_speed)

        # Always drive forward while turning -- quadrupeds can walk and
        # turn simultaneously. Scale down speed when far off heading.
        heading_factor = max(0.3, 1.0 - abs(angle_error) / math.pi)
        linear_vel = np.array([self._linear_speed * heading_factor, 0.0])

        return linear_vel, float(angular_vel)

    def _check_depth_avoidance(
        self, depth: np.ndarray, danger_dist: float = 0.4
    ) -> tuple[np.ndarray, float] | None:
        """Check depth image for close obstacles and return avoidance command.

        Splits the center band of the depth image into left and right halves.
        If either half has obstacles within danger_dist, returns a velocity
        command that stops forward motion and steers away from the obstacle.

        Args:
            depth: (H, W) float32 depth in meters. 0 = invalid.
            danger_dist: Distance threshold in meters.

        Returns:
            (linear_vel, angular_vel) if avoidance needed, else None.
        """
        h, w = depth.shape
        # Check center vertical band (middle 60% of image, middle 80% of height)
        y_lo, y_hi = int(h * 0.1), int(h * 0.9)
        x_lo, x_hi = int(w * 0.2), int(w * 0.8)
        center = depth[y_lo:y_hi, x_lo:x_hi]

        valid = center[(center > 0.05) & (center < danger_dist)]
        if len(valid) == 0:
            return None  # No close obstacles

        # Obstacle detected — steer away from the closer side
        mid_x = center.shape[1] // 2
        left_strip = center[:, :mid_x]
        right_strip = center[:, mid_x:]

        left_close = left_strip[(left_strip > 0.05) & (left_strip < danger_dist)]
        right_close = right_strip[(right_strip > 0.05) & (right_strip < danger_dist)]

        left_danger = np.mean(left_close) if len(left_close) > 0 else danger_dist
        right_danger = np.mean(right_close) if len(right_close) > 0 else danger_dist

        # Steer away from the closer side (positive = turn left)
        if left_danger < right_danger:
            turn = -self._angular_speed  # Turn right (away from left obstacle)
        else:
            turn = self._angular_speed   # Turn left (away from right obstacle)

        # Slow down or stop — the closer the obstacle, the slower we go
        min_dist = float(np.min(valid))
        speed_factor = max(0.0, (min_dist - 0.15) / (danger_dist - 0.15))
        linear = np.array([self._linear_speed * speed_factor * 0.3, 0.0])

        return linear, float(turn)

    @property
    def is_complete(self) -> bool:
        """True if all waypoints have been visited."""
        return self._current_index >= len(self._waypoints)

    @property
    def current_waypoint_index(self) -> int:
        """Index of the current target waypoint."""
        return self._current_index

    @property
    def current_waypoint(self) -> np.ndarray | None:
        """Current target waypoint, or None if complete."""
        if self.is_complete:
            return None
        return self._waypoints[self._current_index]

    @property
    def waypoint_count(self) -> int:
        """Total number of waypoints."""
        return len(self._waypoints)
