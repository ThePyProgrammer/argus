from __future__ import annotations

from src.exploration.skills.promotion import PromotionGateConfig, PromotionMetricSummary, evaluate_promotion


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
