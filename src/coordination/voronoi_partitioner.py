"""Perpendicular bisector partitioning for two robots.

For the 2-robot case, scipy.spatial.Voronoi is degenerate (only produces
infinite regions). Instead, compute the perpendicular bisector of the line
segment between robot positions and classify frontiers by which side they
fall on.

Per CONTEXT.md: soft constraint -- frontiers in own region are prioritized
(higher score) but robot CAN enter other's region if no local frontiers remain.
"""

from __future__ import annotations

import numpy as np


class VoronoiPartitioner:
    """Perpendicular bisector partitioning for two robots.

    Assigns frontier centroids to the nearest robot's region using a
    perpendicular bisector (midpoint + direction dot product). Provides
    region-biased scoring for goal selection and repartition detection.
    """

    def __init__(self, in_region_weight: float = 2.0):
        self._in_region_weight = in_region_weight
        self._robot_positions: dict[str, np.ndarray] = {}

    def update_positions(self, positions: dict[str, np.ndarray]) -> None:
        """Update robot positions for partition computation.

        Args:
            positions: {"robot_a": (2,) or (3,) array, "robot_b": ...}
                Only XY components are used for bisector computation.
        """
        self._robot_positions = {k: np.asarray(v)[:2] for k, v in positions.items()}

    def assign_frontiers(
        self,
        frontier_centroids: np.ndarray,
        robot_ids: tuple[str, str] = ("robot_a", "robot_b"),
    ) -> dict[str, np.ndarray]:
        """Assign frontier centroids to robots via perpendicular bisector.

        Points on the A-side of the bisector (dot <= 0) go to robot_a.
        Points on the B-side (dot > 0) go to robot_b.

        Args:
            frontier_centroids: (N, 3) float64 centroids of frontier clusters.
            robot_ids: Tuple of two robot ID strings.

        Returns:
            Dict mapping robot_id -> (K, 3) centroids assigned to that robot.
        """
        pos_a = self._robot_positions[robot_ids[0]]
        pos_b = self._robot_positions[robot_ids[1]]
        midpoint = (pos_a + pos_b) / 2.0
        direction = pos_b - pos_a  # A -> B

        xy_centroids = frontier_centroids[:, :2]
        deltas = xy_centroids - midpoint
        dots = deltas @ direction

        mask_b = dots > 0
        return {
            robot_ids[0]: frontier_centroids[~mask_b],
            robot_ids[1]: frontier_centroids[mask_b],
        }

    def score_frontier_with_bias(
        self,
        frontier_centroid: np.ndarray,
        robot_id: str,
        robot_pose: np.ndarray,
        robot_ids: tuple[str, str] = ("robot_a", "robot_b"),
    ) -> float:
        """Score a frontier with region bias for the given robot.

        Score = 1.0 / (distance + 1e-6) * region_multiplier
        where region_multiplier = in_region_weight if frontier is in robot's
        region, else 1.0.

        Args:
            frontier_centroid: (3,) world coordinates.
            robot_id: Which robot is scoring this frontier.
            robot_pose: (4, 4) current pose of the robot.
            robot_ids: The two robot IDs for bisector computation.

        Returns:
            Float score (higher = more preferred).
        """
        robot_pos = robot_pose[:3, 3]
        distance = float(np.linalg.norm(frontier_centroid - robot_pos))
        base_score = 1.0 / (distance + 1e-6)

        if not self._robot_positions:
            return base_score

        # Determine which region this frontier belongs to
        pos_a = self._robot_positions[robot_ids[0]]
        pos_b = self._robot_positions[robot_ids[1]]
        midpoint = (pos_a + pos_b) / 2.0
        direction = pos_b - pos_a
        dot = np.dot(frontier_centroid[:2] - midpoint, direction)

        is_in_b_region = dot > 0
        frontier_owner = robot_ids[1] if is_in_b_region else robot_ids[0]

        multiplier = self._in_region_weight if frontier_owner == robot_id else 1.0
        return base_score * multiplier

    def should_repartition(
        self,
        robot_id: str,
        frontier_centroids: np.ndarray,
        robot_ids: tuple[str, str] = ("robot_a", "robot_b"),
    ) -> bool:
        """Check if re-partition is needed because robot has zero frontiers in its region.

        Returns True if the given robot's assigned region has zero frontiers.
        """
        if len(frontier_centroids) == 0:
            return True

        assignments = self.assign_frontiers(frontier_centroids, robot_ids)
        return len(assignments[robot_id]) == 0
