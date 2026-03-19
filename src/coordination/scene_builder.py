"""Programmatic XML generation for a two-robot MuJoCo scene.

Reads the single-robot go2.xml model, duplicates and prefixes all named
elements for robot_a and robot_b, then assembles them into a combined
scene XML with floor, lighting, and per-robot cameras.

Supports two scene modes:
- Flat: Simple checkerboard floor (default, for testing).
- Office: DimOS office1 scene with walls, rooms, furniture.

CRITICAL: The generated XML uses named joints/actuators so that
MultiRobotBridge can discover qpos/ctrl indices via mj_name2id()
instead of hardcoding them.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.locomotion import patch_actuators_to_position


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
    # Patch actuators to position-controlled servos before building scene
    patched_xml = patch_actuators_to_position(str(model_path / "go2.xml"))
    go2_root = ET.fromstring(patched_xml)

    # Extract sections from patched go2.xml
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
    # Camera: looks forward (+X in body frame), Y-right = -Y body, Y-up = +Z body
    ET.SubElement(body_a, "camera", name="robot_a_cam",
                  pos="0.35 0 0.15", xyaxes="0 0 -1 0 1 0", fovy="45")
    wb.append(body_a)

    # Create robot_b body
    body_b = copy.deepcopy(robot_body)
    _prefix_element(body_b, "robot_b_")
    sx, sy, sz = spawn_positions.get("robot_b", (10.0, 0.0, 0.3))
    body_b.attrib["pos"] = f"{sx} {sy} {sz}"
    ET.SubElement(body_b, "camera", name="robot_b_cam",
                  pos="0.35 0 0.15", xyaxes="0 0 -1 0 1 0", fovy="45")
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


def _find_dimos_scene_data() -> Path:
    """Locate the DimOS mujoco_sim data directory.

    Checks for extracted data at dimos/data/mujoco_sim/. If not found,
    attempts to extract from the LFS archive.

    Returns:
        Path to the mujoco_sim directory containing scene XMLs and assets.

    Raises:
        FileNotFoundError: If data cannot be found or extracted.
    """
    # Relative to project root
    project_root = Path(__file__).parent.parent.parent
    data_dir = project_root / "dimos" / "data" / "mujoco_sim"
    if data_dir.exists():
        return data_dir

    # Try extracting from LFS archive
    archive = project_root / "dimos" / "data" / ".lfs" / "mujoco_sim.tar.gz"
    if archive.exists():
        import tarfile
        with tarfile.open(str(archive), "r:gz") as tar:
            tar.extractall(archive.parent.parent)
        if data_dir.exists():
            return data_dir

    raise FileNotFoundError(
        f"DimOS mujoco_sim data not found at {data_dir}. "
        "Run: cd dimos && git lfs pull --include 'data/.lfs/mujoco_sim.tar.gz'"
    )


def build_two_robot_office_scene(
    model_dir: str,
    spawn_positions: dict[str, tuple[float, float, float]],
) -> tuple[str, dict[str, bytes]]:
    """Build a MuJoCo XML with two Go2 robots in the DimOS office scene.

    Loads scene_office1.xml from the DimOS data, injects two prefixed
    Go2 robot bodies and actuators, and returns the XML along with the
    asset dictionary needed for mujoco.MjModel.from_xml_string().

    Args:
        model_dir: Path to directory containing go2.xml and assets/.
        spawn_positions: Mapping from robot_id to (x, y, z) world position.

    Returns:
        Tuple of (xml_string, assets_dict) where assets_dict maps
        filenames to bytes for all scene + robot mesh/texture assets.
    """
    scene_data_dir = _find_dimos_scene_data()
    model_path = Path(model_dir)

    # Parse the office scene XML
    scene_xml_path = scene_data_dir / "scene_office1.xml"
    scene_tree = ET.parse(str(scene_xml_path))
    scene_root = scene_tree.getroot()

    # Parse the Go2 robot XML with patched position-controlled actuators
    patched_xml = patch_actuators_to_position(str(model_path / "go2.xml"))
    go2_root = ET.fromstring(patched_xml)

    # Extract Go2 sections
    go2_default = go2_root.find("default")
    go2_asset = go2_root.find("asset")
    go2_worldbody = go2_root.find("worldbody")
    go2_actuator = go2_root.find("actuator")
    robot_body = go2_worldbody.find("body")

    # Merge Go2 defaults into scene
    if go2_default is not None:
        existing_default = scene_root.find("default")
        if existing_default is None:
            scene_root.insert(0, copy.deepcopy(go2_default))
        else:
            for child in go2_default:
                existing_default.append(copy.deepcopy(child))

    # Merge Go2 mesh/material assets into scene assets
    scene_asset = scene_root.find("asset")
    if scene_asset is not None and go2_asset is not None:
        # Track existing asset names to avoid duplicates
        existing_names = {elem.get("name") for elem in scene_asset}
        for asset_child in go2_asset:
            name = asset_child.get("name")
            if name not in existing_names:
                scene_asset.append(copy.deepcopy(asset_child))

    # Inject robots into worldbody
    worldbody = scene_root.find("worldbody")

    for robot_id, prefix in [("robot_a", "robot_a_"), ("robot_b", "robot_b_")]:
        body = copy.deepcopy(robot_body)
        _prefix_element(body, prefix)
        sx, sy, sz = spawn_positions.get(robot_id, (0.0, 0.0, 0.3))
        body.attrib["pos"] = f"{sx} {sy} {sz}"
        ET.SubElement(body, "camera", name=f"{robot_id}_cam",
                      pos="0.35 0 0.15", xyaxes="0 0 -1 0 1 0", fovy="45")
        worldbody.append(body)

    # Add actuators for both robots
    act_section = scene_root.find("actuator")
    if act_section is None:
        act_section = ET.SubElement(scene_root, "actuator")
    for prefix in ("robot_a_", "robot_b_"):
        for motor in go2_actuator:
            new_motor = copy.deepcopy(motor)
            for attr in ("name", "joint", "tendon", "site"):
                if attr in new_motor.attrib:
                    new_motor.attrib[attr] = prefix + new_motor.attrib[attr]
            act_section.append(new_motor)

    # Remove compiler meshdir/texturedir since we'll provide assets dict
    compiler = scene_root.find("compiler")
    if compiler is not None:
        compiler.attrib.pop("meshdir", None)
        compiler.attrib.pop("texturedir", None)

    # Ensure visual znear/zfar for depth rendering
    visual = scene_root.find("visual")
    if visual is None:
        visual = ET.SubElement(scene_root, "visual")
    map_elem = visual.find("map")
    if map_elem is None:
        map_elem = ET.SubElement(visual, "map")
    map_elem.set("znear", "0.01")
    map_elem.set("zfar", "100")

    xml_str = ET.tostring(scene_root, encoding="unicode")

    # Build assets dictionary: scene assets + robot mesh assets
    assets: dict[str, bytes] = {}

    # Office scene assets (meshes from office_split, textures)
    mesh_dir = scene_data_dir / "scene_office1" / "office_split"
    if mesh_dir.exists():
        for f in mesh_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()

    tex_dir = scene_data_dir / "scene_office1" / "textures"
    if tex_dir.exists():
        for f in tex_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()

    # Go2 robot mesh assets
    go2_asset_dir = model_path / "assets"
    if go2_asset_dir.exists():
        for f in go2_asset_dir.iterdir():
            if f.is_file() and f.name not in assets:
                assets[f.name] = f.read_bytes()

    return xml_str, assets
