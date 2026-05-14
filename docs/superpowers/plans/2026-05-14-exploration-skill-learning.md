# Exploration Skill Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a disabled-by-default, auditable v1 exploration skill learner that selects among named high-level exploration skills at bounded decision points while preserving deterministic baseline exploration.

**Architecture:** Add a focused `src/exploration/skills/` package that owns skill contracts, typed proposals, state encoding, gated selection, execution decisions, outcome records, and promotion-gate utilities. Integrate it lightly into `ExplorationLoop.step_once()` through the existing frontier scoring seam so baseline exploration remains the default and path planning, SLAM, collision/stuck handling, and locomotion boundaries stay intact.

**Tech Stack:** Python dataclasses/enums, NumPy, existing `src.exploration` modules, pytest, existing exploration/coordinator mock patterns.

---

## Design Source

Implement against `docs/superpowers/specs/2026-05-14-exploration-skill-learning-design.md` and the literature-backed synthesis in `outputs/navigation-skill-adaptation.md`.

Key constraints to preserve:

- The learner is a policy-over-skills, not a low-level controller.
- Baseline exploration remains runnable and tested without the learner.
- The learner is disabled by default.
- Decisions are typed, gated, logged, replayable, and bounded.
- Failed preconditions, low confidence, repeated failure, or thrashing fall back to baseline.
- Online selection score and offline audit metrics stay separate.

## File Structure

Create these focused files:

- `src/exploration/skills/__init__.py` — public exports for the skill-learning package.
- `src/exploration/skills/types.py` — enums and dataclasses for `SkillState`, `SkillProposal`, `SkillDecision`, `SkillOutcomeVector`, trace records, termination classes, gate results, and parameter profiles.
- `src/exploration/skills/registry.py` — option-like `SkillContract` definition plus `SkillRegistry` validation and proposal collection.
- `src/exploration/skills/state.py` — deterministic `SkillStateEncoder` that converts exploration-loop observations into serializable state.
- `src/exploration/skills/library.py` — initial hand-authored exploration skill contracts and proposal functions.
- `src/exploration/skills/selector.py` — gated hand-authored selector with confidence thresholds, cooldowns, hysteresis, switch limits, and baseline fallback.
- `src/exploration/skills/executor.py` — validates a `SkillDecision` and returns a safe frontier scoring function or baseline fallback.
- `src/exploration/skills/recorder.py` — in-memory decision/outcome trace recorder with JSONL export support.
- `src/exploration/skills/promotion.py` — release-gate evaluation helpers for candidate-vs-baseline aggregate metrics.

Modify these existing files:

- `src/exploration/config.py` — add disabled-by-default skill-learning config fields.
- `src/exploration/exploration_loop.py` — instantiate optional learner pieces and consult them only at rescan/frontier-evaluation decision points.
- `src/exploration/__init__.py` — export no new behavior unless current package style expects exports; otherwise leave unchanged.

Create these tests:

- `tests/exploration/skills/__init__.py`
- `tests/exploration/skills/test_types.py`
- `tests/exploration/skills/test_registry.py`
- `tests/exploration/skills/test_state.py`
- `tests/exploration/skills/test_library.py`
- `tests/exploration/skills/test_selector.py`
- `tests/exploration/skills/test_executor.py`
- `tests/exploration/skills/test_recorder.py`
- `tests/exploration/skills/test_promotion.py`
- Add focused integration tests to `tests/exploration/test_exploration_loop.py`.

---

### Task 1: Skill Package Types

**Files:**
- Create: `src/exploration/skills/__init__.py`
- Create: `src/exploration/skills/types.py`
- Create: `tests/exploration/skills/__init__.py`
- Create: `tests/exploration/skills/test_types.py`

- [ ] **Step 1: Write the failing type serialization tests**

Create `tests/exploration/skills/__init__.py` as an empty file.

Create `tests/exploration/skills/test_types.py`:

```python
from __future__ import annotations

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


def test_authority_enum_prevents_low_level_control_authority() -> None:
    assert [authority.value for authority in SkillAuthority] == [
        "choose_skill",
        "choose_parameter_profile",
        "choose_bounded_sequence",
        "choose_team_assignment",
    ]
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_types.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.exploration.skills'`.

- [ ] **Step 3: Implement the types**

Create `src/exploration/skills/__init__.py`:

```python
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

__all__ = [
    "GateResult",
    "SkillAuthority",
    "SkillDecision",
    "SkillOutcomeVector",
    "SkillParameterProfile",
    "SkillProposal",
    "SkillState",
    "SkillTermination",
]
```

