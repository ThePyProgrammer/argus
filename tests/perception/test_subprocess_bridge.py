"""D-17 handshake tests for SubprocessDetectorBridge.

Drives the bridge against ``scripts/echo_detector_worker.py`` — the permanent
repo helper from Plan 02-07 Task 1 (D-15). These tests cover the full
transport surface that Phase 5 (DET-MODELS-03) will inherit when it composes
this bridge into a real BoxeR backend:

  (a) spawn echo worker subprocess via SubprocessDetectorBridge.start()
  (b) PAIR bind + multipart send_frame([header, rgb_bytes, ...])
  (c) receive echo reply within HANG_TIMEOUT_MS (5 s)
  (d) msgpack round-trip fidelity on header fields the worker reads
  (e) kill echo worker externally → next send_frame raises zmq.Again →
      returns None within ~5 s and ``_alive`` flips to False
  (f) _kill_process cleanup unlinks /tmp IPC socket file + closes zmq ctx

Plan 02-06 already shipped smoke-level skeleton tests in
``test_subprocess_bridge_skeleton.py`` (class separation, endpoint prefix,
pre-start short-circuit). This file exercises the live transport.

Timing: the 0.3 s sleeps after ``start()`` give the Python echo worker time
to ``import msgpack`` / ``import zmq`` and ``connect()`` the PAIR socket.
Bump to 0.5 s on notoriously slow CI if flakes appear; document here.
"""

from __future__ import annotations

import os
import pathlib
import signal
import sys
import time

import numpy as np
import pytest

