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
    "abduction": {"kp": "40", "kv": "2"},
    "hip": {"kp": "40", "kv": "2"},
    "knee": {"kp": "60", "kv": "3"},
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
