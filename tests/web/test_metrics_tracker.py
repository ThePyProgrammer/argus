"""Unit tests for MetricsTracker -- per-robot SLAM metrics accumulation.

Tests cover: record_frame, record_drift, ring buffer eviction,
get_robot_metrics, get_histories, capture_baseline, get_stats_payload,
and edge cases (no data, unknown robot).
"""

import time

import pytest

from src.metrics.metrics_tracker import MetricsTracker


class TestMetricsTracker:
    def test_record_frame_stores_ms_and_status(self):
        """Test 1: record_frame stores ms_per_frame and tracking_status."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 12.5}, "ok")
        m = tracker.get_robot_metrics("robot_a")
        assert m["ms_per_frame"] == 12.5
        assert m["tracking_status"] == "ok"

    def test_record_drift_appends_to_ring_buffer(self):
        """Test 2: record_drift appends ate_rmse and rpe_rmse to deque."""
        tracker = MetricsTracker(history_size=60)
        tracker.record_frame("robot_a", {}, "ok")
        tracker.record_drift("robot_a", 0.05, 0.04, 0.03, 0.02)
        m = tracker.get_robot_metrics("robot_a")
        assert m["ate_rmse"] == 0.05
        assert m["rpe_rmse"] == 0.03

    def test_ring_buffer_evicts_oldest(self):
        """Test 3: ring buffer evicts oldest entry when exceeding history_size."""
        tracker = MetricsTracker(history_size=3)
        tracker.record_frame("robot_a", {}, "ok")
        for i in range(5):
            tracker.record_drift("robot_a", float(i), float(i), float(i), float(i))
        histories = tracker.get_histories()
        assert len(histories["robot_a"]["ate_rmse"]) == 3
        # Oldest (0, 1) evicted; remaining are 2, 3, 4
        assert histories["robot_a"]["ate_rmse"][0] == 2.0
        assert histories["robot_a"]["ate_rmse"][-1] == 4.0

    def test_get_robot_metrics_returns_full_dict(self):
        """Test 4: get_robot_metrics returns dict with all 6 fields."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 10.0}, "ok")
        tracker.record_drift("robot_a", 0.1, 0.08, 0.05, 0.04)
        m = tracker.get_robot_metrics("robot_a")
        assert "ate_rmse" in m
        assert "ate_mean" in m
        assert "rpe_rmse" in m
        assert "rpe_mean" in m
        assert "ms_per_frame" in m
        assert "tracking_status" in m
        assert m["ate_rmse"] == 0.1
        assert m["ate_mean"] == 0.08
        assert m["rpe_rmse"] == 0.05
        assert m["rpe_mean"] == 0.04
        assert m["ms_per_frame"] == 10.0
        assert m["tracking_status"] == "ok"

    def test_get_histories_returns_per_robot_arrays(self):
        """Test 5: get_histories returns per-robot dict with arrays."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 5.0}, "ok")
        tracker.record_frame("robot_a", {"processing_time_ms": 6.0}, "ok")
        tracker.record_drift("robot_a", 0.1, 0.08, 0.05, 0.04)
        tracker.record_drift("robot_a", 0.2, 0.15, 0.1, 0.08)
        h = tracker.get_histories()
        assert "robot_a" in h
        assert len(h["robot_a"]["ate_rmse"]) == 2
        assert len(h["robot_a"]["rpe_rmse"]) == 2
        assert len(h["robot_a"]["ms_per_frame"]) == 2
        assert len(h["robot_a"]["timestamps"]) == 2
        assert h["robot_a"]["ate_rmse"] == [0.1, 0.2]

    def test_capture_baseline_snapshots_metrics(self):
        """Test 6: capture_baseline snapshots current per-robot metrics."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 10.0}, "ok")
        tracker.record_drift("robot_a", 0.1, 0.08, 0.05, 0.04)
        tracker.capture_baseline()
        assert tracker.baseline is not None
        assert "robot_a" in tracker.baseline
        assert tracker.baseline["robot_a"]["ate_rmse"] == 0.1

    def test_get_stats_payload_structure(self):
        """Test 7: get_stats_payload returns correct top-level structure."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 12.0}, "ok")
        tracker.record_drift("robot_a", 0.1, 0.08, 0.05, 0.04)
        payload = tracker.get_stats_payload()
        assert "slam_metrics" in payload
        assert "baseline" in payload
        assert "metric_history" in payload
        assert "robot_a" in payload["slam_metrics"]
        assert payload["slam_metrics"]["robot_a"]["ms_per_frame"] == 12.0
        assert payload["baseline"] is None  # no baseline captured yet

    def test_capture_baseline_none_when_no_metrics(self):
        """Test 8: capture_baseline returns None baseline when no data."""
        tracker = MetricsTracker()
        tracker.capture_baseline()
        assert tracker.baseline is None

    def test_record_frame_unknown_robot_initializes(self):
        """Test 9: record_frame for unknown robot initializes new entry."""
        tracker = MetricsTracker()
        # No prior setup for robot_x
        tracker.record_frame("robot_x", {"processing_time_ms": 7.0}, "initializing")
        m = tracker.get_robot_metrics("robot_x")
        assert m["ms_per_frame"] == 7.0
        assert m["tracking_status"] == "initializing"
        assert m["ate_rmse"] == 0.0  # no drift recorded yet
