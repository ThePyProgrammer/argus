from __future__ import annotations

import pytest

from src.exploration.config import ExplorationConfig
from src.exploration.skills.selector import GatedSkillSelector, SkillSelectorConfig
from src.exploration.skills.types import GateResult, SkillProposal, SkillState, SkillTermination


def _state(is_stuck: bool = False, no_progress_steps: int = 0) -> SkillState:
    return SkillState(
        coverage_pct=15.0,
        recent_coverage_delta=0.2,
        frontier_count=3,
        mean_frontier_distance=2.0,
        largest_frontier_size=10,
        robot_id="robot-1",
        robot_count=1,
        is_stuck=is_stuck,
        no_progress_steps=no_progress_steps,
        blocked_path_count=0,
    )


def _proposal(
    skill_id: str,
    confidence: float,
    coverage_gain: float,
    travel_cost: float,
    risk: float = 0.0,
    reason_codes: tuple[str, ...] = ("candidate",),
) -> SkillProposal:
    return SkillProposal(
        skill_id=skill_id,
        skill_version="1.0",
        target=(1.0, 0.0, 0.0),
        predicted_coverage_gain=coverage_gain,
        predicted_frontier_delta=1.0,
        travel_cost=travel_cost,
        risk=risk,
        connectivity_impact=0.0,
        map_quality_impact=0.0,
        min_commitment_steps=3,
        cancellation_triggers=(),
        confidence=confidence,
        reason_codes=reason_codes,
    )


def test_exploration_skill_learning_is_disabled_by_default() -> None:
    config = ExplorationConfig()

    assert config.skill_learning_enabled is False
    assert config.skill_learning_shadow_mode is False
    assert config.skill_learning_min_confidence == 0.6
    assert config.skill_learning_min_dwell_steps == 3
    assert config.skill_learning_max_failures_before_baseline == 3


def test_selector_returns_baseline_when_no_candidates() -> None:
    selector = GatedSkillSelector()
    gates = (GateResult("frontier_pursuit", False, ("shadow_disabled",)),)

    decision = selector.select(_state(), proposals=(), gates=gates)

    assert decision.uses_baseline
    assert decision.reason_codes == ("no_eligible_proposals",)
    assert decision.rejected_candidates == gates


def test_selector_rejects_low_confidence_candidates() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_confidence=0.7))
    gates = (GateResult("frontier_pursuit", True),)

    decision = selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.5, 1.0, 1.0),), gates=gates)

    assert decision.uses_baseline
    assert decision.reason_codes == ("low_confidence",)
    assert decision.rejected_candidates == gates


def test_selector_prefers_stuck_recovery_when_robot_is_stuck() -> None:
    selector = GatedSkillSelector()

    decision = selector.select(
        _state(is_stuck=True),
        proposals=(
            _proposal("frontier_pursuit", 0.9, 3.0, 1.0),
            _proposal("stuck_recovery", 0.8, 0.0, 0.5),
        ),
        gates=(),
    )

    assert decision.selected_skill_id == "stuck_recovery"
    assert "stuck_priority" in decision.reason_codes


def test_selector_scores_gain_cost_and_risk() -> None:
    selector = GatedSkillSelector()

    decision = selector.select(
        _state(),
        proposals=(
            _proposal("risky", 0.9, 5.0, 1.0, risk=1.0),
            _proposal("efficient", 0.9, 2.0, 0.5, risk=0.0),
        ),
        gates=(),
    )

    assert decision.selected_skill_id == "efficient"


def test_selector_filters_ineligible_gated_proposals() -> None:
    selector = GatedSkillSelector()
    gates = (
        GateResult("blocked", False, ("unsafe",)),
        GateResult("allowed", True),
    )

    decision = selector.select(
        _state(),
        proposals=(
            _proposal("blocked", 0.9, 10.0, 0.1),
            _proposal("allowed", 0.9, 1.0, 0.1),
        ),
        gates=gates,
    )

    assert decision.selected_skill_id == "allowed"
    assert decision.rejected_candidates == gates


