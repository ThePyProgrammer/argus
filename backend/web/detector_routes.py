"""Detector backend REST API routes.

Structural clone of backend/web/slam_routes.py (SLAM pattern for backend
selection + parameter management) per CONTEXT.md D-02. 4 endpoints:

  GET  /api/detectors/backends  — list all registered detector backends
  POST /api/detectors/select    — select backend + trigger restart
  GET  /api/detectors/active    — current active backend + parameters
  PATCH /api/detectors/params   — update params (live-tunable vs requires-restart)

Phase 2 (DET-MODELS-05): pre-session selection with restart; mid-session hot-swap
is explicitly out of scope.

Threat model (mirror SLAM — see 02-08-PLAN.md <threat_model>):
  T-02-19  POST /select validates req.backend ∈ registry BEFORE app.state write.
  T-02-21  SelectRequest / ParamPatch are pydantic BaseModels: FastAPI rejects
           malformed payloads with 422 automatically.
  T-02-22  pending_detector_backend read/write race is accepted (matches SLAM
           precedent; users click once at a time in practice).
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.perception.registry import DetectorRegistry

router = APIRouter(prefix="/api/detectors", tags=["detectors"])


class SelectRequest(BaseModel):
    backend: str
    params: dict | None = None


class ParamPatch(BaseModel):
    params: dict


@router.get("/backends")
async def list_backends():
    """List all registered detector backends with capabilities + parameter schemas."""
    return {"backends": DetectorRegistry.list_backends()}


@router.post("/select")
async def select_backend(req: SelectRequest, request: Request):
    """Select a detector backend by name, triggering simulation restart (D-02)."""
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    if req.backend not in backends:
        raise HTTPException(status_code=404, detail=f"Unknown backend: {req.backend}")
    if not backends[req.backend]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Backend unavailable: {backends[req.backend].get('reason', 'unknown')}",
        )
    request.app.state.pending_detector_backend = req.backend
    if req.params:
        request.app.state.pending_detector_params = req.params
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "backend": req.backend}


@router.get("/active")
async def get_active(request: Request):
    """Return the currently active detector backend name + config."""
    active = getattr(
        request.app.state, "active_detector_backend", DetectorRegistry.get_default()
    )
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    info = backends.get(active, {})
    return {
        "backend": active,
        "display": info.get("display", active),
        "parameters": info.get("parameter_schema", {}),
    }


@router.patch("/params")
async def patch_params(patch: ParamPatch, request: Request):
    """Update detector params — live_tunable applied, non-live queued for next restart."""
    active = getattr(
        request.app.state, "active_detector_backend", DetectorRegistry.get_default()
    )
    backends = {b["name"]: b for b in DetectorRegistry.list_backends()}
    info = backends.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})
    results: dict = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
            pending = getattr(request.app.state, "pending_detector_params", {})
            pending[key] = value
            request.app.state.pending_detector_params = pending
        else:
            results[key] = {"status": "requires_restart", "value": value}
            pending = getattr(request.app.state, "pending_detector_params", {})
            pending[key] = value
            request.app.state.pending_detector_params = pending
    return {"results": results}
