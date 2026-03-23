"""OpenVINS visual-inertial SLAM backend via subprocess bridge.

This backend wraps the OpenVINS VioManager C++ binary through the
SubprocessSLAMBridge. It accepts RGB frames + IMU data and produces
pose estimates. Dense point clouds are generated from depth images
(not native OpenVINS sparse features) using depth_to_pointcloud.

When the openvins_harness binary is not found and OPENVINS_BINARY
env var is not set, the module sets _OPENVINS_AVAILABLE to False
and the constructor raises ImportError.
"""

import logging
import os
import tempfile

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.backends.subprocess_bridge import SubprocessSLAMBridge
from src.slam.depth_to_cloud import depth_to_pointcloud
from src.slam.protocol import SLAMResult, TrackingStatus
from src.slam.registry import slam_backend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency gate
# ---------------------------------------------------------------------------
_DEFAULT_BINARY = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "extern", "openvins_harness", "build", "openvins_harness"
)
_DEFAULT_BINARY = os.path.normpath(_DEFAULT_BINARY)

_OPENVINS_BINARY = os.environ.get("OPENVINS_BINARY", "")
_OPENVINS_AVAILABLE = bool(_OPENVINS_BINARY) or os.path.isfile(_DEFAULT_BINARY)

# ---------------------------------------------------------------------------
# Coordinate transform: OpenVINS FLU -> MuJoCo world
# OpenVINS FLU: x-forward, y-left, z-up
# MuJoCo:       x-forward, y-left, z-up (when robot faces +x)
# These are the SAME convention if robot starts facing +x.
# GT offset handles any starting orientation mismatch.
# ---------------------------------------------------------------------------
T_MUJOCO_FROM_FLU = np.eye(4, dtype=np.float64)


