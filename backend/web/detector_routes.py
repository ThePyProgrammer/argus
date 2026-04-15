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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.perception.registry import DetectorRegistry

router = APIRouter(prefix="/api/detectors", tags=["detectors"])

# Phase 6 DET-METRICS-04: dedicated router for /api/detections/* — separate
# prefix from the detector-registry router so the export endpoint lives under
# /api/detections/export per CONTEXT D-13, not /api/detectors/...
export_router = APIRouter(prefix="/api/detections", tags=["detections"])


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
# Lifter (Detection3D) endpoints — Phase 4 D-09 (supersedes Phase 3 D-09)
# ---------------------------------------------------------------------------
#
# Structural clone of the merge-strategy block in backend/web/slam_routes.py.
# Every handler MUST `import src.perception.lifters` at call time to force
# @detection_3d side-effect registration (Pitfall #4 — without this, a cold
# boot returns {lifters: []}).
#
# Phase 4 supersession: the previous `POST /lifter-select` handler that
# stashed `pending_lifter` and triggered a full simulation restart is GONE.
# Lifters are stateless geometry; switching one is an atomic
# `DetectorWorkerPool.swap_lifter(...)` call under a pool-level lock
# (≪1ms). The new handler is `POST /lifter-hotswap`.
#
# Threat model (Phase 4 04-05-PLAN.md <threat_model>):
#   T-04-18  POST /lifter-hotswap validates req.lifter ∈ registry BEFORE any
#            state mutation (404). Mirrors Phase 2 T-02-19.
#   T-04-19  Unavailable lifter (dep missing) → 400 with vendor reason.
#   T-04-20  Concurrent swap race — serialized by pool._swap_lock;
#            registry.create runs OUTSIDE the lock.
#   T-04-21  Pool not yet initialized → 503.
#   T-04-22  In-flight lift() sees torn state — accepted (GIL atomicity,
#            Pitfall 6).
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


@router.post("/lifter-hotswap")
async def lifter_hotswap(req: LifterSelectRequest, request: Request):
    """Atomic lifter ref swap — no restart, no warmup (Phase 4 D-09, D-10).

    Supersedes Phase 3 `/lifter-select`. Lifters are stateless geometry;
    swapping is a sub-millisecond pool-locked attribute rebind per D-10.

    Flow:
      1. Validate req.lifter against Detection3DRegistry → 404 / 400 on
         unknown / unavailable (T-04-18, T-04-19 — fail BEFORE mutation).
      2. Reach the pool via ``request.app.state.detector_pool``. If None
         (pool not yet constructed — happens during initial boot before the
         first restart block runs), return 503 (T-04-21).
      3. Call ``pool.swap_lifter(req.lifter, req.params or {})`` — this is
         the atomic hook; it builds fresh lifter instances per worker and
         rebinds under the pool's ``_swap_lock``.
      4. Update ``app.state.active_lifter`` so ``GET /active-lifter`` and
         the next restart block see the new pick (restart preserves
         hot-swapped lifter via main.py's active_lifter read).
      5. Return ``{"status": "swapped", "lifter": req.lifter}``.
    """
    import src.perception.lifters  # noqa: F401 — force @detection_3d registration
    from src.perception.registry import Detection3DRegistry

    lifters = {l["name"]: l for l in Detection3DRegistry.list_backends()}
    if req.lifter not in lifters:
        raise HTTPException(status_code=404, detail=f"Unknown lifter: {req.lifter}")
    if not lifters[req.lifter]["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Lifter unavailable: {lifters[req.lifter].get('reason', 'unknown')}",
        )

    pool = getattr(request.app.state, "detector_pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="Detector pool not initialized")

    params = dict(req.params or {})
    pool.swap_lifter(req.lifter, params)

    # Keep app.state in sync so GET /active-lifter reflects the new lifter
    # and the next restart block preserves the hot-swapped pick.
    request.app.state.active_lifter = req.lifter
    if params:
        request.app.state.pending_lifter_params = params
    return {"status": "swapped", "lifter": req.lifter}


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


# ---------------------------------------------------------------------------
# Detections export endpoint (Phase 6 — DET-METRICS-04)
# ---------------------------------------------------------------------------
#
# Streams the current session's detections.jsonl file produced by
# WebStreamingViz.detection_export (DetectionExportWriter). Per CONTEXT D-13:
# snapshot-at-request-time semantics (not `tail -f`), 65536-byte chunks,
# media_type application/x-ndjson. Session ID is server-side (UUID4,
# generated at WebStreamingViz construction; rotated on reset_cloud_tracking).
# The endpoint accepts no path parameter — no traversal risk (T-6-02).
#
# Mounted on a dedicated `export_router` with prefix /api/detections so the
# endpoint lives at /api/detections/export (not /api/detectors/...).

@export_router.get("/export")
async def export_detections(request: Request):
    """Stream the current session's detections.jsonl (DET-METRICS-04).

    Snapshot-at-request-time semantics (CONTEXT D-13): not tail -f.
    Session ID is server-side (UUID4, generated at WebStreamingViz
    construction or rotated on reset_cloud_tracking). Endpoint accepts
    no path parameter — no traversal risk (T-6-02).
    """
    streaming_viz = request.app.state.streaming_viz
    path = streaming_viz.detection_export.file_path
    session = streaming_viz.current_session_id()

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="No detections recorded yet for the current session",
        )

    def generate():
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": f'attachment; filename="detections-{session}.jsonl"',
        },
    )
