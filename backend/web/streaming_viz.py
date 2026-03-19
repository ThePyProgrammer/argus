"""WebSocket-based streaming visualizer -- drop-in for MultiRobotVisualizer.

Queues JSON and binary messages during update() for async broadcast
by the server push loop. Supports cloud delta/full sync, per-robot
pose, trajectory, camera frames, and stats.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

from backend.web.connection_manager import ConnectionManager
from backend.web.message_types import (
    CLOUD_DELTA,
    CLOUD_FULL,
    POSE_UPDATE,
    STATS,
    TRAJECTORY,
    color_for_robot,
    compute_cloud_delta,
    encode_camera_frame,
    encode_depth_frame,
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
        self._update_cloud(merged_voxels, robot_data)
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

    def _update_cloud(self, merged_voxels: np.ndarray, robot_data: dict) -> None:
        """Compute and queue cloud delta/full messages with per-robot colors."""
        if len(merged_voxels) == 0:
            return

        # Shift cloud down to ground level (camera height offset)
        merged_voxels = merged_voxels.copy()
        merged_voxels[:, 2] -= 0.3

        # Get robot world positions for coloring
        robot_positions = []
        for i, (rid, data) in enumerate(robot_data.items()):
            pose = data.get("pose")
            if pose is not None:
                robot_positions.append((i, pose[:3, 3].copy()))
            else:
                robot_positions.append((i, np.zeros(3)))

        # Delta tracking
        delta, updated_set = compute_cloud_delta(merged_voxels, self._last_voxel_set)
        self._last_voxel_set = updated_set

        if len(delta) > 0:
            colors = self._compute_colors(delta, robot_positions)
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
            full_colors = self._compute_colors(merged_voxels, robot_positions)
            self._message_queue.append({
                "type": CLOUD_FULL,
                "payload": {
                    "positions": merged_voxels.tolist(),
                    "colors": full_colors,
                },
            })

    def _build_robot_voxel_sets(
        self, robot_data: dict
    ) -> list[tuple[int, set[tuple[float, float, float]]]]:
        """Build per-robot voxel ownership sets for coloring.

        Returns list of (robot_index, set_of_voxel_tuples) ordered by robot.
        """
        result = []
        for i, (rid, data) in enumerate(robot_data.items()):
            local = data.get("local_voxels")
            if local is not None and len(local) > 0:
                # Round to 2 decimal places for matching (0.1m grid)
                voxel_set = set(
                    tuple(round(float(c), 2) for c in v)
                    for v in local
                )
                result.append((i, voxel_set))
        return result

    def _compute_colors(
        self,
        voxels: np.ndarray,
        robot_positions: list[tuple[int, np.ndarray]],
    ) -> list[list[int]]:
        """Compute per-voxel colors by nearest robot (3D distance).

        Each voxel is colored by the robot whose current world position
        is closest to it.
        """
        if not robot_positions:
            return [list(color_for_robot(0))] * len(voxels)

        # Vectorized: compute distance from each voxel to each robot
        robot_pos_array = np.array([pos for _, pos in robot_positions])  # (R, 3)
        # Broadcast: (N, 1, 3) - (1, R, 3) → (N, R, 3) → (N, R) distances
        dists = np.linalg.norm(
            voxels[:, np.newaxis, :] - robot_pos_array[np.newaxis, :, :],
            axis=2,
        )
        nearest = np.argmin(dists, axis=1)  # (N,) indices into robot_positions

        colors = []
        for i in range(len(voxels)):
            robot_idx = robot_positions[nearest[i]][0]
            colors.append(list(color_for_robot(robot_idx)))
        return colors

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

            # Camera frames (binary) — RGB + depth
            frame = data.get("frame")
            if frame is not None:
                try:
                    binary = encode_camera_frame(rid, frame.rgb)
                    self._message_queue.append(binary)
                except Exception:
                    pass
                if frame.depth is not None:
                    try:
                        depth_binary = encode_depth_frame(rid, frame.depth)
                        self._message_queue.append(depth_binary)
                    except Exception:
                        pass

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
