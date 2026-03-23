"""Tests for IMUReading dataclass and SensorFrame.imu_readings field."""

import numpy as np
import pytest

from src.bridge.sensor_types import IMUReading, SensorFrame


class TestIMUReading:
    """Unit tests for the IMUReading dataclass."""

    def test_construction(self):
        """IMUReading can be constructed with accel, gyro, timestamp."""
        reading = IMUReading(
            accel=np.array([0.0, 0.0, 9.81]),
            gyro=np.array([0.1, 0.2, 0.3]),
            timestamp=1.5,
        )
        np.testing.assert_array_equal(reading.accel, [0.0, 0.0, 9.81])
        np.testing.assert_array_equal(reading.gyro, [0.1, 0.2, 0.3])
        assert reading.timestamp == 1.5

    def test_accel_gyro_shapes(self):
        """IMUReading.accel and .gyro are numpy arrays of shape (3,)."""
        reading = IMUReading(
            accel=np.array([1.0, 2.0, 3.0]),
            gyro=np.array([0.1, 0.2, 0.3]),
            timestamp=0.0,
        )
        assert reading.accel.shape == (3,)
        assert reading.gyro.shape == (3,)


class TestSensorFrameIMU:
    """Tests for the imu_readings field on SensorFrame."""

    def _make_frame(self, **kwargs):
        """Helper to build a minimal SensorFrame."""
        defaults = dict(
            rgb=np.zeros((4, 4, 3), dtype=np.uint8),
            depth=None,
            ground_truth_pose=np.eye(4),
            sim_time=0.0,
        )
        defaults.update(kwargs)
        return SensorFrame(**defaults)

    def test_default_empty_list(self):
        """SensorFrame without imu_readings defaults to an empty list (backward compat)."""
        frame = self._make_frame()
        assert frame.imu_readings == []
        assert isinstance(frame.imu_readings, list)

    def test_with_imu_readings(self):
        """SensorFrame can be constructed with explicit imu_readings list."""
        readings = [
            IMUReading(accel=np.array([0.0, 0.0, 9.81]), gyro=np.zeros(3), timestamp=0.01),
            IMUReading(accel=np.array([0.0, 0.0, 9.82]), gyro=np.zeros(3), timestamp=0.02),
        ]
        frame = self._make_frame(imu_readings=readings)
        assert len(frame.imu_readings) == 2
        assert frame.imu_readings[0].timestamp == 0.01
