"""MuJoCo bridge -- loads Unitree Go2 and publishes SensorFrame data.

Uses MuJoCo's native renderer for RGB and depth images, and extracts
ground-truth poses directly from the simulation state. No GPU required.

The Go2 model comes from mujoco_menagerie (models/unitree_go2/).
"""


import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix, IMUReading
from src.locomotion.controller_dispatch import (
    apply_controller_target,
    command_from_velocity,
    compute_controller_action,
)
from src.locomotion.controllers import ControllerRegistry, LocomotionCommand
from src.locomotion.gait_params import GaitParams
from src.locomotion.xml_patcher import patch_actuators_to_position, patch_actuators_to_position_with_floor

logger = logging.getLogger(__name__)



class MuJoCoBridge:
    """Bridge between MuJoCo simulation and typed SensorFrame output.

    Lifecycle:
        1. ``bridge = MuJoCoBridge(config)``
        2. ``frame = bridge.start()``   -- loads model, steps to settle
        3. ``frame = bridge.step()``    -- steps sim, returns SensorFrame
        4. ``bridge.set_velocity(...)`` -- buffers velocity command
        5. ``bridge.stop()``            -- cleans up

    MuJoCo provides:
    - RGB rendering via offscreen renderer
    - Metric depth (float32, meters) via depth buffer
    - Exact ground-truth pose from qpos (position + quaternion)
    """

    def __init__(self, config: MuJoCoEnvConfig | None = None) -> None:
        self._config = config or MuJoCoEnvConfig()
        self._model: Any = None
        self._data: Any = None
        self._renderer: Any = None
        self._step_count: int = 0
        self._dt: float = 0.0
        self._linear_vel: np.ndarray = np.zeros(2)
        self._angular_vel: float = 0.0
        # Camera ID (added programmatically)
        self._cam_id: int = -1
        # Registered analytical controller for locomotion
        self._controller = ControllerRegistry.create("analytical_trot")
        # IMU sensor addresses (populated in start() if sensors exist)
        self._has_imu: bool = False
        self._accel_adr: int = 0
        self._gyro_adr: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> SensorFrame:
        """Load the MuJoCo model and initialize the simulation.

        Returns:
            The first SensorFrame from the environment.
        """
        import mujoco

        model_path = Path(self._config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"MuJoCo model not found: {model_path}")

        # Locate go2.xml in the model directory for patching
        model_dir = model_path.parent
        go2_xml_path = model_dir / "go2.xml"

        # Patch actuators to position-controlled servos and add floor/light
        # so the model can be loaded standalone (no scene.xml <include> needed)
        patched_xml = patch_actuators_to_position_with_floor(str(go2_xml_path))

        # Load mesh assets for from_xml_string
        asset_dir = model_dir / "assets"
        assets: dict[str, bytes] = {}
        if asset_dir.exists():
            for f in asset_dir.iterdir():
                if f.is_file():
                    assets[f.name] = f.read_bytes()

        self._model = mujoco.MjModel.from_xml_string(patched_xml, assets)
        self._data = mujoco.MjData(self._model)
        self._dt = self._model.opt.timestep * self._config.sim_steps_per_frame

        # Look up IMU sensor addresses (will be -1 if sensors not in XML)
        accel_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_SENSOR, "accelerometer")
        gyro_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_SENSOR, "gyro")
        if accel_id >= 0 and gyro_id >= 0:
            self._accel_adr = self._model.sensor_adr[accel_id]
            self._gyro_adr = self._model.sensor_adr[gyro_id]
            self._has_imu = True
            logger.info("IMU sensors found: accel_adr=%d, gyro_adr=%d", self._accel_adr, self._gyro_adr)
        else:
            self._has_imu = False
            self._accel_adr = 0
            self._gyro_adr = 0

        # Set initial standing pose (skip the 7 free-joint qpos: 3 pos + 4 quat)
        if self._model.nq >= 19:  # 7 (freejoint) + 12 (actuators)
            self._data.qpos[7:19] = STANDING_QPOS

        # Settle the robot (let it land on ground)
        self._controller.reset()
        standing_command = command_from_velocity(np.zeros(2), 0.0)
        standing = compute_controller_action(self._controller, {}, standing_command, 0.0)
        for _ in range(200):
            apply_controller_target(self._data, standing.action)
            mujoco.mj_step(self._model, self._data)

        # Create offscreen renderer
        w, h = self._config.resolution
        self._renderer = mujoco.Renderer(self._model, height=h, width=w)

        # Resolve camera ID for pose extraction (cam_xpos / cam_xmat)
        import mujoco as _mj
        cam_name = self._config.camera_name
        if isinstance(cam_name, str):
            self._cam_id = _mj.mj_name2id(self._model, _mj.mjtObj.mjOBJ_CAMERA, cam_name)
        else:
            self._cam_id = int(cam_name)

        self._step_count = 0
        return self._capture_frame()

    def step(self, action: np.ndarray | None = None) -> SensorFrame:
        """Step the simulation and return a new SensorFrame.

        Args:
            action: Optional 12-element joint position target. If None,
                uses the velocity command from set_velocity().

        Returns:
            SensorFrame with RGB, depth, and ground-truth pose.
        """
        import mujoco

        if self._model is None:
            raise RuntimeError("Bridge not started -- call start() first")

        if action is not None:
            apply_controller_target(self._data, action)
        else:
            # Convert velocity command to joint targets through the registered controller seam
            ctrl = self._velocity_to_ctrl()
            apply_controller_target(self._data, ctrl)

        # Step physics multiple times per frame, collecting IMU at each sub-step
        imu_readings: list[IMUReading] = []
        sim_time_base = self._step_count * self._dt

        for i in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

            if self._has_imu:
                accel = self._data.sensordata[self._accel_adr:self._accel_adr + 3].copy()
                gyro = self._data.sensordata[self._gyro_adr:self._gyro_adr + 3].copy()
                t = sim_time_base + (i + 1) * self._model.opt.timestep
                imu_readings.append(IMUReading(accel=accel, gyro=gyro, timestamp=t))

        self._step_count += 1
        frame = self._capture_frame()
        frame.imu_readings = imu_readings
        return frame

    def stop(self) -> None:
        """Clean up MuJoCo resources."""
        if self._renderer is not None:
            self._renderer.close()
            self._renderer = None
        self._model = None
        self._data = None
        self._step_count = 0

    # ------------------------------------------------------------------
    # Velocity / action control
    # ------------------------------------------------------------------

    def set_velocity(self, linear: np.ndarray, angular: float) -> None:
        """Buffer a velocity command for the next step.

        Args:
            linear: np.ndarray of shape (2,) representing [vx, vy].
            angular: Angular velocity (positive = turn left).
        """
        self._linear_vel = np.asarray(linear, dtype=np.float64)
        self._angular_vel = float(angular)

    def _velocity_command(self) -> LocomotionCommand:
        """Build a typed command from buffered bridge velocities."""
        return command_from_velocity(self._linear_vel, self._angular_vel)

    def _velocity_to_ctrl(self) -> np.ndarray:
        """Convert buffered velocity to validated joint position targets.

        Uses the registered analytical_trot controller seam for proper trot gait
        with position-controlled actuators, producing actual locomotion via
        diagonal pair alternation and differential stride turning.
        """
        dt = self._dt  # self._dt already includes sim_steps_per_frame
        command = self._velocity_command()
        result = compute_controller_action(self._controller, {}, command, dt)
        return result.action

    # ------------------------------------------------------------------
    # Observation capture
    # ------------------------------------------------------------------

    def _capture_frame(self) -> SensorFrame:
        """Render RGB + depth and extract ground-truth pose."""
        import mujoco

        self._renderer.update_scene(self._data, camera=self._config.camera_name)

        # RGB
        rgb = self._renderer.render().copy()  # (H, W, 3) uint8

        # Depth (metric, in meters)
        self._renderer.enable_depth_rendering()
        depth_raw = self._renderer.render().copy()  # (H, W) float32
        self._renderer.disable_depth_rendering()

        # MuJoCo depth: convert based on value range
        extent = self._model.stat.extent
        znear = self._model.vis.map.znear * extent
        zfar = self._model.vis.map.zfar * extent

        if depth_raw.max() <= 1.0 + 1e-6:
            depth = znear * zfar / (zfar - depth_raw * (zfar - znear))
            depth[depth_raw >= 0.999] = 0.0
        else:
            depth = depth_raw.copy()
            depth[depth_raw >= zfar * 0.99] = 0.0

        depth = np.clip(depth, 0, 20.0).astype(np.float32)

        # Ground-truth pose from camera transform (not body qpos).
        # Depth is rendered from the camera, so the pose must match the
        # camera's position and orientation -- not the robot body's.
        # cam_xmat is R_world_from_cam (columns = camera axes in world).
        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = self._data.cam_xpos[self._cam_id]
        pose[:3, :3] = self._data.cam_xmat[self._cam_id].reshape(3, 3)

        sim_time = self._step_count * self._dt

        return SensorFrame(
            rgb=rgb,
            depth=depth,
            ground_truth_pose=pose,
            sim_time=sim_time,
        )

    def _extract_pose(self) -> np.ndarray:
        """Extract 4x4 homogeneous transform from the robot's freejoint."""
        pose = np.eye(4, dtype=np.float64)

        if self._data is None:
            return pose

        # Position: first 3 elements of qpos (freejoint)
        pose[:3, 3] = self._data.qpos[:3]

        # Orientation: quaternion in qpos[3:7] (w, x, y, z in MuJoCo convention)
        quat = self._data.qpos[3:7]
        pose[:3, :3] = quat_to_rotation_matrix(quat)

        return pose

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._model is not None

    @property
    def step_count(self) -> int:
        return self._step_count
