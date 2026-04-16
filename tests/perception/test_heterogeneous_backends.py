"""Heterogeneous per-robot backends (DET-STRETCH-04 SC#4)."""
import pytest


@pytest.mark.skip(reason="Phase 8 Plan 03 -- heterogeneous backends")
def test_swap_backend_for_robot_updates_single_worker():
    """SC#4: swap_backend_for_robot(rid) changes only that robot's detector."""


@pytest.mark.skip(reason="Phase 8 Plan 03 -- heterogeneous backends")
def test_per_robot_backends_dict_tracks_state():
    """_per_robot_backends[rid] updated after swap_backend_for_robot."""


@pytest.mark.skip(reason="Phase 8 Plan 03 -- heterogeneous backends")
def test_swap_backend_all_robots_still_works():
    """swap_backend() (all robots) still works and updates all entries."""


@pytest.mark.skip(reason="Phase 8 Plan 03 -- heterogeneous backends")
def test_crash_fallback_scoped_to_crashed_robot():
    """Crash in robot_1's backend only falls back robot_1, not robot_0."""
