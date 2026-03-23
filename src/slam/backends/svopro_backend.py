"""SVO Pro / DSO backend wrapping DSO via SubprocessSLAMBridge.

DSO (Direct Sparse Odometry) is the practical fallback for SVO Pro
(which is entangled with catkin). DSO provides monocular direct VO
with clean standalone CMake. This backend uses SubprocessSLAMBridge
for IPC with the DSO C++ harness -- the same pattern as OpenVINS.

Dense point clouds are generated from depth images using the
estimated pose (DSO itself is monocular and does not use depth).
The coordinate transform is identical to ORB-SLAM3: DSO outputs
poses in camera-optical frame (x-right, y-down, z-forward).
"""

import logging
import os

import numpy as np
import open3d as o3d

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.backends.subprocess_bridge import SubprocessSLAMBridge
from src.slam.depth_to_cloud import depth_to_pointcloud
from src.slam.protocol import SLAMResult, TrackingStatus
from src.slam.registry import slam_backend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coordinate transform: DSO camera-optical -> MuJoCo z-up world
# DSO camera-optical: x-right, y-down, z-forward (same as ORB-SLAM3)
# MuJoCo world:       x-forward, y-left, z-up
# Transform: x_mj = z_opt, y_mj = -x_opt, z_mj = -y_opt
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
# Default binary path
# ---------------------------------------------------------------------------
_DEFAULT_BINARY = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "extern", "dso_harness", "build", "dso_harness"
)


@slam_backend(name="svopro", display="SVO Pro / DSO")
class SVOProBackend:
    """SVO Pro / DSO direct visual odometry backend.

    Wraps DSO via SubprocessSLAMBridge for IPC. DSO is monocular
    (visual-only, no IMU). Dense point clouds are generated from
    depth images using the estimated pose.
    """

    CAPABILITIES: dict = {
        "supports_imu": False,
        "outputs_dense": True,
        "supports_loop_closure": False,
        "supports_stereo": False,
    }

    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "default": "mono",
                "enum": ["mono"],
                "description": "Sensor mode (DSO is monocular only)",
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
        mode: str = "mono",
        hang_timeout_ms: int = 5000,
        binary_path: str | None = None,
    ):
        self._intrinsics = intrinsics
        self._mode = mode
        self._last_pose = np.eye(4, dtype=np.float64)
        self._poses: list[np.ndarray] = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        # Ground truth offset: DSO starts its world at origin,
        # but MuJoCo robots spawn at known positions. We seed the offset
        # from the first frame's ground truth pose so the map aligns.
        self._gt_offset: np.ndarray | None = None

        # Resolve binary path
        if binary_path is None:
            binary_path = os.environ.get("DSO_BINARY", os.path.normpath(_DEFAULT_BINARY))

        self._bridge = SubprocessSLAMBridge(
            binary_path=binary_path,
            hang_timeout_ms=hang_timeout_ms,
        )
        self._bridge.start()

    # ------------------------------------------------------------------
    # SLAMProtocol interface
    # ------------------------------------------------------------------

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one frame via DSO subprocess, return SLAMResult with dense cloud."""
        # Seed ground truth offset from first frame
        if self._gt_offset is None and frame.ground_truth_pose is not None:
            self._gt_offset = frame.ground_truth_pose.copy()

        # Send frame to DSO subprocess -- NO imu_readings (DSO is visual-only)
        bridge_result = self._bridge.send_frame(
            frame.rgb, frame.depth, frame.sim_time
        )

        # Subprocess crashed or hung
        if bridge_result is None:
            if self._num_frames == 0 and self._gt_offset is not None:
                self._last_pose = self._gt_offset.copy()
            return SLAMResult(
                pose=self._last_pose.copy(),
                points=np.empty((0, 3), dtype=np.float64),
                colors=np.empty((0, 3), dtype=np.float64),
                metrics={"tracking_status_raw": "lost"},
                tracking_status=TrackingStatus.LOST,
            )

        # Check for lost tracking from subprocess
        if bridge_result.tracking_status == TrackingStatus.LOST:
            return SLAMResult(
                pose=self._last_pose.copy(),
                points=np.empty((0, 3), dtype=np.float64),
                colors=np.empty((0, 3), dtype=np.float64),
                metrics=bridge_result.metrics,
                tracking_status=TrackingStatus.LOST,
            )

        # Apply coordinate transform (DSO optical frame -> MuJoCo frame)
        raw_pose = bridge_result.pose
        pose = T_MUJOCO_FROM_OPTICAL @ raw_pose

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

        # Accumulate into global cloud
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
            metrics=bridge_result.metrics,
            tracking_status=TrackingStatus.OK,
        )

    def reset(self) -> None:
        """Clear all accumulated state and restart DSO subprocess."""
        self._poses = []
        self._global_points = np.empty((0, 3), dtype=np.float64)
        self._global_colors = np.empty((0, 3), dtype=np.float64)
        self._num_frames = 0
        self._last_pose = np.eye(4, dtype=np.float64)
        self._gt_offset = None

        self._bridge.shutdown()
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
