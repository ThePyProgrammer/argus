from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.platforms.types import (
    ControllerHealth,
    FallReason,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)
from src.bridge.sensor_types import STANDING_QPOS, quat_to_rotation_matrix
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.xml_patcher import patch_actuators_to_position

GO2_ACTUATOR_NAMES = (
    "FL_hip", "FL_thigh", "FL_calf",
    "FR_hip", "FR_thigh", "FR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
)


class Go2VelocityController:
    def __init__(self) -> None:
        self._gait = TrotGaitController()
        self._health = ControllerHealth(policy_loaded=True)

    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray:
        if command.mode in {"stand", "stop", "recover"}:
            return STANDING_QPOS.copy()
        vx = float(command.linear[0])
        vy = float(command.linear[1])
        return self._gait.compute(vx, vy, float(command.yaw_rate), float(dt))

    def health(self) -> ControllerHealth:
        return self._health

    def reset(self) -> None:
        self._gait = TrotGaitController()


class Go2Platform:
    def __init__(self, model_dir: str = "models/unitree_go2") -> None:
        self._metadata = RobotPlatformMetadata(
            name="go2",
            display_name="Unitree Go2",
            model_dir=model_dir,
            model_xml="go2.xml",
            actuator_count=12,
            command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
            footprint_radius=0.35,
            dimensions=(0.7, 0.35, 0.45),
            max_linear_speed=1.0,
            max_yaw_rate=3.0,
            marker_asset="/go2.glb",
            spawn_height=0.3,
        )

    @property
    def metadata(self) -> RobotPlatformMetadata:
        return self._metadata

    def model_xml_path(self) -> Path:
        return Path(self._metadata.model_dir) / self._metadata.model_xml

    def read_model_xml(self) -> str:
        return patch_actuators_to_position(str(self.model_xml_path()))

    def actuator_names(self) -> tuple[str, ...]:
        return GO2_ACTUATOR_NAMES

    def initial_joint_qpos(self) -> np.ndarray:
        return STANDING_QPOS.copy()

    def root_body_name(self) -> str:
        return "base"

    def camera_spec(self, robot_id: str) -> dict[str, str]:
        return {
            "name": f"{robot_id}_cam",
            "pos": "0.4 0 0.05",
            "xyaxes": "0 -1 0 0 0 1",
            "fovy": "70",
        }

    def make_controller(self, robot_id: str) -> Go2VelocityController:
        return Go2VelocityController()

    def _qvel_start_for_qpos(self, model: Any, qpos_start: int) -> int:
        if model is None or not hasattr(model, "jnt_qposadr") or not hasattr(model, "jnt_dofadr"):
            return qpos_start

        qpos_addresses = np.asarray(model.jnt_qposadr)
        matches = np.flatnonzero(qpos_addresses == qpos_start)
        if matches.size == 0:
            return qpos_start

        dof_addresses = np.asarray(model.jnt_dofadr)
        joint_id = int(matches[0])
        if joint_id >= dof_addresses.size:
            return qpos_start
        return int(dof_addresses[joint_id])

    def extract_state(self, model: Any, data: Any, qpos_start: int, sim_time: float) -> RobotState:
        if data is None:
            pose = np.eye(4, dtype=np.float64)
            pose[:3, 3] = [0.0, 0.0, self.metadata.spawn_height]
            return RobotState(
                base_pose=pose,
                base_velocity=np.zeros(3, dtype=np.float64),
                joint_positions=STANDING_QPOS.copy(),
                joint_velocities=np.zeros(12, dtype=np.float64),
                orientation_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                contacts=(),
                sim_time=float(sim_time),
            )

        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = data.qpos[qpos_start:qpos_start + 3]
        quat = data.qpos[qpos_start + 3:qpos_start + 7]
        pose[:3, :3] = quat_to_rotation_matrix(quat)
        qvel_start = self._qvel_start_for_qpos(model, qpos_start)
        joint_positions = data.qpos[qpos_start + 7:qpos_start + 19].copy()
        joint_velocities = data.qvel[qvel_start + 6:qvel_start + 18].copy() if len(data.qvel) >= qvel_start + 18 else np.zeros(12)
        base_velocity = data.qvel[qvel_start:qvel_start + 3].copy() if len(data.qvel) >= qvel_start + 3 else np.zeros(3)
        fallen = pose[2, 3] < 0.16
        reason = FallReason.BASE_HEIGHT if fallen else FallReason.NONE
        return RobotState(
            base_pose=pose,
            base_velocity=base_velocity,
            joint_positions=joint_positions,
            joint_velocities=joint_velocities,
            orientation_quat=quat.copy(),
            contacts=(),
            sim_time=float(sim_time),
            fallen=fallen,
            fall_reason=reason,
        )

    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus:
        if state.fallen:
            runtime_state = RobotRuntimeState.FALLEN
            fall_reason = state.fall_reason
        elif last_command.mode == "recover":
            runtime_state = RobotRuntimeState.RECOVERING
            fall_reason = FallReason.NONE
        elif last_command.mode in {"stand", "stop"}:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        elif np.linalg.norm(last_command.linear) > 0.01 or abs(last_command.yaw_rate) > 0.01:
            runtime_state = RobotRuntimeState.WALKING
            fall_reason = FallReason.NONE
        else:
            runtime_state = RobotRuntimeState.STANDING
            fall_reason = FallReason.NONE
        return RobotRuntimeStatus(
            state=runtime_state,
            fall_reason=fall_reason,
            last_command=last_command,
            controller_health=controller_health,
            collision_count=collision_count,
            near_miss_count=near_miss_count,
        )
