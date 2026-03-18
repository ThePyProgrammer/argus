"""Tests for src/locomotion -- XML patching, gait params, gait controller.

TDD RED phase: these tests define expected behavior before implementation.
"""

from __future__ import annotations

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
            "abduction": ("40", "2"),
            "hip": ("40", "2"),
            "knee": ("60", "3"),
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
        assert p.frequency == 2.0
        assert p.stance_height == -0.25
        assert p.swing_height == 0.06
        assert p.stride_length == 0.15
        assert p.lateral_stride == 0.08
        assert p.max_speed == 1.0
        assert p.standing_hip == 0.0
        assert p.standing_thigh == 0.9
        assert p.standing_calf == -1.8
