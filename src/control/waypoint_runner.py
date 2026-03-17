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

    def get_velocity(self, current_pose: np.ndarray) -> tuple[np.ndarray, float]:
        """Compute velocity command to drive toward the current waypoint.

        Args:
            current_pose: (4, 4) homogeneous transform of the robot.

        Returns:
            Tuple of (linear_vel as np.ndarray([vx, vy]), angular_vel as float).
        """
        if self.is_complete:
            return np.zeros(2), 0.0

        # Extract current position and heading from pose
        position = current_pose[:3, 3]
        target = self._waypoints[self._current_index]

        # Direction to target in world frame (XY plane)
        delta = target[:2] - position[:2]
        distance = np.linalg.norm(delta)

        # Check arrival
        if distance < self._arrival_threshold:
            logger.info(
                "Reached waypoint %d/%d (dist=%.3f m)",
                self._current_index + 1,
                len(self._waypoints),
                distance,
            )
            self._current_index += 1
            if self.is_complete:
                logger.info("All waypoints reached")
                return np.zeros(2), 0.0
            # Recompute for the new waypoint
            target = self._waypoints[self._current_index]
            delta = target[:2] - position[:2]
            distance = np.linalg.norm(delta)

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

        # Drive forward when roughly facing the target
        if abs(angle_error) < math.pi / 4:
            linear_vel = np.array([self._linear_speed, 0.0])
        else:
            # Turn in place when far off heading
            linear_vel = np.zeros(2)

        return linear_vel, float(angular_vel)

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
