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

Threading: a single thread owns each bridge instance's socket exclusively.
pyzmq sockets are not thread-safe; the Phase 5 per-robot worker thread will
own its bridge's socket. Callers MUST NOT share a bridge across threads.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

import msgpack
import numpy as np
import zmq

logger = logging.getLogger(__name__)


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

        Incoming (from worker to bridge)::

            msgpack({"ts": float, "inference_ms": float, "n_det": int,
                     "classes": list[int], "scores": list[float],
                     "bboxes": list[list[float]]})

    The bridge does NOT interpret the reply — it returns the raw ``dict`` to
    its caller. Phase 5's backend parses classes/scores/bboxes into concrete
    detection dataclasses.
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
            stderr=subprocess.PIPE,
        )
        self._alive = True

    def send_frame(
        self,
        rgb: np.ndarray,
        depth: np.ndarray | None,
        timestamp: float,
        params: dict | None = None,
    ) -> dict | None:
        """Send one frame to the worker, receive and decode the reply dict.

        Returns the raw reply dict on success. Returns ``None`` on any failure
        path (hang, crash, ZMQ error, unexpected exception). All failure paths
        funnel through :meth:`_kill_process` so the bridge cannot be left in a
        half-alive state.

        Args:
            rgb: ``(H, W, 3) uint8`` colour image.
            depth: Optional ``(H, W) float32`` depth image in metres. Detectors
                that do not consume depth (e.g. OWLv2) pass ``None``.
            timestamp: Simulation time in seconds (mirrors SLAM bridge).
            params: Optional per-frame backend parameters (score threshold,
                topk, etc.). Passed opaquely inside the msgpack header.
        """
        if not self._alive:
            return None

        # Crash detection: Popen has exited since last call.
        if self._process is not None and self._process.poll() is not None:
            logger.warning(
                "Detector subprocess exited with code %d",
                self._process.returncode,
            )
            self._cleanup()
            return None

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
            return None
        except zmq.ZMQError as exc:
            logger.error("Detector ZMQ error: %s", exc)
            self._kill_process()
            return None
        except Exception as exc:  # noqa: BLE001 — transport must never leak
            logger.error("Unexpected error in detector send_frame: %s", exc)
            self._kill_process()
            return None

    def shutdown(self) -> None:
        """Gracefully tear down the worker and release all resources."""
        self._kill_process()

    # ------------------------------------------------------------------
    # Internal teardown
    # ------------------------------------------------------------------

    def _kill_process(self) -> None:
        """Kill the worker subprocess and run :meth:`_cleanup`.

        Safe to call repeatedly and before :meth:`start`.
        """
        self._alive = False
        if self._process is not None:
            try:
                self._process.kill()
                self._process.wait(timeout=2)
            except Exception:  # noqa: BLE001 — cleanup must never raise
                pass
            self._process = None
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
