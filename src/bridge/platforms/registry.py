from __future__ import annotations

from collections.abc import Callable

from src.bridge.platforms.base import RobotPlatform

_PlatformFactory = Callable[..., RobotPlatform]
_REGISTRY: dict[str, _PlatformFactory] = {}


def register_platform(name: str, factory: _PlatformFactory) -> None:
    key = name.strip().lower()
    if not key:
        raise ValueError("platform name must not be empty")
    if key in _REGISTRY:
        raise ValueError(f"Robot platform '{key}' is already registered")
    _REGISTRY[key] = factory


def create_platform(name: str, **kwargs) -> RobotPlatform:
    key = name.strip().lower()
    try:
        factory = _REGISTRY[key]
    except KeyError as exc:
        known = ", ".join(list_platforms()) or "none"
        raise ValueError(f"Unknown robot platform '{name}'. Known platforms: {known}") from exc
    return factory(**kwargs)


def list_platforms() -> list[str]:
    return sorted(_REGISTRY)


def clear_platform_registry() -> None:
    _REGISTRY.clear()
