from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np

from src.bridge.platforms.types import (
    ControllerHealth,
    RobotCommand,
    RobotPlatformMetadata,
    RobotRuntimeStatus,
    RobotState,
)


@runtime_checkable
class RobotController(Protocol):
    def compute(self, command: RobotCommand, state: RobotState, dt: float) -> np.ndarray: ...
    def health(self) -> ControllerHealth: ...
    def reset(self) -> None: ...


@runtime_checkable
class RobotPlatform(Protocol):
    @property
    def metadata(self) -> RobotPlatformMetadata: ...
    def model_xml_path(self) -> Path: ...
    def read_model_xml(self) -> str: ...
    def actuator_names(self) -> tuple[str, ...]: ...
    def initial_joint_qpos(self) -> np.ndarray: ...
    def root_body_name(self) -> str: ...
    def camera_spec(self, robot_id: str) -> dict[str, str]: ...
    def make_controller(self, robot_id: str) -> RobotController: ...
    def extract_state(self, model: Any, data: Any, qpos_start: int, sim_time: float) -> RobotState: ...
    def runtime_status(
        self,
        robot_id: str,
        state: RobotState,
        last_command: RobotCommand,
        controller_health: ControllerHealth,
        collision_count: int = 0,
        near_miss_count: int = 0,
    ) -> RobotRuntimeStatus: ...
