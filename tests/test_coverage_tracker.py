"""Unit tests for CoverageTracker and ExplorationConfig.

Tests dual coverage metrics (frontier exhaustion + bounding box ratio),
history logging, and ExplorationResult generation.
"""

import numpy as np
import pytest

from src.exploration.config import ExplorationConfig
from src.exploration.coverage_tracker import CoverageTracker, ExplorationResult


class TestExplorationConfig:
    """Tests for ExplorationConfig dataclass defaults."""

    def test_default_values(self) -> None:
        cfg = ExplorationConfig()
        assert cfg.rescan_distance_m == 2.0
        assert cfg.rescan_voxel_delta == 500
        assert cfg.max_steps == 10000
        assert cfg.stuck_threshold_steps == 20
        assert cfg.stuck_distance_m == 0.3
        assert cfg.log_interval_steps == 50
        assert cfg.voxel_resolution == 0.1
        assert cfg.min_cluster_size == 5
        assert cfg.goal_strategy == "nearest"
        assert cfg.linear_speed == 0.5
        assert cfg.angular_speed == 1.0
        assert cfg.waypoint_arrival_threshold == 1.0

    def test_custom_values(self) -> None:
        cfg = ExplorationConfig(max_steps=500, goal_strategy="largest")
        assert cfg.max_steps == 500
        assert cfg.goal_strategy == "largest"


class TestCoverageTracker:
    """Tests for CoverageTracker coverage computation and logging."""

    def test_initial_coverage_zero(self) -> None:
        """Initial coverage is 0% before any update."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        result = tracker.result(total_steps=0, terminated_reason="no_frontiers")
        assert result.final_coverage_pct == 0.0
        assert result.final_bbox_coverage_pct == 0.0
        assert result.total_steps == 0

    def test_coverage_increases(self) -> None:
        """Coverage increases as frontier count decreases."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        rng = np.random.default_rng(42)

        # First update: 100 voxels, 50 frontiers (sets initial count)
        voxels_1 = rng.random((100, 3)) * 5.0
        cov1, bbox1 = tracker.update(voxels_1, frontier_count=50)
        assert cov1 == 0.0  # 1 - 50/50 = 0%

        # Second update: 200 voxels, 25 frontiers (half consumed)
        voxels_2 = rng.random((200, 3)) * 5.0
        cov2, bbox2 = tracker.update(voxels_2, frontier_count=25)
        assert cov2 == pytest.approx(50.0)  # 1 - 25/50 = 50%

        # Coverage increased
        assert cov2 > cov1

    def test_frontier_exhaustion_ratio(self) -> None:
        """Primary metric: 1 - (current_frontier_count / initial_frontier_count)."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        rng = np.random.default_rng(42)
        voxels = rng.random((100, 3)) * 5.0

        # Initial: 100 frontiers
        cov, _ = tracker.update(voxels, frontier_count=100)
        assert cov == pytest.approx(0.0)

        # Down to 30 frontiers
        cov, _ = tracker.update(voxels, frontier_count=30)
        assert cov == pytest.approx(70.0)

        # Down to 0 frontiers
        cov, _ = tracker.update(voxels, frontier_count=0)
        assert cov == pytest.approx(100.0)

    def test_bbox_coverage_secondary_metric(self) -> None:
        """Secondary metric: occupied_volume / bounding_box_volume."""
        tracker = CoverageTracker(voxel_resolution=0.1)

        # Create a regular grid of voxels in a 1x1x1 cube
        coords = []
        for x in range(10):
            for y in range(10):
                for z in range(10):
                    coords.append([x * 0.1, y * 0.1, z * 0.1])
        voxels = np.array(coords, dtype=np.float64)

        _, bbox_cov = tracker.update(voxels, frontier_count=10)
        # bbox_coverage should be > 0
        assert bbox_cov > 0.0
        assert bbox_cov <= 100.0

    def test_log_records_history(self) -> None:
        """log() appends (step, coverage%, bbox_coverage%, frontier_count) to history."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        tracker.log(step=0, coverage_pct=0.0, bbox_coverage_pct=1.0, frontier_count=50)
        tracker.log(step=50, coverage_pct=50.0, bbox_coverage_pct=5.0, frontier_count=25)

        result = tracker.result(total_steps=100, terminated_reason="no_frontiers")
        assert len(result.history) == 2
        assert result.history[0] == (0, 0.0, 1.0, 50)
        assert result.history[1] == (50, 50.0, 5.0, 25)

    def test_result_returns_exploration_result(self) -> None:
        """result() returns ExplorationResult with final metrics from last history entry."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        rng = np.random.default_rng(42)
        voxels = rng.random((100, 3)) * 5.0

        tracker.update(voxels, frontier_count=50)
        tracker.log(step=0, coverage_pct=0.0, bbox_coverage_pct=1.0, frontier_count=50)

        tracker.update(voxels, frontier_count=10)
        tracker.log(step=50, coverage_pct=80.0, bbox_coverage_pct=5.0, frontier_count=10)

        result = tracker.result(total_steps=100, terminated_reason="no_frontiers")
        assert isinstance(result, ExplorationResult)
        assert result.total_steps == 100
        assert result.final_coverage_pct == 80.0
        assert result.final_bbox_coverage_pct == 5.0
        assert result.final_frontier_count == 10
        assert result.terminated_reason == "no_frontiers"

    def test_result_empty_history(self) -> None:
        """result() returns zeros when history is empty."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        result = tracker.result(total_steps=0, terminated_reason="max_steps")
        assert result.final_coverage_pct == 0.0
        assert result.final_bbox_coverage_pct == 0.0
        assert result.final_frontier_count == 0
        assert result.terminated_reason == "max_steps"
        assert result.history == []

    def test_zero_initial_frontiers(self) -> None:
        """If initial frontier count is 0, coverage stays 0%."""
        tracker = CoverageTracker(voxel_resolution=0.1)
        rng = np.random.default_rng(42)
        voxels = rng.random((100, 3)) * 5.0

        cov, _ = tracker.update(voxels, frontier_count=0)
        assert cov == 0.0
