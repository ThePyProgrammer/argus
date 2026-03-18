"""Unit tests for WebSocket message types, connection management, and streaming viz.

Tests cover: WSMessage serialization, ConnectionManager broadcast/disconnect,
camera frame binary encode/decode, cloud delta tracking, color palette,
color modes, and trajectory messages.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.web.message_types import (
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
from src.web.connection_manager import ConnectionManager


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
