"""Tests for IMU sensor extraction from MuJoCo simulation.

Tests Go2 XML sensor elements and MuJoCoBridge IMU sub-stepping.
"""

import mujoco
import numpy as np
import pytest

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import IMUReading, SensorFrame
from src.bridge.sim_bridge import MuJoCoBridge


class TestGo2XMLSensors:
    """Test that go2.xml has the expected IMU sensor elements."""

    def test_xml_has_accelerometer_and_gyro(self):
        """Go2 XML loads with sensors named 'accelerometer' and 'gyro'."""
        model = mujoco.MjModel.from_xml_path("models/unitree_go2/go2.xml")
        accel_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "accelerometer")
        gyro_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "gyro")
        assert accel_id >= 0, "accelerometer sensor not found in go2.xml"
        assert gyro_id >= 0, "gyro sensor not found in go2.xml"


@pytest.fixture
def bridge():
    """Create and yield a MuJoCo bridge, ensuring cleanup."""
    config = MuJoCoEnvConfig()
    b = MuJoCoBridge(config)
    yield b
    if b.is_running:
        b.stop()


@pytest.mark.integration
class TestIMUExtraction:
    """Integration tests for IMU data extraction via MuJoCoBridge."""

    def test_step_returns_nonempty_imu(self, bridge):
        """MuJoCoBridge.step() returns SensorFrame with non-empty imu_readings."""
        bridge.start()
        frame = bridge.step()
        assert len(frame.imu_readings) > 0

    def test_imu_count_equals_substeps(self, bridge):
        """Number of IMU readings per step equals sim_steps_per_frame."""
        bridge.start()
        frame = bridge.step()
        expected = bridge._config.sim_steps_per_frame
        assert len(frame.imu_readings) == expected

    def test_imu_shapes(self, bridge):
        """Each IMUReading has accel shape (3,) and gyro shape (3,)."""
        bridge.start()
        frame = bridge.step()
        for reading in frame.imu_readings:
            assert isinstance(reading, IMUReading)
            assert reading.accel.shape == (3,)
            assert reading.gyro.shape == (3,)

    def test_imu_timestamps_monotonic(self, bridge):
        """IMU timestamps are monotonically increasing within a step."""
        bridge.start()
        frame = bridge.step()
        timestamps = [r.timestamp for r in frame.imu_readings]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1], (
                f"Timestamps not monotonic: {timestamps[i-1]} >= {timestamps[i]}"
            )

    def test_accelerometer_has_gravity(self, bridge):
        """Accelerometer reading includes gravity (~9.81 m/s^2 on z-ish axis)."""
        bridge.start()
        frame = bridge.step()
        # At least one reading should have a significant z-component from gravity
        accels = np.array([r.accel for r in frame.imu_readings])
        # The magnitude of the mean accel should be close to 9.81
        mean_accel_mag = np.linalg.norm(accels.mean(axis=0))
        assert mean_accel_mag > 5.0, f"Mean accel magnitude {mean_accel_mag} too low (expected ~9.81)"
