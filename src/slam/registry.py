"""SLAM backend registry with decorator-based discovery.

Backends register themselves via the @slam_backend decorator. The registry
supports lazy loading (backends are imported only when instantiated or
listed) and provides a standard create() factory.
"""

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SLAMRegistry:
    """Central registry for SLAM backend discovery and instantiation.

    Backends are stored by name as class path strings and lazily loaded
    on demand. The default backend is 'icp'.
    """

    _backends: dict[str, dict] = {}
    _default: str = "icp"

    @classmethod
    def register(cls, name: str, display: str, class_path: str) -> None:
        """Register a backend by name and importable class path."""
        cls._backends[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered SLAM backend: %s (%s)", name, class_path)

    @classmethod
    def list_backends(cls) -> list[dict]:
        """List all registered backends with availability and metadata.

        Returns list of dicts with keys: name, display, available,
        capabilities, parameter_schema. Unavailable backends include 'reason'.
        """
        result = []
        for name, info in cls._backends.items():
            entry: dict[str, Any] = {
                "name": name,
                "display": info["display"],
            }
            klass = cls._load_class(info["class_path"])
            if klass is not None:
                entry["available"] = True
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
        """Create a backend instance by name.

        Args:
            name: Backend name, or None to use default ('icp').
            **kwargs: Passed to backend constructor.

        Returns:
            Instantiated backend.

        Raises:
            ValueError: If backend name is not registered.
            ImportError: If backend class cannot be loaded.
        """
        if name is None:
            name = cls._default

        if name not in cls._backends:
            raise ValueError(
                f"Unknown SLAM backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )

        info = cls._backends[name]
        klass = cls._load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load backend class: {info['class_path']}")

        return klass(**kwargs)

    @classmethod
    def get_default(cls) -> str:
        """Return the default backend name."""
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
        """Clear all registered backends. Test helper only."""
        cls._backends = {}


def slam_backend(name: str, display: str):
    """Decorator to register a class as a SLAM backend.

    Usage::

        @slam_backend("icp", "ICP Odometry")
        class ICPBackend:
            ...
    """

    def decorator(klass: type) -> type:
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        SLAMRegistry.register(name, display, class_path)
        return klass

    return decorator
