"""Subprocess bridge for out-of-process detector backends (Phase 5 BoxeR skeleton).

Structurally cloned from ``src/slam/backends/subprocess_bridge.py`` but with an
entirely separate class per Phase 2 CONTEXT.md decision D-16:

  * own ``zmq.Context`` per instance — NOT shared with SLAM bridge
  * endpoint prefix ``ipc:///tmp/detector_bridge_<pid>_<id(self)>`` — distinct
    from the SLAM bridge's ``slam_bridge_*`` prefix so a bug in one cannot
    squat or unlink the other's socket file
  * hardened msgpack ingress: ``raw=False`` + ``strict_map_key=True`` — rejects
    non-string map keys and returns ``str`` values (vs SLAM bridge's legacy
    ``raw=True`` path)
  * Phase 2 reply schema per D-17:
        {ts, inference_ms, n_det, classes, scores, bboxes}
    — generic ``dict`` only; detection typing (OrientedBox3D etc.) is a Phase 5
    concern and lives in the composing BoxeR backend, not this transport layer.

Phase 2 scope: skeleton only. No backend registers this bridge. Plan 02-07's
handshake test exercises spawn/send/recv/kill/cleanup via
``scripts/echo_detector_worker.py``. Phase 5 (DET-MODELS-03) composes this
class into a BoxeR backend — one bridge instance per backend, NOT per robot.

Phase 5 extensions (Plan 05-05):
  * Typed exceptions ``BridgeHangError`` / ``SubprocessDiedError`` replace the
    Phase 2 silent ``return None`` failure paths. The pool crash handler
    (Plan 05-09) catches them to drive the ``crash_fallback`` WS + YOLOv11
    swap (RESEARCH D-03).
  * ``wait_for_handshake(timeout_s)`` mitigates Open Risk #3 — BoxeR takes
    5–15 s to load weights; the first ``send_frame`` cannot race the worker's
    ``PAIR.connect()``. This method polls both Popen liveness and
    ``zmq.Poller(POLLOUT)`` readiness.
  * Background stdout/stderr drain thread mitigates T-5-05 — a chatty worker
    whose stdout fills the Popen PIPE buffer (~64 KB) would otherwise block
    indefinitely on ``write()`` and never reply, triggering a bogus
    ``BridgeHangError``. The thread reads to EOF and logs each line.

Threading: a single thread owns each bridge instance's socket exclusively.
pyzmq sockets are not thread-safe; the Phase 5 per-robot worker thread will
own its bridge's socket. Callers MUST NOT share a bridge across threads. The
drain thread reads ONLY ``process.stdout`` (which Popen merges with stderr via
``stderr=STDOUT``), never the ZMQ socket — so it cannot race the caller.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any

import msgpack
import numpy as np
import zmq

logger = logging.getLogger(__name__)


class BridgeHangError(RuntimeError):
    """Raised when SubprocessDetectorBridge.send_frame exceeds HANG_TIMEOUT_MS.

    Phase 5 DET-MODELS-06: DetectorWorkerPool.on_backend_crash catches this
    (along with SubprocessDiedError) to trigger the crash_fallback WS +
    YOLOv11 swap per RESEARCH D-03.
    """


class SubprocessDiedError(RuntimeError):
    """Raised when SubprocessDetectorBridge detects the worker Popen has exited.

    Detected via ``Popen.poll() != None`` OR via ``zmq.ZMQError`` during
    send/recv. Also raised pre-start (bridge is not alive).
    """


class BridgeHandshakeError(RuntimeError):
    """Raised by ``wait_for_handshake`` on protocol-level handshake failure.

    Reserved for future strict-protocol handshakes (e.g. worker-advertised
    schema negotiation). The current POLLOUT-readiness gate raises
    :class:`BridgeHangError` on timeout and :class:`SubprocessDiedError` on
    early worker exit; this class exists so downstream plans have a typed
    hook if they add a schema handshake.
    """


class SubprocessDetectorBridge:
    """Generic ZMQ/msgpack transport to an out-of-process detector worker.

    Independent of :class:`src.slam.backends.subprocess_bridge.SubprocessSLAMBridge`
    by design (D-16). The two classes share structure but not identity, context,
    or endpoint namespace. Composed by Phase 5 BoxeR backend.

    Wire protocol (per D-17):
        Outgoing (from bridge to worker)::

            multipart frame = [
                msgpack({"ts": float, "rgb_shape": [H, W, 3], "rgb_dtype": "uint8",
                         "depth_shape": [H, W] | None, "depth_dtype": "float32" | None,
                         "params": {...}}),
                rgb.tobytes(),
                depth.tobytes(),  # optional — only if depth is not None
            ]

        Incoming (from worker to bridge, Phase 5 D-02 extended schema — ADDITIVE)::

            msgpack({
                "ts": float,
                "inference_ms": float,
                "n_det": int,
                "classes": list[int],
                "scores": list[float],
                "bboxes": list[list[float]],       # 2D xyxy in pixels (Phase 2 — kept for CameraFeed)
                "boxes_3d": list[dict] | None,     # NEW Phase 5 — OMITTED or None when backend not 3D-native
                # each boxes_3d dict carries:
                #   {"tx", "ty", "tz",            # center, world frame, meters
                #    "qx", "qy", "qz", "qw",      # quaternion xyzw
                #    "w",  "h",  "d"}             # extent (FULL, not half — composer divides by 2 per D-02)
            })

    The bridge does NOT interpret the reply — it returns the raw ``dict`` to
    its caller. Phase 5's backend parses classes/scores/bboxes into concrete
    detection dataclasses and, when present, constructs :class:`OrientedBox3D`
    instances from the ``boxes_3d`` entries via ``to_wire()`` (Phase 1 D-10
    single-quaternion-construction-site invariant holds).
    """

    HANG_TIMEOUT_MS = 5000  # per must_haves/truths — locked at Phase 2

    def __init__(
        self,
        binary_path: str,
        args: list[str] | None = None,
        ipc_endpoint: str | None = None,
        hang_timeout_ms: int | None = None,
    ) -> None:
        self._binary = binary_path
        self._args = list(args) if args else []
        # Unique endpoint per instance — pid+id(self) survives fork'd tests
        # and prevents collisions between two bridges in the same process.
        self._endpoint = (
            ipc_endpoint
            if ipc_endpoint is not None
            else f"ipc:///tmp/detector_bridge_{os.getpid()}_{id(self)}"
        )
        self._timeout = hang_timeout_ms if hang_timeout_ms is not None else self.HANG_TIMEOUT_MS
        self._process: subprocess.Popen | None = None
        self._ctx: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._alive = False
        # T-5-05 mitigation: background drain of Popen.stdout (with stderr
        # merged via stderr=STDOUT) so a chatty worker cannot wedge us by
        # filling the PIPE buffer.
        self._stdout_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def alive(self) -> bool:
        """Whether the bridge's subprocess is believed to be running.

        Flips to ``False`` on crash detection, hang (``zmq.Again``), or any
        explicit ``shutdown()`` / ``_kill_process()`` call.
        """
        return self._alive

    @property
    def endpoint(self) -> str:
        """ZMQ IPC endpoint string (``ipc:///tmp/detector_bridge_...``)."""
        return self._endpoint

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Bind the PAIR socket and spawn the worker subprocess.

        Socket options:
            * ``RCVTIMEO = self._timeout`` so ``recv()`` raises
              :class:`zmq.Again` instead of blocking indefinitely.
            * ``LINGER = 0`` so ``ctx.term()`` on cleanup cannot hang
              if the worker crashed mid-reply.

        Popen config:
            * ``stderr=STDOUT`` merges both streams into ``stdout``.
            * ``bufsize=1`` gives line-buffered stdout so the drain thread
              emits log lines promptly.
            * The daemon drain thread is spawned immediately so even a
              burst of pre-handshake stdout output cannot fill the pipe.
        """
        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.PAIR)
        self._socket.setsockopt(zmq.RCVTIMEO, self._timeout)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.bind(self._endpoint)

        cmd = [self._binary, "--zmq", self._endpoint, *self._args]
        logger.info("Spawning detector subprocess: %s", " ".join(cmd))
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merged — one drain thread covers both
            bufsize=1,
            text=True,
        )
        self._alive = True

        # Start drain thread AFTER Popen is assigned so the thread never sees
        # a None _process. daemon=True ensures the thread does not block
        # interpreter shutdown if the worker somehow leaks.
        self._stdout_thread = threading.Thread(
            target=self._drain_worker_output,
            name=f"detector-bridge-drain-{self._process.pid}",
            daemon=True,
        )
        self._stdout_thread.start()

    def wait_for_handshake(self, timeout_s: float = 60.0) -> None:
        """Block until the worker has connected and the socket is write-ready.

        Open Risk #3 (RESEARCH): BoxeR takes 5–15 s to load DINOv3+BoxerNet
        weights before calling ``PAIR.connect()``. The FIRST ``send_frame``
        cannot race that — without a gate, the bridge's send succeeds into
        a queue with no consumer and the subsequent ``recv`` times out
        within 5 s, triggering a bogus :class:`BridgeHangError` even though
        the worker is healthy.

        Implementation: poll both ``Popen.poll()`` (to fail fast if the
        worker crashed during weight load) and ``zmq.Poller(POLLOUT)``
        readiness (which flips True only after the peer connects a PAIR
        socket). The POLLOUT semantics here are reliable because PAIR sockets
        only report writable when a peer is connected — unlike PUSH/ROUTER.

        Args:
            timeout_s: Maximum time to wait for the handshake. Default 60 s
                accommodates BoxeR's weight-load worst case (weights +
                DINOv3 + first CUDA init on a cold box).

        Raises:
            SubprocessDiedError: worker Popen exited before the handshake
                completed.
            BridgeHangError: worker did not connect within ``timeout_s``.
        """
        if self._process is None or self._socket is None:
            raise SubprocessDiedError(
                "bridge is not alive (start() not called or teardown already ran)"
            )

        deadline = self._now() + max(0.0, timeout_s)
        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLOUT)
        # Poll in short slices so we can observe Popen death between slices
        # without waiting the full timeout.
        slice_ms = 100
        while True:
            if self._process.poll() is not None:
                code = self._process.returncode
                raise SubprocessDiedError(
                    f"worker exited with code {code} before handshake"
                )
            events = dict(poller.poll(slice_ms))
            if events.get(self._socket) == zmq.POLLOUT:
                logger.info("bridge handshake complete for %s", self._endpoint)
                return
            if self._now() >= deadline:
                raise BridgeHangError(
                    f"worker did not connect within {timeout_s}s"
                )

    def send_frame(
        self,
        rgb: np.ndarray,
        depth: np.ndarray | None,
        timestamp: float,
        params: dict | None = None,
    ) -> dict:
        """Send one frame to the worker, receive and decode the reply dict.

        Returns the raw reply dict on success. Failure paths raise typed
        exceptions (Plan 05-05): :class:`BridgeHangError` on RCVTIMEO and
        :class:`SubprocessDiedError` on Popen exit / ZMQ error / pre-start
        call. All failure paths funnel through :meth:`_kill_process` so the
        bridge cannot be left in a half-alive state.

        Args:
            rgb: ``(H, W, 3) uint8`` colour image.
            depth: Optional ``(H, W) float32`` depth image in metres. Detectors
                that do not consume depth (e.g. OWLv2) pass ``None``.
            timestamp: Simulation time in seconds (mirrors SLAM bridge).
            params: Optional per-frame backend parameters (score threshold,
                topk, etc.). Passed opaquely inside the msgpack header.

        Raises:
            SubprocessDiedError: bridge not started, Popen exited, or ZMQ
                reported a fatal transport error.
            BridgeHangError: worker did not reply within ``hang_timeout_ms``.
        """
        if not self._alive:
            raise SubprocessDiedError(
                "bridge is not alive (start() not called or teardown already ran)"
            )

        # Crash detection: Popen has exited since last call.
        if self._process is not None and self._process.poll() is not None:
            code = self._process.returncode
            logger.warning("Detector subprocess exited with code %d", code)
            self._cleanup()
            raise SubprocessDiedError(f"worker exited with code {code}")

        try:
            header_dict: dict[str, Any] = {
                "ts": float(timestamp),
                "rgb_shape": list(rgb.shape),
                "rgb_dtype": str(rgb.dtype),
                "depth_shape": None if depth is None else list(depth.shape),
                "depth_dtype": None if depth is None else str(depth.dtype),
                "params": params or {},
            }
            header = msgpack.packb(header_dict)
            parts: list[bytes] = [header, rgb.tobytes()]
            if depth is not None:
                parts.append(depth.tobytes())

            assert self._socket is not None  # narrow for type checkers
            self._socket.send_multipart(parts)

            reply = self._socket.recv()
            # Hardened ingress: strict_map_key=True rejects non-string keys,
            # raw=False auto-decodes bytes values. Phase 2 controls both ends
            # of this protocol, so tightening is safe (unlike the SLAM bridge
            # which must interop with legacy C++ binaries that send bytes keys).
            return msgpack.unpackb(reply, raw=False, strict_map_key=True)

        except zmq.Again:
            logger.error(
                "Detector subprocess hung (no response in %dms)", self._timeout
            )
            self._kill_process()
            raise BridgeHangError(
                f"no response in {self._timeout}ms"
            ) from None
        except zmq.ZMQError as exc:
            logger.error("Detector ZMQ error: %s", exc)
            self._kill_process()
            raise SubprocessDiedError(f"zmq error: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 — transport must never leak
            logger.error("Unexpected error in detector send_frame: %s", exc)
            self._kill_process()
            raise SubprocessDiedError(
                f"unexpected error in send_frame: {exc}"
            ) from exc

    def shutdown(self) -> None:
        """Gracefully tear down the worker and release all resources."""
        self._kill_process()

    # ------------------------------------------------------------------
    # Internal teardown
    # ------------------------------------------------------------------

    def _drain_worker_output(self) -> None:
        """Read Popen.stdout (merged with stderr) to EOF, logging each line.

        T-5-05 mitigation: without this, a chatty worker fills the ~64 KB
        OS pipe buffer and then blocks on its next ``print()`` — no reply
        ever reaches the bridge and ``send_frame`` raises a bogus
        :class:`BridgeHangError`.

        Runs as a daemon thread. Exits on EOF (worker closes stdout / exits).
        Never raises — any exception is swallowed + logged; the drain must
        not be able to crash the main bridge thread.
        """
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        pid = proc.pid
        try:
            # ``for line in proc.stdout`` uses the text-mode iterator with
            # bufsize=1 (line-buffered) so every print() the worker emits
            # surfaces promptly in the parent's logs.
            for line in proc.stdout:
                try:
                    logger.info("[worker %d] %s", pid, line.rstrip())
                except Exception:  # noqa: BLE001 — drain must never raise
                    pass
        except Exception as exc:  # noqa: BLE001 — drain must never raise
            logger.debug("drain thread for worker %d ended: %s", pid, exc)

    def _kill_process(self) -> None:
        """Kill the worker subprocess and run :meth:`_cleanup`.

        Safe to call repeatedly and before :meth:`start`. Joins the drain
        thread briefly so it doesn't outlive the Popen reference.
        """
        self._alive = False
        if self._process is not None:
            try:
                self._process.kill()
                self._process.wait(timeout=2)
            except Exception:  # noqa: BLE001 — cleanup must never raise
                pass
            self._process = None
        # Join the drain thread — after Popen is killed + stdout closed,
        # the for-loop inside the thread will EOF and the thread will exit.
        if self._stdout_thread is not None:
            try:
                self._stdout_thread.join(timeout=1.0)
            except Exception:  # noqa: BLE001
                pass
            self._stdout_thread = None
        self._cleanup()

    def _cleanup(self) -> None:
        """Close socket, terminate context, and unlink the IPC socket file.

        Unlink guarantees that the next bridge bound to the same endpoint
        (e.g. after a deterministic test restart) will not hit EADDRINUSE.
        ``LINGER = 0`` ensures ``ctx.term()`` cannot hang if the worker died
        with queued outbound messages.
        """
        self._alive = False
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:  # noqa: BLE001
                pass
            self._socket = None
        if self._ctx is not None:
            try:
                self._ctx.term()
            except Exception:  # noqa: BLE001
                pass
            self._ctx = None
        if self._endpoint.startswith("ipc://"):
            sock_path = self._endpoint.replace("ipc://", "", 1)
            if os.path.exists(sock_path):
                try:
                    os.unlink(sock_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Small seam for tests — monkeypatchable clock.
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> float:
        import time

        return time.monotonic()
