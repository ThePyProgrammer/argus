"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.go2 import Go2Platform
from src.bridge.platforms.registry import (
    clear_platform_registry,
    create_platform,
    list_platforms,
    register_platform,
)

try:
    register_platform("go2", Go2Platform)
except ValueError:
    pass

__all__ = [
    "Go2Platform",
    "clear_platform_registry",
    "create_platform",
    "list_platforms",
    "register_platform",
]
