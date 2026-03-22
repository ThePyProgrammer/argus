"""Random exploration controller.

Produces velocity commands that change direction periodically, biased
toward forward motion to encourage exploration.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class RandomWalkController:
    """Random walk that periodically changes direction.

    Generates forward-biased random velocity commands, switching direction
    at regular intervals based on simulation time.

    Usage::

        rw = RandomWalkController(seed=42)

        for step in range(1000):
            linear, angular = rw.get_velocity(sim_time=step * 0.1)
            bridge.set_velocity(linear, angular)
            frame = bridge.step()
    """

    def __init__(
        self,
        linear_speed: float = 0.3,
        angular_speed: float = 0.8,
        direction_change_interval: float = 3.0,
        seed: int | None = None,
    ) -> None:
        """Initialize the random walk controller.

        Args:
            linear_speed: Maximum linear speed magnitude.
            angular_speed: Maximum angular speed magnitude.
            direction_change_interval: Seconds between direction changes
                (based on simulation time, not wall clock).
            seed: RNG seed for reproducibility.
        """
        self._linear_speed = linear_speed
        self._angular_speed = angular_speed
        self._direction_change_interval = direction_change_interval
        self._rng = np.random.default_rng(seed)

        self._last_change_time: float = -direction_change_interval  # force immediate change
        self._current_linear = np.zeros(2)
        self._current_angular: float = 0.0

    def get_velocity(self, sim_time: float) -> tuple[np.ndarray, float]:
        """Get current velocity command, potentially sampling a new direction.

        Args:
            sim_time: Current simulation time in seconds.

        Returns:
            Tuple of (linear_vel as np.ndarray([vx, vy]), angular_vel as float).
        """
        if sim_time - self._last_change_time >= self._direction_change_interval:
            self._sample_new_direction()
            self._last_change_time = sim_time

        return self._current_linear.copy(), float(self._current_angular)

    def _sample_new_direction(self) -> None:
        """Randomly sample new velocity, biased toward forward motion."""
        # Forward-biased vx: mostly positive (0 to linear_speed)
        # with small chance of backward (-linear_speed to 0)
        if self._rng.random() < 0.8:
            vx = self._rng.uniform(0.1, 1.0) * self._linear_speed
        else:
            vx = self._rng.uniform(-0.5, 0.0) * self._linear_speed

        # Small lateral component
        vy = self._rng.uniform(-0.3, 0.3) * self._linear_speed

        # Angular velocity: uniform random
        angular = self._rng.uniform(-1.0, 1.0) * self._angular_speed

        self._current_linear = np.array([vx, vy])
        self._current_angular = angular

        logger.debug(
            "New random direction: linear=[%.2f, %.2f], angular=%.2f",
            vx,
            vy,
            angular,
        )

    def reset(self, seed: int | None = None) -> None:
        """Reset the controller state, optionally with a new seed."""
        if seed is not None:
            self._rng = np.random.default_rng(seed)
        self._last_change_time = -self._direction_change_interval
        self._current_linear = np.zeros(2)
        self._current_angular = 0.0
