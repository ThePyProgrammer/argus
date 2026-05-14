from __future__ import annotations

from src.exploration.skills.library import create_default_skill_registry
from src.exploration.skills.types import SkillState, SkillTermination


def _state(
    frontier_count: int = 3,
    is_stuck: bool = False,
    robot_count: int = 1,
    map_quality_health: float = 0.5,
) -> SkillState:
    return SkillState(
        coverage_pct=25.0,
        recent_coverage_delta=0.2,
        frontier_count=frontier_count,
        mean_frontier_distance=3.0,
        largest_frontier_size=12,
        robot_id="robot-1",
        robot_count=robot_count,
        is_stuck=is_stuck,
        no_progress_steps=0,
        blocked_path_count=0,
        recent_termination_reasons=(SkillTermination.SUCCESS,),
        map_quality_health=map_quality_health,
    )


def test_default_registry_contains_initial_skill_candidates() -> None:
    registry = create_default_skill_registry()

    assert [contract.skill_id for contract in registry.all()] == [
        "frontier_pursuit",
        "coverage_sweep",
        "replan",
        "stuck_recovery",
        "viewpoint_shift",
        "robot_deconflict",
        "relay_or_rendezvous",
        "loop_closure_probe",
    ]


def test_default_frontier_state_produces_frontier_proposals() -> None:
    registry = create_default_skill_registry()

    proposals, gates = registry.proposals_for(_state(frontier_count=3, is_stuck=False, robot_count=2))

    proposal_ids = {proposal.skill_id for proposal in proposals}
    assert "frontier_pursuit" in proposal_ids
    assert "coverage_sweep" in proposal_ids
    assert "stuck_recovery" not in proposal_ids
    assert any(gate.skill_id == "stuck_recovery" and not gate.eligible for gate in gates)


def test_stuck_state_prioritizes_recovery_proposal() -> None:
    registry = create_default_skill_registry()

    proposals, gates = registry.proposals_for(_state(frontier_count=1, is_stuck=True))

    assert any(proposal.skill_id == "stuck_recovery" for proposal in proposals)
    assert any(gate.skill_id == "stuck_recovery" and gate.eligible for gate in gates)


def test_targetless_proposals_use_none_targets() -> None:
    registry = create_default_skill_registry()

    proposals, _ = registry.proposals_for(_state(frontier_count=1, is_stuck=True))
    proposal_by_id = {proposal.skill_id: proposal for proposal in proposals}

    assert proposal_by_id["replan"].target is None
    assert proposal_by_id["stuck_recovery"].target is None


def test_team_skills_require_multi_robot_state() -> None:
    registry = create_default_skill_registry()

    single_robot_proposals, _ = registry.proposals_for(_state(robot_count=1))
    multi_robot_proposals, _ = registry.proposals_for(_state(robot_count=3))

    single_robot_ids = {proposal.skill_id for proposal in single_robot_proposals}
    multi_robot_ids = {proposal.skill_id for proposal in multi_robot_proposals}

    assert "robot_deconflict" not in single_robot_ids
    assert "relay_or_rendezvous" not in single_robot_ids
    assert "robot_deconflict" in multi_robot_ids
    assert "relay_or_rendezvous" in multi_robot_ids


def test_loop_closure_probe_eligible_when_map_quality_is_low_and_frontiers_exist() -> None:
    registry = create_default_skill_registry()

    proposals, gates = registry.proposals_for(_state(frontier_count=2, map_quality_health=0.5))

    assert "loop_closure_probe" in {proposal.skill_id for proposal in proposals}
    assert any(gate.skill_id == "loop_closure_probe" and gate.eligible for gate in gates)


def test_loop_closure_probe_reports_only_no_frontiers_when_map_quality_is_low() -> None:
    registry = create_default_skill_registry()

    _, gates = registry.proposals_for(_state(frontier_count=0, map_quality_health=0.5))

    gate = next(gate for gate in gates if gate.skill_id == "loop_closure_probe")
    assert not gate.eligible
    assert gate.reasons == ("no_frontiers",)


def test_loop_closure_probe_reports_only_map_quality_when_frontiers_exist() -> None:
    registry = create_default_skill_registry()

    _, gates = registry.proposals_for(_state(frontier_count=2, map_quality_health=0.95))

    gate = next(gate for gate in gates if gate.skill_id == "loop_closure_probe")
    assert not gate.eligible
    assert gate.reasons == ("map_quality_sufficient",)
