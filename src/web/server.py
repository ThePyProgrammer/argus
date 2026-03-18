"""FastAPI application with WebSocket endpoint for C2 interface.

Provides /ws endpoint for real-time robot data streaming and
command reception. Uses ConnectionManager for client tracking
and WebStreamingViz for data serialization.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from src.web.connection_manager import ConnectionManager
from src.web.streaming_viz import WebStreamingViz

logger = logging.getLogger(__name__)

# Module-level state (set by create_app)
manager = ConnectionManager()
streaming_viz: WebStreamingViz | None = None
command_callback: Callable[[dict[str, Any]], None] | None = None
_robot_ids: list[str] = []

app = FastAPI(title="C2 Interface")


def create_app(
    robot_ids: list[str],
    command_cb: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[FastAPI, WebStreamingViz]:
    """Create and configure the FastAPI application.

    Args:
        robot_ids: List of robot identifiers to manage.
        command_cb: Optional callback for command messages received on WebSocket.

    Returns:
        Tuple of (FastAPI app, WebStreamingViz instance).
    """
    global manager, streaming_viz, command_callback, _robot_ids
    manager = ConnectionManager()
    streaming_viz = WebStreamingViz(manager, robot_ids)
    command_callback = command_cb
    _robot_ids = robot_ids
    return app, streaming_viz


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connections for real-time data streaming.

    On connect: sends robot_list message.
    Loop: receives JSON messages; dispatches commands to callback.
    On disconnect: removes client from manager.
    """
    await manager.connect(websocket)
    try:
        # Send robot list on connect
        await websocket.send_json({
            "type": "robot_list",
            "payload": {"robots": _robot_ids},
        })
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "command" and command_callback is not None:
                command_callback(data.get("payload", {}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def push_loop(interval: float = 0.1) -> None:
    """Background task that drains streaming_viz messages and broadcasts.

    Runs every `interval` seconds, pulling pending messages from
    WebStreamingViz and broadcasting to all connected clients.

    Args:
        interval: Seconds between push cycles (default 100ms).
    """
    while True:
        if streaming_viz is not None:
            messages = streaming_viz.get_pending_messages()
            for msg in messages:
                if isinstance(msg, dict):
                    await manager.broadcast_json(msg)
                elif isinstance(msg, bytes):
                    await manager.broadcast_bytes(msg)
        await asyncio.sleep(interval)
