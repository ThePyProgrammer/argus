from __future__ import annotations

import math
import xml.etree.ElementTree as ET
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
from src.bridge.sensor_types import quat_to_rotation_matrix
from src.locomotion.x2_controller import X2PolicyController


class AgibotX2Platform:
    def __init__(
        self,
        model_dir: str = "models/agibot_x2",
        model_xml: str = "x2_ultra.xml",
        controller_path: str | None = None,
        expected_actuator_count: int = 31,
    ) -> None:
        self._controller_path = controller_path
        self._xml_root_cache: ET.Element | None = None
        self._actuator_names_cache: tuple[str, ...] | None = None
        self._initial_joint_qpos_cache: np.ndarray | None = None
        self._root_body_name_cache: str | None = None
        self._metadata = RobotPlatformMetadata(
            name="agibot_x2",
            display_name="AGIBOT X2 Ultra",
            model_dir=model_dir,
            model_xml=model_xml,
            actuator_count=expected_actuator_count,
            command_modes=("velocity", "stand", "stop", "recover", "waypoint"),
            footprint_radius=0.33,
            dimensions=(0.46, 0.21, 1.31),
            max_linear_speed=0.8,
            max_yaw_rate=1.0,
            marker_asset=None,
            spawn_height=0.85,
        )

    @property
    def metadata(self) -> RobotPlatformMetadata:
        return self._metadata

    def model_xml_path(self) -> Path:
        return Path(self._metadata.model_dir) / self._metadata.model_xml

    def read_model_xml(self) -> str:
        path = self.model_xml_path()
        try:
            return path.read_text()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"AGIBOT X2 model XML not found: {path}") from exc

    def actuator_names(self) -> tuple[str, ...]:
        if self._actuator_names_cache is not None:
            return self._actuator_names_cache

        root = self._xml_root()
        actuator = root.find("actuator")
        names: tuple[str, ...]
        if actuator is None:
            names = ()
        else:
            names = tuple(
                child.attrib.get("name") or f"actuator_{index}"
                for index, child in enumerate(list(actuator))
            )
        if len(names) != self._metadata.actuator_count:
            raise ValueError(
                f"expected {self._metadata.actuator_count} AGIBOT X2 actuators, found {len(names)} in {self.model_xml_path()}"
            )
        self._actuator_names_cache = names
        return names

    def initial_joint_qpos(self) -> np.ndarray:
        if self._initial_joint_qpos_cache is not None:
            return self._initial_joint_qpos_cache.copy()

        root = self._xml_root()
        key = root.find("keyframe/key")
        if key is None or "qpos" not in key.attrib:
            joint_qpos = np.zeros(self._metadata.actuator_count, dtype=np.float64)
        else:
            qpos = np.fromstring(key.attrib["qpos"], sep=" ", dtype=np.float64)
            joint_qpos = qpos[7:7 + self._metadata.actuator_count]
            if joint_qpos.shape != (self._metadata.actuator_count,):
                joint_qpos = np.zeros(self._metadata.actuator_count, dtype=np.float64)
        self._initial_joint_qpos_cache = joint_qpos.copy()
        return joint_qpos.copy()

    def root_body_name(self) -> str:
        if self._root_body_name_cache is not None:
            return self._root_body_name_cache

        root = self._xml_root()
        body = root.find("worldbody/body")
        if body is None:
            raise ValueError(f"AGIBOT X2 model has no root body in {self.model_xml_path()}")
        name = body.attrib.get("name")
        if not name:
            raise ValueError(f"AGIBOT X2 root body is unnamed in {self.model_xml_path()}")
        self._root_body_name_cache = name
        return name

    def camera_spec(self, robot_id: str) -> dict[str, str]:
        return {
            "name": f"{robot_id}_cam",
            "pos": "0.16 0 0.28",
            "xyaxes": "0 -1 0 0 0 1",
            "fovy": "70",
        }

    def make_controller(self, robot_id: str) -> X2PolicyController:
        _ = robot_id
        return X2PolicyController(
            actuator_count=len(self.actuator_names()),
            policy_path=self._controller_path,
            default_qpos=self.initial_joint_qpos(),
        )

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
        actuator_count = len(self.actuator_names())
        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = np.asarray(data.qpos[qpos_start:qpos_start + 3], dtype=np.float64)
        quat = np.asarray(data.qpos[qpos_start + 3:qpos_start + 7], dtype=np.float64)
        pose[:3, :3] = quat_to_rotation_matrix(quat)
        qvel_start = self._qvel_start_for_qpos(model, qpos_start)
        return self._state_from_arrays(
            base_pose=pose,
            base_velocity=np.asarray(data.qvel[qvel_start:qvel_start + 3], dtype=np.float64),
            joint_positions=np.asarray(data.qpos[qpos_start + 7:qpos_start + 7 + actuator_count], dtype=np.float64),
            joint_velocities=np.asarray(data.qvel[qvel_start + 6:qvel_start + 6 + actuator_count], dtype=np.float64),
            orientation_quat=quat,
            sim_time=sim_time,
        )

    def _state_from_arrays(
        self,
        base_pose: np.ndarray,
        base_velocity: np.ndarray,
        joint_positions: np.ndarray,
        joint_velocities: np.ndarray,
        orientation_quat: np.ndarray,
        sim_time: float,
    ) -> RobotState:
        pose = np.asarray(base_pose, dtype=np.float64)
        quat = np.asarray(orientation_quat, dtype=np.float64)
        fall_reason = self._fall_reason(pose, quat)
        return RobotState(
            base_pose=pose,
            base_velocity=np.asarray(base_velocity, dtype=np.float64),
            joint_positions=np.asarray(joint_positions, dtype=np.float64),
            joint_velocities=np.asarray(joint_velocities, dtype=np.float64),
            orientation_quat=quat,
            contacts=(),
            sim_time=float(sim_time),
            fallen=fall_reason != FallReason.NONE,
            fall_reason=fall_reason,
        )

    def _fall_reason(self, base_pose: np.ndarray, quat: np.ndarray) -> FallReason:
        if float(base_pose[2, 3]) < 0.45:
            return FallReason.BASE_HEIGHT
        roll, pitch = self._roll_pitch(quat)
        if abs(roll) > 0.75 or abs(pitch) > 0.75:
            return FallReason.ROLL_PITCH_THRESHOLD
        return FallReason.NONE

    def _roll_pitch(self, quat: np.ndarray) -> tuple[float, float]:
        w, x, y, z = np.asarray(quat, dtype=np.float64)
        sinr_cosp = 2.0 * (w * x + y * z)
        cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2.0 * (w * y - z * x)
        if abs(sinp) >= 1.0:
            pitch = math.copysign(math.pi / 2.0, sinp)
        else:
            pitch = math.asin(sinp)
        return roll, pitch

    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus:
        _ = robot_id
        if state.fallen:
            runtime_state = RobotRuntimeState.FALLEN
            fall_reason = state.fall_reason
        elif not controller_health.nan_guard_ok:
            runtime_state = RobotRuntimeState.DISABLED
            fall_reason = FallReason.CONTROLLER_INVALID_OUTPUT
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

    def _xml_root(self) -> ET.Element:
        if self._xml_root_cache is None:
            self._xml_root_cache = ET.fromstring(self.read_model_xml())
        return self._xml_root_cache
