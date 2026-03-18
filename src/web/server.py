"""FastAPI application with WebSocket endpoint for C2 interface.

Provides /ws endpoint for real-time robot data streaming and
command reception. Uses ConnectionManager for client tracking
and WebStreamingViz for data serialization. Serves React frontend
build as static files at /.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

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

    Sets up WebSocket endpoint, static file serving for the React
    frontend build, and scene asset directories.

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

    # Serve scene assets from DimOS data directory
    scene_dir = Path(__file__).parent.parent.parent / "dimos" / "data" / "mujoco_sim" / "scene_office1"
    if scene_dir.exists():
        app.mount("/scene-data", StaticFiles(directory=str(scene_dir)), name="scene_assets")

    # Serve GLB and other public assets from the frontend public directory
    glb_dir = Path(__file__).parent.parent / "c2-frontend" / "public"
    if glb_dir.exists():
        app.mount("/public", StaticFiles(directory=str(glb_dir)), name="glb_assets")

    # Serve React frontend build as static files (must be last mount -- catch-all)
    frontend_dir = Path(__file__).parent.parent / "c2-frontend" / "dist"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

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
        # Send available cloud configs
        from src.slam.depth_to_cloud import CLOUD_CONFIGS, get_active_config
        await websocket.send_json({
            "type": "cloud_configs",
            "payload": {
                "configs": {k: v["label"] for k, v in CLOUD_CONFIGS.items()},
                "active": get_active_config(),
            },
        })
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message:
                import json
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "command" and command_callback is not None:
                        command_callback(data.get("payload", {}))
                    elif data.get("type") == "set_cloud_config":
                        from src.slam.depth_to_cloud import set_active_config, get_active_config, CLOUD_CONFIGS
                        key = data.get("config", "G")
                        set_active_config(key)
                        label = CLOUD_CONFIGS.get(key, {}).get("label", key)
                        logger.info("Cloud config switched to %s: %s", key, label)
                        # Clear accumulated SLAM data so new config takes effect
                        if streaming_viz is not None:
                            streaming_viz._last_voxel_set = set()
                        # Send acknowledgment
                        await websocket.send_json({
                            "type": "cloud_config_ack",
                            "payload": {"config": key, "label": label},
                        })
                except (json.JSONDecodeError, TypeError):
                    pass
            elif "bytes" in message:
                pass  # Binary messages from client not expected
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
        manager.disconnect(websocket)


@app.on_event("startup")
async def start_push_loop() -> None:
    """Register the push_loop as a background task on server startup."""
    asyncio.create_task(push_loop())


async def push_loop(interval: float = 0.1) -> None:
    """Background task that drains streaming_viz messages and broadcasts.

    Runs every `interval` seconds, pulling pending messages from
    WebStreamingViz and broadcasting to all connected clients.

    Args:
        interval: Seconds between push cycles (default 100ms).
    """
    while True:
        await asyncio.sleep(interval)
        if streaming_viz is not None:
            messages = streaming_viz.get_pending_messages()
            for msg in messages:
                if isinstance(msg, bytes):
                    await manager.broadcast_bytes(msg)
                else:
                    await manager.broadcast_json(msg)
