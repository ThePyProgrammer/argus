"""DET-MODELS-03 + DET-MODELS-08 — BoxeR composer tests (Wave 0 skeleton, Plan 05-04).

Plan 05-08 (Wave 2) fills in composer logic and msgpack->OrientedBox3D translation.
The `test_warmup_returns_3d` integration test is marked `slow_boxer` — it requires
a live subprocess_venvs/boxer/ venv so is skipped unless explicitly selected.
"""
from __future__ import annotations

import pytest


def test_construct_no_spawn() -> None:
    """D-05 lazy spawn — __init__ must NOT touch filesystem or subprocess."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: BoxeRBackend() does not call Popen, does not open bridge socket.")


def test_extent_halving() -> None:
    """D-02 gotcha — msgpack sends FULL extents (w,h,d); composer halves for OrientedBox3D."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: composer divides reply['boxes_3d'][i]['w'] by 2 to produce half_extents[0].")


def test_quaternion_passthrough_no_handcraft() -> None:
    """Phase 1 D-10 invariant — composer passes qx,qy,qz,qw straight into OrientedBox3D(...); no inline construction."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: verify no scipy.spatial.transform import in boxer_backend.py (grep test).")


def test_capability_license() -> None:
    """DET-MODELS-08 — CAPABILITIES['license'] must equal 'CC-BY-NC-4.0' for Phase 3 D-05 badge render."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: BoxeRBackend.CAPABILITIES['license'] == 'CC-BY-NC-4.0'.")


def test_capability_outputs_3d_natively() -> None:
    """Phase 3 D-08 — BoxeR bypasses lifter; CAPABILITIES['outputs_3d_natively'] must be True."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: BoxeRBackend.CAPABILITIES['outputs_3d_natively'] is True.")


def test_available_when_ready_marker_missing() -> None:
    """D-01 — subprocess_venvs/boxer/.ready gates availability."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: BoxeRBackend.available() returns (False, install_hint) when .ready absent.")


@pytest.mark.slow_boxer
def test_warmup_returns_3d() -> None:
    """Integration: real bridge spawn + real BoxeR inference returns Detections3D."""
    pytest.skip("Plan 05-08 (Wave 2) fills in: requires subprocess_venvs/boxer/.ready (run make download-models-boxer).")
