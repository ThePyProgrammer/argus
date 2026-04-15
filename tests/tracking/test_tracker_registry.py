"""Plan 07-03 — DET-PIPELINE-05 TrackerRegistry + NoneTracker lockdown.

Asserts TrackerRegistry.list_backends() returns {"name": "none", ...}
with available=True; TrackerRegistry.create("none") returns an instance
that stamps monotonic track_ids on a Detections3D envelope without mutating
geometry fields (center/half_extents/quaternion preserved).
"""
from __future__ import annotations

import importlib

import numpy as np
import pytest

from src.perception.types import Detections3D, OrientedBox3D
from src.tracking.registry import TrackerRegistry


@pytest.fixture(autouse=True)
def _repopulate_registry():
    """Re-register built-in trackers after any _clear in prior tests (Pitfall 7)."""
    TrackerRegistry._clear()
    import src.tracking.trackers  # noqa: F401 -- side-effect registration
    # Force re-import of none.py so @tracker decorator re-runs after _clear.
    import src.tracking.trackers.none as _none
    importlib.reload(_none)
    yield
    TrackerRegistry._clear()


def _make_envelope(n_boxes: int = 3) -> Detections3D:
    """Build a test Detections3D with n_boxes distinct OBBs.

    Mirrors tests/perception/test_worker_capture_pose.py construction shape:
    numpy arrays for geometry, integer class_id, float score, None track_id.
    """
    items = [
        OrientedBox3D(
            center=np.array([float(i), 0.0, 0.0], dtype=np.float64),
            half_extents=np.array([0.5, 0.5, 0.5], dtype=np.float64),
            quaternion=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
            class_id=i,
            class_name=f"class_{i}",
            score=0.9,
            track_id=None,
        )
        for i in range(n_boxes)
    ]
    return Detections3D(
        items=items,
        lifter_ms=1.0,
        detector_ms=10.0,
        n_raw=n_boxes,
        n_final=n_boxes,
        image_hw=(480, 640),
        capture_pose=np.eye(4, dtype=np.float64),
        capture_timestamp=123.456,
    )


def test_tracker_registry_lists_none() -> None:
    backends = TrackerRegistry.list_backends()
    names = [b["name"] for b in backends]
    assert "none" in names
    none_entry = next(b for b in backends if b["name"] == "none")
    assert none_entry["available"] is True
    assert none_entry["display"] == "Passthrough (no tracking)"
    assert none_entry["capabilities"]["framework"] == "stub"
    assert none_entry["capabilities"]["produces_stable_ids"] is False
    assert none_entry["capabilities"]["license"] == "MIT"


def test_none_tracker_stamps_monotonic_ids() -> None:
    tracker_inst = TrackerRegistry.create("none")
    envelope = _make_envelope(n_boxes=3)
    result = tracker_inst.track(envelope)
    assert [b.track_id for b in result.items] == [0, 1, 2]
    # Geometry preserved byte-identical.
    for old, new in zip(envelope.items, result.items):
        np.testing.assert_array_equal(new.center, old.center)
        np.testing.assert_array_equal(new.half_extents, old.half_extents)
        np.testing.assert_array_equal(new.quaternion, old.quaternion)
        assert new.class_id == old.class_id
        assert new.class_name == old.class_name
        assert new.score == old.score


def test_none_tracker_preserves_capture_pose_and_timestamp() -> None:
    tracker_inst = TrackerRegistry.create("none")
    envelope = _make_envelope(n_boxes=2)
    result = tracker_inst.track(envelope)
    np.testing.assert_array_equal(result.capture_pose, envelope.capture_pose)
    assert result.capture_timestamp == envelope.capture_timestamp
    assert result.detector_ms == envelope.detector_ms
    assert result.lifter_ms == envelope.lifter_ms
    assert result.n_raw == envelope.n_raw
    assert result.n_final == envelope.n_final
    assert result.image_hw == envelope.image_hw


def test_tracker_registry_create_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown tracker"):
        TrackerRegistry.create("bogus")


def test_tracker_registry_reload_after_clear() -> None:
    TrackerRegistry._clear()
    assert TrackerRegistry.list_backends() == []
    import src.tracking.trackers.none as _none
    importlib.reload(_none)
    names = [b["name"] for b in TrackerRegistry.list_backends()]
    assert "none" in names