from src.perception.subprocess_bridge import (
    BridgeHangError,
    SubprocessDetectorBridge,
    SubprocessDiedError,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ECHO_SCRIPT = str(REPO_ROOT / "scripts" / "echo_detector_worker.py")


# Ensure the echo worker is executable at import time — belt-and-suspenders
# with Task 1's chmod +x. Without this the bridge's Popen([ECHO_SCRIPT, ...])
# path (shebang-based invocation) would fail on hosts where the checkout
# stripped the mode bit.
os.chmod(ECHO_SCRIPT, 0o755)


# The bridge Popens the echo worker via its `#!/usr/bin/env python3` shebang.
# In a uv-managed checkout pytest runs under .venv/bin/python3 but the Popen
# child inherits the parent's PATH, and the first python3 on PATH may be the
# system interpreter (no zmq/msgpack). Prepend the venv's bin/ so the
# shebang resolves to the interpreter that actually has the test-time deps.
# This is a test-infrastructure concern — production deployments ship the
# worker alongside the venv on PATH already.
_VENV_BIN = pathlib.Path(sys.executable).parent
if _VENV_BIN.is_dir():
    os.environ["PATH"] = f"{_VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}"


def _make_bridge(
    ipc_endpoint: str | None = None,
    sleep_ms: int = 0,
) -> SubprocessDetectorBridge:
    """Build a bridge that will Popen the echo worker via its shebang.

    The bridge constructs the cmdline as ``[binary_path, "--zmq", endpoint,
    *args]`` (see ``SubprocessDetectorBridge.start``). Passing
    ``binary_path=ECHO_SCRIPT`` lets the shebang handle Python invocation —
    much cleaner than wedging ``sys.executable`` + a script-path argv, which
    would misorder the ``--zmq`` flag relative to the script.
    """
    extra_args = ["--sleep-ms", str(sleep_ms)] if sleep_ms else []
    return SubprocessDetectorBridge(
        binary_path=ECHO_SCRIPT,
        args=extra_args,
        ipc_endpoint=ipc_endpoint,
    )


def _dummy_frame() -> tuple[np.ndarray, np.ndarray]:
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    return rgb, depth


@pytest.fixture
def bridge():
    """Yield a bridge and guarantee teardown (Pitfall 3: /tmp socket leaks)."""
    b = _make_bridge()
    try:
        yield b
    finally:
        try:
            b.shutdown()
        except Exception:  # noqa: BLE001 — teardown must never mask test failures
            pass


# ---------------------------------------------------------------------------
# D-16: endpoint prefix isolation (cheapest test; runs without subprocess).
# ---------------------------------------------------------------------------


def test_endpoint_prefix_distinct_from_slam():
    """D-16: detector bridge endpoint namespace must NOT collide with SLAM."""
    b = SubprocessDetectorBridge(binary_path="/bin/true")
    assert "detector_bridge_" in b.endpoint
    assert "slam_bridge_" not in b.endpoint


# ---------------------------------------------------------------------------
# D-17 handshake surface: spawn → send → recv.
# ---------------------------------------------------------------------------


def test_spawn_send_recv_round_trip(bridge):
    """Minimum viable handshake: Popen worker, send 1 frame, get reply dict."""
    bridge.start()
    time.sleep(0.3)  # echo worker imports msgpack+zmq and connect()s
    rgb, depth = _dummy_frame()
    reply = bridge.send_frame(rgb, depth, timestamp=1.0)
    assert reply is not None, "echo worker failed to reply within HANG_TIMEOUT_MS"
    # raw=False decodes str keys, so we assert against str keys.
    assert set(reply.keys()) >= {
        "ts",
        "inference_ms",
        "n_det",
        "classes",
        "scores",
        "bboxes",
    }
    assert reply["n_det"] == 0
    assert reply["classes"] == []
    assert reply["scores"] == []
    assert reply["bboxes"] == []


def test_msgpack_header_fidelity(bridge):
    """Round-trip: worker reads header['ts'] and echoes it — must match exactly."""
    bridge.start()
    time.sleep(0.3)
    rgb, depth = _dummy_frame()
    reply = bridge.send_frame(
        rgb, depth, timestamp=7.5, params={"confidence": 0.7}
    )
    assert reply is not None
    assert abs(reply["ts"] - 7.5) < 1e-9, (
        f"msgpack round-trip altered ts: sent 7.5, got {reply['ts']!r}"
    )


# ---------------------------------------------------------------------------
# D-17 slow-backend path: --sleep-ms simulation still replies before timeout.
# ---------------------------------------------------------------------------


def test_slow_backend_still_returns_before_timeout():
    """--sleep-ms 200 simulates a slow backend — must return well under 5 s."""
    b = _make_bridge(sleep_ms=200)
    try:
        b.start()
        time.sleep(0.3)
        rgb, depth = _dummy_frame()
        t0 = time.monotonic()
        reply = b.send_frame(rgb, depth, timestamp=2.0)
        elapsed = time.monotonic() - t0
        assert reply is not None
        # 200 ms backend + overhead ≪ 5 s HANG_TIMEOUT_MS
        assert elapsed < 1.0, f"slow-backend path took {elapsed:.3f}s (>1s)"
        # Worker echoes the configured sleep_ms back as inference_ms.
        assert abs(reply["inference_ms"] - 200.0) < 1e-6
    finally:
        b.shutdown()


# ---------------------------------------------------------------------------
# D-17 watchdog: external kill → next send returns None → _alive flips False.
# ---------------------------------------------------------------------------


def test_kill_triggers_none_reply_within_timeout(bridge):
    """SIGKILL the worker mid-session; next send_frame must NOT hang forever."""
    bridge.start()
    time.sleep(0.3)
    rgb, depth = _dummy_frame()

    # Sanity: first send round-trips OK.
    assert bridge.send_frame(rgb, depth, timestamp=1.0) is not None

    # Kill the worker subprocess out from under the bridge.
    assert bridge._process is not None  # fixture started it
    worker_pid = bridge._process.pid
    os.kill(worker_pid, signal.SIGKILL)
    # Give the kernel time to deliver the signal + Popen to observe the exit.
    time.sleep(0.3)

    # Next send: Plan 05-05 flipped the return-None failure paths to typed
    # exceptions. Either the crash-detection (Popen.poll()) path raises
    # SubprocessDiedError immediately, OR zmq.Again-after-kill bubbles up as
    # SubprocessDiedError within HANG_TIMEOUT_MS. Either way the bridge MUST
    # NOT hang past HANG_TIMEOUT_MS + modest slack and MUST NOT return a dict.
    t0 = time.monotonic()
    with pytest.raises((SubprocessDiedError, BridgeHangError)):
        bridge.send_frame(rgb, depth, timestamp=2.0)
    elapsed = time.monotonic() - t0
    assert elapsed < bridge.HANG_TIMEOUT_MS / 1000.0 + 1.0, (
        f"bridge hung {elapsed:.2f}s after worker kill "
        f"(expected ≤{bridge.HANG_TIMEOUT_MS / 1000.0 + 1.0:.1f}s)"
    )
    assert bridge.alive is False, "bridge._alive did not flip False after kill"


# ---------------------------------------------------------------------------
# D-17 cleanup: /tmp IPC socket file MUST NOT leak after shutdown (Pitfall 3).
# ---------------------------------------------------------------------------


def test_shutdown_cleans_up_ipc_socket_file():
    """After bridge.shutdown(), the /tmp/detector_bridge_* file is gone."""
    endpoint = (
        f"ipc:///tmp/detector_bridge_test_{os.getpid()}_{time.time_ns()}"
    )
    sock_path = endpoint.replace("ipc://", "", 1)
    assert not os.path.exists(sock_path), "stale socket file from a previous run"

    b = _make_bridge(ipc_endpoint=endpoint)
    try:
        b.start()
        time.sleep(0.3)
        assert os.path.exists(sock_path), (
            "IPC socket file should exist while bridge is alive "
            f"(endpoint={endpoint})"
        )
    finally:
        b.shutdown()

    assert not os.path.exists(sock_path), (
        f"IPC socket file leaked at {sock_path} after shutdown — "
        "_cleanup() failed to unlink (D-17 Pitfall 3)"
    )
    # Bridge must also report dead.
    assert b.alive is False


def test_shutdown_closes_context_and_socket_handles():
    """_kill_process → _cleanup nulls the socket + ctx references (no leaked fds)."""
    b = _make_bridge()
    b.start()
    time.sleep(0.3)
    # Sanity: socket and ctx are live handles after start().
    assert b._socket is not None
    assert b._ctx is not None
    b.shutdown()
    # After shutdown the bridge drops its references so GC can finalize.
    assert b._socket is None, "_cleanup() did not null the socket reference"
    assert b._ctx is None, "_cleanup() did not null the zmq.Context reference"
    assert b._process is None, "_kill_process() did not null the Popen reference"


# ---------------------------------------------------------------------------
# Plan 05-05: typed exceptions + handshake + stdout drain thread.
# ---------------------------------------------------------------------------


def test_send_frame_before_start_raises_subprocess_died():
    """Plan 05-05: was ``return None`` → now raises SubprocessDiedError."""
    b = _make_bridge()
    rgb, depth = _dummy_frame()
    with pytest.raises(SubprocessDiedError):
        b.send_frame(rgb, depth, timestamp=0.0)


def test_wait_for_handshake_returns_on_socket_ready(bridge):
    """Open Risk #3: wait_for_handshake returns without raising when worker connects."""
    bridge.start()
    # wait_for_handshake must wait long enough for the echo worker to import
    # msgpack+zmq and call connect() on the PAIR socket.
    bridge.wait_for_handshake(timeout_s=10.0)
    # After a successful handshake, send_frame should round-trip normally.
    rgb, depth = _dummy_frame()
    reply = bridge.send_frame(rgb, depth, timestamp=0.0)
    assert reply is not None


def test_wait_for_handshake_raises_on_dead_worker():
    """If the worker Popen has already exited, wait_for_handshake raises SubprocessDiedError."""
    # Spawn a worker that exits immediately (--zmq missing → argparse error → exit 2).
    b = SubprocessDetectorBridge(
        binary_path="/bin/false",  # exits 1 immediately; bridge will observe poll()!=None
        hang_timeout_ms=500,
    )
    try:
        b.start()
        # Give the kernel a moment to deliver the exit to Popen.
        time.sleep(0.3)
        with pytest.raises(SubprocessDiedError):
            b.wait_for_handshake(timeout_s=2.0)
    finally:
        b.shutdown()


def test_stdout_drain_does_not_block_on_verbose_worker(tmp_path):
    """T-5-05: Popen.PIPE stdout DoS mitigated by background drain thread.

    Spawn a worker that writes a burst of stdout lines interleaved with replies.
    Without the drain thread, stdout PIPE buffer (~64 KB) would fill and the
    worker would block on write() → no reply → BridgeHangError. With the drain
    thread reading in the background, the bridge keeps receiving replies.
    """
    # Craft a chatty worker that mirrors echo_detector_worker but also spams
    # stdout between replies.
    chatty = tmp_path / "chatty_worker.py"
    chatty.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, sys, msgpack, zmq\n"
        "ap = argparse.ArgumentParser()\n"
        "ap.add_argument('--zmq', dest='zmq_endpoint', required=True)\n"
        "args = ap.parse_args()\n"
        "ctx = zmq.Context(); sock = ctx.socket(zmq.PAIR); sock.connect(args.zmq_endpoint)\n"
        "try:\n"
        "    while True:\n"
        "        parts = sock.recv_multipart()\n"
        "        if not parts: continue\n"
        "        header = msgpack.unpackb(parts[0], raw=False)\n"
        "        # Spam ~8 KB of stdout before replying — cumulatively exceeds\n"
        "        # PIPE buffer after a few frames if bridge isn't draining.\n"
        "        for i in range(128):\n"
        "            print('chatty-log-line-' + 'x'*50, flush=True)\n"
        "        reply = msgpack.packb({'ts': float(header.get('ts', 0.0)),\n"
        "                               'inference_ms': 0.0, 'n_det': 0,\n"
        "                               'classes': [], 'scores': [], 'bboxes': []})\n"
        "        sock.send(reply)\n"
        "except (KeyboardInterrupt, zmq.ContextTerminated):\n"
        "    pass\n"
    )
    chatty.chmod(0o755)

    b = SubprocessDetectorBridge(binary_path=str(chatty))
    try:
        b.start()
        time.sleep(0.3)
        rgb, depth = _dummy_frame()
        # Run enough frames that the PIPE would fill without a drain.
        for i in range(10):
            reply = b.send_frame(rgb, depth, timestamp=float(i))
            assert reply is not None, (
                f"frame {i} hung — drain thread likely not draining stdout"
            )
    finally:
        b.shutdown()
