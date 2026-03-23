"""Tests for src/locomotion -- XML patching, gait params, gait controller.

TDD RED phase: these tests define expected behavior before implementation.
"""


import os
from pathlib import Path

import numpy as np
import pytest

# Path to the upstream Go2 model (must not be modified by tests)
GO2_XML = str(Path(__file__).parent.parent / "models" / "unitree_go2" / "go2.xml")


# ------------------------------------------------------------------ #
# XML Patcher tests
# ------------------------------------------------------------------ #


class TestPatchActuators:
    """patch_actuators_to_position converts motor -> position with PD gains."""

    def test_patch_actuators_converts_motors(self):
        """All 12 actuators should have tag 'position' instead of 'motor'."""
        import xml.etree.ElementTree as ET

        from src.locomotion.xml_patcher import patch_actuators_to_position

        xml_str = patch_actuators_to_position(GO2_XML)
        root = ET.fromstring(xml_str)
        actuator_elem = root.find("actuator")
        assert actuator_elem is not None

        children = list(actuator_elem)
        assert len(children) == 12
        for child in children:
            assert child.tag == "position", (
                f"Expected tag 'position', got '{child.tag}' for {child.get('name')}"
            )

    def test_patch_gains_by_class(self):
        """Each actuator should have kp/kv gains matching its joint class."""
        import xml.etree.ElementTree as ET

        from src.locomotion.xml_patcher import patch_actuators_to_position

        xml_str = patch_actuators_to_position(GO2_XML)
        root = ET.fromstring(xml_str)
        actuator_elem = root.find("actuator")

        expected_gains = {
            "abduction": ("80", "4"),
            "hip": ("80", "4"),
            "knee": ("120", "6"),
        }

        for child in actuator_elem:
            cls = child.get("class", "")
            assert cls in expected_gains, f"Unknown class '{cls}' for {child.get('name')}"
            exp_kp, exp_kv = expected_gains[cls]
            assert child.get("kp") == exp_kp, (
                f"{child.get('name')}: expected kp={exp_kp}, got kp={child.get('kp')}"
            )
            assert child.get("kv") == exp_kv, (
                f"{child.get('name')}: expected kv={exp_kv}, got kv={child.get('kv')}"
            )

    def test_ctrlrange_removed(self):
        """ctrlrange attributes should be removed from patched actuators."""
        import xml.etree.ElementTree as ET

        from src.locomotion.xml_patcher import patch_actuators_to_position

        xml_str = patch_actuators_to_position(GO2_XML)
        root = ET.fromstring(xml_str)
        actuator_elem = root.find("actuator")

        for child in actuator_elem:
            assert "ctrlrange" not in child.attrib, (
                f"{child.get('name')} still has ctrlrange"
            )

    def test_original_xml_not_modified(self):
        """The original go2.xml on disk must NOT be modified."""
        import xml.etree.ElementTree as ET

        # Read original content hash before
        original = Path(GO2_XML).read_text()

        from src.locomotion.xml_patcher import patch_actuators_to_position

        _ = patch_actuators_to_position(GO2_XML)

        # File must be unchanged
        after = Path(GO2_XML).read_text()
        assert original == after, "go2.xml was modified on disk!"

    def test_joint_names_preserved(self):
        """All 12 joint/name attributes should be preserved after patching."""
        import xml.etree.ElementTree as ET

        from src.locomotion.xml_patcher import patch_actuators_to_position

        expected_names = [
            "FL_hip", "FL_thigh", "FL_calf",
            "FR_hip", "FR_thigh", "FR_calf",
            "RL_hip", "RL_thigh", "RL_calf",
            "RR_hip", "RR_thigh", "RR_calf",
        ]

        xml_str = patch_actuators_to_position(GO2_XML)
        root = ET.fromstring(xml_str)
        actuator_elem = root.find("actuator")

        names = [child.get("name") for child in actuator_elem]
        assert names == expected_names

    def test_patched_xml_loads_in_mujoco(self):
        """MuJoCo must be able to load the patched XML without error."""
        import mujoco

        from src.locomotion.xml_patcher import patch_actuators_to_position

        xml_str = patch_actuators_to_position(GO2_XML)

        # Build assets dict so MuJoCo can find mesh files
        asset_dir = Path(GO2_XML).parent / "assets"
        assets = {}
        if asset_dir.exists():
            for f in asset_dir.iterdir():
                if f.is_file():
                    assets[f.name] = f.read_bytes()

        # Must not raise
        model = mujoco.MjModel.from_xml_string(xml_str, assets)
        assert model.nu == 12  # 12 actuators


# ------------------------------------------------------------------ #
# GaitParams tests
# ------------------------------------------------------------------ #


