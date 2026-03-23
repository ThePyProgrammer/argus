"""Tests for SubprocessSLAMBridge -- ZMQ IPC communication with C++ SLAM backends.

Uses mock subprocess + real ZMQ inproc sockets where possible to verify
the wire protocol (msgpack header + raw numpy multipart).
"""

import os
import subprocess
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import msgpack
import numpy as np
import pytest
import zmq

from src.slam.backends.subprocess_bridge import SubprocessSLAMBridge
from src.slam.protocol import SLAMResult, TrackingStatus


@dataclass
class _FakeIMU:
    """Minimal IMU reading for testing (duck-typed, no dependency on Plan 01)."""
    timestamp: float
    accel: np.ndarray
    gyro: np.ndarray


def _make_bridge(**kwargs) -> SubprocessSLAMBridge:
    """Create bridge with defaults suitable for testing."""
    defaults = {
        "binary_path": "/usr/bin/true",
        "hang_timeout_ms": 500,  # short for tests
    }
    defaults.update(kwargs)
    return SubprocessSLAMBridge(**defaults)


def _make_reply(pose: np.ndarray | None = None, status: str = "ok", time_ms: float = 1.5) -> bytes:
    """Create a msgpack-encoded reply matching the C++ wire protocol."""
    if pose is None:
        pose = np.eye(4, dtype=np.float64)
    return msgpack.packb({
        b"pose": pose.tobytes(),
        b"status": status.encode(),
        b"time_ms": time_ms,
    })


class TestStartProcess:
    """Test 1: start() creates ZMQ PAIR socket and spawns subprocess."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_start_creates_zmq_pair_and_spawns(self, mock_popen):
        mock_popen.return_value = MagicMock()
        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_start")
        try:
            bridge.start()

            assert bridge.alive is True
            assert bridge._socket is not None
            assert bridge._ctx is not None
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert "--zmq" in cmd
            assert "ipc:///tmp/test_bridge_start" in cmd
        finally:
            bridge.shutdown()


class TestSendFrameMultipart:
    """Test 2: send_frame() packs msgpack header + raw numpy bytes in multipart."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_multipart_structure(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_mp")
        try:
            bridge.start()

            # Capture what gets sent
            sent_parts = []
            bridge._socket.send_multipart = MagicMock(side_effect=lambda p: sent_parts.extend([p]))
            bridge._socket.recv = MagicMock(return_value=_make_reply())

            rgb = np.zeros((480, 640, 3), dtype=np.uint8)
            depth = np.ones((480, 640), dtype=np.float32)

            bridge.send_frame(rgb, depth, timestamp=1.0)

            assert len(sent_parts) == 1  # one call with list of parts
            parts = sent_parts[0]
            assert len(parts) == 3  # header, rgb, depth (no IMU)

            # Verify header
            header = msgpack.unpackb(parts[0])
            assert header["ts"] == 1.0
            assert header["rgb_shape"] == [480, 640, 3]
            assert header["rgb_dtype"] == "uint8"
            assert header["depth_shape"] == [480, 640]
            assert header["depth_dtype"] == "float32"
            assert header["n_imu"] == 0
        finally:
            bridge.shutdown()


class TestSendFrameResult:
    """Test 3: send_frame() returns SLAMResult with correct pose, status, metrics."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_returns_slam_result(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        expected_pose = np.diag([1.0, 2.0, 3.0, 1.0])
        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_result")
        try:
            bridge.start()
            bridge._socket.send_multipart = MagicMock()
            bridge._socket.recv = MagicMock(
                return_value=_make_reply(pose=expected_pose, status="ok", time_ms=4.2)
            )

            rgb = np.zeros((10, 10, 3), dtype=np.uint8)
            depth = np.zeros((10, 10), dtype=np.float32)

            result = bridge.send_frame(rgb, depth, timestamp=0.5)

            assert isinstance(result, SLAMResult)
            np.testing.assert_array_almost_equal(result.pose, expected_pose)
            assert result.tracking_status == TrackingStatus.OK
            assert result.metrics["processing_time_ms"] == 4.2
            assert result.points.shape == (0, 3)
        finally:
            bridge.shutdown()


class TestTimeout:
    """Test 4: send_frame() returns None when subprocess times out (zmq.Again)."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_timeout_returns_none(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_timeout")
        try:
            bridge.start()
            bridge._socket.send_multipart = MagicMock()
            bridge._socket.recv = MagicMock(side_effect=zmq.Again())

            rgb = np.zeros((10, 10, 3), dtype=np.uint8)
            depth = np.zeros((10, 10), dtype=np.float32)

            result = bridge.send_frame(rgb, depth, timestamp=0.1)

            assert result is None
            assert bridge.alive is False
            mock_proc.kill.assert_called_once()
        finally:
            bridge.shutdown()


