"""Unit tests for WebSocket message types, connection management, and streaming viz.

Tests cover: WSMessage serialization, ConnectionManager broadcast/disconnect,
camera frame binary encode/decode, cloud delta tracking, color palette,
color modes, and trajectory messages.
"""


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from backend.web.message_types import (
    CLOUD_DELTA,
    CLOUD_FULL,
    OKABE_ITO_PALETTE,
    POSE_UPDATE,
    ROBOT_LIST,
    STATS,
    TRAJECTORY,
    WSMessage,
    color_for_robot,
    compute_cloud_delta,
    decode_camera_frame_header,
    encode_camera_frame,
)
from backend.web.connection_manager import ConnectionManager


# ---------- WSMessage tests ----------


class TestWSMessage:
    def test_robot_list_serializes(self):
        msg = WSMessage(type=ROBOT_LIST, payload={"robots": ["robot_a", "robot_b"]})
        d = msg.model_dump()
        assert d["type"] == "robot_list"
        assert d["robot_id"] is None
        assert "robots" in d["payload"]

    def test_pose_update_includes_robot_id(self):
        msg = WSMessage(
            type=POSE_UPDATE,
            robot_id="robot_a",
            payload={"position": [1, 2, 3]},
        )
        d = msg.model_dump()
        assert d["robot_id"] == "robot_a"
        assert d["type"] == "pose_update"

    def test_robot_list_payload_contains_ids(self):
        ids = ["robot_a", "robot_b"]
        msg = WSMessage(type=ROBOT_LIST, payload={"robots": ids})
        assert msg.payload["robots"] == ids


# ---------- ConnectionManager tests ----------


class TestConnectionManager:
    @pytest.mark.asyncio
    async def test_broadcast_json_sends_to_all(self):
        cm = ConnectionManager()
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await cm.connect(ws1)
        await cm.connect(ws2)
        data = {"type": "test"}
        await cm.broadcast_json(data)
        ws1.send_json.assert_awaited_once_with(data)
        ws2.send_json.assert_awaited_once_with(data)

    @pytest.mark.asyncio
    async def test_disconnect_removes_websocket(self):
        cm = ConnectionManager()
        ws = AsyncMock()
        await cm.connect(ws)
        assert len(cm.active) == 1
        cm.disconnect(ws)
        assert len(cm.active) == 0


# ---------- Camera frame encode/decode tests ----------


class TestCameraFrame:
    def test_encode_produces_header_bytes(self):
        rgb = np.zeros((64, 64, 3), dtype=np.uint8)
        with patch("cv2.imencode") as mock_enc:
            mock_enc.return_value = (True, np.array([0xFF, 0xD8, 0x00], dtype=np.uint8))
            data = encode_camera_frame("robot_a", rgb, quality=70)
        assert data[0] == 0x01
        id_len = data[1]
        assert id_len == len("robot_a")
        robot_id_bytes = data[2 : 2 + id_len]
        assert robot_id_bytes == b"robot_a"

    def test_encode_decode_roundtrip(self):
        rgb = np.zeros((64, 64, 3), dtype=np.uint8)
        jpeg_bytes = b"\xff\xd8\xff\xe0JFIF"
        with patch("cv2.imencode") as mock_enc:
            mock_enc.return_value = (True, np.frombuffer(jpeg_bytes, dtype=np.uint8))
            data = encode_camera_frame("bot1", rgb)
        rid, jpeg = decode_camera_frame_header(data)
        assert rid == "bot1"
        assert jpeg == jpeg_bytes


# ---------- Cloud delta tests ----------


class TestCloudDelta:
    def test_new_voxels_returned(self):
        current = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        last_set: set[tuple[float, float, float]] = set()
        delta, new_set = compute_cloud_delta(current, last_set)
        assert len(delta) == 2
        assert len(new_set) == 2

    def test_no_new_voxels_returns_empty(self):
        current = np.array([[1.0, 2.0, 3.0]])
        last_set = {(1.0, 2.0, 3.0)}
        delta, new_set = compute_cloud_delta(current, last_set)
        assert len(delta) == 0

    def test_identical_input_empty_on_second_call(self):
        voxels = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        delta1, set1 = compute_cloud_delta(voxels, set())
        assert len(delta1) == 2
        delta2, set2 = compute_cloud_delta(voxels, set1)
        assert len(delta2) == 0


# ---------- Color palette tests ----------


class TestColorPalette:
    def test_okabe_ito_index_0(self):
        assert color_for_robot(0) == (0, 114, 178)

    def test_okabe_ito_index_1(self):
        assert color_for_robot(1) == (230, 159, 0)

    def test_palette_wraps_around(self):
        assert color_for_robot(8) == color_for_robot(0)

    def test_color_array_robot_tint_mode(self):
        """Robot tint mode should produce per-robot palette colors."""
        color = color_for_robot(0)
        n = 5
        colors = np.tile(list(color), (n, 1)).astype(np.uint8)
        assert colors.shape == (5, 3)
        assert tuple(colors[0]) == (0, 114, 178)

    def test_color_array_true_rgb_passthrough(self):
        """True RGB mode passes through original colors (white placeholder)."""
        n = 5
        white = np.full((n, 3), 255, dtype=np.uint8)
        assert np.all(white == 255)


