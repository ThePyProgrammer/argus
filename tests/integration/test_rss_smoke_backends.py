"""DET-METRICS-05 SC#5: RSS growth ≤ 200 MB over 100 inferences, per backend.

Parametrized over YOLOv11 (always runs), RT-DETRv2 (honest-skip on missing
ONNX), BoxeR (opt-in via ``-m slow_boxer`` + honest-skip on missing venv).

OWLv2 is INTENTIONALLY absent. ROADMAP Phase 6 SC#5 lists "YOLOv11,
RT-DETRv2, OWLv2, BoxeR" but Phase 5 D-10 (2026-04-15) dropped OWLv2 from
the pluggable pipeline — see RESEARCH F4. The coverage target is the 3
currently-shipped backends.

Replaces the Wave 0 scaffold (CONTEXT D-15). Supersedes
``tests/smoke/test_detector_rss.py`` (YOLOv11-only) once this test is green
in CI; the legacy file remains until a follow-up cleanup plan removes it.

Pitfall 7 ordering (RESEARCH §Pitfall 7):
    1. create backend (may spawn subprocess, allocate caches)
    2. warmup(fixture_frame)               (one-shot first inference cost)
    3. gc.collect()                        (release warmup garbage)
    4. measure rss_before
    5. 100 inferences
    6. gc.collect()
    7. measure rss_after
    8. assert delta < 200 MB
"""
from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
import psutil
import pytest

from src.bridge.sensor_types import SensorFrame

# Trigger detector_backend side-effect registration (yolov11, rtdetrv2, boxer).
import src.perception.backends  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- Honest-skip probes (CONTEXT D-15) ---


def _rtdetrv2_artifact_present() -> bool:
    """True iff a downloaded RT-DETRv2 ONNX model exists under models/rtdetrv2/<sha>/."""
    return any((REPO_ROOT / "models" / "rtdetrv2").glob("*/model.onnx"))


def _boxer_ready() -> bool:
    """True iff the BoxeR subprocess venv has been provisioned by setup_boxer_subprocess.sh."""
    return (REPO_ROOT / "subprocess_venvs" / "boxer" / ".ready").exists()


# --- Fixture: synthetic RGBD frame matching production shape ---

# Reuse the canonical regression fixture if present (mirrors
# tests/smoke/test_detector_rss.py); fall back to a synthetic 480x640 frame
# so this smoke test still runs on a fresh clone without the .npz artifact.
_FIXTURE_NPZ = (
    REPO_ROOT / "tests" / "fixtures" / "yolo_regression_scene_01.npz"
)


@pytest.fixture(scope="module")
def fixture_frame() -> SensorFrame:
    """Single SensorFrame reused across the parametrized backends.

    Module-scope: avoids re-allocating a 480×640 RGBD payload for every
    parametrize case; the inference-loop RSS measurement is the
    interesting allocation, not the fixture.
    """
    if _FIXTURE_NPZ.exists():
        data = np.load(_FIXTURE_NPZ)
        return SensorFrame(
            rgb=data["rgb"],
            depth=data["depth"],
            ground_truth_pose=data["pose"],
            sim_time=float(data["sim_time"]),
        )
    rng = np.random.default_rng(0xA12)
    return SensorFrame(
        rgb=rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8),
        depth=(rng.random((480, 640), dtype=np.float32) * 5.0),
        ground_truth_pose=np.eye(4, dtype=np.float64),
        sim_time=0.0,
    )


# --- The parametrized smoke test ---

RSS_GROWTH_CAP_BYTES = 200 * 1024 * 1024  # 200 MB
INFERENCE_COUNT = 100


@pytest.mark.parametrize(
    "backend_id",
    [
        "yolov11",
        pytest.param(
            "rtdetrv2",
            marks=pytest.mark.skipif(
                not _rtdetrv2_artifact_present(),
                reason=(
                    "RT-DETRv2 ONNX model missing; "
                    "run `make download-models-rtdetrv2`"
                ),
            ),
        ),
        pytest.param(
            "boxer",
            marks=[
                pytest.mark.slow_boxer,
                pytest.mark.skipif(
                    not _boxer_ready(),
                    reason=(
                        "BoxeR subprocess venv missing; "
                        "run `bash scripts/setup_boxer_subprocess.sh`"
                    ),
                ),
            ],
        ),
    ],
)
def test_rss_growth_capped(backend_id: str, fixture_frame: SensorFrame) -> None:
    """RSS growth after 100 inferences must stay under 200 MB.

    Pitfall 7: subprocess startup + warmup allocation MUST NOT count
    toward inference-loop RSS growth. See module docstring for the
    measurement order.

    Regression signal: a missing ``model.eval()`` or absent
    ``torch.inference_mode()`` wrap (DET-API-07) typically blows past
    the 200 MB cap within ~50 inferences as activation tensors are
    retained for autograd.
    """
    from src.perception.registry import DetectorRegistry

    backend = DetectorRegistry.create(backend_id)
    try:
        backend.warmup(fixture_frame)
        gc.collect()

        process = psutil.Process()
        rss_before = process.memory_info().rss

        for _ in range(INFERENCE_COUNT):
            backend.process_frame(fixture_frame)

        gc.collect()
        rss_after = process.memory_info().rss
        delta = rss_after - rss_before

        assert delta < RSS_GROWTH_CAP_BYTES, (
            f"{backend_id} RSS grew by {delta // (1024 * 1024)} MB over "
            f"{INFERENCE_COUNT} inferences "
            f"(cap = {RSS_GROWTH_CAP_BYTES // (1024 * 1024)} MB). "
            "Likely regression: forgotten `model.eval()` or missing "
            "`torch.inference_mode()` wrap (DET-API-07)."
        )
    finally:
        # Be polite to subprocess-isolated backends (BoxeR spawns a worker).
        close = getattr(backend, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001 — cleanup must not mask assertion
                pass
