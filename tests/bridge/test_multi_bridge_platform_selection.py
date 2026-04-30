import sys
import types

import numpy as np

import src.bridge.multi_bridge as multi_bridge_module
from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.types import (
    ControllerHealth,
    RobotCommand,
    RobotRuntimeState,
    RobotRuntimeStatus,
    RobotState,
)


def test_bridge_exposes_platform_metadata_without_starting():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    metadata = bridge.platform_metadata

    assert metadata.name == "go2"
    assert metadata.actuator_count == 12


def test_bridge_buffers_generic_robot_command():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_command("robot_a", RobotCommand.velocity([0.4, 0.0], 0.2))

    assert bridge.get_runtime_status("robot_a").last_command.to_wire() == {
        "mode": "velocity",
        "linear": [0.4, 0.0],
        "yaw_rate": 0.2,
        "waypoint": None,
    }


def test_set_velocity_preserves_existing_api():
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2"))

    bridge.set_velocity("robot_a", np.array([0.1, 0.0]), 0.0)

    assert bridge.get_runtime_status("robot_a").last_command.to_wire()["linear"] == [0.1, 0.0]


class _FakeAgibotLikePlatform:
    metadata = types.SimpleNamespace(
        name="fake_agibot",
        model_dir="models/fake_agibot",
        actuator_count=1,
        footprint_radius=0.3,
    )

    def root_body_name(self):
        return "pelvis"

    def actuator_names(self):
        return ["hip"]

    def initial_joint_qpos(self):
        return np.array([0.0])

    def make_controller(self, robot_id):
        return _FakeController()

    def extract_state(self, model, data, qpos_start, sim_time):
        return _fake_state(sim_time)

    def runtime_status(self, robot_id, state, command, health, **kwargs):
        return RobotRuntimeStatus(
            state=RobotRuntimeState.STANDING,
            last_command=command,
            controller_health=health,
            **kwargs,
        )


class _FakeController:
    def __init__(self):
        self.commands = []

    def compute(self, command, state, dt):
        self.commands.append(command)
        return np.array([0.0])

    def health(self):
        return ControllerHealth()


def _fake_state(sim_time=0.0):
    return RobotState(
        base_pose=np.eye(4),
        base_velocity=np.zeros(3),
        joint_positions=np.zeros(1),
        joint_velocities=np.zeros(1),
        orientation_quat=np.array([1.0, 0.0, 0.0, 0.0]),
        contacts=(),
        sim_time=sim_time,
    )


def test_start_discovers_platform_root_body_name(monkeypatch):
    body_lookups = []

    class FakeModel:
        opt = types.SimpleNamespace(timestep=0.002)
        njnt = 1
        jnt_bodyid = np.array([7])
        jnt_type = np.array([0])
        jnt_qposadr = np.array([0])

        @staticmethod
        def from_xml_string(xml_str, assets):
            return FakeModel()

    class FakeData:
        def __init__(self, model):
            self.qpos = np.zeros(8)
            self.ctrl = np.zeros(1)

    class FakeRenderer:
        def __init__(self, model, height, width):
            pass

    def fake_name2id(model, obj_type, name):
        if obj_type == "body":
            body_lookups.append(name)
            return 7 if name == "robot_a_pelvis" else -1
        if obj_type == "actuator" and name == "robot_a_hip":
            return 0
        if obj_type == "camera" and name == "robot_a_cam":
            return 0
        return -1

    fake_mujoco = types.SimpleNamespace(
        MjModel=FakeModel,
        MjData=FakeData,
        Renderer=FakeRenderer,
        mj_name2id=fake_name2id,
        mj_step=lambda model, data: None,
        mjtObj=types.SimpleNamespace(
            mjOBJ_BODY="body",
            mjOBJ_ACTUATOR="actuator",
            mjOBJ_CAMERA="camera",
        ),
    )
    monkeypatch.setitem(sys.modules, "mujoco", fake_mujoco)
    monkeypatch.setattr(
        multi_bridge_module,
        "build_multi_robot_scene",
        lambda platform, spawn_positions: ("<mujoco/>", {}),
    )
    monkeypatch.setattr(
        MultiRobotBridge,
        "_capture_frame",
        lambda self, robot_id: types.SimpleNamespace(robot_id=robot_id),
    )

    bridge = MultiRobotBridge(MultiRobotConfig(robot_ids=("robot_a",), platform="go2", boot_phase_steps=0))
    bridge._platform = _FakeAgibotLikePlatform()
    bridge._controllers = {"robot_a": bridge._platform.make_controller("robot_a")}

    bridge.start()

    assert body_lookups[0] == "robot_a_pelvis"


def test_step_records_stop_as_last_command_when_robot_was_disabled(monkeypatch):
    controller = _FakeController()
    bridge = MultiRobotBridge(MultiRobotConfig(platform="go2", robot_ids=("robot_a",), sim_steps_per_frame=1))
    bridge._platform = _FakeAgibotLikePlatform()
    bridge._controllers = {"robot_a": controller}
    bridge._model = types.SimpleNamespace(opt=types.SimpleNamespace(timestep=0.002))
    bridge._data = types.SimpleNamespace(qpos=np.zeros(3), ctrl=np.zeros(1))
    bridge._dt = 0.02
    bridge._qpos_starts = {"robot_a": 0}
    bridge._ctrl_indices = {"robot_a": [0]}
    bridge._viewer_handle = None
    bridge._commands = {"robot_a": RobotCommand.velocity([0.7, 0.0], 0.2)}
    bridge._runtime_status = {
        "robot_a": RobotRuntimeStatus(
            state=RobotRuntimeState.DISABLED,
            last_command=RobotCommand.velocity([0.7, 0.0], 0.2),
        )
    }

    monkeypatch.setitem(sys.modules, "mujoco", types.SimpleNamespace(mj_step=lambda model, data: None))
    monkeypatch.setattr(
        MultiRobotBridge,
        "_capture_frame",
        lambda self, robot_id: types.SimpleNamespace(robot_id=robot_id),
    )

    bridge.step()

    assert controller.commands[-1].mode == "stop"
    assert bridge.get_runtime_status("robot_a").last_command.mode == "stop"
