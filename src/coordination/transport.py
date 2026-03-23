"""In-process pub/sub transport for robot-coordinator communication.

Replaces the dimos pLCMTransport dependency with a lightweight callback-based
implementation. All robots and the coordinator run in the same process, so
no serialization or networking is needed.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class InProcessTransport:
    """Simple in-process pub/sub transport matching the pLCMTransport interface.

    Supports broadcast (publish) and subscribe with topic-based routing.
    Messages are delivered synchronously to all subscribers.
    """

    def __init__(self, topic: str):
        self._topic = topic
        self._subscribers: list[Callable] = []
        self._running = False

    @property
    def topic(self) -> str:
        return self._topic

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._subscribers.clear()

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        self._subscribers.append(callback)

    def broadcast(self, _channel: Any, msg: Any) -> None:
        if not self._running:
            logger.warning("broadcast on stopped transport %s", self._topic)
            return
        for cb in self._subscribers:
            cb(msg)


# Drop-in alias so existing imports keep working
pLCMTransport = InProcessTransport
