"""SLAM backend protocol and shared result types.

Defines the contract that all SLAM backends must satisfy, plus the
standard result container and tracking status enum.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np

from src.bridge.sensor_types import SensorFrame


class TrackingStatus(Enum):
    """Current tracking state of a SLAM backend."""

    OK = "ok"
    LOST = "lost"
    INITIALIZING = "initializing"
    RELOCALIZING = "relocalizing"


@dataclass
class SLAMResult:
    """Standard return type from SLAMProtocol.process_frame().

    Attributes:
        pose: (4, 4) float64 homogeneous transform in world frame.
        points: (N, 3) float64 frame point cloud in world frame.
        colors: (N, 3) float64 frame point cloud colors (0-1 range).
        metrics: Backend-specific timing/quality metrics.
        tracking_status: Current tracking state.
    """

    pose: np.ndarray
    points: np.ndarray
    colors: np.ndarray
    metrics: dict = field(default_factory=dict)
    tracking_status: TrackingStatus = TrackingStatus.OK


@runtime_checkable
class SLAMProtocol(Protocol):
    """Interface that all SLAM backends must implement.

    Mirrors the BridgeProtocol pattern: runtime_checkable so callers
    can verify at startup that a backend satisfies the contract.

    Class attributes:
        CAPABILITIES: Dict describing what the backend supports
            (e.g. supports_imu, outputs_dense, supports_loop_closure).
        PARAMETER_SCHEMA: JSON-Schema-like dict describing tunable parameters.
    """

    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def process_frame(self, frame: SensorFrame) -> SLAMResult:
        """Process one RGB-D frame, return pose + cloud + metrics."""
        ...

    def reset(self) -> None:
        """Clear all accumulated state for a fresh start."""
        ...

    def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
        """Return accumulated (points, colors) as (Nx3, Nx3) arrays."""
        ...

    def get_poses(self) -> list[np.ndarray]:
        """Return list of estimated (4,4) poses, one per processed frame."""
        ...

    @property
    def num_frames_processed(self) -> int:
        """Number of frames processed so far."""
        ...
