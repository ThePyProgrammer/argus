"""Integration tests for FastAPI WebSocket server.

Tests WebSocket connection, robot_list handshake, and command dispatch.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.web.server import create_app


class TestWebSocketServer:
    def test_ws_connect_receives_robot_list(self):
        """Connect to /ws and verify robot_list message is sent."""
        app, viz = create_app(["robot_a", "robot_b"])
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "robot_list"
            assert data["payload"]["robots"] == ["robot_a", "robot_b"]

    def test_command_handling(self):
        """Send command via WebSocket and verify callback invoked."""
        callback = MagicMock()
        app, viz = create_app(["robot_a"], command_cb=callback)
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            # Consume the initial robot_list message
            ws.receive_json()
            # Send a command
            ws.send_json({"type": "command", "payload": {"action": "stop"}})
            # Give server a moment to process -- close triggers processing
        # The command_callback should have been called
        callback.assert_called_once_with({"action": "stop"})
