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


class LifterSelectRequest(BaseModel):
    lifter: str
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


# ---------------------------------------------------------------------------
# Lifter (Detection3D) endpoints — Phase 3 D-10
# ---------------------------------------------------------------------------
#
# Structural clone of the merge-strategy block in backend/web/slam_routes.py
# (lines 107-175). Every handler MUST `import src.perception.lifters` at call
# time to force @detection_3d side-effect registration (Pitfall #4 — without
# this, a cold boot returns {lifters: []}).
#
# Threat model (mirror SLAM merge T-02-19..21; see 03-05-PLAN.md):
#   T-03-11  POST /lifter-select validates req.lifter ∈ registry BEFORE write.
#   T-03-12  PATCH /lifter-params per-key schema gate: unknown → no mutation.
#   T-03-13  unknown_parameter oracle leaks schema (accepted; schema already
#            published via GET /active-lifter).
#   T-03-14  Missing side-effect import → empty registry (mitigated by the
#            cold-boot test test_list_lifters_cold_boot_triggers_registry_population).


@router.get("/lifters")
async def list_lifters():
    """List registered Detection3D lifters with capabilities + schemas (D-10)."""
    import src.perception.lifters  # noqa: F401 — trigger @detection_3d registration
    from src.perception.registry import Detection3DRegistry

    return {"lifters": Detection3DRegistry.list_backends()}


@router.post("/lifter-select")
async def select_lifter(req: LifterSelectRequest, request: Request):
    """Select a Detection3D lifter by name, triggering simulation restart (D-09)."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry

    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    if req.lifter not in lifters:
        raise HTTPException(status_code=404, detail=f"Unknown lifter: {req.lifter}")
    if not lifters[req.lifter]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Lifter unavailable: {lifters[req.lifter].get('reason', 'unknown')}",
        )
    request.app.state.pending_lifter = req.lifter
    if req.params:
        request.app.state.pending_lifter_params = req.params
    command_cb = getattr(request.app.state, "command_callback", None)
    if command_cb:
        command_cb({"action": "restart"})
    return {"status": "restarting", "lifter": req.lifter}


@router.get("/active-lifter")
async def get_active_lifter(request: Request):
    """Return the currently active Detection3D lifter name + config."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry

    active = getattr(
        request.app.state, "active_lifter", Detection3DRegistry.get_default()
    )
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    info = lifters.get(active, {})
    return {
        "lifter": active,
        "display": info.get("display", active),
        "parameters": info.get("parameter_schema", {}),
    }


@router.patch("/lifter-params")
async def patch_lifter_params(patch: ParamPatch, request: Request):
    """Update lifter params — live_tunable applied, non-live queued for next restart."""
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry

    active = getattr(
        request.app.state, "active_lifter", Detection3DRegistry.get_default()
    )
    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    info = lifters.get(active, {})
    schema_props = info.get("parameter_schema", {}).get("properties", {})
    results: dict = {}
    for key, value in patch.params.items():
        if key not in schema_props:
            results[key] = {"status": "unknown_parameter"}
        elif schema_props[key].get("live_tunable", False):
            results[key] = {"status": "applied", "value": value}
            pending = getattr(request.app.state, "pending_lifter_params", {})
            pending[key] = value
            request.app.state.pending_lifter_params = pending
        else:
            results[key] = {"status": "requires_restart", "value": value}
            pending = getattr(request.app.state, "pending_lifter_params", {})
            pending[key] = value
            request.app.state.pending_lifter_params = pending
    return {"results": results}
