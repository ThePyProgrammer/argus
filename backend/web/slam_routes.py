"""SLAM backend and merge strategy REST API routes.

Provides discovery, selection, active query, and parameter management
for pluggable SLAM backends via /api/slam/* endpoints and merge
strategies via /api/slam/merge-* endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.coordination.merge_registry import MergeRegistry
from src.slam.registry import SLAMRegistry

router = APIRouter(prefix="/api/slam", tags=["slam"])


class SelectRequest(BaseModel):
    backend: str


class MergeSelectRequest(BaseModel):
    strategy: str


class ParamPatch(BaseModel):
    params: dict


@router.get("/backends")
async def list_backends():
    """List all registered SLAM backends with capabilities and parameter schemas."""
    return {"backends": SLAMRegistry.list_backends()}


@router.post("/select")
async def select_backend(req: SelectRequest, request: Request):
    """Select a SLAM backend by name, triggering simulation restart."""
    # Validate backend exists
    backends = {b["name"]: b for b in SLAMRegistry.list_backends()}
    if req.backend not in backends:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {req.backend}")
    if not backends[req.backend]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Backend unavailable: {backends[req.backend].get('reason', 'unknown')}",
        )

    # Store pending backend selection on app.state
    request.app.state.pending_slam_backend = req.backend

    # Trigger restart via coordinator (same mechanism as "restart" command)
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})

    return {"status": "restarting", "backend": req.backend}


@router.get("/active")
async def get_active(request: Request):
    """Return the currently active SLAM backend name and config."""
    active = getattr(request.app.state, "active_slam_backend", SLAMRegistry.get_default())
    # Find display name and params from registry
    backends = {b["name"]: b for b in SLAMRegistry.list_backends()}
    info = backends.get(active, {})
    return {
        "backend": active,
        "display": info.get("display", active),
        "parameters": info.get("parameter_schema", {}),
    }


@router.patch("/params")
async def patch_params(patch: ParamPatch, request: Request):
    """Update backend parameters. Returns status per parameter."""
    active = getattr(request.app.state, "active_slam_backend", SLAMRegistry.get_default())
    backends = {b["name"]: b for b in SLAMRegistry.list_backends()}
    info = backends.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})

    results = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
        else:
            results[key] = {"status": "requires_restart", "value": value}
            # Store for next restart
            pending = getattr(request.app.state, "pending_slam_params", {})
            pending[key] = value
            request.app.state.pending_slam_params = pending

    return {"results": results}


# ---------------------------------------------------------------------------
# Merge strategy endpoints
# ---------------------------------------------------------------------------


@router.get("/merge-strategies")
async def list_merge_strategies():
    """List all registered merge strategies with capabilities and parameter schemas."""
    import src.coordination.merge_strategies  # noqa: F401

    return {"strategies": MergeRegistry.list_strategies()}


@router.post("/merge-strategy")
async def select_merge_strategy(req: MergeSelectRequest, request: Request):
    """Select a merge strategy by name, triggering simulation restart."""
    import src.coordination.merge_strategies  # noqa: F401

    strategies = {s["name"]: s for s in MergeRegistry.list_strategies()}
    if req.strategy not in strategies:
        raise HTTPException(status_code=404, detail=f"Unknown strategy: {req.strategy}")
    if not strategies[req.strategy]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Strategy unavailable: {strategies[req.strategy].get('reason', 'unknown')}",
        )

    request.app.state.pending_merge_strategy = req.strategy

    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})

    return {"status": "restarting", "strategy": req.strategy}


@router.get("/merge-strategy")
async def get_active_merge_strategy(request: Request):
    """Return the currently active merge strategy name and config."""
    import src.coordination.merge_strategies  # noqa: F401

    active = getattr(request.app.state, "active_merge_strategy", MergeRegistry.get_default())
    strategies = {s["name"]: s for s in MergeRegistry.list_strategies()}
    info = strategies.get(active, {})
    return {
        "strategy": active,
        "display": info.get("display", active),
        "parameters": info.get("parameter_schema", {}),
    }


@router.patch("/merge-params")
async def patch_merge_params(patch: ParamPatch, request: Request):
    """Update merge strategy parameters. Returns status per parameter."""
    import src.coordination.merge_strategies  # noqa: F401

    active = getattr(request.app.state, "active_merge_strategy", MergeRegistry.get_default())
    strategies = {s["name"]: s for s in MergeRegistry.list_strategies()}
    info = strategies.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})

    results = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
        else:
            results[key] = {"status": "requires_restart", "value": value}
            pending = getattr(request.app.state, "pending_merge_params", {})
            pending[key] = value
            request.app.state.pending_merge_params = pending

    return {"results": results}
