from __future__ import annotations

import json

from src.exploration.skills.recorder import SkillOutcomeRecorder
from src.exploration.skills.types import SkillDecision, SkillOutcomeVector, SkillState, SkillTermination


def _state() -> SkillState:
    return SkillState(
        coverage_pct=10.0,
        recent_coverage_delta=1.0,
        frontier_count=2,
        mean_frontier_distance=1.5,
        largest_frontier_size=8,
        robot_id="robot-1",
        robot_count=1,
        is_stuck=False,
        no_progress_steps=0,
        blocked_path_count=0,
    )


def _outcome() -> SkillOutcomeVector:
    return SkillOutcomeVector(
        coverage_gain=1.0,
        frontier_delta=-1.0,
        path_length=2.0,
        command_effort=0.5,
        safety_events=0,
        recovery_events=0,
        duplicate_coverage_delta=0.0,
        connectivity_delta=0.0,
        map_quality_delta=0.1,
        future_affordance_gain=0.2,
        termination=SkillTermination.SUCCESS,
        fallback_used=False,
    )


def test_recorder_creates_decision_and_outcome_trace() -> None:
    recorder = SkillOutcomeRecorder(run_id="run-1", selector_version="selector-v1", skill_library_version="skills-v1")
    decision = SkillDecision.baseline(("no_eligible_proposals",))

    trace_id = recorder.record_decision(
        scenario="office",
        seed=3,
        robot_ids=("robot-1",),
        state=_state(),
        gates=(),
        decision=decision,
    )
    recorder.record_outcome(trace_id, _outcome())

    payload = recorder.records[0].to_dict()

    assert payload["run_id"] == "run-1"
    assert payload["selector_version"] == "selector-v1"
    assert payload["skill_library_version"] == "skills-v1"
    assert payload["decision"]["selected_skill_id"] == "baseline"
    assert payload["outcome"]["termination"] == "success"


def test_recorder_exports_jsonl() -> None:
    recorder = SkillOutcomeRecorder(run_id="run-1", selector_version="selector-v1", skill_library_version="skills-v1")
    trace_id = recorder.record_decision(
        scenario="office",
        seed=3,
        robot_ids=("robot-1",),
        state=_state(),
        gates=(),
        decision=SkillDecision.baseline(("no_eligible_proposals",)),
    )
    recorder.record_outcome(trace_id, _outcome())

    lines = recorder.to_jsonl().splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0])["trace_id"] == trace_id
