"""Robot platform implementations for MuJoCo-backed Argus simulation."""

from src.bridge.platforms.registry import create_platform, list_platforms, register_platform

__all__ = ["create_platform", "list_platforms", "register_platform"]
