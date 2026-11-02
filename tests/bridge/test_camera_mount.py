"""Camera/body separation using compiled mounting calibration, not world truth."""

import mujoco
import numpy as np
import pytest

from src.bridge.sensor_types import SensorFrame, fixed_camera_mount


@pytest.mark.parametrize("yaw", [0., .7, -1.9])
def test_mount_recovers_body_position_and_heading_at_arbitrary_world_pose(yaw):
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <body name="robot" pos="1 2 .3"><freejoint/><geom size=".1"/>
        <camera name="cam" pos=".4 0 .05" xyaxes="0 -1 0 0 0 1"/>
      </body></worldbody></mujoco>''')
    data = mujoco.MjData(model)
    data.qpos[3:7] = [np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)]
    mujoco.mj_forward(model, data)
    camera = np.eye(4)
    camera[:3, :3], camera[:3, 3] = data.cam_xmat[0].reshape(3, 3), data.cam_xpos[0]
    mount = fixed_camera_mount(model, 0, model.body("robot").id)
    frame = SensorFrame(np.zeros((1, 1, 3), np.uint8), None, np.eye(4), 0.,
                        body_from_camera=mount)
    body = frame.body_pose_from_camera(camera)
    np.testing.assert_allclose(body[:3, 3], data.xpos[model.body("robot").id], atol=1e-12)
    np.testing.assert_allclose(body[:3, :3], data.xmat[model.body("robot").id].reshape(3, 3), atol=1e-12)
    # Estimated pose errors must propagate rather than being corrected by GT.
    camera[:3, 3] += [2., -3., 1.]
    np.testing.assert_allclose(frame.body_pose_from_camera(camera)[:3, 3], body[:3, 3] + [2., -3., 1.])
    np.testing.assert_array_equal(frame.ground_truth_pose, np.eye(4))


def test_world_camera_cannot_masquerade_as_a_body_mounted_sensor():
    model = mujoco.MjModel.from_xml_string('''<mujoco><worldbody><camera name="cam"/>
      <body name="robot"><geom size=".1"/></body></worldbody></mujoco>''')
    with pytest.raises(ValueError, match="root body"):
        fixed_camera_mount(model, 0, model.body("robot").id)
