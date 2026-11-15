"""Known-map unit fixtures: real gait/physics, no exploration or video claim."""
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.scene_builder import build_multi_robot_scene
from src.control.motion_clearance import MotionClearanceGuard
from src.exploration.config import ExplorationConfig
from tests.control.test_motion_clearance import room


@pytest.mark.parametrize("direction", [-1., 1.])
@pytest.mark.parametrize("wall_distance", [1.1, 1.5])
def test_actual_forward_and_reverse_motion_preserve_wall_clearance(monkeypatch, direction, wall_distance):
    monkeypatch.setattr(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda:None))
    monkeypatch.setattr(MultiRobotBridge, "_capture_frame", lambda *a:None)
    positions={"robot_a":(0.,0.,.3)}
    def model():
        xml, assets=build_multi_robot_scene(Go2Platform(),positions)
        root=ET.fromstring(xml)
        ET.SubElement(root.find('worldbody'),'geom',name='guard_wall',type='box',
                      pos=f'{direction*wall_distance} 0 .5',size='.025 2 .5',contype='1',conaffinity='1')
        return mujoco.MjModel.from_xml_string(ET.tostring(root,encoding='unicode'),assets)
    bridge=MultiRobotBridge(MultiRobotConfig(robot_ids=('robot_a',),spawn_positions=positions,
                                            spawn_headings={'robot_a':0.},launch_viewer=False),model_factory=model)
    try:
        bridge.start()
        config=ExplorationConfig()
        guard=MotionClearanceGuard(config)
        grid=room((0,direction*wall_distance))
        radius=config.planning_radius(np.linalg.norm([.4,0,.05]),grid.resolution,
                                      bridge._collision_radii['robot_a'])
        start=bridge.get_body_position('robot_a')
        minimum=float('inf')
        scaled=0
        for index in range(300):
            # Perfect state is an explicit unit-test oracle; production supplies
            # only SLAM-derived poses to this same guard interface.
            base=bridge.mj_model.body('robot_a_base').id
            p=np.eye(4)
            p[:3,:3]=bridge.mj_data.xmat[base].reshape(3,3)
            p[:3,3]=bridge.get_body_position('robot_a')
            decision=guard.filter(np.array([direction*.8,0.]),0.,pose=p,
                                  sim_time=index*bridge.frame_dt,observation_time=index*bridge.frame_dt,
                                  grid=grid,radius=radius,calibration_valid=True,tracking_ok=True)
            scaled+=decision.scale<1
            if index:
                assert decision.stopping_clear, (index, direction, decision.reason, decision.clearance_m)
            bridge.set_velocity('robot_a',decision.linear,decision.angular)
            bridge.step()
            assert bridge.get_body_position('robot_a')[2] > .20
            camera=bridge.mj_model.camera('robot_a_cam').id
            clearance=abs(direction*wall_distance-bridge.mj_data.cam_xpos[camera,0])-.025
            minimum=min(minimum,clearance)
            wall=bridge.mj_model.geom('guard_wall').id
            assert not any(c.dist<=0 and wall in (int(c.geom1),int(c.geom2)) for c in bridge.mj_data.contact)
        displacement=(bridge.get_body_position('robot_a')-start)[0]
        if wall_distance == 1.5:
            assert direction*displacement>.03
        # Keep the original 1.1 m fixture as a safety check. The calibrated
        # posture uncertainty can prohibit useful progress there; that is not
        # an exploration success. The wider fixture separately requires motion.
        assert minimum>=config.camera_standoff_m
        assert scaled>0
    finally:
        bridge.stop()
