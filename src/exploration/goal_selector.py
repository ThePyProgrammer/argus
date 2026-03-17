"""Frontier ranking and selection policy.

Selects the best frontier cluster to explore next based on configurable
strategy: "nearest" (closest to robot) or "largest" (most voxels).

Supports optional region bias via select_with_bias() for multi-robot
Voronoi-partitioned exploration.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from src.exploration.frontier_detector import FrontierCluster


class GoalSelector:
    """Select the best frontier cluster for exploration.

    Strategies:
        - "nearest": Pick the cluster whose centroid is closest to the robot.
        - "largest": Pick the cluster with the most frontier voxels.
    """

    def __init__(self, strategy: str = "nearest"):
        if strategy not in ("nearest", "largest"):
            raise ValueError(f"Unknown strategy: {strategy!r}. Use 'nearest' or 'largest'.")
        self._strategy = strategy

    @property
    def strategy(self) -> str:
        """Current selection strategy."""
        return self._strategy

    def select(
        self, frontiers: list[FrontierCluster], robot_pose: np.ndarray
    ) -> np.ndarray | None:
        """Select the best frontier goal from a list of clusters.

        Args:
            frontiers: List of FrontierCluster objects from FrontierDetector.
            robot_pose: (4, 4) homogeneous transform; position extracted as
                robot_pose[:3, 3].

        Returns:
            (3,) float64 centroid of the selected cluster, or None if
            frontiers is empty.
        """
        if not frontiers:
            return None

        robot_position = robot_pose[:3, 3].astype(np.float64)

        if self._strategy == "nearest":
            best = min(
                frontiers,
                key=lambda c: float(np.linalg.norm(c.centroid - robot_position)),
            )
        else:  # "largest"
            best = max(frontiers, key=lambda c: c.voxel_count)

        return best.centroid.astype(np.float64)

    def select_with_bias(
        self,
        frontiers: list[FrontierCluster],
        robot_pose: np.ndarray,
        score_fn: Callable[[np.ndarray], float] | None = None,
    ) -> np.ndarray | None:
        """Select frontier using optional external scoring function.

        If score_fn is provided, use it to score each frontier centroid.
        Otherwise fall back to default strategy.

        Args:
            frontiers: List of FrontierCluster objects.
            robot_pose: (4, 4) homogeneous transform.
            score_fn: Optional callable (centroid) -> float score. Higher = better.

        Returns:
            (3,) float64 centroid of selected cluster, or None.
        """
        if not frontiers:
            return None
        if score_fn is None:
            return self.select(frontiers, robot_pose)
        best = max(frontiers, key=lambda c: score_fn(c.centroid.astype(np.float64)))
        return best.centroid.astype(np.float64)
