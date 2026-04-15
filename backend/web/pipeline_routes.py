"""Pipeline configuration REST API routes.

Provides pipeline graph apply, preset management, and node catalog
endpoints via /api/pipeline/* prefix.

Phase 7 DET-PIPELINE-05 extends apply_pipeline with server-side diff
(CONTEXT D-10). When only perception fields change (detector/lifter with
unchanged topology + non-perception fields), the handler calls
pool.swap_backend / pool.swap_lifter directly and returns
{"status": "hot-applied", ...} WITHOUT a coordinator restart. All other
changes fall through to the existing restart path.
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
# Topology digest helper (Plan 07-09 — DET-PIPELINE-05 diff-then-dispatch)
# ---------------------------------------------------------------------------

def _digest_topology(nodes: list[dict], edges: list[dict]) -> tuple:
    """Stable topology digest = sorted node ids + sorted edge tuples.

    Used by apply_pipeline to decide between hot-apply and restart paths.
    Two graphs with the same node ids + same edges produce the same digest;
    add/remove a node or re-route an edge and the digest changes.
    """
    node_ids = tuple(sorted(n["id"] for n in nodes))
    edge_tuples = tuple(sorted(
        (e["source"], e.get("sourceHandle", ""), e["target"], e.get("targetHandle", ""))
        for e in edges
    ))
    return (node_ids, edge_tuples)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/apply")
async def apply_pipeline(req: PipelineApplyRequest, request: Request):
    """Validate + apply a pipeline graph (CONTEXT D-10 diff-then-dispatch).

    Returns one of:
      {"status": "hot-applied", "changed": [...], "active_detector": ..., "active_lifter": ...}
      {"status": "restarting"}

    Error responses:
      422 — PipelineBuilder.build ValueError (unknown node type, cycle, ...)
      400 — pool.swap_backend / swap_lifter failure (unknown backend, warmup crash)
      503 — detector_pool not yet initialized
    """
    builder = PipelineBuilder()
    try:
        config = builder.build({"nodes": req.nodes, "edges": req.edges})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    topology_digest = _digest_topology(req.nodes, req.edges)
    last_config = getattr(request.app.state, "last_applied_pipeline_config", None)
    last_topology = getattr(request.app.state, "last_applied_topology_digest", None)

    # Diff rules (CONTEXT D-10 strict AND):
    #   topology unchanged AND SLAM/merger/filter/tracker fields unchanged AND
    #   (detector_name or detector_params or lifter_name or lifter_params) moved.
    if last_config is not None and last_topology is not None:
        structural_unchanged = (
            topology_digest == last_topology
            and config.backend_name == last_config.backend_name
            and config.backend_params == last_config.backend_params
            and config.merger_name == last_config.merger_name
            and config.merger_params == last_config.merger_params
            and config.filter_chain == last_config.filter_chain
            and config.tracker_name == last_config.tracker_name
            and config.tracker_params == last_config.tracker_params
        )
        detector_changed = (
            config.detector_name != last_config.detector_name
            or config.detector_params != last_config.detector_params
        )
        lifter_changed = (
            config.lifter_name != last_config.lifter_name
            or config.lifter_params != last_config.lifter_params
        )

        if structural_unchanged and (detector_changed or lifter_changed):
            # HOT-APPLY PATH
            pool = getattr(request.app.state, "detector_pool", None)
            if pool is None:
                raise HTTPException(
                    status_code=503,
                    detail="Detector pool not initialized",
                )

            changed: list[str] = []
            if detector_changed:
                try:
                    pool.swap_backend(
                        config.detector_name,
                        dict(config.detector_params),
                    )
                except (ValueError, ImportError) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"swap_backend failed: {exc}",
                    )
                except Exception as exc:  # noqa: BLE001 — warmup / bridge errors
                    logger.exception("swap_backend raised unexpected exception")
                    raise HTTPException(
                        status_code=400,
                        detail=f"swap_backend failed: {exc}",
                    )
                request.app.state.active_detector_backend = config.detector_name
                request.app.state.pending_detector_params = dict(config.detector_params)
                changed.append(
                    "detector_name"
                    if config.detector_name != last_config.detector_name
                    else "detector_params"
                )

            if lifter_changed:
                try:
                    pool.swap_lifter(
                        config.lifter_name,
                        dict(config.lifter_params),
                    )
                except (ValueError, ImportError) as exc:
                    raise HTTPException(
                        status_code=400,
                        detail=f"swap_lifter failed: {exc}",
                    )
                request.app.state.active_lifter = config.lifter_name
                request.app.state.pending_lifter_params = dict(config.lifter_params)
                changed.append(
                    "lifter_name"
                    if config.lifter_name != last_config.lifter_name
                    else "lifter_params"
                )

            request.app.state.last_applied_pipeline_config = config
            request.app.state.last_applied_topology_digest = topology_digest
            return {
                "status": "hot-applied",
                "changed": changed,
                "active_detector": config.detector_name,
                "active_lifter": config.lifter_name,
            }

    # RESTART PATH (existing + topology-digest update for next diff)
    request.app.state.pending_pipeline_config = config
    request.app.state.last_applied_topology_digest = topology_digest
    # last_applied_pipeline_config updated AFTER successful restart in main.py (Plan 07-11).

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
    """Load a preset by name (matches filename or JSON 'name' field)."""
    for directory in [BUILTIN_DIR, USER_DIR]:
        # Try exact filename match first
        fp = directory / f"{name}.json"
        if fp.exists():
            try:
                return json.loads(fp.read_text())
            except (json.JSONDecodeError, OSError) as exc:
                raise HTTPException(status_code=500, detail=f"Cannot read preset: {exc}")

    # Fall back to matching the 'name' field inside JSON files
    for directory in [BUILTIN_DIR, USER_DIR]:
        if not directory.exists():
            continue
        for fp in directory.glob("*.json"):
            try:
                data = json.loads(fp.read_text())
                if data.get("name") == name:
                    return data
            except (json.JSONDecodeError, OSError):
                continue

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
