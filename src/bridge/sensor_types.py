"""Shared data types for sensor frames and camera intrinsics.

These types define the interface between the simulation bridge and all
downstream consumers (SLAM pipeline, visualization, metrics).
Backend-agnostic: works with MuJoCo, SimWorld, or any future sim.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class SensorFrame:
    """A single timestep of sensor data from SimWorld.

    Discovered from SimWorld source (2026-03-17):
    - RGB comes from UnrealCV ``lit`` viewmode as PNG-decoded (H, W, 3) uint8 BGR.
    - Depth comes from UnrealCV ``depth`` viewmode as npy then log-normalized
      to uint8 with JET colormap applied (H, W, 3) uint8 -- NOT raw meters.
      To get metric depth, the bridge must request raw npy BEFORE the
      ``_decode_npy`` normalization step.
    - Ground-truth pose: ``info["agent"]["agent_location"]`` is np.array([x, y, z])
      in Unreal world units (cm). ``info["agent"]["agent_rotation"]`` is a
      cardinal direction string.  Raw rotation is [roll, pitch, yaw] degrees
      available via ``agent_controller._agent_rotation``.
    - No simulation timestamp is provided; must use step count * dt.

    Attributes:
        rgb: Color image as (H, W, 3) uint8 array (BGR from OpenCV).
        depth: Depth image.  Ideally (H, W) float32 in Unreal depth units
            from raw npy before normalization.  If only the default pipeline
            is available, this will be (H, W, 3) uint8 JET colormap.
            None if observation_type does not include depth.
        ground_truth_pose: 4x4 float64 homogeneous transform (world frame).
            Constructed from agent_location (cm) and agent_rotation (degrees).
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

    fx: float  # focal length x (pixels)
    fy: float  # focal length y (pixels)
    cx: float  # principal point x
    cy: float  # principal point y
    width: int
    height: int
