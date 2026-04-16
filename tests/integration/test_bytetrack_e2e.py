"""ByteTrack in full coordinator loop (DET-STRETCH-01 integration)."""
import pytest


@pytest.mark.skip(reason="Phase 8 Plan 04 -- ByteTrack integration wiring")
def test_bytetrack_stable_track_ids_in_ws_stream():
    """Run ByteTrack in coordinator loop for 30 frames, assert stable track_ids in output."""
