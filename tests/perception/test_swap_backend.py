"""Plan 07-05 — DET-PIPELINE-05 SC#4 DetectorWorkerPool.swap_backend lockdown.

Asserts ``DetectorWorkerPool.swap_backend`` (D-11):
  - Mirrors ``swap_lifter`` atomicity (construct per-worker OUTSIDE lock).
  - Emits ``detector_swap_complete`` via ``streaming_viz._message_queue``.
  - Per-worker-instance separation (each worker gets its own backend instance).
  - Warmup-failure rollback (any worker's warmup raising leaves pool unchanged).
  - Unknown backend name raises BEFORE any worker mutation.

Implementation note (Deviation Rule 3 — blocking issue): this test env lacks
``ultralytics`` / ``torch`` / ``onnxruntime``, so all three production detector
backends (yolov11 / rtdetrv2 / boxer) are unavailable for actual construction.
We use the same torch-free ``FakeDetector`` + ``FakeLifter`` registry pattern
established in ``tests/perception/test_worker_pool.py`` (fixtures wired via
``DetectorRegistry.register`` with an explicit ``class_path``). This still
exercises the complete ``swap_backend`` code path: ``DetectorRegistry.create``
per worker, ``.warmup(dummy)``, atomic ref rebind, WS envelope emit. The real
``yolov11 → rtdetrv2`` cross-backend path is covered by the integration test
in Plan 07-11.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.registry import Detection3DRegistry, DetectorRegistry
from src.perception.types import Detections2D, Detections3D, DetectorInput


# ---------------------------------------------------------------------------
# Torch-free fake backends (mirror tests/perception/test_worker_pool.py)
# ---------------------------------------------------------------------------


class FakeDetector:
    """Fake DetectorProtocol backend: fast, introspectable, torch-free."""

    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 10,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.threshold = 0.5
        self.warmup_count = 0
        self.init_kwargs = dict(kwargs)

    def process_frame(self, f: SensorFrame) -> Detections2D:
        return Detections2D(items=[], inference_ms=1.0, image_hw=(480, 640))

    def reset(self) -> None:
        return None

    def warmup(self, f: SensorFrame) -> None:
        self.warmup_count += 1

    def get_metrics(self) -> dict:
        return {}

    def apply_params(self, p: dict) -> dict:
        return {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


class FakeLifter:
    """Fake Detection3DProtocol backend: returns empty Detections3D envelope."""

    CAPABILITIES = {
        "requires_depth": False,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.init_kwargs = dict(kwargs)

    def lift(
        self,
        d2d: Detections2D,
        f: SensorFrame,
        pose: np.ndarray,
        intr: CameraIntrinsics,
        cloud: np.ndarray | None,
    ) -> Detections3D:
        return Detections3D(
            items=[],
            lifter_ms=0.0,
            detector_ms=d2d.inference_ms,
            n_raw=0,
            n_final=0,
            image_hw=d2d.image_hw,
            capture_pose=np.eye(4),
            capture_timestamp=0.0,
        )

    def reset(self) -> None:
        return None

    def get_metrics(self) -> dict:
        return {}

    def apply_params(self, p: dict) -> dict:
        return {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_and_register_fakes():
    """Clear registries, register FakeDetector + FakeLifter, teardown clears."""
    DetectorRegistry._clear()
    Detection3DRegistry._clear()

    DetectorRegistry.register(
        name="fake_yolo",
        display="Fake YOLO",
        class_path=f"{__name__}.FakeDetector",
        klass=FakeDetector,
    )
    Detection3DRegistry.register(
        name="fake_lifter",
        display="Fake Lifter",
        class_path=f"{__name__}.FakeLifter",
        klass=FakeLifter,
    )
    yield
    # Do NOT clear registries on teardown — trailing tests (e.g. the
    # pipeline-apply-hot integration suite and the perception_rgbd preset
    # contract) rely on real backends being registered, and Python's import
    # cache prevents their side-effect imports from re-triggering the
    # @detector_backend / @detection_3d decorators after a clear. The
    # registry state is overwritten on setup of the next test that uses
    # this fixture, so session-global accumulation is not a concern.


def _make_pool(robot_ids: list[str]):
    """Construct a DetectorWorkerPool wired to the fake_yolo + fake_lifter entries."""
    from src.perception.worker_pool import DetectorWorkerPool

    intrinsics = {
        rid: CameraIntrinsics.from_fov(640, 480, 70.0) for rid in robot_ids
    }
    pool = DetectorWorkerPool(
        robot_ids=list(robot_ids),
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot=intrinsics,
        lifter_params={},
    )
    # Warm up synchronously so _detector is exercised once; do NOT call start().
    dummy_frames = {
        rid: SensorFrame(
            rgb=np.zeros((480, 640, 3), dtype=np.uint8),
            depth=np.zeros((480, 640), dtype=np.float32),
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )
        for rid in robot_ids
    }
    pool.warmup_all(dummy_frames)
    return pool


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_swap_backend_atomic_rebind() -> None:
    pool = _make_pool(["robot0", "robot1"])
    original_detectors = {rid: w._detector for rid, w in pool._workers.items()}
    assert pool.backend_name == "fake_yolo"

    # Swap fake_yolo -> fake_yolo (same registered backend, NEW instances).
    # Exercises the full code path: construct per worker, warmup, rebind,
    # WS emit. The yolov11 -> rtdetrv2 cross-backend path lands in 07-11.
    pool.swap_backend("fake_yolo")

    assert pool.backend_name == "fake_yolo"
    for rid, w in pool._workers.items():
        # Post-swap ref must not equal pre-swap ref (new instance per rid).
        assert w._detector is not original_detectors[rid]


def test_swap_backend_per_worker_instance_separation() -> None:
    pool = _make_pool(["robot0", "robot1", "robot2"])
    pool.swap_backend("fake_yolo")
    dets = [w._detector for w in pool._workers.values()]
    # All three workers must hold distinct instances (Phase 2 D-05 invariant).
    assert dets[0] is not dets[1]
    assert dets[1] is not dets[2]
    assert dets[0] is not dets[2]


def test_swap_backend_emits_detector_swap_complete_ws() -> None:
    pool = _make_pool(["robot0"])
    viz = MagicMock()
    viz._message_queue = []
    pool.set_streaming_viz(viz)

    pool.swap_backend("fake_yolo")

    # Exactly one detector_swap_complete envelope was queued.
    swap_msgs = [
        m
        for m in viz._message_queue
        if isinstance(m, dict) and m.get("type") == "detector_swap_complete"
    ]
    assert len(swap_msgs) == 1
    assert swap_msgs[0]["payload"]["backend"] == "fake_yolo"
    assert swap_msgs[0]["payload"]["reason"] == "hot_swap"


def test_swap_backend_warmup_failure_rollback() -> None:
    pool = _make_pool(["robot0", "robot1", "robot2"])
    original_detectors = {rid: w._detector for rid, w in pool._workers.items()}
    original_name = pool.backend_name

    call_counter = {"n": 0}
    real_create = DetectorRegistry.create

    def failing_create(name, **kwargs):
        call_counter["n"] += 1
        inst = real_create(name, **kwargs)
        if call_counter["n"] == 3:  # third worker's warmup raises
            inst.warmup = MagicMock(side_effect=RuntimeError("simulated warmup failure"))
        return inst

    with patch.object(DetectorRegistry, "create", side_effect=failing_create):
        with pytest.raises(RuntimeError, match="simulated warmup failure"):
            pool.swap_backend("fake_yolo")

    # No worker was mutated (Pitfall 8 — atomic success only).
    for rid, w in pool._workers.items():
        assert w._detector is original_detectors[rid]
    assert pool.backend_name == original_name


def test_swap_backend_unknown_name_raises_before_mutation() -> None:
    pool = _make_pool(["robot0", "robot1"])
    original_detectors = {rid: w._detector for rid, w in pool._workers.items()}
    original_name = pool.backend_name

    with pytest.raises(ValueError):
        pool.swap_backend("bogusname")

    for rid, w in pool._workers.items():
        assert w._detector is original_detectors[rid]
    assert pool.backend_name == original_name
