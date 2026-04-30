"""Gymnasium-style benchmark environment for Unitree Go2 locomotion."""

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import gymnasium
import numpy as np
from src.locomotion.actions import ACTION_MODE_VELOCITY, build_action_space, decode_action
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.observations import build_observation_space, extract_observation
from src.locomotion.scenarios import ScenarioSample, build_scenario_xml, sample_scenario


@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    model_dir: str | None = None
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

        self.action_space = build_action_space(self.config.action_mode)
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
        self._renderer: Any = None
        self._dt = 0.002 * self.config.sim_steps_per_frame
        self._active_push: dict[str, float] | None = None
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
        if self._model is not None and self._data is not None and self._is_real_mujoco_model():
            self._model = None
            self._data = None
            self._dt = 0.002 * self.config.sim_steps_per_frame
        self._step_count = 0
        first_command = self._scenario_sample.command_schedule[0]
        self._command = np.array(
            [first_command["vx"], first_command["vy"], first_command["omega"]],
            dtype=np.float32,
        )
        self._previous_action = np.zeros(12, dtype=np.float32)
        self._active_push = None
        self._gait = TrotGaitController()

        self._try_initialize_mujoco()
        self._reset_mujoco_state()

        observation = extract_observation(self._data, self._command, self._previous_action)
        return observation, self._info()

    def step(
        self,
        action: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Apply a mode-specific action and return the Gymnasium five-tuple."""
        command = self._command
        if self.config.action_mode != ACTION_MODE_VELOCITY:
            command = self._command_at_time(self._current_sim_time())
        ctrl = decode_action(
            action,
            self.config.action_mode,
            self._gait,
            self._dt,
            command,
        )
        if self.config.action_mode == ACTION_MODE_VELOCITY:
            self._command = np.asarray(action, dtype=np.float32).copy()
        else:
            self._command = command
        self._previous_action = ctrl.astype(np.float32)

        if self._data is not None:
            import mujoco

            self._data.ctrl[:] = self._previous_action
            self._apply_push_disturbance()
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
        if self._renderer is not None and hasattr(self._renderer, "close"):
            self._renderer.close()
        self._renderer = None
        self._model = None
        self._data = None
        self._step_count = 0

    @property
    def step_count(self) -> int:
        """Number of successful environment steps since the last reset."""
        return self._step_count

    def _resolved_model_dir(self) -> Path:
        if self.config.model_dir is not None:
            return Path(self.config.model_dir).expanduser().resolve()
        return Path(__file__).resolve().parents[2] / "models" / "unitree_go2"

    def _try_initialize_mujoco(self) -> None:
        if self._model is not None and self._data is not None:
            return
        if self._data is not None:
            return
        try:
            import mujoco
        except ImportError:
            self._model = None
            self._data = None
            return

        model_dir = self._resolved_model_dir()
        go2_xml = model_dir / "go2.xml"
        if not go2_xml.exists():
            raise FileNotFoundError(f"Go2 model not found: {go2_xml}")
        if self._scenario_sample is None:
            return

        xml, assets = build_scenario_xml(str(model_dir), self._scenario_sample)
        self._model = mujoco.MjModel.from_xml_string(xml, assets)
        self._load_heightfield_data()
        self._data = mujoco.MjData(self._model)
        self._dt = float(self._model.opt.timestep) * self.config.sim_steps_per_frame

    def _load_heightfield_data(self) -> None:
        sample = self._scenario_sample
        if self._model is None or sample is None:
            return
        heightfield_data = sample.terrain_parameters.get("heightfield_data")
        if heightfield_data is None or not hasattr(self._model, "hfield_data"):
            return
        heights = np.asarray(heightfield_data, dtype=np.float64)
        if heights.size != self._model.hfield_data.size:
            raise ValueError(
                f"rough heightfield size mismatch: {heights.size} samples for "
                f"{self._model.hfield_data.size} model cells"
            )
        self._model.hfield_data[:] = heights

    def _reset_mujoco_state(self) -> None:
        if self._model is None or self._data is None:
            return

        try:
            import mujoco
        except ImportError:
            mujoco = None

        if mujoco is not None and self._is_real_mujoco_model():
            mujoco.mj_resetData(self._model, self._data)
        sample = self._scenario_sample
        if sample is not None and self._model.nq >= 3:
            self._data.qpos[:3] = sample.spawn_pose[:3]
        if sample is not None and self._model.nq >= 7:
            yaw = sample.spawn_pose[3]
            self._data.qpos[3:7] = (math.cos(yaw / 2), 0.0, 0.0, math.sin(yaw / 2))
        if self._model.nq >= 19:
            standing = GaitParams()
            self._data.qpos[7:19] = [standing.standing_hip, standing.standing_thigh, standing.standing_calf] * 4
        if hasattr(self._data, "qvel"):
            self._data.qvel[:] = 0.0
        if hasattr(self._data, "ctrl"):
            self._data.ctrl[:] = 0.0
        if hasattr(self._data, "xfrc_applied"):
            self._data.xfrc_applied[:] = 0.0
        if mujoco is not None and self._is_real_mujoco_model():
            mujoco.mj_forward(self._model, self._data)

    def _is_real_mujoco_model(self) -> bool:
        return self._model.__class__.__module__.startswith("mujoco")

    def _apply_push_disturbance(self) -> None:
        if self._data is None or not hasattr(self._data, "xfrc_applied"):
            return
        self._data.xfrc_applied[:] = 0.0
        self._active_push = None
        sample = self._scenario_sample
        if sample is None:
            return
        sim_time = self._current_sim_time()
        for push in sample.disturbance_schedule:
            start = float(push["time"])
            end = start + float(push["duration"])
            if start <= sim_time + 1e-12 < end:
                force = np.array([push["force_x"], push["force_y"], push["force_z"]], dtype=np.float64)
                self._data.xfrc_applied[0, :3] = force
                self._active_push = dict(push)
                return

    def _command_at_time(self, sim_time: float) -> np.ndarray:
        sample = self._scenario_sample
        if sample is None or not sample.command_schedule:
            return self._command
        active = sample.command_schedule[0]
        for command in sample.command_schedule:
            if float(command["time"]) <= sim_time + 1e-12:
                active = command
            else:
                break
        return np.array([active["vx"], active["vy"], active["omega"]], dtype=np.float32)

    def _current_sim_time(self) -> float:
        if self._data is not None and hasattr(self._data, "time") and float(self._data.time) > 0.0:
            return float(self._data.time)
        return self._step_count * self._dt

    def _info(self) -> dict[str, Any]:
        sample = self._scenario_sample
        return {
            "seed": self._last_seed,
            "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "step_count": self._step_count,
            "sim_time": self._current_sim_time(),
            "spawn_pose": sample.spawn_pose if sample is not None else None,
            "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
            "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
            "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
            "active_push": dict(self._active_push) if self._active_push is not None else None,
        }
