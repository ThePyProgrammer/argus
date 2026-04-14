"""DetectorWorker capture-pose freshness contract tests (Plan 02-05, DET-API-05).

Three invariants proving the submit-time snapshot semantics (02-CONTEXT.md
D-11, D-12, D-13) hold under adversarial scheduling. The implementation lives
in ``src.perception.worker.DetectorWorker`` (Plan 02-03); this file is the
test-only companion that proves the contract:

1. **D-13 -- capture_pose snapshot-at-submit, not at-lift.**
   A caller submits at t=0 with ``pose=P0`` and then mutates ``P0`` in place
   to ``P1`` BEFORE the 300 ms inference completes. ``worker.latest().capture_pose``
   must equal ``P0`` (submit-time), not ``P1`` (lift-time). Without the
   defensive ``np.asarray(pose).copy()`` in ``DetectorWorker.submit`` this
   test would silently regress into "we store a lift-time pose".

2. **D-12 -- capture_timestamp sourced from frame.sim_time at submit.**
   A frame with ``sim_time=42.5`` must yield ``latest.capture_timestamp == 42.5``
   exactly -- ``DetectorWorker.submit`` already does ``float(frame.sim_time)``,
   so the round-trip is bit-exact. Phase 6's freshness metric
   (``sim_now - latest.capture_timestamp``) depends on this being a clean
   subtraction in sim-clock units, not a wall-clock drift.

3. **D-11 -- envelope-level pose storage, not per-box.**
   A lifter that returns N OrientedBox3D items yields a Detections3D whose
   ``capture_pose`` sits on the envelope (one for the whole frame), and
   whose ``items[i]`` carry no ``capture_pose`` attribute. This is the
   ArchitectureDecision lock: pose is per-frame, not per-box, because every
   box in one call to ``detector.process_frame`` shares the capture moment.

The tests intentionally use the same SlowDetector pattern as the Plan 02-03
backpressure tests so we exercise the inference-latency scenario: the whole
point is to prove the snapshot survives a non-trivial gap between submit and
lift. We DO NOT modify ``worker.py`` from this plan -- if a test fails, that
is a Plan 02-03 contract miss and the executor should fail loudly, not patch
the worker.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import Detections2D, Detections3D, OrientedBox3D
from src.perception.worker import DetectorWorker


# ---------------------------------------------------------------------------
# Fakes: SlowDetector (adversarial latency), EmptyLifter, ItemsLifter
# ---------------------------------------------------------------------------


class SlowDetector:
    """Fake detector whose process_frame sleeps 300 ms.

    The latency is the adversarial ingredient: it guarantees the caller has
    time to mutate its pose buffer between submit and _loop's attach step.
    If the worker stored a reference (not a copy), the mutation would land
    in capture_pose and the D-13 test would fail.
    """

    CAPABILITIES: dict = {}
    PARAMETER_SCHEMA: dict = {}

    def warmup(self, f: SensorFrame) -> None:  # pragma: no cover -- trivial
        return None

    def reset(self) -> None:  # pragma: no cover -- trivial
        return None

    def process_frame(self, f: SensorFrame) -> Detections2D:
        time.sleep(0.3)
        return Detections2D(items=[], inference_ms=300.0, image_hw=(480, 640))

    def get_metrics(self) -> dict:  # pragma: no cover -- not exercised
        return {}

    def apply_params(self, p: dict) -> dict:  # pragma: no cover -- not exercised
        return {}


class EmptyLifter:
    """Lifter that returns Detections3D with STALE default pose + timestamp.

    The staleness is deliberate: we populate ``capture_pose=np.eye(4)`` and
    ``capture_timestamp=0.0`` so that if the worker forgets to overwrite via
    ``_attach_capture`` (D-11/D-12/D-13), the test will see the identity pose
    and zero timestamp and fail with a clear message. A non-staleness default
    would mask a worker that fails to attach.
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
            capture_pose=np.eye(4),   # stale default -- worker MUST overwrite
            capture_timestamp=0.0,    # stale default -- worker MUST overwrite
        )

    def reset(self) -> None:  # pragma: no cover -- trivial
        return None


