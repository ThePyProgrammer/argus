"""Control modules for robot velocity generation.

All three modules produce ``(np.ndarray, float)`` velocity commands
``(linear_vel, angular_vel)``, but each has a distinct input contract:

Modules:
    teleop: ``get_velocity() -> (vel, ang)`` -- no arguments; reads keyboard state.
    waypoint_runner: ``get_velocity(current_pose, depth=None) -> (vel, ang)`` --
        requires the robot's current (4,4) pose and optional depth image.
    random_walk: ``get_velocity(sim_time) -> (vel, ang)`` -- requires the
        current simulation time to decide when to change direction.
"""
