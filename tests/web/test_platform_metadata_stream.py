from unittest.mock import MagicMock, patch

import numpy as np

from backend.web.streaming_viz import WebStreamingViz
from backend.web.message_types import STATS


def test_stats_payload_contains_platform_runtime_state():
    viz = WebStreamingViz(MagicMock(), ["robot_a"])
    pose = np.eye(4)
    frame = MagicMock()
    frame.rgb = np.zeros((16, 16, 3), dtype=np.uint8)
    frame.depth = None
    robot_data = {
        "robot_a": {
            "frame": frame,
            "local_voxels": np.zeros((2, 3)),
            "pose": pose,
            "trajectory": [pose],
            "coverage_pct": 12.5,
            "platform": {"name": "agibot_x2", "display_name": "AGIBOT X2 Ultra"},
            "runtime_status": {
                "state": "walking",
                "fall_reason": "none",
                "disabled": False,
                "controller_health": {"policy_loaded": True},
                "collision_count": 0,
                "near_miss_count": 1,
            },
        }
    }

    with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
        viz.update(np.zeros((0, 3)), robot_data)

    stats = [m for m in viz.drain_pending_messages() if isinstance(m, dict) and m.get("type") == STATS][0]

    assert stats["payload"]["robots"]["robot_a"]["platform"]["name"] == "agibot_x2"
    assert stats["payload"]["robots"]["robot_a"]["runtime_status"]["state"] == "walking"
    assert stats["payload"]["robots"]["robot_a"]["runtime_status"]["near_miss_count"] == 1
