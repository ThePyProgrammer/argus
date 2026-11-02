"""Point-to-plane alignment with unsupported motion directions suppressed."""

from dataclasses import dataclass

import numpy as np
import open3d as o3d
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation


# These are numerical conditioning rules, not a pose-accuracy guarantee.
PLANAR_VARIANCE_RATIO = .01
SINGULAR_VALUE_RATIO = .01


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


@dataclass(frozen=True)
class SurfaceAlignment:
    transformation: np.ndarray
    fitness: float
    inlier_rmse: float | None
    observable_rank: int
    correspondences: int


def align_surfaces(source: o3d.geometry.PointCloud, target: o3d.geometry.PointCloud,
                   max_distance: float) -> SurfaceAlignment:
    """Estimate target-from-source using small rigid updates about the camera.

    A plane constrains only three motion directions. Truncated least squares
    keeps unsupported increments zero instead of amplifying numerical noise.
    Rotating about a cloud centroid would introduce an unsupported translation
    when only a wall is visible, so increments use the camera origin.
    """
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
        jacobian = np.column_stack((np.cross(p, n), n))
        residual = np.einsum("ij,ij->i", q - p, n)
        delta, _, rank, _ = np.linalg.lstsq(jacobian, residual, rcond=SINGULAR_VALUE_RATIO)
        step = np.eye(4)
        step[:3, :3] = Rotation.from_rotvec(delta[:3]).as_matrix()
        step[:3, 3] = delta[3:]
        transform = step @ transform
        if np.linalg.norm(delta) < 1e-6:
            break
    distances, _ = tree.query(points @ transform[:3, :3].T + transform[:3, 3])
    inliers = distances < max_distance
    count = int(np.count_nonzero(inliers))
    rmse = float(np.sqrt(np.mean(distances[inliers] ** 2))) if count else None
    return SurfaceAlignment(transform, count / len(points), rmse, int(rank), count)
