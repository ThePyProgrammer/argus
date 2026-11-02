"""Degenerate geometry and rejected-frame handling for surface odometry."""

import numpy as np
import open3d as o3d
import pytest
from scipy.spatial.transform import Rotation

from src.slam.surface_odometry import align_surfaces, surface_cloud


def plane_cloud():
    x, y = np.meshgrid(np.linspace(-1., 1., 30), np.linspace(-1., 1., 30))
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(np.column_stack((x.ravel(), y.ravel(), np.full(x.size, -2.))))
    cloud.normals = o3d.utility.Vector3dVector(np.tile([0., 0., 1.], (x.size, 1)))
    return cloud


def test_wall_rotation_does_not_invent_sideways_camera_motion():
    target = plane_cloud()
    rotation = Rotation.from_rotvec([.02, -.04, 0.]).as_matrix()
    source = o3d.geometry.PointCloud(target)
    source.points = o3d.utility.Vector3dVector(np.asarray(target.points) @ rotation)
    result = align_surfaces(source, target, .15)
    assert result.observable_rank == 3
    assert result.fitness > .99
    np.testing.assert_allclose(result.transformation[:3, :3], rotation, atol=1e-6)
    np.testing.assert_allclose(result.transformation[:3, 3], 0., atol=1e-6)


def test_wall_tangent_translation_remains_unobserved():
    target = plane_cloud()
    source = o3d.geometry.PointCloud(target)
    source.translate([.03, .02, .01])
    result = align_surfaces(source, target, .15)
    assert result.observable_rank == 3
    np.testing.assert_allclose(result.transformation[:3, 3], [0., 0., -.01], atol=1e-6)


def test_surface_preparation_preserves_input_and_rejects_lines():
    cloud = plane_cloud()
    points = np.asarray(cloud.points).copy()
    prepared = surface_cloud(cloud)
    assert len(prepared.points) == len(points)
    np.testing.assert_array_equal(np.asarray(cloud.points), points)
    line = o3d.geometry.PointCloud()
    line.points = o3d.utility.Vector3dVector(np.column_stack((np.linspace(-1., 1., 100), np.zeros((100, 2)))))
    assert len(surface_cloud(line).points) == 0


@pytest.mark.parametrize("empty_source", [True, False])
def test_missing_correspondences_do_not_claim_a_pose_update(empty_source):
    target = plane_cloud()
    source = o3d.geometry.PointCloud() if empty_source else o3d.geometry.PointCloud(target).translate([0., 0., 10.])
    result = align_surfaces(source, target, .09)
    assert result.fitness == 0.
    assert result.observable_rank == 0
    assert result.inlier_rmse is None
    np.testing.assert_array_equal(result.transformation, np.eye(4))
