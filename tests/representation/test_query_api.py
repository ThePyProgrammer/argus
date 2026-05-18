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


def test_belief_queries_report_confidence_staleness_and_confirmation_request():
    graph = build_graph()
    api = WorldQueryAPI(graph)
    now = datetime(2026, 5, 18, 10, 50, tzinfo=timezone.utc)

    assert api.get_confidence("claim_002") == {"claim": "claim_002", "confidence": 0.74, "status": "active"}
    assert api.get_confidence("object_42") == {"entity": "object_42", "confidence": 0.81, "status": "active"}
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


def test_allocate_task_selects_robot_with_required_capability_and_best_battery():
    graph = BeliefGraph()
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
    api = WorldQueryAPI(graph)

    result = api.allocate_task("task_rough_frontier")

    assert result["selected_robot"] == "legged_2"
    assert result["reason"] == "highest feasibility under capability and battery constraints"
    assert result["commitments_created"] == ["commitment_001"]
    commitment = graph.get_commitment("commitment_001")
    assert commitment.robot_id == "legged_2"
    assert commitment.start.tzinfo is not None
    assert commitment.end.tzinfo is not None
    assert commitment.start.tzinfo.utcoffset(commitment.start) == timedelta(0)
    assert commitment.end.tzinfo.utcoffset(commitment.end) == timedelta(0)


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


def test_overlapping_commitments_for_different_resources_are_not_conflicts():
    graph = BeliefGraph()
    api = WorldQueryAPI(graph)
    start = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 18, 10, 10, tzinfo=timezone.utc)

    first = api.reserve_resource("corridor_4", "rover_2", (start, end))
    second = api.reserve_resource("corridor_5", "rover_3", (start + timedelta(minutes=5), end + timedelta(minutes=5)))

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert api.detect_conflicts(second["commitment"]) == {"conflicts": []}
    assert {item["resource_id"] for item in api.list_commitments()["commitments"]} == {"corridor_4", "corridor_5"}
