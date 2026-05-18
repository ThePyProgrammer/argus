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
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "attributes": dict(self.attributes),
        }
        return data


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
        return self.valid_until is not None and now >= self.valid_until

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
            "valid_until": self.valid_until.isoformat() if self.valid_until is not None else None,
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

    def overlaps(self, other: Commitment) -> bool:
        if self.resource_id != other.resource_id:
            return False
        return self.start < other.end and other.start < self.end

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "robot_id": self.robot_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "task_id": self.task_id,
            "status": self.status,
        }
