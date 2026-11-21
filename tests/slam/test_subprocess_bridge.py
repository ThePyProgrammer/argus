"""Tests for SubprocessSLAMBridge -- ZMQ IPC communication with C++ SLAM backends.

Uses mock subprocess + real ZMQ loopback TCP sockets where possible to verify
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
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
        try:
            bridge.start()

            assert bridge.alive is True
            assert bridge._socket is not None
            assert bridge._ctx is not None
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            assert "--zmq" in cmd
            assert bridge.endpoint in cmd
            assert "*" not in bridge.endpoint
        finally:
            bridge.shutdown()


class TestSendFrameMultipart:
    """Test 2: send_frame() packs msgpack header + raw numpy bytes in multipart."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_multipart_structure(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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
    @pytest.mark.skipif(not zmq.has("ipc"), reason="ZeroMQ IPC unavailable")
    def test_kill_cleans_socket(self, mock_popen):
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        sock_path = f"/tmp/test_bridge_kill_{os.getpid()}"
        bridge = _make_bridge(ipc_endpoint=f"ipc://{sock_path}")
        try:
            bridge.start()
            assert bridge.alive is True
            # ZMQ bind creates the IPC socket file
            assert os.path.exists(sock_path)

            bridge._kill_process()

            assert bridge.alive is False
            mock_proc.kill.assert_called_once()
            assert not os.path.exists(sock_path)
        finally:
            bridge.shutdown()
            # Ensure cleanup even if test fails
            if os.path.exists(sock_path):
                os.unlink(sock_path)


class TestUniqueEndpoint:
    """Test 7: IPC endpoint uses unique path with PID to prevent address collisions."""

    @patch("src.slam.backends.subprocess_bridge.zmq.has", return_value=True)
    def test_default_endpoint_contains_pid(self, _has):
        bridge = _make_bridge()
        assert str(os.getpid()) in bridge.endpoint
        assert bridge.endpoint.startswith("ipc:///tmp/slam_bridge_")

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_two_bridges_have_different_endpoints(self, mock_popen):
        a = _make_bridge()
        b = _make_bridge()
        try:
            a.start()
            b.start()
            assert a.endpoint != b.endpoint
        finally:
            a.shutdown()
            b.shutdown()


