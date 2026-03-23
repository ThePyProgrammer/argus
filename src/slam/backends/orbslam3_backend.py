"""ORB-SLAM3 backend wrapping orbslam3-python.

This backend wraps the orbslam3-python binding to provide feature-based
visual SLAM through the standard SLAMProtocol interface. Dense point
clouds are generated from depth images (not sparse ORB features) to
match the project convention (BACK-02).

When orbslam3-python is not installed, the module sets _ORBSLAM3_AVAILABLE
to False and the constructor raises ImportError. The backend stays
unregistered if the decorator never fires on an importable class.
"""

import atexit
import logging
import os
import tempfile

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.depth_to_cloud import depth_to_pointcloud
from src.slam.protocol import SLAMResult, TrackingStatus
from src.slam.registry import slam_backend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency gate
# ---------------------------------------------------------------------------
try:
    import orbslam3  # type: ignore[import-untyped]

    _ORBSLAM3_AVAILABLE = True
except ImportError:
    _ORBSLAM3_AVAILABLE = False

# ---------------------------------------------------------------------------
# Coordinate transform: ORB-SLAM3 camera-optical -> MuJoCo z-up world
# ---------------------------------------------------------------------------
T_MUJOCO_FROM_OPTICAL = np.array(
    [
        [0, 0, 1, 0],
        [-1, 0, 0, 0],
        [0, -1, 0, 0],
        [0, 0, 0, 1],
    ],
    dtype=np.float64,
)

# ---------------------------------------------------------------------------
# Default vocab path (relative to project root)
# ---------------------------------------------------------------------------
_DEFAULT_VOCAB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "models", "orbslam3", "ORBvoc.txt"
)


