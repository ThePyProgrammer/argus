"""DetectorWorker: per-robot daemon thread with single-slot newest-wins queue.

Central runtime concurrency primitive for Phase 2 (DET-API-04).

Design (per 02-CONTEXT.md and 02-RESEARCH.md §Pattern 3):
- One ``DetectorWorker`` per robot_id, each owning a daemon thread named
  ``det-{rid}`` so Phase 6's MetricsPanel can filter by thread name.
- ``_pending`` is a single-slot tuple ``(frame, pose, slam_cloud, sim_time) | None``.
  ``submit()`` overwrites an existing ``_pending`` under lock (newest-wins per D-04)
  and increments ``_drops`` so the pool can expose a session-lifetime drop counter.
- ``submit()`` defensively copies ``pose`` via ``np.asarray(pose).copy()`` before
  stashing it (Pitfall 4 / T-02-06): a caller that mutates its pose buffer after
  calling ``submit`` MUST NOT be able to corrupt the worker's snapshot.
- ``_loop()`` drains ``_pending`` under lock, runs ``detector.process_frame`` +
  ``lifter.lift``, then uses ``dataclasses.replace`` to attach envelope-level
  ``capture_pose`` + ``capture_timestamp`` to the ``Detections3D`` (D-11/D-12/D-13).
  Any exception inside the inference path is caught + logged so the worker thread
  NEVER dies (T-02-07); the next ``submit()`` will simply enqueue a new frame.
- ``inspect()`` exposes ``{queue_depth, drops_since_session_start, last_submit_sim_time}``
  for the MetricsPanel; the caller sees a consistent lock-held snapshot.

Module-scope invariants (P9):
- No ``torch`` / ``ultralytics`` / ``transformers`` imports here. ``DetectorProtocol``
  and ``Detection3DProtocol`` are imported under ``TYPE_CHECKING`` only.
- ``tests/perception/test_protocol_contracts.py`` asserts that importing
  ``src.perception.worker`` does not pull torch into ``sys.modules``.

Plan 04 wraps this class in ``DetectorWorkerPool``. Plan 05 extends the
capture-pose test coverage. Wave 4 rewires the coordinator to call it.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from src.perception.types import Detections3D

if TYPE_CHECKING:  # pragma: no cover -- P9: TYPE_CHECKING only, no runtime import
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    from src.perception.protocol import Detection3DProtocol, DetectorProtocol


_LOGGER = logging.getLogger(__name__)

# Polling interval for the worker's drain loop when _pending is empty.
# 10 ms is well below the 200 Hz sim tick and the 30 Hz submit cadence, so the
# worker always picks up a new frame within one tick. Shorter intervals burn CPU
# for no throughput gain; longer intervals starve the 2 FPS detector of work.
_POLL_INTERVAL_SEC = 0.01

# shutdown() join timeout. 2 s is generous: _loop's inner work is either
# a time.sleep(_POLL_INTERVAL_SEC) or one detector inference, both bounded.
_SHUTDOWN_JOIN_TIMEOUT_SEC = 2.0


def _attach_capture(
    dets_3d: Detections3D,
    pose: np.ndarray,
    sim_time: float,
) -> Detections3D:
    """Overwrite ``capture_pose`` + ``capture_timestamp`` on a ``Detections3D``.

    Per 02-CONTEXT.md D-11/D-12/D-13, the worker owns the envelope-level pose +
    timestamp: Phase 1 lifters may set their own defaults (identity pose, 0.0
    timestamp), but the canonical source of truth for a detection's capture-time
    pose is the snapshot stashed in ``_pending`` at ``submit()`` time. Using
    ``dataclasses.replace`` preserves immutability of the frozen dataclass.
    """
    return replace(dets_3d, capture_pose=pose, capture_timestamp=sim_time)


class DetectorWorker:
    """Per-robot daemon-thread worker with single-slot newest-wins backpressure.

    Public API (all methods thread-safe under ``self._lock``):
      - ``start()``       -- spawn the daemon thread (idempotent: call once)
      - ``submit(frame, pose, slam_cloud)`` -- enqueue (newest-wins); increments
        drop counter when overwriting a non-drained pending frame
      - ``latest()``      -- most recent ``Detections3D`` or ``None``
      - ``inspect()``     -- ``{queue_depth, drops_since_session_start,
                              last_submit_sim_time}`` snapshot
      - ``warmup(dummy_frame)`` -- delegates to ``detector.warmup``; pool calls
        this BEFORE emitting ``detector_restart_complete`` (D-03)
      - ``reset()``       -- clears ``_pending`` + ``_latest`` and resets
        detector + lifter
      - ``shutdown()``    -- signals stop, joins the thread (timeout 2 s)

    Concurrency model:
      - Exactly two threads access ``_pending`` and ``_latest``: the caller
        (submit + reset + inspect + latest) and ``_loop``. ``threading.Lock``
        protects both fields; there are no unlocked reads.
      - ``_loop`` holds the lock only to grab-and-clear ``_pending`` and to
        write ``_latest``; the detector + lifter calls run WITHOUT the lock so
        a slow 2 FPS backend cannot starve ``submit()``.
      - The drop counter is session-lifetime (never reset by ``reset()``);
        ``reset()`` is for clearing queued work on detector swap, not for
        resetting metrics. The pool owns metric lifecycle.
    """

    def __init__(
        self,
        robot_id: str,
        detector: "DetectorProtocol",
        lifter: "Detection3DProtocol",
        intrinsics: "CameraIntrinsics",
    ) -> None:
        self._rid = robot_id
        self._detector = detector
        self._lifter = lifter
        self._intrinsics = intrinsics
        self._pending: tuple | None = None
        self._latest: Detections3D | None = None
        self._drops: int = 0
        self._last_submit_sim_time: float = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the daemon thread running ``_loop``.

        The thread name ``det-{robot_id}`` is consumed by Phase 6 MetricsPanel
        thread-name filtering; do not rename without updating that panel.
        """
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name=f"det-{self._rid}",
        )
        self._thread.start()

    def shutdown(self) -> None:
        """Signal stop and join the thread (bounded wait).

        Safe to call multiple times; safe to call before ``start()`` (no-op).
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=_SHUTDOWN_JOIN_TIMEOUT_SEC)

    # ------------------------------------------------------------------
    # Submission + introspection
    # ------------------------------------------------------------------

    def submit(
        self,
        frame: "SensorFrame",
        pose: np.ndarray,
        slam_cloud: np.ndarray | None,
    ) -> None:
        """Enqueue a frame for inference with newest-wins semantics (D-04).

        Snapshots captured at submit time (per D-12 / D-13):
          - ``pose``     -> deep-copied via ``np.asarray(pose).copy()`` so a
                           later in-place mutation by the caller cannot
                           corrupt the worker's snapshot (T-02-06 mitigation).
          - ``sim_time`` -> taken from ``frame.sim_time`` (NOT ``time.time()``)
                           so Phase 6 freshness metrics use sim-clock units.

        If ``_pending`` is not ``None`` when submit is called, the existing
        entry is DISCARDED and ``_drops`` is incremented -- the newer frame
        always wins. This is the core backpressure invariant: a slow detector
        can be overrun at any submit rate; the queue depth stays at {0, 1}.
        """
        # Copy outside the lock: np.asarray + .copy() only touches caller data.
        pose_snapshot = np.asarray(pose, dtype=np.float64).copy()
        sim_time = float(frame.sim_time)
        with self._lock:
            if self._pending is not None:
                self._drops += 1
            self._pending = (frame, pose_snapshot, slam_cloud, sim_time)
            self._last_submit_sim_time = sim_time

    def latest(self) -> Detections3D | None:
        """Return the most recent ``Detections3D``, or ``None`` if none yet."""
        with self._lock:
            return self._latest

    def inspect(self) -> dict:
        """Snapshot of queue depth + drop count + last submit sim-time.

        Returned fields:
          - ``queue_depth``: 0 or 1 (single-slot queue)
          - ``drops_since_session_start``: monotonic counter, never reset by
            ``reset()`` (pool owns metric lifecycle)
          - ``last_submit_sim_time``: sim-clock seconds of the most recent
            ``submit()`` call, 0.0 if none yet
        """
        with self._lock:
            return {
                "queue_depth": 1 if self._pending is not None else 0,
                "drops_since_session_start": self._drops,
                "last_submit_sim_time": self._last_submit_sim_time,
            }

    # ------------------------------------------------------------------
    # Backend lifecycle
    # ------------------------------------------------------------------

    def warmup(self, dummy_frame: "SensorFrame") -> None:
        """Delegate to ``detector.warmup``.

        Per D-03, the pool MUST call this BEFORE emitting
        ``detector_restart_complete`` so the UI never races a first-inference
        stall. Run on the caller's thread (pool thread), not the worker's
        ``_loop`` thread, so warmup completes deterministically.
        """
        self._detector.warmup(dummy_frame)

    def reset(self) -> None:
        """Reset detector + lifter state and drop any queued/latest frame.

        Does NOT reset ``_drops`` (session-lifetime counter). Does NOT stop
        the thread -- callers continue to call ``submit`` after ``reset``.
        """
        self._detector.reset()
        self._lifter.reset()
        with self._lock:
            self._pending = None
            self._latest = None

    # ------------------------------------------------------------------
    # Inference loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Drain ``_pending`` one frame at a time; never raise out.

        Loop structure:
          1. Under lock, grab + clear ``_pending``.
          2. If empty: sleep ``_POLL_INTERVAL_SEC`` and continue.
          3. Otherwise: run detector -> lifter -> attach capture envelope.
             Any exception is logged via ``logger.exception`` and the loop
             continues (T-02-07: worker thread must never silently die).
          4. Under lock, write the result to ``_latest``.

        The detector + lifter calls run OUTSIDE the lock so a slow backend
        cannot block ``submit()`` (newest-wins requires cheap submits).
        """
        while not self._stop.is_set():
            with self._lock:
                job, self._pending = self._pending, None
            if job is None:
                time.sleep(_POLL_INTERVAL_SEC)
                continue
            frame, pose, slam_cloud, sim_time = job
            try:
                dets_2d = self._detector.process_frame(frame)
                dets_3d = self._lifter.lift(
                    dets_2d,
                    frame,
                    pose,
                    self._intrinsics,
                    slam_cloud,
                )
                # D-11/D-12/D-13: worker is the authoritative source for the
                # envelope-level pose + timestamp. Phase 1 lifter defaults are
                # always overwritten here so the invariant holds even for
                # backends that happen to populate their own values.
                dets_3d = _attach_capture(dets_3d, pose, sim_time)
            except Exception as exc:
                # Defensive: the worker thread must never silently die. Log the
                # exception (including traceback via logger.exception) and loop
                # back -- the next submit() will enqueue a fresh frame.
                _LOGGER.exception(
                    "DetectorWorker %s: inference failed: %s", self._rid, exc
                )
                continue
            with self._lock:
                self._latest = dets_3d
