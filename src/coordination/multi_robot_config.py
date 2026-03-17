"""Configuration for multi-robot MuJoCo simulation.

Defines spawn positions, robot IDs, and shared parameters for the
two-robot coordination setup.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MultiRobotConfig:
    """Configuration for a two-robot MuJoCo scene.

    Attributes:
        robot_ids: Tuple of two robot identifier strings.
        spawn_positions: Mapping from robot_id to (x, y, z) world spawn position.
        resolution: Render resolution as (width, height).
        sim_steps_per_frame: Number of MuJoCo physics steps per sensor frame.
        model_dir: Path to the directory containing go2.xml and assets.
        boot_phase_steps: Number of physics steps for initial settling.
    """

    robot_ids: tuple[str, str] = ("robot_a", "robot_b")
    spawn_positions: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "robot_a": (0.0, 0.0, 0.3),
            "robot_b": (10.0, 0.0, 0.3),
        }
    )
    resolution: tuple[int, int] = (320, 240)
    sim_steps_per_frame: int = 10
    model_dir: str = "models/unitree_go2"
    boot_phase_steps: int = 200
