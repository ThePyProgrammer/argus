"""Side-effect import module — registers all built-in trackers.

Usage:
    import src.tracking.trackers  # noqa: F401
    # TrackerRegistry is now populated with 'none' and any Phase-8 additions.
"""
from . import bytetrack  # noqa: F401
from . import none  # noqa: F401
