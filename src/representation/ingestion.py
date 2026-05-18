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
    facts: tuple[ObservationFact, ...] | list[ObservationFact]

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", tuple(self.facts))


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