Create `src/exploration/skills/types.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillTermination(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ECONOMIC = "economic"
    COORDINATION = "coordination"
    SAFETY = "safety"
    PRECONDITION_INVALIDATED = "precondition_invalidated"
    BASELINE_FALLBACK = "baseline_fallback"
    OPERATOR_OVERRIDE = "operator_override"


class SkillAuthority(str, Enum):
    CHOOSE_SKILL = "choose_skill"
    CHOOSE_PARAMETER_PROFILE = "choose_parameter_profile"
    CHOOSE_BOUNDED_SEQUENCE = "choose_bounded_sequence"
    CHOOSE_TEAM_ASSIGNMENT = "choose_team_assignment"


@dataclass(frozen=True)
class SkillParameterProfile:
    profile_id: str
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"profile_id": self.profile_id, "values": dict(self.values)}


@dataclass(frozen=True)
class GateResult:
    skill_id: str
    eligible: bool
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"skill_id": self.skill_id, "eligible": self.eligible, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class SkillState:
    coverage_pct: float
    recent_coverage_delta: float
    frontier_count: int
    mean_frontier_distance: float
    largest_frontier_size: int
    robot_id: str
    robot_count: int
    is_stuck: bool
    no_progress_steps: int
    blocked_path_count: int
    recent_skill_ids: tuple[str, ...] = ()
    recent_termination_reasons: tuple[SkillTermination, ...] = ()
    overlap_score: float = 0.0
    idle_robot_count: int = 0
    connectivity_health: float = 1.0
    localization_health: float = 1.0
    map_quality_health: float = 1.0
    scenario_id: str | None = None
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_pct": self.coverage_pct,
            "recent_coverage_delta": self.recent_coverage_delta,
            "frontier_count": self.frontier_count,
            "mean_frontier_distance": self.mean_frontier_distance,
            "largest_frontier_size": self.largest_frontier_size,
            "robot_id": self.robot_id,
            "robot_count": self.robot_count,
            "is_stuck": self.is_stuck,
            "no_progress_steps": self.no_progress_steps,
            "blocked_path_count": self.blocked_path_count,
            "recent_skill_ids": list(self.recent_skill_ids),
            "recent_termination_reasons": [reason.value for reason in self.recent_termination_reasons],
            "overlap_score": self.overlap_score,
            "idle_robot_count": self.idle_robot_count,
            "connectivity_health": self.connectivity_health,
            "localization_health": self.localization_health,
            "map_quality_health": self.map_quality_health,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class SkillProposal:
    skill_id: str
    skill_version: str
    target: tuple[float, float, float] | None
    predicted_coverage_gain: float
    predicted_frontier_delta: float
    travel_cost: float
    risk: float
    connectivity_impact: float
    map_quality_impact: float
    min_commitment_steps: int
    cancellation_triggers: tuple[str, ...]
    confidence: float
    reason_codes: tuple[str, ...]
    robot_assignments: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    parameter_overrides: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "target": list(self.target) if self.target is not None else None,
            "predicted_coverage_gain": self.predicted_coverage_gain,
            "predicted_frontier_delta": self.predicted_frontier_delta,
            "travel_cost": self.travel_cost,
            "risk": self.risk,
            "connectivity_impact": self.connectivity_impact,
            "map_quality_impact": self.map_quality_impact,
            "min_commitment_steps": self.min_commitment_steps,
            "cancellation_triggers": list(self.cancellation_triggers),
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "robot_assignments": {key: list(value) for key, value in self.robot_assignments.items()},
            "parameter_overrides": dict(self.parameter_overrides),
        }


@dataclass(frozen=True)
class SkillDecision:
    selected_skill_id: str
    selected_proposal: SkillProposal | None
    parameter_profile: SkillParameterProfile
    confidence: float
    reason_codes: tuple[str, ...]
    fallback_skill_id: str
    rejected_candidates: tuple[GateResult, ...] = ()

    @classmethod
    def baseline(cls, reason_codes: tuple[str, ...]) -> "SkillDecision":
        return cls(
            selected_skill_id="baseline",
            selected_proposal=None,
            parameter_profile=SkillParameterProfile(profile_id="baseline"),
            confidence=1.0,
            reason_codes=reason_codes,
            fallback_skill_id="baseline",
        )

    @property
    def uses_baseline(self) -> bool:
        return self.selected_skill_id == "baseline" or self.selected_proposal is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_skill_id": self.selected_skill_id,
            "selected_proposal": self.selected_proposal.to_dict() if self.selected_proposal else None,
            "parameter_profile": self.parameter_profile.to_dict(),
            "confidence": self.confidence,
            "reason_codes": list(self.reason_codes),
            "fallback_skill_id": self.fallback_skill_id,
            "rejected_candidates": [candidate.to_dict() for candidate in self.rejected_candidates],
        }


@dataclass(frozen=True)
class SkillOutcomeVector:
    coverage_gain: float
    frontier_delta: float
    path_length: float
    command_effort: float
    safety_events: int
    recovery_events: int
    duplicate_coverage_delta: float
    connectivity_delta: float
    map_quality_delta: float
    future_affordance_gain: float
    termination: SkillTermination
    fallback_used: bool

    def balanced_score(self, weights: dict[str, float]) -> float:
        values = self.to_dict()
        return sum(float(values[key]) * weight for key, weight in weights.items() if key in values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_gain": self.coverage_gain,
            "frontier_delta": self.frontier_delta,
            "path_length": self.path_length,
            "command_effort": self.command_effort,
            "safety_events": self.safety_events,
            "recovery_events": self.recovery_events,
            "duplicate_coverage_delta": self.duplicate_coverage_delta,
            "connectivity_delta": self.connectivity_delta,
            "map_quality_delta": self.map_quality_delta,
            "future_affordance_gain": self.future_affordance_gain,
            "termination": self.termination.value,
            "fallback_used": self.fallback_used,
        }
```

- [ ] **Step 4: Run the type tests and verify they pass**

Run:

```bash
uv run pytest tests/exploration/skills/test_types.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/__init__.py src/exploration/skills/types.py tests/exploration/skills/__init__.py tests/exploration/skills/test_types.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill learning types

Define the typed state, proposal, decision, and outcome contracts that keep exploration skill learning auditable and bounded.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Skill Registry

**Files:**
- Create: `src/exploration/skills/registry.py`
- Create: `tests/exploration/skills/test_registry.py`

- [ ] **Step 1: Write the failing registry tests**

Create `tests/exploration/skills/test_registry.py`:

```python
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
```

- [ ] **Step 2: Run the registry tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_registry.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.registry`.

- [ ] **Step 3: Implement registry contracts**

Create `src/exploration/skills/registry.py`:

```python
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from src.exploration.skills.types import GateResult, SkillAuthority, SkillProposal, SkillState, SkillTermination


@dataclass(frozen=True)
class SkillContract:
    skill_id: str
    version: str
    purpose: str
    authority: tuple[SkillAuthority, ...]
    precondition: Callable[[SkillState], GateResult]
    propose: Callable[[SkillState], tuple[SkillProposal, ...]]
    termination_conditions: tuple[SkillTermination, ...]
    failure_modes: tuple[str, ...]
    required_telemetry: tuple[str, ...]
    required_metrics: tuple[str, ...]
    cooldown_steps: int = 0
    expected_outcome_window_steps: int = 10

    def __post_init__(self) -> None:
        required_text = {
            "skill_id": self.skill_id,
            "version": self.version,
            "purpose": self.purpose,
        }
        for field_name, value in required_text.items():
            if not value:
                raise ValueError(f"SkillContract requires {field_name}")
        required_sequences = {
            "authority": self.authority,
            "termination_conditions": self.termination_conditions,
            "failure_modes": self.failure_modes,
            "required_telemetry": self.required_telemetry,
            "required_metrics": self.required_metrics,
        }
        for field_name, value in required_sequences.items():
            if not value:
                raise ValueError(f"SkillContract requires {field_name}")


class SkillRegistry:
    def __init__(self, contracts: Iterable[SkillContract] = ()):
        self._contracts: dict[str, SkillContract] = {}
        for contract in contracts:
            self.register(contract)

    def register(self, contract: SkillContract) -> None:
        if contract.skill_id in self._contracts:
            raise ValueError(f"Skill {contract.skill_id!r} is already registered")
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
```

Update `src/exploration/skills/__init__.py`:

```python
from src.exploration.skills.registry import SkillContract, SkillRegistry
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

__all__ = [
    "GateResult",
    "SkillAuthority",
    "SkillContract",
    "SkillDecision",
    "SkillOutcomeVector",
    "SkillParameterProfile",
    "SkillProposal",
    "SkillRegistry",
    "SkillState",
    "SkillTermination",
]
```

- [ ] **Step 4: Run registry and type tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_types.py tests/exploration/skills/test_registry.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/__init__.py src/exploration/skills/registry.py tests/exploration/skills/test_registry.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill registry

Validate option-like skill contracts before selection so the learner can audit gates, proposals, and termination semantics.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Skill State Encoder

**Files:**
- Create: `src/exploration/skills/state.py`
- Create: `tests/exploration/skills/test_state.py`

- [ ] **Step 1: Write the failing state encoder tests**

Create `tests/exploration/skills/test_state.py`:

