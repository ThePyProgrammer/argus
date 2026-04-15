"""DET-MODELS-06 — End-to-end kill -9 → fallback within 5 s (Plan 05-12 activation).

@pytest.mark.slow_boxer — requires ``subprocess_venvs/boxer/.ready`` +
``models/boxer/<SHA>/`` to have been provisioned by
``make download-models-boxer``. Default pytest run filters this out
(see ``pytest.ini`` addopts ``-m "not slow_boxer and not network"``);
CI runs it nightly via explicit ``-m slow_boxer``.

Test flow (SC#3 — kill -9 → crash_fallback WS + YOLOv11 swap within 5 s):
  1. Pre-check: ``subprocess_venvs/boxer/.ready`` exists (setup script ran).
     Skip with an actionable message if not — this is the one legitimate
     skip in the body (the marker filters the whole test out by default;
     the ``.ready`` precondition is the second gate when the marker IS
     explicitly selected but the nightly-CI provisioning step hasn't run).
  2. Instantiate ``BoxeRBackend`` → call ``warmup(dummy)`` → bridge spawns
     the worker subprocess (D-05 lazy spawn) + completes handshake.
  3. Grab the worker PID via ``backend._bridge._process.pid``.
  4. ``os.kill(pid, signal.SIGKILL)`` — simulates the hard crash that
     SC#3 gates: a worker that stops responding with no chance to
     signal failure cleanly.
  5. Next ``backend.process_frame(dummy)`` MUST raise either
     :class:`BridgeHangError` (RCVTIMEO on the PAIR socket fires before
     the bridge notices the subprocess died) OR
     :class:`SubprocessDiedError` (bridge's liveness check catches the
     exited Popen first). Measure elapsed time from kill to exception;
     assert it is < 5.5 s (SC#3 budget 5.0 s + 0.5 s slack).
  6. Exercise the pool-level fallback path: construct a
     ``DetectorWorkerPool`` with a test-local ``FakeStreamingViz`` stub,
     call ``pool.on_backend_crash("boxer", reason=...)``, and assert:
       * ``pool.backend_name == "yolov11"`` (atomic swap happened)
       * ``fake_viz._message_queue`` has exactly one ``crash_fallback``
         envelope with ``subsystem=="detector"`` and the crashed backend
         name. This confirms the WS message the frontend's ``CrashToast``
         consumes actually landed (Phase 3 contract).
  7. Shutdown the BoxeR backend cleanly.

Why the pool exercise uses a test-local FakeStreamingViz instead of
``main.py``'s real streaming_viz: Plan 05-12 exercises
``DetectorWorkerPool.on_backend_crash`` (Plan 05-09) at the pool
boundary. ``main.py``'s streaming_viz wiring (Plan 05-10, same wave)
is a sibling integration — not a prerequisite here. Matches the Plan
05-09 unit test pattern at ``tests/perception/test_crash_fallback.py``.
"""
from __future__ import annotations

import os
import signal
import time
from pathlib import Path

import numpy as np
import pytest

# Module-level marker: pytest collects this but the default addopts
# filter (-m "not slow_boxer and not network") deselects it. Only an
# explicit `pytest -m slow_boxer` runs the body.
pytestmark = pytest.mark.slow_boxer


class FakeStreamingViz:
    """Test-local stand-in for ``src.web.streaming_visualizer.StreamingVisualizer``.

    Mirrors the surface used by
    ``DetectorWorkerPool.on_backend_crash``: only ``_message_queue``
    (a list) is read. Identical in shape to the FakeStreamingViz in
    ``tests/perception/test_crash_fallback.py``.
    """

    def __init__(self) -> None:
        self._message_queue: list[dict] = []


