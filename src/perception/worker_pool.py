"""DetectorWorkerPool: Coordinator-owned keyed dispatch across per-robot workers.

Plan 02-04 deliverable (DET-API-04 + DET-MODELS-05).

Design (per 02-CONTEXT.md D-03 / D-05 and 02-RESEARCH.md Pattern 4):

- The pool wraps one ``DetectorWorker`` per ``robot_id``, each with ITS OWN
  ``DetectorProtocol`` + ``Detection3DProtocol`` instance (constructed via
  ``DetectorRegistry.create()`` / ``Detection3DRegistry.create()``). Per-robot
  instance separation — not a shared singleton — is what enables Phase 8's
  stretch DET-STRETCH-04 per-robot param tuning: mutating one worker's
  detector state never leaks into another.

- ``submit(rid, frame, pose, slam_cloud)`` is the single submission entry
  point for the Coordinator (D-05). Unknown ``rid`` -> defensive no-op so a
  stale-rid race during restart cannot crash the pool (T-02-08 mitigation).

- ``warmup_all(dummy_frames)`` is SYNCHRONOUS: every ``worker.warmup`` call
  completes on the caller's thread before ``warmup_all`` returns. Wave 4's
  ``main.py`` restart block chains this before emitting
  ``detector_restart_complete`` (D-03) so the UI restart overlay dismisses
  only after first inference is real — no oneDNN cold-start stall on the
  next real frame.

- ``inspect_worker_queues()`` returns a stable per-rid snapshot consumed by
  Phase 6's MetricsPanel: ``{rid: {queue_depth, drops_since_session_start,
  last_submit_sim_time}}``.

Construction sequence Wave 4's ``main.py`` must follow::

    pool = DetectorWorkerPool(
        robot_ids=[...],
        backend_name="yolov11",
        backend_params={...},
        lifter_name="median_depth",
        intrinsics_per_robot={...},
    )
    pool.warmup_all({rid: first_frame_per_rid})   # D-03 gate
    pool.start()                                   # spawn daemon threads
    # ... pool.submit(rid, frame, pose, cloud) from here on ...
    # at shutdown: pool.shutdown()

Module-scope invariants (Pitfall P9):
- No ``torch`` / ``ultralytics`` / ``transformers`` imports here. The only
  heavy-adjacent imports are ``registry`` + ``worker``, both torch-free.
- ``SensorFrame`` / ``CameraIntrinsics`` / ``Detections3D`` live behind
  ``TYPE_CHECKING`` so this module's import graph stays minimal.

Threat register references:
- T-02-08 (DoS via unknown rid) — mitigated by defensive no-op in submit/latest.
- T-02-09 (Tampering via backend_name) — transferred to Registry.create, which
  validates against the registered set. Plan 08's REST ``/select`` validates
  BEFORE writing to ``app.state``.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

import numpy as np

from src.perception.registry import Detection3DRegistry, DetectorRegistry
from src.perception.subprocess_bridge import BridgeHangError, SubprocessDiedError
from src.perception.worker import DetectorWorker

if TYPE_CHECKING:  # pragma: no cover -- P9: TYPE_CHECKING only, no runtime import
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    from src.perception.types import Detections3D

# Keep the typed exception imports visible at module scope — they are the
# failure surface DetectorWorker catches and escalates via on_backend_crash.
# Assigning to a sentinel silences unused-import lint without hiding them.
_BRIDGE_CRASH_EXCEPTIONS = (BridgeHangError, SubprocessDiedError)


_LOGGER = logging.getLogger(__name__)


class DetectorWorkerPool:
    """Keyed dispatch over per-robot ``DetectorWorker`` instances.

    Public API (thread-safe — each call delegates to a single worker whose
    internal state is guarded by its own lock):

      - ``start()``                       -- spawn every worker's daemon thread
      - ``submit(rid, frame, pose, cloud)`` -- dispatch to worker; unknown rid
                                             is a silent no-op (D-05)
      - ``latest(rid) -> Detections3D | None`` -- most recent result, or None
                                             for unknown rid
      - ``warmup_all(dummy_frames)``      -- synchronous per-worker warmup
                                             (D-03 restart gate)
      - ``inspect_worker_queues()``       -- per-rid snapshot for Phase 6
      - ``reset_all()``                   -- reset every worker's backend state
                                             and drop queued/latest frames
      - ``shutdown()``                    -- stop + join every worker thread
      - ``robot_ids``                     -- property; list of managed rids

    Construction contract:
      ``__init__`` constructs workers but does NOT call ``start()``. Callers
      typically chain::

          pool = DetectorWorkerPool(...)
          pool.warmup_all({...})   # D-03 gate — synchronous
          pool.start()             # threads spawn AFTER warmup

      This ordering matters because ``warmup`` runs on the CALLER's thread
      (delegating to ``detector.warmup`` synchronously), which is the whole
      point of the D-03 gate: the next ``submit`` call can race a worker
      thread on already-warmed state.
    """

    def __init__(
        self,
        robot_ids: list[str],
        backend_name: str,
        backend_params: dict | None,
        lifter_name: str,
        intrinsics_per_robot: dict[str, "CameraIntrinsics"],
        lifter_params: dict | None = None,
        streaming_viz: Any = None,
    ) -> None:
        """Construct one ``DetectorWorker`` per rid with its own detector + lifter.

        Args:
            robot_ids: Non-empty list of robot identifiers. Duplicates are
                silently deduplicated by dict construction (last wins).
            backend_name: Name registered in ``DetectorRegistry``. Upstream
                callers (Phase 8 REST ``/select``) MUST validate against the
                registered set before reaching the pool — T-02-09 transfer.
            backend_params: kwargs forwarded to ``DetectorRegistry.create``.
                ``None`` is treated as empty. Copied defensively so mutations
                by the caller after construction do not leak into later
                worker instantiations (irrelevant here because all workers
                are created in this call, but defensive anyway).
            lifter_name: Name registered in ``Detection3DRegistry``.
            intrinsics_per_robot: Dict keyed by rid. Each worker gets its
                rid's intrinsics — different robots may have different
                cameras. KeyError if a rid in ``robot_ids`` is missing
                from this dict (caller bug, fail loudly at construction).
            lifter_params: kwargs forwarded to
                ``Detection3DRegistry.create(lifter_name, **lifter_params)``.
                ``None`` is treated as empty. Defensive copy mirrors
                ``backend_params`` semantics so caller mutations cannot
                leak into per-worker lifter instances. Plan 03-06 added
                this kwarg to thread ``app.state.pending_lifter_params``
                from the ``main.py`` restart block (D-10).
            streaming_viz: Optional reference to the coordinator's
                ``StreamingVisualizer``. When set, :meth:`on_backend_crash`
                (Plan 05-09 / D-03) appends a ``crash_fallback`` message to
                ``streaming_viz._message_queue`` on subprocess-backend crash.
                Default ``None`` keeps unit-test construction trivial and
                lets ``main.py`` wire the viz post-construction via
                :meth:`set_streaming_viz` if the construction order needs it.
        """
        self.backend_name = backend_name
        self.lifter_name = lifter_name
        # Defensive copy: caller's dict mutations cannot retro-actively
        # change the kwargs that were forwarded to the registry.
        params = dict(backend_params or {})
        lifter_kwargs = dict(lifter_params or {})
        self._lifter_params = lifter_kwargs  # retained for repr/debug
        self._backend_params = params  # retained for fallback + debug
        self._intrinsics_per_robot = dict(intrinsics_per_robot)
        # Plan 05-09 (D-03): streaming_viz ref used by on_backend_crash to
        # emit the crash_fallback WS message. See set_streaming_viz for the
        # post-construction wiring path main.py uses.
        self._streaming_viz: Any = streaming_viz
        # Plan 04-05 (D-10): serialize concurrent hot-swappers. Held only
        # during the per-worker ref rebind loop (≪1ms); registry.create runs
        # OUTSIDE the lock so failing swaps don't block queued swappers.
        # Plan 05-09 reuses the same lock for on_backend_crash atomicity —
        # detector hot-swap and lifter hot-swap both rebind worker refs and
        # must not interleave.
        self._swap_lock = threading.Lock()
        self._workers: dict[str, DetectorWorker] = {}
        for rid in robot_ids:
            # Per-robot instance separation — two separate create() calls
            # yield two independent backend instances. This is the invariant
            # tested by test_instance_separation_backend_mutations_do_not_leak.
            detector = DetectorRegistry.create(backend_name, **params)
            lifter = Detection3DRegistry.create(lifter_name, **lifter_kwargs)
            self._workers[rid] = DetectorWorker(
                robot_id=rid,
                detector=detector,
                lifter=lifter,
                intrinsics=intrinsics_per_robot[rid],
                pool_ref=self,  # D-03 — reverse ref for on_backend_crash
            )

    def set_streaming_viz(self, streaming_viz: Any) -> None:
        """Store the StreamingVisualizer ref used by :meth:`on_backend_crash`.

        Plan 05-09 (D-03). ``main.py`` constructs the pool and the streaming
        visualizer in the same restart block, but the construction order may
        vary — this post-init setter lets the wiring happen once both objects
        exist. Idempotent: calling multiple times just overwrites the ref.
        ``None`` clears it (and the crash handler degrades to log-only).
        """
        self._streaming_viz = streaming_viz

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn each worker's daemon thread. Call AFTER ``warmup_all``."""
        for w in self._workers.values():
            w.start()

    def warmup_all(self, dummy_frames: dict[str, "SensorFrame"]) -> None:
        """Synchronously warm every worker's detector before threads are live.

        Per D-03 (restart protocol), Wave 4's ``main.py`` restart block awaits
        this call before emitting ``detector_restart_complete`` so the UI
        restart overlay dismisses only after first inference is real — no
        oneDNN cold-start stall on the next real frame.

        Iteration is SEQUENTIAL (not thread-pooled) because all workers share
        the oneDNN / BLAS thread pool; running warmups in parallel would
        contend the same CPU cores and defeat the point. Sequential keeps
        timing predictable.

        If a rid is missing from ``dummy_frames``, log a WARNING and skip
        that worker. Wave 4's restart path may only have captured a first
        real frame for a subset of robots at the moment of restart; hanging
        the whole restart until every robot has a frame would be worse than
        shipping a cold-start stall for the late ones.

        If a worker's ``warmup`` raises, log a WARNING and continue — the
        other robots must still come online. The restart completion event
        still fires; the bad backend reports its failure via ``get_metrics``
        in Phase 6.
        """
        for rid, w in self._workers.items():
            frame = dummy_frames.get(rid)
            if frame is None:
                _LOGGER.warning(
                    "warmup_all: no dummy frame for robot %s; skipping warmup "
                    "(cold-start stall possible on first real frame).",
                    rid,
                )
                continue
            try:
                w.warmup(frame)
            except Exception as exc:
                _LOGGER.warning(
                    "warmup_all: worker %s raised during warmup: %s "
                    "(continuing — backend will show the error via get_metrics).",
                    rid,
                    exc,
                )

    def reset_all(self) -> None:
        """Reset every worker's backend state and drop queued/latest frames.

        Used on detector swap (Phase 8 REST ``/select``): the new backend
        instance is NOT installed here — Wave 4 constructs a fresh pool
        behind ``app.state.detector_pool`` — but any residual state in a
        still-live pool (e.g., during a soft reset) is cleared.

        Does NOT reset per-worker session-lifetime drop counters; the
        MetricsPanel (Phase 6) wants cumulative drops across restarts.
        """
        for w in self._workers.values():
            w.reset()

    def swap_lifter(
        self,
        new_lifter_name: str,
        new_lifter_params: dict | None = None,
    ) -> None:
        """Hot-swap the lifter on every worker atomically (D-09 / D-10).

        Per Phase 4 D-10 (supersedes Phase 3 D-09):
          - Construct a FRESH lifter per worker via
            ``Detection3DRegistry.create(...)`` (per-worker-instance
            separation preserved — mirrors ``__init__``).
          - Hold ``self._swap_lock`` during the ref rebind loop (≪1ms;
            non-blocking for ``submit``/``latest`` which run on per-worker
            locks).
          - Workers reading ``self._lifter`` in ``_loop`` see either the
            old or the new ref — never torn. Python attribute-write
            atomicity under the GIL is the load-bearing primitive here
            (04-RESEARCH.md Pattern Template 3 + Pitfall 6).

        Does NOT call ``warmup()`` — lifters are stateless geometry in the
        Phase 4 contract. A ``ValueError`` from
        ``Detection3DRegistry.create`` (unknown name, missing dep) propagates
        BEFORE any worker is mutated — no partial swap, fail loudly.

        Pitfall 6 note: an in-flight ``lift`` call completes on the OLD
        lifter (Python captured the method-bound ref at dispatch time). The
        NEXT ``submit`` uses the new lifter. This is the documented behavior
        of an atomic ref swap — not a bug (threat register T-04-22).
        """
        # Force @detection_3d registration (matches the pattern at the route
        # handler boundaries — never rely on a pre-populated registry in a
        # public entry point).
        import src.perception.lifters  # noqa: F401

        lifter_kwargs = dict(new_lifter_params or {})
        # Construct per-worker lifters BEFORE touching any worker. If create
        # raises (unknown name, missing dep), no worker is mutated.
        new_lifters = {
            rid: Detection3DRegistry.create(new_lifter_name, **lifter_kwargs)
            for rid in self._workers
        }
        with self._swap_lock:
            for rid, w in self._workers.items():
                w._lifter = new_lifters[rid]  # atomic attribute write under GIL
            self.lifter_name = new_lifter_name
            self._lifter_params = lifter_kwargs

    # ------------------------------------------------------------------
    # Plan 05-09 (D-03) — crash fallback handler.
    # ------------------------------------------------------------------

    def _dummy_frame_for(self, rid: str) -> "SensorFrame":
        """Return a zero-RGB-and-depth ``SensorFrame`` for fallback warmup.

        Used by :meth:`on_backend_crash` to warm the freshly-constructed
        YOLOv11 fallback before atomic swap. 480×640 matches the Phase 1
        MuJoCo default frame size so the warmup's JIT/trace path is
        representative; the zero contents keep the warmup fast (≪1 s) and
        deterministic.
        """
        # Local import keeps sensor_types out of module-scope (Pitfall P9).
        from src.bridge.sensor_types import SensorFrame

        return SensorFrame(
            rgb=np.zeros((480, 640, 3), dtype=np.uint8),
            depth=np.zeros((480, 640), dtype=np.float32),
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )

    def on_backend_crash(
        self,
        crashed_backend: str,
        reason: str,
        fallback: str = "yolov11",
    ) -> None:
        """D-03 — emit ``crash_fallback`` WS + atomically swap to a fallback backend.

        Mirror of the SLAM crash pattern in
        ``src/exploration/exploration_loop.py:207``. Triggered by
        :class:`DetectorWorker` when ``detector.process_frame`` raises
        :class:`BridgeHangError` or :class:`SubprocessDiedError` (Plan 05-05
        typed exceptions from :class:`SubprocessDetectorBridge`).

        Steps (in order):

          1. Append a ``crash_fallback`` envelope to
             ``self._streaming_viz._message_queue`` when a viz is wired. The
             envelope matches the SLAM precedent literally
             (``type``/``payload.subsystem``/``payload.crashed_backend``/
             ``payload.fallback_backend``/``payload.reason``) so the frontend
             ``useWebSocket`` handler + ``CrashToast`` (Phase 3) consume it
             without a new branch. Emission failures are logged and swallowed
             — the worker thread must never block on viz I/O (T-5-05).

          2. Mark ``crashed_backend`` unavailable in the registry (D-04) so
             the detector dropdown greys it out with the crash reason until
             the coordinator restarts. Failures (unknown name, etc.) are
             logged and do not abort the fallback.

          3. Construct one fresh ``fallback`` backend **per worker**
             (per-instance separation invariant from ``__init__``), warm it
             with a dummy frame, then rebind every worker's ``_detector``
             under ``self._swap_lock``. The construction + warmup run
             OUTSIDE the lock so a failing fallback cannot leave workers
             with torn state. ``self.backend_name`` updates inside the lock
             so ``repr`` / dropdown reflects the live backend.

        Exceptions from step 3 are logged but NOT re-raised — a crashed
        fallback is still better than leaving the caller thread with a dead
        bridge, and the worker loop tolerates subsequent crashes because
        each ``process_frame`` exception is caught in :class:`DetectorWorker`.
        """
        _LOGGER.warning(
            "on_backend_crash: crashed=%s reason=%r → fallback=%s",
            crashed_backend,
            reason,
            fallback,
        )

        # Step 1 — WS message (same envelope as SLAM crash at exploration_loop.py:207).
        viz = self._streaming_viz
        if viz is not None and hasattr(viz, "_message_queue"):
            try:
                viz._message_queue.append(
                    {
                        "type": "crash_fallback",
                        "payload": {
                            "subsystem": "detector",
                            "crashed_backend": crashed_backend,
                            "fallback_backend": fallback,
                            "reason": reason,
                        },
                    }
                )
            except Exception:  # noqa: BLE001 — viz enqueue must never block the worker
                _LOGGER.exception(
                    "on_backend_crash: failed to enqueue crash_fallback message"
                )
        else:
            _LOGGER.warning(
                "on_backend_crash: no streaming_viz wired — "
                "skipping crash_fallback WS emit (fallback still proceeding)."
            )

        # Step 2 — Session-scoped availability lockout (D-04).
        try:
            DetectorRegistry.set_available(
                crashed_backend,
                False,
                reason=f"{reason} — restart the coordinator to retry.",
            )
        except Exception:  # noqa: BLE001 — registry lookup failure must not block fallback
            _LOGGER.exception(
                "on_backend_crash: set_available(%s, False) failed",
                crashed_backend,
            )

        # Step 3 — Construct + warm fallback per worker, then atomic ref swap.
        try:
            import src.perception.backends  # noqa: F401 -- trigger registration
            new_detectors: dict[str, Any] = {}
            for rid in self._workers:
                det = DetectorRegistry.create(fallback)
                try:
                    det.warmup(self._dummy_frame_for(rid))
                except Exception:  # noqa: BLE001 — log and continue; swap still proceeds
                    _LOGGER.exception(
                        "on_backend_crash: fallback %s warmup failed for %s",
                        fallback,
                        rid,
                    )
                new_detectors[rid] = det
            with self._swap_lock:
                for rid, w in self._workers.items():
                    w._detector = new_detectors[rid]  # atomic attr write under GIL
                self.backend_name = fallback
            _LOGGER.info(
                "on_backend_crash: swapped crashed %s → %s across %d workers",
                crashed_backend,
                fallback,
                len(self._workers),
            )
        except Exception:  # noqa: BLE001 — fallback construction is second-order
            _LOGGER.exception(
                "on_backend_crash: fallback construction failed for %s",
                fallback,
            )

    def shutdown(self) -> None:
        """Signal every worker to stop and join its thread (bounded 2 s each).

        Safe to call even if ``start()`` was never invoked — each worker's
        ``shutdown`` is a no-op when the thread is ``None``.
        """
        for w in self._workers.values():
            w.shutdown()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def submit(
        self,
        rid: str,
        frame: "SensorFrame",
        pose: np.ndarray,
        slam_cloud: np.ndarray | None = None,
    ) -> None:
        """Dispatch a frame to the worker owning ``rid`` (newest-wins on that worker).

        Unknown ``rid`` is a SILENT NO-OP (D-05 / T-02-08): Coordinator may
        race a stale rid past a robot teardown, and propagating KeyError
        would crash the detection dataflow for every other robot.
        """
        w = self._workers.get(rid)
        if w is None:
            return
        w.submit(frame, pose, slam_cloud)

    def latest(self, rid: str) -> "Detections3D | None":
        """Most recent Detections3D for ``rid``, or ``None`` (also for unknown rid)."""
        w = self._workers.get(rid)
        return w.latest() if w is not None else None

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def inspect_worker_queues(self) -> dict[str, dict]:
        """Per-rid snapshot for Phase 6 MetricsPanel.

        Returns::

            {rid: {
                "queue_depth": 0 | 1,
                "drops_since_session_start": int,
                "last_submit_sim_time": float,
            }, ...}

        Each worker's ``inspect()`` takes its own lock, so the per-rid
        entries are individually consistent. Cross-rid snapshots are NOT
        atomic — adjacent entries may differ by a submit that landed
        between calls. Phase 6 treats metrics as monotonic counters so
        this is fine.
        """
        return {rid: w.inspect() for rid, w in self._workers.items()}

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def robot_ids(self) -> list[str]:
        """List of managed robot ids (order matches construction)."""
        return list(self._workers.keys())

    def get_worker(self, rid: str) -> DetectorWorker | None:
        """Escape hatch for tests + Phase 6 probes. None if rid unknown."""
        return self._workers.get(rid)

    def __len__(self) -> int:
        return len(self._workers)

    def __contains__(self, rid: object) -> bool:
        return rid in self._workers

    # ------------------------------------------------------------------
    # Repr (debug-friendly)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover -- trivial formatting
        # Plan 03-06: include lifter_params only when non-empty so the
        # representation stays compact for the common Phase 2 path that
        # omits the kwarg.
        lp_part = (
            f", lifter_params={self._lifter_params!r}"
            if self._lifter_params
            else ""
        )
        return (
            f"DetectorWorkerPool(backend={self.backend_name!r}, "
            f"lifter={self.lifter_name!r}"
            f"{lp_part}, "
            f"robots={list(self._workers.keys())!r})"
        )


# Lightweight sanity: ``Any`` imported above is reserved for a future
# typed-params escape hatch; silence unused-import lint without moving the
# import off module-scope (keeps TYPE_CHECKING footprint visible).
_ = Any
