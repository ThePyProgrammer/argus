"""MCP server exposing robot skills to Claude Code.

Provides tools that Claude Code can call to control robots:
- get_status: Current robot positions, coverage, step count
- get_detections: Latest YOLO detections per robot
- get_scene_description: VLM scene description per robot
- send_command: Pause/resume/stop/set_speed
- get_coverage: Current exploration coverage stats

Runs as a FastAPI HTTP endpoint at /mcp alongside the Argus WebSocket.

Protocol: JSON-RPC 2.0 (same as DimOS MCP server)
"""


import json
import logging
from typing import Any, TYPE_CHECKING

from fastapi import Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from src.coordination.coordinator import Coordinator

logger = logging.getLogger(__name__)

# Module-level state, set by configure()
_coordinator: "Coordinator | None" = None
_robot_ids: list[str] = []


def configure(coordinator: "Coordinator", robot_ids: list[str]) -> None:
    """Set the coordinator reference for MCP tool calls."""
    global _coordinator, _robot_ids
    _coordinator = coordinator
    _robot_ids = robot_ids


# Tool definitions (exposed to Claude Code)
TOOLS = [
    {
        "name": "get_status",
        "description": "Get current status of all robots: positions, step count, coverage, merge count.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_detections",
        "description": "Get latest YOLO object detections for a robot. Returns class names, confidence, and 3D positions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "robot_id": {"type": "string", "description": "Robot ID (e.g., 'robot_a')"},
            },
            "required": ["robot_id"],
        },
    },
    {
        "name": "get_scene_description",
        "description": "Get VLM-generated scene description for a robot -- what the robot currently sees.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "robot_id": {"type": "string", "description": "Robot ID"},
            },
            "required": ["robot_id"],
        },
    },
    {
        "name": "send_command",
        "description": "Send a control command to the simulation: pause, resume, stop, or set_speed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["pause", "resume", "stop", "set_speed"],
                    "description": "Command action",
                },
                "value": {"type": "number", "description": "Speed value (for set_speed)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_coverage",
        "description": "Get exploration coverage statistics: per-robot voxel counts, merge count, total steps.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def _handle_tool_call(name: str, arguments: dict) -> str:
    """Execute a tool call and return the result as a string."""
    if _coordinator is None:
        return json.dumps({"error": "Coordinator not initialized"})

    if name == "get_status":
        status: dict[str, Any] = {
            "step": _coordinator.step_count,
            "merge_count": _coordinator.merge_count,
            "robots": {},
        }
        for rid in _robot_ids:
            status["robots"][rid] = _coordinator.get_robot_status(rid)
        return json.dumps(status)

    elif name == "get_detections":
        rid = arguments.get("robot_id", "robot_a")
        # Phase 2 D-18 cutover: coordinator.detector now exposes the DetectorWorkerPool.
        # ``latest(rid)`` returns a Detections3D envelope (or None); serialize via
        # to_wire() so MCP clients see the Phase 2 3D schema directly.
        pool = _coordinator.detector
        if pool is not None:
            envelope = pool.latest(rid)
            if envelope is not None:
                return json.dumps(envelope.to_wire())
        return json.dumps([])

    elif name == "get_scene_description":
        rid = arguments.get("robot_id", "robot_a")
        if _coordinator.describer is not None:
            desc = _coordinator.describer.get_description(rid)
            if desc:
                return json.dumps({"description": desc.description, "objects": desc.objects})
        return json.dumps({"description": "No description available", "objects": []})

    elif name == "send_command":
        action = arguments.get("action", "")
        value = arguments.get("value")
        cmd: dict[str, Any] = {"action": action}
        if value is not None:
            cmd["value"] = value
        _coordinator.handle_command(cmd)
        return json.dumps({"status": "ok", "action": action})

    elif name == "get_coverage":
        result: dict[str, Any] = {
            "step": _coordinator.step_count,
            "merge_count": _coordinator.merge_count,
            "per_robot": {},
        }
        for rid in _robot_ids:
            result["per_robot"][rid] = _coordinator.get_robot_coverage(rid)
        return json.dumps(result)

    return json.dumps({"error": f"Unknown tool: {name}"})


async def mcp_endpoint(request: Request) -> JSONResponse:
    """Handle MCP JSON-RPC 2.0 requests."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})

    method = body.get("method", "")
    req_id = body.get("id")
    params = body.get("params", {})

    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2025-11-25",
                "serverInfo": {"name": "dimensional-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
            "id": req_id,
        })

    elif method == "tools/list":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {"tools": TOOLS},
            "id": req_id,
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result_text = _handle_tool_call(tool_name, arguments)
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": result_text}],
            },
            "id": req_id,
        })

    return JSONResponse({
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
        "id": req_id,
    })
