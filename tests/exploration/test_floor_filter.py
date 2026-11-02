"""Floor separation under pose shifts, sparse support, and low obstacles."""

import numpy as np
import pytest

from src.exploration.floor_filter import FloorFilter
from src.exploration.occupancy_grid import CELL_FREE, CELL_OCCUPIED, project_voxels_to_2d


def plane(z=0., *, side=2., count=31):
    x, y = np.meshgrid(np.linspace(-side / 2, side / 2, count), np.linspace(-side / 2, side / 2, count))
    return np.column_stack((x.ravel(), y.ravel(), np.full(x.size, z)))


@pytest.mark.parametrize("offset,tilt", [(0, 0), (.17, 0), (-.25, 12), (.1, -18)])
def test_floor_removed_before_pose_errors_spread_it_across_height_bins(offset, tilt):
    floor = plane()
    obstacles = plane(.06, side=.4, count=15)
    points = np.vstack([floor, obstacles])
    angle = np.deg2rad(tilt)
    rotation = np.array([[np.cos(angle), 0, np.sin(angle)], [0, 1, 0], [-np.sin(angle), 0, np.cos(angle)]])
    translation = np.array([2., -1., offset])
    transformed = points @ rotation.T + translation
    origin = np.array([0, 0, .32]) @ rotation.T + translation
    before = transformed.copy()
    mask = FloorFilter().mask(transformed, origin)
    assert mask[:len(floor)].mean() > .99
    assert not mask[len(floor):].any()
    np.testing.assert_array_equal(transformed, before)


def test_floor_need_not_be_largest_height_bin_or_majority_surface():
    floor = plane(side=1, count=20)
    wall = plane(side=2, count=80)[:, [2, 0, 1]] + [.8, 0, 1]
    points = np.vstack([floor, wall])
    mask = FloorFilter().mask(points, np.array([0, 0, .32]))
    assert mask[:len(floor)].mean() > .99
    assert not mask[len(floor):][wall[:, 2] > .02].any()


@pytest.mark.parametrize("points", [plane(.05), plane(.08), plane(.5), plane()[:20], plane()[:, [2, 0, 1]]])
def test_missing_floor_raised_surface_and_wall_are_not_erased(points):
    assert not FloorFilter().mask(points, np.array([0, 0, .32])).any()


def test_floor_classification_is_independent_of_point_order():
    cloud = np.vstack([plane(), plane(.06, side=.4, count=15)])
    first = FloorFilter().mask(cloud, np.array([0, 0, .32]))
    order = np.random.default_rng(42).permutation(len(cloud))
    second = FloorFilter().mask(cloud[order], np.array([0, 0, .32]))
    np.testing.assert_array_equal(second, first[order])


def test_observed_floor_creates_free_space_but_does_not_erase_low_obstacle():
    floor = plane()
    obstacle = plane(.06, side=.4, count=15)
    cloud = np.vstack([floor, obstacle])
    mask = FloorFilter().mask(cloud, np.array([0, 0, .32]))
    grid = project_voxels_to_2d(cloud[~mask], .1, observed_free_xy=cloud[mask, :2])
    assert grid.grid[grid.world_to_grid(np.array([0., 0.]))] == CELL_OCCUPIED
    assert grid.grid[grid.world_to_grid(np.array([.8, .8]))] == CELL_FREE


def test_projection_does_not_erase_a_dominant_obstacle_layer():
    obstacle = plane(.06)
    grid = project_voxels_to_2d(np.vstack([obstacle, [[1.5, 1.5, 1.]]]), .1)
    assert grid.grid[grid.world_to_grid(np.array([0., 0.]))] == CELL_OCCUPIED


def test_projection_and_world_queries_use_the_same_cell_convention():
    points = np.array([[.049, .051, .2], [.151, .149, .2], [-.151, -.149, .2]])
    grid = project_voxels_to_2d(points, .1)
    for point in points:
        assert grid.grid[grid.world_to_grid(point[:2])] == CELL_OCCUPIED


def test_real_depth_preserves_six_centimeter_obstacle():
    import mujoco
    from src.bridge.sensor_types import CameraIntrinsics
    from src.slam.depth_to_cloud import depth_to_pointcloud
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom type="plane" size="2 2 .1"/>
      <geom type="box" size=".035 .035 .03" pos=".09 0 .03"/>
      <camera name="cam" pos="0 0 .32" fovy="70"/>
    </worldbody></mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, width=64, height=48) as renderer:
        renderer.update_scene(data, camera="cam")
        renderer.enable_depth_rendering()
        depth = renderer.render().copy()
    cloud = depth_to_pointcloud(depth, np.zeros((48, 64, 3), np.uint8),
                               CameraIntrinsics.from_fov(64, 48), cloud_config_key="1")
    points = np.asarray(cloud.points).copy() + [0, 0, .32]
    mask = FloorFilter().mask(points, np.array([0., 0., .32]))
    obstacle = points[:, 2] > .05
    floor = np.abs(points[:, 2]) < 1e-5
    assert obstacle.any() and floor.any()
    assert not mask[obstacle].any()
    assert mask[floor].mean() > .99


@pytest.mark.parametrize("robot_id,ticks", [("robot_a", 0), ("robot_b", 2), ("robot_b", 6)])
def test_rendered_column_edges_do_not_displace_supported_floor(robot_id, ticks):
    from src.exploration.evaluation.episode import ExplorationEpisode
    from src.slam.slam_pipeline import SLAMPipeline

    with ExplorationEpisode.from_scenario("cluttered_room", 101, horizon_s=.1) as episode:
        for _ in range(ticks):
            episode.advance()
        frame = episode.bridge.get_frame(robot_id)
        pipeline = SLAMPipeline(episode.bridge.camera_intrinsics(robot_id), cloud_config_key="1")
        pipeline.process_frame(frame)
        points = pipeline.last_frame_cloud
        mask = FloorFilter().mask(points, frame.ground_truth_pose[:3, 3])
        floor = np.abs(points[:, 2]) <= .002
        raised = points[:, 2] > .04
        assert floor.sum() >= 100
        assert mask[floor].mean() > .99
        assert not mask[raised].any()
