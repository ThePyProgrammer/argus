from __future__ import annotations

from collections.abc import Callable

from src.bridge.platforms.base import RobotPlatform

_PlatformFactory = Callable[..., RobotPlatform]
_REGISTRY: dict[str, _PlatformFactory] = {}


def _normalize_platform_name(name: str) -> str:
    key = name.strip().lower()
    if not key:
        raise ValueError("platform name must not be empty")
    return key


def register_platform(name: str, factory: _PlatformFactory) -> None:
    key = _normalize_platform_name(name)
    if key in _REGISTRY:
        raise ValueError(f"Robot platform '{key}' is already registered")
    _REGISTRY[key] = factory


def get_platform_factory(name: str) -> _PlatformFactory | None:
    key = _normalize_platform_name(name)
    return _REGISTRY.get(key)


def ensure_platform_registered(name: str, factory: _PlatformFactory) -> None:
    key = _normalize_platform_name(name)
    existing = _REGISTRY.get(key)
    if existing is None:
        _REGISTRY[key] = factory
        return
    if existing is not factory:
        raise ValueError(f"Robot platform '{key}' is already registered")


def create_platform(name: str, **kwargs) -> RobotPlatform:
    key = _normalize_platform_name(name)
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
