"""Rendered oblique planes expose half-pixel errors hidden by frontal views."""

import mujoco
import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics
from src.slam.depth_to_cloud import depth_to_pointcloud


@pytest.mark.parametrize("width,height", [(64, 48), (65, 49), (320, 240)])
def test_rendered_oblique_floor_unprojects_to_authored_plane(width, height):
    model = mujoco.MjModel.from_xml_string('''<mujoco>
      <compiler angle="degree"/>
      <statistic extent="1"/>
      <visual><map znear=".1" zfar="20"/></visual>
      <worldbody>
        <geom type="plane" size="20 20 .1"/>
        <camera name="camera" pos="1 -2 3" euler="25 15 10" fovy="70"/>
      </worldbody>
    </mujoco>''')
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    with mujoco.Renderer(model, width=width, height=height) as renderer:
        renderer.update_scene(data, camera="camera")
        renderer.enable_depth_rendering()
        depth = renderer.render().copy()
    cloud = depth_to_pointcloud(depth, None, CameraIntrinsics.from_fov(width, height),
                               max_depth=20., cloud_config_key="1")
    points = np.asarray(cloud.points) @ data.cam_xmat[0].reshape(3, 3).T + data.cam_xpos[0]
    assert len(points) == width * height
    # Check authored geometry, without fitting a plane to the reconstructed points.
    # Allow 0.2 mm of raster/depth precision error, far below the old 1-6 cm bias.
    np.testing.assert_allclose(points[:, 2], 0., atol=2e-4, rtol=0.)
