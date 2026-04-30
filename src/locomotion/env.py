"""Gymnasium-style benchmark environment for Unitree Go2 locomotion."""

import copy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import gymnasium
import numpy as np
from src.locomotion.actions import ACTION_MODE_VELOCITY, build_action_space, decode_action
from src.locomotion.controller_dispatch import command_from_velocity, dispatch_controller
from src.locomotion.controllers import ControllerRegistry
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.metrics import (
    Go2FootMapping,
    LocomotionMetricsCollector,
    LocomotionMetricsConfig,
    foot_contact_payload_from_mujoco,
)
from src.locomotion.observations import build_observation_space, extract_observation
from src.locomotion.scenarios import ScenarioSample, build_scenario_xml, sample_scenario


@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    controller_id: str = "analytical_trot"
    model_dir: str | None = None
    sim_steps_per_frame: int = 10
    max_episode_steps: int = 500
    render_mode: str | None = None
    heightfield_size: int = 16
    metrics_config: LocomotionMetricsConfig | None = None


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
        self._controller = ControllerRegistry.create(self.config.controller_id)
        self._controller_metadata = self._metadata_for_controller(self.config.controller_id)
        self._gait = TrotGaitController()
        self._metrics = LocomotionMetricsCollector(self.config.metrics_config)
        self._last_locomotion_metrics_summary: dict[str, Any] | None = None
        self._foot_mapping: Go2FootMapping | None = None
        self._previous_previous_action = np.zeros(12, dtype=np.float32)

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
        self._previous_previous_action = np.zeros(12, dtype=np.float32)
        self._active_push = None
        self._foot_mapping = None
        self._controller.reset(seed=seed)
        self._gait = TrotGaitController()

        self._try_initialize_mujoco()
        if self._model is not None and self._is_real_mujoco_model():
            self._foot_mapping = Go2FootMapping.from_mujoco_model(self._model)
        self._reset_mujoco_state()
        self._metrics.reset_episode()

        observation = extract_observation(self._data, self._command, self._previous_action)
        return observation, self._info()

    def step(
        self,
        action: np.ndarray,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
        """Apply a mode-specific action and return the Gymnasium five-tuple."""
        previous_action = self._previous_action.copy()
        previous_previous_action = self._previous_previous_action.copy()
        pose_before = self._base_pose_snapshot()
        command = self._command
        if self.config.action_mode != ACTION_MODE_VELOCITY:
            command = self._command_at_time(self._current_sim_time())
        if self.config.action_mode == ACTION_MODE_VELOCITY:
            velocity_action = self._validate_velocity_action(action)
            command_obj = command_from_velocity(
                velocity_action[:2],
                float(velocity_action[2]),
                metadata={"controller_id": self.config.controller_id},
            )
            result = dispatch_controller(
                self._controller,
                extract_observation(self._data, self._command, self._previous_action),
                command_obj,
                self._dt,
                data=self._data,
            )
            ctrl = result.action
            self._command = velocity_action.copy()
        else:
            ctrl = decode_action(
                action,
                self.config.action_mode,
                self._gait,
                self._dt,
                command,
            )
            self._command = command
        action_target = np.asarray(ctrl, dtype=np.float32).reshape(12).copy()
        self._previous_previous_action = previous_action
        self._previous_action = action_target

        if self._data is not None:
            import mujoco

            if self.config.action_mode != ACTION_MODE_VELOCITY:
                self._data.ctrl[:] = self._previous_action
            self._apply_push_disturbance()
            for _ in range(self.config.sim_steps_per_frame):
                mujoco.mj_step(self._model, self._data)

        pose_after = self._base_pose_snapshot()
        self._step_count += 1
        metrics_step = self._record_locomotion_metrics(
            desired_command=self._command,
            pose_before=pose_before,
            pose_after=pose_after,
            action_target=action_target,
            previous_action_target=previous_action,
            previous_previous_action_target=previous_previous_action,
        )
        observation = extract_observation(self._data, self._command, self._previous_action)
        reward = 0.0
        terminated = metrics_step.failure_reason is not None
        truncated = self._step_count >= self.config.max_episode_steps
        info = self._info()
        info["locomotion_metrics"] = self._metrics.latest_info_payload()
        if terminated or truncated:
            summary = self._locomotion_summary_payload()
            self._last_locomotion_metrics_summary = copy.deepcopy(summary)
            info["locomotion_metrics_summary"] = summary
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

    @property
    def last_locomotion_metrics_summary(self) -> dict[str, Any] | None:
        """Latest completed locomotion metrics summary, defensively copied."""
        if self._last_locomotion_metrics_summary is None:
            return None
        return copy.deepcopy(self._last_locomotion_metrics_summary)

    def _resolved_model_dir(self) -> Path:
        if self.config.model_dir is not None:
            return Path(self.config.model_dir).expanduser().resolve()
        return Path(__file__).resolve().parents[2] / "models" / "unitree_go2"

    def _validate_velocity_action(self, action: np.ndarray) -> np.ndarray:
        vector = np.asarray(action, dtype=np.float32)
        if vector.shape != (3,):
            raise ValueError(f"Velocity command action must have shape (3,), got {vector.shape}")
        if not np.all(np.isfinite(vector)):
            raise ValueError("Velocity command action values must be finite")
        low = self.action_space.low.astype(np.float32)
        high = self.action_space.high.astype(np.float32)
        if np.any(vector < low) or np.any(vector > high):
            raise ValueError("Velocity command action values must be within the action space bounds")
        return vector.copy()

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

    def _base_pose_snapshot(self) -> tuple[np.ndarray, float, float]:
        if self._data is None:
            return np.zeros(2, dtype=np.float64), 0.0, self._current_sim_time()
        qpos = np.asarray(self._data.qpos, dtype=np.float64)
        xy = np.zeros(2, dtype=np.float64)
        if qpos.size >= 2:
            xy = qpos[:2].copy()
        yaw = self._yaw_from_qpos(qpos)
        return xy, yaw, self._current_sim_time()

    def _record_locomotion_metrics(
        self,
        *,
        desired_command: np.ndarray,
        pose_before: tuple[np.ndarray, float, float],
        pose_after: tuple[np.ndarray, float, float],
        action_target: np.ndarray,
        previous_action_target: np.ndarray,
        previous_previous_action_target: np.ndarray,
    ):
        qpos = self._qpos_snapshot()
        qvel = self._qvel_snapshot()
        dt = max(float(pose_after[2] - pose_before[2]), self._dt)
        delta_xy = pose_after[0] - pose_before[0]
        measured = np.array(
            [
                float(delta_xy[0] / dt),
                float(delta_xy[1] / dt),
                float(self._wrapped_angle(pose_after[1] - pose_before[1]) / dt),
            ],
            dtype=np.float64,
        )
        roll, pitch = self._roll_pitch_from_qpos(qpos)
        contact_payload = self._contact_payload()
        return self._metrics.record_step(
            desired_command=np.asarray(desired_command, dtype=np.float64).copy(),
            measured_base_velocity=measured,
            roll_rad=roll,
            pitch_rad=pitch,
            base_height_m=float(qpos[2]) if qpos.size > 2 else 0.0,
            base_xy_position=pose_after[0],
            action_target=action_target,
            previous_action_target=previous_action_target,
            previous_previous_action_target=previous_previous_action_target,
            joint_qpos=qpos[7:19] if qpos.size >= 19 else np.zeros(12, dtype=np.float64),
            joint_qvel=qvel[6:18] if qvel.size >= 18 else np.zeros(12, dtype=np.float64),
            dt=dt,
            **contact_payload,
        )

    def _contact_payload(self) -> dict[str, Any]:
        if self._data is None or self._foot_mapping is None:
            return {"contact_terrain_payload": {}}
        return foot_contact_payload_from_mujoco(self._foot_mapping, self._data, self._scenario_sample)

    def _qpos_snapshot(self) -> np.ndarray:
        qpos = np.zeros(19, dtype=np.float64)
        if self._data is not None and hasattr(self._data, "qpos"):
            source = np.asarray(self._data.qpos, dtype=np.float64).reshape(-1)
            qpos[: min(source.size, qpos.size)] = source[: qpos.size]
        return qpos

    def _qvel_snapshot(self) -> np.ndarray:
        qvel = np.zeros(18, dtype=np.float64)
        if self._data is not None and hasattr(self._data, "qvel"):
            source = np.asarray(self._data.qvel, dtype=np.float64).reshape(-1)
            qvel[: min(source.size, qvel.size)] = source[: qvel.size]
        return qvel

    def _yaw_from_qpos(self, qpos: np.ndarray) -> float:
        if qpos.size < 7:
            return 0.0
        w, x, y, z = [float(value) for value in qpos[3:7]]
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return float(math.atan2(siny_cosp, cosy_cosp))

    def _roll_pitch_from_qpos(self, qpos: np.ndarray) -> tuple[float, float]:
        if qpos.size < 7:
            return 0.0, 0.0
        w, x, y, z = [float(value) for value in qpos[3:7]]
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        sinp = 2.0 * (w * y - z * x)
        pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
        return float(roll), float(pitch)

    def _locomotion_summary_payload(self) -> dict[str, Any]:
        summary = self._metrics.episode_summary()
        payload = {
            "command_tracking": dict(summary.command_tracking),
            "stability": dict(summary.stability),
            "action_quality": dict(summary.action_quality),
            "contact_terrain": dict(summary.contact_terrain),
            "success": bool(summary.success),
            "failure_reason": summary.failure_reason,
            "step_count": int(summary.step_count),
        }
        payload["stability"]["success"] = bool(summary.success)
        return payload

    def _wrapped_angle(self, angle: float) -> float:
        return float((angle + math.pi) % (2.0 * math.pi) - math.pi)

    def _current_sim_time(self) -> float:
        if self._data is not None and hasattr(self._data, "time") and float(self._data.time) > 0.0:
            return float(self._data.time)
        return self._step_count * self._dt

    def _metadata_for_controller(self, controller_id: str) -> dict[str, Any]:
        for entry in ControllerRegistry.list_controllers():
            if entry["name"] == controller_id:
                return {
                    "controller_id": entry["controller_id"],
                    "display_name": entry["display_name"],
                    "family": entry["family"],
                    "action_mode": entry["action_mode"],
                    "deterministic": entry["deterministic"],
                    "parameter_hash": entry["parameter_hash"],
                    "parameter_summary": dict(entry["parameter_summary"]),
                    "capabilities": dict(entry["capabilities"]),
                    "available": entry["available"],
                }
        raise ValueError(
            f"Unknown locomotion controller '{controller_id}'. "
            f"Available: {[entry['name'] for entry in ControllerRegistry.list_controllers()]}"
        )

    def _info(self) -> dict[str, Any]:
        sample = self._scenario_sample
        info = {
            "seed": self._last_seed,
            "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "controller_id": self.config.controller_id,
            "step_count": self._step_count,
            "sim_time": self._current_sim_time(),
            "spawn_pose": sample.spawn_pose if sample is not None else None,
            "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
            "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
            "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
            "active_push": dict(self._active_push) if self._active_push is not None else None,
        }
        if self._step_count == 0:
            info["controller_metadata"] = dict(self._controller_metadata)
        return info
