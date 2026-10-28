"""Validated map placement for initial startup and simulation restarts."""

from dataclasses import dataclass, field
import math
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, FiniteFloat

router = APIRouter(prefix="/api/spawn", tags=["spawn"])


def set_simulation_status(app, phase: str, message: str, positions=None):
    previous = getattr(app.state, 'simulation_status', {})
    positions = positions if positions is not None else previous.get('positions', {})
    app.state.simulation_status = {
        'phase': phase, 'message': message,
        'positions': positions,
        # Match MultiRobotBridge.start(): evenly spaced headings in robot order.
        'headings': {rid: 2 * math.pi * i / len(positions)
                     for i, rid in enumerate(positions)},
    }


@router.get('/status')
async def get_simulation_status(request: Request):
    return getattr(request.app.state, 'simulation_status', {'phase': 'idle', 'message': ''})


@dataclass
class StartupSpawnSelection:
    scene: str
    defaults: dict[str, tuple[float, float, float]]
    footprint_radius: float = 0.35
    ready: threading.Event = field(default_factory=threading.Event)
    positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)

    def choose(self, positions: dict[str, tuple[float, float]]) -> None:
        if self.ready.is_set():
            raise ValueError("Startup positions have already been confirmed")
        if positions.keys() != self.defaults.keys():
            raise ValueError("Select one position for every robot in this session")
        selected = {}
        for robot_id in self.defaults:
            x, y = positions[robot_id]
            if not math.isfinite(x) or not math.isfinite(y) or max(abs(x), abs(y)) > 1000:
                raise ValueError("Spawn coordinates must be finite and within 1000 meters")
            for other in selected.values():
                if math.hypot(x - other[0], y - other[1]) < 2 * self.footprint_radius:
                    raise ValueError("Robot spawn positions overlap; place them farther apart")
            selected[robot_id] = (x, y, self.defaults[robot_id][2])
        self.positions = selected
        self.ready.set()


class SpawnRequest(BaseModel):
    positions: dict[str, tuple[FiniteFloat, FiniteFloat]]


@router.get('/restart')
async def get_restart_selection(request: Request):
    selection = getattr(request.app.state, 'restart_spawn', None)
    if selection is None:
        raise HTTPException(status_code=409, detail='Restart placement is unavailable for this session')
    return {
        'scene': selection.scene,
        'robot_ids': list(selection.defaults),
        'defaults': {rid: list(point[:2]) for rid, point in selection.defaults.items()},
    }


@router.post('/restart')
async def confirm_restart(body: SpawnRequest, request: Request):
    template = getattr(request.app.state, 'restart_spawn', None)
    callback = getattr(request.app.state, 'command_callback', None)
    startup = getattr(request.app.state, 'startup_spawn', None)
    if template is None or callback is None or (startup is not None and not startup.ready.is_set()):
        raise HTTPException(status_code=409, detail='Simulation is not ready to restart')
    selection = StartupSpawnSelection(template.scene, template.defaults, template.footprint_radius)
    try:
        selection.choose(body.positions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    set_simulation_status(request.app, 'loading', 'Preparing simulation restart', selection.positions)
    callback({'action': 'restart', 'positions': selection.positions})
    return {'positions': selection.positions, 'status': request.app.state.simulation_status}


@router.get("")
async def get_spawn_selection(request: Request):
    selection = getattr(request.app.state, "startup_spawn", None)
    if selection is None:
        return {"awaiting_selection": False}
    return {
        "awaiting_selection": not selection.ready.is_set(),
        "scene": selection.scene,
        "robot_ids": list(selection.defaults),
        "defaults": {rid: list(point[:2]) for rid, point in selection.defaults.items()},
    }


@router.post("")
async def confirm_spawn(body: SpawnRequest, request: Request):
    selection = getattr(request.app.state, "startup_spawn", None)
    if selection is None or selection.ready.is_set():
        raise HTTPException(status_code=409, detail="This session is not waiting for spawn selection")
    try:
        # Validate separately so the preview is available before waking MuJoCo.
        validated = StartupSpawnSelection(selection.scene, selection.defaults, selection.footprint_radius)
        validated.choose(body.positions)
        set_simulation_status(request.app, 'loading', 'Preparing simulation', validated.positions)
        selection.choose(body.positions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"positions": selection.positions, "status": request.app.state.simulation_status}
