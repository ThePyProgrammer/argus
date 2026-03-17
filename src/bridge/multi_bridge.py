"""Multi-robot MuJoCo bridge -- loads two Go2 robots in a shared scene.

Extends the single-robot MuJoCoBridge concept to support two independently
controlled robots. Each robot gets its own renderer, camera, and velocity
buffer. Joint/actuator indices are discovered dynamically via mj_name2id().
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from src.bridge.sensor_types import SensorFrame
from src.coordination.multi_robot_config import MultiRobotConfig
from src.coordination.scene_builder import build_two_robot_scene

logger = logging.getLogger(__name__)

# Standing joint positions for one Go2 (12 actuators: 4 legs x 3 joints)
_STANDING_QPOS = np.array([
    0.0, 0.8, -1.5,   # FR: hip, thigh, calf
    0.0, 0.8, -1.5,   # FL
    0.0, 0.8, -1.5,   # RR
    0.0, 0.8, -1.5,   # RL
])

# Actuator name suffixes in the order they appear in go2.xml
_ACTUATOR_NAMES = [
    "FL_hip", "FL_thigh", "FL_calf",
    "FR_hip", "FR_thigh", "FR_calf",
    "RL_hip", "RL_thigh", "RL_calf",
    "RR_hip", "RR_thigh", "RR_calf",
]


class MultiRobotBridge:
    """Bridge for two Go2 robots in a shared MuJoCo simulation.

    Lifecycle:
        1. ``bridge = MultiRobotBridge(config)``
        2. ``frames = bridge.start()``   -- builds scene, loads model
        3. ``frames = bridge.step()``    -- steps sim, returns SensorFrames
        4. ``bridge.set_velocity(robot_id, ...)`` -- buffers velocity
        5. ``bridge.stop()``             -- cleans up
    """

    def __init__(self, config: MultiRobotConfig | None = None) -> None:
        self._config = config or MultiRobotConfig()
        self._model: Any = None
        self._data: Any = None
        self._renderers: dict[str, Any] = {}
        self._step_count: int = 0
        self._dt: float = 0.0

        # Per-robot state discovered at start() time via mj_name2id
        self._qpos_starts: dict[str, int] = {}  # robot_id -> qpos start index (7 elements)
        self._ctrl_indices: dict[str, list[int]] = {}  # robot_id -> list of 12 ctrl indices
        self._cam_ids: dict[str, int] = {}  # robot_id -> camera ID

        # Velocity buffers
        self._velocities: dict[str, tuple[np.ndarray, float]] = {
            rid: (np.zeros(2), 0.0) for rid in self._config.robot_ids
        }

        # Last captured frames
        self._last_frames: dict[str, SensorFrame] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> dict[str, SensorFrame]:
        """Build the two-robot scene, load into MuJoCo, and return initial frames.

        Returns:
            Dict mapping robot_id to initial SensorFrame.
        """
        import mujoco

        # Generate combined XML
        xml_str = build_two_robot_scene(
            self._config.model_dir,
            self._config.spawn_positions,
        )

        self._model = mujoco.MjModel.from_xml_string(xml_str)
        self._data = mujoco.MjData(self._model)
        self._dt = self._model.opt.timestep * self._config.sim_steps_per_frame

        # Discover per-robot indices via mj_name2id
        for robot_id in self._config.robot_ids:
            # Freejoint: named "{robot_id}_base" body has a freejoint
            # The freejoint is discovered via the joint named after the body
            # In go2.xml the freejoint has no name, but we prefixed it.
            # Actually, freejoints in go2.xml use <freejoint/> without a name.
            # We need to find the body and then its freejoint's qpos address.
            body_name = f"{robot_id}_base"
            body_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_BODY, body_name)
            if body_id < 0:
                raise RuntimeError(f"Body '{body_name}' not found in model")

            # Find the freejoint for this body by iterating joints
            freejoint_id = -1
            for j in range(self._model.njnt):
                if self._model.jnt_bodyid[j] == body_id and self._model.jnt_type[j] == 0:
                    # type 0 = mjJNT_FREE
                    freejoint_id = j
                    break

            if freejoint_id < 0:
                raise RuntimeError(f"Freejoint not found for body '{body_name}'")

            qpos_start = self._model.jnt_qposadr[freejoint_id]
            self._qpos_starts[robot_id] = qpos_start

            # Discover actuator ctrl indices
            ctrl_ids = []
            for act_name in _ACTUATOR_NAMES:
                full_name = f"{robot_id}_{act_name}"
                act_id = mujoco.mj_name2id(
                    self._model, mujoco.mjtObj.mjOBJ_ACTUATOR, full_name
                )
                if act_id < 0:
                    raise RuntimeError(f"Actuator '{full_name}' not found in model")
                ctrl_ids.append(act_id)
            self._ctrl_indices[robot_id] = ctrl_ids

            # Discover camera ID
            cam_name = f"{robot_id}_cam"
            cam_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_CAMERA, cam_name)
            if cam_id < 0:
                raise RuntimeError(f"Camera '{cam_name}' not found in model")
            self._cam_ids[robot_id] = cam_id

        # Set initial standing pose for both robots
        for robot_id in self._config.robot_ids:
            qstart = self._qpos_starts[robot_id]
            # qpos layout: [x, y, z, qw, qx, qy, qz, joint1..joint12]
            self._data.qpos[qstart + 7 : qstart + 19] = _STANDING_QPOS
            # Set ctrl to standing
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = _STANDING_QPOS[i]

        # Settle physics
        for _ in range(self._config.boot_phase_steps):
            mujoco.mj_step(self._model, self._data)

        # Create one renderer per robot
        w, h = self._config.resolution
        for robot_id in self._config.robot_ids:
            self._renderers[robot_id] = mujoco.Renderer(self._model, height=h, width=w)

        self._step_count = 0

        # Capture initial frames
        frames = {}
        for robot_id in self._config.robot_ids:
            frames[robot_id] = self._capture_frame(robot_id)
        self._last_frames = frames
        return frames

    def step(self) -> dict[str, SensorFrame]:
        """Step the simulation and return SensorFrames for both robots.

        Returns:
            Dict mapping robot_id to SensorFrame.
        """
        import mujoco

        if self._model is None:
            raise RuntimeError("Bridge not started -- call start() first")

        # Apply velocity-to-ctrl for each robot
        for robot_id in self._config.robot_ids:
            ctrl = self._velocity_to_ctrl(robot_id)
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = ctrl[i]

        # Step physics
        for _ in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

        self._step_count += 1

        # Capture frames
        frames = {}
        for robot_id in self._config.robot_ids:
            frames[robot_id] = self._capture_frame(robot_id)
        self._last_frames = frames
        return frames

    def set_velocity(self, robot_id: str, linear: np.ndarray, angular: float) -> None:
        """Buffer a velocity command for the specified robot.

        Args:
            robot_id: Which robot to command.
            linear: (2,) array [vx, vy].
            angular: Angular velocity (positive = turn left).
        """
        self._velocities[robot_id] = (np.asarray(linear, dtype=np.float64), float(angular))

    def get_frame(self, robot_id: str) -> SensorFrame:
        """Return the last captured frame for the specified robot.

        Args:
            robot_id: Which robot's frame to return.

        Returns:
            The most recently captured SensorFrame for that robot.
        """
        return self._last_frames[robot_id]

    def stop(self) -> None:
        """Clean up MuJoCo resources."""
        for renderer in self._renderers.values():
            renderer.close()
        self._renderers.clear()
        self._model = None
        self._data = None
        self._step_count = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _capture_frame(self, robot_id: str) -> SensorFrame:
        """Render RGB + depth from robot's camera, extract pose.

        Args:
            robot_id: Which robot's camera and pose to use.

        Returns:
            SensorFrame with RGB, depth, ground-truth pose, and sim_time.
        """
        renderer = self._renderers[robot_id]
        cam_id = self._cam_ids[robot_id]

        renderer.update_scene(self._data, camera=cam_id)

        # RGB
        rgb = renderer.render().copy()

        # Depth (metric)
        renderer.enable_depth_rendering()
        depth_raw = renderer.render().copy()
        renderer.disable_depth_rendering()

        # Convert depth buffer to metric meters
        extent = self._model.stat.extent
        znear = self._model.vis.map.znear * extent
        zfar = self._model.vis.map.zfar * extent
        depth = znear / (1.0 - depth_raw * (1.0 - znear / zfar) + 1e-10)
        depth = np.where(depth_raw >= 0.999, 0.0, depth).astype(np.float32)

        # Ground-truth pose
        pose = self._extract_pose(robot_id)
        sim_time = self._step_count * self._dt

        return SensorFrame(
            rgb=rgb,
            depth=depth,
            ground_truth_pose=pose,
            sim_time=sim_time,
        )

    def _extract_pose(self, robot_id: str) -> np.ndarray:
        """Extract 4x4 homogeneous transform from robot's freejoint qpos.

        Args:
            robot_id: Which robot's pose to extract.

        Returns:
            (4, 4) float64 homogeneous transform matrix.
        """
        pose = np.eye(4, dtype=np.float64)
        if self._data is None:
            return pose

        start = self._qpos_starts[robot_id]
        pose[:3, 3] = self._data.qpos[start : start + 3]

        # Quaternion: w, x, y, z in MuJoCo convention
        quat = self._data.qpos[start + 3 : start + 7]
        pose[:3, :3] = self._quat_to_rotation_matrix(quat)

        return pose

    def _velocity_to_ctrl(self, robot_id: str) -> np.ndarray:
        """Convert buffered velocity to 12-element joint position targets.

        Uses same sinusoidal gait pattern as MuJoCoBridge._velocity_to_ctrl().

        Args:
            robot_id: Which robot's velocity buffer to read.

        Returns:
            (12,) float64 joint position targets.
        """
        linear, angular = self._velocities[robot_id]
        t = self._step_count * self._dt
        speed = float(np.linalg.norm(linear))
        turn = angular

        ctrl = _STANDING_QPOS.copy()

        if speed > 0.01 or abs(turn) > 0.01:
            freq = 4.0
            amplitude = 0.3 * min(speed + abs(turn), 1.0)
            phase = 2 * math.pi * freq * t

            # FR and RL move together (phase 0), FL and RR (phase pi)
            for leg_idx in [0, 3]:  # FR, RL
                ctrl[leg_idx * 3 + 1] += amplitude * math.sin(phase)
                ctrl[leg_idx * 3 + 2] += amplitude * math.sin(phase) * 0.5
            for leg_idx in [1, 2]:  # FL, RR
                ctrl[leg_idx * 3 + 1] += amplitude * math.sin(phase + math.pi)
                ctrl[leg_idx * 3 + 2] += amplitude * math.sin(phase + math.pi) * 0.5

            if abs(turn) > 0.01:
                hip_offset = 0.2 * turn
                ctrl[0] += hip_offset
                ctrl[3] -= hip_offset
                ctrl[6] += hip_offset
                ctrl[9] -= hip_offset

        return ctrl

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

    @property
    def robot_ids(self) -> tuple[str, str]:
        """The two robot IDs."""
        return self._config.robot_ids
