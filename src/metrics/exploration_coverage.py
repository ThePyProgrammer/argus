"""Passive floor visibility and fixed-horizon exploration measurements.

Only captured sensor data crosses this boundary. Reference geometry is never
queried for visibility and must never be passed back to navigation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from numbers import Integral, Real
from pathlib import Path
from typing import Mapping

import numpy as np

from src.metrics.exploration_reference import ReferenceGrid


COVERAGE_VERSION = "floor-depth-support-v2"
TERMINATION_REASONS = frozenset({
    "horizon", "no_frontiers", "all_unreachable", "all_robots_failed", "algorithm_error",
})


def _number(value, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _readonly(value: np.ndarray) -> np.ndarray:
    """Copy into immutable storage, including against setflags(write=True)."""
    return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)


@dataclass(frozen=True)
class CameraCalibration:
    """Intrinsics with integer coordinates at pixel centers, as in Open3D."""
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def __post_init__(self):
        for name in ("fx", "fy", "cx", "cy"):
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.fx <= 0 or self.fy <= 0:
            raise ValueError("Focal lengths must be positive")
        for name in ("width", "height"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 2:
                raise ValueError("Image dimensions must be integers of at least two pixels")
            object.__setattr__(self, name, int(value))


@dataclass(frozen=True)
class DepthObservation:
    sim_time: float
    world_from_camera: np.ndarray = field(repr=False)
    depth: np.ndarray | None = field(repr=False)
    calibration: CameraCalibration

    def __post_init__(self):
        object.__setattr__(self, "sim_time", _number(self.sim_time, "sim_time"))
        if not isinstance(self.calibration, CameraCalibration):
            raise ValueError("An immutable CameraCalibration is required")
        pose = np.asarray(self.world_from_camera, dtype=np.float64)
        if (pose.shape != (4, 4) or not np.isfinite(pose).all()
                or not np.allclose(pose[3], [0, 0, 0, 1], rtol=0, atol=1e-8)
                or not np.allclose(pose[:3, :3].T @ pose[:3, :3], np.eye(3), rtol=0, atol=1e-6)
                or not math.isclose(np.linalg.det(pose[:3, :3]), 1, abs_tol=1e-6)):
            raise ValueError("world_from_camera must be a rigid homogeneous transform")
        object.__setattr__(self, "world_from_camera", _readonly(pose))
        if self.depth is not None:
            depth = np.asarray(self.depth)
            if (depth.shape != (self.calibration.height, self.calibration.width)
                    or not np.issubdtype(depth.dtype, np.floating)):
                raise ValueError("Depth must be an H x W floating-point metric image")
            object.__setattr__(self, "depth", _readonly(depth))

    @classmethod
    def from_frame(cls, frame, intrinsics) -> DepthObservation:
        """Snapshot the bridge frame's capture-time camera transform and calibration."""
        calibration = CameraCalibration(**{
            key: getattr(intrinsics, key) for key in ("fx", "fy", "cx", "cy", "width", "height")
        })
        return cls(frame.sim_time, frame.ground_truth_pose, frame.depth, calibration)


@dataclass(frozen=True)
class CoverageConfig:
    horizon_s: float = 300.0
    threshold: float = .9
    min_depth_m: float = .01
    max_depth_m: float = 20.0
    depth_absolute_tolerance_m: float = .005
    depth_relative_tolerance: float = .001

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _number(getattr(self, name), name))
        if self.horizon_s <= 0 or not 0 < self.threshold <= 1:
            raise ValueError("Positive horizon and threshold in (0, 1] are required")
        if not 0 < self.min_depth_m < self.max_depth_m:
            raise ValueError("Depth range must be positive and ordered")
        if self.depth_absolute_tolerance_m < 0 or self.depth_relative_tolerance < 0:
            raise ValueError("Depth tolerances cannot be negative")


def _floor_points(reference: ReferenceGrid) -> np.ndarray:
    rows, cols = np.nonzero(reference.mask)
    x0, y0 = reference.config.bounds[:2]
    res = reference.config.resolution_m
    return np.column_stack((x0 + (cols + .5) * res, y0 + (rows + .5) * res,
                            np.full(len(rows), reference.floor_height_m)))


