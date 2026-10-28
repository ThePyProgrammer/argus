"""One-shot startup placement; MuJoCo waits until selection is confirmed."""

from dataclasses import dataclass, field
import math
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, FiniteFloat

router = APIRouter(prefix="/api/spawn", tags=["spawn"])


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
        for robot_id, (x, y) in positions.items():
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
        selection.choose(body.positions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"positions": selection.positions}
