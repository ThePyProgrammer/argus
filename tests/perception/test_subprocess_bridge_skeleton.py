"""Smoke tests for SubprocessDetectorBridge skeleton (Plan 02-06).

Plan 02-06 ships the class skeleton only. Real handshake semantics
(spawn echo worker, round-trip msgpack, timeout → kill, cleanup of IPC
file) are exercised by Plan 02-07's tests against scripts/echo_detector_worker.py.

These tests verify:
  - Module imports cleanly.
  - Class is NOT a subclass of SubprocessSLAMBridge (D-16 blast-radius isolation).
  - Default endpoint uses the distinct `ipc:///tmp/detector_bridge_<pid>_<id>`
    prefix (NOT the SLAM bridge's `ipc:///tmp/slam_bridge_` prefix).
  - HANG_TIMEOUT_MS is 5000 as fixed by must_haves/truths and D-17.
  - Construction sets `_alive` to False and exposes `alive`/`endpoint` properties.
  - send_frame is a short-circuit no-op when the bridge has not been started
    (no process, no context) — returns None without raising.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from src.perception.subprocess_bridge import SubprocessDetectorBridge
from src.slam.backends.subprocess_bridge import SubprocessSLAMBridge


def _make_bridge(**overrides) -> SubprocessDetectorBridge:
    defaults = {"binary_path": "/usr/bin/true", "hang_timeout_ms": 500}
    defaults.update(overrides)
    return SubprocessDetectorBridge(**defaults)


class TestD16ClassSeparation:
    """D-16: SubprocessDetectorBridge is a SEPARATE class, not a subclass."""

    def test_not_subclass_of_slam_bridge(self):
        assert not issubclass(SubprocessDetectorBridge, SubprocessSLAMBridge)

    def test_slam_bridge_not_subclass_of_detector_bridge(self):
        assert not issubclass(SubprocessSLAMBridge, SubprocessDetectorBridge)


class TestEndpointPattern:
    """D-16: endpoint prefix is `ipc:///tmp/detector_bridge_` — distinct from SLAM."""

    def test_default_endpoint_has_detector_prefix(self):
        bridge = _make_bridge()
        assert bridge.endpoint.startswith("ipc:///tmp/detector_bridge_")

    def test_default_endpoint_does_not_collide_with_slam_prefix(self):
        bridge = _make_bridge()
        assert "slam_bridge_" not in bridge.endpoint

    def test_default_endpoint_includes_pid_and_id(self):
        bridge = _make_bridge()
        pid = os.getpid()
        assert str(pid) in bridge.endpoint
        assert str(id(bridge)) in bridge.endpoint

    def test_two_instances_get_different_endpoints(self):
        b1 = _make_bridge()
        b2 = _make_bridge()
        assert b1.endpoint != b2.endpoint

    def test_ipc_endpoint_override_is_respected(self):
        override = "ipc:///tmp/detector_bridge_manual_test"
        bridge = _make_bridge(ipc_endpoint=override)
        assert bridge.endpoint == override


class TestClassConstants:
    """Transport invariants (D-17, must_haves/truths)."""

    def test_hang_timeout_ms_is_5000(self):
        assert SubprocessDetectorBridge.HANG_TIMEOUT_MS == 5000


class TestInitialState:
    """Construction should not start a process or bind a socket."""

    def test_alive_starts_false(self):
        bridge = _make_bridge()
        assert bridge.alive is False

    def test_endpoint_property_matches_init(self):
        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/detector_bridge_init_test")
        assert bridge.endpoint == "ipc:///tmp/detector_bridge_init_test"

    def test_send_frame_before_start_returns_none(self):
        bridge = _make_bridge()
        rgb = np.zeros((4, 4, 3), dtype=np.uint8)
        depth = np.zeros((4, 4), dtype=np.float32)
        assert bridge.send_frame(rgb, depth, timestamp=0.0) is None

    def test_shutdown_before_start_is_safe(self):
        bridge = _make_bridge()
        # Should not raise even though start() was never called.
        bridge.shutdown()
        assert bridge.alive is False


class TestAPISurface:
    """Mirrors SLAM bridge API (start/send_frame/shutdown/_kill_process/_cleanup)."""

    @pytest.mark.parametrize(
        "method_name", ["start", "send_frame", "shutdown", "_kill_process", "_cleanup"],
    )
    def test_method_exists(self, method_name):
        bridge = _make_bridge()
        assert callable(getattr(bridge, method_name))
