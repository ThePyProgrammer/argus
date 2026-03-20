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
        """Pure pursuit with lookahead on smoothed path.

        Instead of driving at the next waypoint, finds the point 0.5m
        ahead on the path and steers toward that. Produces smooth curves.

        Args:
            current_pose: (4, 4) homogeneous transform of the robot.
            depth: Optional depth image (currently unused -- camera faces sideways).

        Returns:
            Tuple of (linear_vel as np.ndarray([vx, vy]), angular_vel as float).
        """
        if self.is_complete:
            return np.zeros(2), 0.0

        position = current_pose[:3, 3]
        lookahead_dist = 0.5  # meters ahead on path

        # Find closest waypoint on path
        min_dist = float('inf')
        closest_idx = self._current_index
        for i in range(self._current_index, len(self._waypoints)):
            d = np.linalg.norm(self._waypoints[i][:2] - position[:2])
            if d < min_dist:
                min_dist = d
                closest_idx = i

        # Advance current index to closest (don't go backward)
        self._current_index = max(self._current_index, closest_idx)

        # Find lookahead point: walk along path from closest until 0.5m ahead
        target = self._waypoints[self._current_index]
        cumulative = 0.0
        for i in range(self._current_index, len(self._waypoints) - 1):
            seg = np.linalg.norm(self._waypoints[i + 1][:2] - self._waypoints[i][:2])
            if cumulative + seg >= lookahead_dist:
                # Interpolate within this segment
                remaining = lookahead_dist - cumulative
                t = remaining / max(seg, 1e-6)
                target = self._waypoints[i] + t * (self._waypoints[i + 1] - self._waypoints[i])
                break
            cumulative += seg
            target = self._waypoints[i + 1]

        # Check if we've reached the final waypoint
        final_dist = np.linalg.norm(self._waypoints[-1][:2] - position[:2])
        if final_dist < self._arrival_threshold:
            self._current_index = len(self._waypoints)
            return np.zeros(2), 0.0

        # Compute heading to lookahead target
        delta = target[:2] - position[:2]
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
        self, depth: np.ndarray, danger_dist: float = 1.5
    ) -> tuple[np.ndarray, float] | None:
        """Check depth image for close obstacles and return avoidance command.

        Uses three zones: wide scan for early detection, center for imminent
        collision. Steers away from the closer side and slows/stops based on
        proximity.

        Args:
            depth: (H, W) float32 depth in meters. 0 = invalid.
            danger_dist: Distance threshold for obstacle detection in meters.

        Returns:
            (linear_vel, angular_vel) if avoidance needed, else None.
        """
        h, w = depth.shape

        # Wide scan: full width, middle 80% of height
        y_lo, y_hi = int(h * 0.1), int(h * 0.9)
        scan = depth[y_lo:y_hi, :]

        valid = scan[(scan > 0.05) & (scan < danger_dist)]
        if len(valid) == 0:
            return None  # No close obstacles

        min_dist = float(np.min(valid))

        # Split into left/right thirds for steering direction
        third = scan.shape[1] // 3
        left = scan[:, :third]
        center = scan[:, third:2*third]
        right = scan[:, 2*third:]

        def avg_close(region):
            close = region[(region > 0.05) & (region < danger_dist)]
            return float(np.mean(close)) if len(close) > 0 else danger_dist

        left_d = avg_close(left)
        center_d = avg_close(center)
        right_d = avg_close(right)

        # Steer away from the closer side
        if left_d < right_d:
            turn = -self._angular_speed * 1.5  # Turn right hard
        else:
            turn = self._angular_speed * 1.5   # Turn left hard

        # Speed: full stop if very close, slow if medium, normal if far
        if min_dist < 0.3:
            # Emergency: reverse
            linear = np.array([-self._linear_speed * 0.3, 0.0])
        elif min_dist < 0.6:
            # Stop forward, only turn
            linear = np.array([0.0, 0.0])
        else:
            # Slow down proportionally
            speed_factor = (min_dist - 0.6) / (danger_dist - 0.6)
            linear = np.array([self._linear_speed * speed_factor * 0.5, 0.0])

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
