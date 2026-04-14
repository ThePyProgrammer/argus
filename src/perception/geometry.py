"""Single projection entrypoint per DET-3D-06 / CONTEXT D-05, D-06.

Stateless pinhole unprojection. No FOV constants; callers pass CameraIntrinsics.
Per D-06, this module MUST be the only place in src/perception/ that mentions
focal length / FOV in executable code. Docstrings may reference these concepts.

The camera-frame sign flip (cam_pt = [cam_x, -cam_y, -depth]) is preserved
verbatim from src/perception/lifters/median_depth.py:96-97 to match MuJoCo's
OpenCV-optical convention (+x right, +y DOWN, +z INTO scene). Changing this
sign flip breaks MuJoCo-authored poses and the Plan 07 SC#1 integration test.

Pitfall 10: this module must NOT import src.bridge.cloud_config. That file
is SLAM-owned; its axis flips belong to a different trust/semantic boundary.
"""
from __future__ import annotations

import numpy as np

from src.bridge.sensor_types import CameraIntrinsics


def unproject_pixel_to_world(
    u: float,
    v: float,
    depth: float,
    intrinsics: CameraIntrinsics,
    pose: np.ndarray,
) -> np.ndarray:
    """Unproject one pixel (u, v, depth_m) into the world frame.

    Convention matches the legacy median_depth.py sign flip for MuJoCo camera
    frame (OpenCV optical: +x right, +y DOWN, +z INTO scene). The cam frame
    point is (cam_x, -cam_y, -depth) before applying the pose R * p + t.
    """
    fx, fy, cx, cy = intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy
    cam_x = (u - cx) * depth / fx
    cam_y = (v - cy) * depth / fy
    cam_pt = np.array([cam_x, -cam_y, -depth], dtype=np.float64)
    return pose[:3, :3] @ cam_pt + pose[:3, 3]


def unproject_pixels_batched(
    uvs: np.ndarray,
    depths: np.ndarray,
    intrinsics: CameraIntrinsics,
    pose: np.ndarray,
) -> np.ndarray:
    """Vectorized unprojection. uvs: (N, 2) float; depths: (N,) float. Returns (N, 3)."""
    fx, fy, cx, cy = intrinsics.fx, intrinsics.fy, intrinsics.cx, intrinsics.cy
    u = uvs[:, 0]
    v = uvs[:, 1]
    cam_x = (u - cx) * depths / fx
    cam_y = (v - cy) * depths / fy
    cam_pts = np.stack([cam_x, -cam_y, -depths], axis=1)           # (N, 3)
    world_pts = cam_pts @ pose[:3, :3].T + pose[:3, 3]             # (N, 3)
    return world_pts