class TestGaitParams:
    """GaitParams dataclass has correct default values."""

    def test_defaults(self):
        from src.locomotion.gait_params import GaitParams

        p = GaitParams()
        assert p.frequency == 3.0
        assert p.stance_height == -0.25
        assert p.swing_height == 0.15
        assert p.stride_length == 0.4
        assert p.lateral_stride == 0.08
        assert p.max_speed == 1.0
        assert p.standing_hip == 0.0
        assert p.standing_thigh == 0.9
        assert p.standing_calf == -1.8


# ------------------------------------------------------------------ #
# Helper: load patched Go2 model in MuJoCo
# ------------------------------------------------------------------ #


def _load_patched_model():
    """Load Go2 with patched position actuators + floor for physics tests."""
    import mujoco

    from src.locomotion.xml_patcher import patch_actuators_to_position_with_floor

    xml_str = patch_actuators_to_position_with_floor(GO2_XML)

    # Build assets dict
    asset_dir = Path(GO2_XML).parent / "assets"
    assets = {}
    if asset_dir.exists():
        for f in asset_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()

    model = mujoco.MjModel.from_xml_string(xml_str, assets)
    data = mujoco.MjData(model)
    return model, data


# ------------------------------------------------------------------ #
# TrotGaitController unit tests
# ------------------------------------------------------------------ #


class TestTrotGaitController:
    """TrotGaitController produces valid joint targets."""

    def test_standing_pose_with_zero_velocity(self):
        """compute(vx=0, vy=0, omega=0) returns standing pose."""
        from src.locomotion.gait_controller import TrotGaitController
        from src.locomotion.gait_params import GaitParams

        params = GaitParams()
        ctrl = TrotGaitController(params)
        result = ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)

        assert result.shape == (12,)
        # Each leg should be at standing pose
        for leg in range(4):
            base = leg * 3
            np.testing.assert_allclose(result[base], params.standing_hip, atol=1e-6)
            np.testing.assert_allclose(result[base + 1], params.standing_thigh, atol=1e-6)
            np.testing.assert_allclose(result[base + 2], params.standing_calf, atol=1e-6)

    def test_output_within_joint_limits(self):
        """compute with forward velocity returns 12 elements within Go2 joint limits."""
        from src.locomotion.gait_controller import TrotGaitController

        ctrl = TrotGaitController()
        # Run several timesteps to exercise all gait phases
        for _ in range(50):
            result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)

        assert result.shape == (12,)

        # Go2 joint limits (from go2.xml defaults)
        hip_limits = (-1.0472, 1.0472)
        thigh_limits = (-1.5708, 4.5379)  # union of front_hip and back_hip
        knee_limits = (-2.7227, -0.83776)

        for leg in range(4):
            base = leg * 3
            assert hip_limits[0] <= result[base] <= hip_limits[1], (
                f"Leg {leg} hip {result[base]} out of range"
            )
            assert thigh_limits[0] <= result[base + 1] <= thigh_limits[1], (
                f"Leg {leg} thigh {result[base + 1]} out of range"
            )
            assert knee_limits[0] <= result[base + 2] <= knee_limits[1], (
                f"Leg {leg} calf {result[base + 2]} out of range"
            )

    def test_phase_advances_when_moving(self):
        """Gait phase advances when speed > 0 and stays fixed when speed = 0."""
        from src.locomotion.gait_controller import TrotGaitController

        ctrl = TrotGaitController()

        # Zero velocity -- phase should not advance
        ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=0.02)
        phase_after_zero = ctrl._phase
        assert phase_after_zero == 0.0

        # Nonzero velocity -- phase should advance
        ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)
        phase_after_move = ctrl._phase
        assert phase_after_move > 0.0

    def test_diagonal_pairs_antiphase(self):
        """Diagonal pairs (FL+RR vs FR+RL) have 180-degree phase offset in thigh targets."""
        from src.locomotion.gait_controller import TrotGaitController

        ctrl = TrotGaitController()
        # Advance to a mid-gait position
        for _ in range(10):
            result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)

        # FL (index 0) and RR (index 3) should be in the same phase
        fl_thigh = result[0 * 3 + 1]
        rr_thigh = result[3 * 3 + 1]

        # FR (index 1) and RL (index 2) should be in the same phase
        fr_thigh = result[1 * 3 + 1]
        rl_thigh = result[2 * 3 + 1]

        # Pair A (FL, RR) should match each other
        np.testing.assert_allclose(fl_thigh, rr_thigh, atol=0.05)

        # Pair B (FR, RL) should match each other
        np.testing.assert_allclose(fr_thigh, rl_thigh, atol=0.05)

        # The two pairs should differ (anti-phase)
        assert abs(fl_thigh - fr_thigh) > 0.001, (
            "Diagonal pairs should have different thigh targets"
        )


