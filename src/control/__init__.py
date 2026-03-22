"""Control modules for robot velocity generation.

Provides three control modes that produce velocity commands:
``get_velocity() -> (np.ndarray, float)`` returning ``(linear_vel, angular_vel)``.

Modules:
    teleop: Keyboard WASD control via pynput
    waypoint_runner: Scripted waypoint follower
    random_walk: Random exploration with periodic direction changes
"""
