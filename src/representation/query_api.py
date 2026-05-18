from __future__ import annotations

from datetime import datetime, timezone
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
        claims = self._graph.claims_for_subject(region_id)
        object_count = 0
        hazard_count = 0
        for claim in claims:
            if claim.predicate != RelationType.CONTAINS or claim.status != ClaimStatus.ACTIVE or not isinstance(claim.object, str):
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
        claims = [
            item
            for item in self._graph.claims()
            if item.subject == claim_or_entity_id or item.object == claim_or_entity_id
        ]
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
            result["recommended_action"] = self.request_confirmation(target)
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