```python
from __future__ import annotations

import numpy as np

from src.exploration.frontier_detector import FrontierCluster
from src.exploration.skills.state import SkillStateEncoder
from src.exploration.skills.types import SkillTermination


def _cluster(centroid: tuple[float, float, float], count: int) -> FrontierCluster:
    return FrontierCluster(cells=[], centroid=np.array(centroid), size=count)


def test_state_encoder_summarizes_frontiers_deterministically() -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=2, scenario_id="office", seed=42)
    frontiers = [_cluster((1.0, 0.0, 0.0), 5), _cluster((4.0, 0.0, 0.0), 15)]

    state = encoder.encode(
        coverage_pct=20.0,
        previous_coverage_pct=18.0,
        robot_position=np.array([0.0, 0.0, 0.0]),
        frontiers=frontiers,
        is_stuck=False,
        no_progress_steps=2,
        blocked_path_count=1,
        recent_skill_ids=("frontier_pursuit",),
        recent_termination_reasons=(SkillTermination.SUCCESS,),
    )

    assert state.coverage_pct == 20.0
    assert state.recent_coverage_delta == 2.0
    assert state.frontier_count == 2
    assert state.mean_frontier_distance == 2.5
    assert state.largest_frontier_size == 15
    assert state.robot_id == "robot-1"
    assert state.robot_count == 2
    assert state.scenario_id == "office"
    assert state.seed == 42


def test_state_encoder_handles_no_frontiers() -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=1)

    state = encoder.encode(
        coverage_pct=10.0,
        previous_coverage_pct=10.0,
        robot_position=np.array([0.0, 0.0, 0.0]),
        frontiers=[],
        is_stuck=True,
        no_progress_steps=12,
        blocked_path_count=0,
        recent_skill_ids=(),
        recent_termination_reasons=(),
    )

    assert state.frontier_count == 0
    assert state.mean_frontier_distance == 0.0
    assert state.largest_frontier_size == 0
    assert state.is_stuck is True
```

- [ ] **Step 2: Run the state tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_state.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.state`.

- [ ] **Step 3: Implement the encoder**

Create `src/exploration/skills/state.py`:

```python
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from src.exploration.frontier_detector import FrontierCluster
from src.exploration.skills.types import SkillState, SkillTermination


class SkillStateEncoder:
    def __init__(self, robot_id: str = "robot", robot_count: int = 1, scenario_id: str | None = None, seed: int | None = None):
        self._robot_id = robot_id
        self._robot_count = robot_count
        self._scenario_id = scenario_id
        self._seed = seed

    def encode(
        self,
        *,
        coverage_pct: float,
        previous_coverage_pct: float,
        robot_position: np.ndarray,
        frontiers: Sequence[FrontierCluster],
        is_stuck: bool,
        no_progress_steps: int,
        blocked_path_count: int,
        recent_skill_ids: tuple[str, ...],
        recent_termination_reasons: tuple[SkillTermination, ...],
        overlap_score: float = 0.0,
        idle_robot_count: int = 0,
        connectivity_health: float = 1.0,
        localization_health: float = 1.0,
        map_quality_health: float = 1.0,
    ) -> SkillState:
        distances = [float(np.linalg.norm(frontier.centroid[:2] - robot_position[:2])) for frontier in frontiers]
        sizes = [int(frontier.size) for frontier in frontiers]
        return SkillState(
            coverage_pct=float(coverage_pct),
            recent_coverage_delta=float(coverage_pct - previous_coverage_pct),
            frontier_count=len(frontiers),
            mean_frontier_distance=float(np.mean(distances)) if distances else 0.0,
            largest_frontier_size=max(sizes) if sizes else 0,
            robot_id=self._robot_id,
            robot_count=self._robot_count,
            is_stuck=bool(is_stuck),
            no_progress_steps=int(no_progress_steps),
            blocked_path_count=int(blocked_path_count),
            recent_skill_ids=recent_skill_ids,
            recent_termination_reasons=recent_termination_reasons,
            overlap_score=float(overlap_score),
            idle_robot_count=int(idle_robot_count),
            connectivity_health=float(connectivity_health),
            localization_health=float(localization_health),
            map_quality_health=float(map_quality_health),
            scenario_id=self._scenario_id,
            seed=self._seed,
        )
```

- [ ] **Step 4: Run state tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/state.py tests/exploration/skills/test_state.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill state encoder

Summarize exploration-loop state into deterministic skill observations without exposing raw simulator internals.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Initial Skill Library

**Files:**
- Create: `src/exploration/skills/library.py`
- Create: `tests/exploration/skills/test_library.py`

- [ ] **Step 1: Write the failing skill library tests**

Create `tests/exploration/skills/test_library.py`:

```python
from __future__ import annotations

from src.exploration.skills.library import create_default_skill_registry
from src.exploration.skills.types import SkillState, SkillTermination


def _state(frontier_count: int = 3, is_stuck: bool = False, robot_count: int = 1) -> SkillState:
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


def test_team_skills_require_multi_robot_state() -> None:
    registry = create_default_skill_registry()

    single_robot_proposals, _ = registry.proposals_for(_state(robot_count=1))
    multi_robot_proposals, _ = registry.proposals_for(_state(robot_count=3))

    assert "robot_deconflict" not in {proposal.skill_id for proposal in single_robot_proposals}
    assert "robot_deconflict" in {proposal.skill_id for proposal in multi_robot_proposals}
```

- [ ] **Step 2: Run the skill library tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_library.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.library`.

- [ ] **Step 3: Implement initial skill contracts**

Create `src/exploration/skills/library.py`:

```python
from __future__ import annotations

from src.exploration.skills.registry import SkillContract, SkillRegistry
from src.exploration.skills.types import GateResult, SkillAuthority, SkillProposal, SkillState, SkillTermination


VERSION = "1.0"


def _proposal(
    state: SkillState,
    skill_id: str,
    *,
    target: tuple[float, float, float] | None = None,
    coverage_gain: float,
    frontier_delta: float,
    travel_cost: float,
    risk: float = 0.0,
    connectivity_impact: float = 0.0,
    map_quality_impact: float = 0.0,
    min_commitment_steps: int = 5,
    reason_codes: tuple[str, ...],
) -> SkillProposal:
    return SkillProposal(
        skill_id=skill_id,
        skill_version=VERSION,
        target=target,
        predicted_coverage_gain=coverage_gain,
        predicted_frontier_delta=frontier_delta,
        travel_cost=travel_cost,
        risk=risk,
        connectivity_impact=connectivity_impact,
        map_quality_impact=map_quality_impact,
        min_commitment_steps=min_commitment_steps,
        cancellation_triggers=("precondition_invalidated", "no_progress"),
        confidence=0.5 + min(state.frontier_count, 5) * 0.05,
        reason_codes=reason_codes,
    )


def _frontier_target(state: SkillState) -> tuple[float, float, float]:
    return (max(state.mean_frontier_distance, 0.5), 0.0, 0.0)


def _requires_frontiers(skill_id: str, state: SkillState) -> GateResult:
    if state.frontier_count <= 0:
        return GateResult(skill_id, False, ("no_frontiers",))
    return GateResult(skill_id, True)


def _requires_stuck(skill_id: str, state: SkillState) -> GateResult:
    if not state.is_stuck:
        return GateResult(skill_id, False, ("robot_not_stuck",))
    return GateResult(skill_id, True)


def _requires_team(skill_id: str, state: SkillState) -> GateResult:
    if state.robot_count < 2:
        return GateResult(skill_id, False, ("single_robot",))
    return GateResult(skill_id, True)


def create_default_skill_registry() -> SkillRegistry:
    return SkillRegistry(
        [
            SkillContract(
                skill_id="frontier_pursuit",
                version=VERSION,
                purpose="Choose and pursue a high-value frontier through existing exploration planning.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_PARAMETER_PROFILE),
                precondition=lambda state: _requires_frontiers("frontier_pursuit", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "frontier_pursuit",
                        target=_frontier_target(state),
                        coverage_gain=max(0.1, state.largest_frontier_size / 100.0),
                        frontier_delta=-1.0,
                        travel_cost=max(state.mean_frontier_distance, 0.1),
                        reason_codes=("frontier_available",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE, SkillTermination.TIMEOUT),
                failure_modes=("frontier_invalidated", "path_failed"),
                required_telemetry=("coverage_pct", "frontier_count"),
                required_metrics=("coverage_gain", "frontier_delta", "path_length"),
            ),
            SkillContract(
                skill_id="coverage_sweep",
                version=VERSION,
                purpose="Prefer moves that improve coverage density when frontiers remain available.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_PARAMETER_PROFILE),
                precondition=lambda state: _requires_frontiers("coverage_sweep", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "coverage_sweep",
                        target=_frontier_target(state),
                        coverage_gain=0.2,
                        frontier_delta=-0.5,
                        travel_cost=max(state.mean_frontier_distance * 1.2, 0.1),
                        map_quality_impact=0.1,
                        reason_codes=("coverage_density",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.ECONOMIC, SkillTermination.TIMEOUT),
                failure_modes=("low_marginal_gain",),
                required_telemetry=("coverage_pct", "recent_coverage_delta"),
                required_metrics=("coverage_gain", "command_effort"),
            ),
            SkillContract(
                skill_id="replan",
                version=VERSION,
                purpose="Force a new frontier and path evaluation when progress stalls.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=lambda state: GateResult("replan", state.no_progress_steps > 0, () if state.no_progress_steps > 0 else ("progress_ok",)),
                propose=lambda state: (
                    _proposal(
                        state,
                        "replan",
                        target=None,
                        coverage_gain=0.05,
                        frontier_delta=0.0,
                        travel_cost=0.1,
                        min_commitment_steps=1,
                        reason_codes=("progress_stalled",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE),
                failure_modes=("no_new_plan",),
                required_telemetry=("no_progress_steps",),
                required_metrics=("path_length", "frontier_delta"),
            ),
            SkillContract(
                skill_id="stuck_recovery",
                version=VERSION,
                purpose="Invoke existing recovery behavior when the robot is stuck.",
                authority=(SkillAuthority.CHOOSE_SKILL,),
                precondition=lambda state: _requires_stuck("stuck_recovery", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "stuck_recovery",
                        target=None,
                        coverage_gain=0.0,
                        frontier_delta=0.0,
                        travel_cost=0.5,
                        risk=0.1,
                        min_commitment_steps=3,
                        reason_codes=("stuck_detected",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.FAILURE, SkillTermination.TIMEOUT),
                failure_modes=("recovery_failed", "oscillation"),
                required_telemetry=("is_stuck",),
                required_metrics=("recovery_events", "safety_events"),
                cooldown_steps=10,
            ),
            SkillContract(
                skill_id="viewpoint_shift",
                version=VERSION,
                purpose="Move to improve map or perception angle before committing to a frontier.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_PARAMETER_PROFILE),
                precondition=lambda state: _requires_frontiers("viewpoint_shift", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "viewpoint_shift",
                        target=_frontier_target(state),
                        coverage_gain=0.1,
                        frontier_delta=0.5,
                        travel_cost=max(state.mean_frontier_distance * 0.8, 0.1),
                        map_quality_impact=0.2,
                        reason_codes=("improve_viewpoint",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.ECONOMIC, SkillTermination.TIMEOUT),
                failure_modes=("viewpoint_blocked",),
                required_telemetry=("map_quality_health", "frontier_count"),
                required_metrics=("map_quality_delta", "future_affordance_gain"),
            ),
            SkillContract(
                skill_id="robot_deconflict",
                version=VERSION,
                purpose="Reduce overlap or redundant work between robots.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_TEAM_ASSIGNMENT),
                precondition=lambda state: _requires_team("robot_deconflict", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "robot_deconflict",
                        target=None,
                        coverage_gain=0.1,
                        frontier_delta=0.0,
                        travel_cost=0.2,
                        connectivity_impact=0.1,
                        reason_codes=("multi_robot_deconflict",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.COORDINATION, SkillTermination.TIMEOUT),
                failure_modes=("assignment_churn",),
                required_telemetry=("robot_count", "overlap_score"),
                required_metrics=("duplicate_coverage_delta", "connectivity_delta"),
            ),
            SkillContract(
                skill_id="relay_or_rendezvous",
                version=VERSION,
                purpose="Improve communication or team topology when exploration health depends on it.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_TEAM_ASSIGNMENT),
                precondition=lambda state: _requires_team("relay_or_rendezvous", state),
                propose=lambda state: (
                    _proposal(
                        state,
                        "relay_or_rendezvous",
                        target=None,
                        coverage_gain=0.0,
                        frontier_delta=0.0,
                        travel_cost=0.3,
                        connectivity_impact=0.3,
                        reason_codes=("team_connectivity",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.COORDINATION, SkillTermination.TIMEOUT),
                failure_modes=("connectivity_not_improved",),
                required_telemetry=("connectivity_health", "robot_count"),
                required_metrics=("connectivity_delta",),
            ),
            SkillContract(
                skill_id="loop_closure_probe",
                version=VERSION,
                purpose="Revisit a candidate region when map topology quality benefits from closure.",
                authority=(SkillAuthority.CHOOSE_SKILL, SkillAuthority.CHOOSE_PARAMETER_PROFILE),
                precondition=lambda state: GateResult(
                    "loop_closure_probe",
                    state.map_quality_health < 0.9 and state.frontier_count > 0,
                    () if state.map_quality_health < 0.9 and state.frontier_count > 0 else ("map_quality_ok",),
                ),
                propose=lambda state: (
                    _proposal(
                        state,
                        "loop_closure_probe",
                        target=_frontier_target(state),
                        coverage_gain=0.05,
                        frontier_delta=0.0,
                        travel_cost=max(state.mean_frontier_distance, 0.1),
                        map_quality_impact=0.4,
                        reason_codes=("map_quality_probe",),
                    ),
                ),
                termination_conditions=(SkillTermination.SUCCESS, SkillTermination.ECONOMIC, SkillTermination.TIMEOUT),
                failure_modes=("loop_candidate_invalid",),
                required_telemetry=("map_quality_health",),
                required_metrics=("map_quality_delta",),
            ),
        ]
    )
```

- [ ] **Step 4: Run library and registry tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_registry.py tests/exploration/skills/test_library.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/library.py tests/exploration/skills/test_library.py
git commit -m "$(cat <<'EOF'
feat: add initial exploration skill library

Register the first option-like exploration skills with explicit gates, proposals, telemetry, and termination contracts.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Gated Online Selector

**Files:**
- Create: `src/exploration/skills/selector.py`
- Create: `tests/exploration/skills/test_selector.py`

- [ ] **Step 1: Write the failing selector tests**

Create `tests/exploration/skills/test_selector.py`:

```python
from __future__ import annotations

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


def _proposal(skill_id: str, confidence: float, coverage_gain: float, travel_cost: float, risk: float = 0.0) -> SkillProposal:
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
        reason_codes=("candidate",),
    )


def test_selector_returns_baseline_when_no_candidates() -> None:
    selector = GatedSkillSelector()

    decision = selector.select(_state(), proposals=(), gates=())

    assert decision.uses_baseline
    assert decision.reason_codes == ("no_eligible_proposals",)


def test_selector_rejects_low_confidence_candidates() -> None:
    selector = GatedSkillSelector(SkillSelectorConfig(min_confidence=0.7))

    decision = selector.select(_state(), proposals=(_proposal("frontier_pursuit", 0.5, 1.0, 1.0),), gates=())

    assert decision.uses_baseline
    assert decision.reason_codes == ("low_confidence",)


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
```

- [ ] **Step 2: Run the selector tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_selector.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.selector`.

- [ ] **Step 3: Implement the selector**

Create `src/exploration/skills/selector.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from src.exploration.skills.types import GateResult, SkillDecision, SkillParameterProfile, SkillProposal, SkillState, SkillTermination


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


@dataclass
class GatedSkillSelector:
    config: SkillSelectorConfig = field(default_factory=SkillSelectorConfig)

    def __post_init__(self) -> None:
        self._current_skill_id: str | None = None
        self._steps_in_current_skill = 0
        self._failure_counts: dict[str, int] = {}
        self._degraded_to_baseline = False

    def select(
        self,
        state: SkillState,
        *,
        proposals: tuple[SkillProposal, ...],
        gates: tuple[GateResult, ...],
    ) -> SkillDecision:
        if self._degraded_to_baseline:
            return SkillDecision.baseline(("episode_degraded_to_baseline",))
        if not proposals:
            return SkillDecision.baseline(("no_eligible_proposals",))

        confident = tuple(proposal for proposal in proposals if proposal.confidence >= self.config.min_confidence)
        if not confident:
            return SkillDecision.baseline(("low_confidence",))

        selected = max(confident, key=lambda proposal: self._score(state, proposal))
        if self._current_skill_id and selected.skill_id != self._current_skill_id and self._steps_in_current_skill < self.config.min_dwell_steps:
            return SkillDecision.baseline(("minimum_dwell_active",))

        self._steps_in_current_skill = self._steps_in_current_skill + 1 if selected.skill_id == self._current_skill_id else 1
        self._current_skill_id = selected.skill_id
        reasons = selected.reason_codes
        if state.is_stuck and selected.skill_id == "stuck_recovery":
            reasons = reasons + ("stuck_priority",)
        return SkillDecision(
            selected_skill_id=selected.skill_id,
            selected_proposal=selected,
            parameter_profile=SkillParameterProfile(profile_id="default"),
            confidence=selected.confidence,
            reason_codes=reasons,
            fallback_skill_id="baseline",
            rejected_candidates=gates,
        )

    def record_termination(self, skill_id: str, termination: SkillTermination) -> None:
        if termination in {SkillTermination.FAILURE, SkillTermination.TIMEOUT, SkillTermination.SAFETY}:
            self._failure_counts[skill_id] = self._failure_counts.get(skill_id, 0) + 1
        if self._failure_counts.get(skill_id, 0) >= self.config.max_failures_before_baseline:
            self._degraded_to_baseline = True

    def _score(self, state: SkillState, proposal: SkillProposal) -> float:
        score = (
            proposal.predicted_coverage_gain * self.config.coverage_gain_weight
            + proposal.predicted_frontier_delta * self.config.frontier_delta_weight
            - proposal.travel_cost * self.config.travel_cost_weight
            - proposal.risk * self.config.risk_weight
            + proposal.connectivity_impact * self.config.connectivity_weight
            + proposal.map_quality_impact * self.config.map_quality_weight
        )
        if state.is_stuck and proposal.skill_id == "stuck_recovery":
            score += self.config.stuck_recovery_bonus
        return score
```

- [ ] **Step 4: Run selector tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_selector.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/selector.py tests/exploration/skills/test_selector.py
git commit -m "$(cat <<'EOF'
feat: add gated exploration skill selector

Choose exploration skills through confidence gates, bounded dwell behavior, and baseline degradation after repeated failures.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Skill Executor

**Files:**
- Create: `src/exploration/skills/executor.py`
- Create: `tests/exploration/skills/test_executor.py`

- [ ] **Step 1: Write the failing executor tests**

Create `tests/exploration/skills/test_executor.py`:

```python
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
```

- [ ] **Step 2: Run the executor tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_executor.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.executor`.

- [ ] **Step 3: Implement the executor**

Create `src/exploration/skills/executor.py`:

```python
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from src.exploration.skills.types import SkillDecision


@dataclass(frozen=True)
class SkillExecutionResult:
    score_fn: Callable[[np.ndarray], float] | None
    fallback_used: bool
    termination_reason: str | None
    reason_codes: tuple[str, ...]


class SkillExecutor:
    _TARGET_REQUIRED_SKILLS = {"frontier_pursuit", "coverage_sweep", "viewpoint_shift", "loop_closure_probe"}

    def apply(self, decision: SkillDecision) -> SkillExecutionResult:
        if decision.uses_baseline:
            return SkillExecutionResult(
                score_fn=None,
                fallback_used=True,
                termination_reason="baseline_fallback",
                reason_codes=decision.reason_codes,
            )

        proposal = decision.selected_proposal
        if proposal is None:
            return SkillExecutionResult(None, True, "baseline_fallback", decision.reason_codes)
        if proposal.skill_id in self._TARGET_REQUIRED_SKILLS and proposal.target is None:
            return SkillExecutionResult(None, True, "precondition_invalidated", decision.reason_codes)
        if proposal.target is None:
            return SkillExecutionResult(None, False, None, decision.reason_codes)

        target = np.array(proposal.target, dtype=float)

        def score_fn(candidate: np.ndarray) -> float:
            return -float(np.linalg.norm(candidate[:2] - target[:2]))

        return SkillExecutionResult(score_fn=score_fn, fallback_used=False, termination_reason=None, reason_codes=decision.reason_codes)
```

- [ ] **Step 4: Run executor tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_executor.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/executor.py tests/exploration/skills/test_executor.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill executor

Translate selected skill proposals into safe frontier bias functions while falling back when preconditions fail.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Outcome Recorder

**Files:**
- Create: `src/exploration/skills/recorder.py`
- Create: `tests/exploration/skills/test_recorder.py`

- [ ] **Step 1: Write the failing recorder tests**

Create `tests/exploration/skills/test_recorder.py`:

```python
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
```

- [ ] **Step 2: Run the recorder tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_recorder.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.recorder`.

- [ ] **Step 3: Implement the recorder**

Create `src/exploration/skills/recorder.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
from uuid import uuid4

from src.exploration.skills.types import GateResult, SkillDecision, SkillOutcomeVector, SkillState


@dataclass
class SkillTraceRecord:
    trace_id: str
    run_id: str
    scenario: str
    seed: int | None
    robot_ids: tuple[str, ...]
    selector_version: str
    skill_library_version: str
    state: SkillState
    gates: tuple[GateResult, ...]
    decision: SkillDecision
    outcome: SkillOutcomeVector | None = None

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "scenario": self.scenario,
            "seed": self.seed,
            "robot_ids": list(self.robot_ids),
            "selector_version": self.selector_version,
            "skill_library_version": self.skill_library_version,
            "state": self.state.to_dict(),
            "gates": [gate.to_dict() for gate in self.gates],
            "decision": self.decision.to_dict(),
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }


class SkillOutcomeRecorder:
    def __init__(self, run_id: str, selector_version: str, skill_library_version: str):
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
        seed: int | None,
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
                robot_ids=robot_ids,
                selector_version=self._selector_version,
                skill_library_version=self._skill_library_version,
                state=state,
                gates=gates,
                decision=decision,
            )
        )
        return trace_id

    def record_outcome(self, trace_id: str, outcome: SkillOutcomeVector) -> None:
        for record in self._records:
            if record.trace_id == trace_id:
                record.outcome = outcome
                return
        raise KeyError(trace_id)

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(record.to_dict(), sort_keys=True) for record in self._records)
```

- [ ] **Step 4: Run recorder tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_recorder.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/recorder.py tests/exploration/skills/test_recorder.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill outcome recorder

Capture decision and outcome traces so online skill selection can be replayed, audited, and promoted against baselines.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Promotion Gate Utilities

**Files:**
- Create: `src/exploration/skills/promotion.py`
- Create: `tests/exploration/skills/test_promotion.py`

- [ ] **Step 1: Write the failing promotion tests**

Create `tests/exploration/skills/test_promotion.py`:

```python
from __future__ import annotations

from src.exploration.skills.promotion import PromotionGateConfig, PromotionMetricSummary, evaluate_promotion


def test_promotion_passes_when_candidate_improves_without_regressions() -> None:
    baseline = PromotionMetricSummary(
        balanced_score_mean=10.0,
        coverage_mean=80.0,
        safety_events_mean=0.0,
        recovery_events_mean=1.0,
        path_length_mean=100.0,
        switch_rate_mean=0.1,
        map_quality_mean=0.9,
    )
    candidate = PromotionMetricSummary(
        balanced_score_mean=11.0,
        coverage_mean=82.0,
        safety_events_mean=0.0,
        recovery_events_mean=1.0,
        path_length_mean=98.0,
        switch_rate_mean=0.1,
        map_quality_mean=0.91,
    )

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig(min_score_improvement=0.5))

    assert report.promoted is True
    assert report.regressions == ()


def test_promotion_fails_on_safety_regression_even_with_score_gain() -> None:
    baseline = PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    candidate = PromotionMetricSummary(12.0, 85.0, 1.0, 1.0, 95.0, 0.1, 0.9)

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig())

    assert report.promoted is False
    assert "safety_events_regressed" in report.regressions


def test_promotion_fails_when_switch_rate_regresses() -> None:
    baseline = PromotionMetricSummary(10.0, 80.0, 0.0, 1.0, 100.0, 0.1, 0.9)
    candidate = PromotionMetricSummary(11.0, 83.0, 0.0, 1.0, 95.0, 0.4, 0.9)

    report = evaluate_promotion(baseline, candidate, PromotionGateConfig(max_switch_rate_delta=0.2))

    assert report.promoted is False
    assert "switch_rate_regressed" in report.regressions
```

- [ ] **Step 2: Run the promotion tests and verify they fail**

Run:

```bash
uv run pytest tests/exploration/skills/test_promotion.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `src.exploration.skills.promotion`.

- [ ] **Step 3: Implement promotion gate utilities**

Create `src/exploration/skills/promotion.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromotionMetricSummary:
    balanced_score_mean: float
    coverage_mean: float
    safety_events_mean: float
    recovery_events_mean: float
    path_length_mean: float
    switch_rate_mean: float
    map_quality_mean: float


@dataclass(frozen=True)
class PromotionGateConfig:
    min_score_improvement: float = 0.0
    min_coverage_delta: float = 0.0
    max_safety_event_delta: float = 0.0
    max_recovery_event_delta: float = 1.0
    max_path_length_delta: float = 10.0
    max_switch_rate_delta: float = 0.1
    min_map_quality_delta: float = -0.01


@dataclass(frozen=True)
class PromotionReport:
    promoted: bool
    score_delta: float
    coverage_delta: float
    regressions: tuple[str, ...]


def evaluate_promotion(
    baseline: PromotionMetricSummary,
    candidate: PromotionMetricSummary,
    config: PromotionGateConfig,
) -> PromotionReport:
    regressions: list[str] = []
    score_delta = candidate.balanced_score_mean - baseline.balanced_score_mean
    coverage_delta = candidate.coverage_mean - baseline.coverage_mean

    if score_delta < config.min_score_improvement:
        regressions.append("score_improvement_too_small")
    if coverage_delta < config.min_coverage_delta:
        regressions.append("coverage_regressed")
    if candidate.safety_events_mean - baseline.safety_events_mean > config.max_safety_event_delta:
        regressions.append("safety_events_regressed")
    if candidate.recovery_events_mean - baseline.recovery_events_mean > config.max_recovery_event_delta:
        regressions.append("recovery_events_regressed")
    if candidate.path_length_mean - baseline.path_length_mean > config.max_path_length_delta:
        regressions.append("path_length_regressed")
    if candidate.switch_rate_mean - baseline.switch_rate_mean > config.max_switch_rate_delta:
        regressions.append("switch_rate_regressed")
    if candidate.map_quality_mean - baseline.map_quality_mean < config.min_map_quality_delta:
        regressions.append("map_quality_regressed")

    return PromotionReport(
        promoted=not regressions,
        score_delta=score_delta,
        coverage_delta=coverage_delta,
        regressions=tuple(regressions),
    )
```

- [ ] **Step 4: Run promotion tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_promotion.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/skills/promotion.py tests/exploration/skills/test_promotion.py
git commit -m "$(cat <<'EOF'
feat: add exploration skill promotion gate

Compare candidate skill-selection runs against deterministic baselines with explicit no-regression guardrails.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Disabled-by-Default Config

**Files:**
- Modify: `src/exploration/config.py`
- Add tests to: `tests/exploration/skills/test_selector.py`

- [ ] **Step 1: Write the failing config tests**

Append to `tests/exploration/skills/test_selector.py`:

```python
from src.exploration.config import ExplorationConfig


def test_exploration_skill_learning_is_disabled_by_default() -> None:
    config = ExplorationConfig()

    assert config.skill_learning_enabled is False
    assert config.skill_learning_shadow_mode is False
    assert config.skill_learning_min_confidence == 0.6
    assert config.skill_learning_min_dwell_steps == 3
    assert config.skill_learning_max_failures_before_baseline == 3
```

- [ ] **Step 2: Run the new config test and verify it fails**

Run:

```bash
uv run pytest tests/exploration/skills/test_selector.py::test_exploration_skill_learning_is_disabled_by_default -q
```

Expected: FAIL with `AttributeError: 'ExplorationConfig' object has no attribute 'skill_learning_enabled'`.

- [ ] **Step 3: Add skill-learning config fields**

Modify `src/exploration/config.py` by adding these fields to `ExplorationConfig` after `goal_strategy: str = "nearest"`:

```python
    skill_learning_enabled: bool = False
    skill_learning_shadow_mode: bool = False
    skill_learning_min_confidence: float = 0.6
    skill_learning_min_dwell_steps: int = 3
    skill_learning_max_failures_before_baseline: int = 3
```