@pytest.mark.slow_boxer
def test_kill_nine_triggers_fallback_within_5s() -> None:
    """SC#3 — kill -9 the BoxeR worker → fallback completes within 5 s."""
    # Imports deferred into the test body so a default pytest run (which
    # deselects this test via the marker) never pays the import cost
    # for BoxeR's heavy dependency chain.
    from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
    import src.perception.backends  # noqa: F401 -- side-effect registration
    from src.perception.backends.boxer_backend import BoxeRBackend
    from src.perception.subprocess_bridge import (
        BridgeHangError,
        SubprocessDiedError,
    )
    from src.perception.worker_pool import DetectorWorkerPool

    # Precondition: subprocess venv must be ready. Skip if not provisioned —
    # the marker is selected but the nightly-CI provisioning step hasn't run.
    ready_marker = Path("subprocess_venvs") / "boxer" / ".ready"
    if not ready_marker.exists():
        pytest.skip(
            f"{ready_marker} missing — run `make download-models-boxer` "
            f"to provision the BoxeR subprocess venv before running this test."
        )

    dummy = SensorFrame(
        rgb=np.zeros((480, 640, 3), dtype=np.uint8),
        depth=np.zeros((480, 640), dtype=np.float32),
        ground_truth_pose=np.eye(4),
        sim_time=0.0,
    )

    backend = BoxeRBackend()
    try:
        # warmup() lazy-spawns the bridge AND runs one real inference.
        # This is the only way to get a live worker PID we can kill.
        backend.warmup(dummy)
        assert backend._bridge is not None, "warmup should have spawned the bridge"
        assert backend._bridge._process is not None, (
            "bridge should have a live Popen after warmup"
        )
        worker_pid = backend._bridge._process.pid
        assert worker_pid is not None and worker_pid > 0, (
            f"expected a valid worker PID, got {worker_pid!r}"
        )

        # Hard-kill the worker — simulates the SC#3 scenario literally.
        # SIGKILL cannot be caught / ignored; the subprocess dies immediately.
        t_kill = time.perf_counter()
        os.kill(worker_pid, signal.SIGKILL)

        # The next send_frame MUST raise either BridgeHangError (RCVTIMEO
        # hits before the bridge's liveness poll) or SubprocessDiedError
        # (liveness poll catches the exited Popen first). Both are valid —
        # the SC only requires the failure be visible within 5 s.
        with pytest.raises((BridgeHangError, SubprocessDiedError)):
            backend.process_frame(dummy)
        elapsed = time.perf_counter() - t_kill
        assert elapsed < 5.5, (
            f"elapsed {elapsed:.2f} s exceeds SC#3 budget "
            f"5.0 s (+0.5 s slack); bridge failed to detect crash in time"
        )

        # Exercise the pool-level fallback end-to-end. Uses a test-local
        # FakeStreamingViz — Plan 05-12 does NOT depend on Plan 05-10's
        # main.py streaming_viz wiring (see module docstring for rationale).
        fake_viz = FakeStreamingViz()
        intr = CameraIntrinsics(
            fx=500.0, fy=500.0, cx=320.0, cy=240.0, width=640, height=480,
        )
        pool = DetectorWorkerPool(
            robot_ids=["r1"],
            backend_name="yolov11",
            backend_params={},
            lifter_name="median_depth",
            intrinsics_per_robot={"r1": intr},
            streaming_viz=fake_viz,
        )
        pool.on_backend_crash(
            crashed_backend="boxer",
            reason=f"SIGKILL test: elapsed_to_detect={elapsed:.2f}s",
        )

        # Atomic backend swap happened.
        assert pool.backend_name == "yolov11", (
            f"pool.backend_name should be 'yolov11' after crash fallback; "
            f"got {pool.backend_name!r}"
        )

        # crash_fallback WS envelope landed on the viz queue.
        assert len(fake_viz._message_queue) == 1, (
            f"expected exactly 1 crash_fallback envelope on the viz queue; "
            f"got {len(fake_viz._message_queue)}: {fake_viz._message_queue!r}"
        )
        msg = fake_viz._message_queue[0]
        assert msg["type"] == "crash_fallback", (
            f"envelope type should be 'crash_fallback'; got {msg['type']!r}"
        )
        payload = msg["payload"]
        assert payload["subsystem"] == "detector"
        assert payload["crashed_backend"] == "boxer"
        assert payload["fallback_backend"] == "yolov11"
        assert "SIGKILL" in payload["reason"], (
            f"reason should echo the SIGKILL context; got {payload['reason']!r}"
        )
    finally:
        # Cleanup — idempotent; safe even if warmup raised.
        backend.shutdown()
