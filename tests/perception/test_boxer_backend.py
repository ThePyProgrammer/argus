"""DET-MODELS-03 + DET-MODELS-08 — BoxeR composer tests (Plan 05-08 activation).

All unit-level tests are active. The integration test `test_warmup_returns_3d`
stays `@pytest.mark.slow_boxer` because it requires a real subprocess_venvs/boxer/
— skipped unless `pytest -m slow_boxer` is explicitly invoked.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def test_construct_no_spawn() -> None:
    """D-05 — __init__ must NOT touch subprocess or filesystem."""
    import src.perception.backends  # noqa: F401
    with patch("subprocess.Popen") as mock_popen, \
         patch("src.perception.subprocess_bridge.SubprocessDetectorBridge.start") as mock_start:
        from src.perception.backends.boxer_backend import BoxeRBackend
        backend = BoxeRBackend()
        # Construction does NOT spawn or start the bridge.
        assert mock_popen.call_count == 0
        assert mock_start.call_count == 0
        assert backend._bridge is None


def test_extent_halving() -> None:
    """D-02 gotcha — composer divides reply['boxes_3d'] w/h/d by 2 for half_extents."""
    import src.perception.backends  # noqa: F401
    from src.perception.backends.boxer_backend import BoxeRBackend
    from src.bridge.sensor_types import SensorFrame

    backend = BoxeRBackend(score_threshold=0.0)
    fake_bridge = MagicMock()
    fake_bridge.send_frame.return_value = {
        "ts": 0.0,
        "inference_ms": 42.0,
        "n_det": 1,
        "classes": [56],       # chair
        "scores": [0.9],
        "bboxes": [[10.0, 20.0, 100.0, 200.0]],
        "boxes_3d": [{
            "tx": 1.0, "ty": 2.0, "tz": 3.0,
            "qx": 0.0, "qy": 0.0, "qz": 0.0, "qw": 1.0,
            "w": 2.0, "h": 4.0, "d": 6.0,   # FULL extents per D-02
        }],
    }
    backend._bridge = fake_bridge  # bypass lazy spawn for unit test

    dummy = SensorFrame(
        rgb=np.zeros((480, 640, 3), dtype=np.uint8),
        depth=np.zeros((480, 640), dtype=np.float32),
        ground_truth_pose=np.eye(4),
        sim_time=0.0,
    )
    dets = backend.process_frame(dummy)
    assert len(dets.items) == 1
    box = dets.items[0]
    # HALF extents — D-02 gotcha: composer divided FULL by 2.
    assert box.half_extents[0] == pytest.approx(1.0)   # w=2.0 / 2
    assert box.half_extents[1] == pytest.approx(2.0)   # h=4.0 / 2
    assert box.half_extents[2] == pytest.approx(3.0)   # d=6.0 / 2
    # Center passes through as-is.
    assert box.center[0] == pytest.approx(1.0)
    # Quaternion passes through as-is (Phase 1 D-10: no recomputation).
    assert tuple(box.quaternion) == (0.0, 0.0, 0.0, 1.0)
    assert box.class_id == 56
    assert box.class_name == "chair"


def test_quaternion_passthrough_no_handcraft() -> None:
    """Phase 1 D-10 — no inline quaternion construction in composer source.

    Grep-style assertion: boxer_backend.py must NOT import scipy transform
    utilities (Phase 1 invariant — only OrientedBox3D dataclass constructs q's).
    """
    from pathlib import Path
    src = Path("src/perception/backends/boxer_backend.py").read_text()
    assert "from scipy.spatial.transform" not in src, \
        "Phase 1 D-10 violation: scipy.spatial.transform import in composer"
    assert "Rotation.from_matrix" not in src
    assert "OrientedBox3D(" in src
    # Quaternion comes from wire dict keys qx/qy/qz/qw.
    assert 'float(b3["qx"])' in src
    assert 'float(b3["qw"])' in src


def test_capability_license() -> None:
    """DET-MODELS-08 — BoxeRBackend.CAPABILITIES['license'] == 'CC-BY-NC-4.0'."""
    import src.perception.backends  # noqa: F401
    from src.perception.backends.boxer_backend import BoxeRBackend
    assert BoxeRBackend.CAPABILITIES["license"] == "CC-BY-NC-4.0"


def test_capability_outputs_3d_natively() -> None:
    """Phase 3 D-08 — outputs_3d_natively=True hides LifterDropdown in frontend."""
    from src.perception.backends.boxer_backend import BoxeRBackend
    assert BoxeRBackend.CAPABILITIES["outputs_3d_natively"] is True
    assert BoxeRBackend.CAPABILITIES["framework"] == "subprocess"


def test_available_when_ready_marker_missing(monkeypatch, tmp_path) -> None:
    """D-01 — subprocess_venvs/boxer/.ready gates availability."""
    from src.perception.backends import boxer_backend
    monkeypatch.setattr(boxer_backend, "_READY_MARKER", tmp_path / "missing" / ".ready")
    available, reason = boxer_backend.BoxeRBackend.available()
    assert available is False
    assert reason is not None
    assert "make download-models-boxer" in reason or "setup_boxer_subprocess.sh" in reason


def test_available_when_ready_marker_present(monkeypatch, tmp_path) -> None:
    """Inverse of above — .ready marker → available=True."""
    from src.perception.backends import boxer_backend
    ready_path = tmp_path / ".ready"
    ready_path.write_text("")
    monkeypatch.setattr(boxer_backend, "_READY_MARKER", ready_path)
    available, reason = boxer_backend.BoxeRBackend.available()
    assert available is True
    assert reason is None


@pytest.mark.slow_boxer
def test_warmup_returns_3d() -> None:
    """Integration test — requires real subprocess_venvs/boxer/ + pinned checkpoints."""
    pytest.skip(
        "Requires live subprocess_venvs/boxer/.ready (run `make download-models-boxer` first). "
        "Remove this skip and exercise `BoxeRBackend().warmup(dummy_frame)` end-to-end."
    )
