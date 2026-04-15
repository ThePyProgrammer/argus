"""Unit tests for DetectionMetricsTracker (CONTEXT D-01, D-02, D-03, D-09).

Replaces the Wave 0 skip-stub (06-02-PLAN.md) with 7 real tests per
06-04-PLAN.md <behavior>. Covers:
  1. p50/p95 reflect the backend_metrics input verbatim.
  2. Ring-buffer eviction at maxlen=history_size.
  3. Empty-state defaults are finite, non-NaN.
  4. Nearest-neighbor jitter math with 0.5m class-gate (CONTEXT D-03).
  5. Stats payload shape (3 top-keys, exact metric key-sets).
  6. record_gt_match accumulates center_err_ring + matched_count
     (SC#2 / CONTEXT D-09).
  7. reset_gt() clears GT state only (SC#1 history continuity).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pytest

from src.metrics.detection_metrics_tracker import DetectionMetricsTracker


# ───────────────────────────────────────────────────────────────
# Local fakes — intentionally NOT importing Detections3D / OrientedBox3D
# from src.perception.types (keeps this test decoupled from Phase 2 wiring).
# The tracker only reads duck-typed attributes; that's all we replicate.
# ───────────────────────────────────────────────────────────────
@dataclass
class FakeOBB:
    center: np.ndarray
    score: float
    class_name: str


@dataclass
class FakeDetections3D:
    items: list
    capture_timestamp: float = 0.0


def _make_det(centers: list[tuple[float, float, float]], classes: list[str], scores: list[float],
              capture_timestamp: float = 0.0) -> FakeDetections3D:
    items = [
        FakeOBB(center=np.asarray(c, dtype=np.float64), score=s, class_name=cn)
        for c, cn, s in zip(centers, classes, scores)
    ]
    return FakeDetections3D(items=items, capture_timestamp=capture_timestamp)


# ───────────────────────────────────────────────────────────────
# Test 1 — p50 / p95 propagate from backend_metrics verbatim.
# ───────────────────────────────────────────────────────────────
def test_p50_p95_against_known_sequence():
    tracker = DetectionMetricsTracker(history_size=60)
    backend = {"inference_ms_p50": 12.0, "inference_ms_p95": 40.0,
               "detections_per_frame": 0.0, "mean_confidence": 0.0,
               "first_inference_ms": 99.0}
    inspect = {"queue_depth": 1, "drops_since_session_start": 0,
               "last_submit_sim_time": 0.0}
    det = _make_det(centers=[(0.0, 0.0, 0.0)], classes=["chair"], scores=[0.9])
    for i in range(10):
        tracker.record_frame(
            robot_id="robot_0",
            sim_now=float(i) * 0.1,
            latest=det,
            inspect=inspect,
            backend_metrics=backend,
        )
    payload = tracker.get_stats_payload()
    live = payload["detection_metrics"]["robot_0"]
    assert live["inference_ms_p50"] == 12.0
    assert live["inference_ms_p95"] == 40.0


# ───────────────────────────────────────────────────────────────
# Test 2 — ring buffer bounded at history_size; older entries evicted.
# ───────────────────────────────────────────────────────────────
def test_ring_buffer_eviction():
    tracker = DetectionMetricsTracker(history_size=3)
    inspect = {"queue_depth": 0}
    for i in range(5):
        backend = {"inference_ms_p50": float(i), "inference_ms_p95": float(i) * 2.0}
        tracker.record_frame(
            robot_id="robot_0",
            sim_now=float(i),
            latest=None,
            inspect=inspect,
            backend_metrics=backend,
        )
    payload = tracker.get_stats_payload()
    hist = payload["detection_history"]["robot_0"]
    assert len(hist["inference_ms"]) == 3
    # Oldest two evicted → only i=2,3,4 remain.
    assert hist["inference_ms"] == [2.0, 3.0, 4.0]


# ───────────────────────────────────────────────────────────────
# Test 3 — empty-state + no-op record_frame yields finite values.
# ───────────────────────────────────────────────────────────────
def test_empty_state_no_nan():
    tracker = DetectionMetricsTracker(history_size=60)

    # Before any record_frame: empty dicts, no NaN, no KeyError.
    payload = tracker.get_stats_payload()
    assert payload == {
        "detection_metrics": {},
        "detection_history": {},
        "detection_gt_metrics": {},
    }

    # First record_frame with latest=None, empty inspect + backend_metrics.
    tracker.record_frame(
        robot_id="robot_0",
        sim_now=0.0,
        latest=None,
        inspect={},
        backend_metrics={},
    )
    payload = tracker.get_stats_payload()
    live = payload["detection_metrics"]["robot_0"]
    for k, v in live.items():
        assert math.isfinite(v), f"{k} is not finite: {v}"
        assert not (isinstance(v, float) and math.isnan(v)), f"{k} is NaN"

    # All 7 live keys present.
    expected = {
        "inference_ms_p50", "inference_ms_p95", "detections_per_frame",
        "mean_confidence", "queue_depth", "freshness_s", "jitter_m",
    }
    assert set(live.keys()) == expected

    # detection_gt_metrics is empty until first record_gt_match.
    assert payload["detection_gt_metrics"] == {}


# ───────────────────────────────────────────────────────────────
# Test 4 — nearest-neighbor jitter with 0.5m class gate (CONTEXT D-03).
# ───────────────────────────────────────────────────────────────
def test_nn_jitter_within_gate():
    tracker = DetectionMetricsTracker(history_size=60)
    inspect = {"queue_depth": 0}
    backend = {"inference_ms_p50": 10.0, "inference_ms_p95": 20.0}

    # Feed 5 frames of one chair moving ≤0.2m along x (all within 0.5m gate).
    for i, x in enumerate([0.0, 0.05, 0.10, 0.15, 0.20]):
        det = _make_det(centers=[(x, 0.0, 0.0)], classes=["chair"], scores=[0.9])
        tracker.record_frame(
            robot_id="robot_0",
            sim_now=float(i) * 0.1,
            latest=det,
            inspect=inspect,
            backend_metrics=backend,
        )

    payload = tracker.get_stats_payload()
    live = payload["detection_metrics"]["robot_0"]
    jitter_chair_only = live["jitter_m"]
    assert math.isfinite(jitter_chair_only)
    assert jitter_chair_only > 0.0
    assert jitter_chair_only < 0.2  # stddev of distances from mean must be < spread

    # Now feed one frame with a chair still near AND a far-away table.
    # Table is a new class → new tracked history, seeded fresh.
    det2 = _make_det(
        centers=[(0.22, 0.0, 0.0), (10.0, 10.0, 10.0)],
        classes=["chair", "table"],
        scores=[0.9, 0.8],
    )
    tracker.record_frame(
        robot_id="robot_0",
        sim_now=0.6,
        latest=det2,
        inspect=inspect,
        backend_metrics=backend,
    )
    payload = tracker.get_stats_payload()
    live = payload["detection_metrics"]["robot_0"]
    # jitter_m is the max over classes; must remain finite & non-negative.
    assert math.isfinite(live["jitter_m"])
    assert live["jitter_m"] >= 0.0


# ───────────────────────────────────────────────────────────────
# Test 5 — stats payload shape (exact keys, exact metric names).
# ───────────────────────────────────────────────────────────────
def test_stats_payload_shape():
    tracker = DetectionMetricsTracker(history_size=60)
    inspect = {"queue_depth": 0}
    backend = {"inference_ms_p50": 10.0, "inference_ms_p95": 20.0}
    det = _make_det(centers=[(0.0, 0.0, 0.0)], classes=["chair"], scores=[0.5])
    tracker.record_frame(
        robot_id="robot_0", sim_now=0.0, latest=det,
        inspect=inspect, backend_metrics=backend,
    )

    payload = tracker.get_stats_payload()
    assert set(payload.keys()) == {"detection_metrics", "detection_history", "detection_gt_metrics"}

    live = payload["detection_metrics"]["robot_0"]
    assert set(live.keys()) == {
        "inference_ms_p50", "inference_ms_p95", "detections_per_frame",
        "mean_confidence", "queue_depth", "freshness_s", "jitter_m",
    }

    hist = payload["detection_history"]["robot_0"]
    assert set(hist.keys()) == {"inference_ms", "det_per_frame", "confidence", "freshness", "jitter"}

    # Empty GT state until first record_gt_match.
    assert payload["detection_gt_metrics"] == {}


# ───────────────────────────────────────────────────────────────
# Test 6 — record_gt_match accumulates center_error + recall (SC#2).
# ───────────────────────────────────────────────────────────────
def test_record_gt_match_accumulates_center_error_and_recall():
    tracker = DetectionMetricsTracker(history_size=60)

    # Path A: 2 matches + 1 miss.
    tracker.record_gt_match("robot_0", "chair", 0.10, True)
    tracker.record_gt_match("robot_0", "chair", 0.20, True)
    tracker.record_gt_match("robot_0", "chair", None, False)

    payload = tracker.get_stats_payload()
    gt = payload["detection_gt_metrics"]["robot_0"]["chair"]
    assert gt["center_error_m"] == pytest.approx(0.15, abs=1e-9)
    assert gt["per_class_recall"] == pytest.approx(2.0 / 3.0, abs=1e-9)

    # Path B: fresh robot, single miss → center_error_m is None, recall 0.0.
    tracker.record_gt_match("robot_1", "chair", None, False)
    payload = tracker.get_stats_payload()
    gt1 = payload["detection_gt_metrics"]["robot_1"]["chair"]
    assert gt1["center_error_m"] is None
    assert gt1["per_class_recall"] == 0.0


# ───────────────────────────────────────────────────────────────
# Test 7 — reset_gt() clears GT state only; live metrics preserved.
# ───────────────────────────────────────────────────────────────
def test_reset_gt_clears_only_gt_state():
    tracker = DetectionMetricsTracker(history_size=60)
    inspect = {"queue_depth": 2}
    backend = {"inference_ms_p50": 7.0, "inference_ms_p95": 15.0}
    det = _make_det(centers=[(1.0, 1.0, 1.0)], classes=["chair"], scores=[0.75])

    # Populate both live and GT state.
    for i in range(3):
        tracker.record_frame(
            robot_id="robot_0",
            sim_now=float(i) * 0.1,
            latest=det,
            inspect=inspect,
            backend_metrics=backend,
        )
    tracker.record_gt_match("robot_0", "chair", 0.05, True)
    tracker.record_gt_match("robot_0", "chair", 0.15, True)

    payload_before = tracker.get_stats_payload()
    assert payload_before["detection_gt_metrics"]["robot_0"]["chair"]["center_error_m"] == pytest.approx(0.10, abs=1e-9)
    live_before = dict(payload_before["detection_metrics"]["robot_0"])
    hist_before = {k: list(v) for k, v in payload_before["detection_history"]["robot_0"].items()}

    # Surgical reset_gt() — does NOT touch live/history.
    tracker.reset_gt()

    payload_after = tracker.get_stats_payload()
    assert payload_after["detection_gt_metrics"] == {}
    # Live metrics + history unchanged.
    assert payload_after["detection_metrics"]["robot_0"] == live_before
    for k, v in hist_before.items():
        assert list(payload_after["detection_history"]["robot_0"][k]) == v
