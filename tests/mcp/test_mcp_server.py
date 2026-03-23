"""Tests for src/mcp/server.py -- JSON-RPC MCP endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.mcp import server as mcp_server


# ------------------------------------------------------------------ #
# Mock Coordinator
# ------------------------------------------------------------------ #


class MockCoordinator:
    """Lightweight mock matching the Coordinator public API used by MCP server."""

    def __init__(self):
        self.step_count = 42
        self.merge_count = 3
        self.robots = {"robot_a": MagicMock(), "robot_b": MagicMock()}
        self.detector = None
        self.describer = None
        self._last_command = None

    def handle_command(self, command: dict) -> None:
        self._last_command = command

    def get_robot_status(self, rid: str) -> dict:
        return {"position": [1.0, 2.0, 0.3], "voxels": 500}

    def get_robot_coverage(self, rid: str) -> dict:
        return {"voxels": 500, "slam_frames": 100}


@pytest.fixture(autouse=True)
def _configure_mcp():
    """Configure the MCP server module with a mock coordinator before each test."""
    coordinator = MockCoordinator()
    mcp_server.configure(coordinator, ["robot_a", "robot_b"])
    yield
    # Reset module state
    mcp_server._coordinator = None
    mcp_server._robot_ids = []


# ------------------------------------------------------------------ #
# Helper to call the endpoint
# ------------------------------------------------------------------ #


async def _call(body: dict) -> dict:
    """Send a JSON-RPC request to the MCP endpoint and return the parsed response."""
    request = MagicMock()
    request.json = AsyncMock(return_value=body)
    response = await mcp_server.mcp_endpoint(request)
    return json.loads(response.body.decode())


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestMCPInitialize:
    """Test the initialize JSON-RPC method."""

    @pytest.mark.asyncio
    async def test_initialize_returns_protocol_version(self):
        """initialize returns protocolVersion and capabilities."""
        result = await _call({"jsonrpc": "2.0", "method": "initialize", "id": 1})

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert "protocolVersion" in result["result"]
        assert "capabilities" in result["result"]
        assert "tools" in result["result"]["capabilities"]


class TestMCPToolsList:
    """Test the tools/list JSON-RPC method."""

    @pytest.mark.asyncio
    async def test_tools_list_returns_all_five_tools(self):
        """tools/list returns exactly 5 tools."""
        result = await _call({"jsonrpc": "2.0", "method": "tools/list", "id": 2})

        tools = result["result"]["tools"]
        assert len(tools) == 5

        tool_names = {t["name"] for t in tools}
        assert tool_names == {
            "get_status", "get_detections", "get_scene_description",
            "send_command", "get_coverage",
        }


class TestMCPToolsCall:
    """Test the tools/call JSON-RPC method for each tool."""

    @pytest.mark.asyncio
    async def test_get_status_returns_robot_positions(self):
        """get_status returns step count, merge count, and per-robot data."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "get_status", "arguments": {}},
            "id": 3,
        })

        content = result["result"]["content"]
        assert len(content) == 1
        data = json.loads(content[0]["text"])

        assert data["step"] == 42
        assert data["merge_count"] == 3
        assert "robot_a" in data["robots"]
        assert "robot_b" in data["robots"]
        assert data["robots"]["robot_a"]["position"] == [1.0, 2.0, 0.3]

    @pytest.mark.asyncio
    async def test_send_command_dispatches_to_coordinator(self):
        """send_command forwards the action to coordinator.handle_command."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "send_command", "arguments": {"action": "pause"}},
            "id": 4,
        })

        content = result["result"]["content"]
        data = json.loads(content[0]["text"])
        assert data["status"] == "ok"
        assert data["action"] == "pause"

        # Verify the coordinator received the command
        assert mcp_server._coordinator._last_command == {"action": "pause"}

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Calling an unknown tool returns an error message in the result."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
            "id": 5,
        })

        content = result["result"]["content"]
        data = json.loads(content[0]["text"])
        assert "error" in data
        assert "nonexistent_tool" in data["error"]

    @pytest.mark.asyncio
    async def test_get_coverage_returns_per_robot_data(self):
        """get_coverage returns step, merge_count, and per-robot coverage."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "get_coverage", "arguments": {}},
            "id": 6,
        })

        content = result["result"]["content"]
        data = json.loads(content[0]["text"])
        assert data["step"] == 42
        assert data["merge_count"] == 3
        assert "robot_a" in data["per_robot"]
        assert data["per_robot"]["robot_a"]["voxels"] == 500

    @pytest.mark.asyncio
    async def test_get_detections_no_detector(self):
        """get_detections returns empty list when detector is None."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "get_detections", "arguments": {"robot_id": "robot_a"}},
            "id": 7,
        })

        content = result["result"]["content"]
        data = json.loads(content[0]["text"])
        assert data == []

    @pytest.mark.asyncio
    async def test_get_scene_description_no_describer(self):
        """get_scene_description returns fallback when describer is None."""
        result = await _call({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "get_scene_description", "arguments": {"robot_id": "robot_a"}},
            "id": 8,
        })

        content = result["result"]["content"]
        data = json.loads(content[0]["text"])
        assert data["description"] == "No description available"
        assert data["objects"] == []


class TestMCPMalformedRequest:
    """Test error handling for invalid requests."""

    @pytest.mark.asyncio
    async def test_malformed_json_returns_parse_error(self):
        """Malformed JSON body returns JSON-RPC parse error (-32700)."""
        request = MagicMock()
        request.json = AsyncMock(side_effect=Exception("Invalid JSON"))
        response = await mcp_server.mcp_endpoint(request)
        data = json.loads(response.body.decode())

        assert data["error"]["code"] == -32700
        assert "Parse error" in data["error"]["message"]

    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self):
        """Unknown JSON-RPC method returns -32601 error."""
        result = await _call({
            "jsonrpc": "2.0", "method": "nonexistent/method", "id": 99,
        })

        assert "error" in result
        assert result["error"]["code"] == -32601
