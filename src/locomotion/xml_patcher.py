"""MJCF actuator type conversion for Unitree Go2.

Converts the upstream go2.xml torque-mode <motor> actuators to
position-controlled <position> actuators with PD gains, so that
ctrl[i] = desired_joint_angle works correctly.

The original XML file is never modified on disk.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET


# PD gains per actuator class (from community Go2 controllers).
# Keys match the ``class`` attribute on <motor> elements in go2.xml.
_GAINS: dict[str, dict[str, str]] = {
    "abduction": {"kp": "80", "kv": "4"},
    "hip": {"kp": "80", "kv": "4"},
    "knee": {"kp": "120", "kv": "6"},
}


def patch_actuators_to_position(xml_path: str) -> str:
    """Convert torque motors to position actuators in Go2 MJCF.

    Parses the XML at *xml_path*, changes every ``<motor>`` element
    inside ``<actuator>`` to ``<position>`` with appropriate ``kp``/``kv``
    gains, and removes the ``ctrlrange`` attribute (position actuators
    use joint limits instead).

    Args:
        xml_path: Filesystem path to the go2.xml model file.

    Returns:
        The modified XML document as a string.  The file on disk is
        **not** modified.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    actuator_elem = root.find("actuator")
    if actuator_elem is None:
        return ET.tostring(root, encoding="unicode")

    for motor in list(actuator_elem):
        if motor.tag != "motor":
            continue

        joint_class = motor.get("class", "")
        gains = _GAINS.get(joint_class, _GAINS["hip"])

        # Convert tag from <motor> to <position>
        motor.tag = "position"

        # Set PD gains
        motor.set("kp", gains["kp"])
        motor.set("kv", gains["kv"])

        # Remove torque ctrlrange -- position actuators use joint limits
        motor.attrib.pop("ctrlrange", None)

    return ET.tostring(root, encoding="unicode")


def patch_actuators_to_position_with_floor(xml_path: str) -> str:
    """Like :func:`patch_actuators_to_position` but also adds a ground plane.

    Inserts a ``<geom type="plane" .../>`` and a ``<light>`` into the
    worldbody so that the patched model can be loaded standalone for
    physics testing without a separate scene XML.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Patch actuators (same logic)
    actuator_elem = root.find("actuator")
    if actuator_elem is not None:
        for motor in list(actuator_elem):
            if motor.tag != "motor":
                continue
            joint_class = motor.get("class", "")
            gains = _GAINS.get(joint_class, _GAINS["hip"])
            motor.tag = "position"
            motor.set("kp", gains["kp"])
            motor.set("kv", gains["kv"])
            motor.attrib.pop("ctrlrange", None)

    # Add floor and light to worldbody
    worldbody = root.find("worldbody")
    if worldbody is not None:
        has_floor = any(
            g.get("type") == "plane" for g in worldbody.findall("geom")
        )
        if not has_floor:
            floor = ET.SubElement(worldbody, "geom")
            floor.set("name", "floor")
            floor.set("type", "plane")
            floor.set("size", "100 100 0.05")
            floor.set("condim", "6")
            floor.set("friction", "0.8 0.02 0.01")

            light = ET.SubElement(worldbody, "light")
            light.set("pos", "0 0 3")
            light.set("dir", "0 0 -1")
            light.set("directional", "true")

    # Add a forward-facing camera attached to the robot base body
    worldbody = root.find("worldbody")
    if worldbody is not None:
        base_body = worldbody.find("body")  # first body = robot base
        if base_body is not None:
            # Check if camera already exists
            has_cam = any(c.get("name") == "front_cam" for c in base_body.findall("camera"))
            if not has_cam:
                cam = ET.SubElement(base_body, "camera")
                cam.set("name", "front_cam")
                cam.set("pos", "0.3 0 0.05")  # front of robot, slightly above center
                cam.set("xyaxes", "0 -1 0 0 0 1")  # looking forward
                cam.set("fovy", "45")

    # Add visual settings for depth rendering (znear/zfar)
    # Without these, MuJoCo's depth buffer returns all zeros
    visual = root.find("visual")
    if visual is None:
        visual = ET.SubElement(root, "visual")
    map_elem = visual.find("map")
    if map_elem is None:
        map_elem = ET.SubElement(visual, "map")
    map_elem.set("znear", "0.01")
    map_elem.set("zfar", "50")

    # Add statistic extent for proper depth scaling
    stat = root.find("statistic")
    if stat is None:
        stat = ET.SubElement(root, "statistic")
    stat.set("extent", "2")

    return ET.tostring(root, encoding="unicode")
