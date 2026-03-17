"""MuJoCo bridge -- loads Unitree Go2 and publishes SensorFrame data.

Uses MuJoCo's native renderer for RGB and depth images, and extracts
ground-truth poses directly from the simulation state. This replaces the
SimWorld gym bridge after pivoting to MuJoCo (no GPU required).

The Go2 model comes from mujoco_menagerie (models/unitree_go2/).
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame

logger = logging.getLogger(__name__)

# Action mapping: we command joint velocities to move the robot.
# The Go2 has 12 actuators (4 legs x 3 joints: hip, thigh, calf).
# For locomotion, we use a simple gait pattern.
_STANDING_QPOS = np.array([
    0.0, 0.8, -1.5,   # FR: hip, thigh, calf
    0.0, 0.8, -1.5,   # FL
    0.0, 0.8, -1.5,   # RR
    0.0, 0.8, -1.5,   # RL
])


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

        self._model = mujoco.MjModel.from_xml_path(str(model_path))
        self._data = mujoco.MjData(self._model)
        self._dt = self._model.opt.timestep * self._config.sim_steps_per_frame

        # Set initial standing pose (skip the 7 free-joint qpos: 3 pos + 4 quat)
        if self._model.nq >= 19:  # 7 (freejoint) + 12 (actuators)
            self._data.qpos[7:19] = _STANDING_QPOS

        # Settle the robot (let it land on ground)
        for _ in range(200):
            self._data.ctrl[:] = _STANDING_QPOS
            mujoco.mj_step(self._model, self._data)

        # Create offscreen renderer
        w, h = self._config.resolution
        self._renderer = mujoco.Renderer(self._model, height=h, width=w)

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
            self._data.ctrl[:] = action
        else:
            # Convert velocity command to joint targets for a simple walk
            ctrl = self._velocity_to_ctrl()
            self._data.ctrl[:] = ctrl

        # Step physics multiple times per frame
        for _ in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

        self._step_count += 1
        return self._capture_frame()

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

    def _velocity_to_ctrl(self) -> np.ndarray:
        """Convert buffered velocity to joint position targets.

        Uses a simple sinusoidal gait pattern modulated by the velocity
        command. This is a crude but functional locomotion controller
        sufficient for SLAM testing.
        """
        t = self._step_count * self._dt
        speed = float(np.linalg.norm(self._linear_vel))
        turn = self._angular_vel

        # Base standing pose
        ctrl = _STANDING_QPOS.copy()

        if speed > 0.01 or abs(turn) > 0.01:
            # Simple trot gait: diagonal legs move together
            freq = 4.0  # gait frequency Hz
            amplitude = 0.3 * min(speed + abs(turn), 1.0)
            phase = 2 * math.pi * freq * t

            # FR and RL move together (phase 0), FL and RR (phase pi)
            for leg_idx in [0, 3]:  # FR, RL
                ctrl[leg_idx * 3 + 1] += amplitude * math.sin(phase)      # thigh
                ctrl[leg_idx * 3 + 2] += amplitude * math.sin(phase) * 0.5  # calf
            for leg_idx in [1, 2]:  # FL, RR
                ctrl[leg_idx * 3 + 1] += amplitude * math.sin(phase + math.pi)
                ctrl[leg_idx * 3 + 2] += amplitude * math.sin(phase + math.pi) * 0.5

            # Turning: offset hip joints
            if abs(turn) > 0.01:
                hip_offset = 0.2 * turn
                ctrl[0] += hip_offset   # FR hip
                ctrl[3] -= hip_offset   # FL hip
                ctrl[6] += hip_offset   # RR hip
                ctrl[9] -= hip_offset   # RL hip

        return ctrl

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

        # MuJoCo depth is distance from near plane; convert to metric
        # The renderer returns linear depth in [0, 1] mapped to [znear, zfar]
        extent = self._model.stat.extent
        znear = self._model.vis.map.znear * extent
        zfar = self._model.vis.map.zfar * extent
        # Convert from [0,1] buffer to metric meters
        depth = znear / (1.0 - depth_raw * (1.0 - znear / zfar) + 1e-10)
        # Clip max distance
        depth = np.where(depth_raw >= 0.999, 0.0, depth).astype(np.float32)

        # Ground-truth pose from freejoint qpos
        pose = self._extract_pose()

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
        pose[:3, :3] = self._quat_to_rotation_matrix(quat)

        return pose

    @staticmethod
    def _quat_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
        """Convert MuJoCo quaternion (w, x, y, z) to 3x3 rotation matrix."""
        w, x, y, z = q
        return np.array([
            [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
            [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
            [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
        ], dtype=np.float64)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the simulation is active."""
        return self._model is not None

    @property
    def step_count(self) -> int:
        """Number of steps taken since start."""
        return self._step_count
