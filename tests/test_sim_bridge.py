"""Tests for SimWorld gym bridge (SIM-01 through SIM-04).

Integration tests (marked @pytest.mark.integration) require a running SimWorld
instance and are expected to skip in CI. Unit-level tests use mocks and can
run anywhere.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.env_config import SimWorldEnvConfig
from src.bridge.sensor_types import SensorFrame
from src.bridge.sim_bridge import (
    ACTION_MOVE_BACKWARD,
    ACTION_MOVE_FORWARD,
    ACTION_MOVE_LEFT,
    ACTION_MOVE_RIGHT,
    ACTION_TURN_LEFT,
    ACTION_TURN_RIGHT,
    SimWorldGymBridge,
)


# ---------------------------------------------------------------------------
# Helpers -- mock gym environment
# ---------------------------------------------------------------------------

def _make_mock_obs(
    width: int = 320,
    height: int = 240,
    include_depth: bool = True,
) -> dict:
    """Create a mock observation dict matching SimWorld's format."""
    obs = {"rgb": np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)}
    if include_depth:
        obs["depth"] = np.random.randint(0, 256, (height, width, 1), dtype=np.uint8)
    return obs


def _make_mock_info(
    location: list | None = None,
    rotation: str = "North",
) -> dict:
    """Create a mock info dict matching SimWorld's format."""
    return {
        "agent": {
            "agent_location": np.array(location or [100.0, 200.0, 50.0]),
            "agent_rotation": rotation,
        }
    }


def _create_mock_env(obs=None, info=None):
    """Create a mock gym environment."""
    if obs is None:
        obs = _make_mock_obs()
    if info is None:
        info = _make_mock_info()

    mock_env = MagicMock()
    mock_env.reset.return_value = (obs, info)
    mock_env.step.return_value = (obs, 0.0, False, False, info)
    return mock_env


# ---------------------------------------------------------------------------
# Unit tests (no SimWorld required)
# ---------------------------------------------------------------------------

