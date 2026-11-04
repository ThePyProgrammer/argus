"""Separate an observed floor plane before scans accumulate pose/voxel error.

The calibrated sensor-to-floor distance is a robot assumption, not a scene
oracle. No plane is removed unless local surface normals, height, support, and
two-dimensional extent agree. Unknown surfaces remain obstacles.
"""

from dataclasses import dataclass
import math

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class FloorFilter:
    camera_height_m: float = .32
    height_tolerance_m: float = .04
    distance_tolerance_m: float = .015
    max_tilt_degrees: float = 25.
    min_support: int = 40
    min_axis_spread_m: float = .08

    def __post_init__(self):
        for name in ("camera_height_m", "height_tolerance_m", "distance_tolerance_m", "min_axis_spread_m"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.height_tolerance_m >= self.camera_height_m or not 0 < self.max_tilt_degrees < 90:
            raise ValueError("Invalid floor height/tilt calibration")
        if not isinstance(self.min_support, int) or self.min_support < 3:
            raise ValueError("At least three supporting points are required")

    def mask(self, points: np.ndarray, sensor_origin: np.ndarray) -> np.ndarray:
        """Return floor inliers in one SLAM frame, without mutating its cloud.

        Rank eligible planes by residual-weighted support, then by height.
        Calibration bounds detection during large body-height/attitude changes;
        the first benchmark assumes an upright Go2 on approximately level floor.
        """
        points = np.asarray(points, dtype=float)
        result = np.zeros(len(points), dtype=bool)
        valid = np.flatnonzero(np.isfinite(points).all(axis=1))
        if len(valid) < self.min_support:
            return result
        cloud = points[valid]
        order = np.lexsort((cloud[:, 2], cloud[:, 1], cloud[:, 0]))
        sample = cloud[order[np.linspace(0, len(order) - 1, min(1024, len(order)), dtype=int)]]
        _, indices = cKDTree(cloud).query(sample, k=min(12, len(cloud)))
        neighbors = cloud[indices]
        centers = neighbors.mean(axis=1)
        centered = neighbors - centers[:, None, :]
        eigenvalues, eigenvectors = np.linalg.eigh(np.einsum("nki,nkj->nij", centered, centered))
        normals = eigenvectors[:, :, 0]
        normals[normals[:, 2] < 0] *= -1
        distances = np.einsum("ni,ni->n", sensor_origin - centers, normals)
        cosine = math.cos(math.radians(self.max_tilt_degrees))
        eligible = ((normals[:, 2] >= cosine)
                    & (eigenvalues[:, 0] < .1 * eigenvalues[:, 1])
                    & (np.abs(distances - self.camera_height_m) <= self.height_tolerance_m))
        candidates = np.flatnonzero(eligible)
        # A locally tilted wall/floor edge can appear lower than the actual
        # floor while fitting only a narrow strip. Weight support by residual
        # so a tilted plane cannot win by grazing additional obstacle points.
        # Rank before quantized hypothesis deduplication as well as refinement.
        candidates = sorted(candidates, key=lambda i: (
            -float(np.maximum(0., 1. - (((cloud - centers[i]) @ normals[i])
                                       / self.distance_tolerance_m) ** 2).sum()),
            -float(distances[i]), *centers[i]))
        tried = set()
        for index in candidates:
            normal, center = normals[index], centers[index]
            offset = float(normal @ center)
            key = tuple(np.round(np.r_[normal * 20, offset / self.distance_tolerance_m]).astype(int))
            if key in tried:
                continue
            tried.add(key)
            inliers = np.abs(cloud @ normal - offset) <= self.distance_tolerance_m
            if int(inliers.sum()) < self.min_support:
                continue
            support = cloud[inliers]
            center = support.mean(axis=0)
            _, spread, axes = np.linalg.svd(support - center, full_matrices=False)
            if spread[1] / math.sqrt(len(support)) < self.min_axis_spread_m:
                continue
            normal = axes[-1]
            if normal[2] < 0:
                normal = -normal
            height = float((sensor_origin - center) @ normal)
            if normal[2] < cosine or abs(height - self.camera_height_m) > self.height_tolerance_m:
                continue
            result[valid] = np.abs((cloud - center) @ normal) <= self.distance_tolerance_m
            return result
        return result


class FloorTracker:
    """Reuse an observed floor plane through gait-height changes and narrow views.

    Bootstrap uses the full stateless filter. Once established, the plane lives
    in the estimated map frame and can classify sparse observations without
    pretending each frame independently established a floor. Fresh supported
    detections may replace it when the implied height at the camera agrees.
    This is a flat-floor assumption, not a general terrain classifier.
    """

    def __init__(self, config: FloorFilter | None = None):
        self.config = config or FloorFilter()
        self._plane: tuple[np.ndarray, float] | None = None
        self.reacquired = False

    @property
    def plane(self) -> tuple[np.ndarray, float] | None:
        return None if self._plane is None else (self._plane[0].copy(), self._plane[1])

    def _fit(self, support: np.ndarray) -> tuple[np.ndarray, float] | None:
        if len(support) < self.config.min_support:
            return
        center = support.mean(axis=0)
        _, spread, axes = np.linalg.svd(support - center, full_matrices=False)
        if spread[1] / math.sqrt(len(support)) < self.config.min_axis_spread_m:
            return
        normal = axes[-1]
        if normal[2] < 0:
            normal = -normal
        if normal[2] < math.cos(math.radians(self.config.max_tilt_degrees)):
            return
        return normal.copy(), float(normal @ center)

    def mask(self, points: np.ndarray, sensor_origin: np.ndarray) -> np.ndarray:
        points = np.asarray(points, dtype=float)
        self.reacquired = False
        fresh = self.config.mask(points, sensor_origin)
        candidate = self._fit(points[fresh])
        if self._plane is None:
            self._plane = candidate
            return fresh

        normal, offset = self._plane
        historical = (np.isfinite(points).all(axis=1)
                      & (np.abs(points @ normal - offset) <= self.config.distance_tolerance_m))
        if candidate is not None:
            new_normal, new_offset = candidate
            old_height = float(sensor_origin @ normal - offset)
            new_height = float(sensor_origin @ new_normal - new_offset)
            # A small attitude error produces a large distant-plane residual.
            # Compare heights at the current camera, not distant map points.
            # This still rejects a competing raised plane beyond the inlier band.
            if abs(new_height - old_height) <= self.config.distance_tolerance_m:
                self.reacquired = int((fresh & ~historical).sum()) >= self.config.min_support
                self._plane = candidate
                return fresh
        # Narrow views and gait-height dips reuse history without refitting a
        # truncated strip of inliers. Such a fit can drift onto wall-base points.
        return historical
