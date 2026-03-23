"""In-process pub/sub transport for robot-coordinator communication.

Replaces the dimos pLCMTransport dependency with a lightweight callback-based
implementation. All robots and the coordinator run in the same process, so
no serialization or networking is needed.

Uses a global topic registry so that separate InProcessTransport instances
on the same topic share subscribers — a publisher on topic X reaches all
subscribers on topic X regardless of which instance they registered on.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Global registry: topic -> list of callbacks
_topic_registry: dict[str, list[Callable]] = {}


class InProcessTransport:
    """In-process pub/sub transport with global topic registry.

    Multiple instances on the same topic share a single subscriber list,
    so a broadcast from any instance reaches all subscribers on that topic.
    """

    def __init__(self, topic: str):
        self._topic = topic
        self._running = False
        self._own_callbacks: list[Callable] = []
        if topic not in _topic_registry:
            _topic_registry[topic] = []

    @property
    def topic(self) -> str:
        return self._topic

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False
        # Remove only this instance's callbacks from the global registry
        topic_cbs = _topic_registry.get(self._topic, [])
        for cb in self._own_callbacks:
            try:
                topic_cbs.remove(cb)
            except ValueError:
                pass
        self._own_callbacks.clear()

    def subscribe(self, callback: Callable[[Any], None]) -> None:
        _topic_registry[self._topic].append(callback)
        self._own_callbacks.append(callback)

    def broadcast(self, _channel: Any, msg: Any) -> None:
        if not self._running:
            logger.warning("broadcast on stopped transport %s", self._topic)
            return
        for cb in _topic_registry.get(self._topic, []):
            cb(msg)


def clear_registry() -> None:
    """Clear all topics and subscribers. Useful for test teardown."""
    _topic_registry.clear()


# Drop-in alias so existing imports keep working
pLCMTransport = InProcessTransport
