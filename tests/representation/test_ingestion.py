from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import ClaimStatus, Entity, EntityType, RelationType, Source


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


def test_ingest_copies_metadata_and_propagates_frame_and_expiry():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    valid_until = observed_at + timedelta(minutes=5)
    metadata = {"sensor": "stereo", "confidence_source": "fusion"}
    fact = ObservationFact(
        subject="region_8",
        subject_type=EntityType.REGION,
        predicate=RelationType.CONTAINS,
        object="object_42",
        object_type=EntityType.OBJECT,
        object_label="red_vehicle",
        confidence=0.81,
        evidence_type="image",
        evidence_uri="image://drone_2/frame_5401",
        frame_id="odom",
        valid_until=valid_until,
        metadata=metadata,
    )

    claims = ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=observed_at,
            facts=[fact],
        )
    )
    metadata["sensor"] = "changed"

    claim = claims[0]
    assert claim.frame_id == "odom"
    assert claim.valid_until == valid_until
    assert claim.metadata == {"sensor": "stereo", "confidence_source": "fusion"}


def test_ingest_assigns_sequential_claim_ids_for_multiple_facts():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    claims = ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=observed_at,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_42",
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5401",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_43",
                    object_type=EntityType.OBJECT,
                    confidence=0.79,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5402",
                ),
            ],
        )
    )

    assert [claim.id for claim in claims] == ["claim_001", "claim_002"]


def test_ingest_updates_existing_entity_label_when_non_none_label_arrives():
    graph = BeliefGraph()
    graph.add_entity(Entity(id="region_8", type=EntityType.REGION, label="old label"))
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=observed_at,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    subject_label="new label",
                    predicate=RelationType.CONTAINS,
                    object="object_42",
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5401",
                )
            ],
        )
    )

    assert graph.get_entity("region_8").label == "new label"


def test_ingest_preserves_scalar_object_values_without_creating_object_entities():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    claims = ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=observed_at,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object=3,
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5401",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object=2.5,
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5402",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object=True,
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5403",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object=None,
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5404",
                ),
            ],
        )
    )

    assert [claim.object for claim in claims] == [3, 2.5, True, None]
    assert graph.get_entity("3") is None
    assert graph.get_entity("2.5") is None
    assert graph.get_entity("True") is None
    assert graph.get_entity("None") is None


def test_ingest_creates_object_entities_only_when_object_type_is_provided():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="drone_2"),
            observed_at=observed_at,
            facts=[
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_42",
                    object_type=EntityType.OBJECT,
                    confidence=0.81,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5401",
                ),
                ObservationFact(
                    subject="region_8",
                    subject_type=EntityType.REGION,
                    predicate=RelationType.CONTAINS,
                    object="object_43",
                    confidence=0.79,
                    evidence_type="image",
                    evidence_uri="image://drone_2/frame_5402",
                ),
            ],
        )
    )

    assert graph.get_entity("object_42") is not None
    assert graph.get_entity("object_43") is None


def test_observation_batch_converts_facts_to_tuple():
    batch = ObservationBatch(
        source=Source(type="robot", id="drone_2"),
        observed_at=datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc),
        facts=[
            ObservationFact(
                subject="region_8",
                subject_type=EntityType.REGION,
                predicate=RelationType.CONTAINS,
                object="object_42",
                object_type=EntityType.OBJECT,
                confidence=0.81,
                evidence_type="image",
                evidence_uri="image://drone_2/frame_5401",
            )
        ],
    )

    assert isinstance(batch.facts, tuple)
    assert len(batch.facts) == 1


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
