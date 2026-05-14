from __future__ import annotations

import numpy as np

from src.exploration.skills.executor import SkillExecutor
from src.exploration.skills.types import SkillDecision, SkillParameterProfile, SkillProposal


def _proposal(skill_id: str, target: tuple[float, float, float] | None = (2.0, 0.0, 0.0)) -> SkillProposal:
    return SkillProposal(
        skill_id=skill_id,
        skill_version="1.0",
        target=target,
        predicted_coverage_gain=1.0,
        predicted_frontier_delta=1.0,
        travel_cost=1.0,
        risk=0.0,
        connectivity_impact=0.0,
        map_quality_impact=0.0,
        min_commitment_steps=3,
        cancellation_triggers=(),
        confidence=0.9,
        reason_codes=("candidate",),
    )


def _decision(proposal: SkillProposal | None) -> SkillDecision:
    if proposal is None:
        return SkillDecision.baseline(("test",))
    return SkillDecision(
        selected_skill_id=proposal.skill_id,
        selected_proposal=proposal,
        parameter_profile=SkillParameterProfile(profile_id="default"),
        confidence=proposal.confidence,
        reason_codes=proposal.reason_codes,
        fallback_skill_id="baseline",
    )


def test_executor_returns_none_for_baseline_decision() -> None:
    executor = SkillExecutor()

    result = executor.apply(_decision(None))

    assert result.score_fn is None
    assert result.fallback_used is True
    assert result.reason_codes == ("test",)


def test_executor_rejects_targetless_frontier_skill() -> None:
    executor = SkillExecutor()

    result = executor.apply(_decision(_proposal("frontier_pursuit", target=None)))

    assert result.score_fn is None
    assert result.fallback_used is True
    assert result.termination_reason == "precondition_invalidated"


def test_executor_builds_frontier_bias_for_targeted_skill() -> None:
    executor = SkillExecutor()
    result = executor.apply(_decision(_proposal("frontier_pursuit", target=(2.0, 0.0, 0.0))))

    near_score = result.score_fn(np.array([2.0, 0.0, 0.0]))
    far_score = result.score_fn(np.array([10.0, 0.0, 0.0]))

    assert result.fallback_used is False
    assert near_score > far_score
