"""Shared Go2 command transitions for execution and motion prediction."""
import math


def filter_gait_command(vx, vy, omega, dt, active_yaw, restart_remaining, params):
    """Return effective vx/vy/yaw and next yaw/restart state.

    None yaw state means standing. An active reversal can have zero filtered
    yaw without being idle. A new stop starts one settling interval; repeated
    stops or restart requests count it down rather than extending it forever.
    Inputs must already have the controller's speed/time clamps applied.
    """
    idle = math.hypot(vx, vy) <= .01 and abs(omega) <= .01
    if idle and active_yaw is not None:
        restart_remaining = params.restart_settle_s
    settling = restart_remaining > 1e-12
    restart_remaining = max(0., restart_remaining - dt)
    if idle or settling:
        return 0., 0., 0., None, restart_remaining
    if active_yaw is not None:
        limit = params.command_yaw_acceleration * dt
        omega = active_yaw + max(-limit, min(omega - active_yaw, limit))
    return vx, vy, omega, omega, restart_remaining
