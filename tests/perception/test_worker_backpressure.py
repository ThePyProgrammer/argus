"""DetectorWorker backpressure + safety tests (Plan 02-03, DET-API-04).

Three invariants under test:

1. **Newest-wins under adversarial load** -- 30 Hz submit into a 2 FPS fake
   detector. The single-slot queue must hold at most 1 frame; the drop counter
   must grow monotonically (STRIDE T-02-05 mitigation).

2. **Worker thread never dies** -- a detector that raises ``RuntimeError``
   MUST be caught inside ``_loop`` so the thread stays alive. The next
   ``submit()`` just enqueues a new frame (STRIDE T-02-07 mitigation).

3. **Defensive pose copy** -- a caller that mutates its ``pose`` ndarray
   after calling ``submit()`` must NOT corrupt the worker's snapshot
   (STRIDE T-02-06 mitigation / Plan 02-03 Pitfall 4).

The tests avoid heavy dependencies: fake Detector + fake Lifter classes are
defined inline, so this file runs without torch/ultralytics and respects
Pitfall P9 at the test level (``src.perception.worker`` stays torch-free).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import Detections2D, Detections3D
from src.perception.worker import DetectorWorker


# ---------------------------------------------------------------------------
# Fakes (no heavy deps, deterministic timing)
# ---------------------------------------------------------------------------


class SlowDetector:
    """Fake 2 FPS detector: each process_frame sleeps 0.5 s."""

    CAPABILITIES: dict = {}
    PARAMETER_SCHEMA: dict = {}

    def warmup(self, f: SensorFrame) -> None:  # pragma: no cover -- trivial
        return None

    def reset(self) -> None:  # pragma: no cover -- trivial
        return None

    def process_frame(self, f: SensorFrame) -> Detections2D:
        time.sleep(0.5)  # 2 FPS steady-state
        return Detections2D(items=[], inference_ms=500.0, image_hw=(480, 640))

    def get_metrics(self) -> dict:  # pragma: no cover -- not exercised
        return {}

    def apply_params(self, p: dict) -> dict:  # pragma: no cover -- not exercised
        return {k: "applied" for k in p}


class FlakyDetector(SlowDetector):
    """Fake detector that always raises: proves worker thread survival."""

    def process_frame(self, f: SensorFrame) -> Detections2D:
        raise RuntimeError("intentional test exception")


class DummyLifter:
    """Fake lifter: returns an empty Detections3D with identity pose defaults.

    The worker OVERWRITES ``capture_pose`` + ``capture_timestamp`` via
    ``_attach_capture`` (D-11/D-12/D-13), so whatever this returns for those
    fields is overridden before the result lands in ``_latest``.
    """

    CAPABILITIES: dict = {}
    PARAMETER_SCHEMA: dict = {}

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

    def reset(self) -> None:  # pragma: no cover -- trivial
        return None

    def get_metrics(self) -> dict:  # pragma: no cover -- not exercised
        return {}

    def apply_params(self, p: dict) -> dict:  # pragma: no cover -- not exercised
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(sim_time: float) -> SensorFrame:
    """Construct a minimal SensorFrame for worker tests."""
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    return SensorFrame(
        rgb=rgb,
        depth=depth,
        ground_truth_pose=np.eye(4),
        sim_time=sim_time,
    )


def _intrinsics() -> CameraIntrinsics:
    return CameraIntrinsics.from_fov(640, 480, 70.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_backpressure_drops_stale_frames() -> None:
    """30 Hz submit into 2 FPS detector: queue_depth <= 1 and drops >= 50.

    60 submits over ~2 s. The 2 FPS detector only picks up ~4 frames total,
    so ~56 submits overwrite a pending entry. Assert the drop counter is at
    least 50 (slack for the small number actually drained) and the single-slot
    queue never exceeds depth 1.
    """
    w = DetectorWorker("r0", SlowDetector(), DummyLifter(), _intrinsics())
    w.start()
    try:
        max_depth_observed = 0
        for i in range(60):
            w.submit(_make_frame(sim_time=i / 30.0), np.eye(4), None)
            # Sample queue depth immediately after submit. Because _loop drains
            # under lock and submit writes under lock, this snapshot is
            # guaranteed to be <= 1; we assert the invariant inline so the
            # failure points at the offending submit.
            depth = w.inspect()["queue_depth"]
            assert depth <= 1, f"queue_depth > 1 at submit {i}: got {depth}"
            max_depth_observed = max(max_depth_observed, depth)
            time.sleep(1.0 / 30.0)

        # Let the inflight frame drain so inspect() reflects a stable state.
        time.sleep(0.6)

        snap = w.inspect()
        assert snap["queue_depth"] <= 1, (
            f"queue_depth > 1 after drain: {snap['queue_depth']}"
        )
        assert snap["drops_since_session_start"] >= 50, (
            f"expected >=50 drops under 30 Hz / 2 FPS, got "
            f"{snap['drops_since_session_start']}"
        )
        # Sanity: we actually observed a pending entry at some point (else the
        # test proves nothing). Because _loop polls every 10 ms while detector
        # holds a 0.5 s sleep, the queue sits at depth=1 for most of the run.
        assert max_depth_observed == 1, (
            "expected to observe queue_depth==1 at least once; test is not "
            "exercising the backpressure path"
        )
    finally:
        w.shutdown()


def test_worker_never_dies_on_inference_exception() -> None:
    """A detector that raises must not kill the worker thread (T-02-07)."""
    w = DetectorWorker("r1", FlakyDetector(), DummyLifter(), _intrinsics())
    w.start()
    try:
        for i in range(3):
            w.submit(_make_frame(sim_time=i * 0.1), np.eye(4), None)
            # Give _loop enough time to pick up + fail + continue. 150 ms is
            # well above the 10 ms poll interval; the inference path itself is
            # an immediate raise (no sleep in FlakyDetector.process_frame).
            time.sleep(0.15)

        assert w._thread is not None and w._thread.is_alive(), (
            "worker thread died after inference exception"
        )
        assert w.latest() is None, (
            "latest() must remain None when every inference raises"
        )
    finally:
        w.shutdown()


def test_defensive_pose_copy() -> None:
    """Caller mutation of pose after submit() must not corrupt the snapshot.

    Plan 02-03 Pitfall 4 / STRIDE T-02-06. Without the defensive
    ``np.asarray(pose).copy()`` inside ``submit()``, the caller's later
    in-place write would flow through to ``_latest.capture_pose``.
    """
    w = DetectorWorker("r2", SlowDetector(), DummyLifter(), _intrinsics())
    w.start()
    try:
        original_pose = np.eye(4)
        original_pose[0, 3] = 5.0
        frame = _make_frame(sim_time=0.1)
        w.submit(frame, original_pose, None)

        # Caller mutates its buffer AFTER submit: the worker must already have
        # copied. This is the whole point of the defensive copy.
        original_pose[0, 3] = 999.0

        # Wait for _loop to drain + run inference (0.5 s SlowDetector) + write
        # _latest. 0.7 s is 0.5 s inference + 0.2 s slack for scheduler jitter.
        time.sleep(0.7)

        latest = w.latest()
        assert latest is not None, "worker did not drain submit within 0.7 s"
        assert latest.capture_pose[0, 3] == pytest.approx(5.0), (
            f"pose snapshot corrupted by caller mutation: "
            f"got {latest.capture_pose[0, 3]}, expected 5.0"
        )
        assert latest.capture_timestamp == pytest.approx(0.1), (
            f"capture_timestamp should come from frame.sim_time: "
            f"got {latest.capture_timestamp}, expected 0.1"
        )
    finally:
        w.shutdown()


def test_worker_module_does_not_import_torch() -> None:
    """Pitfall P9: importing src.perception.worker must not pull torch in.

    The worker is protocol-agnostic: it never touches torch / ultralytics /
    transformers at module scope. If this test fails, a new import at the top
    of worker.py is violating the layered import order.
    """
    import sys

    # Drop any cached reference so we re-import fresh.
    for mod in list(sys.modules):
        if mod.startswith("src.perception.worker"):
            del sys.modules[mod]
    pre = set(sys.modules.keys())
    import src.perception.worker  # noqa: F401
    post = set(sys.modules.keys())
    delta = post - pre
    for fw in ("torch", "ultralytics", "transformers", "onnxruntime"):
        assert fw not in delta or fw in pre, (
            f"importing src.perception.worker pulled {fw} into sys.modules "
            f"(Pitfall P9 violation)"
        )
