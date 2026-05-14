from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .types import GateResult, SkillDecision, SkillParameterProfile, SkillProposal, SkillState, SkillTermination


@dataclass(frozen=True)
class SkillSelectorConfig:
    min_confidence: float = 0.6
    coverage_gain_weight: float = 1.0
    frontier_delta_weight: float = 0.25
    travel_cost_weight: float = 0.5
    risk_weight: float = 3.0
    connectivity_weight: float = 0.5
    map_quality_weight: float = 0.5
    stuck_recovery_bonus: float = 100.0
    min_dwell_steps: int = 3
    max_failures_before_baseline: int = 3


class GatedSkillSelector:
    def __init__(self, config: SkillSelectorConfig | None = None) -> None:
        self._config = config or SkillSelectorConfig()
        self._current_skill_id: str | None = None
        self._dwell_steps = 0
        self._failure_counts: dict[str, int] = {}
        self._degraded_to_baseline = False

    def record_termination(self, skill_id: str, termination: SkillTermination) -> None:
        if termination not in {
            SkillTermination.FAILURE,
            SkillTermination.TIMEOUT,
            SkillTermination.SAFETY,
        }:
            return

        self._failure_counts[skill_id] = self._failure_counts.get(skill_id, 0) + 1
        if self._failure_counts[skill_id] >= self._config.max_failures_before_baseline:
            self._degraded_to_baseline = True

    def select(
        self,
        state: SkillState,
        *,
        proposals: Iterable[SkillProposal],
        gates: Iterable[GateResult],
    ) -> SkillDecision:
        gate_results = tuple(gates)
        proposal_candidates = tuple(proposals)

        if self._degraded_to_baseline:
            return SkillDecision.baseline(("episode_degraded_to_baseline",))

        eligible_proposals = [proposal for proposal in proposal_candidates if proposal.confidence >= self._config.min_confidence]
        if not proposal_candidates:
            return SkillDecision.baseline(("no_eligible_proposals",))
        if not eligible_proposals:
            return SkillDecision.baseline(("low_confidence",))

        best_proposal = max(eligible_proposals, key=lambda proposal: self._score(state, proposal))

        if self._should_enforce_dwell(best_proposal):
            return SkillDecision(
                selected_skill_id="baseline",
                selected_proposal=None,
                parameter_profile=None,
                confidence=0.0,
                reason_codes=("minimum_dwell_active",),
                fallback_skill_id="baseline",
                rejected_candidates=gate_results,
            )

        reason_codes = tuple(best_proposal.reason_codes)
        if state.is_stuck and best_proposal.skill_id == "stuck_recovery":
            reason_codes = reason_codes + ("stuck_priority",)

        self._update_selection(best_proposal.skill_id)
        return SkillDecision(
            selected_skill_id=best_proposal.skill_id,
            selected_proposal=best_proposal,
            parameter_profile=SkillParameterProfile(profile_id="default"),
            confidence=best_proposal.confidence,
            reason_codes=reason_codes,
            fallback_skill_id="baseline",
            rejected_candidates=gate_results,
        )

    def _score(self, state: SkillState, proposal: SkillProposal) -> float:
        score = (
            self._config.coverage_gain_weight * proposal.predicted_coverage_gain
            + self._config.frontier_delta_weight * proposal.predicted_frontier_delta
            - self._config.travel_cost_weight * proposal.travel_cost
            - self._config.risk_weight * proposal.risk
            + self._config.connectivity_weight * proposal.connectivity_impact
            + self._config.map_quality_weight * proposal.map_quality_impact
        )
        if state.is_stuck and proposal.skill_id == "stuck_recovery":
            score += self._config.stuck_recovery_bonus
        return score

    def _should_enforce_dwell(self, best_proposal: SkillProposal) -> bool:
        if self._current_skill_id is None:
            return False
        if best_proposal.skill_id == self._current_skill_id:
            return False
        if best_proposal.skill_id == "stuck_recovery":
            return False
        return self._dwell_steps < self._config.min_dwell_steps

    def _update_selection(self, skill_id: str) -> None:
        if self._current_skill_id is None:
            self._current_skill_id = skill_id
            self._dwell_steps = 0
            return

        if skill_id != self._current_skill_id:
            self._current_skill_id = skill_id
            self._dwell_steps = 0
        else:
            self._dwell_steps += 1


__all__ = ["GatedSkillSelector", "SkillSelectorConfig"]
