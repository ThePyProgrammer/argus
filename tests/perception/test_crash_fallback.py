"""DET-MODELS-06 — Crash fallback unit tests (Wave 0 skeleton, Plan 05-04).

Plan 05-05 (Wave 1) lands bridge typed exceptions (BridgeHangError, SubprocessDiedError).
Plan 05-09 (Wave 2) lands DetectorWorkerPool.on_backend_crash handler.
"""
from __future__ import annotations

import pytest


def test_bridge_hang_raises() -> None:
    """SubprocessDetectorBridge.send_frame raises BridgeHangError on RCVTIMEO (Plan 05-05)."""
    pytest.skip("Plan 05-05 (Wave 1) fills in: bridge.send_frame raises BridgeHangError when worker silent > 5s.")


def test_subprocess_died_raises() -> None:
    """SubprocessDetectorBridge.send_frame raises SubprocessDiedError when Popen exited (Plan 05-05)."""
    pytest.skip("Plan 05-05 (Wave 1) fills in: bridge.send_frame raises SubprocessDiedError after Popen.poll != None.")


def test_pool_on_backend_crash_emits_ws_message() -> None:
    """DetectorWorkerPool.on_backend_crash appends crash_fallback to streaming_viz._message_queue."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: message shape per RESEARCH D-03 + SLAM precedent.")


def test_pool_swaps_to_yolo() -> None:
    """on_backend_crash creates YOLOv11Backend, warms it, atomically swaps under _swap_lock."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: all workers' _detector is YOLOv11Backend instance after call.")


def test_pool_marks_crashed_backend_unavailable() -> None:
    """D-04 — on_backend_crash calls DetectorRegistry.set_available(name, False, reason=...)."""
    pytest.skip("Plan 05-09 (Wave 2) fills in: DetectorRegistry.list_backends() shows boxer available=False with reason.")
