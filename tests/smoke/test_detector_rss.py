"""RSS memory smoke test for every registered detector backend (CONTEXT.md D-09, D-10).

Catches forgotten model.eval() + torch.inference_mode() — retained activation
tensors make RSS climb linearly with inference count. Pitfall P5: without
eval/inference_mode, a 2-FPS detector climbs to 6-8 GB RSS in 5 minutes.

Contract (CONTEXT.md D-10):
  warn  at delta_mb > 200 MB over 100 measured inferences post-warmup
  fail  at delta_mb > 400 MB over 100 measured inferences post-warmup

Legacy YOLOv11-only smoke coverage. The newer integration RSS test owns
multi-backend coverage and keeps resource-backed backends in explicit lanes.
"""

from __future__ import annotations

import gc
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "yolo_regression_scene_01.npz"
WARN_MB = 200.0
FAIL_MB = 400.0
N_WARMUP = 5
N_MEASURED = 100


def _psutil_available() -> bool:
    try:
        import psutil  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _psutil_available(),
    reason="psutil required for RSS smoke test",
)


def _iter_available_backends() -> list[str]:
    try:
        import src.perception.backends  # noqa: F401
        from src.perception.registry import DetectorRegistry
    except Exception:
        return []
    entries = {e["name"]: e for e in DetectorRegistry.list_backends()}
    return ["yolov11"] if entries.get("yolov11", {}).get("available") else []


@pytest.fixture(scope="module")
def fixture_frame():
    assert FIXTURE.exists(), f"Missing fixture: {FIXTURE}"
    data = np.load(FIXTURE)
    return SensorFrame(
        rgb=data["rgb"],
        depth=data["depth"],
        ground_truth_pose=data["pose"],
        sim_time=float(data["sim_time"]),
    )


@pytest.mark.slow
@pytest.mark.timeout(180)
@pytest.mark.parametrize("backend_name", _iter_available_backends())
def test_rss_growth_bounded(backend_name, fixture_frame):
    """D-09/D-10: warn@200MB, fail@400MB over N_WARMUP + N_MEASURED inferences."""
    import psutil
    from src.perception.registry import DetectorRegistry

    proc = psutil.Process()
    backend = DetectorRegistry.create(backend_name)

    for _ in range(N_WARMUP):
        backend.warmup(fixture_frame)

    gc.collect()
    baseline_mb = proc.memory_info().rss / (1024 * 1024)

    for _ in range(N_MEASURED):
        _ = backend.process_frame(fixture_frame)

    gc.collect()
    final_mb = proc.memory_info().rss / (1024 * 1024)
    delta_mb = final_mb - baseline_mb

    print(
        f"[rss] {backend_name} baseline={baseline_mb:.1f}MB "
        f"final={final_mb:.1f}MB delta={delta_mb:.1f}MB "
        f"(warn={WARN_MB}MB fail={FAIL_MB}MB)",
        file=sys.stderr,
    )

    if delta_mb > FAIL_MB:
        pytest.fail(
            f"{backend_name} RSS growth {delta_mb:.1f}MB exceeds fail threshold "
            f"{FAIL_MB}MB over {N_MEASURED} inferences. "
            f"Likely missing .eval() / torch.inference_mode() (Pitfall P5)."
        )
    if delta_mb > WARN_MB:
        warnings.warn(
            f"{backend_name} RSS growth {delta_mb:.1f}MB exceeds warn threshold "
            f"{WARN_MB}MB over {N_MEASURED} inferences — slow drift; "
            f"review eval()/inference_mode() coverage soon.",
            stacklevel=2,
        )
