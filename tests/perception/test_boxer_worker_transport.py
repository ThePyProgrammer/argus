from pathlib import Path
import sys
import time
from unittest.mock import Mock

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.subprocess_bridge import SubprocessDetectorBridge
from src.perception.types import Detections3D, OrientedBox3D
from src.perception.worker import DetectorWorker


@pytest.mark.parametrize("endpoint", [None, "tcp://127.0.0.1:*"])
def test_python_worker_round_trip_over_tcp(endpoint, monkeypatch):
    import src.perception.subprocess_bridge as transport

    monkeypatch.setattr(transport.zmq, "has", lambda capability: False)
    script = Path(__file__).resolve().parents[2] / "scripts/echo_detector_worker.py"
    bridge = SubprocessDetectorBridge(
        sys.executable, args=[str(script)], ipc_endpoint=endpoint,
    )
    try:
        bridge.start()
        bridge.wait_for_handshake(timeout_s=10)
        reply = bridge.send_frame(np.zeros((24, 32, 3), dtype=np.uint8), None, 1.5)
        assert reply["ts"] == 1.5
        assert bridge.endpoint.startswith("tcp://127.0.0.1:")
    finally:
        bridge.shutdown()


def test_native_3d_results_bypass_lifter_and_keep_world_coordinates():
    box = OrientedBox3D(
        center=np.array([4., 5., 6.]), half_extents=np.ones(3),
        quaternion=np.array([0., 0., 0., 1.]), class_id=56, class_name="chair", score=0.8,
    )
    result = Detections3D(
        items=[box], detector_ms=10., lifter_ms=0., n_raw=1, n_final=1, image_hw=(24, 32),
    )
    detector = Mock()
    detector.process_frame.return_value = result
    lifter = Mock()
    lifter.lift.side_effect = AssertionError("Native 3D boxes must not be lifted again")
    worker = DetectorWorker("robot_a", detector, lifter, CameraIntrinsics.from_fov(32, 24))
    frame = SensorFrame(np.zeros((24, 32, 3), dtype=np.uint8), None, np.eye(4), 42.)
    try:
        worker.start()
        worker.submit(frame, np.eye(4), None)
        deadline = time.monotonic() + 3
        while worker.latest() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        latest = worker.latest()
        assert latest is not None
        np.testing.assert_array_equal(latest.items[0].center, [4., 5., 6.])
        assert latest.capture_timestamp == 42.
        lifter.lift.assert_not_called()
    finally:
        worker.shutdown()
