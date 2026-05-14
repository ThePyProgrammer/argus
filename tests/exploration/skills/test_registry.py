from __future__ import annotations

import pytest

from src.exploration.skills.registry import SkillContract, SkillRegistry
from src.exploration.skills.types import GateResult, SkillAuthority, SkillProposal, SkillState, SkillTermination


def _state(frontier_count: int = 1, is_stuck: bool = False) -> SkillState:
    return SkillState(
        coverage_pct=10.0,
        recent_coverage_delta=0.5,
        frontier_count=frontier_count,
        mean_frontier_distance=2.0,
        largest_frontier_size=8,
        robot_id="robot-1",
        robot_count=1,
        is_stuck=is_stuck,
        no_progress_steps=0,
        blocked_path_count=0,
        recent_termination_reasons=(SkillTermination.SUCCESS,),
    )


def _proposal(skill_id: str) -> SkillProposal:
    return SkillProposal(
        skill_id=skill_id,
        skill_version="1.0",
        target=(1.0, 0.0, 0.0),
        predicted_coverage_gain=0.5,
        predicted_frontier_delta=1.0,
        travel_cost=1.0,
        risk=0.0,
        connectivity_impact=0.0,
        map_quality_impact=0.0,
        min_commitment_steps=3,
        cancellation_triggers=(),
        confidence=0.8,
        reason_codes=("test",),
    )


def test_registry_rejects_duplicate_skill_ids() -> None:
    contract = SkillContract(
        skill_id="frontier_pursuit",
        version="1.0",
        purpose="Choose a frontier",
        authority=(SkillAuthority.CHOOSE_SKILL,),
        precondition=lambda state: GateResult("frontier_pursuit", True),
        propose=lambda state: (_proposal("frontier_pursuit"),),
        termination_conditions=(SkillTermination.SUCCESS,),
        failure_modes=("no_frontiers",),
        required_telemetry=("coverage_pct",),
        required_metrics=("coverage_gain",),
    )

    registry = SkillRegistry()
    registry.register(contract)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(contract)


def test_registry_collects_only_eligible_proposals() -> None:
    eligible = SkillContract(
        skill_id="frontier_pursuit",
        version="1.0",
        purpose="Choose a frontier",
        authority=(SkillAuthority.CHOOSE_SKILL,),
        precondition=lambda state: GateResult("frontier_pursuit", state.frontier_count > 0),
        propose=lambda state: (_proposal("frontier_pursuit"),),
        termination_conditions=(SkillTermination.SUCCESS,),
        failure_modes=("no_frontiers",),
        required_telemetry=("coverage_pct",),
        required_metrics=("coverage_gain",),
    )
    ineligible = SkillContract(
        skill_id="stuck_recovery",
        version="1.0",
        purpose="Recover when stuck",
        authority=(SkillAuthority.CHOOSE_SKILL,),
        precondition=lambda state: GateResult("stuck_recovery", state.is_stuck, ("robot_not_stuck",)),
        propose=lambda state: (_proposal("stuck_recovery"),),
        termination_conditions=(SkillTermination.SUCCESS,),
        failure_modes=("recovery_failed",),
        required_telemetry=("is_stuck",),
        required_metrics=("recovery_events",),
    )

    registry = SkillRegistry([eligible, ineligible])
    proposals, gates = registry.proposals_for(_state(frontier_count=2, is_stuck=False))

    assert [proposal.skill_id for proposal in proposals] == ["frontier_pursuit"]
    assert [gate.to_dict() for gate in gates] == [
        {"skill_id": "frontier_pursuit", "eligible": True, "reasons": []},
        {"skill_id": "stuck_recovery", "eligible": False, "reasons": ["robot_not_stuck"]},
    ]


def test_contract_validation_requires_option_like_fields() -> None:
    with pytest.raises(ValueError, match="purpose"):
        SkillContract(
            skill_id="frontier_pursuit",
            version="1.0",
            purpose="",
            authority=(SkillAuthority.CHOOSE_SKILL,),
            precondition=lambda state: GateResult("frontier_pursuit", True),
            propose=lambda state: (_proposal("frontier_pursuit"),),
            termination_conditions=(SkillTermination.SUCCESS,),
            failure_modes=("no_frontiers",),
            required_telemetry=("coverage_pct",),
            required_metrics=("coverage_gain",),
        )
