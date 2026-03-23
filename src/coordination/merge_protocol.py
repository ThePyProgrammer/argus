"""Merge strategy protocol and shared result types.

Defines the contract that all merge strategies must satisfy, plus the
standard result container and per-robot input data type.

Mirrors src/slam/protocol.py pattern: runtime_checkable Protocol with
class-level CAPABILITIES and PARAMETER_SCHEMA.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import open3d as o3d


@dataclass
class RobotMapData:
    """Per-robot input to merge strategies.

    Attributes:
        robot_id: Unique identifier for the robot.
        poses: List of (4, 4) float64 homogeneous transforms (one per frame).
        frame_clouds: List of (N, 3) float64 point arrays per frame.
        current_voxels: (M, 3) float64 currently occupied voxel centers.
    """

    robot_id: str
    poses: list[np.ndarray]
    frame_clouds: list[np.ndarray]
    current_voxels: np.ndarray


@dataclass
class MergeResult:
    """Standard return type from MergeProtocol.merge().

    Attributes:
        merged_voxels: (N, 3) float64 deduplicated merged voxel centers.
        merged_cloud: Open3D PointCloud of the merged map.
        optimized_poses: Dict mapping robot_id -> list of (4, 4) transforms.
        metrics: Strategy-specific quality/timing metrics.
    """

    merged_voxels: np.ndarray
    merged_cloud: o3d.geometry.PointCloud
    optimized_poses: dict[str, list[np.ndarray]]
    metrics: dict = field(default_factory=dict)


@runtime_checkable
class MergeProtocol(Protocol):
    """Interface that all merge strategies must implement.

    Mirrors SLAMProtocol pattern: runtime_checkable so callers can verify
    at startup that a strategy satisfies the contract.

    Class attributes:
        CAPABILITIES: Dict describing strategy capabilities
            (e.g. supports_loop_closure, incremental).
        PARAMETER_SCHEMA: JSON-Schema-like dict describing tunable parameters.
    """

    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def merge(self, robot_data: dict[str, RobotMapData]) -> MergeResult:
        """Merge maps from multiple robots into a unified result."""
        ...

    def reset(self) -> None:
        """Clear all accumulated merge state."""
        ...

    @property
    def last_merged_voxels(self) -> np.ndarray:
        """Most recently merged voxel array."""
        ...

    @property
    def last_merged_cloud(self) -> o3d.geometry.PointCloud:
        """Most recently merged point cloud."""
        ...
