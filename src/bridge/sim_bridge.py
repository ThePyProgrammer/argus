"""MuJoCo bridge -- loads Unitree Go2 and publishes SensorFrame data.

Uses MuJoCo's native renderer for RGB and depth images, and extracts
ground-truth poses directly from the simulation state. This replaces the
SimWorld gym bridge after pivoting to MuJoCo (no GPU required).

The Go2 model comes from mujoco_menagerie (models/unitree_go2/).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame
from src.locomotion import TrotGaitController, GaitParams, patch_actuators_to_position
from src.locomotion.xml_patcher import patch_actuators_to_position_with_floor

logger = logging.getLogger(__name__)

# Standing joint positions from go2.xml keyframe (position-controlled).
_STANDING_QPOS = np.array([
    0.0, 0.9, -1.8,   # FR: hip, thigh, calf
    0.0, 0.9, -1.8,   # FL
    0.0, 0.9, -1.8,   # RR
    0.0, 0.9, -1.8,   # RL
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
        # Trot gait controller for locomotion
        self._gait = TrotGaitController()

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

        # Set initial standing pose (skip the 7 free-joint qpos: 3 pos + 4 quat)
        if self._model.nq >= 19:  # 7 (freejoint) + 12 (actuators)
            self._data.qpos[7:19] = _STANDING_QPOS

        # Settle the robot (let it land on ground)
        standing = self._gait.compute(0.0, 0.0, 0.0, 0.0)
        for _ in range(200):
            self._data.ctrl[:] = standing
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

        Uses TrotGaitController for proper trot gait with position-controlled
        actuators, producing actual locomotion via diagonal pair alternation
        and differential stride turning.
        """
        dt = self._dt  # self._dt already includes sim_steps_per_frame
        vx = float(self._linear_vel[0]) if len(self._linear_vel) > 0 else 0.0
        vy = float(self._linear_vel[1]) if len(self._linear_vel) > 1 else 0.0
        return self._gait.compute(vx, vy, self._angular_vel, dt)

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
