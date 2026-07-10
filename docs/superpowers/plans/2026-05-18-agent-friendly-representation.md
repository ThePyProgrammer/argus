# Agent-Friendly Representation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested in-memory Layered Belief Graph + Query Services MVP for agent-friendly swarm world representation.

**Architecture:** Add a new `src/representation` package that models entities, claims, evidence, commitments, and query services. The MVP is a local Python library with synthetic observation ingestion and in-memory fusion/conflict handling; ROS, SLAM, Gaussian splat storage, and live robot integration stay outside this first implementation.

**Tech Stack:** Python 3.10+ dataclasses, standard library `datetime`, pytest, existing `src` package layout.

---

## Scope Check

The approved spec covers a broad platform. This plan implements the smallest independently useful core:

- claim-with-evidence data model
- in-memory belief graph
- synthetic observation ingestion
- conflict/staleness semantics
- four query tool families
- scenario tests proving the minimum demo criteria

This plan deliberately does not implement a ROS node, persistent database, real SLAM extraction, splat-region indexing, or live robot executors. Those should be separate plans after this core library exists.

## File Structure

Create a focused package under `src/representation`:

- `src/representation/__init__.py` — public exports for the representation package.
- `src/representation/models.py` — enums and dataclasses: entity types, relation types, claim statuses, source, evidence, entity, claim, commitment, query result containers.
- `src/representation/graph.py` — in-memory belief graph: entity/claim/commitment storage, status transitions, conflict handling, staleness refresh, indexes.
- `src/representation/ingestion.py` — synthetic observation batch ingestion that turns local extractor outputs into claims.
- `src/representation/query_api.py` — agent-facing query services for perception, navigation, coordination, and belief inspection.

Create tests under `tests/representation`:

- `tests/representation/__init__.py`
- `tests/representation/test_models.py`
- `tests/representation/test_belief_graph.py`
- `tests/representation/test_ingestion.py`
- `tests/representation/test_query_api.py`
- `tests/representation/test_scenarios.py`

---

### Task 1: Representation Models

**Files:**
- Create: `src/representation/__init__.py`
- Create: `src/representation/models.py`
- Create: `tests/representation/__init__.py`
- Test: `tests/representation/test_models.py`

- [ ] **Step 1: Write the failing model tests**

Create `tests/representation/__init__.py` as an empty file.

Create `tests/representation/test_models.py`:

```python
from datetime import datetime, timezone

import pytest

from src.representation.models import (
    Claim,
    ClaimStatus,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)


def test_entity_and_relation_type_values_match_design_spec():
    assert EntityType.ROBOT.value == "robot"
    assert EntityType.FRONTIER.value == "frontier"
    assert EntityType.TERRAIN_PATCH.value == "terrain_patch"
    assert EntityType.COMMITMENT.value == "commitment"

    assert RelationType.CONTAINS.value == "contains"
    assert RelationType.BLOCKS.value == "blocks"
    assert RelationType.REQUIRES_CAPABILITY.value == "requires_capability"
    assert RelationType.CONFLICTS_WITH.value == "conflicts_with"


def test_claim_serializes_required_metadata():
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    claim = Claim(
        id="claim_123",
        subject="path_segment_4",
        predicate=RelationType.BLOCKS,
        object="hazard_12",
        confidence=0.74,
        source=Source(type="robot", id="rover_3"),
        observed_at=observed_at,
        frame_id="map",
        evidence=Evidence(type="point_cloud_slice", uri="local_submap://rover_3/session_22/slice_91"),
    )

    assert claim.to_dict() == {
        "id": "claim_123",
        "subject": "path_segment_4",
        "predicate": "blocks",
        "object": "hazard_12",
        "confidence": 0.74,
        "source": {"type": "robot", "id": "rover_3"},
        "observed_at": "2026-05-18T10:41:00+00:00",
        "frame_id": "map",
        "evidence": {
            "type": "point_cloud_slice",
            "uri": "local_submap://rover_3/session_22/slice_91",
        },
        "status": "active",
        "valid_until": None,
        "conflicts_with": [],
        "metadata": {},
    }


def test_claim_rejects_confidence_outside_unit_interval():
    observed_at = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        Claim(
            id="claim_bad",
            subject="path_segment_4",
            predicate=RelationType.BLOCKS,
            object="hazard_12",
            confidence=1.2,
            source=Source(type="robot", id="rover_3"),
            observed_at=observed_at,
            frame_id="map",
            evidence=Evidence(type="point_cloud_slice", uri="local_submap://slice"),
        )


def test_entity_keeps_label_and_attributes():
    entity = Entity(
        id="rover_3",
        type=EntityType.ROBOT,
        label="Rover 3",
        attributes={"robot_type": "wheeled", "battery": 0.8},
    )

    assert entity.to_dict() == {
        "id": "rover_3",
        "type": "robot",
        "label": "Rover 3",
        "attributes": {"robot_type": "wheeled", "battery": 0.8},
    }


def test_claim_status_values_are_explicit():
    assert [status.value for status in ClaimStatus] == [
        "active",
        "superseded",
        "conflicted",
        "stale",
        "rejected",
    ]
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run:

```bash
pytest tests/representation/test_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.representation'`.

- [ ] **Step 3: Implement the model dataclasses and exports**

