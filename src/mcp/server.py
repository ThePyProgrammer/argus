"""MCP server exposing robot skills to Claude Code.

Provides tools that Claude Code can call to control robots:
- get_status: Current robot positions, coverage, step count
- get_detections: Latest YOLO detections per robot
- get_scene_description: VLM scene description per robot
- send_command: Pause/resume/stop/set_speed
- get_coverage: Current exploration coverage stats

Runs as a FastAPI HTTP endpoint at /mcp alongside the C2 WebSocket.

Protocol: JSON-RPC 2.0 (same as DimOS MCP server)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Module-level state, set by configure()
_coordinator = None
_robot_ids: list[str] = []


def configure(coordinator: Any, robot_ids: list[str]) -> None:
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
        status = {
            "step": _coordinator.step_count,
            "merge_count": _coordinator.merge_count,
            "robots": {},
        }
        for rid in _robot_ids:
            robot = _coordinator.robots.get(rid)
            if robot and robot.slam.slam_poses:
                pos = robot.slam.slam_poses[-1][:3, 3].tolist()
            else:
                pos = [0, 0, 0]
            status["robots"][rid] = {
                "position": pos,
                "voxels": robot.octomap.num_occupied if robot else 0,
            }
        return json.dumps(status)

    elif name == "get_detections":
        rid = arguments.get("robot_id", "robot_a")
        if _coordinator.detector is not None:
            dets = _coordinator.detector.get_detections(rid)
            return json.dumps([
                {"class": d.class_name, "confidence": round(d.confidence, 2),
                 "bbox": list(d.bbox),
                 "pos_3d": d.center_3d.tolist() if d.center_3d is not None else None}
                for d in dets
            ])
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
        cmd = {"action": action}
        if value is not None:
            cmd["value"] = value
        _coordinator.handle_command(cmd)
        return json.dumps({"status": "ok", "action": action})

    elif name == "get_coverage":
        result = {
            "step": _coordinator.step_count,
            "merge_count": _coordinator.merge_count,
            "per_robot": {},
        }
        for rid in _robot_ids:
            robot = _coordinator.robots.get(rid)
            result["per_robot"][rid] = {
                "voxels": robot.octomap.num_occupied if robot else 0,
                "slam_frames": robot.slam.num_frames_processed if robot else 0,
            }
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
