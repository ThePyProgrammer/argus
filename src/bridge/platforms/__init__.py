"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.go2 import Go2Platform
from src.bridge.platforms.registry import (
    clear_platform_registry,
    create_platform,
    ensure_platform_registered,
    list_platforms,
    register_platform,
)

ensure_platform_registered("go2", Go2Platform)

__all__ = [
    "Go2Platform",
    "clear_platform_registry",
    "create_platform",
    "list_platforms",
    "register_platform",
]
