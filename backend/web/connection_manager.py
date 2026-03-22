"""WebSocket connection manager for broadcast-based client communication.

Tracks active WebSocket connections and provides broadcast methods
for both JSON and binary payloads. Dead connections are silently
removed on send failure.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast_json(self, data: dict[str, Any]) -> None:
        """Send JSON data to all connected clients. Dead connections are removed."""
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning("Failed to send JSON to client, removing")
                self.disconnect(ws)

    async def broadcast_bytes(self, data: bytes) -> None:
        """Send binary data to all connected clients. Dead connections are removed."""
        for ws in list(self.active):
            try:
                await ws.send_bytes(data)
            except Exception:
                logger.warning("Failed to send bytes to client, removing")
                self.disconnect(ws)
