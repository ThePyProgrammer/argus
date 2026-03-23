"""Pipeline configuration REST API routes.

Provides pipeline graph apply, preset management, and node catalog
endpoints via /api/pipeline/* prefix.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.coordination.pipeline_builder import PipelineBuilder, NodeCatalog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

PRESET_DIR = Path(__file__).parent.parent.parent / "data" / "presets"
BUILTIN_DIR = PRESET_DIR / "builtin"
USER_DIR = PRESET_DIR / "user"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PipelineApplyRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]


class PresetSaveRequest(BaseModel):
    name: str
    nodes: list[dict]
    edges: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/apply")
async def apply_pipeline(req: PipelineApplyRequest, request: Request):
    """Validate and apply a pipeline graph configuration.

    Builds via PipelineBuilder, stores the config on app.state, and
    triggers a simulation restart via the command callback.
    """
    builder = PipelineBuilder()
    try:
        config = builder.build({"nodes": req.nodes, "edges": req.edges})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    request.app.state.pending_pipeline_config = config

    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})

    return {"status": "restarting"}


@router.get("/node-catalog")
async def node_catalog():
    """Return all available node types from registries and static definitions."""
    return {"nodes": NodeCatalog.get_catalog()}


@router.get("/presets")
async def list_presets():
    """List all built-in and user presets."""
    presets = []

    for directory, built_in in [(BUILTIN_DIR, True), (USER_DIR, False)]:
        if not directory.exists():
            continue
        for fp in sorted(directory.glob("*.json")):
            try:
                data = json.loads(fp.read_text())
                presets.append({
                    "name": data.get("name", fp.stem),
                    "builtIn": built_in,
                    "nodeCount": len(data.get("nodes", [])),
                })
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Skipping preset %s: %s", fp, exc)

    return {"presets": presets}


@router.post("/presets")
async def save_preset(req: PresetSaveRequest):
    """Save a named user preset."""
    USER_DIR.mkdir(parents=True, exist_ok=True)
    preset_data = {
        "name": req.name,
        "nodes": req.nodes,
        "edges": req.edges,
    }
    fp = USER_DIR / f"{req.name}.json"
    fp.write_text(json.dumps(preset_data, indent=2))
    return {"status": "saved", "name": req.name}


@router.get("/presets/{name}")
async def load_preset(name: str):
    """Load a preset by name (searches builtin then user directories)."""
    for directory in [BUILTIN_DIR, USER_DIR]:
        fp = directory / f"{name}.json"
        if fp.exists():
            try:
                return json.loads(fp.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                raise HTTPException(status_code=500, detail=f"Cannot read preset: {exc}")

    raise HTTPException(status_code=404, detail=f"Preset not found: {name}")


@router.delete("/presets/{name}")
async def delete_preset(name: str):
    """Delete a user preset. Built-in presets cannot be deleted."""
    # Check if it's a builtin preset
    builtin_fp = BUILTIN_DIR / f"{name}.json"
    if builtin_fp.exists():
        raise HTTPException(status_code=403, detail="Cannot delete built-in preset")

    user_fp = USER_DIR / f"{name}.json"
    if not user_fp.exists():
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")

    user_fp.unlink()
    return {"status": "deleted", "name": name}
