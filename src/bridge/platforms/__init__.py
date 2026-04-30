"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.agibot_x2 import AgibotX2Platform
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.platforms.registry import (
    clear_platform_registry,
    create_platform,
    ensure_platform_registered,
    list_platforms,
    register_platform,
)

ensure_platform_registered("go2", Go2Platform)
ensure_platform_registered("agibot_x2", AgibotX2Platform)

__all__ = [
    "AgibotX2Platform",
    "Go2Platform",
    "clear_platform_registry",
    "create_platform",
    "list_platforms",
    "register_platform",
]
