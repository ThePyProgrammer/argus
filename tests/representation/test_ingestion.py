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
