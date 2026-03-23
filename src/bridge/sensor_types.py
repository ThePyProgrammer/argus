"""Shared data types and utilities for sensor frames and camera intrinsics.

These types define the interface between the simulation bridge and all
downstream consumers (SLAM pipeline, visualization, metrics).
Backend-agnostic: works with MuJoCo or any future sim.
"""


from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


# Standing joint positions from go2.xml keyframe (position-controlled).
STANDING_QPOS = np.array([
    0.0, 0.9, -1.8,   # FR: hip, thigh, calf
    0.0, 0.9, -1.8,   # FL
    0.0, 0.9, -1.8,   # RR
    0.0, 0.9, -1.8,   # RL
])


def quat_to_rotation_matrix(q: np.ndarray) -> np.ndarray:
    """Convert MuJoCo quaternion (w, x, y, z) to 3x3 rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - w*z),     2*(x*z + w*y)],
        [2*(x*y + w*z),     1 - 2*(x*x + z*z), 2*(y*z - w*x)],
        [2*(x*z - w*y),     2*(y*z + w*x),     1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


@dataclass
class SensorFrame:
    """A single timestep of sensor data from the simulation.

    Attributes:
        rgb: Color image as (H, W, 3) uint8 array (BGR from OpenCV).
        depth: Depth image as (H, W) float32 in meters, or None if unavailable.
        ground_truth_pose: 4x4 float64 homogeneous transform (world frame).
        sim_time: Simulation timestamp in seconds (computed as step_count * dt).
    """

    rgb: np.ndarray  # (H, W, 3) uint8
    depth: np.ndarray | None  # (H, W) float32 or (H, W, 3) uint8 JET; None if unavailable
    ground_truth_pose: np.ndarray  # (4, 4) float64 homogeneous transform
    sim_time: float  # simulation timestamp in seconds


@dataclass
class CameraIntrinsics:
    """Pinhole camera intrinsic parameters.

    Attributes:
        fx: Focal length in x (pixels).
        fy: Focal length in y (pixels).
        cx: Principal point x coordinate.
        cy: Principal point y coordinate.
        width: Image width in pixels.
        height: Image height in pixels.
    """

    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    @classmethod
    def from_fov(cls, width: int, height: int, fov_degrees: float = 70.0) -> "CameraIntrinsics":
        """Create intrinsics from vertical field-of-view angle."""
        import math
        fov_rad = math.radians(fov_degrees)
        fx = height / (2.0 * math.tan(fov_rad / 2.0))
        return cls(fx=fx, fy=fx, cx=width / 2.0, cy=height / 2.0, width=width, height=height)


@runtime_checkable
class BridgeProtocol(Protocol):
    """Minimal interface for a single-robot simulation bridge.

    Used by ExplorationLoop and RobotInstance. MuJoCoBridge implements
    this directly. For multi-robot scenarios, the Coordinator provides
    per-robot bridge wrappers that satisfy this protocol -- MultiRobotBridge
    itself has a different (dict-based) API and does NOT implement this protocol.
    """

    def start(self) -> SensorFrame: ...
    def step(self) -> SensorFrame: ...
    def set_velocity(self, linear: np.ndarray, angular: float) -> None: ...
    def stop(self) -> None: ...
