"""FastAPI application with WebSocket endpoint for Argus interface.

Provides /ws endpoint for real-time robot data streaming and
command reception. Uses ConnectionManager for client tracking
and WebStreamingViz for data serialization. Serves React frontend
build as static files at /.
"""


import asyncio
import logging
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend.web.connection_manager import ConnectionManager
from backend.web.streaming_viz import WebStreamingViz
from src.slam.registry import SLAMRegistry

logger = logging.getLogger(__name__)

app = FastAPI(title="Argus")


def create_app(
    robot_ids: list[str],
    command_cb: Callable[[dict[str, Any]], None] | None = None,
    slam_reset_cb: Callable[[], None] | None = None,
    mcp_endpoint: Callable | None = None,
    cloud_config_fns: dict[str, Callable] | None = None,
) -> tuple[FastAPI, WebStreamingViz]:
    """Configure and return the FastAPI app.

    Stores all shared state on app.state instead of module-level globals.

    Args:
        robot_ids: List of robot identifiers.
        command_cb: Callback for command messages from WebSocket clients.
        slam_reset_cb: Callback to reset SLAM/OctoMap when cloud config changes.
        mcp_endpoint: Optional MCP endpoint handler to register at /mcp.
        cloud_config_fns: Optional dict with 'get', 'set', 'configs' callables
            for cloud configuration. Injected to avoid importing from src/.

    Returns:
        Tuple of (FastAPI app, WebStreamingViz instance).
    """
    app.state.manager = ConnectionManager()
    app.state.streaming_viz = WebStreamingViz(app.state.manager, robot_ids)
    app.state.command_callback = command_cb
    app.state.slam_reset_callback = slam_reset_cb
    app.state.robot_ids = robot_ids
    app.state.cloud_config_fns = cloud_config_fns

    # SLAM backend selection state
    app.state.active_slam_backend = "icp"
    app.state.pending_slam_backend = None
    app.state.pending_slam_params = {}

    # Wire SLAM REST API routes
    from backend.web.slam_routes import router as slam_router
    app.include_router(slam_router)

    # Wire pipeline configuration routes
    from backend.web.pipeline_routes import router as pipeline_router
    app.include_router(pipeline_router)

    if mcp_endpoint is not None:
        app.post("/mcp")(mcp_endpoint)

    return app, app.state.streaming_viz


def _mount_static_dirs() -> None:
    """Mount static file directories for frontend assets."""
    project_root = Path(__file__).parent.parent.parent

    scene_dir = project_root / "dimos" / "data" / "mujoco_sim" / "scene_office1"
    if scene_dir.exists():
        try:
            app.mount("/scene-data", StaticFiles(directory=str(scene_dir)), name="scene_assets")
        except Exception:
            logger.warning("Failed to mount scene data from %s", scene_dir)

    frontend_dir = project_root / "frontend" / "dist"
    if frontend_dir.exists():
        try:
            app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        except Exception:
            logger.warning("Failed to mount frontend from %s", frontend_dir)


async def _dispatch_ws_message(data: dict, websocket: WebSocket) -> None:
    """Route an incoming WebSocket message to the appropriate handler."""
    state = websocket.app.state
    msg_type = data.get("type")
    if msg_type == "command" and state.command_callback is not None:
        state.command_callback(data.get("payload", {}))
    elif msg_type == "set_cloud_config" and state.cloud_config_fns is not None:
        key = data.get("config", "1")
        state.cloud_config_fns["set"](key)
        configs = state.cloud_config_fns["configs"]()
        label = configs.get(key, {}).get("label", key)
        logger.info("Cloud config switched to %s: %s", key, label)
        if state.streaming_viz is not None:
            state.streaming_viz.reset_cloud_tracking()
        if state.slam_reset_callback is not None:
            state.slam_reset_callback()
        await websocket.send_json({
            "type": "cloud_config_ack",
            "payload": {"config": key, "label": label},
        })
    elif msg_type == "set_color_mode":
        mode = data.get("mode", "robot_tint")
        if state.streaming_viz is not None:
            state.streaming_viz.set_color_mode(mode)
            state.streaming_viz.reset_cloud_tracking()
            logger.info("Color mode switched to %s", mode)
        await websocket.send_json({
            "type": "color_mode_ack",
            "payload": {"mode": mode},
        })
    elif msg_type == "slam_param_update":
        param = data.get("param")
        value = data.get("value")
        active = getattr(state, "active_slam_backend", SLAMRegistry.get_default())
        backends = {b["name"]: b for b in SLAMRegistry.list_backends()}
        info = backends.get(active, {})
        schema_props = info.get("parameter_schema", {}).get("properties", {})

        if param not in schema_props:
            await websocket.send_json({
                "type": "slam_param_ack",
                "payload": {"param": param, "status": "unknown_parameter"},
            })
        elif schema_props[param].get("live_tunable", False):
            # Store the live update for the coordinator to pick up
            pending = getattr(state, "pending_slam_params", {})
            pending[param] = value
            state.pending_slam_params = pending
            logger.info("Live param update: %s = %s", param, value)
            await websocket.send_json({
                "type": "slam_param_ack",
                "payload": {"param": param, "status": "applied", "value": value},
            })
        else:
            await websocket.send_json({
                "type": "slam_param_ack",
                "payload": {"param": param, "status": "requires_restart"},
            })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connections for real-time data streaming.

    On connect: sends robot_list message.
    Loop: receives JSON messages; dispatches commands to callback.
    On disconnect: removes client from manager.
    """
    state = websocket.app.state
    manager = state.manager
    await manager.connect(websocket)
    try:
        # Send robot list on connect
        await websocket.send_json({
            "type": "robot_list",
            "payload": {"robots": state.robot_ids},
        })
        # Send available cloud configs if configured
        if state.cloud_config_fns is not None:
            configs = state.cloud_config_fns["configs"]()
            active = state.cloud_config_fns["get"]()
            await websocket.send_json({
                "type": "cloud_configs",
                "payload": {
                    "configs": {k: v["label"] for k, v in configs.items()},
                    "active": active,
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
                    await _dispatch_ws_message(data, websocket)
                except (json.JSONDecodeError, TypeError):
                    logger.debug("Ignoring malformed WebSocket text message")
            elif "bytes" in message:
                pass  # Binary messages from client not expected
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.warning("WebSocket error: %s", e)
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup() -> None:
    """Mount static dirs (after routes) and start push loop."""
    _mount_static_dirs()
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
        streaming_viz = getattr(app.state, "streaming_viz", None)
        if streaming_viz is not None:
            messages = streaming_viz.drain_pending_messages()
            manager = app.state.manager
            for msg in messages:
                if isinstance(msg, bytes):
                    await manager.broadcast_bytes(msg)
                else:
                    await manager.broadcast_json(msg)
