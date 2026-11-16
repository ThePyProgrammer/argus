"""Known-map recovery fixtures with real gait/physics and exact test pose oracles.

No SLAM or live-exploration claim: simulator poses supply test estimates only.
"""
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
import pytest

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.scene_builder import build_multi_robot_scene
from src.exploration.config import ExplorationConfig
from src.exploration.evaluation.episode import _contacts
from src.exploration.exploration_loop import ExplorationLoop
from src.exploration.frontier_detector import FrontierCluster
from src.metrics.contact_metrics import PhysicsContactCollector
from tests.control.test_motion_clearance import room
from tests.exploration.test_exploration_loop import MockSLAM, MockOctoMap
from tests.exploration.test_motion_clearance_integration import frame


@pytest.mark.timeout(90)
@pytest.mark.parametrize("trapped", [False, True])
def test_physical_blockage_recovery_or_explicit_trap(monkeypatch, trapped):
    monkeypatch.setattr(mujoco, "Renderer", lambda *a, **kw: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(MultiRobotBridge, "_capture_frame", lambda *a: None)
    positions = {"robot_a": (0., 0., .3)}
    wall_distance = .7 if trapped else 1.5
    def model():
        xml, assets = build_multi_robot_scene(Go2Platform(), positions)
        root = ET.fromstring(xml)
        ET.SubElement(root.find("worldbody"), "geom", name="recovery_wall", type="box",
                      pos=f"{wall_distance} 0 .5", size=".025 3 .5", contype="1", conaffinity="1")
        return mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"), assets)
    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a",), spawn_positions=positions,
        spawn_headings={"robot_a": 0.}, launch_viewer=False), model_factory=model)
    try:
        bridge.start()
        contacts = PhysicsContactCollector(_contacts(bridge), start_sim_time=float(bridge.mj_data.time))
        bridge.add_physics_step_observer(contacts.observe_step)
        loop = ExplorationLoop(bridge, MockSLAM(), MockOctoMap(), ExplorationConfig(ground_filter=False))
        grid = room((0, wall_distance))
        monkeypatch.setattr(loop, "planning_grid", lambda *a: grid)
        def observe(sensor):
            loop._last_observation_time = sensor.sim_time
            p = bridge._extract_pose("robot_a")
            return p, p[:3, 3].copy()
        monkeypatch.setattr(loop, "_update_slam", observe)
        def frontiers(*a, **kw):
            # Initially only a frontier across the wall is observed. Retreat
            # exposes a reachable frontier on this side; no obstacles are erased.
            goal = np.array([-2., 0., 0.] if loop._blocked.recovery_outcome == "progress" else [2., 0., 0.])
            return [FrontierCluster(goal, 1, np.array([grid.world_to_grid(goal[:2])]))]
        monkeypatch.setattr(loop.frontier_detector, "detect", frontiers)
        recovery_start = None
        minimum_reverse = 0.
        for i in range(1200):
            sensor = frame(i * bridge.frame_dt)
            sensor.collision_radius_m = bridge._collision_radii["robot_a"]
            linear, angular, metrics = loop.step_once(sensor, i + 30)
            nav = loop.measurement_state["navigation"]
            if trapped:
                assert not linear.any() and angular == 0.
            if nav["state"] == "recovering":
                assert loop.measurement_state["motion_clearance"]["stopping_clear"]
                if recovery_start is None:
                    recovery_start = bridge.get_body_position("robot_a").copy()
            if recovery_start is not None:
                minimum_reverse = min(minimum_reverse, bridge.get_body_position("robot_a")[0] - recovery_start[0])
            bridge.set_velocity("robot_a", linear, angular)
            bridge.step()
            assert bridge.get_body_position("robot_a")[2] > .20
            if metrics.terminated or nav["reason"] == "navigation_progress":
                break
        contacts.finish()
        assert all(count == 0 for kind, count in contacts.summary()["episodes_by_kind"].items()
                   if kind != "foot_floor")
        if trapped:
            assert nav["state"] == "failed" and nav["reason"] == "no_safe_recovery"
            assert recovery_start is None
        else:
            assert minimum_reverse <= -.10
            assert nav["recovery_outcome"] == "progress"
            assert nav["state"] == "navigating" and nav["reason"] == "navigation_progress"
    finally:
        bridge.stop()
