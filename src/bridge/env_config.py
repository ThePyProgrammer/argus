"""SimWorld environment configuration.

Centralizes all configuration for the SimWorld gym environment so that
downstream code references a single source of truth for env ID, step rate
targets, and environment kwargs.
"""

from dataclasses import dataclass, field


@dataclass
class SimWorldEnvConfig:
    """Configuration for creating and running a SimWorld gym environment.

    Discovered from SimWorld-Robotics source code (2026-03-17):
    - Uses legacy ``gym`` (not ``gymnasium``): ``from gym.envs.registration import register``
    - Env IDs: ``simworld_gym/SimpleWorld`` (single-agent),
      ``simworld_gym/BufferWorld`` (multi-agent), ``simworld_gym/TrafficWorld``
    - Action space: Discrete(6) -- 0-3 movement, 4-5 rotation
    - Observation types: ``ground_truth``, ``rgb``, ``depth``, ``rgbd``, ``all``
    - Default resolution: (320, 240)  (W, H)
    - Camera FOV: 120 degrees (hardcoded in agent_controller._generate_agent)

    Attributes:
        env_id: Gym registration ID for the SimWorld environment.
            Discovered: ``simworld_gym/SimpleWorld`` for single-agent.
        observation_type: One of ``ground_truth``, ``rgb``, ``depth``,
            ``rgbd``, ``all``.  Use ``rgbd`` for SLAM.
        render_mode: Gym render mode (None, "human", "rgb_array").
        max_episode_steps: Maximum steps before truncation.
        resolution: Image resolution as (width, height).
        env_kwargs: Additional keyword arguments passed to gym.make().
        target_step_hz: Target gym step rate in Hz. The go/no-go criterion
            requires >= 5 Hz for real-time SLAM.
    """

    env_id: str = "simworld_gym/SimpleWorld"  # discovered from __init__.py
    observation_type: str = "rgbd"  # rgb + depth for SLAM
    render_mode: str | None = None
    max_episode_steps: int = 10000
    resolution: tuple[int, int] = (320, 240)  # (width, height)
    env_kwargs: dict = field(default_factory=dict)
    target_step_hz: float = 10.0  # target gym step rate
