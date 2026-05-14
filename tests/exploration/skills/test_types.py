from __future__ import annotations

import pytest

from src.exploration.skills.types import (
    GateResult,
    SkillAuthority,
    SkillDecision,
    SkillOutcomeVector,
    SkillParameterProfile,
    SkillProposal,
    SkillState,
    SkillTermination,
)


def test_skill_state_serializes_to_plain_dict() -> None:
    state = SkillState(
        coverage_pct=12.5,
        recent_coverage_delta=1.25,
        frontier_count=3,
        mean_frontier_distance=2.5,
        largest_frontier_size=12,
        robot_id="robot-1",
        robot_count=2,
        is_stuck=False,
        no_progress_steps=0,
        blocked_path_count=1,
        recent_skill_ids=("frontier_pursuit",),
        recent_termination_reasons=(SkillTermination.SUCCESS,),
        scenario_id="office",
        seed=7,
    )

    payload = state.to_dict()

    assert payload["coverage_pct"] == 12.5
    assert payload["recent_skill_ids"] == ["frontier_pursuit"]
    assert payload["recent_termination_reasons"] == ["success"]
    assert payload["scenario_id"] == "office"
    assert payload["seed"] == 7


def test_skill_state_rejects_invalid_bounds() -> None:
    for kwargs, expected_message in [
        ({"coverage_pct": -0.1}, "coverage_pct must be between 0.0 and 100.0"),
        ({"coverage_pct": 100.1}, "coverage_pct must be between 0.0 and 100.0"),
        ({"robot_count": -1}, "robot_count must be a non-negative integer"),
        ({"no_progress_steps": -1}, "no_progress_steps must be a non-negative integer"),
        ({"blocked_path_count": -1}, "blocked_path_count must be a non-negative integer"),
    ]:
        base_kwargs = dict(
            coverage_pct=12.5,
            recent_coverage_delta=1.25,
            frontier_count=3,
            mean_frontier_distance=2.5,
            largest_frontier_size=12,
            robot_id="robot-1",
            robot_count=2,
            is_stuck=False,
            no_progress_steps=0,
            blocked_path_count=1,
        )
        base_kwargs.update(kwargs)

        with pytest.raises((TypeError, ValueError), match=expected_message):
            SkillState(**base_kwargs)


def test_skill_state_rejects_string_termination_values() -> None:
    with pytest.raises(TypeError, match="recent_termination_reasons must be a SkillTermination instance"):
        SkillState(
            coverage_pct=12.5,
            recent_coverage_delta=1.25,
            frontier_count=3,
            mean_frontier_distance=2.5,
            largest_frontier_size=12,
            robot_id="robot-1",
            robot_count=2,
            is_stuck=False,
            no_progress_steps=0,
            blocked_path_count=1,
            recent_termination_reasons=("success",),
        )


def test_skill_proposal_contains_audit_fields() -> None:
    proposal = SkillProposal(
        skill_id="frontier_pursuit",
        skill_version="1.0",
        target=(1.0, 2.0, 0.0),
        predicted_coverage_gain=0.4,
        predicted_frontier_delta=2.0,
        travel_cost=3.0,
        risk=0.1,
        connectivity_impact=0.0,
        map_quality_impact=0.2,
        min_commitment_steps=5,
        cancellation_triggers=("precondition_invalidated",),
        confidence=0.8,
        reason_codes=("nearest_high_value_frontier",),
    )

    payload = proposal.to_dict()

    assert payload["skill_id"] == "frontier_pursuit"
    assert payload["target"] == [1.0, 2.0, 0.0]
    assert payload["cancellation_triggers"] == ["precondition_invalidated"]
    assert payload["reason_codes"] == ["nearest_high_value_frontier"]


def test_skill_proposal_rejects_invalid_bounds() -> None:
    base_kwargs = dict(
        skill_id="frontier_pursuit",
        skill_version="1.0",
        target=(1.0, 2.0, 0.0),
        predicted_coverage_gain=0.4,
        predicted_frontier_delta=2.0,
        travel_cost=3.0,
        risk=0.1,
        connectivity_impact=0.0,
        map_quality_impact=0.2,
        min_commitment_steps=5,
        cancellation_triggers=(),
        confidence=0.8,
        reason_codes=(),
    )

    for field_name, value, expected_message in [
        ("risk", -0.1, "risk must be between 0.0 and 1.0"),
        ("risk", 1.1, "risk must be between 0.0 and 1.0"),
        ("risk", float("nan"), "risk must be finite and between 0.0 and 1.0"),
        ("confidence", -0.1, "confidence must be between 0.0 and 1.0"),
        ("confidence", 1.1, "confidence must be between 0.0 and 1.0"),
        ("confidence", float("nan"), "confidence must be finite and between 0.0 and 1.0"),
        ("min_commitment_steps", -1, "min_commitment_steps must be a non-negative integer"),
    ]:
        kwargs = dict(base_kwargs)
        kwargs[field_name] = value

        with pytest.raises((TypeError, ValueError), match=expected_message):
            SkillProposal(**kwargs)