Create `src/representation/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    ROBOT = "robot"
    REGION = "region"
    FRONTIER = "frontier"
    PATH_SEGMENT = "path_segment"
    TERRAIN_PATCH = "terrain_patch"
    OBJECT = "object"
    HAZARD = "hazard"
    HUMAN = "human"
    LANDMARK = "landmark"
    AFFORDANCE = "affordance"
    TASK = "task"
    RESOURCE = "resource"
    COMMITMENT = "commitment"


class RelationType(str, Enum):
    CONTAINS = "contains"
    CONNECTS = "connects"
    NEAR = "near"
    BLOCKS = "blocks"
    OBSERVED_BY = "observed_by"
    REACHABLE_BY = "reachable_by"
    ASSIGNED_TO = "assigned_to"
    RESERVED_BY = "reserved_by"
    REQUIRES_CAPABILITY = "requires_capability"
    HAS_AFFORDANCE = "has_affordance"
    CONFLICTS_WITH = "conflicts_with"


class ClaimStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONFLICTED = "conflicted"
    STALE = "stale"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Source:
    type: str
    id: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "id": self.id}


@dataclass(frozen=True)
class Evidence:
    type: str
    uri: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "uri": self.uri}


@dataclass
class Entity:
    id: str
    type: EntityType | str
    label: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.type = EntityType(self.type)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "attributes": dict(self.attributes),
        }


@dataclass
class Claim:
    id: str
    subject: str
    predicate: RelationType | str
    object: str | int | float | bool | None
    confidence: float
    source: Source
    observed_at: datetime
    frame_id: str
    evidence: Evidence
    status: ClaimStatus | str = ClaimStatus.ACTIVE
    valid_until: datetime | None = None
    conflicts_with: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.predicate = RelationType(self.predicate)
        self.status = ClaimStatus(self.status)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def is_stale_at(self, now: datetime) -> bool:
        return self.valid_until is not None and self.valid_until <= now

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "predicate": self.predicate.value,
            "object": self.object,
            "confidence": self.confidence,
            "source": self.source.to_dict(),
            "observed_at": self.observed_at.isoformat(),
            "frame_id": self.frame_id,
            "evidence": self.evidence.to_dict(),
            "status": self.status.value,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "conflicts_with": list(self.conflicts_with),
            "metadata": dict(self.metadata),
        }


@dataclass
class Commitment:
    id: str
    resource_id: str
    robot_id: str
    start: datetime
    end: datetime
    task_id: str | None = None
    status: str = "active"

    def overlaps(self, other: "Commitment") -> bool:
        if self.resource_id != other.resource_id:
            return False
        return self.start < other.end and other.start < self.end

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "robot_id": self.robot_id,
            "task_id": self.task_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "status": self.status,
        }
```

Create `src/representation/__init__.py`:

```python
from src.representation.models import (
    Claim,
    ClaimStatus,
    Commitment,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)

__all__ = [
    "Claim",
    "ClaimStatus",
    "Commitment",
    "Entity",
    "EntityType",
    "Evidence",
    "RelationType",
    "Source",
]
```

- [ ] **Step 4: Run the model tests to verify they pass**

Run:

```bash
pytest tests/representation/test_models.py -q
```

Expected: PASS, `5 passed`.

- [ ] **Step 5: Commit model layer**

```bash
git add src/representation/__init__.py src/representation/models.py tests/representation/__init__.py tests/representation/test_models.py
git commit -m "feat: add representation belief models"
```

---

### Task 2: In-Memory Belief Graph

**Files:**
- Create: `src/representation/graph.py`
- Modify: `src/representation/__init__.py`
- Test: `tests/representation/test_belief_graph.py`

- [ ] **Step 1: Write the failing graph tests**

Create `tests/representation/test_belief_graph.py`:

```python
from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.models import (
    Claim,
    ClaimStatus,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)


def make_claim(
    claim_id: str,
    subject: str = "path_segment_4",
    predicate: RelationType = RelationType.BLOCKS,
    object: str = "hazard_12",
    confidence: float = 0.74,
    valid_until: datetime | None = None,
) -> Claim:
    return Claim(
        id=claim_id,
        subject=subject,
        predicate=predicate,
        object=object,
        confidence=confidence,
        source=Source(type="robot", id="rover_3"),
        observed_at=datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc),
        frame_id="map",
        evidence=Evidence(type="point_cloud_slice", uri=f"local_submap://{claim_id}"),
        valid_until=valid_until,
    )


def test_add_and_get_entity_and_claim():
    graph = BeliefGraph()
    entity = Entity(id="path_segment_4", type=EntityType.PATH_SEGMENT)
    claim = make_claim("claim_1")

    graph.add_entity(entity)
    graph.add_claim(claim)

    assert graph.get_entity("path_segment_4") == entity
    assert graph.get_claim("claim_1") == claim
    assert graph.claims_for_subject("path_segment_4") == [claim]


def test_same_subject_predicate_object_supersedes_older_active_claim():
    graph = BeliefGraph()
    older = make_claim("claim_old", confidence=0.5)
    newer = make_claim("claim_new", confidence=0.9)

    graph.add_claim(older)
    graph.add_claim(newer)

    assert graph.get_claim("claim_old").status == ClaimStatus.SUPERSEDED
    assert graph.get_claim("claim_new").status == ClaimStatus.ACTIVE


def test_same_subject_predicate_different_object_marks_both_conflicted():
    graph = BeliefGraph()
    blocked = make_claim("claim_blocked", object="hazard_12")
    clear = make_claim("claim_clear", object="clear")

    graph.add_claim(blocked)
    graph.add_claim(clear)

    assert graph.get_claim("claim_blocked").status == ClaimStatus.CONFLICTED
    assert graph.get_claim("claim_clear").status == ClaimStatus.CONFLICTED
    assert graph.get_claim("claim_blocked").conflicts_with == ["claim_clear"]
    assert graph.get_claim("claim_clear").conflicts_with == ["claim_blocked"]


def test_refresh_stale_marks_expired_active_claims_stale():
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)
    expired = make_claim("claim_expired", valid_until=now - timedelta(minutes=1))
    fresh = make_claim("claim_fresh", valid_until=now + timedelta(minutes=1))
    graph = BeliefGraph()

    graph.add_claim(expired)
    graph.add_claim(fresh)
    stale_ids = graph.refresh_stale(now)

    assert stale_ids == ["claim_expired"]
    assert graph.get_claim("claim_expired").status == ClaimStatus.STALE
    assert graph.get_claim("claim_fresh").status == ClaimStatus.ACTIVE


def test_active_claims_excludes_superseded_stale_and_rejected():
    graph = BeliefGraph()
    active = make_claim("claim_active")
    stale = make_claim("claim_stale")
    rejected = make_claim("claim_rejected")
    stale.status = ClaimStatus.STALE
    rejected.status = ClaimStatus.REJECTED

    graph.add_claim(active)
    graph.add_claim(stale, resolve=False)
    graph.add_claim(rejected, resolve=False)

    assert graph.active_claims() == [active]
```

- [ ] **Step 2: Run the graph tests to verify they fail**

Run:

```bash
pytest tests/representation/test_belief_graph.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.representation.graph'`.

- [ ] **Step 3: Implement the in-memory belief graph**

Create `src/representation/graph.py`:

```python
from __future__ import annotations

from datetime import datetime

from src.representation.models import Claim, ClaimStatus, Commitment, Entity


class BeliefGraph:
    def __init__(self) -> None:
        self._entities: dict[str, Entity] = {}
        self._claims: dict[str, Claim] = {}
        self._commitments: dict[str, Commitment] = {}
        self._claim_counter = 0
        self._commitment_counter = 0

    def next_claim_id(self) -> str:
        self._claim_counter += 1
        return f"claim_{self._claim_counter:03d}"

    def next_commitment_id(self) -> str:
        self._commitment_counter += 1
        return f"commitment_{self._commitment_counter:03d}"

    def add_entity(self, entity: Entity) -> Entity:
        self._entities[entity.id] = entity
        return entity

    def get_entity(self, entity_id: str) -> Entity | None:
        return self._entities.get(entity_id)

    def entities(self) -> list[Entity]:
        return list(self._entities.values())

    def entities_by_type(self, entity_type: str) -> list[Entity]:
        return [entity for entity in self._entities.values() if entity.type.value == entity_type]

    def add_claim(self, claim: Claim, *, resolve: bool = True) -> Claim:
        self._claims[claim.id] = claim
        if resolve:
            self._resolve_new_claim(claim)
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def claims(self) -> list[Claim]:
        return list(self._claims.values())

    def active_claims(self) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.status == ClaimStatus.ACTIVE]

    def claims_for_subject(self, subject: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.subject == subject]

    def claims_by_predicate(self, predicate: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.predicate.value == predicate]

    def set_claim_status(self, claim_id: str, status: ClaimStatus) -> None:
        claim = self._claims[claim_id]
        claim.status = status

    def refresh_stale(self, now: datetime) -> list[str]:
        stale_ids: list[str] = []
        for claim in self._claims.values():
            if claim.status in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED} and claim.is_stale_at(now):
                claim.status = ClaimStatus.STALE
                stale_ids.append(claim.id)
        return stale_ids

    def add_commitment(self, commitment: Commitment) -> Commitment:
        self._commitments[commitment.id] = commitment
        return commitment

    def commitments(self) -> list[Commitment]:
        return list(self._commitments.values())

    def get_commitment(self, commitment_id: str) -> Commitment | None:
        return self._commitments.get(commitment_id)

    def _resolve_new_claim(self, new_claim: Claim) -> None:
        if new_claim.status != ClaimStatus.ACTIVE:
            return

        for old_claim in self._claims.values():
            if old_claim.id == new_claim.id:
                continue
            if old_claim.status not in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED}:
                continue
            if old_claim.subject != new_claim.subject:
                continue
            if old_claim.predicate != new_claim.predicate:
                continue
            if old_claim.object == new_claim.object:
                old_claim.status = ClaimStatus.SUPERSEDED
                continue

            old_claim.status = ClaimStatus.CONFLICTED
            new_claim.status = ClaimStatus.CONFLICTED
            if new_claim.id not in old_claim.conflicts_with:
                old_claim.conflicts_with.append(new_claim.id)
            if old_claim.id not in new_claim.conflicts_with:
                new_claim.conflicts_with.append(old_claim.id)
```

Update `src/representation/__init__.py`:

```python
from src.representation.graph import BeliefGraph
from src.representation.models import (
    Claim,
    ClaimStatus,
    Commitment,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)

__all__ = [
    "BeliefGraph",
    "Claim",
    "ClaimStatus",
    "Commitment",
    "Entity",
    "EntityType",
    "Evidence",
    "RelationType",
    "Source",
]
```

- [ ] **Step 4: Run graph and model tests**

Run:

```bash
pytest tests/representation/test_models.py tests/representation/test_belief_graph.py -q
```

Expected: PASS, `10 passed`.

- [ ] **Step 5: Commit graph layer**

```bash
git add src/representation/__init__.py src/representation/graph.py tests/representation/test_belief_graph.py
git commit -m "feat: add in-memory belief graph"
```

---

### Task 3: Synthetic Observation Ingestion

**Files:**
- Create: `src/representation/ingestion.py`
- Modify: `src/representation/__init__.py`
- Test: `tests/representation/test_ingestion.py`

- [ ] **Step 1: Write the failing ingestion tests**

Create `tests/representation/test_ingestion.py`:

```python
from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import ClaimStatus, EntityType, RelationType, Source


def test_ingest_observation_batch_creates_entities_and_claims():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    batch = ObservationBatch(
        source=Source(type="robot", id="drone_2"),
        observed_at=observed_at,
        facts=[
            ObservationFact(
                subject="region_8",
                subject_type=EntityType.REGION,
                predicate=RelationType.CONTAINS,
                object="object_42",
                object_type=EntityType.OBJECT,
                object_label="red_vehicle",
                confidence=0.81,
                evidence_type="image",
                evidence_uri="image://drone_2/frame_5401",
            )
        ],
    )

    claims = ingestor.ingest(batch)

    assert [claim.id for claim in claims] == ["claim_001"]
    assert graph.get_entity("region_8").type == EntityType.REGION
    assert graph.get_entity("object_42").label == "red_vehicle"
    assert graph.get_claim("claim_001").source.id == "drone_2"


def test_ingest_conflicting_robot_reports_keeps_conflict_visible():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_3"),
            observed_at=observed_at,
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="hazard_12",
                    object_type=EntityType.HAZARD,
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                )
            ],
        )
    )
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_5"),
            observed_at=observed_at + timedelta(seconds=5),
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="clear",
                    confidence=0.66,
                    evidence_type="image",
                    evidence_uri="image://rover_5/frame_8",
                )
            ],
        )
    )

    statuses = {claim.id: claim.status for claim in graph.claims_for_subject("path_segment_4")}
    assert statuses == {
        "claim_001": ClaimStatus.CONFLICTED,
        "claim_002": ClaimStatus.CONFLICTED,
    }
```

- [ ] **Step 2: Run the ingestion tests to verify they fail**

Run:

```bash
pytest tests/representation/test_ingestion.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.representation.ingestion'`.

- [ ] **Step 3: Implement synthetic observation ingestion**

