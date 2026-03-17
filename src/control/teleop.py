"""Keyboard WASD teleop controller using pynput.

Thread-safe velocity output compatible with SimWorldGymBridge.set_velocity().

Controls:
    W / S  -- forward / backward (vx)
    A / D  -- turn left / turn right (angular)
    Q / E  -- strafe left / strafe right (vy)
"""

from __future__ import annotations

import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)


class TeleopController:
    """Keyboard WASD teleop that produces velocity commands.

    Usage::

        teleop = TeleopController(linear_speed=0.5, angular_speed=1.0)
        teleop.start()

        # In your step loop:
        linear, angular = teleop.get_velocity()
        bridge.set_velocity(linear, angular)

        teleop.stop()
    """

    def __init__(
        self,
        linear_speed: float = 0.5,
        angular_speed: float = 1.0,
    ) -> None:
        self._linear_speed = linear_speed
        self._angular_speed = angular_speed
        self._keys_pressed: set = set()
        self._lock = threading.Lock()
        self._listener = None

    def start(self) -> None:
        """Start the keyboard listener thread."""
        from pynput import keyboard

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("Teleop started -- WASD to move, Q/E to strafe")

    def stop(self) -> None:
        """Stop the keyboard listener thread."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._lock:
            self._keys_pressed.clear()
        logger.info("Teleop stopped")

    def get_velocity(self) -> tuple[np.ndarray, float]:
        """Return current velocity command based on pressed keys.

        Returns:
            Tuple of (linear_vel as np.ndarray([vx, vy]), angular_vel as float).
            Compatible with ``SimWorldGymBridge.set_velocity(linear, angular)``.
        """
        from pynput import keyboard

        with self._lock:
            keys = set(self._keys_pressed)

        vx = 0.0
        vy = 0.0
        wz = 0.0

        # Forward / backward
        if keyboard.KeyCode.from_char("w") in keys:
            vx += self._linear_speed
        if keyboard.KeyCode.from_char("s") in keys:
            vx -= self._linear_speed

        # Turn left / right
        if keyboard.KeyCode.from_char("a") in keys:
            wz += self._angular_speed
        if keyboard.KeyCode.from_char("d") in keys:
            wz -= self._angular_speed

        # Strafe left / right
        if keyboard.KeyCode.from_char("q") in keys:
            vy += self._linear_speed
        if keyboard.KeyCode.from_char("e") in keys:
            vy -= self._linear_speed

        return np.array([vx, vy]), wz

    def _on_press(self, key) -> None:
        """Callback for key press events."""
        with self._lock:
            self._keys_pressed.add(key)

    def _on_release(self, key) -> None:
        """Callback for key release events."""
        with self._lock:
            self._keys_pressed.discard(key)

    @property
    def is_running(self) -> bool:
        """True if the keyboard listener is active."""
        return self._listener is not None and self._listener.is_alive()
