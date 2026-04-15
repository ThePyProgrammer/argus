"""DET-MODELS-06 — Crash fallback unit tests (Wave 0 skeleton, Plan 05-04).

Plan 05-05 (Wave 1) lands bridge typed exceptions (BridgeHangError, SubprocessDiedError).
Plan 05-09 (Wave 2) lands DetectorWorkerPool.on_backend_crash handler.
"""
from __future__ import annotations

import os
import pathlib
import sys
import time

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.subprocess_bridge import (
    BridgeHangError,
    SubprocessDetectorBridge,
    SubprocessDiedError,
)
from src.perception.types import Detections2D, Detections3D, DetectorInput

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ECHO_SCRIPT = str(REPO_ROOT / "scripts" / "echo_detector_worker.py")


# Mirror test_subprocess_bridge.py: ensure the worker script is executable and
# prepend the venv bin to PATH so its `#!/usr/bin/env python3` shebang resolves
# to the interpreter that has zmq/msgpack available.
os.chmod(ECHO_SCRIPT, 0o755)
_VENV_BIN = pathlib.Path(sys.executable).parent
if _VENV_BIN.is_dir():
    os.environ["PATH"] = f"{_VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}"


# ---------------------------------------------------------------------------
# Fake detector/lifter backends for the Wave 2 pool tests — registered in the
# DetectorRegistry so the pool's fallback path (``DetectorRegistry.create(
# "yolov11_fake")``) can construct them without needing ultralytics/torch
# installed in the test env. Mirrors the pattern at
# tests/perception/test_worker_pool.py lines 68-183.
# ---------------------------------------------------------------------------