class TestZMQError:
    """Test 5: send_frame() returns None and kills process on ZMQError."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_zmq_error_returns_none(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_zmqerr")
        try:
            bridge.start()
            bridge._socket.send_multipart = MagicMock(
                side_effect=zmq.ZMQError(msg="test error")
            )

            rgb = np.zeros((10, 10, 3), dtype=np.uint8)
            depth = np.zeros((10, 10), dtype=np.float32)

            result = bridge.send_frame(rgb, depth, timestamp=0.1)

            assert result is None
            assert bridge.alive is False
        finally:
            bridge.shutdown()


class TestKillProcess:
    """Test 6: _kill_process() terminates subprocess and cleans up IPC socket file."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_kill_cleans_socket(self, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        sock_path = "/tmp/test_bridge_kill_sock"
        bridge = _make_bridge(ipc_endpoint=f"ipc://{sock_path}")
        try:
            bridge.start()
            assert bridge.alive is True

            # Create a fake socket file
            with open(sock_path, "w") as f:
                f.write("")

            bridge._kill_process()

            assert bridge.alive is False
            mock_proc.kill.assert_called_once()
            assert not os.path.exists(sock_path)
        finally:
            bridge.shutdown()


class TestUniqueEndpoint:
    """Test 7: IPC endpoint uses unique path with PID to prevent address collisions."""

    def test_default_endpoint_contains_pid(self):
        bridge = _make_bridge()
        assert str(os.getpid()) in bridge.endpoint
        assert bridge.endpoint.startswith("ipc:///tmp/slam_bridge_")

    def test_two_bridges_have_different_endpoints(self):
        a = _make_bridge()
        b = _make_bridge()
        assert a.endpoint != b.endpoint


class TestIMUPacking:
    """Test 8: send_frame() correctly packs IMU readings when provided."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_imu_packed_as_part3(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_imu")
        try:
            bridge.start()

            sent_parts = []
            bridge._socket.send_multipart = MagicMock(side_effect=lambda p: sent_parts.extend([p]))
            bridge._socket.recv = MagicMock(return_value=_make_reply())

            rgb = np.zeros((10, 10, 3), dtype=np.uint8)
            depth = np.zeros((10, 10), dtype=np.float32)
            imu = [
                _FakeIMU(timestamp=0.001, accel=np.array([0, 0, 9.81]), gyro=np.array([0.1, 0.2, 0.3])),
                _FakeIMU(timestamp=0.002, accel=np.array([0, 0, 9.82]), gyro=np.array([0.4, 0.5, 0.6])),
            ]

            bridge.send_frame(rgb, depth, timestamp=1.0, imu_readings=imu)

            parts = sent_parts[0]
            assert len(parts) == 4  # header, rgb, depth, imu

            header = msgpack.unpackb(parts[0])
            assert header["n_imu"] == 2

            # Verify IMU bytes: 2 readings x 7 floats = 14 float64
            imu_arr = np.frombuffer(parts[3], dtype=np.float64).reshape(2, 7)
            assert imu_arr[0, 0] == pytest.approx(0.001)  # timestamp
            assert imu_arr[0, 3] == pytest.approx(9.81)   # accel z
            assert imu_arr[1, 4] == pytest.approx(0.4)    # gyro x of 2nd reading
        finally:
            bridge.shutdown()


class TestNoIMU:
    """Test 9: send_frame() omits IMU part when imu_readings is None or empty."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_no_imu_none(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_noimu1")
        try:
            bridge.start()

            sent_parts = []
            bridge._socket.send_multipart = MagicMock(side_effect=lambda p: sent_parts.extend([p]))
            bridge._socket.recv = MagicMock(return_value=_make_reply())

            rgb = np.zeros((10, 10, 3), dtype=np.uint8)
            depth = np.zeros((10, 10), dtype=np.float32)

            bridge.send_frame(rgb, depth, timestamp=1.0, imu_readings=None)
            assert len(sent_parts[0]) == 3

            sent_parts.clear()
            bridge._alive = True  # reset for second call
            bridge.send_frame(rgb, depth, timestamp=1.0, imu_readings=[])
            assert len(sent_parts[0]) == 3
        finally:
            bridge.shutdown()


class TestShutdown:
    """Test 10: shutdown() cleans up ZMQ context, socket, and subprocess."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_shutdown_cleans_everything(self, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/test_bridge_shutdown")
        bridge.start()
        assert bridge.alive is True

        bridge.shutdown()

        assert bridge.alive is False
        assert bridge._socket is None
        assert bridge._ctx is None
        assert bridge._process is None
        mock_proc.kill.assert_called_once()
