"""Heterogeneous per-robot backends (DET-STRETCH-04 SC#4).

Tests for ``swap_backend_for_robot``, ``_per_robot_backends`` dict tracking,
``swap_backend`` (all-robots) updating the dict, and scoped crash fallback.

Uses torch-free fake backends registered via ``DetectorRegistry.register``
following the established pattern from ``test_swap_backend.py`` and
``test_crash_fallback.py``.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.registry import Detection3DRegistry, DetectorRegistry
from src.perception.types import Detections2D, Detections3D, DetectorInput


# ---------------------------------------------------------------------------
# Torch-free fake backends (mirror test_swap_backend.py / test_crash_fallback.py)
# ---------------------------------------------------------------------------


class _MockDetector:
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


class _MockDetectorAlt:
    """Second fake backend (stands in for 'rtdetrv2' or similar alternative)."""

    CAPABILITIES = {
        "framework": "fake_alt",
        "license": "Apache-2.0",
        "cpu_latency_hint_ms": 20,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.warmup_count = 0
        self.init_kwargs = dict(kwargs)

    def process_frame(self, f: SensorFrame) -> Detections2D:
        return Detections2D(items=[], inference_ms=2.0, image_hw=(480, 640))

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


class _MockLifter:
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
    """Clear registries, register mock backends, teardown restores."""
    # Drop any cached backend modules so re-registration works cleanly
    for mod_name in list(sys.modules):
        if mod_name.startswith("src.perception.backends"):
            del sys.modules[mod_name]

    DetectorRegistry._clear()
    Detection3DRegistry._clear()

    DetectorRegistry.register(
        name="fake_yolo",
        display="Fake YOLO",
        class_path=f"{__name__}._MockDetector",
        klass=_MockDetector,
    )
    DetectorRegistry.register(
        name="fake_rtdetr",
        display="Fake RT-DETR",
        class_path=f"{__name__}._MockDetectorAlt",
        klass=_MockDetectorAlt,
    )
    Detection3DRegistry.register(
        name="fake_lifter",
        display="Fake Lifter",
        class_path=f"{__name__}._MockLifter",
        klass=_MockLifter,
    )
    yield
    # Don't clear on teardown -- other tests may need real backends populated
    # by import-side-effect and Python's import cache prevents re-triggering.


def _make_pool(robot_ids: list[str]):
    """Construct a DetectorWorkerPool wired to fake_yolo + fake_lifter."""
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
    # Warmup synchronously; do NOT call start().
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
# Tests: swap_backend_for_robot
# ---------------------------------------------------------------------------


def test_swap_backend_for_robot_updates_single_worker():
    """swap_backend_for_robot(rid) changes only that robot's detector."""
    pool = _make_pool(["robot_0", "robot_1"])
    original_r0 = pool._workers["robot_0"]._detector
    original_r1 = pool._workers["robot_1"]._detector

    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")

    # robot_0 detector changed (new instance of _MockDetectorAlt)
    assert pool._workers["robot_0"]._detector is not original_r0
    assert isinstance(pool._workers["robot_0"]._detector, _MockDetectorAlt)
    # robot_1 detector unchanged (same instance)
    assert pool._workers["robot_1"]._detector is original_r1


def test_per_robot_backends_dict_tracks_state():
    """_per_robot_backends[rid] updated after swap_backend_for_robot."""
    pool = _make_pool(["robot_0", "robot_1"])

    # Initial state: both should be fake_yolo
    backends = pool.per_robot_backends
    assert backends["robot_0"] == "fake_yolo"
    assert backends["robot_1"] == "fake_yolo"

    # Swap robot_0 to fake_rtdetr
    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")

    backends = pool.per_robot_backends
    assert backends["robot_0"] == "fake_rtdetr"
    assert backends["robot_1"] == "fake_yolo"  # unchanged


def test_swap_backend_all_robots_still_works():
    """swap_backend() (all robots) still works and updates all _per_robot_backends entries."""
    pool = _make_pool(["robot_0", "robot_1", "robot_2"])

    # Make heterogeneous first
    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")
    backends = pool.per_robot_backends
    assert backends["robot_0"] == "fake_rtdetr"
    assert backends["robot_1"] == "fake_yolo"

    # swap_backend (all) resets everyone to fake_yolo
    pool.swap_backend("fake_yolo")

    backends = pool.per_robot_backends
    assert all(v == "fake_yolo" for v in backends.values())
    assert pool.backend_name == "fake_yolo"


def test_crash_fallback_scoped_to_crashed_robot():
    """Crash in robot_1's backend only falls back robot_1, not robot_0."""
    pool = _make_pool(["robot_0", "robot_1"])

    # Make heterogeneous: robot_0 -> fake_rtdetr, robot_1 stays fake_yolo
    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")
    original_r0_det = pool._workers["robot_0"]._detector

    # Simulate a crash for robot_1 only (scoped fallback)
    pool.on_backend_crash(
        crashed_backend="fake_yolo",
        reason="simulated crash",
        fallback="fake_yolo",
        robot_id="robot_1",
    )

    # robot_0's detector must be UNCHANGED (same instance)
    assert pool._workers["robot_0"]._detector is original_r0_det
    assert pool.per_robot_backends["robot_0"] == "fake_rtdetr"

    # robot_1 got a fresh fallback (new instance)
    assert isinstance(pool._workers["robot_1"]._detector, _MockDetector)
    assert pool.per_robot_backends["robot_1"] == "fake_yolo"


def test_per_robot_backends_updated_inside_swap_lock_during_crash():
    """_per_robot_backends updated inside _swap_lock during scoped crash fallback."""
    pool = _make_pool(["robot_0", "robot_1"])

    # Make heterogeneous
    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")

    # Scoped crash: robot_0 falls back to fake_yolo
    pool.on_backend_crash(
        crashed_backend="fake_rtdetr",
        reason="simulated",
        fallback="fake_yolo",
        robot_id="robot_0",
    )

    # _per_robot_backends should reflect the fallback
    assert pool.per_robot_backends["robot_0"] == "fake_yolo"
    assert pool.per_robot_backends["robot_1"] == "fake_yolo"


def test_swap_backend_for_robot_unknown_rid_raises():
    """swap_backend_for_robot raises ValueError for unknown robot_id."""
    pool = _make_pool(["robot_0", "robot_1"])

    with pytest.raises(ValueError, match="Unknown robot_id"):
        pool.swap_backend_for_robot("robot_999", "fake_yolo")


def test_swap_backend_for_robot_emits_ws_message():
    """swap_backend_for_robot emits detector_swap_complete with robot_id."""
    pool = _make_pool(["robot_0"])
    viz = MagicMock()
    viz._message_queue = []
    pool.set_streaming_viz(viz)

    pool.swap_backend_for_robot("robot_0", "fake_rtdetr")

    swap_msgs = [
        m for m in viz._message_queue
        if isinstance(m, dict) and m.get("type") == "detector_swap_complete"
    ]
    assert len(swap_msgs) == 1
    assert swap_msgs[0]["payload"]["backend"] == "fake_rtdetr"
    assert swap_msgs[0]["payload"]["robot_id"] == "robot_0"
    assert swap_msgs[0]["payload"]["reason"] == "per_robot_swap"
