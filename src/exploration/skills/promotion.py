from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True)
class PromotionMetricSummary:
    balanced_score_mean: float
    coverage_mean: float
    safety_events_mean: float
    recovery_events_mean: float
    path_length_mean: float
    switch_rate_mean: float
    map_quality_mean: float


@dataclass(frozen=True)
class PromotionGateConfig:
    min_score_improvement: float = 0.0
    min_coverage_delta: float = 0.0
    max_safety_event_delta: float = 0.0
    max_recovery_event_delta: float = 1.0
    max_path_length_delta: float = 10.0
    max_switch_rate_delta: float = 0.1
    min_map_quality_delta: float = -0.01

    def __post_init__(self) -> None:
        for field_name in (
            "min_score_improvement",
            "min_coverage_delta",
            "max_safety_event_delta",
            "max_recovery_event_delta",
            "max_path_length_delta",
            "max_switch_rate_delta",
            "min_map_quality_delta",
        ):
            _as_finite_real(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class PromotionReport:
    promoted: bool
    score_delta: float
    coverage_delta: float
    regressions: tuple[str, ...]


def _as_finite_real(value: object, field_name: str = "metric values") -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a finite real number")
    numeric_value = float(value)
    if not isfinite(numeric_value):
        raise ValueError(f"{field_name} must be a finite real number")
    return numeric_value


def evaluate_promotion(
    baseline: PromotionMetricSummary,
    candidate: PromotionMetricSummary,
    config: PromotionGateConfig,
) -> PromotionReport:
    score_delta = _as_finite_real(candidate.balanced_score_mean) - _as_finite_real(baseline.balanced_score_mean)
    coverage_delta = _as_finite_real(candidate.coverage_mean) - _as_finite_real(baseline.coverage_mean)
    safety_event_delta = _as_finite_real(candidate.safety_events_mean) - _as_finite_real(baseline.safety_events_mean)
    recovery_event_delta = _as_finite_real(candidate.recovery_events_mean) - _as_finite_real(baseline.recovery_events_mean)
    path_length_delta = _as_finite_real(candidate.path_length_mean) - _as_finite_real(baseline.path_length_mean)
    switch_rate_delta = _as_finite_real(candidate.switch_rate_mean) - _as_finite_real(baseline.switch_rate_mean)
    map_quality_delta = _as_finite_real(candidate.map_quality_mean) - _as_finite_real(baseline.map_quality_mean)

    regressions: list[str] = []
    if score_delta < config.min_score_improvement:
        regressions.append("score_improvement_too_small")
    if coverage_delta < config.min_coverage_delta:
        regressions.append("coverage_regressed")
    if safety_event_delta > config.max_safety_event_delta:
        regressions.append("safety_events_regressed")
    if recovery_event_delta > config.max_recovery_event_delta:
        regressions.append("recovery_events_regressed")
    if path_length_delta > config.max_path_length_delta:
        regressions.append("path_length_regressed")
    if switch_rate_delta > config.max_switch_rate_delta:
        regressions.append("switch_rate_regressed")
    if map_quality_delta < config.min_map_quality_delta:
        regressions.append("map_quality_regressed")

    return PromotionReport(
        promoted=not regressions,
        score_delta=score_delta,
        coverage_delta=coverage_delta,
        regressions=tuple(regressions),
    )


__all__ = [
    "PromotionGateConfig",
    "PromotionMetricSummary",
    "PromotionReport",
    "evaluate_promotion",
]
