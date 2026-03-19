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

        # Build per-robot voxel ownership for coloring
        robot_voxel_sets = self._build_robot_voxel_sets(robot_data)

        # Delta tracking
        delta, updated_set = compute_cloud_delta(merged_voxels, self._last_voxel_set)
        self._last_voxel_set = updated_set

        if len(delta) > 0:
            colors = self._compute_colors(delta, robot_voxel_sets)
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
            full_colors = self._compute_colors(merged_voxels, robot_voxel_sets)
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
        robot_voxel_sets: list[tuple[int, set[tuple[float, float, float]]]],
    ) -> list[list[int]]:
        """Compute per-voxel colors based on spatial proximity to robots.

        Uses X coordinate to roughly assign voxels to the nearest robot
        (since robots start at different X positions). Simple but effective
        for two-robot scenarios on flat ground.
        """
        if not robot_voxel_sets:
            return [list(color_for_robot(0))] * len(voxels)

        # Get approximate robot X positions from their voxel set centers
        robot_centers = []
        for robot_idx, voxel_set in robot_voxel_sets:
            if voxel_set:
                xs = [v[0] for v in voxel_set]
                robot_centers.append((robot_idx, sum(xs) / len(xs)))
            else:
                robot_centers.append((robot_idx, 0.0))

        colors = []
        for v in voxels:
            vx = float(v[0])
            # Assign to nearest robot by X distance
            best_idx = robot_centers[0][0]
            best_dist = abs(vx - robot_centers[0][1])
            for robot_idx, cx in robot_centers[1:]:
                d = abs(vx - cx)
                if d < best_dist:
                    best_dist = d
                    best_idx = robot_idx
            colors.append(list(color_for_robot(best_idx)))
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