def _visible(points: np.ndarray, floor_z: float, observation: DepthObservation,
             config: CoverageConfig) -> np.ndarray:
    visible = np.zeros(len(points), dtype=bool)
    if observation.depth is None or observation.world_from_camera[2, 3] <= floor_z:
        return visible
    pose, cal = observation.world_from_camera, observation.calibration
    camera = (points - pose[:3, 3]) @ pose[:3, :3]
    axial = -camera[:, 2]  # MuJoCo looks down -Z, with +Y up.
    candidates = np.flatnonzero((axial >= config.min_depth_m) & (axial <= config.max_depth_m))
    camera, axial = camera[candidates], axial[candidates]
    u = cal.fx * camera[:, 0] / axial + cal.cx
    v = cal.cy - cal.fy * camera[:, 1] / axial
    # Four surrounding pixel centers must all see the floor. This intentionally
    # rejects the outer half-pixel border and ambiguous silhouettes. Intrinsics
    # use integer pixel centers, shared with SLAM's depth unprojection.
    inside = (u >= 0) & (u < cal.width - 1) & (v >= 0) & (v < cal.height - 1)
    candidates, u, v = candidates[inside], u[inside], v[inside]
    col, row = np.floor(u).astype(int), np.floor(v).astype(int)
    supported = np.ones(len(candidates), dtype=bool)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        x = (col + dx - cal.cx) / cal.fx
        y = -(row + dy - cal.cy) / cal.fy
        world_ray_z = pose[2, 0] * x + pose[2, 1] * y - pose[2, 2]
        expected = np.zeros(len(x))
        downward = world_ray_z < 0
        np.divide(floor_z - pose[2, 3], world_ray_z, out=expected, where=downward)
        measured = observation.depth[row + dy, col + dx]
        tolerance = config.depth_absolute_tolerance_m + config.depth_relative_tolerance * expected
        supported &= (downward & np.isfinite(measured)
                      & (measured >= config.min_depth_m) & (measured <= config.max_depth_m)
                      & (expected >= config.min_depth_m) & (expected <= config.max_depth_m)
                      & (np.abs(measured - expected) <= tolerance))
    visible[candidates] = supported
    return visible


def visible_reference_cells(reference: ReferenceGrid, observation: DepthObservation,
                            config: CoverageConfig = CoverageConfig()) -> np.ndarray:
    """Return a grid mask supported by captured depth, without ray-casting geometry."""
    result = np.zeros(reference.mask.shape, dtype=bool)
    result[reference.mask] = _visible(_floor_points(reference), reference.floor_height_m, observation, config)
    return result


