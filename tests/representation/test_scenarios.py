from datetime import datetime, timedelta, timezone

from src.representation.graph import BeliefGraph
from src.representation.ingestion import ObservationBatch, ObservationFact, ObservationIngestor
from src.representation.models import Entity, EntityType, RelationType, Source
from src.representation.query_api import WorldQueryAPI


def test_minimum_demo_two_robot_conflict_and_four_query_families():
    graph = BeliefGraph()
    ingestor = ObservationIngestor(graph)
    now = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)

    graph.add_entity(Entity(
        id="drone_2",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "confirm"], "battery": 0.6},
    ))
    graph.add_entity(Entity(
        id="legged_1",
        type=EntityType.ROBOT,
        attributes={"capabilities": ["navigate", "rough_terrain"], "battery": 0.8},
    ))
    graph.add_entity(Entity(
        id="task_inspect_path",
        type=EntityType.TASK,
        attributes={"required_capabilities": ["navigate", "rough_terrain"]},
    ))

    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_3"),
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
                    evidence_uri="image://rover_3/frame_1",
                ),
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
                    valid_until=now + timedelta(minutes=5),
                    metadata={"alternatives": [{"send_robot": "legged_1"}]},
                ),
            ],
        )
    )
    ingestor.ingest(
        ObservationBatch(
            source=Source(type="robot", id="rover_5"),
            observed_at=now + timedelta(seconds=5),
            facts=[
                ObservationFact(
                    subject="path_segment_4",
                    subject_type=EntityType.PATH_SEGMENT,
                    predicate=RelationType.BLOCKS,
                    object="clear",
                    confidence=0.66,
                    evidence_type="image",
                    evidence_uri="image://rover_5/frame_8",
                ),
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
                ),
            ],
        )
    )

    api = WorldQueryAPI(graph)

    vehicle = api.find_objects("vehicle")["objects"][0]
    assert vehicle["id"] == "object_42"
    assert vehicle["source"] == {"type": "robot", "id": "rover_3"}
    assert vehicle["evidence"] == {"type": "image", "uri": "image://rover_3/frame_1"}
    assert api.get_frontiers(region="region_8", robot_type="drone")["frontiers"][0]["id"] == "frontier_9"
    assert api.compare_claims(["claim_002", "claim_003"])["conflicts"] == ["claim_002", "claim_003"]
    assert api.allocate_task("task_inspect_path")["selected_robot"] == "legged_1"


def test_stale_blockage_degrades_route_recommendation_to_confirmation():
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
                    confidence=0.74,
                    evidence_type="point_cloud_slice",
                    evidence_uri="local_submap://rover_3/slice_91",
                    valid_until=now + timedelta(minutes=1),
                )
            ],
        )
    )
    api = WorldQueryAPI(graph)

    stale = api.check_staleness("claim_001", now=now + timedelta(minutes=2))
    route = api.plan_route("rover_2", goal="path_segment_4")

    assert stale["status"] == "stale"
    assert stale["recommended_action"] == {
        "request_confirmation": {
            "target": "path_segment_4",
            "preferred_robot_type": None,
        }
    }
    assert route == {"robot": "rover_2", "goal": "path_segment_4", "feasible": True, "route": ["path_segment_4"]}
    assert api.request_confirmation("path_segment_4", preferred_robot_type="drone") == {
        "request_confirmation": {
            "target": "path_segment_4",
            "preferred_robot_type": "drone",
        }
    }