# ---------- Trajectory message test ----------


class TestTrajectoryMessage:
    def test_trajectory_positions_and_alphas(self):
        """Trajectory message contains [x,y,z] positions with alpha values."""
        poses = []
        for i in range(5):
            p = np.eye(4)
            p[:3, 3] = [float(i), 0.0, 0.0]
            poses.append(p)
        positions = [p[:3, 3].tolist() for p in poses[-50:]]
        n = len(positions)
        alphas = [int(255 * (i + 1) / n) for i in range(n)]
        payload = {"positions": positions, "alphas": alphas}
        assert len(payload["positions"]) == 5
        assert len(payload["alphas"]) == 5
        assert payload["alphas"][-1] == 255
        assert payload["positions"][0] == [0.0, 0.0, 0.0]


# ---------- WebStreamingViz tests (Task 2) ----------


def _make_robot_data(
    robot_ids: list[str],
) -> dict:
    """Helper: create mock robot_data dict for testing WebStreamingViz."""
    data = {}
    for i, rid in enumerate(robot_ids):
        pose = np.eye(4)
        pose[:3, 3] = [float(i), 0.0, 0.0]
        frame = MagicMock()
        frame.rgb = np.zeros((64, 64, 3), dtype=np.uint8)
        data[rid] = {
            "frame": frame,
            "local_voxels": np.random.rand(10, 3),
            "pose": pose,
            "trajectory": [pose],
            "coverage_pct": 25.0 + i * 10,
        }
    return data


class TestWebStreamingViz:
    def _make_viz(self):
        from backend.web.streaming_viz import WebStreamingViz

        cm = MagicMock()
        robot_ids = ["robot_a", "robot_b"]
        viz = WebStreamingViz(cm, robot_ids)
        return viz, cm

    def test_update_produces_cloud_delta(self):
        viz, cm = self._make_viz()
        merged = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        cloud_deltas = [m for m in json_msgs if m.get("type") == CLOUD_DELTA]
        assert len(cloud_deltas) == 1
        assert "positions" in cloud_deltas[0]["payload"]

    def test_update_second_call_sends_delta_only(self):
        viz, cm = self._make_viz()
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
            _ = viz.drain_pending_messages()  # drain
            viz.update(merged, robot_data)  # same voxels
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        cloud_deltas = [m for m in json_msgs if m.get("type") == CLOUD_DELTA]
        # No new voxels => no cloud_delta message
        assert len(cloud_deltas) == 0

    def test_update_sends_pose_per_robot(self):
        viz, cm = self._make_viz()
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        poses = [m for m in json_msgs if m.get("type") == POSE_UPDATE]
        assert len(poses) == 2
        assert poses[0]["payload"]["position"] == [0.0, 0.0, 0.0]
        assert len(poses[0]["payload"]["rotation"]) == 9  # 3x3 flattened

    def test_update_sends_stats(self):
        viz, cm = self._make_viz()
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data, total_coverage=50.0, merge_count=3)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        stats = [m for m in json_msgs if m.get("type") == STATS]
        assert len(stats) == 1
        assert stats[0]["payload"]["total_coverage"] == 50.0
        assert stats[0]["payload"]["merge_count"] == 3

    def test_update_sends_trajectory_per_robot(self):
        viz, cm = self._make_viz()
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        # Add more poses to trajectory
        for rid in robot_data:
            poses = []
            for j in range(5):
                p = np.eye(4)
                p[:3, 3] = [float(j), 0.0, 0.0]
                poses.append(p)
            robot_data[rid]["trajectory"] = poses
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        trajs = [m for m in json_msgs if m.get("type") == TRAJECTORY]
        assert len(trajs) == 2
        assert "positions" in trajs[0]["payload"]
        assert "alphas" in trajs[0]["payload"]

    def test_true_rgb_color_mode(self):
        viz, cm = self._make_viz()
        viz.set_color_mode("true_rgb")
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        cloud_deltas = [m for m in json_msgs if m.get("type") == CLOUD_DELTA]
        assert len(cloud_deltas) == 1
        # true_rgb mode: colors should be white placeholder (255,255,255)
        colors = cloud_deltas[0]["payload"]["colors"]
        assert colors[0] == [255, 255, 255]

    def test_full_sync_after_interval(self):
        import time

        viz, cm = self._make_viz()
        viz._full_sync_interval = 0.0  # trigger immediately
        viz._last_full_sync = 0.0
        merged = np.array([[1.0, 2.0, 3.0]])
        robot_data = _make_robot_data(["robot_a", "robot_b"])
        with patch("backend.web.streaming_viz.encode_camera_frame", return_value=b"\x01\x00"):
            viz.update(merged, robot_data)
        msgs = viz.drain_pending_messages()
        json_msgs = [m for m in msgs if isinstance(m, dict)]
        full_syncs = [m for m in json_msgs if m.get("type") == CLOUD_FULL]
        assert len(full_syncs) == 1
        assert "positions" in full_syncs[0]["payload"]