@slam_backend(name="openvins", display="OpenVINS (VIO)")
class OpenVINSBackend:
    """OpenVINS visual-inertial SLAM backend.

    Wraps the OpenVINS C++ harness via SubprocessSLAMBridge. Generates
    dense point clouds from depth images using the estimated pose, with
    IMU data forwarded to the subprocess for visual-inertial fusion.

    The harness binary must be built from extern/openvins_harness/ or
    specified via the OPENVINS_BINARY environment variable.
    """

    CAPABILITIES: dict = {
        "supports_imu": True,
        "outputs_dense": True,  # via depth_to_pointcloud
        "supports_loop_closure": False,
        "supports_stereo": False,
    }

    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "max_cameras": {
                "type": "integer",
                "default": 1,
                "minimum": 1,
                "maximum": 4,
                "description": "Number of cameras to use",
                "live_tunable": False,
            },
            "num_pts": {
                "type": "integer",
                "default": 200,
                "minimum": 50,
                "maximum": 500,
                "description": "Max number of tracked features",
                "live_tunable": False,
            },
            "hang_timeout_ms": {
                "type": "integer",
                "default": 5000,
                "minimum": 1000,
                "maximum": 30000,
                "description": "Subprocess hang timeout in milliseconds",
                "live_tunable": False,
            },
        },
    }

    def __init__(
        self,
        intrinsics: CameraIntrinsics,
        max_cameras: int = 1,
        num_pts: int = 200,
        hang_timeout_ms: int = 5000,
    ):
        if not _OPENVINS_AVAILABLE:
            raise ImportError(
                "OpenVINS harness binary not found. Build it from "
                "extern/openvins_harness/ or set OPENVINS_BINARY env var."
            )

        self._intrinsics = intrinsics
        self._max_cameras = max_cameras
        self._num_pts = num_pts
        self._hang_timeout_ms = hang_timeout_ms
        self._last_pose = np.eye(4, dtype=np.float64)
        self._poses: list[np.ndarray] = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        self._config_path: str | None = None
        # Ground truth offset: OpenVINS starts its world at origin,
        # but MuJoCo robots spawn at known positions. We seed the offset
        # from the first frame's ground truth pose so the map aligns.
        self._gt_offset: np.ndarray | None = None

        # Resolve binary path
        self._binary = _OPENVINS_BINARY or _DEFAULT_BINARY

        # Write OpenVINS config YAML
        self._write_config()

        # Create and start subprocess bridge
        self._bridge = SubprocessSLAMBridge(
            binary_path=self._binary,
            args=["--config", self._config_path],
            hang_timeout_ms=self._hang_timeout_ms,
        )
        self._bridge.start()

    # ------------------------------------------------------------------
    # SLAMProtocol interface
    # ------------------------------------------------------------------

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one frame via OpenVINS subprocess, return SLAMResult with dense cloud."""
        # Seed ground truth offset from first frame so OpenVINS's world
        # frame aligns with MuJoCo's world frame (robots spawn at known pos).
        if self._gt_offset is None and frame.ground_truth_pose is not None:
            self._gt_offset = frame.ground_truth_pose.copy()

        # Send frame to subprocess with IMU readings
        bridge_result = self._bridge.send_frame(
            frame.rgb, frame.depth, frame.sim_time, frame.imu_readings
        )

        # Handle subprocess crash/timeout or not-yet-tracking
        if bridge_result is None:
            if self._num_frames == 0 and self._gt_offset is not None:
                # During initialization, use ground truth so robot is visible
                self._last_pose = self._gt_offset.copy()
            return SLAMResult(
                pose=self._last_pose.copy(),
                points=np.empty((0, 3), dtype=np.float64),
                colors=np.empty((0, 3), dtype=np.float64),
                metrics={"tracking_status_raw": "lost" if self._num_frames > 0 else "initializing"},
                tracking_status=TrackingStatus.INITIALIZING if self._num_frames == 0 else TrackingStatus.LOST,
            )

        # Apply coordinate transform (FLU -> MuJoCo, identity if conventions match)
        pose = T_MUJOCO_FROM_FLU @ bridge_result.pose

        # Apply ground truth offset so map is in MuJoCo world coordinates
        if self._gt_offset is not None:
            pose = self._gt_offset @ pose
        self._last_pose = pose.copy()
        self._poses.append(pose.copy())
        self._num_frames += 1

        # Generate dense point cloud from depth image
        pcd = depth_to_pointcloud(frame.depth, frame.rgb, self._intrinsics)
        frame_points = np.asarray(pcd.points, dtype=np.float64)
        frame_colors = np.asarray(pcd.colors, dtype=np.float64)

        # Transform points to world frame
        if len(frame_points) > 0:
            ones = np.ones((len(frame_points), 1), dtype=np.float64)
            pts_h = np.hstack([frame_points, ones])  # (N, 4)
            world_pts = (pose @ pts_h.T).T[:, :3]
            frame_points = world_pts

        # Accumulate into global cloud (copy to prevent mutable reference bugs)
        if len(frame_points) > 0:
            self._global_points = np.vstack(
                [self._global_points, frame_points.copy()]
            )
            self._global_colors = np.vstack(
                [self._global_colors, frame_colors.copy()]
            )

        return SLAMResult(
            pose=pose,
            points=frame_points.copy(),
            colors=frame_colors.copy(),
            metrics={
                "processing_time_ms": bridge_result.metrics.get("processing_time_ms", 0),
                "tracking_status_raw": "ok",
            },
            tracking_status=TrackingStatus.OK,
        )

    def reset(self) -> None:
        """Clear all accumulated state and restart the subprocess bridge."""
        self._poses = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        self._last_pose = np.eye(4, dtype=np.float64)
        self._gt_offset = None

        # Shutdown existing bridge
        try:
            self._bridge.shutdown()
        except Exception:
            pass

        # Clean up and rewrite config
        self._cleanup_config()
        self._write_config()

        # Create and start new bridge
        self._bridge = SubprocessSLAMBridge(
            binary_path=self._binary,
            args=["--config", self._config_path],
            hang_timeout_ms=self._hang_timeout_ms,
        )
        self._bridge.start()

    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        """Return accumulated (points, colors) as (Nx3, Nx3) arrays."""
        return self._global_points.copy(), self._global_colors.copy()

    def get_poses(self) -> list[np.ndarray]:
        """Return list of estimated (4,4) poses, one per processed frame."""
        return list(self._poses)

    @property
    def num_frames_processed(self) -> int:
        """Number of frames processed so far."""
        return self._num_frames

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write_config(self) -> None:
        """Generate OpenVINS YAML config from camera intrinsics and params."""
        config_content = f"""# OpenVINS configuration (auto-generated)
# Camera intrinsics
cam0_wh: [{self._intrinsics.width}, {self._intrinsics.height}]
cam0_k: [{self._intrinsics.fx}, 0.0, {self._intrinsics.cx}, 0.0, {self._intrinsics.fy}, {self._intrinsics.cy}, 0.0, 0.0, 1.0]
cam0_d: [0.0, 0.0, 0.0, 0.0]
cam0_is_fisheye: false

# Number of cameras and features
max_cameras: {self._max_cameras}
num_pts: {self._num_pts}

# IMU noise parameters (very small for simulation data, per RESEARCH.md pitfall 3)
gyroscope_noise_density: 1.0e-6
accelerometer_noise_density: 1.0e-5
gyroscope_random_walk: 1.0e-8
accelerometer_random_walk: 1.0e-7

# Camera-IMU extrinsics (identity for co-located sim sensors)
T_imu_cam0: [1.0, 0.0, 0.0, 0.0,
              0.0, 1.0, 0.0, 0.0,
              0.0, 0.0, 1.0, 0.0,
              0.0, 0.0, 0.0, 1.0]

# Feature tracking
use_stereo: false
use_klt: true
"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="openvins_", delete=False
        )
        tmp.write(config_content)
        tmp.close()
        self._config_path = tmp.name

    def _cleanup_config(self) -> None:
        """Remove temporary YAML config file if it exists."""
        if self._config_path and os.path.isfile(self._config_path):
            try:
                os.unlink(self._config_path)
            except OSError:
                pass
