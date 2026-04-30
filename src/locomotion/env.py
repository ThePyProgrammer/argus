"""Gymnasium-style benchmark environment for Unitree Go2 locomotion."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gymnasium
import numpy as np
from gymnasium import spaces

from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.observations import build_observation_space, extract_observation
from src.locomotion.scenarios import ScenarioSample, sample_scenario
from src.locomotion.xml_patcher import patch_actuators_to_position_with_floor


@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    model_dir: str = "models/unitree_go2"
    sim_steps_per_frame: int = 10
    max_episode_steps: int = 500
    render_mode: str | None = None
    heightfield_size: int = 16


class ArgusGo2Env(gymnasium.Env):
    """Gymnasium boundary for the existing analytical Go2 locomotion path."""

    metadata = {"render_modes": ["rgb_array"]}

    def __init__(self, config: ArgusGo2EnvConfig | None = None) -> None:
        self.config = config or ArgusGo2EnvConfig()
        if self.config.sim_steps_per_frame < 1:
            raise ValueError("sim_steps_per_frame must be >= 1")
        if self.config.max_episode_steps < 1:
            raise ValueError("max_episode_steps must be >= 1")
        if self.config.heightfield_size > 64:
            raise ValueError("heightfield_size must be <= 64")
        if self.config.action_mode != "velocity_command":
            raise ValueError("Only velocity_command action_mode is supported in LOC-ENV-01")

        self.action_space = spaces.Box(
            low=np.array([-1.0, -1.0, -3.0], dtype=np.float32),
            high=np.array([1.0, 1.0, 3.0], dtype=np.float32),
            dtype=np.float32,
        )
        self.observation_space = build_observation_space()
        self.render_mode = self.config.render_mode

        self._command = np.zeros(3, dtype=np.float32)
        self._previous_action = np.zeros(12, dtype=np.float32)
        self._step_count = 0
        self._seed: int | None = None
        self._last_seed: int | None = None
        self._scenario_sample: ScenarioSample | None = None
        self._model: Any = None
        self._data: Any = None
        self._dt = 0.002 * self.config.sim_steps_per_frame
        self._gait = TrotGaitController()

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        """Reset the episode and return an observation plus reproducibility info."""
        super().reset(seed=seed)
        self._seed = seed
        self._last_seed = seed
        self._scenario_sample = sample_scenario(self.config.scenario_id, self.np_random,
                                                heightfield_size=self.config.heightfield_size)
        self._step_count = 0
        first_command = self._scenario_sample.command_schedule[0]
        self._command = np.array(
            [first_command["vx"], first_command["vy"], first_command["omega"]],
            dtype=np.float32,
        )
        self._previous_action = np.zeros(12, dtype=np.float32)
        self._gait = TrotGaitController()

        if options and options.get("load_model", False):
            self._ensure_model_loaded()
            self._reset_mujoco_state()

        observation = extract_observation(self._data, self._command, self._previous_action)
        return observation, self._info()

    def step(
        self,
        action: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Apply a velocity command and return the Gymnasium five-tuple."""
        velocity_action = self._validate_velocity_action(action)
        self._command = velocity_action
        vx, vy, omega = (float(value) for value in velocity_action)
        self._previous_action = self._gait.compute(vx, vy, omega, self._dt).astype(
            np.float32,
        )

        if self._data is not None:
            import mujoco

            if self._data.ctrl.shape[0] >= self._previous_action.shape[0]:
                self._data.ctrl[: self._previous_action.shape[0]] = self._previous_action
            for _ in range(self.config.sim_steps_per_frame):
                mujoco.mj_step(self._model, self._data)

        self._step_count += 1
        observation = extract_observation(self._data, self._command, self._previous_action)
        reward = 0.0
        terminated = False
        truncated = self._step_count >= self.config.max_episode_steps
        info = self._info()
        return observation, reward, terminated, truncated, info

    def close(self) -> None:
        """Release MuJoCo handles owned by the environment."""
        self._model = None
        self._data = None

    def _validate_velocity_action(self, action: np.ndarray) -> np.ndarray:
        values = np.asarray(action, dtype=np.float32)
        if values.shape != (3,):
            raise ValueError("velocity_command action must have shape (3,)")
        if not np.all(np.isfinite(values)):
            raise ValueError("velocity_command action must contain only finite values")
        return values.copy()

    def _ensure_model_loaded(self) -> None:
        if self._model is not None and self._data is not None:
            return

        import mujoco

        model_dir = Path(self.config.model_dir)
        go2_xml_path = model_dir / "go2.xml"
        if not go2_xml_path.exists():
            raise FileNotFoundError(f"MuJoCo model not found: {go2_xml_path}")

        patched_xml = patch_actuators_to_position_with_floor(str(go2_xml_path))
        asset_dir = model_dir / "assets"
        assets: dict[str, bytes] = {}
        if asset_dir.exists():
            for asset_path in asset_dir.iterdir():
                if asset_path.is_file():
                    assets[asset_path.name] = asset_path.read_bytes()

        self._model = mujoco.MjModel.from_xml_string(patched_xml, assets)
        self._data = mujoco.MjData(self._model)
        self._dt = float(self._model.opt.timestep) * self.config.sim_steps_per_frame

    def _reset_mujoco_state(self) -> None:
        if self._model is None or self._data is None:
            return

        import mujoco

        mujoco.mj_resetData(self._model, self._data)
        if self._model.nq >= 19:
            self._data.qpos[7:19] = self._previous_action
        mujoco.mj_forward(self._model, self._data)

    def _info(self) -> dict[str, Any]:
        sample = self._scenario_sample
        return {
            "seed": self._last_seed,
            "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "step_count": self._step_count,
            "sim_time": self._step_count * self._dt,
            "spawn_pose": sample.spawn_pose if sample is not None else None,
            "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
            "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
            "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
        }