class TestSimWorldGymBridgeUnit:
    """Unit tests using a mocked gym environment."""

    def test_import(self):
        """SimWorldGymBridge can be imported."""
        from src.bridge.sim_bridge import SimWorldGymBridge
        assert SimWorldGymBridge is not None

    def test_init_default_config(self):
        """Bridge initialises with default SimWorldEnvConfig."""
        bridge = SimWorldGymBridge()
        assert not bridge.is_running
        assert bridge.step_count == 0

    def test_init_custom_config(self):
        """Bridge accepts a custom config."""
        config = SimWorldEnvConfig(env_id="test/Env", target_step_hz=5.0)
        bridge = SimWorldGymBridge(config)
        assert not bridge.is_running

    @patch("src.bridge.sim_bridge.gym", create=True)
    def test_lifecycle(self, mock_gym_module):
        """SIM-01: Bridge starts, runs, and stops correctly."""
        mock_env = _create_mock_env()
        # Patch the import inside start() -- we mock gym.make
        with patch.dict("sys.modules", {"gym": MagicMock(make=MagicMock(return_value=mock_env))}):
            bridge = SimWorldGymBridge()
            frame = bridge.start()

            assert bridge.is_running
            assert isinstance(frame, SensorFrame)

            frame2 = bridge.step()
            assert isinstance(frame2, SensorFrame)
            assert bridge.step_count == 1

            bridge.stop()
            assert not bridge.is_running
            assert bridge.step_count == 0

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_sensor_extraction(self):
        """SIM-02: step() returns SensorFrame with correct shapes and dtypes."""
        obs = _make_mock_obs(320, 240, include_depth=True)
        info = _make_mock_info()
        mock_env = _create_mock_env(obs, info)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        bridge = SimWorldGymBridge()
        frame = bridge.start()

        assert isinstance(frame, SensorFrame)
        # RGB
        assert frame.rgb.shape == (240, 320, 3)
        assert frame.rgb.dtype == np.uint8
        # Depth -- SimWorld returns (H,W,1) uint8, bridge squeezes to (H,W)
        assert frame.depth is not None
        assert frame.depth.ndim == 2
        assert frame.depth.shape == (240, 320)
        # Pose
        assert frame.ground_truth_pose.shape == (4, 4)
        assert frame.ground_truth_pose.dtype == np.float64
        # Sim time
        assert isinstance(frame.sim_time, float)

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_sensor_extraction_no_depth(self):
        """SIM-02 fallback: monocular mode when no depth in observation."""
        obs = _make_mock_obs(320, 240, include_depth=False)
        info = _make_mock_info()
        mock_env = _create_mock_env(obs, info)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        bridge = SimWorldGymBridge()
        frame = bridge.start()

        assert frame.depth is None  # monocular fallback

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_movement_command(self):
        """SIM-03: Velocity commands produce correct discrete actions and change pose."""
        # First call: initial position
        obs1 = _make_mock_obs()
        info1 = _make_mock_info(location=[0.0, 0.0, 0.0])

        # After moving: different position
        obs2 = _make_mock_obs()
        info2 = _make_mock_info(location=[500.0, 0.0, 0.0])  # 5m forward in cm

        mock_env = MagicMock()
        mock_env.reset.return_value = (obs1, info1)
        mock_env.step.return_value = (obs2, 0.0, False, False, info2)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        bridge = SimWorldGymBridge()
        frame_initial = bridge.start()
        initial_pos = frame_initial.ground_truth_pose[:3, 3].copy()

        # Set forward velocity
        bridge.set_velocity(np.array([0.5, 0.0]), 0.0)
        assert bridge._current_action == ACTION_MOVE_FORWARD

        frame_moved = bridge.step()
        new_pos = frame_moved.ground_truth_pose[:3, 3]

        # Position should have changed
        assert np.linalg.norm(new_pos - initial_pos) > 0.01

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_ground_truth_pose(self):
        """SIM-04: Ground-truth pose is valid 4x4 homogeneous transform."""
        obs = _make_mock_obs()
        info = _make_mock_info(location=[100.0, 200.0, 50.0], rotation="North")
        mock_env = _create_mock_env(obs, info)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        bridge = SimWorldGymBridge()
        frame = bridge.start()

        pose = frame.ground_truth_pose
        assert pose.shape == (4, 4)
        assert pose.dtype == np.float64

        # Rotation part should be orthonormal (det(R) approx 1.0)
        R = pose[:3, :3]
        assert abs(np.linalg.det(R) - 1.0) < 1e-6

        # Position should be in meters (converted from cm)
        assert np.allclose(pose[:3, 3], [1.0, 2.0, 0.5])  # 100cm -> 1m, etc.

    def test_set_velocity_mapping(self):
        """set_velocity correctly maps continuous velocities to discrete actions."""
        bridge = SimWorldGymBridge()

        # Forward
        bridge.set_velocity(np.array([1.0, 0.0]), 0.0)
        assert bridge._current_action == ACTION_MOVE_FORWARD

        # Backward
        bridge.set_velocity(np.array([-1.0, 0.0]), 0.0)
        assert bridge._current_action == ACTION_MOVE_BACKWARD

        # Strafe left
        bridge.set_velocity(np.array([0.0, 1.0]), 0.0)
        assert bridge._current_action == ACTION_MOVE_LEFT

        # Strafe right
        bridge.set_velocity(np.array([0.0, -1.0]), 0.0)
        assert bridge._current_action == ACTION_MOVE_RIGHT

        # Turn left (angular > 0)
        bridge.set_velocity(np.array([0.0, 0.0]), 1.0)
        assert bridge._current_action == ACTION_TURN_LEFT

        # Turn right (angular < 0)
        bridge.set_velocity(np.array([0.0, 0.0]), -1.0)
        assert bridge._current_action == ACTION_TURN_RIGHT

    def test_euler_to_rotation_matrix_identity(self):
        """Zero rotation gives identity rotation matrix."""
        R = SimWorldGymBridge._euler_to_rotation_matrix(0, 0, 0)
        assert np.allclose(R, np.eye(3))

    def test_euler_to_rotation_matrix_orthonormal(self):
        """Rotation matrix from arbitrary angles is orthonormal."""
        R = SimWorldGymBridge._euler_to_rotation_matrix(0.3, 0.5, 1.2)
        assert abs(np.linalg.det(R) - 1.0) < 1e-10
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-10)

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_step_without_start_raises(self):
        """Calling step() before start() raises RuntimeError."""
        bridge = SimWorldGymBridge()
        with pytest.raises(RuntimeError, match="not started"):
            bridge.step()

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_auto_reset_on_terminated(self):
        """Bridge auto-resets when episode terminates."""
        obs = _make_mock_obs()
        info = _make_mock_info()
        mock_env = MagicMock()
        mock_env.reset.return_value = (obs, info)
        # step returns terminated=True
        mock_env.step.return_value = (obs, 0.0, True, False, info)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        bridge = SimWorldGymBridge()
        bridge.start()
        frame = bridge.step()

        # Should have called reset again
        assert mock_env.reset.call_count == 2
        assert isinstance(frame, SensorFrame)

    @patch.dict("sys.modules", {"gym": MagicMock()})
    def test_sim_time_increments(self):
        """sim_time advances with each step based on target_step_hz."""
        obs = _make_mock_obs()
        info = _make_mock_info()
        mock_env = _create_mock_env(obs, info)

        import sys
        sys.modules["gym"].make = MagicMock(return_value=mock_env)

        config = SimWorldEnvConfig(target_step_hz=10.0)
        bridge = SimWorldGymBridge(config)
        frame0 = bridge.start()
        assert frame0.sim_time == 0.0

        frame1 = bridge.step()
        assert abs(frame1.sim_time - 0.1) < 1e-9  # 1/10 Hz = 0.1s

        frame2 = bridge.step()
        assert abs(frame2.sim_time - 0.2) < 1e-9


