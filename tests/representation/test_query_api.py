from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import ClaimStatus, Entity, EntityType, RelationType, Source
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


def test_summarize_region_ignores_stale_contains_for_presence_counts():
    graph = build_graph()
    api = WorldQueryAPI(graph)
    graph.set_claim_status("claim_002", ClaimStatus.STALE)

    result = api.summarize_region("region_8")

    assert result == {
        "region": "region_8",
        "objects": 1,
        "hazards": 0,
        "active_claims": 1,
        "conflicted_claims": 0,
        "stale_claims": 1,
    }


def test_retrieve_evidence_returns_claim_evidence():
    api = WorldQueryAPI(build_graph())

    result = api.retrieve_evidence("claim_001")

    assert result == {
        "claim_id": "claim_001",
        "evidence": {"type": "image", "uri": "image://drone_2/frame_5401"},
    }