def test_skill_decision_records_selected_and_rejected_candidates() -> None:
    selected = SkillProposal(
        skill_id="frontier_pursuit",
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
        confidence=0.9,
        reason_codes=("best_score",),
    )

    decision = SkillDecision(
        selected_skill_id="frontier_pursuit",
        selected_proposal=selected,
        parameter_profile=SkillParameterProfile(profile_id="default", values={"goal_strategy": "nearest"}),
        confidence=0.9,
        reason_codes=("best_score",),
        fallback_skill_id="baseline",
        rejected_candidates=(GateResult(skill_id="coverage_sweep", eligible=False, reasons=("no_frontiers",)),),
    )

    payload = decision.to_dict()

    assert payload["selected_skill_id"] == "frontier_pursuit"
    assert payload["selected_proposal"]["skill_id"] == "frontier_pursuit"
    assert payload["parameter_profile"]["profile_id"] == "default"
    assert payload["rejected_candidates"] == [
        {"skill_id": "coverage_sweep", "eligible": False, "reasons": ["no_frontiers"]}
    ]


def test_outcome_vector_keeps_score_projection_separate() -> None:
    outcome = SkillOutcomeVector(
        coverage_gain=1.0,
        frontier_delta=-2.0,
        path_length=4.0,
        command_effort=2.0,
        safety_events=0,
        recovery_events=1,
        duplicate_coverage_delta=-0.5,
        connectivity_delta=0.0,
        map_quality_delta=0.2,
        future_affordance_gain=0.3,
        termination=SkillTermination.SUCCESS,
        fallback_used=False,
    )

    assert outcome.balanced_score(weights={"coverage_gain": 2.0, "path_length": -0.25}) == 1.0
    assert outcome.to_dict()["termination"] == "success"


def test_outcome_vector_rejects_invalid_counts_and_strings() -> None:
    base_kwargs = dict(
        coverage_gain=1.0,
        frontier_delta=-2.0,
        path_length=4.0,
        command_effort=2.0,
        safety_events=0,
        recovery_events=1,
        duplicate_coverage_delta=-0.5,
        connectivity_delta=0.0,
        map_quality_delta=0.2,
        future_affordance_gain=0.3,
        termination=SkillTermination.SUCCESS,
        fallback_used=False,
    )

    for field_name, value, expected_message in [
        ("safety_events", -1, "safety_events must be a non-negative integer"),
        ("recovery_events", -1, "recovery_events must be a non-negative integer"),
        ("termination", "success", "termination must be a SkillTermination instance"),
    ]:
        kwargs = dict(base_kwargs)
        kwargs[field_name] = value

        with pytest.raises((TypeError, ValueError), match=expected_message):
            SkillOutcomeVector(**kwargs)


def test_authority_enum_prevents_low_level_control_authority() -> None:
    assert [authority.value for authority in SkillAuthority] == [
        "choose_skill",
        "choose_parameter_profile",
        "choose_bounded_sequence",
        "choose_team_assignment",
    ]


def test_parameter_profile_detaches_mutable_mapping_inputs() -> None:
    values = {"goal_strategy": "nearest", "nested": {"window": [1, 2]}}
    profile = SkillParameterProfile(profile_id="default", values=values)

    values["goal_strategy"] = "global"
    values["nested"]["window"].append(3)

    assert profile.to_dict()["values"] == {"goal_strategy": "nearest", "nested": {"window": [1, 2]}}


def test_parameter_profile_to_dict_returns_detached_nested_values() -> None:
    profile = SkillParameterProfile(profile_id="default", values={"nested": {"window": [1, 2]}})

    payload = profile.to_dict()
    payload["values"]["nested"]["window"].append(3)

    assert profile.to_dict()["values"] == {"nested": {"window": [1, 2]}}