Create `src/representation/ingestion.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.representation.graph import BeliefGraph
from src.representation.models import Claim, Entity, EntityType, Evidence, RelationType, Source


@dataclass(frozen=True)
class ObservationFact:
    subject: str
    subject_type: EntityType | str
    predicate: RelationType | str
    object: str | int | float | bool | None
    confidence: float
    evidence_type: str
    evidence_uri: str
    object_type: EntityType | str | None = None
    subject_label: str | None = None
    object_label: str | None = None
    frame_id: str = "map"
    valid_until: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationBatch:
    source: Source
    observed_at: datetime
    facts: list[ObservationFact]


class ObservationIngestor:
    def __init__(self, graph: BeliefGraph) -> None:
        self._graph = graph

    def ingest(self, batch: ObservationBatch) -> list[Claim]:
        claims: list[Claim] = []
        for fact in batch.facts:
            self._ensure_entity(fact.subject, fact.subject_type, fact.subject_label)
            if isinstance(fact.object, str) and fact.object_type is not None:
                self._ensure_entity(fact.object, fact.object_type, fact.object_label)

            claim = Claim(
                id=self._graph.next_claim_id(),
                subject=fact.subject,
                predicate=fact.predicate,
                object=fact.object,
                confidence=fact.confidence,
                source=batch.source,
                observed_at=batch.observed_at,
                frame_id=fact.frame_id,
                evidence=Evidence(type=fact.evidence_type, uri=fact.evidence_uri),
                valid_until=fact.valid_until,
                metadata=dict(fact.metadata),
            )
            self._graph.add_claim(claim)
            claims.append(claim)
        return claims

    def _ensure_entity(
        self,
        entity_id: str,
        entity_type: EntityType | str,
        label: str | None,
    ) -> None:
        existing = self._graph.get_entity(entity_id)
        if existing is not None:
            if label is not None:
                existing.label = label
            return
        self._graph.add_entity(Entity(id=entity_id, type=entity_type, label=label))
```

Update `src/representation/__init__.py`:

```python
from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import (
    Claim,
    ClaimStatus,
    Commitment,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)

__all__ = [
    "BeliefGraph",
    "Claim",
    "ClaimStatus",
    "Commitment",
    "Entity",
    "EntityType",
    "Evidence",
    "ObservationBatch",
    "ObservationFact",
    "ObservationIngestor",
    "RelationType",
    "Source",
]
```

- [ ] **Step 4: Run ingestion tests and earlier representation tests**

Run:

```bash
pytest tests/representation/test_models.py tests/representation/test_belief_graph.py tests/representation/test_ingestion.py -q
```

Expected: PASS, `12 passed`.

- [ ] **Step 5: Commit ingestion layer**

```bash
git add src/representation/__init__.py src/representation/ingestion.py tests/representation/test_ingestion.py
git commit -m "feat: ingest synthetic representation observations"
```

---

### Task 4: Perception and Belief Query Services

**Files:**
- Create: `src/representation/query_api.py`
- Modify: `src/representation/__init__.py`
- Test: `tests/representation/test_query_api.py`

- [ ] **Step 1: Write failing tests for perception and belief queries**

Create `tests/representation/test_query_api.py`:

```python
from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import EntityType, RelationType, Source
from src.representation.query_api import WorldQueryAPI


def build_graph() -> BeliefGraph:
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=now,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_42",
                    object_type=EntityType.OBJECT,
                    object_label="red_vehicle",
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5401",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="hazard_12",
                    object_type=EntityType.HAZARD,
                    object_label="fallen_tree",
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                    valid_until=now + timedelta(minutes=5),
                ),
            ],
        )
    )
    return graph


def test_find_objects_filters_by_label_and_min_confidence():
    api = WorldQueryAPI(build_graph())

    result = api.find_objects("vehicle", min_confidence=0.8)

    assert result == {
        "objects": [
            {
                "id": "object_42",
                "label": "red_vehicle",
                "region": "region_8",
                "confidence": 0.81,
                "source": {"type": "robot", "id": "drone_2"},
                "observed_at": "2026-05-18T10:41:00+00:00",
                "evidence": {"type": "image", "uri": "image://drone_2/frame_5401"},
                "claim_id": "claim_001",
            }
        ]
    }


def test_find_hazards_returns_hazard_claims_for_region():
    api = WorldQueryAPI(build_graph())

    result = api.find_hazards(region="region_8")

    assert result["hazards"][0]["id"] == "hazard_12"
    assert result["hazards"][0]["label"] == "fallen_tree"
    assert result["hazards"][0]["claim_id"] == "claim_002"


def test_summarize_region_counts_objects_hazards_and_claims():
    api = WorldQueryAPI(build_graph())

    result = api.summarize_region("region_8")

    assert result == {
        "region": "region_8",
        "objects": 1,
        "hazards": 1,
        "active_claims": 2,
        "conflicted_claims": 0,
        "stale_claims": 0,
    }


def test_retrieve_evidence_returns_claim_evidence():
    api = WorldQueryAPI(build_graph())

    result = api.retrieve_evidence("claim_001")

    assert result == {
        "claim_id": "claim_001",
        "evidence": {"type": "image", "uri": "image://drone_2/frame_5401"},
    }


def test_belief_queries_report_confidence_staleness_and_confirmation_request():
    graph = build_graph()
    api = WorldQueryAPI(graph)
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)

    assert api.get_confidence("claim_002") == {"claim": "claim_002", "confidence": 0.74, "status": "active"}
    stale = api.check_staleness("claim_002", now=now)
    assert stale["status"] == "stale"
    assert stale["recommended_action"] == {
        "request_confirmation": {
            "target": "region_8",
            "preferred_robot_type": None,
        }
    }
    assert api.request_confirmation("path_segment_4", preferred_robot_type="drone") == {
        "request_confirmation": {
            "target": "path_segment_4",
            "preferred_robot_type": "drone",
        }
    }
```

- [ ] **Step 2: Run query tests to verify they fail**

Run:

```bash
pytest tests/representation/test_query_api.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.representation.query_api'`.

- [ ] **Step 3: Implement perception and belief queries**

