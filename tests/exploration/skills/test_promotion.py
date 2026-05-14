from __future__ import annotations

import pytest

from src.exploration.skills.promotion import PromotionGateConfig, PromotionMetricSummary, evaluate_promotion


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "error_type"),
    [
        *[(field_name, float("nan"), ValueError) for field_name in PromotionGateConfig.__dataclass_fields__],
        *[(field_name, float("inf"), ValueError) for field_name in PromotionGateConfig.__dataclass_fields__],
        *[(field_name, float("-inf"), ValueError) for field_name in PromotionGateConfig.__dataclass_fields__],
        *[(field_name, True, TypeError) for field_name in PromotionGateConfig.__dataclass_fields__],
        *[(field_name, False, TypeError) for field_name in PromotionGateConfig.__dataclass_fields__],
    ],
)
def test_promotion_gate_config_rejects_invalid_thresholds(
    field_name: str, invalid_value: object, error_type: type[Exception]
) -> None:
    with pytest.raises(error_type, match=field_name):
        PromotionGateConfig(**{field_name: invalid_value})


def test_promotion_passes_on_threshold_equality() -> None:
    baseline = PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    candidate = PromotionMetricSummary(11.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    config = PromotionGateConfig(
        min_score_improvement=1.0,
        min_coverage_delta=0.0,
        max_safety_event_delta=0.0,
        max_recovery_event_delta=0.0,
        max_path_length_delta=0.0,
        max_switch_rate_delta=0.0,
        min_map_quality_delta=0.0,
    )

    report = evaluate_promotion(baseline, candidate, config)

    assert report.promoted is True
    assert report.regressions == ()


@pytest.mark.parametrize(
    ("baseline", "candidate", "expected_regression"),
    [
        (
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            PromotionMetricSummary(9.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            "score_improvement_too_small",
        ),
        (
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            PromotionMetricSummary(10.0, 79.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            "coverage_regressed",
        ),
        (
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            PromotionMetricSummary(10.0, 80.0, 0.0, 2.0, 100.0, 0.1, 0.9),
            "recovery_events_regressed",
        ),
        (
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 101.0, 0.1, 0.9),
            "path_length_regressed",
        ),
        (
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9),
            PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.89),
            "map_quality_regressed",
        ),
    ],
)
def test_promotion_reports_documented_regressions(
    baseline: PromotionMetricSummary, candidate: PromotionMetricSummary, expected_regression: str
) -> None:
    report = evaluate_promotion(
        baseline,
        candidate,
        PromotionGateConfig(
            min_score_improvement=0.0,
            min_coverage_delta=0.0,
            max_safety_event_delta=0.0,
            max_recovery_event_delta=0.0,
            max_path_length_delta=0.0,
            max_switch_rate_delta=0.0,
            min_map_quality_delta=0.0,
        ),
    )

    assert report.promoted is False
    assert expected_regression in report.regressions


def test_promotion_passes_when_candidate_improves_without_regressions() -> None:
    baseline = PromotionMetricSummary(
        balanced_score_mean=10.0,
        coverage_mean=80.0,
        safety_events_mean=0.0,
        recovery_events_mean=1.0,
        path_length_mean=100.0,
        switch_rate_mean=0.1,
        map_quality_mean=0.9,
    )
    candidate = PromotionMetricSummary(
        balanced_score_mean=11.0,
        coverage_mean=82.0,
        safety_events_mean=0.0,
        recovery_events_mean=1.0,
        path_length_mean=98.0,
        switch_rate_mean=0.1,
        map_quality_mean=0.91,
    )

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig(min_score_improvement=0.5))

    assert report.promoted is True
    assert report.regressions == ()


def test_promotion_fails_on_safety_regression_even_with_score_gain() -> None:
    baseline = PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    candidate = PromotionMetricSummary(12.0, 85.0, 1.0, 1.0, 95.0, 0.1, 0.9)

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig())

    assert report.promoted is False
    assert "safety_events_regressed" in report.regressions


def test_promotion_fails_when_switch_rate_regresses() -> None:
    baseline = PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    candidate = PromotionMetricSummary(11.0, 83.0, 0.0, 1.0, 95.0, 0.4, 0.9)

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig(max_switch_rate_delta=0.2))

    assert report.promoted is False
    assert "switch_rate_regressed" in report.regressions
