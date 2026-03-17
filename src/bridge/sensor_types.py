"""Shared data types for sensor frames and camera intrinsics.

These types define the interface between the SimWorld gym bridge and all
downstream consumers (SLAM pipeline, visualization, metrics).
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class SensorFrame:
    """A single timestep of sensor data from SimWorld.

    Attributes:
        rgb: Color image as (H, W, 3) uint8 array.
        depth: Depth image as (H, W) float32 array in meters.
            None if SimWorld does not provide depth (monocular fallback).
        ground_truth_pose: 4x4 float64 homogeneous transform (world frame).
        sim_time: Simulation timestamp in seconds.
    """

    rgb: np.ndarray  # (H, W, 3) uint8
    depth: np.ndarray | None  # (H, W) float32 meters, None if monocular fallback
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
