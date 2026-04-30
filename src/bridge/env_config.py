"""MuJoCo environment configuration.

Centralizes all configuration for the MuJoCo simulation so that
downstream code references a single source of truth.
"""

from dataclasses import dataclass


@dataclass
class MuJoCoEnvConfig:
    """Configuration for the MuJoCo simulation environment.

    Attributes:
        model_path: Path to the MuJoCo XML model file.
        resolution: Render resolution as (width, height).
        camera_name: Fixed camera name or id for rendering and pose extraction.
        sim_steps_per_frame: Number of physics steps per sensor frame.
            Higher = more stable physics but slower frame rate.
        target_step_hz: Target sensor frame rate in Hz.
    """

    model_path: str = "models/unitree_go2/scene.xml"
    resolution: tuple[int, int] = (320, 240)
    camera_name: int | str = "front_cam"  # named camera attached to robot base
    sim_steps_per_frame: int = 10  # 10 steps * 0.002s dt = 50Hz physics, 5Hz frames
    target_step_hz: float = 10.0
