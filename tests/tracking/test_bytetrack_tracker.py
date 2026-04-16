"""ByteTrack tracker -- stable track_id across frames (DET-STRETCH-01 SC#1).

Tests cover: 100-frame stability, track_thresh gating, track deletion after
frame_gap, geometry immutability (T-08-01 threat mitigation), capture_pose
preservation, reset() behavior, PARAMETER_SCHEMA/CAPABILITIES shape, and
registry integration.
"""
from __future__ import annotations

import importlib

import numpy as np
import pytest

from src.perception.types import Detections3D, OrientedBox3D
from src.tracking.registry import TrackerRegistry


@pytest.fixture(autouse=True)
def _repopulate_registry():
    """Re-register built-in trackers after any _clear in prior tests."""
    TrackerRegistry._clear()
    import src.tracking.trackers  # noqa: F401
    import src.tracking.trackers.none as _none
    importlib.reload(_none)
    # Also reload bytetrack to re-register after _clear.
    import src.tracking.trackers.bytetrack as _bt
    importlib.reload(_bt)
    yield


def _make_box(
    center: tuple[float, float, float] = (1.0, 0.5, 0.8),
    class_name: str = "chair",
    class_id: int = 0,
    score: float = 0.9,
) -> OrientedBox3D:
    return OrientedBox3D(
        center=np.array(center, dtype=np.float64),
        half_extents=np.array([0.3, 0.3, 0.5], dtype=np.float64),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
        class_id=class_id,
        class_name=class_name,
        score=score,
        track_id=None,
    )


def _make_envelope(items: list[OrientedBox3D]) -> Detections3D:
    return Detections3D(
        items=items,
        lifter_ms=1.0,
        detector_ms=10.0,
        n_raw=len(items),
        n_final=len(items),
        image_hw=(480, 640),
        capture_pose=np.eye(4, dtype=np.float64) * 2.0,  # non-identity to detect mutation
        capture_timestamp=42.0,
    )


def test_stationary_chair_keeps_single_track_id_100_frames():
    """SC#1: stationary chair keeps one track_id across >=100 frames."""
    tracker = TrackerRegistry.create("bytetrack")
    box = _make_box()
    tid_set: set[int] = set()
    for _ in range(100):
        envelope = _make_envelope([box])
        result = tracker.track(envelope)
        assert len(result.items) == 1
        tid = result.items[0].track_id
        assert tid is not None
        tid_set.add(tid)
    # Must be exactly one unique track_id across all 100 frames.
    assert len(tid_set) == 1


def test_track_creation_respects_track_thresh():
    """New track only created when confidence >= track_thresh (default 0.3)."""
    tracker = TrackerRegistry.create("bytetrack")
    low_score_box = _make_box(score=0.2)
    envelope = _make_envelope([low_score_box])
    result = tracker.track(envelope)
    # Score 0.2 < track_thresh 0.3 => no track created => track_id is None
    assert result.items[0].track_id is None


def test_track_deletion_after_frame_gap():
    """Track deleted after frames_since_seen > frame_gap (default 30)."""
    tracker = TrackerRegistry.create("bytetrack", frame_gap=5)
    box = _make_box()
    # Create a track.
    envelope = _make_envelope([box])
    result = tracker.track(envelope)
    original_tid = result.items[0].track_id
    assert original_tid is not None

    # Send 6 empty frames (> frame_gap=5).
    empty = _make_envelope([])
    for _ in range(6):
        tracker.track(empty)

    # Re-observe -- should get a NEW track_id because old one was pruned.
    result2 = tracker.track(envelope)
    new_tid = result2.items[0].track_id
    assert new_tid is not None
    assert new_tid != original_tid


def test_geometry_fields_not_mutated():
    """Tracker MUST NOT mutate center, half_extents, quaternion, class_name, score (T-08-01)."""
    tracker = TrackerRegistry.create("bytetrack")
    box = _make_box()
    envelope = _make_envelope([box])
    result = tracker.track(envelope)
    out_box = result.items[0]
    # Geometry must be identical to input.
    np.testing.assert_array_equal(out_box.center, box.center)
    np.testing.assert_array_equal(out_box.half_extents, box.half_extents)
    np.testing.assert_array_equal(out_box.quaternion, box.quaternion)
    assert out_box.class_id == box.class_id
    assert out_box.class_name == box.class_name
    assert out_box.score == box.score


def test_capture_pose_timestamp_preserved():
    """capture_pose + capture_timestamp MUST NOT be mutated by tracker."""
    tracker = TrackerRegistry.create("bytetrack")
    envelope = _make_envelope([_make_box()])
    result = tracker.track(envelope)
    np.testing.assert_array_equal(result.capture_pose, envelope.capture_pose)
    assert result.capture_timestamp == envelope.capture_timestamp
    assert result.detector_ms == envelope.detector_ms
    assert result.lifter_ms == envelope.lifter_ms
    assert result.n_raw == envelope.n_raw
    assert result.n_final == envelope.n_final
    assert result.image_hw == envelope.image_hw


def test_reset_clears_all_tracks():
    """reset() clears internal state; next frame creates fresh track_ids starting from 0."""
    tracker = TrackerRegistry.create("bytetrack")
    box = _make_box()
    envelope = _make_envelope([box])
    # Create tracks.
    result = tracker.track(envelope)
    first_tid = result.items[0].track_id
    assert first_tid == 0

    # Reset.
    tracker.reset()

    # Next frame should start from track_id 0 again.
    result2 = tracker.track(envelope)
    assert result2.items[0].track_id == 0


def test_parameter_schema_keys():
    """PARAMETER_SCHEMA has track_thresh, match_thresh, frame_gap keys."""
    tracker = TrackerRegistry.create("bytetrack")
    schema = tracker.PARAMETER_SCHEMA
    assert "track_thresh" in schema
    assert "match_thresh" in schema
    assert "frame_gap" in schema
    # Check types and defaults.
    assert schema["track_thresh"]["default"] == 0.3
    assert schema["match_thresh"]["default"] == 0.5
    assert schema["frame_gap"]["default"] == 30


def test_capabilities():
    """CAPABILITIES has produces_stable_ids: True, license: Apache-2.0."""
    tracker = TrackerRegistry.create("bytetrack")
    caps = tracker.CAPABILITIES
    assert caps["produces_stable_ids"] is True
    assert caps["license"] == "Apache-2.0"
    assert caps["framework"] == "bytetrack_3d"


def test_bytetrack_in_registry_list_backends():
    """ByteTrack appears in TrackerRegistry.list_backends()."""
    backends = TrackerRegistry.list_backends()
    names = [b["name"] for b in backends]
    assert "bytetrack" in names
    bt = next(b for b in backends if b["name"] == "bytetrack")
    assert bt["available"] is True
    assert bt["capabilities"]["produces_stable_ids"] is True
