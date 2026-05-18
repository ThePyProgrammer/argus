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
