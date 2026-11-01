"""Evaluation-only reference grids extracted from compiled MuJoCo geometry.

Supports static boxes (including full 3D rotations) above one named horizontal
box or plane floor. Other collidable shapes and moving scenes fail explicitly.
Robot clearance is a world-aligned rectangular prism. This module never reads
observations, planning grids, spawn outcomes, or the analytical fixture masks.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import hashlib
from html import escape
import json
import math
from numbers import Integral, Real
from pathlib import Path

import numpy as np


REFERENCE_VERSION = "compiled-box-prism-v1"
_TOLERANCE_M = 1e-10
_MAX_CELLS = 1_000_000


def _finite(value: Real, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class ReferenceConfig:
    bounds: tuple[float, float, float, float]
    component_anchor: tuple[float, float]
    resolution_m: float = 0.10
    clearance_half_extent_m: float = 0.40
    clearance_height_m: float = 0.60
    floor_geom_name: str = "floor"
    robot_contype: int = 1
    robot_conaffinity: int = 1

    def __post_init__(self) -> None:
        for name, length in (("bounds", 4), ("component_anchor", 2)):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or len(values) != length:
                raise ValueError(f"{name} must contain {length} coordinates")
            object.__setattr__(self, name, tuple(_finite(v, name) for v in values))
        x0, y0, x1, y1 = self.bounds
        if x1 <= x0 or y1 <= y0:
            raise ValueError("Bounds must have positive width and height")
        for name in ("resolution_m", "clearance_half_extent_m", "clearance_height_m"):
            value = _finite(getattr(self, name), name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        if not isinstance(self.floor_geom_name, str) or not self.floor_geom_name:
            raise ValueError("A floor geom name is required")
        for name in ("robot_contype", "robot_conaffinity"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or not 0 <= value < 2**31:
                raise ValueError(f"{name} must be a nonnegative 31-bit integer")
            object.__setattr__(self, name, int(value))
        if not (self.robot_contype or self.robot_conaffinity):
            raise ValueError("The clearance proxy must collide with the environment")
        self.shape  # Validate divisibility and allocation limit before constructing a grid.

    @property
    def shape(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.bounds
        dimensions = ((y1 - y0) / self.resolution_m, (x1 - x0) / self.resolution_m)
        if any(not math.isfinite(v) or v < 1 or v > _MAX_CELLS for v in dimensions):
            raise ValueError("Reference grid dimensions are out of range")
        if any(not math.isclose(v, round(v), rel_tol=0, abs_tol=1e-8) for v in dimensions):
            raise ValueError("Resolution must divide the bounds exactly")
        rows, cols = map(round, dimensions)
        if rows * cols > _MAX_CELLS:
            raise ValueError("Reference grid exceeds 1,000,000 cells")
        return rows, cols


@dataclass(frozen=True)
class _Geom:
    name: str
    kind: str
    center: tuple[float, float, float]
    rotation: tuple[float, ...]
    half_size: tuple[float, float, float]


@dataclass(frozen=True)
class SpawnCheck:
    x: float
    y: float
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ReferenceGrid:
    config: ReferenceConfig
    mask: np.ndarray = field(repr=False)
    free_mask: np.ndarray = field(repr=False)
    floor_height_m: float
    geometry_sha256: str
    _floor: _Geom = field(repr=False)
    _obstacles: tuple[_Geom, ...] = field(repr=False)

    def metadata(self) -> dict:
        config = asdict(self.config)
        mask_hash = hashlib.sha256(self.mask.tobytes(order="C")).hexdigest()
        identity = {
            "reference_version": REFERENCE_VERSION,
            "config": config,
            "geometry_sha256": self.geometry_sha256,
            "mask_sha256": mask_hash,
        }
        return {
            **identity,
            "reference_sha256": _hash_json(identity),
            "floor_height_m": self.floor_height_m,
            "origin_xy": list(self.config.bounds[:2]),
            "shape_rows_columns": list(self.mask.shape),
            "row_direction": "positive_world_y",
            "connectivity": "four_neighbors_with_swept_clearance",
            "cell_count": int(self.mask.sum()),
            "area_m2": float(self.mask.sum() * self.config.resolution_m**2),
            "disconnected_cell_count": int((self.free_mask & ~self.mask).sum()),
            "contact_tolerance_m": _TOLERANCE_M,
        }

    def check_spawn(self, x: float, y: float) -> SpawnCheck:
        x, y = _finite(x, "Spawn x"), _finite(y, "Spawn y")
        cell = _cell(self.config, x, y)
        if cell is None:
            return SpawnCheck(x, y, False, "outside_bounds")
        point = np.array([[x, y]])
        if not _clear(point, self.config, self._floor, self._obstacles)[0]:
            return SpawnCheck(x, y, False, "blocked")
        if not self.free_mask[cell]:
            return SpawnCheck(x, y, False, "blocked_cell")
        if not self.mask[cell]:
            return SpawnCheck(x, y, False, "disconnected")
        if not _connected_to_cell(point[0], cell, self.config, self._floor, self._obstacles):
            return SpawnCheck(x, y, False, "unresolved_cell_connection")
        return SpawnCheck(x, y, True, "accepted")

    def write_diagnostics(self, directory: str | Path, *, spawn_points=()) -> dict[str, Path]:
        """Write portable reference data and an SVG overlay, without a renderer."""
        checks = [self.check_spawn(x, y) for x, y in spawn_points]
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        paths = {name: directory / name for name in ("reference.json", "reference.npz", "reference.svg")}
        metadata = {**self.metadata(), "spawn_checks": [asdict(c) for c in checks]}
        paths["reference.json"].write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        np.savez_compressed(paths["reference.npz"], mask=self.mask, free_mask=self.free_mask)
        paths["reference.svg"].write_text(_overlay(self, checks), encoding="utf-8")
        return paths


def build_reference_grid(model, config: ReferenceConfig) -> ReferenceGrid:
    """Extract a fixed denominator from a static environment before robot insertion.

    A fresh MjData ensures poses use compiled forward kinematics, not stale caller
    buffers. The returned arrays and geometry are snapshots independent of model
    mutation. Explicit contact pairs/exclusions are unsupported in this version.
    """
    import mujoco

    if not isinstance(model, mujoco.MjModel):
        raise TypeError("Expected a compiled MuJoCo model")
    if model.nq or model.nv or model.nmocap or model.nflex:
        raise ValueError("Reference extraction requires a static environment before robot insertion")
    if model.npair or model.nexclude:
        raise ValueError("Explicit contact pairs and exclusions are unsupported")
    if int(model.opt.disableflags) & int(mujoco.mjtDisableBit.mjDSBL_CONTACT):
        raise ValueError("Scene contacts are disabled")
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, config.floor_geom_name)
    if floor_id < 0:
        raise ValueError(f"Floor geom {config.floor_geom_name!r} does not exist")
    geoms = []
    for index in range(model.ngeom):
        collides = ((int(model.geom_contype[index]) & config.robot_conaffinity)
                    or (config.robot_contype & int(model.geom_conaffinity[index])))
        if not collides:
            if index == floor_id:
                raise ValueError("The named floor does not collide with the clearance proxy")
            continue
        kind = model.geom_type[index]
        is_box = kind == mujoco.mjtGeom.mjGEOM_BOX
        is_plane_floor = index == floor_id and kind == mujoco.mjtGeom.mjGEOM_PLANE
        if not (is_box or is_plane_floor):
            raise ValueError("Unsupported collidable geometry: only boxes and a horizontal floor plane are supported")
        center = data.geom_xpos[index].copy()
        rotation = data.geom_xmat[index].copy()
        size = model.geom_size[index].copy()
        if not (np.isfinite(center).all() and np.isfinite(rotation).all() and np.isfinite(size).all()):
            raise ValueError("Compiled geometry contains non-finite values")
        if is_box and np.any(size <= 0):
            raise ValueError("Collision boxes must have positive half sizes")
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, index) or f"geom_{index}"
        geoms.append(_Geom(name, "box" if is_box else "plane", tuple(center), tuple(rotation), tuple(size)))
    floor = next(g for g in geoms if g.name == config.floor_geom_name)
    rotation = np.array(floor.rotation).reshape(3, 3)
    if not np.allclose(rotation[2], [0, 0, 1], atol=1e-10, rtol=0):
        raise ValueError("The named floor must be horizontal and face upward")
    floor_height = floor.center[2] + (floor.half_size[2] if floor.kind == "box" else 0)
    obstacles = tuple(g for g in geoms if g is not floor)
    rows, cols = config.shape
    x0, y0, _, _ = config.bounds
    xs = x0 + (np.arange(cols) + .5) * config.resolution_m
    ys = y0 + (np.arange(rows) + .5) * config.resolution_m
    xx, yy = np.meshgrid(xs, ys)
    points = np.column_stack((xx.ravel(), yy.ravel()))
    free_mask = _clear(points, config, floor, obstacles).reshape(rows, cols)
    anchor = _cell(config, *config.component_anchor)
    if anchor is None or not free_mask[anchor]:
        raise ValueError("Reference component anchor is outside the free grid")
    if not _connected_to_cell(np.array(config.component_anchor), anchor, config, floor, obstacles):
        raise ValueError("Reference component anchor has no clear connection to its cell")

    # Swept prisms prevent thin/rotated obstacles from connecting free cell centers
    # through a wall. A translating axis-aligned box sweeps exactly this prism.
    r, step = config.clearance_half_extent_m, config.resolution_m
    horizontal = np.column_stack(((xx[:, :-1] + step/2).ravel(), yy[:, :-1].ravel()))
    vertical = np.column_stack((xx[:-1].ravel(), (yy[:-1] + step/2).ravel()))
    h_edges = _clear(horizontal, config, floor, obstacles, (r + step/2, r)).reshape(rows, cols-1)
    v_edges = _clear(vertical, config, floor, obstacles, (r, r + step/2)).reshape(rows-1, cols)
    component = np.zeros_like(free_mask)
    component[anchor] = True
    queue = deque([anchor])
    while queue:
        row, col = queue.popleft()
        neighbors = []
        if col > 0 and h_edges[row, col-1]:
            neighbors.append((row, col-1))
        if col + 1 < cols and h_edges[row, col]:
            neighbors.append((row, col+1))
        if row > 0 and v_edges[row-1, col]:
            neighbors.append((row-1, col))
        if row + 1 < rows and v_edges[row, col]:
            neighbors.append((row+1, col))
        for neighbor in neighbors:
            if free_mask[neighbor] and not component[neighbor]:
                component[neighbor] = True
                queue.append(neighbor)
    # Byte-backed arrays cannot be made writable via setflags(write=True).
    mask = np.frombuffer(component.tobytes(), dtype=np.bool_).reshape(component.shape)
    free = np.frombuffer(free_mask.tobytes(), dtype=np.bool_).reshape(free_mask.shape)
    geometry_hash = _hash_json([asdict(g) for g in geoms])
    return ReferenceGrid(config, mask, free, floor_height, geometry_hash, floor, obstacles)


def _cell(config: ReferenceConfig, x: float, y: float) -> tuple[int, int] | None:
    x0, y0, x1, y1 = config.bounds
    if not (x0 <= x < x1 and y0 <= y < y1):
        return None
    return math.floor((y-y0)/config.resolution_m), math.floor((x-x0)/config.resolution_m)


def _connected_to_cell(point, cell, config, floor, obstacles) -> bool:
    row, col = cell
    center = np.array([config.bounds[0] + (col+.5)*config.resolution_m,
                       config.bounds[1] + (row+.5)*config.resolution_m])
    half = config.clearance_half_extent_m + np.abs(center-point)/2
    # For a diagonal offset this bounding prism is conservative. Reject ambiguous
    # point-to-cell connections rather than assigning a spawn to the wrong room.
    return bool(_clear(np.array([(center+point)/2]), config, floor, obstacles, half)[0])


def _clear(points, config, floor, obstacles, half_xy=None) -> np.ndarray:
    hx, hy = half_xy if half_xy is not None else (config.clearance_half_extent_m,) * 2
    x0, y0, x1, y1 = config.bounds
    tol = _TOLERANCE_M
    clear = ((points[:, 0] > x0+hx+tol) & (points[:, 0] < x1-hx-tol)
             & (points[:, 1] > y0+hy+tol) & (points[:, 1] < y1-hy-tol))
    floor_height = floor.center[2] + (floor.half_size[2] if floor.kind == "box" else 0)
    if floor.kind == "box":
        rotation = np.array(floor.rotation).reshape(3, 3)
        local = (points - np.array(floor.center[:2])) @ rotation[:2, :2]
        for axis in range(2):
            extent = hx * abs(rotation[0, axis]) + hy * abs(rotation[1, axis])
            clear &= np.abs(local[:, axis]) + extent <= floor.half_size[axis] - tol
    hz = config.clearance_height_m / 2
    center_z = floor_height + hz
    for obstacle in obstacles:
        rotation = np.array(obstacle.rotation).reshape(3, 3)
        size = np.array(obstacle.half_size)
        top = obstacle.center[2] + np.abs(rotation[2]) @ size
        if top <= floor_height + tol:
            continue  # Touching the supporting floor is not an obstacle collision.
        # Separating axis theorem for an axis-aligned prism and an oriented box.
        axes = [*np.eye(3), *rotation.T]
        axes.extend(np.cross(a, b) for a in np.eye(3) for b in rotation.T)
        overlaps = np.ones(len(points), dtype=bool)
        dx = points[:, 0] - obstacle.center[0]
        dy = points[:, 1] - obstacle.center[1]
        dz = center_z - obstacle.center[2]
        for axis in axes:
            norm = np.linalg.norm(axis)
            if norm < 1e-12:
                continue
            axis = axis / norm
            radius = np.abs(axis) @ np.array([hx, hy, hz]) + np.abs(axis @ rotation) @ size
            distance = np.abs(dx*axis[0] + dy*axis[1] + dz*axis[2])
            overlaps &= distance <= radius + tol
        clear &= ~overlaps
    return clear


def _hash_json(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _overlay(reference: ReferenceGrid, checks: list[SpawnCheck]) -> str:
    """Run-length encoded SVG cells keep diagnostics small and dependency-free."""
    config = reference.config
    rows, cols = reference.mask.shape
    scale = 6
    width, height = cols*scale, rows*scale
    codes = np.where(reference.mask, 2, np.where(reference.free_mask, 1, 0))
    colors = ("#334155", "#fbbf24", "#5eead4")
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -8 {width+16} {height+68}">',
             '<title>Exploration reference area and spawn validation</title>',
             f'<rect x="-8" y="-8" width="{width+16}" height="{height+68}" fill="white"/>']
    for row in range(rows):
        start = 0
        while start < cols:
            end = start + 1
            code = int(codes[row, start])
            while end < cols and codes[row, end] == code:
                end += 1
            parts.append(f'<rect x="{start*scale}" y="{(rows-1-row)*scale}" '
                         f'width="{(end-start)*scale}" height="{scale}" fill="{colors[code]}"/>')
            start = end
    for index, check in enumerate(checks):
        x = (check.x-config.bounds[0])/config.resolution_m*scale
        y = height-(check.y-config.bounds[1])/config.resolution_m*scale
        # Outside-bounds rejections remain visible at the edge; tooltips retain
        # their actual world coordinates and rejection reason.
        x, y = min(max(x, 0), width), min(max(y, 0), height)
        color = "#1d4ed8" if check.accepted else "#dc2626"
        parts.append(f'<circle cx="{x:g}" cy="{y:g}" r="4" fill="{color}">'
                     f'<title>Spawn {index}: {escape(check.reason)} ({check.x:g}, {check.y:g})</title></circle>')
    anchor_x = (config.component_anchor[0]-config.bounds[0])/config.resolution_m*scale
    anchor_y = height-(config.component_anchor[1]-config.bounds[1])/config.resolution_m*scale
    parts.append(f'<path d="M {anchor_x:g} {anchor_y-5:g} l 5 5 l -5 5 l -5 -5 Z" fill="#111827">'
                 '<title>Fixed reference component anchor</title></path>')
    parts.extend([
        f'<text x="0" y="{height+16}" font-family="sans-serif" font-size="11">'
        'Teal: reference area | Yellow: disconnected | Slate: blocked / no support</text>',
        f'<text x="0" y="{height+32}" font-family="sans-serif" font-size="11">'
        'Blue: accepted spawn | Red: rejected | Black: anchor | World +Y points up</text>',
        f'<text x="0" y="{height+48}" font-family="sans-serif" font-size="11">'
        f'Area {reference.metadata()["area_m2"]:.2f} m2 | Cell {config.resolution_m:g} m</text>',
        '</svg>\n',
    ])
    return "\n".join(parts)
