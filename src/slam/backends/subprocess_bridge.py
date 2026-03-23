"""Generic subprocess bridge for C++ SLAM backends via ZMQ IPC.

Spawns a C++ binary, communicates via ZMQ PAIR socket with msgpack
headers and raw numpy byte arrays. Handles crash detection (process
exit), hang detection (5s timeout), and IPC socket cleanup.

Concrete backends (OpenVINS, SVO Pro, DSO) inherit this and provide
binary_path, config_path, and optional coordinate transforms.
"""

import logging
import os
import subprocess

import msgpack
import numpy as np
import zmq

from src.slam.protocol import SLAMResult, TrackingStatus

logger = logging.getLogger(__name__)


class SubprocessSLAMBridge:
    """Generic subprocess wrapper for C++ SLAM backends.

    Implements frame send/receive over ZMQ IPC. NOT a SLAMProtocol
    itself -- concrete backends (OpenVINSBackend, SVOProBackend)
    compose this bridge and implement SLAMProtocol on top.
    """

    HANG_TIMEOUT_MS = 5000  # 5 seconds per user decision

    def __init__(
        self,
        binary_path: str,
        args: list[str] | None = None,
        ipc_endpoint: str | None = None,
        hang_timeout_ms: int | None = None,
    ):
        self._binary = binary_path
        self._args = args or []
        # Unique endpoint per instance to avoid collisions
        self._endpoint = ipc_endpoint or f"ipc:///tmp/slam_bridge_{os.getpid()}_{id(self)}"
        self._timeout = hang_timeout_ms or self.HANG_TIMEOUT_MS
        self._process: subprocess.Popen | None = None
        self._ctx: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._alive = False

    @property
    def alive(self) -> bool:
        """Whether the subprocess bridge is running."""
        return self._alive

    @property
    def endpoint(self) -> str:
        """ZMQ IPC endpoint string."""
        return self._endpoint

    def start(self) -> None:
        """Spawn the C++ subprocess and bind the ZMQ socket."""
        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.PAIR)
        self._socket.setsockopt(zmq.RCVTIMEO, self._timeout)
        self._socket.setsockopt(zmq.LINGER, 0)
        self._socket.bind(self._endpoint)

        cmd = [self._binary, "--zmq", self._endpoint] + self._args
        logger.info("Spawning subprocess: %s", " ".join(cmd))
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._alive = True

    def send_frame(
        self,
        rgb: np.ndarray,
        depth: np.ndarray,
        timestamp: float,
        imu_readings: list | None = None,
    ) -> SLAMResult | None:
        """Send frame to subprocess, receive pose back.

        Returns SLAMResult on success, None on crash/timeout.
        Caller (concrete backend) should fall back to ICP on None.

        Args:
            rgb: (H, W, 3) uint8 color image.
            depth: (H, W) float32 depth image in meters.
            timestamp: Simulation time in seconds.
            imu_readings: Optional list of IMU readings. Each must have
                timestamp (float), accel (ndarray(3,)), gyro (ndarray(3,))
                attributes (duck-typed, works with any IMUReading-like class).
        """
        if not self._alive:
            return None

        # Check if process has exited
        if self._process and self._process.poll() is not None:
            logger.warning("Subprocess exited with code %d", self._process.returncode)
            self._cleanup()
            return None

        try:
            # Build header
            header = msgpack.packb({
                "ts": timestamp,
                "rgb_shape": list(rgb.shape),
                "rgb_dtype": str(rgb.dtype),
                "depth_shape": list(depth.shape),
                "depth_dtype": str(depth.dtype),
                "n_imu": len(imu_readings) if imu_readings else 0,
            })

            # Multipart: header, rgb bytes, depth bytes, [imu bytes]
            parts = [header, rgb.tobytes(), depth.tobytes()]
            if imu_readings:
                imu_array = np.array(
                    [(r.timestamp, *r.accel, *r.gyro) for r in imu_readings],
                    dtype=np.float64,
                )
                parts.append(imu_array.tobytes())

            self._socket.send_multipart(parts)

            # Receive response
            reply = self._socket.recv()
            result_data = msgpack.unpackb(reply, raw=True)

            pose = np.frombuffer(
                result_data[b"pose"], dtype=np.float64
            ).reshape(4, 4).copy()
            status_str = result_data[b"status"]
            if isinstance(status_str, bytes):
                status_str = status_str.decode()
            status = TrackingStatus(status_str)

            return SLAMResult(
                pose=pose,
                points=np.empty((0, 3), dtype=np.float64),
                colors=np.empty((0, 3), dtype=np.float64),
                metrics={"processing_time_ms": result_data.get(b"time_ms", 0)},
                tracking_status=status,
            )

        except zmq.Again:
            logger.error("Subprocess hung (no response in %dms)", self._timeout)
            self._kill_process()
            return None
        except zmq.ZMQError as e:
            logger.error("ZMQ error: %s", e)
            self._kill_process()
            return None
        except Exception as e:
            logger.error("Unexpected error in send_frame: %s", e)
            self._kill_process()
            return None

    def shutdown(self) -> None:
        """Gracefully shut down subprocess and clean up resources."""
        self._kill_process()

    def _kill_process(self) -> None:
        """Kill subprocess and clean up ZMQ + IPC socket file."""
        self._alive = False
        if self._process:
            try:
                self._process.kill()
                self._process.wait(timeout=2)
            except Exception:
                pass
            self._process = None
        self._cleanup()

    def _cleanup(self) -> None:
        """Close ZMQ socket/context and remove IPC socket file."""
        self._alive = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        if self._ctx:
            try:
                self._ctx.term()
            except Exception:
                pass
            self._ctx = None
        # Remove IPC socket file to prevent "address already in use"
        if self._endpoint.startswith("ipc://"):
            sock_path = self._endpoint.replace("ipc://", "")
            if os.path.exists(sock_path):
                try:
                    os.unlink(sock_path)
                except OSError:
                    pass
