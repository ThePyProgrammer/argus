"""Control modules for robot navigation in SimWorld.

Provides three control modes that share the same interface:
``get_velocity() -> (np.ndarray, float)`` returning ``(linear_vel, angular_vel)``
compatible with ``SimWorldGymBridge.set_velocity(linear, angular)``.

Modules:
    teleop: Keyboard WASD control via pynput
    waypoint_runner: Scripted waypoint follower
    random_walk: Random exploration with periodic direction changes
"""