Create `src/representation/query_api.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from src.representation.graph import BeliefGraph
from src.representation.models import Claim, ClaimStatus, Commitment, EntityType, RelationType


class WorldQueryAPI:
    def __init__(self, graph: BeliefGraph) -> None:
        self._graph = graph

    def find_objects(
        self,
        query: str,
        region: str | None = None,
        min_confidence: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        query_lower = query.lower()
        objects: list[dict[str, Any]] = []
        for claim in self._graph.claims_by_predicate(RelationType.CONTAINS.value):
            if claim.status != ClaimStatus.ACTIVE:
                continue
            if region is not None and claim.subject != region:
                continue
            if min_confidence is not None and claim.confidence < min_confidence:
                continue
            if not isinstance(claim.object, str):
                continue
            entity = self._graph.get_entity(claim.object)
            if entity is None or entity.type != EntityType.OBJECT:
                continue
            label = entity.label or entity.id
            if query_lower not in label.lower():
                continue
            objects.append(self._entity_claim_view(entity.id, label, claim))
        return {"objects": objects}

    def find_hazards(
        self,
        region: str | None = None,
        hazard_type: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        hazards: list[dict[str, Any]] = []
        for claim in self._graph.claims_by_predicate(RelationType.CONTAINS.value):
            if claim.status != ClaimStatus.ACTIVE:
                continue
            if region is not None and claim.subject != region:
                continue
            if not isinstance(claim.object, str):
                continue
            entity = self._graph.get_entity(claim.object)
            if entity is None or entity.type != EntityType.HAZARD:
                continue
            label = entity.label or entity.id
            if hazard_type is not None and hazard_type.lower() not in label.lower():
                continue
            hazards.append(self._entity_claim_view(entity.id, label, claim))
        return {"hazards": hazards}

    def summarize_region(self, region_id: str, include_uncertainty: bool = True) -> dict[str, Any]:
        claims = [claim for claim in self._graph.claims_for_subject(region_id)]
        object_count = 0
        hazard_count = 0
        for claim in claims:
            if claim.predicate != RelationType.CONTAINS or not isinstance(claim.object, str):
                continue
            entity = self._graph.get_entity(claim.object)
            if entity is None:
                continue
            if entity.type == EntityType.OBJECT:
                object_count += 1
            if entity.type == EntityType.HAZARD:
                hazard_count += 1
        return {
            "region": region_id,
            "objects": object_count,
            "hazards": hazard_count,
            "active_claims": sum(1 for claim in claims if claim.status == ClaimStatus.ACTIVE),
            "conflicted_claims": sum(1 for claim in claims if claim.status == ClaimStatus.CONFLICTED),
            "stale_claims": sum(1 for claim in claims if claim.status == ClaimStatus.STALE),
        }

    def retrieve_evidence(self, claim_id: str) -> dict[str, Any]:
        claim = self._require_claim(claim_id)
        return {"claim_id": claim.id, "evidence": claim.evidence.to_dict()}

    def get_confidence(self, claim_or_entity_id: str) -> dict[str, Any]:
        claim = self._graph.get_claim(claim_or_entity_id)
        if claim is not None:
            return {"claim": claim.id, "confidence": claim.confidence, "status": claim.status.value}
        claims = self._graph.claims_for_subject(claim_or_entity_id)
        if not claims:
            return {"entity": claim_or_entity_id, "confidence": None, "status": "unknown"}
        best = max(claims, key=lambda item: item.confidence)
        return {"entity": claim_or_entity_id, "confidence": best.confidence, "status": best.status.value}

    def check_staleness(self, claim_or_region_id: str, now: datetime) -> dict[str, Any]:
        self._graph.refresh_stale(now)
        claim = self._graph.get_claim(claim_or_region_id)
        if claim is not None:
            target = claim.subject
            status = claim.status.value
            claim_id = claim.id
        else:
            target = claim_or_region_id
            stale_claims = [
                item for item in self._graph.claims_for_subject(claim_or_region_id)
                if item.status == ClaimStatus.STALE
            ]
            status = "stale" if stale_claims else "fresh"
            claim_id = stale_claims[0].id if stale_claims else None
        result: dict[str, Any] = {"target": target, "status": status}
        if claim_id is not None:
            result["claim"] = claim_id
        if status == "stale":
            result["recommended_action"] = self.request_confirmation(target)["request_confirmation"]
            result["recommended_action"] = {"request_confirmation": result["recommended_action"]}
        return result

    def compare_claims(self, claim_ids: list[str]) -> dict[str, Any]:
        claims = [self._require_claim(claim_id) for claim_id in claim_ids]
        return {
            "claims": [claim.to_dict() for claim in claims],
            "conflicts": [claim.id for claim in claims if claim.status == ClaimStatus.CONFLICTED],
        }

    def request_confirmation(
        self,
        target: str,
        preferred_robot_type: str | None = None,
    ) -> dict[str, dict[str, str | None]]:
        return {
            "request_confirmation": {
                "target": target,
                "preferred_robot_type": preferred_robot_type,
            }
        }

    def _entity_claim_view(self, entity_id: str, label: str, claim: Claim) -> dict[str, Any]:
        return {
            "id": entity_id,
            "label": label,
            "region": claim.subject,
            "confidence": claim.confidence,
            "source": claim.source.to_dict(),
            "observed_at": claim.observed_at.isoformat(),
            "evidence": claim.evidence.to_dict(),
            "claim_id": claim.id,
        }

    def _require_claim(self, claim_id: str) -> Claim:
        claim = self._graph.get_claim(claim_id)
        if claim is None:
            raise KeyError(f"unknown claim: {claim_id}")
        return claim
```

Update `src/representation/__init__.py`:

```python
from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import (
    Claim,
    ClaimStatus,
    Commitment,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)
from src.representation.query_api import WorldQueryAPI

__all__ = [
    "BeliefGraph",
    "Claim",
    "ClaimStatus",
    "Commitment",
    "Entity",
    "EntityType",
    "Evidence",
    "ObservationBatch",
    "ObservationFact",
    "ObservationIngestor",
    "RelationType",
    "Source",
    "WorldQueryAPI",
]
```

- [ ] **Step 4: Run query tests**

Run:

```bash
pytest tests/representation/test_query_api.py -q
```

Expected: PASS, `5 passed`.

- [ ] **Step 5: Run all representation tests so far**

Run:

```bash
pytest tests/representation -q
```

Expected: PASS, `17 passed`.

- [ ] **Step 6: Commit perception and belief query services**

```bash
git add src/representation/__init__.py src/representation/query_api.py tests/representation/test_query_api.py
git commit -m "feat: add representation query services"
```

---

### Task 5: Navigation Query Services

**Files:**
- Modify: `src/representation/query_api.py`
- Test: `tests/representation/test_query_api.py`

- [ ] **Step 1: Append failing tests for navigation queries**

Append to `tests/representation/test_query_api.py`:

```python

def test_navigation_queries_reject_blocked_path_and_suggest_alternatives():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_3"),
            observed_at=now,
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="hazard_12",
                    object_type=EntityType.HAZARD,
                    object_label="fallen_tree",
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                    metadata={"alternatives": [{"send_robot": "legged_1"}, {"route": "path_segment_7"}]},
                )
            ],
        )
    )
    api = WorldQueryAPI(graph)

    traversability = api.query_traversability("path_segment_4", robot_type="wheeled")
    route = api.plan_route("rover_2", goal="path_segment_4")
    blockage = api.explain_blockage("path_segment_4")

    assert traversability["traversable"] is False
    assert traversability["blocking_claims"] == ["claim_001"]
    assert route["feasible"] is False
    assert route["reason"] == "path_segment_4 blocked_by hazard_12"
    assert route["alternatives"] == [{"send_robot": "legged_1"}, {"route": "path_segment_7"}]
    assert blockage["blockages"][0]["claim_id"] == "claim_001"


def test_get_frontiers_filters_by_region_and_robot_type():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=now,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="frontier_9",
                    object_type=EntityType.FRONTIER,
                    confidence=0.9,
                    evidence_type="frontier_detector",
                    evidence_uri="frontier://region_8/frontier_9",
                    metadata={"robot_types": ["drone", "legged"]},
                )
            ],
        )
    )
    api = WorldQueryAPI(graph)

    assert api.get_frontiers(region="region_8", robot_type="drone") == {
        "frontiers": [
            {
                "id": "frontier_9",
                "region": "region_8",
                "confidence": 0.9,
                "claim_id": "claim_001",
                "robot_types": ["drone", "legged"],
            }
        ]
    }
    assert api.get_frontiers(region="region_8", robot_type="wheeled") == {"frontiers": []}
```

- [ ] **Step 2: Run navigation query tests to verify they fail**

Run:

```bash
pytest tests/representation/test_query_api.py::test_navigation_queries_reject_blocked_path_and_suggest_alternatives tests/representation/test_query_api.py::test_get_frontiers_filters_by_region_and_robot_type -q
```

Expected: FAIL with `AttributeError` for missing navigation methods.

- [ ] **Step 3: Add navigation methods to `WorldQueryAPI`**

Insert these methods into `WorldQueryAPI` in `src/representation/query_api.py` before `_entity_claim_view`:

```python
    def get_frontiers(
        self,
        region: str | None = None,
        robot_type: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        frontiers: list[dict[str, Any]] = []
        for claim in self._graph.claims_by_predicate(RelationType.CONTAINS.value):
            if claim.status != ClaimStatus.ACTIVE:
                continue
            if region is not None and claim.subject != region:
                continue
            if not isinstance(claim.object, str):
                continue
            entity = self._graph.get_entity(claim.object)
            if entity is None or entity.type != EntityType.FRONTIER:
                continue
            robot_types = claim.metadata.get("robot_types", [])
            if robot_type is not None and robot_type not in robot_types:
                continue
            frontiers.append(
                {
                    "id": entity.id,
                    "region": claim.subject,
                    "confidence": claim.confidence,
                    "claim_id": claim.id,
                    "robot_types": list(robot_types),
                }
            )
        return {"frontiers": frontiers}

    def query_traversability(self, region_or_path: str, robot_type: str) -> dict[str, Any]:
        blocking_claims = self._blocking_claims(region_or_path)
        if not blocking_claims:
            return {
                "target": region_or_path,
                "robot_type": robot_type,
                "traversable": True,
                "blocking_claims": [],
            }
        return {
            "target": region_or_path,
            "robot_type": robot_type,
            "traversable": False,
            "blocking_claims": [claim.id for claim in blocking_claims],
            "confidence": max(claim.confidence for claim in blocking_claims),
        }

    def plan_route(
        self,
        robot_id: str,
        goal: str,
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        blocking_claims = self._blocking_claims(goal)
        if not blocking_claims:
            return {"robot": robot_id, "goal": goal, "feasible": True, "route": [goal]}
        strongest = max(blocking_claims, key=lambda claim: claim.confidence)
        return {
            "robot": robot_id,
            "goal": goal,
            "feasible": False,
            "reason": f"{strongest.subject} blocked_by {strongest.object}",
            "confidence": strongest.confidence,
            "source": strongest.source.to_dict(),
            "alternatives": list(strongest.metadata.get("alternatives", [])),
        }

    def explain_blockage(self, route_or_region: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "blockages": [
                {
                    "claim_id": claim.id,
                    "subject": claim.subject,
                    "object": claim.object,
                    "confidence": claim.confidence,
                    "source": claim.source.to_dict(),
                    "evidence": claim.evidence.to_dict(),
                    "status": claim.status.value,
                }
                for claim in self._blocking_claims(route_or_region)
            ]
        }

    def _blocking_claims(self, target: str) -> list[Claim]:
        return [
            claim for claim in self._graph.claims_for_subject(target)
            if claim.predicate == RelationType.BLOCKS
            and claim.status in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED}
            and claim.object != "clear"
        ]
```

- [ ] **Step 4: Run query tests**

Run:

```bash
pytest tests/representation/test_query_api.py -q
```

Expected: PASS, `7 passed`.

- [ ] **Step 5: Run all representation tests**

Run:

```bash
pytest tests/representation -q
```

Expected: PASS, `19 passed`.

- [ ] **Step 6: Commit navigation query services**

```bash
git add src/representation/query_api.py tests/representation/test_query_api.py
git commit -m "feat: add navigation representation queries"
```

---

### Task 6: Coordination Query Services

**Files:**
- Modify: `src/representation/query_api.py`
- Test: `tests/representation/test_query_api.py`

- [ ] **Step 1: Append failing tests for coordination queries**

Append to `tests/representation/test_query_api.py`:

```python

def test_allocate_task_selects_robot_with_required_capability_and_best_battery():
    graph = BeliefGraph()
    graph.add_entity(EntityType.ROBOT and __import__("src.representation.models", fromlist=["Entity"]).Entity(
        id="rover_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate"], "battery": 0.9},
    ))
    graph.add_entity(__import__("src.representation.models", fromlist=["Entity"]).Entity(
        id="legged_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.7},
    ))
    graph.add_entity(__import__("src.representation.models", fromlist=["Entity"]).Entity(
        id="legged_2",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.8},
    ))
    graph.add_entity(__import__("src.representation.models", fromlist=["Entity"]).Entity(
        id="task_rough_frontier",
        type=EntityType.TASK,
        attributes={"required_capabilities": ["navigate", "rough_terrain"]},
    ))
    api = WorldQueryAPI(graph)

    result = api.allocate_task("task_rough_frontier")

    assert result["selected_robot"] == "legged_2"
    assert result["reason"] == "highest feasibility under capability and battery constraints"
    assert result["commitments_created"] == ["commitment_001"]
    assert graph.get_commitment("commitment_001").robot_id == "legged_2"


def test_reserve_resource_and_detect_conflicts_for_overlapping_commitments():
    graph = BeliefGraph()
    api = WorldQueryAPI(graph)
    start = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 18, 10, 10, tzinfo=timezone.utc)

    first = api.reserve_resource("corridor_4", "rover_2", (start, end))
    second = api.reserve_resource("corridor_4", "rover_3", (start + timedelta(minutes=5), end + timedelta(minutes=5)))
    conflicts = api.detect_conflicts(second["commitment"])

    assert first["accepted"] is True
    assert second["accepted"] is False
    assert conflicts == {
        "conflicts": [
            {
                "commitment": "commitment_001",
                "resource_id": "corridor_4",
                "robot_id": "rover_2",
            }
        ]
    }
    assert api.list_commitments(resource_id="corridor_4")["commitments"][0]["id"] == "commitment_001"
```