class TestIMUPacking:
    """Test 8: send_frame() correctly packs IMU readings when provided."""

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_imu_packed_as_part3(self, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
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

        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
        bridge.start()
        assert bridge.alive is True

        bridge.shutdown()

        assert bridge.alive is False
        assert bridge._socket is None
        assert bridge._ctx is None
        assert bridge._process is None
        mock_proc.kill.assert_called_once()

class TestPortableTransport:
    @patch("src.slam.backends.subprocess_bridge.zmq.has", return_value=False)
    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_default_falls_back_to_bound_loopback(self, popen, _has):
        bridge = _make_bridge(args=["--config", "calibration.yaml"])
        assert bridge.endpoint == "tcp://127.0.0.1:*"
        try:
            bridge.start()
            assert bridge.endpoint.startswith("tcp://127.0.0.1:")
            assert "*" not in bridge.endpoint
            assert popen.call_args.args[0] == [
                "/usr/bin/true", "--zmq", bridge.endpoint,
                "--config", "calibration.yaml",
            ]
        finally:
            bridge.shutdown()

    @patch("src.slam.backends.subprocess_bridge.zmq.has", return_value=False)
    @patch("src.slam.backends.subprocess_bridge.zmq.Context")
    def test_explicit_unsupported_ipc_is_actionable(self, context, _has):
        bridge = _make_bridge(ipc_endpoint="ipc:///tmp/explicit_slam")
        with pytest.raises(ValueError, match="tcp://127.0.0.1"):
            bridge.start()
        context.assert_not_called()
        assert not bridge.alive

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_bind_failure_closes_resources(self, popen):
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
        context = zmq.Context()
        socket = context.socket(zmq.PAIR)
        with patch("src.slam.backends.subprocess_bridge.zmq.Context", return_value=context), \
             patch.object(context, "socket", return_value=socket), \
             patch.object(socket, "bind", side_effect=zmq.ZMQError("bind failed")):
            with pytest.raises(zmq.ZMQError, match="bind failed"):
                bridge.start()
        assert socket.closed and context.closed
        assert bridge._socket is None and bridge._ctx is None
        assert not bridge.alive
        popen.assert_not_called()

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen", side_effect=OSError("spawn failed"))
    def test_spawn_failure_closes_resources(self, popen):
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*")
        context = zmq.Context()
        socket = context.socket(zmq.PAIR)
        with patch("src.slam.backends.subprocess_bridge.zmq.Context", return_value=context), \
             patch.object(context, "socket", return_value=socket):
            with pytest.raises(OSError, match="spawn failed"):
                bridge.start()
        assert socket.closed and context.closed
        assert bridge._socket is None and bridge._ctx is None
        assert not bridge.alive
        bridge.shutdown()

    @pytest.mark.skipif(not zmq.has("ipc"), reason="ZeroMQ IPC unavailable")
    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen", side_effect=OSError("spawn failed"))
    def test_spawn_failure_removes_ipc_file(self, popen):
        bridge = _make_bridge()
        with pytest.raises(OSError, match="spawn failed"):
            bridge.start()
        assert not os.path.exists(bridge.endpoint.removeprefix("ipc://"))
        assert bridge._socket is None and bridge._ctx is None

    def test_failed_bind_does_not_unlink_unowned_ipc_file(self, tmp_path):
        path = tmp_path / "unowned.sock"
        path.write_text("owned by another process")
        bridge = _make_bridge(ipc_endpoint=f"ipc://{path}")
        with patch("src.slam.backends.subprocess_bridge.zmq.has", return_value=True), \
             patch("zmq.Socket.bind", side_effect=zmq.ZMQError("bind failed")):
            with pytest.raises(zmq.ZMQError):
                bridge.start()
        bridge.shutdown()
        assert path.read_text() == "owned by another process"

    def test_tcp_round_trip_with_real_worker(self):
        import sys
        worker = '''
import sys, msgpack, numpy as np, zmq
ctx = zmq.Context()
sock = ctx.socket(zmq.PAIR)
sock.setsockopt(zmq.RCVTIMEO, 5000)
sock.connect(sys.argv[1])
parts = sock.recv_multipart()
header = msgpack.unpackb(parts[0])
assert header['rgb_shape'] == [2, 3, 3]
assert len(parts[1]) == 18 and len(parts[2]) == 24
sock.send(msgpack.packb({'pose': np.eye(4).tobytes(), 'status': 'ok', 'time_ms': 2.0}))
sock.close()
ctx.term()
'''
        real_popen = subprocess.Popen
        def spawn(cmd, **kwargs):
            return real_popen([sys.executable, "-c", worker, cmd[2]], **kwargs)
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*", hang_timeout_ms=5000)
        try:
            with patch("src.slam.backends.subprocess_bridge.subprocess.Popen", side_effect=spawn):
                bridge.start()
            result = bridge.send_frame(
                np.zeros((2, 3, 3), dtype=np.uint8),
                np.ones((2, 3), dtype=np.float32), 1.0,
            )
            assert result is not None
            np.testing.assert_array_equal(result.pose, np.eye(4))
            assert result.tracking_status == TrackingStatus.OK
            assert bridge._process.wait(timeout=5) == 0
        finally:
            bridge.shutdown()

    @patch("src.slam.backends.subprocess_bridge.subprocess.Popen")
    def test_unconnected_worker_times_out_on_send(self, popen):
        popen.return_value.poll.return_value = None
        bridge = _make_bridge(ipc_endpoint="tcp://127.0.0.1:*", hang_timeout_ms=50)
        try:
            bridge.start()
            assert bridge.send_frame(np.zeros((1, 1, 3)), np.zeros((1, 1)), 0) is None
            assert not bridge.alive
            popen.return_value.kill.assert_called_once()
        finally:
            bridge.shutdown()