- [ ] **Step 4: Run config and existing exploration config tests**

Run:

```bash
uv run pytest tests/exploration/skills/test_selector.py::test_exploration_skill_learning_is_disabled_by_default tests/exploration/test_explore_mode.py tests/exploration/test_exploration_loop.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/config.py tests/exploration/skills/test_selector.py
git commit -m "$(cat <<'EOF'
feat: gate exploration skill learning behind config

Keep skill learning disabled by default while making confidence, dwell, and failure guardrails explicit.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Exploration Loop Integration

**Files:**
- Modify: `src/exploration/exploration_loop.py`
- Modify: `tests/exploration/test_exploration_loop.py`

- [ ] **Step 1: Write a failing baseline-preservation integration test**

Append to `tests/exploration/test_exploration_loop.py`:

```python

def test_skill_learning_disabled_preserves_baseline_score_fn() -> None:
    bridge = MockBridge(frames=[_make_sensor_frame()])
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(skill_learning_enabled=False),
    )
    observed = {}

    def score_fn(candidate: np.ndarray) -> float:
        observed["called"] = True
        return -float(np.linalg.norm(candidate[:2]))

    loop.frontier_detector.detect = lambda grid: [_make_cluster([2.0, 0.0, 0.0])]
    loop.path_planner.plan = lambda start, goal: [start, goal]

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=0, score_fn=score_fn)

    assert metrics.frontiers == 1
    assert observed["called"] is True
```

- [ ] **Step 2: Run the baseline-preservation test**

Run:

```bash
uv run pytest tests/exploration/test_exploration_loop.py::test_skill_learning_disabled_preserves_baseline_score_fn -q
```

Expected: PASS before integration changes. If it fails because the helper mocks differ from this plan, adjust the test to match the existing helper pattern while preserving the assertion: disabled skill learning must pass through the caller-provided `score_fn`.

- [ ] **Step 3: Write a failing enabled-path decision test**

Append to `tests/exploration/test_exploration_loop.py`:

```python

def test_skill_learning_enabled_records_decision_trace() -> None:
    bridge = MockBridge(frames=[_make_sensor_frame()])
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(skill_learning_enabled=True),
    )
    loop.frontier_detector.detect = lambda grid: [_make_cluster([2.0, 0.0, 0.0])]
    loop.path_planner.plan = lambda start, goal: [start, goal]

    frame = _make_sensor_frame()
    _, _, metrics = loop.step_once(frame, step=0)

    assert metrics.frontiers == 1
    assert loop.skill_trace_jsonl()
    assert "frontier_pursuit" in loop.skill_trace_jsonl()
```

- [ ] **Step 4: Run the enabled-path test and verify it fails**

Run:

```bash
uv run pytest tests/exploration/test_exploration_loop.py::test_skill_learning_enabled_records_decision_trace -q
```

Expected: FAIL with `AttributeError` for missing skill-learning integration or `skill_trace_jsonl`.

- [ ] **Step 5: Add optional skill learner construction to `ExplorationLoop.__init__`**

Modify `src/exploration/exploration_loop.py` imports:

```python
from src.exploration.skills.executor import SkillExecutor
from src.exploration.skills.library import create_default_skill_registry
from src.exploration.skills.recorder import SkillOutcomeRecorder
from src.exploration.skills.selector import GatedSkillSelector, SkillSelectorConfig
from src.exploration.skills.state import SkillStateEncoder
from src.exploration.skills.types import SkillOutcomeVector, SkillTermination
```

Add these attributes near the end of `ExplorationLoop.__init__` after existing config-dependent initialization:

```python
        self._skill_registry = create_default_skill_registry() if self._config.skill_learning_enabled else None
        self._skill_selector = (
            GatedSkillSelector(
                SkillSelectorConfig(
                    min_confidence=self._config.skill_learning_min_confidence,
                    min_dwell_steps=self._config.skill_learning_min_dwell_steps,
                    max_failures_before_baseline=self._config.skill_learning_max_failures_before_baseline,
                )
            )
            if self._config.skill_learning_enabled
            else None
        )
        self._skill_executor = SkillExecutor() if self._config.skill_learning_enabled else None
        self._skill_state_encoder = SkillStateEncoder() if self._config.skill_learning_enabled else None
        self._skill_recorder = (
            SkillOutcomeRecorder(run_id="local", selector_version="gated-v1", skill_library_version="default-v1")
            if self._config.skill_learning_enabled
            else None
        )
        self._last_skill_trace_id: str | None = None
```

Add this method to `ExplorationLoop`:

```python
    def skill_trace_jsonl(self) -> str:
        if self._skill_recorder is None:
            return ""
        return self._skill_recorder.to_jsonl()
```

- [ ] **Step 6: Add skill selection at frontier evaluation boundary**

Modify `_evaluate_frontiers` so it computes an `effective_score_fn` before calling `GoalSelector.select_with_bias`. Preserve existing behavior if the learner is disabled or shadow mode is enabled.

Use this structure inside `_evaluate_frontiers` after `frontiers = self.frontier_detector.detect(grid)` and before selecting the goal:

```python
        effective_score_fn = score_fn
        if self._skill_registry and self._skill_selector and self._skill_executor and self._skill_state_encoder and self._skill_recorder:
            state = self._skill_state_encoder.encode(
                coverage_pct=self.coverage_tracker.coverage_percentage(),
                previous_coverage_pct=self._last_coverage,
                robot_position=current_pos,
                frontiers=frontiers,
                is_stuck=self.stuck_recovery.is_active,
                no_progress_steps=0,
                blocked_path_count=0,
                recent_skill_ids=(),
                recent_termination_reasons=(),
            )
            proposals, gates = self._skill_registry.proposals_for(state)
            decision = self._skill_selector.select(state, proposals=proposals, gates=gates)
            self._last_skill_trace_id = self._skill_recorder.record_decision(
                scenario="local",
                seed=None,
                robot_ids=(state.robot_id,),
                state=state,
                gates=gates,
                decision=decision,
            )
            execution = self._skill_executor.apply(decision)
            if not self._config.skill_learning_shadow_mode:
                effective_score_fn = execution.score_fn if execution.score_fn is not None else score_fn
```

Then change the existing goal selection call from:

```python
        goal = self.goal_selector.select_with_bias(frontiers, current_pos, score_fn)
```

to:

```python
        goal = self.goal_selector.select_with_bias(frontiers, current_pos, effective_score_fn)
```

- [ ] **Step 7: Record a minimal outcome window after frontier evaluation**

At the end of `_evaluate_frontiers`, after the goal/path decision outcome is known, add:

```python
        if self._skill_recorder and self._last_skill_trace_id:
            self._skill_recorder.record_outcome(
                self._last_skill_trace_id,
                SkillOutcomeVector(
                    coverage_gain=max(0.0, self.coverage_tracker.coverage_percentage() - self._last_coverage),
                    frontier_delta=0.0,
                    path_length=float(len(path)) if path else 0.0,
                    command_effort=0.0,
                    safety_events=0,
                    recovery_events=0,
                    duplicate_coverage_delta=0.0,
                    connectivity_delta=0.0,
                    map_quality_delta=0.0,
                    future_affordance_gain=0.0,
                    termination=SkillTermination.SUCCESS if path else SkillTermination.BASELINE_FALLBACK,
                    fallback_used=path is None,
                ),
            )
