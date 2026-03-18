"""WebSocket-based streaming visualizer -- drop-in for MultiRobotVisualizer.

Queues JSON and binary messages during update() for async broadcast
by the server push loop. Supports cloud delta/full sync, per-robot
pose, trajectory, camera frames, and stats.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

from src.web.connection_manager import ConnectionManager
from src.web.message_types import (
    CLOUD_DELTA,
    CLOUD_FULL,
    POSE_UPDATE,
    STATS,
    TRAJECTORY,
    color_for_robot,
    compute_cloud_delta,
    encode_camera_frame,
)

if TYPE_CHECKING:
    pass


class WebStreamingViz:
    """Drop-in replacement for MultiRobotVisualizer that streams over WebSocket.

    Instead of logging to Rerun, this class queues messages that the
    FastAPI server drains and broadcasts to connected clients.

    Args:
        connection_manager: ConnectionManager for tracking active clients.
        robot_ids: List of robot identifiers.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        robot_ids: list[str],
    ) -> None:
        self._cm = connection_manager
        self._robot_ids = robot_ids
        self._last_voxel_set: set[tuple[float, float, float]] = set()
        self._last_full_sync: float = 0.0
        self._full_sync_interval: float = 10.0
        self._color_mode: str = "robot_tint"
        self._start_time: float = time.monotonic()
        self._message_queue: list[dict | bytes] = []

    def update(
        self,
        merged_voxels: np.ndarray,
        robot_data: dict,
        frontier_cells: np.ndarray | None = None,
        voronoi_midpoint: np.ndarray | None = None,
        voronoi_direction: np.ndarray | None = None,
        total_coverage: float = 0.0,
        merge_count: int = 0,
    ) -> None:
        """Update all streaming channels -- same signature as MultiRobotVisualizer.

        Computes cloud delta, per-robot poses, trajectories, camera frames,
        and stats. All messages queued for async broadcast.

        Args:
            merged_voxels: (N, 3) float array of merged voxel positions.
            robot_data: Dict keyed by robot_id with frame, local_voxels,
                pose, trajectory, coverage_pct.
            frontier_cells: Optional frontier cell positions (unused for now).
            voronoi_midpoint: Optional Voronoi bisector midpoint (unused).
            voronoi_direction: Optional Voronoi direction (unused).
            total_coverage: Combined coverage percentage.
            merge_count: Number of map merges performed.
        """
        self._update_cloud(merged_voxels)
        self._update_robots(robot_data)
        self._update_stats(robot_data, total_coverage, merge_count)

    def set_color_mode(self, mode: str) -> None:
        """Set color mode for point cloud visualization.

        Args:
            mode: Either "robot_tint" (per-robot palette) or "true_rgb".
        """
        self._color_mode = mode

    def get_pending_messages(self) -> list[dict | bytes]:
        """Drain and return all queued messages.

        Returns:
            List of dict (JSON messages) and bytes (binary frames).
        """
        msgs = self._message_queue
        self._message_queue = []
        return msgs

    def _update_cloud(self, merged_voxels: np.ndarray) -> None:
        """Compute and queue cloud delta/full messages."""
        if len(merged_voxels) == 0:
            return

        # Shift cloud Z down to ground level. The forward-facing camera
        # reconstructs the ground plane at Z≈0.15 instead of Z=0 due to
        # the camera height and viewing angle. Subtract the offset so the
        # cloud sits on the ground in the web UI.
        corrected = merged_voxels.copy()
        corrected[:, 2] -= 0.15

        # Delta tracking
        delta, updated_set = compute_cloud_delta(corrected, self._last_voxel_set)
        self._last_voxel_set = updated_set

        if len(delta) > 0:
            colors = self._compute_colors(delta)
            self._message_queue.append({
                "type": CLOUD_DELTA,
                "payload": {
                    "positions": delta.tolist(),
                    "colors": colors,
                },
            })

        # Full sync check
        now = time.monotonic()
        if now - self._last_full_sync > self._full_sync_interval:
            self._last_full_sync = now
            full_colors = self._compute_colors(corrected)
            self._message_queue.append({
                "type": CLOUD_FULL,
                "payload": {
                    "positions": corrected.tolist(),
                    "colors": full_colors,
                },
            })

    def _compute_colors(self, voxels: np.ndarray) -> list[list[int]]:
        """Compute per-voxel colors based on current color mode.

        Args:
            voxels: (N, 3) voxel positions.

        Returns:
            List of [R, G, B] per voxel.
        """
        n = len(voxels)
        if self._color_mode == "true_rgb":
            # Placeholder: white since merged voxels don't carry color
            return [[255, 255, 255]] * n
        else:
            # robot_tint: use first robot's color as default for merged cloud
            color = list(color_for_robot(0))
            return [color] * n

    def _update_robots(self, robot_data: dict) -> None:
        """Queue per-robot pose, trajectory, and camera frame messages."""
        for i, (rid, data) in enumerate(robot_data.items()):
            pose = data["pose"]

            # Pose update
            self._message_queue.append({
                "type": POSE_UPDATE,
                "robot_id": rid,
                "payload": {
                    "position": pose[:3, 3].tolist(),
                    "rotation": pose[:3, :3].flatten().tolist(),
                },
            })

            # Trajectory
            trajectory = data.get("trajectory", [])
            if len(trajectory) >= 1:
                recent = trajectory[-50:]
                positions = [p[:3, 3].tolist() for p in recent]
                n = len(positions)
                alphas = [int(255 * (j + 1) / n) for j in range(n)]
                self._message_queue.append({
                    "type": TRAJECTORY,
                    "robot_id": rid,
                    "payload": {
                        "positions": positions,
                        "alphas": alphas,
                    },
                })

            # Camera frame (binary)
            frame = data.get("frame")
            if frame is not None:
                try:
                    binary = encode_camera_frame(rid, frame.rgb)
                    self._message_queue.append(binary)
                except Exception:
                    pass  # Skip if encoding fails

    def _update_stats(
        self,
        robot_data: dict,
        total_coverage: float,
        merge_count: int,
    ) -> None:
        """Queue stats message."""
        elapsed = time.monotonic() - self._start_time
        robots = {}
        for rid, data in robot_data.items():
            robots[rid] = {
                "coverage_pct": data.get("coverage_pct", 0.0),
                "voxel_count": len(data.get("local_voxels", [])),
                "action": "exploring",
            }
        self._message_queue.append({
            "type": STATS,
            "payload": {
                "total_coverage": total_coverage,
                "merge_count": merge_count,
                "elapsed": elapsed,
                "robots": robots,
            },
        })
