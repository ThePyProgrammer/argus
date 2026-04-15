"""DET-METRICS-03 runtime-guard tests — payload-time rejection of mAP-family keys.

Replaces the Wave 0 scaffold. Tests ``_assert_no_map_keys`` from
``backend.web.streaming_viz`` (added by 06-08-PLAN.md). The runtime guard
is the belt-and-suspenders companion to the Plan 12 grep test: the grep
test catches source-level regressions and this test catches
serialization-time regressions (e.g., a key injected via dict-merge
from an external dependency).

Covers (per 06-08-PLAN.md Task 2 <behavior>):
  1. Healthy payload with valid Phase 6 keys does not raise.
  2. Top-level ``mAP`` inside ``detection_metrics`` raises.
  3. ``map_50`` raises (with key name in the message).
  4. ``mean_average_precision`` raises (with key name in the message).
  5. Forbidden key nested inside a list element raises (recursive walk).
  6. Forbidden key nested UNDER ``detection_gt_metrics[rid][class]``
     raises — exercises the SC#2 (2026-04-15 revision) payload key to
     ensure the guard still walks into it.
"""
from __future__ import annotations

import pytest

from backend.web.streaming_viz import _assert_no_map_keys


def test_assert_no_map_keys_passes_on_healthy_payload() -> None:
    """Healthy payload shape with all Phase 6 keys does not raise."""
    payload = {
        "detection_metrics": {
            "r0": {
                "inference_ms_p50": 12.0,
                "inference_ms_p95": 18.5,
                "detections_per_frame": 3,
                "mean_confidence": 0.87,
                "queue_depth": 0,
                "freshness_s": 0.042,
                "jitter_m": 0.015,
            }
        },
        "detection_history": {
            "r0": {
                "inference_ms": [10.0, 11.0, 12.0],
                "det_per_frame": [3, 3, 4],
            }
        },
        "detection_gt_metrics": {
            "r0": {
                "chair": {"center_error_m": 0.12, "per_class_recall": 0.66},
                "tv": {"center_error_m": 0.34, "per_class_recall": 1.0},
            }
        },
        "slam_metrics": {"r0": {"ate_rmse": 0.1, "ms_per_frame": 18.0}},
        "baseline": {},
        "metric_history": {"r0": {"ate_rmse": [0.1, 0.09, 0.11]}},
    }
    # Must not raise.
    _assert_no_map_keys(payload)


def test_assert_no_map_keys_raises_on_mAP_key() -> None:
    """Top-level mAP key inside detection_metrics raises with key in message."""
    with pytest.raises(AssertionError, match="mAP"):
        _assert_no_map_keys({"detection_metrics": {"r0": {"mAP": 0.7}}})


def test_assert_no_map_keys_raises_on_map_50() -> None:
    """map_50 raises with DET-METRICS-03 reference in the message."""
    with pytest.raises(AssertionError, match="map_50"):
        _assert_no_map_keys({"detection_metrics": {"r0": {"map_50": 0.3}}})


def test_assert_no_map_keys_raises_on_map_75() -> None:
    """map_75 raises — completes coverage of all four forbidden keys."""
    with pytest.raises(AssertionError, match="map_75"):
        _assert_no_map_keys({"detection_metrics": {"r0": {"map_75": 0.25}}})


def test_assert_no_map_keys_raises_on_mean_average_precision() -> None:
    """mean_average_precision anywhere raises — walker descends into nested dicts."""
    with pytest.raises(AssertionError, match="mean_average_precision"):
        _assert_no_map_keys({"r0": {"mean_average_precision": 0.5}})


def test_assert_no_map_keys_catches_nested_list() -> None:
    """Forbidden key inside a list element raises — recursive walker covers lists."""
    with pytest.raises(AssertionError, match="mAP"):
        _assert_no_map_keys(
            {"history": [{"inference": 10.0}, {"mAP": 0.9}]}
        )


def test_assert_no_map_keys_catches_forbidden_under_detection_gt_metrics() -> None:
    """SC#2 (revision 2026-04-15): guard walks into the new detection_gt_metrics key.

    If the recursive walker short-circuited at the first sign of a new
    payload key, a forbidden key nested three levels deep under
    ``detection_gt_metrics[rid][class]`` would escape. This test locks in
    that the walker descends all the way down.
    """
    with pytest.raises(AssertionError, match="mAP"):
        _assert_no_map_keys(
            {"detection_gt_metrics": {"r0": {"chair": {"mAP": 0.9}}}}
        )


def test_assert_no_map_keys_message_includes_det_metrics_03_reference() -> None:
    """Guard message references DET-METRICS-03 for on-call debuggability."""
    with pytest.raises(AssertionError, match="DET-METRICS-03"):
        _assert_no_map_keys({"detection_metrics": {"r0": {"mAP": 0.7}}})
