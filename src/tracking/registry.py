"""TrackerRegistry: decorator-based registration with lazy loading.

Simpler than DetectorRegistry (no D-05/D-06 capability validation machinery) —
trackers only need framework + produces_stable_ids + license. Mirrors
src/slam/registry.py shape. Follows Pitfall P9: module-scope imports are
stdlib only.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


_REQUIRED_CAPABILITIES = ("framework", "produces_stable_ids", "license")


class TrackerRegistry:
    """Class-path registry for tracker backends.

    Registration pattern:
        @tracker(name="none", display="Passthrough (no tracking)")
        class NoneTracker:
            CAPABILITIES = {"framework": "stub", "produces_stable_ids": False, "license": "MIT"}
            ...
    """

    _backends: dict[str, dict[str, Any]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        display: str,
        class_path: str,
        capabilities: dict,
        available: bool = True,
        install_hint: str | None = None,
    ) -> None:
        """Register a tracker backend. Called by the @tracker decorator."""
        missing = [k for k in _REQUIRED_CAPABILITIES if k not in capabilities]
        if missing:
            raise ValueError(
                f"Tracker '{name}' missing CAPABILITIES keys: {sorted(missing)}. "
                f"Required: {list(_REQUIRED_CAPABILITIES)}."
            )
        cls._backends[name] = {
            "name": name,
            "display": display,
            "class_path": class_path,
            "capabilities": dict(capabilities),
            "available": available,
            "install_hint": install_hint,
            "parameter_schema": {},
        }
        logger.debug("Registered tracker: %s (%s)", name, class_path)

    @classmethod
    def list_backends(cls) -> list[dict[str, Any]]:
        """Return sorted backend metadata list.

        Each entry: {name, display, available, install_hint, capabilities,
        parameter_schema}. Sorted by name for deterministic ordering.
        """
        return [
            {
                "name": meta["name"],
                "display": meta["display"],
                "available": meta["available"],
                "install_hint": meta["install_hint"],
                "capabilities": dict(meta["capabilities"]),
                "parameter_schema": dict(meta["parameter_schema"]),
            }
            for meta in sorted(cls._backends.values(), key=lambda m: m["name"])
        ]

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> Any:
        """Instantiate a tracker by registered name. Raises ValueError if unknown."""
        if name not in cls._backends:
            raise ValueError(
                f"Unknown tracker: {name!r}. Available: "
                f"{sorted(cls._backends.keys())}"
            )
        meta = cls._backends[name]
        module_path, _, class_name = meta["class_path"].rpartition(".")
        module = importlib.import_module(module_path)
        klass = getattr(module, class_name)
        return klass(**kwargs)

    @classmethod
    def get_default(cls) -> str:
        """Return the default tracker name. 'none' per CONTEXT D-13."""
        return "none"

    @classmethod
    def _clear(cls) -> None:
        """Test-only: wipe registry (re-import tracker modules to repopulate)."""
        cls._backends = {}


def tracker(name: str, display: str, install_hint: str | None = None):
    """Decorator: register a class in TrackerRegistry.

    Usage:
        @tracker(name="none", display="Passthrough (no tracking)")
        class NoneTracker:
            CAPABILITIES = {...}
            ...
    """

    def _decorate(klass: type) -> type:
        caps = getattr(klass, "CAPABILITIES", None)
        if not isinstance(caps, dict):
            raise ValueError(
                f"Tracker '{name}' ({klass.__qualname__}) must declare CAPABILITIES dict."
            )
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        TrackerRegistry.register(
            name=name,
            display=display,
            class_path=class_path,
            capabilities=caps,
            available=True,
            install_hint=install_hint,
        )
        return klass

    return _decorate
