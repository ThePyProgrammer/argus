from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SkillTermination(str, Enum):
    success = "success"
    failure = "failure"
    timeout = "timeout"
    economic = "economic"
    coordination = "coordination"
    safety = "safety"
    precondition_invalidated = "precondition_invalidated"
    baseline_fallback = "baseline_fallback"
    operator_override = "operator_override"

    SUCCESS = success
    FAILURE = failure
    TIMEOUT = timeout
    ECONOMIC = economic
    COORDINATION = coordination
    SAFETY = safety
    PRECONDITION_INVALIDATED = precondition_invalidated
    BASELINE_FALLBACK = baseline_fallback
    OPERATOR_OVERRIDE = operator_override


class SkillAuthority(str, Enum):
    choose_skill = "choose_skill"
    choose_parameter_profile = "choose_parameter_profile"
    choose_bounded_sequence = "choose_bounded_sequence"
    choose_team_assignment = "choose_team_assignment"

    CHOOSE_SKILL = choose_skill
    CHOOSE_PARAMETER_PROFILE = choose_parameter_profile
    CHOOSE_BOUNDED_SEQUENCE = choose_bounded_sequence
    CHOOSE_TEAM_ASSIGNMENT = choose_team_assignment


@dataclass(frozen=True)
class SkillParameterProfile:
    profile_id: str
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"profile_id": self.profile_id, "values": dict(self.values)}


@dataclass(frozen=True)
class GateResult:
    skill_id: str
    eligible: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "eligible": self.eligible,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class SkillState:
    coverage_pct: float
    recent_coverage_delta: float
    frontier_count: int
    mean_frontier_distance: float
    largest_frontier_size: int
    robot_id: str
    robot_count: int
    is_stuck: bool
    no_progress_steps: int
    blocked_path_count: int
    recent_skill_ids: tuple[str, ...] = ()
    recent_termination_reasons: tuple[SkillTermination, ...] = ()
    scenario_id: str | None = None
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["recent_skill_ids"] = list(self.recent_skill_ids)
        payload["recent_termination_reasons"] = [reason.value for reason in self.recent_termination_reasons]
        return payload


@dataclass(frozen=True)
class SkillProposal:
    skill_id: str
    skill_version: str
    target: tuple[float, ...]
    predicted_coverage_gain: float
    predicted_frontier_delta: float
    travel_cost: float
    risk: float
    connectivity_impact: float
    map_quality_impact: float
    min_commitment_steps: int
    cancellation_triggers: tuple[str, ...] = ()
    confidence: float = 0.0
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "target": list(self.target),
            "predicted_coverage_gain": self.predicted_coverage_gain,
            "predicted_frontier_delta": self.predicted_frontier_delta,
            "travel_cost": self.travel_cost,
            "risk": self.risk,
            "connectivity_impact": self.connectivity_impact,
            "map_quality_impact": self.map_quality_impact,
            "min_commitment_steps": self.min_commitment_steps,
            "cancellation_triggers": list(self.cancellation_triggers),
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True)
class SkillDecision:
    selected_skill_id: str
    selected_proposal: SkillProposal | None
    parameter_profile: SkillParameterProfile | None
    confidence: float
    reason_codes: tuple[str, ...] = ()
    fallback_skill_id: str | None = None
    rejected_candidates: tuple[GateResult, ...] = ()

    @classmethod
    def baseline(cls, reason_codes: tuple[str, ...]) -> SkillDecision:
        return cls(
            selected_skill_id="baseline",
            selected_proposal=None,
            parameter_profile=None,
            confidence=0.0,
            reason_codes=reason_codes,
            fallback_skill_id="baseline",
            rejected_candidates=(),
        )

    @property
    def uses_baseline(self) -> bool:
        return self.selected_skill_id == self.fallback_skill_id or self.selected_skill_id == "baseline"

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_skill_id": self.selected_skill_id,
            "selected_proposal": None if self.selected_proposal is None else self.selected_proposal.to_dict(),
            "parameter_profile": None if self.parameter_profile is None else self.parameter_profile.to_dict(),
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "fallback_skill_id": self.fallback_skill_id,
            "rejected_candidates": [candidate.to_dict() for candidate in self.rejected_candidates],
        }


@dataclass(frozen=True)
class SkillOutcomeVector:
    coverage_gain: float
    frontier_delta: float
    path_length: float
    command_effort: float
    safety_events: int
    recovery_events: int
    duplicate_coverage_delta: float
    connectivity_delta: float
    map_quality_delta: float
    future_affordance_gain: float
    termination: SkillTermination
    fallback_used: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_gain": self.coverage_gain,
            "frontier_delta": self.frontier_delta,
            "path_length": self.path_length,
            "command_effort": self.command_effort,
            "safety_events": self.safety_events,
            "recovery_events": self.recovery_events,
            "duplicate_coverage_delta": self.duplicate_coverage_delta,
            "connectivity_delta": self.connectivity_delta,
            "map_quality_delta": self.map_quality_delta,
            "future_affordance_gain": self.future_affordance_gain,
            "termination": self.termination.value,
            "fallback_used": self.fallback_used,
        }

    def balanced_score(self, weights: dict[str, float]) -> float:
        payload = self.to_dict()
        score = 0.0
        for key, weight in weights.items():
            value = payload.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            score += float(weight) * float(value)
        return score
