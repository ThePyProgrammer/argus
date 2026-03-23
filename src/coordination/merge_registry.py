"""Merge strategy registry with decorator-based discovery.

Strategies register themselves via the @merge_strategy decorator. The registry
supports lazy loading (strategies are imported only when instantiated or
listed) and provides a standard create() factory.

Mirrors src/slam/registry.py pattern with "strategies" naming.
"""

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MergeRegistry:
    """Central registry for merge strategy discovery and instantiation.

    Strategies are stored by name as class path strings and lazily loaded
    on demand. The default strategy is 'icp_union'.
    """

    _strategies: dict[str, dict] = {}
    _default: str = "icp_union"

    @classmethod
    def register(cls, name: str, display: str, class_path: str) -> None:
        """Register a strategy by name and importable class path."""
        cls._strategies[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered merge strategy: %s (%s)", name, class_path)

    @classmethod
    def list_strategies(cls) -> list[dict]:
        """List all registered strategies with availability and metadata.

        Returns list of dicts with keys: name, display, available,
        capabilities, parameter_schema. Unavailable strategies include 'reason'.
        """
        result = []
        for name, info in list(cls._strategies.items()):
            entry: dict[str, Any] = {
                "name": name,
                "display": info["display"],
            }
            klass = cls._load_class(info["class_path"])
            if klass is not None:
                available = getattr(klass, "AVAILABLE", True)
                entry["available"] = available
                if not available:
                    entry["reason"] = getattr(
                        klass, "INSTALL_HINT", "Optional dependency not installed"
                    )
                entry["capabilities"] = getattr(klass, "CAPABILITIES", {})
                entry["parameter_schema"] = getattr(klass, "PARAMETER_SCHEMA", {})
            else:
                entry["available"] = False
                entry["capabilities"] = {}
                entry["parameter_schema"] = {}
                entry["reason"] = f"Cannot load {info['class_path']}"
            result.append(entry)
        return result

    @classmethod
    def create(cls, name: str | None = None, **kwargs: Any) -> Any:
        """Create a strategy instance by name.

        Args:
            name: Strategy name, or None to use default ('icp_union').
            **kwargs: Passed to strategy constructor.

        Returns:
            Instantiated strategy.

        Raises:
            ValueError: If strategy name is not registered.
            ImportError: If strategy class cannot be loaded.
        """
        if name is None:
            name = cls._default

        if name not in cls._strategies:
            raise ValueError(
                f"Unknown merge strategy '{name}'. "
                f"Available: {list(cls._strategies.keys())}"
            )

        info = cls._strategies[name]
        klass = cls._load_class(info["class_path"])
        if klass is None:
            raise ImportError(
                f"Cannot load strategy class: {info['class_path']}"
            )

        available = getattr(klass, "AVAILABLE", True)
        if not available:
            hint = getattr(klass, "INSTALL_HINT", "missing dependency")
            raise ImportError(
                f"Strategy '{name}' is not available: {hint}"
            )

        return klass(**kwargs)

    @classmethod
    def get_default(cls) -> str:
        """Return the default strategy name."""
        return cls._default

    @classmethod
    def _load_class(cls, class_path: str) -> type | None:
        """Lazily import and return a class from its dotted path.

        Returns None if the module or class cannot be found.
        """
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except (ImportError, AttributeError, ValueError) as exc:
            logger.debug("Cannot load %s: %s", class_path, exc)
            return None

    @classmethod
    def _clear(cls) -> None:
        """Clear all registered strategies. Test helper only."""
        cls._strategies = {}


def merge_strategy(name: str, display: str):
    """Decorator to register a class as a merge strategy.

    Usage::

        @merge_strategy("icp_union", "ICP Union (Baseline)")
        class ICPUnionStrategy:
            ...
    """

    def decorator(klass: type) -> type:
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        MergeRegistry.register(name, display, class_path)
        return klass

    return decorator
