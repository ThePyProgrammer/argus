from __future__ import annotations

from datetime import datetime

from src.representation.models import Claim, ClaimStatus, Commitment, Entity, RelationType


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
        self._sync_live_conflicts()

    def refresh_stale(self, now: datetime) -> list[str]:
        stale_ids: list[str] = []
        for claim in self._claims.values():
            if claim.status in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED} and claim.is_stale_at(now):
                claim.status = ClaimStatus.STALE
                stale_ids.append(claim.id)

        self._sync_live_conflicts()

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
            if new_claim.predicate == RelationType.CONTAINS:
                continue

            old_claim.status = ClaimStatus.CONFLICTED
            new_claim.status = ClaimStatus.CONFLICTED

        self._sync_live_conflicts()

    def _sync_live_conflicts(self) -> None:
        live_claims = [
            claim
            for claim in self._claims.values()
            if claim.status in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED}
        ]

        live_conflicts: dict[str, list[str]] = {claim.id: [] for claim in live_claims}
        for idx, claim in enumerate(live_claims):
            for other in live_claims[idx + 1 :]:
                if (
                    other.subject == claim.subject
                    and other.predicate == claim.predicate
                    and claim.predicate != RelationType.CONTAINS
                    and other.object != claim.object
                ):
                    live_conflicts[claim.id].append(other.id)
                    live_conflicts[other.id].append(claim.id)

        for claim in self._claims.values():
            conflicts = live_conflicts.get(claim.id, [])
            claim.conflicts_with = conflicts
            if claim.status in {ClaimStatus.ACTIVE, ClaimStatus.CONFLICTED}:
                claim.status = ClaimStatus.CONFLICTED if conflicts else ClaimStatus.ACTIVE
            else:
                claim.conflicts_with = []
