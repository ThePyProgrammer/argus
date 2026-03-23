"""ICP odometry backend wrapping the existing SLAMPipeline.

This backend delegates all heavy lifting to SLAMPipeline and wraps
results in the standard SLAMResult container. It serves as the baseline
backend and proves that the abstraction layer works with zero behavioral
regression.
"""

import numpy as np

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.slam.protocol import SLAMResult, TrackingStatus
from src.slam.registry import slam_backend
from src.slam.slam_pipeline import SLAMPipeline


@slam_backend(name="icp", display="ICP Odometry")
class ICPBackend:
    """ICP-based SLAM backend wrapping SLAMPipeline.

    Provides the same point-to-point ICP odometry as before, but through
    the standard SLAMProtocol interface so it can be swapped with other
    backends (ORB-SLAM3, OpenVINS, etc.) without changing caller code.
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
            "voxel_size": {
                "type": "number",
                "default": 0.03,
                "minimum": 0.01,
                "maximum": 0.2,
                "description": "Voxel size for downsampling (meters)",
                "live_tunable": False,
            },
            "max_cloud_points": {
                "type": "integer",
                "default": 500000,
                "minimum": 10000,
                "maximum": 5000000,
                "description": "Maximum accumulated cloud points before aggressive downsampling",
                "live_tunable": False,
            },
        },
    }

    def __init__(self, intrinsics: CameraIntrinsics, voxel_size: float = 0.03):
        self._pipeline = SLAMPipeline(intrinsics, voxel_size=voxel_size)

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one RGB-D frame via ICP, return SLAMResult."""
        pose = self._pipeline.process_frame(frame)
        return SLAMResult(
            pose=pose,
            points=self._pipeline.last_frame_cloud.copy(),
            colors=self._pipeline._last_frame_colors.copy(),
            metrics={"fitness": 1.0},
            tracking_status=TrackingStatus.OK,
        )

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._pipeline.reset()

    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        """Return accumulated (points, colors) from the global cloud."""
        return self._pipeline.get_cloud_points(), self._pipeline.get_cloud_colors()

    def get_poses(self) -> list[np.ndarray]:
        """Return list of estimated (4,4) poses."""
        return self._pipeline.slam_poses

    @property
    def num_frames_processed(self) -> int:
        """Number of frames processed so far."""
        return self._pipeline.num_frames_processed
