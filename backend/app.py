"""Backend entry point for the C2 web interface.

Run with:
    uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

The app is created lazily on first import. For standalone mode (without
the simulation loop), it serves the frontend with a placeholder robot
list. When used with main.py --control web, the simulation thread calls
create_app() to wire in the real Coordinator and streaming viz.
"""

from backend.web.server import app, create_app

__all__ = ["app", "create_app"]