def test_selector_degrades_to_baseline_after_repeated_failure() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(max_failures_before_baseline=2))
    selector.record_termination("frontier_pursuit", SkillTermination.FAILURE)
    selector.record_termination("frontier_pursuit", SkillTermination.FAILURE)

    decision = selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    assert decision.uses_baseline
    assert decision.reason_codes == ("episode_degraded_to_baseline",)


def test_selector_respects_minimum_dwell_for_non_safety_switches() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_dwell_steps=4))
    selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    decision = selector.select(
        _state(),
        proposals=(_proposal("coverage_sweep", 0.9, 4.0, 0.5),),
        gates=(GateResult("coverage_sweep", True),),
    )

    assert decision.uses_baseline
    assert decision.reason_codes == ("minimum_dwell_active",)


def test_selector_minimum_dwell_eventually_expires() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_dwell_steps=2))
    selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    first_blocked = selector.select(_state(), proposals=(_proposal("coverage_sweep", 0.9, 4.0, 0.5),), gates=())
    second_blocked = selector.select(_state(), proposals=(_proposal("coverage_sweep", 0.9, 4.0, 0.5),), gates=())
    allowed = selector.select(_state(), proposals=(_proposal("coverage_sweep", 0.9, 4.0, 0.5),), gates=())

    assert first_blocked.reason_codes == ("minimum_dwell_active",)
    assert second_blocked.reason_codes == ("minimum_dwell_active",)
    assert allowed.selected_skill_id == "coverage_sweep"


def test_selector_non_safety_stuck_recovery_respects_minimum_dwell() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_dwell_steps=4))
    selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    decision = selector.select(
        _state(),
        proposals=(_proposal("stuck_recovery", 0.9, 0.0, 0.1),),
        gates=(),
    )

    assert decision.uses_baseline
    assert decision.reason_codes == ("minimum_dwell_active",)


def test_selector_safety_reason_code_bypasses_minimum_dwell() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_dwell_steps=4))
    selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    decision = selector.select(
        _state(),
        proposals=(_proposal("hazard_response", 0.9, 0.0, 0.1, reason_codes=("safety",)),),
        gates=(),
    )

    assert decision.selected_skill_id == "hazard_response"
    assert decision.reason_codes == ("safety",)



def test_selector_emergency_reason_code_bypasses_minimum_dwell() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_dwell_steps=4))
    selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.9, 2.0, 1.0),), gates=())

    decision = selector.select(
        _state(),
        proposals=(_proposal("emergency_stop", 0.9, 0.0, 0.1, reason_codes=("emergency",)),),
        gates=(),
    )

    assert decision.selected_skill_id == "emergency_stop"
    assert decision.reason_codes == ("emergency",)


@pytest.mark.parametrize(
    ("field_name", "value", "exception_type"),
    (
        ("min_confidence", -0.1, ValueError),
        ("min_confidence", 1.1, ValueError),
        ("min_confidence", float("nan"), ValueError),
        ("min_confidence", True, TypeError),
        ("min_dwell_steps", -1, ValueError),
        ("min_dwell_steps", 1.5, TypeError),
        ("min_dwell_steps", False, TypeError),
        ("max_failures_before_baseline", 0, ValueError),
        ("max_failures_before_baseline", 1.5, TypeError),
        ("max_failures_before_baseline", True, TypeError),
        ("coverage_gain_weight", float("inf"), ValueError),
        ("frontier_delta_weight", "heavy", TypeError),
        ("travel_cost_weight", True, TypeError),
        ("risk_weight", float("nan"), ValueError),
        ("connectivity_weight", object(), TypeError),
        ("map_quality_weight", float("-inf"), ValueError),
        ("stuck_recovery_bonus", None, TypeError),
    ),
)
def test_selector_config_rejects_invalid_values(field_name: str, value: object, exception_type: type[Exception]) -> None:
    with pytest.raises(exception_type, match=field_name):
        SkillSelectorConfig(**{field_name: value})