@slam_backend(name="orbslam3", display="ORB-SLAM3")
class ORBSlam3Backend:
    """ORB-SLAM3 feature-based SLAM backend.

    Wraps orbslam3-python's System class. Generates dense point clouds
    from depth images using the estimated pose, with sparse ORB feature
    count available in SLAMResult.metrics.

    Supports both RGBD and monocular modes via the ``mode`` parameter.
    """

    CAPABILITIES: dict = {
        "supports_imu": False,
        "outputs_dense": True,
        "supports_loop_closure": True,
        "supports_stereo": False,
    }

    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "nFeatures": {
                "type": "integer",
                "default": 1000,
                "minimum": 100,
                "maximum": 5000,
                "description": "Number of ORB features per frame",
                "live_tunable": False,
            },
            "scaleFactor": {
                "type": "number",
                "default": 1.2,
                "minimum": 1.01,
                "maximum": 2.0,
                "description": "Scale factor between pyramid levels",
                "live_tunable": False,
            },
            "nLevels": {
                "type": "integer",
                "default": 8,
                "minimum": 1,
                "maximum": 16,
                "description": "Number of pyramid levels",
                "live_tunable": False,
            },
            "mode": {
                "type": "string",
                "default": "rgbd",
                "enum": ["rgbd", "monocular"],
                "description": "Sensor mode: rgbd or monocular",
                "live_tunable": False,
            },
        },
    }

    def __init__(
        self,
        intrinsics: CameraIntrinsics,
        nFeatures: int = 1000,
        scaleFactor: float = 1.2,
        nLevels: int = 8,
        mode: str = "rgbd",
        vocab_path: str | None = None,
    ):
        if not _ORBSLAM3_AVAILABLE:
            raise ImportError(
                "orbslam3-python is not installed. Install it or use a different backend."
            )

        self._intrinsics = intrinsics
        self._mode = mode
        self._nFeatures = nFeatures
        self._scaleFactor = scaleFactor
        self._nLevels = nLevels
        self._last_pose = np.eye(4, dtype=np.float64)
        self._poses: list[np.ndarray] = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        self._config_path: str | None = None

        # Resolve vocab path
        if vocab_path is None:
            vocab_path = os.path.normpath(_DEFAULT_VOCAB_PATH)
        if not os.path.isfile(vocab_path):
            raise FileNotFoundError(
                f"ORB-SLAM3 vocabulary not found at {vocab_path}. "
                "Run: bash scripts/download_orbslam3_vocab.sh"
            )
        self._vocab_path = vocab_path

        # Write ORB-SLAM3 config YAML
        self._write_config()

        # Select sensor type
        sensor_enum = (
            orbslam3.Sensor.MONOCULAR if mode == "monocular" else orbslam3.Sensor.RGBD
        )

        # Create and initialize ORB-SLAM3 system
        self._slam = orbslam3.System(self._vocab_path, self._config_path, sensor_enum)
        self._slam.set_use_viewer(False)
        self._slam.initialize()

        atexit.register(self._cleanup_config)

    # ------------------------------------------------------------------
    # SLAMProtocol interface
    # ------------------------------------------------------------------

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one frame via ORB-SLAM3, return SLAMResult with dense cloud."""
        # Feed frame to ORB-SLAM3
        if self._mode == "monocular":
            self._slam.process_image_mono(frame.rgb, frame.sim_time)
        else:
            self._slam.process_image_rgbd(frame.rgb, frame.depth, frame.sim_time)

        # Get estimated pose
        raw_pose = self._slam.get_frame_pose()

        # Check for lost tracking
        if raw_pose is None:
            return SLAMResult(
                pose=self._last_pose.copy(),
                points=np.empty((0, 3), dtype=np.float64),
                colors=np.empty((0, 3), dtype=np.float64),
                metrics={"sparse_feature_count": 0, "tracking_status_raw": "lost"},
                tracking_status=TrackingStatus.LOST,
            )

        # Apply coordinate transform
        pose = self._convert_pose(raw_pose)
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

        # Get sparse feature count
        sparse_points = self._slam.get_current_points()
        sparse_count = len(sparse_points) if sparse_points else 0

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
                "sparse_feature_count": sparse_count,
                "tracking_status_raw": "ok",
            },
            tracking_status=TrackingStatus.OK,
        )

    def reset(self) -> None:
        """Clear all accumulated state and reinitialize ORB-SLAM3."""
        self._poses = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        self._last_pose = np.eye(4, dtype=np.float64)

        # Shutdown and reinitialize
        try:
            self._slam.shutdown()
        except Exception:
            pass

        self._cleanup_config()
        self._write_config()

        sensor_enum = (
            orbslam3.Sensor.MONOCULAR
            if self._mode == "monocular"
            else orbslam3.Sensor.RGBD
        )
        self._slam = orbslam3.System(self._vocab_path, self._config_path, sensor_enum)
        self._slam.set_use_viewer(False)
        self._slam.initialize()

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

    def _convert_pose(self, orbslam_pose: np.ndarray) -> np.ndarray:
        """Apply T_MUJOCO_FROM_OPTICAL to convert ORB-SLAM3 pose to MuJoCo frame."""
        return T_MUJOCO_FROM_OPTICAL @ orbslam_pose

    def _write_config(self) -> None:
        """Generate ORB-SLAM3 YAML config from camera intrinsics."""
        config_content = f"""%YAML:1.0

# ORB-SLAM3 configuration (auto-generated)

Camera.type: "PinHole"
Camera.fx: {self._intrinsics.fx}
Camera.fy: {self._intrinsics.fy}
Camera.cx: {self._intrinsics.cx}
Camera.cy: {self._intrinsics.cy}

Camera.k1: 0.0
Camera.k2: 0.0
Camera.p1: 0.0
Camera.p2: 0.0

Camera.width: {self._intrinsics.width}
Camera.height: {self._intrinsics.height}

Camera.fps: 30.0
Camera.RGB: 1

DepthMapFactor: 1.0

ORBextractor.nFeatures: {self._nFeatures}
ORBextractor.scaleFactor: {self._scaleFactor}
ORBextractor.nLevels: {self._nLevels}
ORBextractor.iniThFAST: 20
ORBextractor.minThFAST: 7

Viewer.KeyFrameSize: 0.05
Viewer.KeyFrameLineWidth: 1
Viewer.GraphLineWidth: 0.9
Viewer.PointSize: 2
Viewer.CameraSize: 0.08
Viewer.CameraLineWidth: 3
Viewer.ViewpointX: 0
Viewer.ViewpointY: -0.7
Viewer.ViewpointZ: -1.8
Viewer.ViewpointF: 500
"""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", prefix="orbslam3_", delete=False
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
