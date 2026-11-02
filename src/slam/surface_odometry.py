"""Point-to-plane alignment with unsupported motion directions suppressed."""

from dataclasses import dataclass

import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


# These are numerical conditioning rules, not a pose-accuracy guarantee.
PLANAR_VARIANCE_RATIO = .01
SINGULAR_VALUE_RATIO = .01
MIN_CORRESPONDENCES = 100


def surface_cloud(cloud: o3d.geometry.PointCloud) -> o3d.geometry.PointCloud:
    """Keep locally planar samples for registration, leaving the map cloud intact.

    K-nearest neighbourhoods avoid default normals from undersampled fixed-radius
    searches. Reject edges and line-like neighbourhoods whose plane is ambiguous.
    """
    result = o3d.geometry.PointCloud(cloud)
    if len(result.points) < 20:
        return o3d.geometry.PointCloud()
    result.estimate_covariances(o3d.geometry.KDTreeSearchParamKNN(knn=20))
    values, vectors = np.linalg.eigh(np.asarray(result.covariances))
    valid = (values[:, 1] > 1e-10) & (values[:, 0] < PLANAR_VARIANCE_RATIO * values[:, 1])
    result.normals = o3d.utility.Vector3dVector(vectors[:, :, 0])
    return result.select_by_index(np.flatnonzero(valid).tolist())


def registration_cloud(observation: o3d.geometry.PointCloud, map_cloud: o3d.geometry.PointCloud,
                       voxel_size: float) -> tuple[o3d.geometry.PointCloud, float]:
    """Preserve close-range support without increasing map density.

    Refine at most three times from the original observed points. A twofold
    support margin allows some correspondence loss while retaining the same
    minimum acceptance count. No points are synthesized or duplicated.
    """
    result = surface_cloud(map_cloud)
    resolution = voxel_size
    for _ in range(3):
        if len(result.points) >= 2 * MIN_CORRESPONDENCES or len(observation.points) < MIN_CORRESPONDENCES:
            break
        resolution *= .5
        finer = observation.voxel_down_sample(resolution)
        if len(finer.points) > 50:
            finer, _ = finer.remove_statistical_outlier(nb_neighbors=10, std_ratio=2.)
        result = surface_cloud(finer)
    return result, resolution


@dataclass(frozen=True)
class SurfaceAlignment:
    transformation: np.ndarray
    fitness: float
    inlier_rmse: float | None
    observable_rank: int
    correspondences: int


def align_surfaces(source: o3d.geometry.PointCloud, target: o3d.geometry.PointCloud,
                   max_distance: float, *, motion_origin: np.ndarray | None = None) -> SurfaceAlignment:
    """Estimate target-from-source about a calibrated motion origin.

    A plane constrains only three motion directions. Truncated least squares
    keeps unsupported increments zero instead of amplifying numerical noise.
    The origin is the robot body origin expressed in target camera coordinates.
    Its known camera offset accounts for camera motion during body rotation.
    Without mounting calibration, retain the coincident camera/body convention.
    A cloud centroid is not a physical motion origin.
    """
    origin = np.zeros(3) if motion_origin is None else np.asarray(motion_origin, dtype=float)
    points = np.asarray(source.points)
    reference = np.asarray(target.points)
    normals = np.asarray(target.normals)
    transform = np.eye(4)
    rank = 0
    if len(points) < 6 or len(reference) < 6:
        return SurfaceAlignment(transform, 0., None, rank, 0)
    tree = cKDTree(reference)
    for _ in range(30):
        current = points @ transform[:3, :3].T + transform[:3, 3]
        distances, indices = tree.query(current)
        inliers = distances < max_distance
        if np.count_nonzero(inliers) < 6:
            break
        p, q, n = current[inliers], reference[indices[inliers]], normals[indices[inliers]]
        jacobian = np.column_stack((np.cross(p - origin, n), n))
        residual = np.einsum("ij,ij->i", q - p, n)
        delta, _, rank, _ = np.linalg.lstsq(jacobian, residual, rcond=SINGULAR_VALUE_RATIO)
        step = np.eye(4)
        step[:3, :3] = Rotation.from_rotvec(delta[:3]).as_matrix()
        step[:3, 3] = origin + delta[3:] - step[:3, :3] @ origin
        transform = step @ transform
        if np.linalg.norm(delta) < 1e-6:
            break
    distances, _ = tree.query(points @ transform[:3, :3].T + transform[:3, 3])
    inliers = distances < max_distance
    count = int(np.count_nonzero(inliers))
    rmse = float(np.sqrt(np.mean(distances[inliers] ** 2))) if count else None
    return SurfaceAlignment(transform, count / len(points), rmse, int(rank), count)