class ItemsLifter:
    """Lifter that returns Detections3D with 3 synthetic OrientedBox3D items.

    Used by ``test_envelope_level_not_per_box`` to prove that:
      - the 3 items survive the worker's ``_attach_capture`` unmodified
        (the lifter's box objects are NOT rewrapped per D-11), and
      - capture_pose lives on the envelope (Detections3D), not on each box.
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
        items = [
            OrientedBox3D(
                center=np.array([float(i), 0.0, 0.0], dtype=np.float64),
                half_extents=np.array([0.5, 0.5, 0.5], dtype=np.float64),
                quaternion=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
                class_id=56,
                class_name="chair",
                score=0.9,
                track_id=None,
            )
            for i in range(3)
        ]
        return Detections3D(
            items=items,
            lifter_ms=1.0,
            detector_ms=d2d.inference_ms,
            n_raw=3,
            n_final=3,
            image_hw=d2d.image_hw,
            capture_pose=np.eye(4),   # stale default -- worker overwrites
            capture_timestamp=0.0,    # stale default -- worker overwrites
        )

    def reset(self) -> None:  # pragma: no cover -- trivial
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(sim_time: float) -> SensorFrame:
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


# Ample wait: SlowDetector is 300 ms, _loop polls every 10 ms, so 500 ms
# (300 ms inference + 200 ms slack for scheduler jitter on a loaded CI host)
# is enough for every test to observe the posted Detections3D in _latest.
_INFERENCE_WAIT_SEC = 0.5


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_capture_pose_snapshotted_at_submit() -> None:
    """D-13: capture_pose reflects submit-time pose, not lift-time pose.

    Scenario:
      t=0.00  caller builds pose_at_submit with translation 5.0
      t=0.00  caller calls ``worker.submit(frame, pose_at_submit, None)``
      t=0.00  caller mutates pose_at_submit[0,3] = 99.0 in place
              (simulates the robot continuing to move during the 300 ms
               inference: the coordinator's pose buffer is updated before
               the detector's output lands)
      t=0.30  SlowDetector.process_frame returns, _loop attaches capture_pose
      t=0.50  assert latest.capture_pose[0,3] == 5.0

    Failure mode without defensive copy: the worker would store a reference
    to pose_at_submit; the caller's in-place mutation at t=0.00 would change
    the stored pose to translation 99.0, and the 300 ms later ``_attach_capture``
    would bake that polluted pose into Detections3D.capture_pose.
    """
    w = DetectorWorker("r0", SlowDetector(), EmptyLifter(), _intrinsics())
    w.start()
    try:
        pose_at_submit = np.eye(4)
        pose_at_submit[0, 3] = 5.0
        frame = _make_frame(sim_time=1.0)
        w.submit(frame, pose_at_submit, None)

        # Caller-side mutation AFTER submit: worker's copy must already be done.
        pose_at_submit[0, 3] = 99.0

        # Wait for inference to complete and _latest to be posted.
        time.sleep(_INFERENCE_WAIT_SEC)

        latest = w.latest()
        assert latest is not None, (
            "worker did not produce a Detections3D within "
            f"{_INFERENCE_WAIT_SEC} s -- _loop may be starved or dead"
        )
        assert latest.capture_pose[0, 3] == pytest.approx(5.0), (
            f"capture_pose drifted: expected translation 5.0 (submit-time), "
            f"got {latest.capture_pose[0, 3]} (would be 99.0 if worker "
            f"stored a reference instead of a copy). D-13 contract violated."
        )
    finally:
        w.shutdown()


def test_capture_timestamp_from_frame_sim_time() -> None:
    """D-12: capture_timestamp equals frame.sim_time (exact, sim-clock source).

    Phase 6 freshness metric computes ``sim_now - latest.capture_timestamp``
    in sim-clock seconds. If the worker accidentally captured ``time.time()``
    instead of ``frame.sim_time`` the subtraction would return garbage.

    We pick 42.5 (an odd non-zero sim_time) so the test distinguishes between
    "worker attached correctly" (42.5) and "worker left the lifter's stale
    default" (0.0) with no room for confusion.
    """
    w = DetectorWorker("r0", SlowDetector(), EmptyLifter(), _intrinsics())
    w.start()
    try:
        frame = _make_frame(sim_time=42.5)
        w.submit(frame, np.eye(4), None)

        time.sleep(_INFERENCE_WAIT_SEC)

        latest = w.latest()
        assert latest is not None, "worker did not produce a Detections3D"
        assert latest.capture_timestamp == pytest.approx(42.5), (
            f"capture_timestamp drift: expected 42.5 (frame.sim_time at submit), "
            f"got {latest.capture_timestamp} (would be 0.0 if worker left the "
            f"lifter's stale default, or a wall-clock value if worker sourced "
            f"time.time()). D-12 contract violated."
        )
    finally:
        w.shutdown()


def test_envelope_level_not_per_box() -> None:
    """D-11: capture_pose is an envelope field on Detections3D, not per-box.

    An N-item lifter output yields:
      - ``Detections3D.capture_pose`` set ONCE on the envelope
      - ``Detections3D.capture_timestamp`` set ONCE on the envelope
      - each ``Detections3D.items[i]`` (an OrientedBox3D) carries NO per-box
        capture_pose / capture_timestamp attribute

    The OrientedBox3D dataclass is frozen and does not declare capture_pose
    as a field, so ``hasattr(item, 'capture_pose')`` must be False. This
    test guards against a future refactor that "helpfully" duplicates the
    pose onto every OBB (which would waste ~16*8 bytes per box and break
    the wire format -- see types.to_wire()).
    """
    w = DetectorWorker("r0", SlowDetector(), ItemsLifter(), _intrinsics())
    w.start()
    try:
        pose = np.eye(4)
        pose[0, 3] = 7.0
        frame = _make_frame(sim_time=3.14)
        w.submit(frame, pose, None)

        time.sleep(_INFERENCE_WAIT_SEC)

        latest = w.latest()
        assert latest is not None, "worker did not produce a Detections3D"

        # Envelope-level fields: one capture_pose shared by all 3 items.
        assert len(latest.items) == 3, (
            f"expected 3 OBB items from ItemsLifter, got {len(latest.items)}"
        )
        assert latest.capture_pose[0, 3] == pytest.approx(7.0), (
            f"envelope capture_pose wrong: expected translation 7.0, "
            f"got {latest.capture_pose[0, 3]}"
        )
        assert latest.capture_timestamp == pytest.approx(3.14), (
            f"envelope capture_timestamp wrong: expected 3.14, "
            f"got {latest.capture_timestamp}"
        )

        # No per-box pose / timestamp leakage (D-11 invariant).
        for i, item in enumerate(latest.items):
            assert not hasattr(item, "capture_pose"), (
                f"items[{i}]: OrientedBox3D must not carry per-box capture_pose "
                f"(D-11: pose is envelope-level, not per-box)"
            )
            assert not hasattr(item, "capture_timestamp"), (
                f"items[{i}]: OrientedBox3D must not carry per-box capture_timestamp "
                f"(D-11: timestamp is envelope-level, not per-box)"
            )
    finally:
        w.shutdown()
