"""Project 2D YOLO detections onto 3D point cloud.

Takes 2D bounding boxes from YOLO and depth images, computes median
depth within each bbox, then projects the bbox center to 3D using
camera intrinsics and the camera's world pose.

This gives each detected object a world-frame 3D position that can
be displayed as a label in the web UI's 3D viewer.
"""


import numpy as np

from src.bridge.sensor_types import CameraIntrinsics


def project_detections_to_3d(
    detections: list[dict],
    depth: np.ndarray,
    intrinsics: CameraIntrinsics,
    pose: np.ndarray,
) -> list[dict]:
    """Add 3D world positions to 2D detections using depth.

    Args:
        detections: List of detection dicts with 'bbox' [x1,y1,x2,y2].
        depth: (H, W) float32 depth image in meters.
        intrinsics: Camera intrinsic parameters.
        pose: (4, 4) camera-to-world transform.

    Returns:
        Same detections with 'pos_3d' field added/updated.
    """
    h, w = depth.shape

    for det in detections:
        bbox = det.get("bbox")
        if bbox is None or len(bbox) != 4:
            continue

        x1, y1, x2, y2 = bbox
        # Clamp to image bounds
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w - 1))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h - 1))

        if x2 <= x1 or y2 <= y1:
            continue

        # Get median depth in the bbox (robust to outliers)
        roi = depth[y1:y2, x1:x2]
        valid = roi[(roi > 0.1) & (roi < 10.0)]

        if len(valid) == 0:
            continue

        median_depth = float(np.median(valid))

        # Project bbox center to 3D
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0

        # Camera frame point (using intrinsics)
        cam_x = (cx - intrinsics.cx) * median_depth / intrinsics.fx
        cam_y = (cy - intrinsics.cy) * median_depth / intrinsics.fy

        # Apply same Y/Z flip as depth_to_cloud config
        from src.bridge.cloud_config import CLOUD_CONFIGS, get_active_config
        cfg = CLOUD_CONFIGS[get_active_config()]
        cam_point = np.array([
            cfg["fy"] * cam_x if cfg.get("sx") is not None else cam_x,
            cfg["fy"] * cam_y,
            cfg["fz"] * median_depth,
        ])

        # Transform to world using camera pose
        world_point = pose[:3, :3] @ cam_point + pose[:3, 3]

        det["pos_3d"] = world_point.tolist()
        det["depth"] = round(median_depth, 2)

    return detections
