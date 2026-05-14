from __future__ import annotations

from collections.abc import Callable

from .registry import SkillContract, SkillRegistry
from .types import GateResult, SkillAuthority, SkillProposal, SkillState, SkillTermination

_VERSION = "1.0"


def _proposal(
    skill_id: str,
    *,
    target: tuple[float, float, float] | None,
    predicted_coverage_gain: float,
    predicted_frontier_delta: float,
    travel_cost: float,
    risk: float,
    connectivity_impact: float,
    map_quality_impact: float,
    min_commitment_steps: int,
    confidence: float,
    reason_codes: tuple[str, ...],
) -> SkillProposal:
    return SkillProposal(
        skill_id=skill_id,
        skill_version=_VERSION,
        target=target,
        predicted_coverage_gain=predicted_coverage_gain,
        predicted_frontier_delta=predicted_frontier_delta,
        travel_cost=travel_cost,
        risk=risk,
        connectivity_impact=connectivity_impact,
        map_quality_impact=map_quality_impact,
        min_commitment_steps=min_commitment_steps,
        cancellation_triggers=("precondition_invalidated",),
        confidence=confidence,
        reason_codes=reason_codes,
    )


def _frontier_precondition(skill_id: str) -> Callable[[SkillState], GateResult]:
    def precondition(state: SkillState) -> GateResult:
        eligible = state.frontier_count > 0
        reasons = () if eligible else ("no_frontiers",)
        return GateResult(skill_id=skill_id, eligible=eligible, reasons=reasons)

    return precondition


def _stuck_precondition(state: SkillState) -> GateResult:
    eligible = state.is_stuck
    reasons = () if eligible else ("not_stuck",)
    return GateResult(skill_id="stuck_recovery", eligible=eligible, reasons=reasons)


def _team_precondition(skill_id: str) -> Callable[[SkillState], GateResult]:
    def precondition(state: SkillState) -> GateResult:
        eligible = state.robot_count >= 2
        reasons = () if eligible else ("single_robot",)
        return GateResult(skill_id=skill_id, eligible=eligible, reasons=reasons)

    return precondition


def _loop_closure_precondition(state: SkillState) -> GateResult:
    reasons: list[str] = []
    if state.map_quality_health >= 0.9:
        reasons.append("map_quality_sufficient")
    if state.frontier_count <= 0:
        reasons.append("no_frontiers")
    return GateResult(
        skill_id="loop_closure_probe",
        eligible=not reasons,
        reasons=tuple(reasons),
    )


def _frontier_pursuit(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "frontier_pursuit",
            target=(1.0, 0.0, 0.0),
            predicted_coverage_gain=0.6,
            predicted_frontier_delta=1.0,
            travel_cost=1.0,
            risk=0.1,
            connectivity_impact=0.0,
            map_quality_impact=0.0,
            min_commitment_steps=2,
            confidence=0.8,
            reason_codes=("frontier_available",),
        ),
    )


def _coverage_sweep(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "coverage_sweep",
            target=(0.0, 1.0, 0.0),
            predicted_coverage_gain=0.5,
            predicted_frontier_delta=0.6,
            travel_cost=1.2,
            risk=0.15,
            connectivity_impact=0.0,
            map_quality_impact=0.0,
            min_commitment_steps=3,
            confidence=0.7,
            reason_codes=("coverage_growth",),
        ),
    )


def _replan(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "replan",
            target=None,
            predicted_coverage_gain=0.1,
            predicted_frontier_delta=0.2,
            travel_cost=0.2,
            risk=0.0,
            connectivity_impact=0.1,
            map_quality_impact=0.0,
            min_commitment_steps=1,
            confidence=0.6,
            reason_codes=("replan_after_progress",),
        ),
    )


def _stuck_recovery(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "stuck_recovery",
            target=None,
            predicted_coverage_gain=0.0,
            predicted_frontier_delta=0.0,
            travel_cost=0.3,
            risk=0.05,
            connectivity_impact=0.1,
            map_quality_impact=0.0,
            min_commitment_steps=1,
            confidence=0.95,
            reason_codes=("stuck",),
        ),
    )


def _viewpoint_shift(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "viewpoint_shift",
            target=(0.5, 0.5, 0.0),
            predicted_coverage_gain=0.2,
            predicted_frontier_delta=0.4,
            travel_cost=0.8,
            risk=0.1,
            connectivity_impact=0.0,
            map_quality_impact=0.1,
            min_commitment_steps=2,
            confidence=0.65,
            reason_codes=("improve_visibility",),
        ),
    )


def _robot_deconflict(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "robot_deconflict",
            target=(0.0, 0.0, 0.0),
            predicted_coverage_gain=0.0,
            predicted_frontier_delta=0.0,
            travel_cost=0.4,
            risk=0.05,
            connectivity_impact=0.3,
            map_quality_impact=0.0,
            min_commitment_steps=1,
            confidence=0.9,
            reason_codes=("multi_robot_coordination",),
        ),
    )