```

If `_evaluate_frontiers` currently has multiple early returns, place this logic before each return using the actual local `path` variable. Keep the implementation minimal and local; do not restructure the whole loop.

- [ ] **Step 8: Run integration tests**

Run:

```bash
uv run pytest tests/exploration/test_exploration_loop.py::test_skill_learning_disabled_preserves_baseline_score_fn tests/exploration/test_exploration_loop.py::test_skill_learning_enabled_records_decision_trace -q
```

Expected: PASS.

- [ ] **Step 9: Run full exploration skill and loop tests**

Run:

```bash
uv run pytest tests/exploration/skills tests/exploration/test_exploration_loop.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/exploration_loop.py tests/exploration/test_exploration_loop.py
git commit -m "$(cat <<'EOF'
feat: integrate exploration skill learner behind config

Consult the gated skill selector at frontier-evaluation boundaries while preserving baseline exploration and shadow-mode behavior.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Shadow Mode Behavior

**Files:**
- Modify: `tests/exploration/test_exploration_loop.py`
- Modify: `src/exploration/exploration_loop.py` only if Task 10 did not already preserve shadow mode.

- [ ] **Step 1: Write the shadow-mode test**

Append to `tests/exploration/test_exploration_loop.py`:

```python

def test_skill_learning_shadow_mode_records_without_changing_baseline_bias() -> None:
    bridge = MockBridge(frames=[_make_sensor_frame()])
    slam = MockSLAM()
    octomap = MockOctoMap()
    loop = ExplorationLoop(
        bridge,
        slam,
        octomap,
        config=ExplorationConfig(skill_learning_enabled=True, skill_learning_shadow_mode=True),
    )
    loop.frontier_detector.detect = lambda grid: [_make_cluster([1.0, 0.0, 0.0]), _make_cluster([5.0, 0.0, 0.0])]
    selected_goals = []

    def fake_plan(start: np.ndarray, goal: np.ndarray) -> list[np.ndarray]:
        selected_goals.append(goal)
        return [start, goal]

    loop.path_planner.plan = fake_plan

    def prefer_far(candidate: np.ndarray) -> float:
        return float(candidate[0])

    frame = _make_sensor_frame()
    loop.step_once(frame, step=0, score_fn=prefer_far)

    assert selected_goals
    assert selected_goals[0][0] == 5.0
    assert loop.skill_trace_jsonl()
```

- [ ] **Step 2: Run the shadow-mode test**

Run:

```bash
uv run pytest tests/exploration/test_exploration_loop.py::test_skill_learning_shadow_mode_records_without_changing_baseline_bias -q
```

Expected: PASS if Task 10 implemented shadow mode correctly. If it fails, fix only the shadow-mode branch so `effective_score_fn` remains the caller-provided `score_fn` when `skill_learning_shadow_mode=True`.

- [ ] **Step 3: Run the exploration integration tests**

Run:

```bash
uv run pytest tests/exploration/test_exploration_loop.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

Only run this commit step if commit creation has been explicitly approved for execution.

```bash
git add src/exploration/exploration_loop.py tests/exploration/test_exploration_loop.py
git commit -m "$(cat <<'EOF'
test: cover exploration skill shadow mode

Ensure shadow mode records skill decisions while deterministic baseline frontier bias remains in control.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: Final Verification and Documentation Traceability

**Files:**
- Modify: `docs/superpowers/specs/2026-05-14-exploration-skill-learning-design.md` only if implementation reveals a real spec mismatch.
- No new README or documentation files.

- [ ] **Step 1: Run the focused skill-learning test suite**

Run:

```bash
uv run pytest tests/exploration/skills tests/exploration/test_exploration_loop.py tests/exploration/test_goal_selector.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the broader exploration and coordination tests**

Run:

```bash
uv run pytest tests/exploration tests/coordination/test_coordinator.py -q
```

Expected: PASS.

- [ ] **Step 3: Run static/type checks used by the project**

Run the project’s existing checks. If the repository has no single lint/typecheck command, run the available Python test command only and record that no separate lint/type command was found.

Suggested command:

```bash
uv run pytest -q
```

Expected: PASS, or report unrelated pre-existing failures with exact failing tests.

- [ ] **Step 4: Manually verify no default behavior changed**

Run:

```bash
uv run argus --scene office --static
```

Expected: the baseline static simulation starts without requiring skill-learning flags, model downloads, GPU resources, or new services.

Stop the run after verifying startup and no immediate traceback.

- [ ] **Step 5: Verify no generated caches are staged**

Run:

```bash
git status --short
```

Expected: source and test changes only. Do not stage `__pycache__`, `.pyc`, `.pytest_cache`, `*.tsbuildinfo`, logs, or generated traces.

- [ ] **Step 6: Final commit**

Only run this commit step if commit creation has been explicitly approved for execution and there are verification-only changes to commit.

```bash
git add docs/superpowers/specs/2026-05-14-exploration-skill-learning-design.md
git commit -m "$(cat <<'EOF'
docs: align exploration skill learning spec with implementation

Record any implementation-discovered contract clarifications without expanding learner authority beyond the approved design.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Skip this commit if the spec did not change.

---

## Self-Review

### Spec Coverage

- Skill registry and option-like contracts: Tasks 1, 2, and 4.
- Typed skill proposals: Tasks 1, 2, and 4.
- Skill state encoder and serialization: Task 3.
- Gated online selector: Task 5.
- Skill executor and baseline fallback: Task 6.
- Outcome recorder and replayable traces: Task 7.
- Promotion gate: Task 8.
- Disabled-by-default baseline preservation: Tasks 9 and 10.
- Shadow mode: Task 11.
- Anti-thrashing controls: Task 5 covers minimum dwell and repeated-failure baseline degradation.
- Termination taxonomy: Task 1 defines all termination classes; Tasks 5, 7, and 10 use them.
- Bounded outcome vector plus balanced score: Task 1.
- No low-level locomotion, SLAM, actuator, or map-fusion control: all implementation tasks stay inside `src/exploration/skills/` and use only frontier scoring integration.
- Future RL/options path: supported by stable typed logs and promotion utilities; no RL implementation in this plan.

### Placeholder Scan

The plan contains no `TBD`, no incomplete task, no undefined future implementation step, and no open-ended “write tests for the above” instruction. Each code-writing step includes concrete code or a precise existing-file edit.

### Type Consistency

The same names are used throughout:

- `SkillState`
- `SkillProposal`
- `SkillDecision`
- `SkillOutcomeVector`
- `SkillTermination`
- `SkillAuthority`
- `SkillContract`
- `SkillRegistry`
- `SkillStateEncoder`
- `GatedSkillSelector`
- `SkillExecutor`
- `SkillOutcomeRecorder`
- `PromotionMetricSummary`
- `evaluate_promotion`

### Scope Check

This plan implements v1 gated skill selection and logging only. It does not implement contextual bandits, learned outcome models, SkiMo-style planning, FraCOs-style hierarchy learning, GPU training, model artifact handling, or production dashboard visualization. Those belong in later specs/ADRs after the v1 contracts are stable.
