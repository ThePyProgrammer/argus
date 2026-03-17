"""Programmatic XML generation for a two-robot MuJoCo scene.

Reads the single-robot go2.xml model, duplicates and prefixes all named
elements for robot_a and robot_b, then assembles them into a combined
scene XML with floor, lighting, and per-robot cameras.

CRITICAL: The generated XML uses named joints/actuators so that
MultiRobotBridge can discover qpos/ctrl indices via mj_name2id()
instead of hardcoding them.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path


# Attributes that contain names which must be prefixed
_NAME_ATTRS = frozenset({
    "name", "joint", "target", "body1", "body2", "site",
    "tendon",
})
# NOTE: "class" is deliberately excluded -- class attributes reference
# shared <default> classes (visual, collision, go2, etc.) that are NOT
# prefixed per-robot.


def _prefix_element(elem: ET.Element, prefix: str) -> None:
    """Recursively prefix name-bearing attributes on elem and children."""
    for attr in list(elem.attrib.keys()):
        if attr in _NAME_ATTRS:
            elem.attrib[attr] = prefix + elem.attrib[attr]
        # Handle mesh references in geom elements -- do NOT prefix mesh names
        # as they reference shared assets
    for child in elem:
        _prefix_element(child, prefix)


def _prefix_actuators(actuator_elem: ET.Element, prefix: str) -> ET.Element:
    """Create a prefixed copy of actuator elements."""
    new_act = copy.deepcopy(actuator_elem)
    for motor in new_act:
        for attr in ("name", "joint", "tendon", "site"):
            if attr in motor.attrib:
                motor.attrib[attr] = prefix + motor.attrib[attr]
        # Also prefix class if present
        if "class" in motor.attrib:
            motor.attrib["class"] = prefix + motor.attrib["class"]
    return new_act


def build_two_robot_scene(
    model_dir: str,
    spawn_positions: dict[str, tuple[float, float, float]],
) -> str:
    """Build a MuJoCo XML scene containing two Go2 robots.

    Reads go2.xml from model_dir, duplicates the robot body and actuators
    with robot_a_ and robot_b_ prefixes, and inserts them into a scene
    with floor and lighting.

    Args:
        model_dir: Path to directory containing go2.xml and assets/.
        spawn_positions: Mapping from robot_id to (x, y, z) world position.

    Returns:
        Combined MuJoCo XML as a string.
    """
    model_path = Path(model_dir)
    go2_tree = ET.parse(str(model_path / "go2.xml"))
    go2_root = go2_tree.getroot()

    # Extract sections from go2.xml
    compiler_elem = go2_root.find("compiler")
    option_elem = go2_root.find("option")
    default_elem = go2_root.find("default")
    asset_elem = go2_root.find("asset")
    worldbody_elem = go2_root.find("worldbody")
    actuator_elem = go2_root.find("actuator")

    # The robot body is the first <body> child of <worldbody>
    robot_body = worldbody_elem.find("body")

    # Build the combined scene root
    scene = ET.Element("mujoco", model="go2_two_robot_scene")

    # Compiler: update meshdir to be relative to model_dir
    comp = copy.deepcopy(compiler_elem)
    # meshdir in go2.xml is "assets", make it relative to model_dir
    comp.attrib["meshdir"] = str(model_path / "assets")
    scene.append(comp)

    # Option
    if option_elem is not None:
        scene.append(copy.deepcopy(option_elem))

    # Default -- do NOT prefix default classes, they are shared
    if default_elem is not None:
        scene.append(copy.deepcopy(default_elem))

    # Visual (from scene template)
    visual = ET.SubElement(scene, "visual")
    ET.SubElement(visual, "headlight", diffuse="0.6 0.6 0.6", ambient="0.3 0.3 0.3", specular="0 0 0")
    ET.SubElement(visual, "rgba", haze="0.15 0.25 0.35 1")
    ET.SubElement(visual, "global", azimuth="-130", elevation="-20")

    # Asset: merge go2 assets + scene assets
    merged_asset = copy.deepcopy(asset_elem)
    # Add scene textures and materials
    ET.SubElement(merged_asset, "texture", type="skybox", builtin="gradient",
                  rgb1="0.3 0.5 0.7", rgb2="0 0 0", width="512", height="3072")
    ET.SubElement(merged_asset, "texture", type="2d", name="groundplane",
                  builtin="checker", mark="edge",
                  rgb1="0.2 0.3 0.4", rgb2="0.1 0.2 0.3",
                  markrgb="0.8 0.8 0.8", width="300", height="300")
    ET.SubElement(merged_asset, "material", name="groundplane",
                  texture="groundplane", texuniform="true",
                  texrepeat="5 5", reflectance="0.2")
    scene.append(merged_asset)

    # Worldbody: floor + light + two robot bodies
    wb = ET.SubElement(scene, "worldbody")
    ET.SubElement(wb, "light", pos="0 0 3", dir="0 0 -1", directional="true")
    ET.SubElement(wb, "geom", name="floor", size="100 100 0.05", type="plane",
                  material="groundplane")

    # Create robot_a body
    body_a = copy.deepcopy(robot_body)
    _prefix_element(body_a, "robot_a_")
    # Set spawn position
    sx, sy, sz = spawn_positions.get("robot_a", (0.0, 0.0, 0.3))
    body_a.attrib["pos"] = f"{sx} {sy} {sz}"
    # Add per-robot camera as child of base body
    ET.SubElement(body_a, "camera", name="robot_a_cam",
                  pos="0.3 0 0.1", xyaxes="0 -1 0 0 0 1", fovy="45")
    wb.append(body_a)

    # Create robot_b body
    body_b = copy.deepcopy(robot_body)
    _prefix_element(body_b, "robot_b_")
    sx, sy, sz = spawn_positions.get("robot_b", (10.0, 0.0, 0.3))
    body_b.attrib["pos"] = f"{sx} {sy} {sz}"
    ET.SubElement(body_b, "camera", name="robot_b_cam",
                  pos="0.3 0 0.1", xyaxes="0 -1 0 0 0 1", fovy="45")
    wb.append(body_b)

    # Actuators: duplicate with prefixes (do NOT prefix class on actuators)
    act_section = ET.SubElement(scene, "actuator")
    for prefix in ("robot_a_", "robot_b_"):
        for motor in actuator_elem:
            new_motor = copy.deepcopy(motor)
            for attr in ("name", "joint", "tendon", "site"):
                if attr in new_motor.attrib:
                    new_motor.attrib[attr] = prefix + new_motor.attrib[attr]
            # Do NOT prefix "class" on actuators -- they reference shared defaults
            act_section.append(new_motor)

    return ET.tostring(scene, encoding="unicode")
