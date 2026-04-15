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

from src.perception.subprocess_bridge import (
    BridgeHangError,
    SubprocessDetectorBridge,
    SubprocessDiedError,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ECHO_SCRIPT = str(REPO_ROOT / "scripts" / "echo_detector_worker.py")


# Mirror test_subprocess_bridge.py: ensure the worker script is executable and
# prepend the venv bin to PATH so its `#!/usr/bin/env python3` shebang resolves
# to the interpreter that has zmq/msgpack available.
os.chmod(ECHO_SCRIPT, 0o755)
_VENV_BIN = pathlib.Path(sys.executable).parent
if _VENV_BIN.is_dir():
    os.environ["PATH"] = f"{_VENV_BIN}{os.pathsep}{os.environ.get('PATH', '')}"


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


def test_pool_on_backend_crash_emits_ws_message() -> None:
    """DetectorWorkerPool.on_backend_crash appends crash_fallback to streaming_viz._message_queue."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: message shape per RESEARCH D-03 + SLAM precedent.")


def test_pool_swaps_to_yolo() -> None:
    """on_backend_crash creates YOLOv11Backend, warms it, atomically swaps under _swap_lock."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: all workers' _detector is YOLOv11Backend instance after call.")


def test_pool_marks_crashed_backend_unavailable() -> None:
    """D-04 — on_backend_crash calls DetectorRegistry.set_available(name, False, reason=...)."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: DetectorRegistry.list_backends() shows boxer available=False with reason.")
