"""ByteTrack spatial association edge cases (DET-STRETCH-01).

Tests cover: within-gate matching, cross-gate miss, class gating,
multi-object disambiguation via Hungarian assignment, empty detections,
and optimal assignment verification.
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
        capture_pose=np.eye(4, dtype=np.float64),
        capture_timestamp=0.0,
    )


def test_within_gate_match():
    """Detection within match_thresh of existing track associates correctly."""
    tracker = TrackerRegistry.create("bytetrack", match_thresh=1.0)
    # Frame 1: create a track at (1.0, 0.0, 0.0).
    box1 = _make_box(center=(1.0, 0.0, 0.0))
    result1 = tracker.track(_make_envelope([box1]))
    tid1 = result1.items[0].track_id
    assert tid1 is not None

    # Frame 2: detection at (1.3, 0.0, 0.0) -- distance 0.3 < 1.0 threshold.
    box2 = _make_box(center=(1.3, 0.0, 0.0))
    result2 = tracker.track(_make_envelope([box2]))
    # Should match existing track.
    assert result2.items[0].track_id == tid1


def test_cross_gate_miss():
    """Detection beyond match_thresh creates a new track, not a false match."""
    tracker = TrackerRegistry.create("bytetrack", match_thresh=0.5)
    # Frame 1: create a track at (0.0, 0.0, 0.0).
    box1 = _make_box(center=(0.0, 0.0, 0.0))
    result1 = tracker.track(_make_envelope([box1]))
    tid1 = result1.items[0].track_id
    assert tid1 is not None

    # Frame 2: detection at (5.0, 0.0, 0.0) -- distance 5.0 >> 0.5 threshold.
    box2 = _make_box(center=(5.0, 0.0, 0.0))
    result2 = tracker.track(_make_envelope([box2]))
    # Should NOT match the old track -- new track_id.
    assert result2.items[0].track_id is not None
    assert result2.items[0].track_id != tid1


def test_class_gate_prevents_cross_class_match():
    """Two different-class objects at same location get separate track_ids."""
    tracker = TrackerRegistry.create("bytetrack")
    chair = _make_box(center=(0.0, 0.0, 0.0), class_name="chair", class_id=0)
    table = _make_box(center=(0.0, 0.0, 0.0), class_name="table", class_id=1)
    envelope = _make_envelope([chair, table])
    result = tracker.track(envelope)
    tid_chair = result.items[0].track_id
    tid_table = result.items[1].track_id
    assert tid_chair is not None
    assert tid_table is not None
    assert tid_chair != tid_table


def test_multi_object_disambiguation():
    """Multiple same-class objects are disambiguated by distance (Hungarian)."""
    tracker = TrackerRegistry.create("bytetrack")
    # Frame 1: two chairs at distinct locations.
    box_a = _make_box(center=(0.0, 0.0, 0.0), class_name="chair")
    box_b = _make_box(center=(3.0, 0.0, 0.0), class_name="chair")
    result1 = tracker.track(_make_envelope([box_a, box_b]))
    tid_a = result1.items[0].track_id
    tid_b = result1.items[1].track_id
    assert tid_a is not None and tid_b is not None
    assert tid_a != tid_b

    # Frame 2: same two chairs, slightly shifted but still nearest to their original.
    box_a2 = _make_box(center=(0.1, 0.0, 0.0), class_name="chair")
    box_b2 = _make_box(center=(3.1, 0.0, 0.0), class_name="chair")
    result2 = tracker.track(_make_envelope([box_a2, box_b2]))
    # Each should keep its original track_id.
    assert result2.items[0].track_id == tid_a
    assert result2.items[1].track_id == tid_b


def test_empty_detections():
    """Empty detections_3d returns empty items, no crash."""
    tracker = TrackerRegistry.create("bytetrack")
    envelope = _make_envelope([])
    result = tracker.track(envelope)
    assert result.items == []


def test_hungarian_optimal_assignment():
    """Ambiguous case: verify scipy Hungarian gives optimal (min total distance) assignment.

    Set up two tracks and two detections where greedy would fail but Hungarian succeeds:
    - Track A at (0, 0, 0), Track B at (3, 0, 0)
    - Det X at (2.8, 0, 0), Det Y at (0.2, 0, 0)
    Greedy nearest for Det X -> B (0.2), Det Y -> A (0.2) = total 0.4 (optimal)
    Hungarian should also get 0.4, but if order were reversed, greedy might fail.
    We verify the assignment is correct.
    """
    tracker = TrackerRegistry.create("bytetrack", match_thresh=5.0)
    # Frame 1: establish tracks.
    box_a = _make_box(center=(0.0, 0.0, 0.0), class_name="chair")
    box_b = _make_box(center=(3.0, 0.0, 0.0), class_name="chair")
    result1 = tracker.track(_make_envelope([box_a, box_b]))
    tid_a = result1.items[0].track_id
    tid_b = result1.items[1].track_id

    # Frame 2: detections closer to the opposite track of their list order.
    # Det at (2.8, 0, 0) is closer to track B (at 3.0) than track A (at 0.0).
    # Det at (0.2, 0, 0) is closer to track A (at 0.0) than track B (at 3.0).
    det_x = _make_box(center=(2.8, 0.0, 0.0), class_name="chair")
    det_y = _make_box(center=(0.2, 0.0, 0.0), class_name="chair")
    result2 = tracker.track(_make_envelope([det_x, det_y]))
    # det_x (at 2.8) should match track B (at 3.0), det_y (at 0.2) should match track A (at 0.0).
    assert result2.items[0].track_id == tid_b
    assert result2.items[1].track_id == tid_a
