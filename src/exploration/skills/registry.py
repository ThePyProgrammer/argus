from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from .types import GateResult, SkillAuthority, SkillProposal, SkillState, SkillTermination


SkillPrecondition = Callable[[SkillState], GateResult]
SkillProposer = Callable[[SkillState], tuple[SkillProposal, ...]]


@dataclass(frozen=True)
class SkillContract:
    skill_id: str
    version: str
    purpose: str
    authority: tuple[SkillAuthority, ...]
    precondition: SkillPrecondition
    propose: SkillProposer
    termination_conditions: tuple[SkillTermination, ...]
    failure_modes: tuple[str, ...]
    required_telemetry: tuple[str, ...]
    required_metrics: tuple[str, ...]
    cooldown_steps: int = 0
    expected_outcome_window_steps: int = 10

    def __post_init__(self) -> None:
        for field_name, value in (
            ("skill_id", self.skill_id),
            ("version", self.version),
            ("purpose", self.purpose),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must not be empty")

        for field_name, value in (
            ("authority", self.authority),
            ("termination_conditions", self.termination_conditions),
            ("failure_modes", self.failure_modes),
            ("required_telemetry", self.required_telemetry),
            ("required_metrics", self.required_metrics),
        ):
            if value is None or isinstance(value, (str, bytes)):
                raise ValueError(f"{field_name} must not be empty")
            try:
                items = tuple(value)
            except TypeError as exc:
                raise ValueError(f"{field_name} must not be empty") from exc
            if not items:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, items)

        if isinstance(self.cooldown_steps, bool) or not isinstance(self.cooldown_steps, int) or self.cooldown_steps < 0:
            raise ValueError("cooldown_steps must be a non-negative integer")
        if (
            isinstance(self.expected_outcome_window_steps, bool)
            or not isinstance(self.expected_outcome_window_steps, int)
            or self.expected_outcome_window_steps < 0
        ):
            raise ValueError("expected_outcome_window_steps must be a non-negative integer")


@dataclass
class SkillRegistry:
    _contracts: dict[str, SkillContract] = field(default_factory=dict)

    def __init__(self, contracts: Iterable[SkillContract] | None = None) -> None:
        object.__setattr__(self, "_contracts", {})
        if contracts is not None:
            for contract in contracts:
                self.register(contract)

    def register(self, contract: SkillContract) -> None:
        if contract.skill_id in self._contracts:
            raise ValueError(f"skill_id {contract.skill_id!r} is already registered")
        self._contracts[contract.skill_id] = contract

    def get(self, skill_id: str) -> SkillContract:
        return self._contracts[skill_id]

    def all(self) -> tuple[SkillContract, ...]:
        return tuple(self._contracts.values())

    def proposals_for(self, state: SkillState) -> tuple[tuple[SkillProposal, ...], tuple[GateResult, ...]]:
        proposals: list[SkillProposal] = []
        gates: list[GateResult] = []
        for contract in self._contracts.values():
            gate = contract.precondition(state)
            gates.append(gate)
            if gate.eligible:
                proposals.extend(contract.propose(state))
        return tuple(proposals), tuple(gates)


__all__ = ["SkillContract", "SkillRegistry"]