# ---------------------------------------------------------------------------
# Integration tests (require running SimWorld)
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_lifecycle():
    """SIM-01: Gym env connects, resets, steps, and closes without errors.

    Verifies:
    - gym.make() with the discovered env_id succeeds
    - env.reset() returns SensorFrame with expected fields
    - env.step() returns SensorFrame
    - env.close() completes without error
    """
    bridge = SimWorldGymBridge()
    frame = bridge.start()
    assert bridge.is_running
    assert isinstance(frame, SensorFrame)

    frame2 = bridge.step()
    assert isinstance(frame2, SensorFrame)

    bridge.stop()
    assert not bridge.is_running


@pytest.mark.integration
def test_sensor_extraction():
    """SIM-02: Step returns RGB and depth arrays with correct shapes and dtypes.

    Verifies:
    - Observation contains RGB image as uint8 array with 3 channels
    - Observation contains depth image (or None for monocular)
    - Image dimensions match expected resolution from env config
    """
    bridge = SimWorldGymBridge()
    bridge.start()
    frame = bridge.step()

    assert frame.rgb.dtype == np.uint8
    assert frame.rgb.ndim == 3
    assert frame.rgb.shape[2] == 3

    if frame.depth is not None:
        assert frame.depth.ndim in (2, 3)

    bridge.stop()


@pytest.mark.integration
def test_movement_command():
    """SIM-03: Velocity command changes robot position in SimWorld.

    Verifies:
    - Sending a forward velocity command results in position change
    - Position change is measurable (> 0.01 m)
    """
    bridge = SimWorldGymBridge()
    bridge.start()
    initial_frame = bridge.step()
    initial_pos = initial_frame.ground_truth_pose[:3, 3].copy()

    bridge.set_velocity(np.array([0.5, 0.0]), 0.0)
    for _ in range(10):
        frame = bridge.step()

    new_pos = frame.ground_truth_pose[:3, 3]
    assert np.linalg.norm(new_pos - initial_pos) > 0.01

    bridge.stop()


@pytest.mark.integration
def test_ground_truth_pose():
    """SIM-04: Ground-truth pose extracted per step as 4x4 homogeneous transform.

    Verifies:
    - Ground-truth pose is a valid (4, 4) homogeneous transform
    - Rotation part is orthonormal (det(R) approx 1.0)
    - Pose changes when robot moves
    """
    bridge = SimWorldGymBridge()
    bridge.start()
    frame = bridge.step()

    pose = frame.ground_truth_pose
    assert pose.shape == (4, 4)
    assert pose.dtype == np.float64

    R = pose[:3, :3]
    assert abs(np.linalg.det(R) - 1.0) < 1e-6

    bridge.stop()
