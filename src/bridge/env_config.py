"""SimWorld environment configuration.

Centralizes all configuration for the SimWorld gym environment so that
downstream code references a single source of truth for env ID, step rate
targets, and environment kwargs.
"""

from dataclasses import dataclass, field


@dataclass
class SimWorldEnvConfig:
    """Configuration for creating and running a SimWorld gym environment.

    Attributes:
        env_id: Gymnasium registration ID for the SimWorld environment.
            Updated after discovery script confirms the actual ID.
        render_mode: Gymnasium render mode (None, "human", "rgb_array").
        max_episode_steps: Maximum steps before truncation.
        env_kwargs: Additional keyword arguments passed to gym.make().
        target_step_hz: Target gym step rate in Hz. The go/no-go criterion
            requires >= 5 Hz for real-time SLAM.
    """

    env_id: str = "SimWorldRobotics-v0"  # UPDATE after discovery
    render_mode: str | None = None
    max_episode_steps: int = 10000
    env_kwargs: dict = field(default_factory=dict)
    target_step_hz: float = 10.0  # target gym step rate
