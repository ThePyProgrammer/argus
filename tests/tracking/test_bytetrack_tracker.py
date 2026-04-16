"""ByteTrack tracker -- stable track_id across frames (DET-STRETCH-01 SC#1)."""
import pytest


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_stationary_chair_keeps_single_track_id_100_frames():
    """SC#1: stationary chair keeps one track_id across >=100 frames."""


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_track_creation_respects_track_thresh():
    """New track only created when confidence >= track_thresh (default 0.3)."""


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_track_deletion_after_frame_gap():
    """Track deleted after frames_since_seen > frame_gap (default 30)."""


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_geometry_fields_not_mutated():
    """Tracker MUST NOT mutate center, half_extents, quaternion, class_name, score."""


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_capture_pose_timestamp_preserved():
    """capture_pose + capture_timestamp MUST NOT be mutated by tracker."""


@pytest.mark.skip(reason="Phase 8 Plan 02 -- ByteTrack implementation")
def test_reset_clears_all_tracks():
    """reset() clears internal state; next frame creates fresh tracks."""
