"""Plan 07-03 target — DET-PIPELINE-05 (TrackerRegistry skeleton + NoneTracker).

Asserts TrackerRegistry.list_backends() returns {"name": "none", ...}
with available=True; TrackerRegistry.create("none") returns an instance
that stamps monotonic track_ids on a Detections3D envelope without mutating
geometry fields (center/half_extents/quaternion preserved).
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-05 TrackerRegistry (implemented in Plan 07-03)",
    allow_module_level=True,
)


def test_tracker_registry_lists_none() -> None:
    # TODO Plan 07-03: import src.tracking.trackers; assert
    # TrackerRegistry.list_backends() has entry name="none", available=True.
    assert False, "implemented in Plan 07-03"


def test_none_tracker_stamps_monotonic_ids() -> None:
    # TODO Plan 07-03: construct 3-box Detections3D, call track(), assert
    # returned boxes have track_id in (0, 1, 2) order, geometry unchanged.
    assert False, "implemented in Plan 07-03"


def test_none_tracker_preserves_capture_pose_and_timestamp() -> None:
    # TODO Plan 07-03: Phase 2 D-11 invariant — envelope's capture_pose +
    # capture_timestamp pass through unchanged.
    assert False, "implemented in Plan 07-03"


def test_tracker_registry_create_unknown_raises() -> None:
    # TODO Plan 07-03: TrackerRegistry.create("bogus") raises ValueError.
    assert False, "implemented in Plan 07-03"


def test_tracker_registry_reload_after_clear() -> None:
    # TODO Plan 07-03: Pitfall 7 — after _clear(), re-importing
    # src.tracking.trackers.none repopulates the registry.
    assert False, "implemented in Plan 07-03"
