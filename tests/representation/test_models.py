from datetime import datetime, timedelta, timezone

import pytest

from src.representation.models import (
    Claim,
    Commitment,
    ClaimStatus,
    Entity,
    EntityType,
    Evidence,
    RelationType,
    Source,
)


def test_entity_and_relation_type_values_match_design_spec():
    assert EntityType.ROBOT.value == "robot"
    assert EntityType.FRONTIER.value == "frontier"
    assert EntityType.TERRAIN_PATCH.value == "terrain_patch"
    assert EntityType.COMMITMENT.value == "commitment"

    assert RelationType.CONTAINS.value == "contains"
    assert RelationType.BLOCKS.value == "blocks"
    assert RelationType.REQUIRES_CAPABILITY.value == "requires_capability"
    assert RelationType.CONFLICTS_WITH.value == "conflicts_with"


def test_claim_serializes_required_metadata():
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    claim = Claim(
        id="claim_123",
        subject="path_segment_4",
        predicate=RelationType.BLOCKS,
        object="hazard_12",
        confidence=0.74,
        source=Source(type="robot", id="rover_3"),
        observed_at=observed_at,
        frame_id="map",
        evidence=Evidence(type="point_cloud_slice", uri="local_submap://rover_3/session_22/slice_91"),
    )

    assert claim.to_dict() == {
        "id": "claim_123",
        "subject": "path_segment_4",
        "predicate": "blocks",
        "object": "hazard_12",
        "confidence": 0.74,
        "source": {"type": "robot", "id": "rover_3"},
        "observed_at": "2026-05-18T10:41:00+00:00",
        "frame_id": "map",
        "evidence": {
            "type": "point_cloud_slice",
            "uri": "local_submap://rover_3/session_22/slice_91",
        },
        "status": "active",
        "valid_until": None,
        "conflicts_with": [],
        "metadata": {},
    }


@pytest.mark.parametrize("object_value", [42, 0.5, True, None])
def test_claim_serializes_scalar_object_values(object_value):
    observed_at = datetime(2026, 5, 18, 10, 41, tzinfo=timezone.utc)
    claim = Claim(
        id="claim_123",
        subject="path_segment_4",
        predicate=RelationType.BLOCKS,
        object=object_value,
        confidence=0.74,
        source=Source(type="robot", id="rover_3"),
        observed_at=observed_at,
        frame_id="map",
        evidence=Evidence(type="point_cloud_slice", uri="local_submap://rover_3/session_22/slice_91"),
    )

    assert claim.to_dict()["object"] == object_value


def test_claim_rejects_confidence_outside_unit_interval():
    observed_at = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
        Claim(
            id="claim_bad",
            subject="path_segment_4",
            predicate=RelationType.BLOCKS,
            object="hazard_12",
            confidence=1.2,
            source=Source(type="robot", id="rover_3"),
            observed_at=observed_at,
            frame_id="map",
            evidence=Evidence(type="point_cloud_slice", uri="local_submap://slice"),
        )


def test_entity_keeps_label_and_attributes():
    entity = Entity(
        id="rover_3",
        type=EntityType.ROBOT,
        label="Rover 3",
        attributes={"robot_type": "wheeled", "battery": 0.8},
    )

    assert entity.to_dict() == {
        "id": "rover_3",
        "type": "robot",
        "label": "Rover 3",
        "attributes": {"robot_type": "wheeled", "battery": 0.8},
    }


def test_claim_status_values_are_explicit():
    assert [status.value for status in ClaimStatus] == [
        "active",
        "superseded",
        "conflicted",
        "stale",
        "rejected",
    ]


def test_commitment_serializes_iso_timestamps_and_overlap_boundaries():
    start = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    commitment = Commitment(
        id="commitment_1",
        resource_id="charger_1",
        robot_id="rover_3",
        start=start,
        end=start + timedelta(minutes=30),
        task_id="task_42",
    )

    assert commitment.to_dict() == {
        "id": "commitment_1",
        "resource_id": "charger_1",
        "robot_id": "rover_3",
        "start": "2026-05-18T10:00:00+00:00",
        "end": "2026-05-18T10:30:00+00:00",
        "task_id": "task_42",
        "status": "active",
    }

    adjacent = Commitment(
        id="commitment_2",
        resource_id="charger_1",
        robot_id="rover_4",
        start=start + timedelta(minutes=30),
        end=start + timedelta(minutes=45),
    )
    overlapping = Commitment(
        id="commitment_3",
        resource_id="charger_1",
        robot_id="rover_5",
        start=start + timedelta(minutes=20),
        end=start + timedelta(minutes=40),
    )
    different_resource = Commitment(
        id="commitment_4",
        resource_id="charger_2",
        robot_id="rover_6",
        start=start + timedelta(minutes=20),
        end=start + timedelta(minutes=40),
    )

    assert not commitment.overlaps(adjacent)
    assert commitment.overlaps(overlapping)
    assert not commitment.overlaps(different_resource)
