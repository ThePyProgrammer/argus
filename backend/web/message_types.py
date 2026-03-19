"""WebSocket message types, binary protocols, and color utilities.

Defines the Pydantic message envelope, message type constants,
Okabe-Ito color palette, camera frame binary encoding, and
delta point cloud tracking for the C2 web interface.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

# ---- Message type literals ----
ROBOT_LIST = "robot_list"
POSE_UPDATE = "pose_update"
CLOUD_DELTA = "cloud_delta"
CLOUD_FULL = "cloud_full"
CAMERA_FRAME = "camera_frame"
STATS = "stats"
COMMAND = "command"
TRAJECTORY = "trajectory"


class WSMessage(BaseModel):
    """Envelope for all JSON WebSocket messages.

    Attributes:
        type: Message type literal (e.g. "robot_list", "pose_update").
        robot_id: Optional robot identifier for per-robot messages.
        payload: Message-specific data as dict or list.
    """

    type: str
    robot_id: str | None = None
    payload: dict | list


# ---- Okabe-Ito colorblind-friendly palette (8 colors) ----
OKABE_ITO_PALETTE: list[tuple[int, int, int]] = [
    (0, 114, 178),    # blue
    (230, 159, 0),    # orange
    (86, 180, 233),   # sky blue
    (0, 158, 115),    # bluish green
    (240, 228, 66),   # yellow
    (213, 94, 0),     # vermilion
    (204, 121, 167),  # reddish purple
    (0, 0, 0),        # black
]


def color_for_robot(index: int) -> tuple[int, int, int]:
    """Return Okabe-Ito palette color for robot index (wraps at 8).

    Args:
        index: Zero-based robot index.

    Returns:
        RGB tuple (0-255 per channel).
    """
    return OKABE_ITO_PALETTE[index % 8]


def encode_camera_frame(
    robot_id: str, rgb: np.ndarray, quality: int = 70
) -> bytes:
    """Encode RGB image as JPEG with binary protocol header.

    Binary layout: [0x01][id_len: 1 byte][robot_id ASCII][JPEG bytes]

    Args:
        robot_id: Robot identifier string.
        rgb: (H, W, 3) uint8 image array.
        quality: JPEG compression quality (0-100).

    Returns:
        bytes with header + JPEG payload.
    """
    import cv2

    # MuJoCo camera xyaxes="0 -1 0 0 0 1" produces a rotated image;
    # rotate 90° clockwise to get the natural orientation
    rgb_rotated = cv2.rotate(rgb, cv2.ROTATE_180)
    bgr = cv2.cvtColor(rgb_rotated, cv2.COLOR_RGB2BGR)
    success, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("JPEG encoding failed")
    jpeg_bytes = buf.tobytes()
    rid_bytes = robot_id.encode("ascii")
    header = bytes([0x01, len(rid_bytes)]) + rid_bytes
    return header + jpeg_bytes


def encode_depth_frame(
    robot_id: str, depth: np.ndarray, max_range: float = 10.0, quality: int = 70
) -> bytes:
    """Encode depth image as a colorized JPEG with binary protocol header.

    Normalizes depth to [0, max_range], applies a turbo/inferno-style
    colormap for visualization, and encodes as JPEG.

    Binary layout: [0x02][id_len: 1 byte][robot_id ASCII][JPEG bytes]

    Args:
        robot_id: Robot identifier string.
        depth: (H, W) float32 depth in meters. 0 = invalid.
        max_range: Max depth for normalization in meters.
        quality: JPEG compression quality (0-100).

    Returns:
        bytes with header + JPEG payload.
    """
    import cv2

    # Normalize to 0-255 range
    valid = (depth > 0) & (depth < max_range)
    normalized = np.zeros_like(depth, dtype=np.uint8)
    if np.any(valid):
        normalized[valid] = (255 * (1.0 - depth[valid] / max_range)).clip(0, 255).astype(np.uint8)

    # Apply colormap (TURBO gives a nice rainbow depth visualization)
    colored = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)
    # Black out invalid pixels
    colored[~valid] = 0
    # Rotate 90° clockwise to match camera xyaxes orientation
    colored = cv2.rotate(colored, cv2.ROTATE_180)

    success, buf = cv2.imencode(".jpg", colored, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("Depth JPEG encoding failed")

    jpeg_bytes = buf.tobytes()
    rid_bytes = robot_id.encode("ascii")
    header = bytes([0x02, len(rid_bytes)]) + rid_bytes
    return header + jpeg_bytes


def decode_camera_frame_header(data: bytes) -> tuple[str, bytes]:
    """Decode binary camera frame header to extract robot_id and JPEG data.

    Args:
        data: Raw bytes from encode_camera_frame.

    Returns:
        Tuple of (robot_id, jpeg_bytes).
    """
    # data[0] == 0x01 (marker)
    id_len = data[1]
    robot_id = data[2 : 2 + id_len].decode("ascii")
    jpeg_bytes = data[2 + id_len :]
    return robot_id, jpeg_bytes


def compute_cloud_delta(
    current_voxels: np.ndarray,
    last_voxel_set: set[tuple[float, float, float]],
) -> tuple[np.ndarray, set[tuple[float, float, float]]]:
    """Compute new voxels not in the previous set via set difference.

    Rounds coordinates to 2 decimal places for stable comparison.

    Args:
        current_voxels: (N, 3) float array of voxel positions.
        last_voxel_set: Set of (x, y, z) tuples from previous call.

    Returns:
        Tuple of (delta_voxels as (M, 3) array, updated voxel set).
    """
    if len(current_voxels) == 0:
        return np.empty((0, 3), dtype=np.float64), last_voxel_set

    rounded = np.round(current_voxels, 2)
    current_set = set(map(tuple, rounded))
    new_keys = current_set - last_voxel_set
    updated_set = last_voxel_set | current_set

    if not new_keys:
        return np.empty((0, 3), dtype=np.float64), updated_set

    delta = np.array(list(new_keys), dtype=np.float64)
    return delta, updated_set
