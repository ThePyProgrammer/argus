from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from json import dumps
from uuid import uuid4

from .types import GateResult, SkillDecision, SkillOutcomeVector, SkillState


@dataclass(frozen=True)
class SkillTraceRecord:
    trace_id: str
    run_id: str
    scenario: str
    seed: int
    robot_ids: tuple[str, ...]
    selector_version: str
    skill_library_version: str
    state: dict[str, object]
    gates: tuple[dict[str, object], ...]
    decision: dict[str, object]
    outcome: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "robot_ids": list(self.robot_ids),
            "selector_version": self.selector_version,
            "skill_library_version": self.skill_library_version,
            "state": deepcopy(self.state),
            "gates": [deepcopy(gate) for gate in self.gates],
            "decision": deepcopy(self.decision),
            "outcome": None if self.outcome is None else deepcopy(self.outcome),
        }


class SkillOutcomeRecorder:
    def __init__(self, run_id: str, selector_version: str, skill_library_version: str) -> None:
        self._run_id = run_id
        self._selector_version = selector_version
        self._skill_library_version = skill_library_version
        self._records: list[SkillTraceRecord] = []

    @property
    def records(self) -> tuple[SkillTraceRecord, ...]:
        return tuple(self._records)

    def record_decision(
        self,
        *,
        scenario: str,
        seed: int,
        robot_ids: tuple[str, ...],
        state: SkillState,
        gates: tuple[GateResult, ...],
        decision: SkillDecision,
    ) -> str:
        trace_id = str(uuid4())
        self._records.append(
            SkillTraceRecord(
                trace_id=trace_id,
                run_id=self._run_id,
                scenario=scenario,
                seed=seed,
                robot_ids=tuple(robot_ids),
                selector_version=self._selector_version,
                skill_library_version=self._skill_library_version,
                state=state.to_dict(),
                gates=tuple(gate.to_dict() for gate in gates),
                decision=decision.to_dict(),
            )
        )
        return trace_id

    def record_outcome(self, trace_id: str, outcome: SkillOutcomeVector) -> None:
        for index, record in enumerate(self._records):
            if record.trace_id == trace_id:
                self._records[index] = SkillTraceRecord(
                    trace_id=record.trace_id,
                    run_id=record.run_id,
                    scenario=record.scenario,
                    seed=record.seed,
                    robot_ids=record.robot_ids,
                    selector_version=record.selector_version,
                    skill_library_version=record.skill_library_version,
                    state=record.state,
                    gates=record.gates,
                    decision=record.decision,
                    outcome=outcome.to_dict(),
                )
                return
        raise KeyError(trace_id)

    def to_jsonl(self) -> str:
        return "\n".join(dumps(record.to_dict(), sort_keys=True, allow_nan=False) for record in self._records)