class CoverageCollector:
    """Accumulate first sightings on a simulation clock that starts after settling.

    Batches are atomic and may omit robots without new frames. A missing depth
    image counts as a received frame but contributes no observations. Times must
    be monotonic, and each robot may contribute at most one frame at a given time.
    """

    def __init__(self, reference: ReferenceGrid, robot_ids: tuple[str, ...], *,
                 start_sim_time: float, config: CoverageConfig = CoverageConfig()):
        self.robot_ids = tuple(robot_ids)
        if (not self.robot_ids or len(set(self.robot_ids)) != len(self.robot_ids)
                or any(not isinstance(r, str) or not r for r in self.robot_ids)):
            raise ValueError("Unique nonempty robot IDs are required")
        self.reference, self.config = reference, config
        self.start_sim_time = _number(start_sim_time, "start_sim_time")
        self._points = _floor_points(reference)
        if not len(self._points):
            raise ValueError("Reference area is empty")
        self._first = np.full((len(self.robot_ids), len(self._points)), np.inf)
        self._frames = dict.fromkeys(self.robot_ids, 0)
        self._missing = dict.fromkeys(self.robot_ids, 0)
        self._last_frame = dict.fromkeys(self.robot_ids, -math.inf)
        self._stopped: dict[str, float] = {}
        self._elapsed = 0.0
        self._reason: str | None = None

    def _time(self, sim_time: float) -> float:
        if self._reason is not None:
            raise ValueError("Episode measurements have ended")
        elapsed = _number(sim_time, "sim_time") - self.start_sim_time
        if math.isclose(elapsed, self.config.horizon_s, rel_tol=0, abs_tol=1e-9):
            elapsed = self.config.horizon_s
        if elapsed < self._elapsed or elapsed > self.config.horizon_s:
            raise ValueError("Time must be monotonic and within the episode horizon")
        return elapsed

    def observe_batch(self, sim_time: float, observations: Mapping[str, DepthObservation]) -> dict:
        elapsed = self._time(sim_time)
        pending = {}
        for robot, observation in observations.items():
            if robot not in self._frames or robot in self._stopped:
                raise ValueError("Observation belongs to an unknown or stopped robot")
            if observation.sim_time != sim_time or sim_time <= self._last_frame[robot]:
                raise ValueError("Frames must match the batch capture time and cannot be repeated")
            pending[robot] = _visible(self._points, self.reference.floor_height_m, observation, self.config)
        for robot, visible in pending.items():
            index = self.robot_ids.index(robot)
            self._first[index, visible & np.isinf(self._first[index])] = elapsed
            self._frames[robot] += 1
            self._missing[robot] += int(observations[robot].depth is None)
            self._last_frame[robot] = sim_time
        self._elapsed = elapsed
        return self.snapshot()

    def advance(self, sim_time: float) -> None:
        self._elapsed = self._time(sim_time)

    def stop_robot(self, robot_id: str, sim_time: float) -> None:
        elapsed = self._time(sim_time)
        if robot_id not in self._frames or robot_id in self._stopped:
            raise ValueError("Robot must be active")
        self._stopped[robot_id] = elapsed
        self._elapsed = elapsed

    def snapshot(self) -> dict:
        seen = np.isfinite(self._first)
        union = seen.any(axis=0)
        observed = int(union.sum())
        return {
            "elapsed_s": self._elapsed,
            "observed_cells": observed,
            "coverage": float(union.mean()),
            "overlap": float((seen.sum(axis=0) >= 2).sum() / observed) if observed else 0.0,
            "zero_observation": observed == 0,
            "per_robot_observed_cells": dict(zip(self.robot_ids, map(int, seen.sum(axis=1)))),
            "sensor_frames": dict(self._frames),
            "missing_depth_frames": dict(self._missing),
        }

    def finalize(self, reason: str) -> dict:
        if self._reason is not None or reason not in TERMINATION_REASONS:
            raise ValueError("A valid, single termination is required")
        if reason == "horizon" and self._elapsed != self.config.horizon_s:
            raise ValueError("Horizon termination requires reaching the horizon")
        self._reason = reason
        first = self._first.min(axis=0)
        # Exact integral of the right-continuous, zero-order-held coverage curve.
        # Infinite (unobserved) times contribute zero, including after failure.
        auc = np.maximum(0, self.config.horizon_s - first).mean() / self.config.horizon_s
        rank = int(np.searchsorted(np.arange(1, len(first) + 1) / len(first), self.config.threshold))
        threshold_time = float(np.sort(first)[rank])
        success = math.isfinite(threshold_time)
        return {
            **self.snapshot(), "coverage_version": COVERAGE_VERSION,
            "reference_sha256": self.reference.metadata()["reference_sha256"],
            "config": asdict(self.config), "start_sim_time": self.start_sim_time,
            "termination_reason": reason, "normalized_auc": float(auc),
            "threshold_success": success,
            "time_to_threshold_s": threshold_time if success else None,
            "capped_time_s": threshold_time if success else self.config.horizon_s,
            "stopped_robots": dict(self._stopped),
        }

    def first_observation_times(self) -> np.ndarray:
        """Robot x row x column array; infinity means outside R or never seen."""
        result = np.full((len(self.robot_ids), *self.reference.mask.shape), np.inf)
        result[:, self.reference.mask] = self._first
        return _readonly(result)

    def write_observations(self, path: str | Path) -> None:
        """Portable arrays suffice to regenerate coverage, overlap, and AUC."""
        np.savez_compressed(path, robot_ids=np.asarray(self.robot_ids),
                            first_seen_s=self.first_observation_times(), reference_mask=self.reference.mask)
