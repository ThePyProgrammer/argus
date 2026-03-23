"""Coverage percentage computation and periodic logging.

Tracks exploration progress using two complementary metrics:
1. Frontier exhaustion ratio: `1 - (current / initial)` frontier count.
2. Bounding box ratio: `occupied_volume / bbox_volume`.

Maintains a history log for post-run analysis and produces an
ExplorationResult summary on termination.
"""


import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ExplorationResult:
    """Summary of a completed exploration run.

    Attributes:
        total_steps: Number of simulation steps executed.
        final_coverage_pct: Frontier exhaustion ratio at termination (0-100).
        final_bbox_coverage_pct: Bounding box fill ratio at termination (0-100).
        final_frontier_count: Number of frontier clusters remaining.
        terminated_reason: Why the loop stopped ("no_frontiers" | "max_steps" | "all_unreachable").
        history: Periodic snapshots as (step, coverage%, bbox_coverage%, frontier_count).
    """

    total_steps: int
    final_coverage_pct: float
    final_bbox_coverage_pct: float
    final_frontier_count: int
    terminated_reason: str  # "no_frontiers" | "max_steps" | "all_unreachable"
    history: list[tuple[int, float, float, int]] = field(default_factory=list)


class CoverageTracker:
    """Track exploration coverage using dual metrics.

    Primary metric (frontier exhaustion): percentage of initial frontiers
    that have been consumed. Secondary metric (bounding box): ratio of
    observed voxel volume to the bounding box volume.

    Args:
        voxel_resolution: Edge length of a single voxel in meters.
    """

    def __init__(self, voxel_resolution: float = 0.1) -> None:
        self._voxel_resolution = voxel_resolution
        self._initial_frontier_count: int | None = None
        self._history: list[tuple[int, float, float, int]] = []
        self._last_coverage: float = 0.0
        self._last_bbox_coverage: float = 0.0
        self._last_frontier_count: int = 0

    def update(
        self, occupied_voxels: np.ndarray, frontier_count: int
    ) -> tuple[float, float]:
        """Update coverage metrics from current map state.

        On the first call with frontier_count > 0, records the initial
        frontier count as the baseline for the exhaustion ratio.

        Args:
            occupied_voxels: (N, 3) float64 voxel centers.
            frontier_count: Current number of frontier clusters.

        Returns:
            (coverage_pct, bbox_coverage_pct) both in [0, 100].
        """
        # Set initial frontier count on first non-zero observation
        if self._initial_frontier_count is None and frontier_count > 0:
            self._initial_frontier_count = frontier_count

        # Primary metric: frontier exhaustion ratio
        if self._initial_frontier_count is not None and self._initial_frontier_count > 0:
            raw = (1.0 - frontier_count / self._initial_frontier_count) * 100.0
            coverage = max(0.0, min(raw, 100.0))
        else:
            coverage = 0.0

        # Secondary metric: bounding box fill ratio
        bbox_coverage = 0.0
        if occupied_voxels.size > 0 and len(occupied_voxels) > 0:
            vmin = occupied_voxels.min(axis=0)
            vmax = occupied_voxels.max(axis=0)
            extents = vmax - vmin
            bbox_volume = float(np.prod(np.maximum(extents, self._voxel_resolution)))
            observed_volume = len(occupied_voxels) * (self._voxel_resolution ** 3)
            bbox_coverage = min(observed_volume / bbox_volume, 1.0) * 100.0

        self._last_coverage = coverage
        self._last_bbox_coverage = bbox_coverage
        self._last_frontier_count = frontier_count

        return coverage, bbox_coverage

    def log(
        self,
        step: int,
        coverage_pct: float,
        bbox_coverage_pct: float,
        frontier_count: int,
    ) -> None:
        """Record a coverage snapshot and print status.

        Args:
            step: Current simulation step.
            coverage_pct: Frontier exhaustion percentage.
            bbox_coverage_pct: Bounding box fill percentage.
            frontier_count: Number of remaining frontier clusters.
        """
        self._history.append((step, coverage_pct, bbox_coverage_pct, frontier_count))
        logger.info(
            "[Step %5d] Coverage: %.1f%% (bbox: %.1f%%)  Frontiers: %d",
            step,
            coverage_pct,
            bbox_coverage_pct,
            frontier_count,
        )

    def result(self, total_steps: int, terminated_reason: str) -> ExplorationResult:
        """Build final ExplorationResult from accumulated history.

        Args:
            total_steps: Total simulation steps executed.
            terminated_reason: Why exploration stopped.

        Returns:
            ExplorationResult with final metrics and full history.
        """
        if self._history:
            _, final_cov, final_bbox, final_fc = self._history[-1]
        else:
            final_cov = 0.0
            final_bbox = 0.0
            final_fc = 0

        return ExplorationResult(
            total_steps=total_steps,
            final_coverage_pct=final_cov,
            final_bbox_coverage_pct=final_bbox,
            final_frontier_count=final_fc,
            terminated_reason=terminated_reason,
            history=list(self._history),
        )