def _relay_or_rendezvous(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "relay_or_rendezvous",
            target=(1.0, 1.0, 0.0),
            predicted_coverage_gain=0.1,
            predicted_frontier_delta=0.1,
            travel_cost=0.9,
            risk=0.08,
            connectivity_impact=0.4,
            map_quality_impact=0.0,
            min_commitment_steps=2,
            confidence=0.72,
            reason_codes=("maintain_team_connectivity",),
        ),
    )


def _loop_closure_probe(state: SkillState) -> tuple[SkillProposal, ...]:
    return (
        _proposal(
            "loop_closure_probe",
            target=(0.0, 0.0, 0.0),
            predicted_coverage_gain=0.0,
            predicted_frontier_delta=0.2,
            travel_cost=0.5,
            risk=0.12,
            connectivity_impact=0.0,
            map_quality_impact=0.3,
            min_commitment_steps=2,
            confidence=0.68,
            reason_codes=("map_quality_degraded",),
        ),
    )


def create_default_skill_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            SkillContract(
                skill_id="frontier_pursuit",
                version=_VERSION,
                purpose="Pursue the best available frontier to advance coverage.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_frontier_precondition("frontier_pursuit"),
                propose=_frontier_pursuit,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE, SkillTermination.TIMEOUT),
                failure_modes=("no_frontiers", "blocked_path", "loss_of_progress"),
                required_telemetry=("frontier_count", "mean_frontier_distance", "coverage_pct"),
                required_metrics=("coverage_gain", "frontier_delta", "travel_cost"),
            ),
            SkillContract(
                skill_id="coverage_sweep",
                version=_VERSION,
                purpose="Bias motion toward broader coverage when frontiers remain available.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_frontier_precondition("coverage_sweep"),
                propose=_coverage_sweep,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.TIMEOUT, SkillTermination.ECONOMIC),
                failure_modes=("no_frontiers", "coverage_plateau", "path_reuse"),
                required_telemetry=("coverage_pct", "recent_coverage_delta", "frontier_count"),
                required_metrics=("coverage_gain", "duplicate_coverage_delta", "future_affordance_gain"),
            ),
            SkillContract(
                skill_id="replan",
                version=_VERSION,
                purpose="Refresh the local plan when recent progress suggests stale route choices.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_frontier_precondition("replan"),
                propose=_replan,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE),
                failure_modes=("stale_frontier_model", "planner_conflict"),
                required_telemetry=("recent_coverage_delta", "no_progress_steps", "frontier_count"),
                required_metrics=("coverage_gain", "connectivity_delta"),
            ),
            SkillContract(
                skill_id="stuck_recovery",
                version=_VERSION,
                purpose="Recover mobility when the robot is stuck or blocked.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_stuck_precondition,
                propose=_stuck_recovery,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE, SkillTermination.SAFETY),
                failure_modes=("not_stuck", "recovery_failed", "safety_interlock"),
                required_telemetry=("is_stuck", "blocked_path_count", "no_progress_steps"),
                required_metrics=("recovery_events", "travel_cost"),
            ),
            SkillContract(
                skill_id="viewpoint_shift",
                version=_VERSION,
                purpose="Adjust pose to improve sensing geometry around nearby work.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_frontier_precondition("viewpoint_shift"),
                propose=_viewpoint_shift,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.TIMEOUT),
                failure_modes=("no_frontiers", "visibility_not_improved"),
                required_telemetry=("mean_frontier_distance", "coverage_pct", "map_quality_health"),
                required_metrics=("coverage_gain", "map_quality_delta"),
            ),
            SkillContract(
                skill_id="robot_deconflict",
                version=_VERSION,
                purpose="Separate nearby robots to reduce interference and duplicate work.",
                authority=(SkillAuthority.CHOOSE_TEAM_ASSIGNMENT,),
                precondition=_team_precondition("robot_deconflict"),
                propose=_robot_deconflict,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.COORDINATION),
                failure_modes=("single_robot", "team_deadlock"),
                required_telemetry=("robot_count", "idle_robot_count", "overlap_score"),
                required_metrics=("connectivity_delta", "duplicate_coverage_delta"),
            ),
            SkillContract(
                skill_id="relay_or_rendezvous",
                version=_VERSION,
                purpose="Coordinate robot movement to sustain communication or meet at a waypoint.",
                authority=(SkillAuthority.CHOOSE_TEAM_ASSIGNMENT,),
                precondition=_team_precondition("relay_or_rendezvous"),
                propose=_relay_or_rendezvous,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.COORDINATION),
                failure_modes=("single_robot", "relay_failure"),
                required_telemetry=("robot_count", "connectivity_health", "idle_robot_count"),
                required_metrics=("connectivity_delta", "future_affordance_gain"),
            ),
            SkillContract(
                skill_id="loop_closure_probe",
                version=_VERSION,
                purpose="Probe a likely loop-closure opportunity when map quality weakens.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=_loop_closure_precondition,
                propose=_loop_closure_probe,
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE, SkillTermination.TIMEOUT),
                failure_modes=("map_quality_sufficient", "no_frontiers", "loop_not_found"),
                required_telemetry=("map_quality_health", "frontier_count", "coverage_pct"),
                required_metrics=("map_quality_delta", "coverage_gain"),
            ),
        ]
    )


__all__ = ["create_default_skill_registry"]
