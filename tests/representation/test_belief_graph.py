from datetime import datetime, timedelta, timezone

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


def test_next_ids_increment_deterministically():
    graph = BeliefGraph()

    assert graph.next_claim_id() == "claim_001"
    assert graph.next_claim_id() == "claim_002"
    assert graph.next_commitment_id() == "commitment_001"
    assert graph.next_commitment_id() == "commitment_002"


def test_entities_and_claims_accessors_filter_by_type_and_predicate():
    graph = BeliefGraph()
    entity_a = Entity(id="path_segment_4", type=EntityType.PATH_SEGMENT)
    entity_b = Entity(id="hazard_12", type=EntityType.HAZARD)
    claim_blocks = make_claim("claim_1")
    claim_clear = make_claim("claim_2", object="clear", predicate=RelationType.BLOCKS)

    graph.add_entity(entity_a)
    graph.add_entity(entity_b)
    graph.add_claim(claim_blocks)
    graph.add_claim(claim_clear)

    assert graph.entities() == [entity_a, entity_b]
    assert graph.entities_by_type(EntityType.PATH_SEGMENT.value) == [entity_a]
    assert graph.entities_by_type(EntityType.HAZARD.value) == [entity_b]
    assert graph.claims() == [claim_blocks, claim_clear]
    assert graph.claims_by_predicate(RelationType.BLOCKS.value) == [claim_blocks, claim_clear]


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


def test_superseded_claim_is_removed_from_live_conflicts():
    graph = BeliefGraph()
    claim_a = make_claim("claim_a", object="hazard_12")
    claim_b = make_claim("claim_b", object="clear")
    claim_c = make_claim("claim_c", object="hazard_12")

    graph.add_claim(claim_a)
    graph.add_claim(claim_b)
    graph.add_claim(claim_c)

    assert graph.get_claim("claim_a").status == ClaimStatus.SUPERSEDED
    assert graph.get_claim("claim_a").conflicts_with == []
    assert graph.get_claim("claim_b").status == ClaimStatus.CONFLICTED
    assert graph.get_claim("claim_c").status == ClaimStatus.CONFLICTED
    assert graph.get_claim("claim_b").conflicts_with == ["claim_c"]
    assert graph.get_claim("claim_c").conflicts_with == ["claim_b"]


def test_set_claim_status_cleans_up_conflicts_and_reactivates_remaining_live_claim():
    graph = BeliefGraph()
    claim_a = make_claim("claim_a", object="hazard_12")
    claim_b = make_claim("claim_b", object="clear")

    graph.add_claim(claim_a)
    graph.add_claim(claim_b)

    graph.set_claim_status("claim_a", ClaimStatus.REJECTED)

    assert graph.get_claim("claim_a").status == ClaimStatus.REJECTED
    assert graph.get_claim("claim_a").conflicts_with == []
    assert graph.get_claim("claim_b").status == ClaimStatus.ACTIVE
    assert graph.get_claim("claim_b").conflicts_with == []
    assert graph.active_claims() == [graph.get_claim("claim_b")]


def test_refresh_stale_marks_expired_active_claims_stale():
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)
    expired = make_claim("claim_expired", valid_until=now - timedelta(minutes=1))
    fresh = make_claim("claim_fresh", valid_until=now + timedelta(minutes=1))
    graph = BeliefGraph()

    graph.add_claim(expired, resolve=False)
    graph.add_claim(fresh, resolve=False)
    stale_ids = graph.refresh_stale(now)

    assert stale_ids == ["claim_expired"]
    assert graph.get_claim("claim_expired").status == ClaimStatus.STALE
    assert graph.get_claim("claim_fresh").status == ClaimStatus.ACTIVE


def test_refresh_stale_skips_expired_superseded_claims():
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)
    superseded = make_claim("claim_superseded", valid_until=now - timedelta(minutes=1))
    superseded.status = ClaimStatus.SUPERSEDED
    graph = BeliefGraph()

    graph.add_claim(superseded, resolve=False)

    stale_ids = graph.refresh_stale(now)

    assert stale_ids == []
    assert graph.get_claim("claim_superseded").status == ClaimStatus.SUPERSEDED


def test_refresh_stale_reactivates_nonexpired_claims_after_conflict_expires():
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)
    expired_conflict = make_claim("claim_expired", object="hazard_12", valid_until=now - timedelta(minutes=1))
    live_claim = make_claim("claim_live", object="clear")
    graph = BeliefGraph()

    graph.add_claim(expired_conflict)
    graph.add_claim(live_claim)

    stale_ids = graph.refresh_stale(now)

    assert stale_ids == ["claim_expired"]
    assert graph.get_claim("claim_expired").status == ClaimStatus.STALE
    assert graph.get_claim("claim_live").status == ClaimStatus.ACTIVE
    assert graph.get_claim("claim_live").conflicts_with == []
    assert graph.active_claims() == [graph.get_claim("claim_live")]


def test_add_and_get_commitment_and_commitments():
    graph = BeliefGraph()
    commitment = Commitment(
        id="commitment_1",
        resource_id="charger_1",
        robot_id="rover_3",
        start=datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 5, 18, 10, 30, tzinfo=timezone.utc),
        task_id="task_42",
    )

    graph.add_commitment(commitment)

    assert graph.get_commitment("commitment_1") == commitment
    assert graph.commitments() == [commitment]


def test_active_claims_excludes_superseded_stale_rejected_and_conflicted():
    graph = BeliefGraph()
    active = make_claim("claim_active", subject="path_segment_5")
    stale = make_claim("claim_stale")
    rejected = make_claim("claim_rejected")
    conflict_base = make_claim("claim_conflict_base")
    conflicted = make_claim("claim_conflicted", object="clear")
    stale.status = ClaimStatus.STALE
    rejected.status = ClaimStatus.REJECTED

    graph.add_claim(active)
    graph.add_claim(stale, resolve=False)
    graph.add_claim(rejected, resolve=False)
    graph.add_claim(conflict_base)
    graph.add_claim(conflicted)

    assert graph.get_claim("claim_conflicted").status == ClaimStatus.CONFLICTED
    assert graph.active_claims() == [active]
