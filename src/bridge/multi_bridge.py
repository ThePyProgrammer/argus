"""Multi-robot MuJoCo bridge -- loads N Go2 robots in a shared scene.

Extends the single-robot MuJoCoBridge concept to support N independently
controlled robots. Each robot gets its own renderer, camera, and velocity
buffer. Joint/actuator indices are discovered dynamically via mj_name2id().
"""


import logging
from typing import Any

import numpy as np

from src.bridge.collision_state import compute_collision_summaries
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms import create_platform
from src.bridge.platforms.types import RobotCommand, RobotRuntimeStatus, RobotState
from src.bridge.scene_builder import build_multi_robot_scene, build_two_robot_office_scene
from src.bridge.sensor_types import SensorFrame, quat_to_rotation_matrix

logger = logging.getLogger(__name__)

class MultiRobotBridge:
    """Bridge for N Go2 robots in a shared MuJoCo simulation.

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
        self._overview_renderer: Any = None
        self._step_count: int = 0
        self._dt: float = 0.0
        self._platform = create_platform(
            self._config.platform,
            **({"model_dir": self._config.model_dir} if self._config.platform == "go2" else {}),
            **self._config.platform_config,
        )
        self._qpos_starts: dict[str, int] = {}
        self._ctrl_indices: dict[str, list[int]] = {}
        self._cam_ids: dict[str, int] = {}
        self._commands: dict[str, RobotCommand] = {
            rid: RobotCommand.stand() for rid in self._config.robot_ids
        }
        self._controllers = {
            rid: self._platform.make_controller(rid) for rid in self._config.robot_ids
        }
        self._runtime_status: dict[str, RobotRuntimeStatus] = {}
        self._collision_summaries: dict[str, dict[str, int]] = {
            rid: {"collision_count": 0, "near_miss_count": 0}
            for rid in self._config.robot_ids
        }

        # Last captured frames
        self._last_frames: dict[str, SensorFrame] = {}

        # Trajectory traces for MuJoCo viewer persistence
        self._trace_positions: dict[str, list[np.ndarray]] = {
            rid: [] for rid in self._config.robot_ids
        }
        # Colors: blue for robot_a, orange for robot_b (RGBA 0-1)
        self._trace_colors: dict[str, np.ndarray] = {
            "robot_a": np.array([0.26, 0.52, 0.96, 1.0]),
            "robot_b": np.array([1.0, 0.60, 0.0, 1.0]),
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> dict[str, SensorFrame]:
        """Build the two-robot scene, load into MuJoCo, and return initial frames.

        Returns:
            Dict mapping robot_id to initial SensorFrame.
        """
        import mujoco

        self._viewer_handle = None
        self._step_count = 0

        # Generate combined XML
        if self._config.scene == "office" and self._config.platform == "go2":
            xml_str, assets = build_two_robot_office_scene(
                self._platform.metadata.model_dir,
                self._config.spawn_positions,
            )
            self._model = mujoco.MjModel.from_xml_string(xml_str, assets)
        else:
            xml_str, assets = build_multi_robot_scene(
                self._platform,
                self._config.spawn_positions,
            )
            self._model = mujoco.MjModel.from_xml_string(xml_str, assets)
        self._data = mujoco.MjData(self._model)
        self._dt = self._model.opt.timestep * self._config.sim_steps_per_frame

        # Discover per-robot indices via mj_name2id
        for robot_id in self._config.robot_ids:
            # The root body name is platform-specific and prefixed by scene_builder.
            body_name = f"{robot_id}_{self._platform.root_body_name()}"
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
            for act_name in self._platform.actuator_names():
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

        # Set initial standing pose and heading for both robots
        import math
        initial_qpos = self._platform.initial_joint_qpos()
        n_robots = len(self._config.robot_ids)
        for i, robot_id in enumerate(self._config.robot_ids):
            qstart = self._qpos_starts[robot_id]
            yaw = (2 * math.pi * i) / n_robots
            self._data.qpos[qstart + 3] = math.cos(yaw / 2)
            self._data.qpos[qstart + 4] = 0.0
            self._data.qpos[qstart + 5] = 0.0
            self._data.qpos[qstart + 6] = math.sin(yaw / 2)
            self._data.qpos[qstart + 7:qstart + 7 + len(initial_qpos)] = initial_qpos
            state = self._platform.extract_state(self._model, self._data, qstart, sim_time=0.0)
            ctrl = self._controllers[robot_id].compute(RobotCommand.stand(), state, self._dt or 0.02)
            for ctrl_i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = ctrl[ctrl_i]
            self._runtime_status[robot_id] = self._platform.runtime_status(
                robot_id,
                state,
                RobotCommand.stand(),
                self._controllers[robot_id].health(),
            )

        # Settle physics
        for _ in range(self._config.boot_phase_steps):
            mujoco.mj_step(self._model, self._data)

        # Create one renderer per robot
        w, h = self._config.resolution
        for robot_id in self._config.robot_ids:
            self._renderers[robot_id] = mujoco.Renderer(self._model, height=h, width=w)
        self._overview_renderer = mujoco.Renderer(self._model, height=h, width=w)

        # Launch interactive MuJoCo 3D viewer
        self._viewer_handle = None
        try:
            import warnings
            import mujoco.viewer
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message=".*Wayland.*")
                self._viewer_handle = mujoco.viewer.launch_passive(self._model, self._data)
            logger.info("MuJoCo interactive viewer launched")
        except Exception as e:
            logger.warning("Could not launch MuJoCo viewer: %s", e)

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

        # Apply platform controller outputs for each robot
        applied_commands: dict[str, RobotCommand] = {}
        for robot_id in self._config.robot_ids:
            status = self.get_runtime_status(robot_id)
            command = RobotCommand.stop() if status.disabled else self._commands[robot_id]
            applied_commands[robot_id] = command
            state = self._platform.extract_state(
                self._model,
                self._data,
                self._qpos_starts[robot_id],
                self._step_count * self._dt,
            )
            ctrl = self._controllers[robot_id].compute(command, state, self._dt)
            if ctrl.shape != (len(self._ctrl_indices[robot_id]),):
                raise RuntimeError(
                    f"Controller for {robot_id} returned {ctrl.shape}, expected {(len(self._ctrl_indices[robot_id]),)}"
                )
            for i, act_id in enumerate(self._ctrl_indices[robot_id]):
                self._data.ctrl[act_id] = ctrl[i]

        # Step physics
        for _ in range(self._config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

        self._step_count += 1

        # Record trajectory positions and sync viewer with traces
        for robot_id in self._config.robot_ids:
            start = self._qpos_starts[robot_id]
            pos = self._data.qpos[start : start + 3].copy()
            trace = self._trace_positions[robot_id]
            # Only record if moved enough (avoids clutter when stationary)
            if not trace or np.linalg.norm(pos - trace[-1]) > 0.05:
                trace.append(pos)

        positions = {
            rid: self._data.qpos[self._qpos_starts[rid]:self._qpos_starts[rid] + 3].copy()
            for rid in self._config.robot_ids
        }
        self._collision_summaries = compute_collision_summaries(
            positions,
            footprint_radius=self._platform.metadata.footprint_radius,
        )
        for rid in self._config.robot_ids:
            state = self._platform.extract_state(
                self._model,
                self._data,
                self._qpos_starts[rid],
                self._step_count * self._dt,
            )
            summary = self._collision_summaries[rid]
            status = self._platform.runtime_status(
                rid,
                state,
                applied_commands.get(rid, self._commands[rid]),
                self._controllers[rid].health(),
                collision_count=summary["collision_count"],
                near_miss_count=summary["near_miss_count"],
            )
            self._runtime_status[rid] = status
            if status.disabled:
                self._commands[rid] = RobotCommand.stop()

        if self._viewer_handle is not None:
            try:
                # Add trajectory trace geoms to the viewer scene
                with self._viewer_handle.lock():
                    self._viewer_handle.opt.flags[mujoco.mjtVisFlag.mjVIS_COM] = False
                    scn = self._viewer_handle.user_scn
                    scn.ngeom = 0  # clear previous custom geoms
                    for robot_id in self._config.robot_ids:
                        trace = self._trace_positions[robot_id]
                        color = self._trace_colors.get(robot_id, np.array([0.5, 0.5, 0.5, 1.0]))
                        # Draw line segments between consecutive positions
                        for i in range(len(trace) - 1):
                            if scn.ngeom >= scn.maxgeom:
                                break
                            mujoco.mjv_initGeom(
                                scn.geoms[scn.ngeom],
                                mujoco.mjtGeom.mjGEOM_CAPSULE,
                                np.zeros(3),  # size filled by connector
                                np.zeros(3),  # pos filled by connector
                                np.zeros(9),  # mat filled by connector
                                color.astype(np.float32),
                            )
                            mujoco.mjv_connector(
                                scn.geoms[scn.ngeom],
                                mujoco.mjtGeom.mjGEOM_CAPSULE,
                                0.01,  # width of the trace line
                                trace[i],
                                trace[i + 1],
                            )
                            scn.ngeom += 1
                self._viewer_handle.sync()
            except Exception:
                self._viewer_handle = None

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
        self.set_command(robot_id, RobotCommand.velocity(linear, angular))

    def set_command(self, robot_id: str, command: RobotCommand) -> None:
        if robot_id not in self._commands:
            raise KeyError(f"Unknown robot_id: {robot_id}")
        self._commands[robot_id] = command

    def stop_robot(self, robot_id: str) -> None:
        self.set_command(robot_id, RobotCommand.stop())

    def recover_robot(self, robot_id: str) -> None:
        self._controllers[robot_id].reset()
        self.set_command(robot_id, RobotCommand.recover())

    def get_runtime_status(self, robot_id: str) -> RobotRuntimeStatus:
        if robot_id in self._runtime_status:
            return self._runtime_status[robot_id]
        if robot_id not in self._commands:
            raise KeyError(f"Unknown robot_id: {robot_id}")
        return self._platform.runtime_status(
            robot_id,
            self._default_state(),
            self._commands[robot_id],
            self._controllers[robot_id].health(),
        )

    @property
    def platform_metadata(self):
        return self._platform.metadata

    @property
    def runtime_statuses(self) -> dict[str, RobotRuntimeStatus]:
        return dict(self._runtime_status)

    def get_frame(self, robot_id: str) -> SensorFrame:
        """Return the last captured frame for the specified robot.

        Args:
            robot_id: Which robot's frame to return.

        Returns:
            The most recently captured SensorFrame for that robot.
        """
        return self._last_frames[robot_id]

    def get_last_frame(self, robot_id: str) -> SensorFrame:
        return self.get_frame(robot_id)

    def stop(self) -> None:
        """Clean up MuJoCo resources."""
        for renderer in self._renderers.values():
            renderer.close()
        self._renderers.clear()
        if self._overview_renderer is not None:
            self._overview_renderer.close()
            self._overview_renderer = None
        viewer = self._viewer_handle
        self._viewer_handle = None
        if viewer is not None:
            try:
                viewer.close()
            except Exception:
                logger.debug("Viewer handle close failed (may already be closed)")
        self._model = None
        self._data = None
        self._step_count = 0

    def render_overview(self, distance: float = 8.0, elevation: float = -35.0) -> np.ndarray:
        """Render a bird's-eye overview of the scene using MuJoCo's free camera.

        The camera tracks the midpoint between both robots and looks down
        at the scene from a configurable distance and elevation angle.

        Args:
            distance: Camera distance from the lookat point in meters.
            elevation: Camera elevation angle in degrees (negative = above).

        Returns:
            (H, W, 3) uint8 RGB image of the full scene with both robots.
        """
        import mujoco

        if self._model is None or self._data is None:
            w, h = self._config.resolution
            return np.zeros((h, w, 3), dtype=np.uint8)

        # Compute midpoint between the two robots as lookat target
        positions = []
        for robot_id in self._config.robot_ids:
            start = self._qpos_starts[robot_id]
            positions.append(self._data.qpos[start : start + 3].copy())
        midpoint = np.mean(positions, axis=0)

        # Configure free camera
        cam = mujoco.MjvCamera()
        cam.type = mujoco.mjtCamera.mjCAMERA_FREE
        cam.lookat[:] = midpoint
        cam.distance = distance
        cam.elevation = elevation
        cam.azimuth = 90.0

        self._overview_renderer.update_scene(self._data, camera=cam)
        return self._overview_renderer.render().copy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _default_state(self) -> RobotState:
        try:
            return self._platform.extract_state(None, None, 0, 0.0)
        except Exception:
            pose = np.eye(4, dtype=np.float64)
            pose[:3, 3] = [0.0, 0.0, self._platform.metadata.spawn_height]
            initial_qpos = self._platform.initial_joint_qpos()
            return RobotState(
                base_pose=pose,
                base_velocity=np.zeros(3, dtype=np.float64),
                joint_positions=initial_qpos,
                joint_velocities=np.zeros_like(initial_qpos),
                orientation_quat=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64),
                contacts=(),
                sim_time=0.0,
            )

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

        # MuJoCo depth: convert based on value range
        extent = self._model.stat.extent
        znear = self._model.vis.map.znear * extent
        zfar = self._model.vis.map.zfar * extent

        if depth_raw.max() <= 1.0 + 1e-6:
            # Normalized [0,1] buffer: convert to metric
            depth = znear * zfar / (zfar - depth_raw * (zfar - znear))
            depth[depth_raw >= 0.999] = 0.0
        else:
            # Raw values already in distance units: clip far pixels to 0
            depth = depth_raw.copy()
            depth[depth_raw >= zfar * 0.99] = 0.0

        depth = np.clip(depth, 0, 20.0).astype(np.float32)  # cap at 20m

        # Pose from camera transform (not body qpos).
        # cam_xmat is R_world_from_cam (columns = camera axes in world).
        cam_id = self._cam_ids[robot_id]
        pose = np.eye(4, dtype=np.float64)
        pose[:3, 3] = self._data.cam_xpos[cam_id]
        pose[:3, :3] = self._data.cam_xmat[cam_id].reshape(3, 3)
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
        pose[:3, :3] = quat_to_rotation_matrix(quat)

        return pose

    def get_body_yaw(self, robot_id: str) -> float:
        """Extract body heading (yaw around Z) from freejoint quaternion.

        Returns:
            Yaw angle in radians.
        """
        import math
        if self._data is None:
            return 0.0
        start = self._qpos_starts[robot_id]
        qw = self._data.qpos[start + 3]
        qz = self._data.qpos[start + 6]
        return 2.0 * math.atan2(qz, qw)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._model is not None

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def robot_ids(self) -> tuple[str, ...]:
        """All robot IDs in this simulation."""
        return self._config.robot_ids

    @property
    def mj_model(self):
        """Public accessor for the MuJoCo model handle (Phase 6 BLOCKER 2 / RESEARCH Pitfall 8).

        Exposed so the coordinator bootstrap can attach the GT extractor
        (``streaming_viz.attach_gt_extractor(yaml, mj_model, mj_data)``)
        without reaching into ``self._model`` via ``# noqa: SLF001``. Returns
        ``None`` if :meth:`start` has not been called yet; callers guard with
        ``hasattr`` and a ``is not None`` check.
        """
        return self._model

    @property
    def mj_data(self):
        """Public accessor for the MuJoCo data handle (Phase 6 BLOCKER 2 / RESEARCH Pitfall 8).

        Exposed alongside :attr:`mj_model` for the GT-extractor bootstrap.
        Returns ``None`` if :meth:`start` has not been called yet.
        """
        return self._data
