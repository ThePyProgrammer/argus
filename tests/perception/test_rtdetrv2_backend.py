"""DET-MODELS-02 — RT-DETRv2 ONNX backend tests (Plan 05-07 activation).

Tests are real now; skeleton skips replaced with monkeypatched ort.InferenceSession
so we exercise the backend logic without requiring the 300+ MB ONNX artifact.

The one test that DOES require the real artifact, test_latency_p95_under_250ms,
stays skipped with a clear rerun hint.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame


# ---------- Helpers ----------

def _fake_session(logits_shape=(1, 300, 80), boxes_shape=(1, 300, 4)):
    """Return a MagicMock that pretends to be ort.InferenceSession.

    run() returns (fake_logits, fake_pred_boxes). Logits include a single
    high-confidence detection at class_id=56 (chair) for post-process testing.
    """
    sess = MagicMock()
    logits = np.full(logits_shape, -10.0, dtype=np.float32)
    logits[0, 0, 56] = 5.0  # chair @ query 0
    boxes = np.zeros(boxes_shape, dtype=np.float32)
    boxes[0, 0] = [0.5, 0.5, 0.2, 0.2]  # centered, 20% of canvas
    sess.run.return_value = [logits, boxes]
    return sess


def _install_fake_session(monkeypatch) -> MagicMock:
    """Monkeypatch onnxruntime.InferenceSession to return a fake session.

    Also monkeypatches the ONNX artifact existence check so __init__ proceeds.
    """
    import onnxruntime as ort
    from src.perception.backends import rtdetrv2_backend

    sess = _fake_session()
    monkeypatch.setattr(ort, "InferenceSession", lambda *a, **kw: sess)
    # Pretend the ONNX file exists so __init__'s FileNotFoundError path is skipped.
    real_exists = Path.exists
    fake_path = rtdetrv2_backend.RT_DETRV2_MODEL_DIR / "model.onnx"
    monkeypatch.setattr(
        Path, "exists",
        lambda self: True if self == fake_path else real_exists(self),
    )
    return sess


# ---------- Tests ----------

def test_construct_no_onnx_file_raises(monkeypatch, tmp_path) -> None:
    """D-06 — construction raises with install hint when ONNX artifact missing."""
    from src.perception.backends import rtdetrv2_backend
    # Redirect the expected path to a non-existent location.
    monkeypatch.setattr(
        rtdetrv2_backend, "RT_DETRV2_MODEL_DIR", tmp_path / "nonexistent"
    )
    with pytest.raises(FileNotFoundError, match="make download-models-rtdetrv2"):
        rtdetrv2_backend.RTDETRv2Backend()


def test_construct_with_onnx_file_succeeds(monkeypatch) -> None:
    """Constructor returns a working backend when the artifact exists."""
    sess = _install_fake_session(monkeypatch)
    from src.perception.backends.rtdetrv2_backend import RTDETRv2Backend
    backend = RTDETRv2Backend(score_threshold=0.3)
    assert backend._session is sess
    assert backend._score_threshold == 0.3


def test_preprocess_letterbox_480x640_to_320x320() -> None:
    """D-08 — letterbox 480×640 → 320×320 preserves aspect ratio, pads black."""
    from src.perception.backends.rtdetrv2_backend import _letterbox_320
    rgb = np.full((480, 640, 3), 128, dtype=np.uint8)
    x, scale, pad = _letterbox_320(rgb)
    assert x.shape == (1, 3, 320, 320)
    assert x.dtype == np.float32
    assert abs(scale - 0.5) < 1e-6
    assert pad == (40, 0)
    # Top 40 rows are black pad (all zeros), rows 280-320 are bottom black pad.
    assert np.all(x[0, :, :40, :] == 0.0)
    assert np.all(x[0, :, 280:, :] == 0.0)


def test_warmup_runs_one_inference(monkeypatch) -> None:
    sess = _install_fake_session(monkeypatch)
    from src.perception.backends.rtdetrv2_backend import RTDETRv2Backend
    backend = RTDETRv2Backend()
    dummy = SensorFrame(
        rgb=np.zeros((480, 640, 3), dtype=np.uint8),
        depth=np.zeros((480, 640), dtype=np.float32),
        ground_truth_pose=np.eye(4),
        sim_time=0.0,
    )
    backend.warmup(dummy)
    assert sess.run.call_count == 1
    assert backend._first_inference_ms is not None
    assert backend._first_inference_ms >= 0.0


def test_capabilities_include_framework_and_license() -> None:
    from src.perception.backends.rtdetrv2_backend import RTDETRv2Backend
    from src.perception.types import DetectorInput
    caps = RTDETRv2Backend.CAPABILITIES
    assert caps["framework"] == "onnxruntime"
    assert caps["license"] == "Apache-2.0"
    assert caps["outputs_3d_natively"] is False
    assert caps["input_type"] == DetectorInput.RGB_ONLY
    assert isinstance(caps["cpu_latency_hint_ms"], int)


def test_thread_budget_inherits_from_thread_config(monkeypatch) -> None:
    """D-07 — intra_op_num_threads reads get_default_budget(), not hardcoded."""
    from src.perception.backends import rtdetrv2_backend
    import src._thread_config as tc

    captured = {}

    class FakeSessOpts:
        intra_op_num_threads = None
        inter_op_num_threads = None
        graph_optimization_level = None

    import onnxruntime as ort
    monkeypatch.setattr(ort, "SessionOptions", FakeSessOpts)
    sess = _install_fake_session(monkeypatch)

    def capture_session(path, sess_options=None, providers=None):
        captured["intra_op"] = sess_options.intra_op_num_threads
        captured["providers"] = providers
        return sess

    monkeypatch.setattr(ort, "InferenceSession", capture_session)
    monkeypatch.setattr(tc, "_DEFAULT_BUDGET", 7)

    rtdetrv2_backend.RTDETRv2Backend()
    assert captured["intra_op"] == 7
    assert captured["providers"] == ["CPUExecutionProvider"]


def test_construct_registers_in_registry() -> None:
    """@detector_backend decorator side-effect registers 'rtdetrv2'."""
    import src.perception.backends  # noqa: F401 -- triggers registration
    from src.perception.registry import DetectorRegistry
    names = [e["name"] for e in DetectorRegistry.list_backends()]
    assert "rtdetrv2" in names


@pytest.mark.skip(reason="Requires real models/rtdetrv2/<SHA>/model.onnx; run after `make download-models-rtdetrv2`.")
def test_latency_p95_under_250ms() -> None:
    """SC#1 proxy — 30 inferences on 480×640 fixture, P95 < 250 ms."""
    import time
    from src.perception.backends.rtdetrv2_backend import RTDETRv2Backend
    backend = RTDETRv2Backend()
    rgb = np.random.randint(0, 255, size=(480, 640, 3), dtype=np.uint8)
    frame = SensorFrame(
        rgb=rgb, depth=None, ground_truth_pose=np.eye(4), sim_time=0.0
    )
    backend.warmup(frame)
    times = []
    for _ in range(30):
        t0 = time.perf_counter()
        backend.process_frame(frame)
        times.append((time.perf_counter() - t0) * 1000.0)
    p95 = float(np.percentile(times, 95))
    assert p95 < 250.0, f"RT-DETRv2 P95 {p95:.1f} ms exceeds SC#1 budget 250 ms"
