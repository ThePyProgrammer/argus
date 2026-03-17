"""Tests for SimWorld gym bridge (SIM-01 through SIM-04).

These are integration tests that require a running SimWorld instance.
Currently stubbed as pending implementation.
"""

import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_lifecycle():
    """SIM-01: Gym env connects, resets, steps, and closes without errors.

    Verifies:
    - gym.make() with the discovered env_id succeeds
    - env.reset() returns (obs, info) with expected keys
    - env.step() returns (obs, reward, terminated, truncated, info)
    - env.close() completes without error
    """
    assert False, "pending"


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_sensor_extraction():
    """SIM-02: Step returns RGB and depth arrays with correct shapes and dtypes.

    Verifies:
    - Observation contains RGB image as uint8 array with 3 channels
    - Observation contains depth image as float32 array (or None for monocular)
    - Image dimensions match expected resolution from env config
    """
    assert False, "pending"


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_movement_command():
    """SIM-03: Velocity command changes robot position in SimWorld.

    Verifies:
    - Sending a forward velocity command results in position change
    - Position change direction matches commanded velocity direction
    - Zero velocity results in no significant position change
    """
    assert False, "pending"


@pytest.mark.integration
@pytest.mark.skip(reason="pending implementation")
def test_ground_truth_pose():
    """SIM-04: Ground-truth pose extracted per step as 4x4 homogeneous transform.

    Verifies:
    - Ground-truth pose is available in observation or info dict
    - Pose is a valid (4, 4) homogeneous transform (rotation is orthonormal)
    - Pose changes when robot moves
    """
    assert False, "pending"
