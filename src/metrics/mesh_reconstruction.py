"""Server-side mesh reconstruction using Open3D Poisson surface reconstruction.

Follows the project's optional dependency pattern: try/import with _AVAILABLE
flag and INSTALL_HINT for graceful degradation when Open3D is not installed.
"""

import numpy as np

INSTALL_HINT = "Mesh mode requires Open3D. Install: pip install open3d"

try:
    import open3d as o3d

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


def reconstruct_mesh_available() -> bool:
    """Check if mesh reconstruction is available (Open3D installed)."""
    return _AVAILABLE


def reconstruct_mesh(
    points: np.ndarray,
    colors: np.ndarray | None = None,
    depth: int = 7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Reconstruct triangle mesh from point cloud using Poisson reconstruction.

    Args:
        points: (N, 3) float64 point positions.
        colors: Optional (N, 3) float64 colors [0-1].
        depth: Octree depth for Poisson reconstruction (7-9 typical).

    Returns:
        (vertices, faces, vertex_colors) as (V,3), (F,3), and optional (V,3) numpy arrays.
        Returns (empty, empty, None) if fewer than 10 points.

    Raises:
        ImportError: If Open3D is not available.
    """
    if not _AVAILABLE:
        raise ImportError(INSTALL_HINT)

    if len(points) < 10:
        return np.empty((0, 3), dtype=np.float64), np.empty((0, 3), dtype=np.int64), None

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points.astype(np.float64))
    if colors is not None:
        pcd.colors = o3d.utility.Vector3dVector(colors.astype(np.float64))

    # Normals required for Poisson reconstruction
    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.2, max_nn=30)
    )
    pcd.orient_normals_consistent_tangent_plane(k=15)

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd, depth=depth
    )

    # Remove low-density vertices (cleanup artifacts)
    densities_arr = np.asarray(densities)
    if len(densities_arr) > 0:
        vertices_to_remove = densities_arr < np.quantile(densities_arr, 0.01)
        mesh.remove_vertices_by_mask(vertices_to_remove)

    vertices = np.asarray(mesh.vertices)
    faces = np.asarray(mesh.triangles)

    # Transfer vertex colors if available
    vertex_colors = None
    if mesh.has_vertex_colors():
        vertex_colors = np.asarray(mesh.vertex_colors)

    return vertices, faces, vertex_colors