Then replace the dynamic imports at the top of `tests/representation/test_query_api.py` by adding `Entity` to the existing model import line:

```python
from src.representation.models import Entity, EntityType, RelationType, Source
```

Replace the three `graph.add_entity(...)` robot/task setup calls with direct `Entity(...)` calls:

```python
    graph.add_entity(Entity(
        id="rover_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate"], "battery": 0.9},
    ))
    graph.add_entity(Entity(
        id="legged_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.7},
    ))
    graph.add_entity(Entity(
        id="legged_2",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.8},
    ))
    graph.add_entity(Entity(
        id="task_rough_frontier",
        type=EntityType.TASK,
        attributes={"required_capabilities": ["navigate", "rough_terrain"]},
    ))
```

- [ ] **Step 2: Run coordination tests to verify they fail**

Run:

```bash
pytest tests/representation/test_query_api.py::test_allocate_task_selects_robot_with_required_capability_and_best_battery tests/representation/test_query_api.py::test_reserve_resource_and_detect_conflicts_for_overlapping_commitments -q
```

Expected: FAIL with `AttributeError` for missing coordination methods.

- [ ] **Step 3: Add coordination methods to `WorldQueryAPI`**

Add `Commitment` and `EntityType` imports if they are not already present:

```python
from src.representation.models import Claim, ClaimStatus, Commitment, EntityType, RelationType
```

Insert these methods into `WorldQueryAPI` before `_entity_claim_view`:

```python
    def allocate_task(
        self,
        task: str,
        candidate_robots: list[str] | None = None,
    ) -> dict[str, Any]:
        task_entity = self._graph.get_entity(task)
        if task_entity is None:
            raise KeyError(f"unknown task: {task}")
        required = set(task_entity.attributes.get("required_capabilities", []))
        candidates = [
            entity for entity in self._graph.entities_by_type(EntityType.ROBOT.value)
            if candidate_robots is None or entity.id in candidate_robots
        ]
        feasible = [
            entity for entity in candidates
            if required.issubset(set(entity.attributes.get("capabilities", [])))
        ]
        if not feasible:
            return {
                "selected_robot": None,
                "reason": "no candidate robot satisfies required capabilities",
                "commitments_created": [],
                "conflicts": [],
            }
        selected = max(feasible, key=lambda entity: entity.attributes.get("battery", 0.0))
        commitment = Commitment(
            id=self._graph.next_commitment_id(),
            resource_id=task,
            robot_id=selected.id,
            task_id=task,
            start=datetime.min,
            end=datetime.max,
        )
        self._graph.add_commitment(commitment)
        return {
            "selected_robot": selected.id,
            "reason": "highest feasibility under capability and battery constraints",
            "commitments_created": [commitment.id],
            "conflicts": [],
        }

    def reserve_resource(
        self,
        resource_id: str,
        robot_id: str,
        time_window: tuple[datetime, datetime],
    ) -> dict[str, Any]:
        commitment = Commitment(
            id=self._graph.next_commitment_id(),
            resource_id=resource_id,
            robot_id=robot_id,
            start=time_window[0],
            end=time_window[1],
        )
        conflicts = self._conflicting_commitments(commitment)
        if conflicts:
            return {"accepted": False, "commitment": commitment.to_dict(), "conflicts": conflicts}
        self._graph.add_commitment(commitment)
        return {"accepted": True, "commitment": commitment.to_dict(), "conflicts": []}

    def list_commitments(
        self,
        region: str | None = None,
        robot_id: str | None = None,
        resource_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        commitments = self._graph.commitments()
        if robot_id is not None:
            commitments = [item for item in commitments if item.robot_id == robot_id]
        if resource_id is not None:
            commitments = [item for item in commitments if item.resource_id == resource_id]
        if region is not None:
            commitments = [item for item in commitments if item.resource_id == region]
        return {"commitments": [item.to_dict() for item in commitments]}

    def detect_conflicts(self, plan_or_commitment: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        incoming = Commitment(
            id=plan_or_commitment["id"],
            resource_id=plan_or_commitment["resource_id"],
            robot_id=plan_or_commitment["robot_id"],
            task_id=plan_or_commitment.get("task_id"),
            start=datetime.fromisoformat(plan_or_commitment["start"]),
            end=datetime.fromisoformat(plan_or_commitment["end"]),
            status=plan_or_commitment.get("status", "active"),
        )
        return {"conflicts": self._conflicting_commitments(incoming)}

    def _conflicting_commitments(self, incoming: Commitment) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        for existing in self._graph.commitments():
            if existing.robot_id == incoming.robot_id:
                continue
            if not existing.overlaps(incoming):
                continue
            conflicts.append(
                {
                    "commitment": existing.id,
                    "resource_id": existing.resource_id,
                    "robot_id": existing.robot_id,
                }
            )
        return conflicts
```

- [ ] **Step 4: Run query tests**

Run:

```bash
pytest tests/representation/test_query_api.py -q
```

Expected: PASS, `9 passed`.

- [ ] **Step 5: Run all representation tests**

Run:

```bash
pytest tests/representation -q
```

Expected: PASS, `21 passed`.

- [ ] **Step 6: Commit coordination query services**

```bash
git add src/representation/query_api.py tests/representation/test_query_api.py
git commit -m "feat: add coordination representation queries"
```

---

### Task 7: End-to-End Scenario Tests

**Files:**
- Test: `tests/representation/test_scenarios.py`
- Modify implementation files only if these tests expose bugs in previous tasks.

- [ ] **Step 1: Write scenario tests covering the minimum demo**

Create `tests/representation/test_scenarios.py`:

```python
from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import Entity, EntityType, RelationType, Source
from src.representation.query_api import WorldQueryAPI


def test_minimum_demo_two_robot_conflict_and_four_query_families():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    graph.add_entity(Entity(
        id="drone_2",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "confirm"], "battery": 0.6},
    ))
    graph.add_entity(Entity(
        id="legged_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.8},
    ))
    graph.add_entity(Entity(
        id="task_inspect_path",
        type=EntityType.TASK,
        attributes={"required_capabilities": ["navigate", "rough_terrain"]},
    ))

    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_3"),
            observed_at=now,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_42",
                    object_type=EntityType.OBJECT,
                    object_label="red_vehicle",
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://rover_3/frame_1",
                ),
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="hazard_12",
                    object_type=EntityType.HAZARD,
                    object_label="fallen_tree",
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                    valid_until=now + timedelta(minutes=5),
                    metadata={"alternatives": [{"send_robot": "legged_1"}]},
                ),
            ],
        )
    )
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_5"),
            observed_at=now + timedelta(seconds=5),
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="clear",
                    confidence=0.66,
                    evidence_type="image",
                    evidence_uri="image://rover_5/frame_8",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="frontier_9",
                    object_type=EntityType.FRONTIER,
                    confidence=0.9,
                    evidence_type="frontier_detector",
                    evidence_uri="frontier://region_8/frontier_9",
                    metadata={"robot_types": ["drone", "legged"]},
                ),
            ],
        )
    )

    api = WorldQueryAPI(graph)

    assert api.find_objects("vehicle")["objects"][0]["id"] == "object_42"
    assert api.get_frontiers(region="region_8", robot_type="drone")["frontiers"][0]["id"] == "frontier_9"
    assert api.compare_claims(["claim_002", "claim_003"])["conflicts"] == ["claim_002", "claim_003"]
    assert api.allocate_task("task_inspect_path")["selected_robot"] == "legged_1"


def test_stale_blockage_degrades_route_recommendation_to_confirmation():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_3"),
            observed_at=now,
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="hazard_12",
                    object_type=EntityType.HAZARD,
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                    valid_until=now + timedelta(minutes=1),
                )
            ],
        )
    )
    api = WorldQueryAPI(graph)

    stale = api.check_staleness("claim_001", now=now + timedelta(minutes=2))
    route = api.plan_route("rover_2", goal="path_segment_4")

    assert stale["status"] == "stale"
    assert route == {"robot": "rover_2", "goal": "path_segment_4", "feasible": True, "route": ["path_segment_4"]}
    assert api.request_confirmation("path_segment_4", preferred_robot_type="drone") == {
        "request_confirmation": {
            "target": "path_segment_4",
            "preferred_robot_type": "drone",
        }
    }
```

- [ ] **Step 2: Run scenario tests**

Run:

```bash
pytest tests/representation/test_scenarios.py -q
```

Expected: PASS, `2 passed`.

- [ ] **Step 3: Run all representation tests**

Run:

```bash
pytest tests/representation -q
```

Expected: PASS, `23 passed`.

- [ ] **Step 4: Run a wider smoke test for nearby packages**

Run:

```bash
pytest tests/representation tests/coordination/test_map_merger.py tests/exploration/test_costmap.py -q
```

Expected: PASS. The exact count may vary if existing tests are added before execution, but there must be zero failures.

- [ ] **Step 5: Commit scenario coverage**

```bash
git add tests/representation/test_scenarios.py src/representation
git commit -m "test: cover agent-friendly representation scenarios"
```

---

### Task 8: Package Export and Plan Verification

**Files:**
- Modify: `src/representation/__init__.py` only if exports are missing.
- No new tests unless verification exposes a missing export.

- [ ] **Step 1: Verify public imports work**

Run:

```bash
python - <<'PY'
from src.representation import (
    BeliefGraph,
    Entity,
    EntityType,
    ObservationBatch,
    ObservationFact,
    ObservationIngestor,
    RelationType,
    Source,
    WorldQueryAPI,
)

print(BeliefGraph.__name__)
print(EntityType.ROBOT.value)
print(RelationType.BLOCKS.value)
print(WorldQueryAPI.__name__)
PY
```

Expected output:

```text
BeliefGraph
robot
blocks
WorldQueryAPI
```

- [ ] **Step 2: Run the final representation test suite**

Run:

```bash
pytest tests/representation -q
```

Expected: PASS, zero failures.

- [ ] **Step 3: Run selected nearby regression tests**

Run:

```bash
pytest tests/coordination/test_map_merger.py tests/exploration/test_costmap.py -q
```

Expected: PASS, zero failures.

- [ ] **Step 4: Inspect changed files**

Run:

```bash
git status --short
git diff --stat
```

Expected: only `src/representation/*` and `tests/representation/*` remain changed if all earlier commits were made; no unrelated frontend, planning, cache, or generated files should be staged.

- [ ] **Step 5: Final commit if any verification-only changes were needed**

If Step 4 shows uncommitted representation files, commit them:

```bash
git add src/representation tests/representation
git commit -m "feat: finalize representation package exports"
```

If Step 4 shows no representation changes, do not create an empty commit.

---

## Self-Review

### Spec Coverage

- Layered Belief Graph + Query Services: covered by `BeliefGraph`, `ObservationIngestor`, and `WorldQueryAPI`.
- Claim-with-evidence data model: covered by `Claim`, `Source`, `Evidence`, and model tests.
- Entity/relation/status categories: covered by enums and tests.
- Four query tool families: covered by `WorldQueryAPI` perception, navigation, coordination, and belief methods.
- Observation-to-belief flow: covered by `ObservationIngestor` and ingestion tests.
- Agent-decision-to-action flow: covered by route planning, task allocation, resource reservation, and commitment tests.
- Conflict/staleness semantics: covered by graph tests, query tests, and scenario tests.
- Minimum demo success criteria: covered by `test_minimum_demo_two_robot_conflict_and_four_query_families` and `test_stale_blockage_degrades_route_recommendation_to_confirmation`.

### Deliberate Deferrals

- Real point-cloud/splat evidence slicing is represented by evidence URIs only.
- Persistent storage is deferred; the MVP uses in-memory storage.
- ROS node/service wiring is deferred.
- Full route planning is deferred; MVP route feasibility checks target-level blockage and returns grounded explanations.
- Learned object detection and terrain extraction are deferred; synthetic observation facts stand in for extractor outputs.

### Type Consistency

- Entity types, relation types, and claim statuses are centralized in `src/representation/models.py`.
- Query services use `BeliefGraph` and return dictionaries shaped like the approved spec examples.
- The `source` field is consistently modeled as `Source(type, id)`.
- Claim object values use the spec field name `object`.
