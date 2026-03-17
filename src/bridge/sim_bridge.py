"""SimWorld gym bridge -- owns the gym env handle and publishes SensorFrame data.

Bridges the SimWorld gym environment (legacy ``gym``) to typed SensorFrame
outputs consumed by SLAM, visualization, and metrics modules.

Key discoveries from Plan 01-01 (docs/simworld_discovery.md):
- SimWorld uses legacy ``gym`` (not ``gymnasium``)
- Env ID: ``simworld_gym/SimpleWorld``
- Action space: Discrete(6) -- 0-3 movement, 4-5 rotation
- Observation keys: ``rgb`` (H,W,3 uint8), ``depth`` (H,W,1 uint8 JET)
- Ground-truth pose: ``info["agent"]["agent_location"]`` (xyz in cm),
  ``info["agent"]["agent_rotation"]`` (cardinal string)
- No simulation timestamp exposed; computed as step_count * dt
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from src.bridge.env_config import SimWorldEnvConfig
from src.bridge.sensor_types import SensorFrame

logger = logging.getLogger(__name__)

# Cardinal direction string -> yaw in radians (counterclockwise from +X)
_CARDINAL_TO_YAW: dict[str, float] = {
    "North": math.pi / 2,
    "South": -math.pi / 2,
    "East": 0.0,
    "West": math.pi,
    "NorthEast": math.pi / 4,
    "NorthWest": 3 * math.pi / 4,
    "SouthEast": -math.pi / 4,
    "SouthWest": -3 * math.pi / 4,
}

# Discrete action indices (from simworld_gym action_config.json)
ACTION_MOVE_FORWARD = 0
ACTION_MOVE_BACKWARD = 1
ACTION_MOVE_LEFT = 2
ACTION_MOVE_RIGHT = 3
ACTION_TURN_RIGHT = 4
ACTION_TURN_LEFT = 5


class SimWorldGymBridge:
    """Bridge between the SimWorld gym environment and typed SensorFrame output.

    Lifecycle:
        1. ``bridge = SimWorldGymBridge(config)``
        2. ``frame = bridge.start()``   -- creates env, calls reset
        3. ``frame = bridge.step()``    -- steps env, returns SensorFrame
        4. ``bridge.set_velocity(...)`` -- buffers next action
        5. ``bridge.stop()``            -- closes env

    The bridge translates high-level velocity intentions into the discrete
    action space that SimWorld actually supports (Discrete(6): forward,
    backward, left, right, turn-right, turn-left).
    """

    def __init__(self, config: SimWorldEnvConfig | None = None) -> None:
        self._config = config or SimWorldEnvConfig()
        self._env: Any = None
        self._current_action: int = 0  # default: move forward (idle would be better but no noop)
        self._step_count: int = 0
        self._dt: float = 1.0 / self._config.target_step_hz  # simulated dt per step

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, reset_options: dict | None = None) -> SensorFrame:
        """Create the gym environment and reset it.

        Args:
            reset_options: Optional dict passed to ``env.reset(options=...)``.
                SimWorld's SimpleEnv expects ``task_path``, ``world_json``,
                ``agent_json`` keys.  If *None*, the env's built-in defaults
                are used (which may or may not work depending on SimWorld
                installation).

        Returns:
            The first SensorFrame from the environment.
        """
        try:
            import gym  # legacy gym used by SimWorld
        except ImportError:
            import gymnasium as gym  # fallback for testing without SimWorld

        env_kwargs: dict[str, Any] = {**self._config.env_kwargs}
        if self._config.observation_type:
            env_kwargs["observation_type"] = self._config.observation_type
        if self._config.render_mode is not None:
            env_kwargs["render_mode"] = self._config.render_mode

        self._env = gym.make(
            self._config.env_id,
            max_episode_steps=self._config.max_episode_steps,
            **env_kwargs,
        )
        self._step_count = 0

        if reset_options is not None:
            obs, info = self._env.reset(options=reset_options)
        else:
            obs, info = self._env.reset()

        return self._parse_observation(obs, info)

    def step(self, action: int | None = None) -> SensorFrame:
        """Step the environment with an action.

        Args:
            action: Discrete action index (0-5).  If *None*, uses the
                buffered action from the most recent ``set_velocity`` call.

        Returns:
            SensorFrame for the new observation.

        Raises:
            RuntimeError: If the bridge has not been started.
        """
        if self._env is None:
            raise RuntimeError("Bridge not started -- call start() first")

        if action is None:
            action = self._current_action

        result = self._env.step(action)
        # SimWorld step() may return 4 values (legacy gym) or 5 (gymnasium)
        if len(result) == 5:
            obs, _reward, terminated, truncated, info = result
        else:
            obs, _reward, done, info = result
            terminated = done
            truncated = False

        self._step_count += 1

        if terminated or truncated:
            logger.info("Episode ended (terminated=%s, truncated=%s) -- auto-resetting", terminated, truncated)
            obs, info = self._env.reset()
            self._step_count = 0

        return self._parse_observation(obs, info)

    def stop(self) -> None:
        """Close the gym environment and release resources."""
        if self._env is not None:
            self._env.close()
            self._env = None
        self._step_count = 0

    # ------------------------------------------------------------------
    # Velocity / action control
    # ------------------------------------------------------------------

    def set_velocity(self, linear: np.ndarray, angular: float) -> None:
        """Buffer a velocity command, translated to the nearest discrete action.

        SimWorld uses Discrete(6) actions, so continuous velocity is mapped
        to the closest discrete movement/rotation command.

        Args:
            linear: np.ndarray of shape (2,) representing [vx, vy].
                Positive vx = forward, positive vy = strafe left.
            angular: Angular velocity (positive = turn left).
        """
        # Priority: rotation commands take precedence over translation
        if abs(angular) > 0.1:
            self._current_action = ACTION_TURN_LEFT if angular > 0 else ACTION_TURN_RIGHT
            return

        vx = linear[0] if len(linear) > 0 else 0.0
        vy = linear[1] if len(linear) > 1 else 0.0

        # Pick the dominant direction
        if abs(vx) >= abs(vy):
            if abs(vx) < 0.01:
                # Near-zero velocity -- default to forward (no noop action)
                self._current_action = ACTION_MOVE_FORWARD
            elif vx > 0:
                self._current_action = ACTION_MOVE_FORWARD
            else:
                self._current_action = ACTION_MOVE_BACKWARD
        else:
            if vy > 0:
                self._current_action = ACTION_MOVE_LEFT
            else:
                self._current_action = ACTION_MOVE_RIGHT

    # ------------------------------------------------------------------
    # Observation parsing
    # ------------------------------------------------------------------

    def _parse_observation(self, obs: Any, info: dict) -> SensorFrame:
        """Convert raw gym observation + info into a typed SensorFrame.

        Uses exact keys discovered in docs/simworld_discovery.md.
        """
        # --- RGB ---
        rgb = self._extract_rgb(obs)

        # --- Depth ---
        depth = self._extract_depth(obs)

        # --- Ground-truth pose ---
        ground_truth_pose = self._extract_pose(info)

        # --- Simulation time ---
        sim_time = self._step_count * self._dt

        return SensorFrame(
            rgb=rgb,
            depth=depth,
            ground_truth_pose=ground_truth_pose,
            sim_time=sim_time,
        )

    def _extract_rgb(self, obs: Any) -> np.ndarray:
        """Extract RGB image from observation dict or raw array."""
        if isinstance(obs, dict):
            if "rgb" in obs:
                img = obs["rgb"]
                if img.dtype != np.uint8:
                    logger.warning("RGB dtype is %s, expected uint8", img.dtype)
                # Ensure (H, W, 3) -- SimWorld returns (H, W, 3) already
                if img.ndim == 3 and img.shape[2] == 3:
                    return img.astype(np.uint8)
                logger.warning("Unexpected RGB shape: %s", img.shape)
                return img.astype(np.uint8)
            else:
                available = list(obs.keys())
                logger.warning("No 'rgb' key in observation; available keys: %s", available)
                # Return a placeholder black image
                h, w = self._config.resolution[1], self._config.resolution[0]
                return np.zeros((h, w, 3), dtype=np.uint8)
        elif isinstance(obs, np.ndarray):
            # Raw array observation -- assume it is the image
            return obs.astype(np.uint8)
        else:
            logger.warning("Unexpected observation type: %s", type(obs))
            h, w = self._config.resolution[1], self._config.resolution[0]
            return np.zeros((h, w, 3), dtype=np.uint8)

    def _extract_depth(self, obs: Any) -> np.ndarray | None:
        """Extract depth from observation dict.

        NOTE: SimWorld's default pipeline returns JET-colormapped uint8
        depth, NOT raw metric depth.  For SLAM we ideally need raw float32
        depth.  This method returns whatever is available; the caller must
        handle the format difference.  A future enhancement would patch
        ``_decode_npy`` to return raw values.
        """
        if not isinstance(obs, dict):
            return None

        if "depth" not in obs:
            logger.debug("No 'depth' key in observation -- monocular fallback")
            return None

        depth_raw = obs["depth"]

        # SimWorld depth comes as (H, W, 1) uint8 -- squeeze last dim
        if depth_raw.ndim == 3 and depth_raw.shape[2] == 1:
            depth_raw = depth_raw.squeeze(axis=2)

        # If it's already float, great (means we got raw metric depth somehow)
        if np.issubdtype(depth_raw.dtype, np.floating):
            return depth_raw.astype(np.float32)

        # Otherwise it's the JET-colormapped uint8 -- return as-is with warning
        if depth_raw.ndim == 3 and depth_raw.shape[2] == 3:
            # JET colormap (H, W, 3) uint8 -- cannot do metric depth
            logger.warning(
                "Depth is JET-colormapped uint8 (H,W,3) -- not metric. "
                "SLAM depth accuracy will be limited."
            )
            return depth_raw

        # (H, W) uint8 single-channel -- could be grayscale encoded depth
        return depth_raw

    def _extract_pose(self, info: dict) -> np.ndarray:
        """Build 4x4 homogeneous transform from info dict.

        Position comes from ``info["agent"]["agent_location"]`` (Unreal cm).
        Rotation comes from cardinal direction string in
        ``info["agent"]["agent_rotation"]`` or, if available, raw
        ``[roll, pitch, yaw]`` from the agent controller.

        The position is converted from centimeters to meters.
        """
        pose = np.eye(4, dtype=np.float64)

        agent_info = info.get("agent", {})

        # --- Position ---
        location = agent_info.get("agent_location", None)
        if location is not None:
            loc = np.asarray(location, dtype=np.float64)
            # Convert Unreal centimeters to meters
            pose[:3, 3] = loc / 100.0
        else:
            logger.warning("No agent_location in info dict")

        # --- Rotation ---
        # Try raw rotation first (if SimWorld exposes it)
        raw_rotation = agent_info.get("agent_raw_rotation", None)
        if raw_rotation is not None:
            # raw_rotation expected as [roll, pitch, yaw] in degrees
            roll, pitch, yaw = np.radians(raw_rotation)
            pose[:3, :3] = self._euler_to_rotation_matrix(roll, pitch, yaw)
        else:
            # Fall back to cardinal direction string
            cardinal = agent_info.get("agent_rotation", None)
            if cardinal is not None and isinstance(cardinal, str):
                yaw = _CARDINAL_TO_YAW.get(cardinal, 0.0)
                pose[:3, :3] = self._euler_to_rotation_matrix(0.0, 0.0, yaw)
            # else: identity rotation (already set)

        return pose

    @staticmethod
    def _euler_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
        """Convert roll-pitch-yaw (radians) to 3x3 rotation matrix (ZYX convention)."""
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)

        R = np.array([
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp,     cp * sr,                cp * cr               ],
        ], dtype=np.float64)
        return R

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the gym environment is active."""
        return self._env is not None

    @property
    def step_count(self) -> int:
        """Number of steps taken since last reset."""
        return self._step_count