# ------------------------------------------------------------------ #
# Bridge gait parity test
# ------------------------------------------------------------------ #


class TestBridgeGaitParity:
    """Both MuJoCoBridge and MultiRobotBridge use the same TrotGaitController."""

    def test_same_gait_output(self):
        """Single-robot and multi-robot gait controllers produce identical output."""
        from src.locomotion.gait_controller import TrotGaitController

        gait_a = TrotGaitController()
        gait_b = TrotGaitController()

        # Run several steps with the same velocity input
        for _ in range(20):
            out_a = gait_a.compute(vx=0.5, vy=0.1, omega=0.3, dt=0.02)
            out_b = gait_b.compute(vx=0.5, vy=0.1, omega=0.3, dt=0.02)
            np.testing.assert_array_equal(out_a, out_b)


# ------------------------------------------------------------------ #
# MuJoCo integration tests
# ------------------------------------------------------------------ #


class TestMuJoCoIntegration:
    """Integration tests verifying the robot actually moves in physics."""

    def test_robot_moves_forward(self):
        """Robot with patched actuators translates >0.5m in 100 steps with vx=0.5."""
        import mujoco

        from src.locomotion.gait_controller import TrotGaitController

        model, data = _load_patched_model()
        ctrl = TrotGaitController()

        # Set initial keyframe pose
        if model.nq >= 19:
            data.qpos[7:19] = [0.0, 0.9, -1.8] * 4

        # Settle the robot
        data.ctrl[:] = [0.0, 0.9, -1.8] * 4
        for _ in range(200):
            mujoco.mj_step(model, data)

        start_x = data.qpos[0]

        # Run 100 steps with forward velocity
        dt = model.opt.timestep * 10  # 10 physics steps per control step
        for _ in range(100):
            targets = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=dt)
            data.ctrl[:] = targets
            for _ in range(10):
                mujoco.mj_step(model, data)

        displacement = data.qpos[0] - start_x
        assert displacement > 0.5, (
            f"Robot only moved {displacement:.3f}m forward, expected >0.5m"
        )

    def test_robot_turns(self):
        """Robot turns >45 degrees (0.785 rad) in 100 steps with omega=1.0."""
        import mujoco

        from src.locomotion.gait_controller import TrotGaitController

        model, data = _load_patched_model()
        ctrl = TrotGaitController()

        # Set initial keyframe pose
        if model.nq >= 19:
            data.qpos[7:19] = [0.0, 0.9, -1.8] * 4

        # Settle
        data.ctrl[:] = [0.0, 0.9, -1.8] * 4
        for _ in range(200):
            mujoco.mj_step(model, data)

        # Extract initial yaw from quaternion (w, x, y, z)
        def _yaw_from_quat(q):
            w, x, y, z = q
            return np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))

        start_yaw = _yaw_from_quat(data.qpos[3:7])

        # Run 100 steps with angular velocity
        dt = model.opt.timestep * 10
        for _ in range(100):
            targets = ctrl.compute(vx=0.0, vy=0.0, omega=1.0, dt=dt)
            data.ctrl[:] = targets
            for _ in range(10):
                mujoco.mj_step(model, data)

        end_yaw = _yaw_from_quat(data.qpos[3:7])
        yaw_change = abs(end_yaw - start_yaw)
        # Handle wrap-around
        if yaw_change > np.pi:
            yaw_change = 2 * np.pi - yaw_change

        assert yaw_change > 0.785, (
            f"Robot only turned {np.degrees(yaw_change):.1f} degrees, expected >45"
        )

    def test_robot_stands_still(self):
        """Robot with zero velocity stays within 0.1m of start over 50 steps."""
        import mujoco

        from src.locomotion.gait_controller import TrotGaitController

        model, data = _load_patched_model()
        ctrl = TrotGaitController()

        # Set initial keyframe pose
        if model.nq >= 19:
            data.qpos[7:19] = [0.0, 0.9, -1.8] * 4

        # Settle
        data.ctrl[:] = [0.0, 0.9, -1.8] * 4
        for _ in range(200):
            mujoco.mj_step(model, data)

        start_pos = data.qpos[:3].copy()

        # Run 50 steps with zero velocity
        dt = model.opt.timestep * 10
        for _ in range(50):
            targets = ctrl.compute(vx=0.0, vy=0.0, omega=0.0, dt=dt)
            data.ctrl[:] = targets
            for _ in range(10):
                mujoco.mj_step(model, data)

        displacement = np.linalg.norm(data.qpos[:2] - start_pos[:2])
        assert displacement < 0.1, (
            f"Robot drifted {displacement:.3f}m with zero velocity, expected <0.1m"
        )