class _FakeYolo:
    """Stand-in for YOLOv11Backend — fast, torch-free, introspectable."""

    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 1,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.warmup_count = 0

    def process_frame(self, f: SensorFrame) -> Detections2D:
        return Detections2D(items=[], inference_ms=1.0, image_hw=(480, 640))

    def warmup(self, f: SensorFrame) -> None:
        self.warmup_count += 1

    def reset(self) -> None:
        return None

    def get_metrics(self) -> dict:
        return {}

    def apply_params(self, p: dict) -> dict:
        return {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


class _FakeLifter:
    """Stand-in lifter — returns an empty Detections3D envelope."""

    CAPABILITIES = {
        "requires_depth": False,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        pass

    def lift(self, d2d, f, pose, intr, cloud) -> Detections3D:
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


@pytest.fixture
def pool_registry():
    """Register a _FakeYolo at ``name="yolov11"`` + _FakeLifter at ``name="median_depth"``.

    Pool tests need these registry slots occupied so that:
      - ``DetectorWorkerPool(backend_name="yolov11", ...)`` constructs the fake
        detector (avoiding the real ultralytics import path).
      - ``on_backend_crash`` can call ``DetectorRegistry.create("yolov11")``
        for the fallback path and land on the same fake.

    We also register a fake "boxer" row so ``set_available("boxer", False)``
    has a registry entry to target (Plan 05-08's real BoxeR backend may or may
    not be importable in this env; the test needs a deterministic row).
    """
    from src.perception.registry import Detection3DRegistry, DetectorRegistry

    # Capture + restore prior state so we don't leak across tests.
    prev_det = dict(DetectorRegistry._backends)  # noqa: SLF001
    prev_3d = dict(Detection3DRegistry._backends)  # noqa: SLF001
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    DetectorRegistry.register(
        name="yolov11",
        display="Fake YOLOv11",
        class_path=f"{__name__}._FakeYolo",
        klass=_FakeYolo,
    )
    DetectorRegistry.register(
        name="boxer",
        display="Fake BoxeR",
        class_path=f"{__name__}._FakeYolo",  # class doesn't matter; only name needed
        klass=_FakeYolo,
    )
    Detection3DRegistry.register(
        name="median_depth",
        display="Fake Lifter",
        class_path=f"{__name__}._FakeLifter",
        klass=_FakeLifter,
    )
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    DetectorRegistry._backends.update(prev_det)  # noqa: SLF001
    Detection3DRegistry._backends.update(prev_3d)  # noqa: SLF001


def _dummy_frame() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((8, 8, 3), dtype=np.uint8)
    depth = np.zeros((8, 8), dtype=np.float32)
    return rgb, depth


def test_bridge_hang_raises() -> None:
    """SubprocessDetectorBridge.send_frame raises BridgeHangError on RCVTIMEO (Plan 05-05)."""
    # Spawn an echo worker that sleeps longer than the bridge's hang timeout.
    # The worker WILL reply eventually, but not before RCVTIMEO fires → zmq.Again
    # → BridgeHangError. Short hang_timeout_ms keeps the test fast.
    bridge = SubprocessDetectorBridge(
        binary_path=ECHO_SCRIPT,
        args=["--sleep-ms", "2000"],
        hang_timeout_ms=500,
    )
    try:
        bridge.start()
        time.sleep(0.3)  # let the worker import + connect
        rgb, depth = _dummy_frame()

        t0 = time.monotonic()
        with pytest.raises(BridgeHangError):
            bridge.send_frame(rgb, depth, timestamp=1.0)
        elapsed = time.monotonic() - t0
        # RCVTIMEO = 500 ms + modest slack; MUST fire within HANG_TIMEOUT_MS + 500 ms.
        assert elapsed < 1.5, (
            f"BridgeHangError fired after {elapsed:.3f}s "
            f"(expected < HANG_TIMEOUT_MS + 0.5s = 1.0s + buffer)"
        )
    finally:
        bridge.shutdown()


def test_subprocess_died_raises() -> None:
    """SubprocessDetectorBridge.send_frame raises SubprocessDiedError when Popen exited (Plan 05-05)."""
    bridge = SubprocessDetectorBridge(
        binary_path=ECHO_SCRIPT,
        hang_timeout_ms=500,
    )
    try:
        bridge.start()
        time.sleep(0.3)
        assert bridge._process is not None
        # Kill the worker out from under the bridge.
        bridge._process.kill()
        bridge._process.wait(timeout=2)
        time.sleep(0.1)  # let the OS settle

        rgb, depth = _dummy_frame()
        with pytest.raises(SubprocessDiedError):
            bridge.send_frame(rgb, depth, timestamp=2.0)
    finally:
        bridge.shutdown()


def test_pool_on_backend_crash_emits_ws_message(pool_registry) -> None:
    """D-03 — on_backend_crash appends crash_fallback to streaming_viz._message_queue.

    Envelope matches the SLAM precedent at ``src/exploration/exploration_loop.py:207``:
    ``{"type": "crash_fallback", "payload": {"subsystem": "detector",
    "crashed_backend": ..., "fallback_backend": ..., "reason": ...}}``.
    """
    from src.perception.worker_pool import DetectorWorkerPool

    # Minimal fake streaming_viz — just exposes a list at ``_message_queue`` so
    # the pool's envelope emit has a target (mirrors the real StreamingVisualizer
    # surface used in exploration_loop.py:207).
    class FakeStreamingViz:
        def __init__(self) -> None:
            self._message_queue: list[dict] = []

    fake_viz = FakeStreamingViz()
    intr = CameraIntrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0, width=640, height=480)
    pool = DetectorWorkerPool(
        robot_ids=["r1"],
        backend_name="yolov11",
        backend_params={},
        lifter_name="median_depth",
        intrinsics_per_robot={"r1": intr},
        streaming_viz=fake_viz,
    )
    pool.on_backend_crash(crashed_backend="boxer", reason="test reason")
    assert len(fake_viz._message_queue) == 1
    msg = fake_viz._message_queue[0]
    assert msg["type"] == "crash_fallback"
    assert msg["payload"]["subsystem"] == "detector"
    assert msg["payload"]["crashed_backend"] == "boxer"
    assert msg["payload"]["fallback_backend"] == "yolov11"
    assert msg["payload"]["reason"] == "test reason"


def test_pool_swaps_to_yolo(pool_registry) -> None:
    """D-03 — on_backend_crash atomically swaps every worker's ._detector to the fallback.

    Uses the fake YOLO stand-in (registered by ``pool_registry`` at ``name="yolov11"``)
    so the test runs without the ultralytics/torch dependency chain. The pool
    fallback path calls ``DetectorRegistry.create("yolov11")`` which lands on
    the same class — so post-crash every worker holds a :class:`_FakeYolo`
    instance.
    """
    from src.perception.worker_pool import DetectorWorkerPool

    intr = CameraIntrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0, width=640, height=480)
    pool = DetectorWorkerPool(
        robot_ids=["r1", "r2"],
        backend_name="yolov11",
        backend_params={},
        lifter_name="median_depth",
        intrinsics_per_robot={"r1": intr, "r2": intr},
    )
    # Replace each worker's detector with a pretend-boxer so the post-crash
    # swap is observable against an obviously-not-YOLO baseline.
    class _FakeBoxerDetector:
        def process_frame(self, f):
            raise RuntimeError("should not be called — fallback should have swapped me out")

    for w in pool._workers.values():
        w._detector = _FakeBoxerDetector()

    pool.on_backend_crash(crashed_backend="boxer", reason="simulated")

    assert pool.backend_name == "yolov11"
    for rid, w in pool._workers.items():
        assert isinstance(w._detector, _FakeYolo), (
            f"worker {rid} detector type = {type(w._detector).__name__}; "
            f"expected _FakeYolo (registered as 'yolov11' fallback)"
        )
        # Warmup was called during fallback construction (SC#3 prereq).
        assert w._detector.warmup_count >= 1, (
            f"worker {rid} fallback was not warmed — violates D-03 warmup-before-swap"
        )


def test_pool_marks_crashed_backend_unavailable(pool_registry) -> None:
    """D-04 — on_backend_crash calls DetectorRegistry.set_available(crashed_backend, False, reason=...).

    After the crash, ``DetectorRegistry.list_backends()`` must surface the
    crashed entry with ``available=False`` and ``reason`` echoing the argument
    passed to ``on_backend_crash``. This drives the Phase 3 frontend
    ``DetectorDropdown`` greying-out behavior per D-04.
    """
    from src.perception.registry import DetectorRegistry
    from src.perception.worker_pool import DetectorWorkerPool

    intr = CameraIntrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0, width=640, height=480)
    pool = DetectorWorkerPool(
        robot_ids=["r1"],
        backend_name="yolov11",
        backend_params={},
        lifter_name="median_depth",
        intrinsics_per_robot={"r1": intr},
    )
    pool.on_backend_crash(crashed_backend="boxer", reason="test reason")
    entries = {e["name"]: e for e in DetectorRegistry.list_backends()}
    assert "boxer" in entries, (
        f"boxer should be registered by the pool_registry fixture; "
        f"got {list(entries.keys())}"
    )
    assert entries["boxer"]["available"] is False
    assert "test reason" in entries["boxer"]["reason"], (
        f"reason should echo the on_backend_crash argument; got {entries['boxer']['reason']!r}"
    )
