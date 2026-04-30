# Phase 1: locomotion-env-contract - Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 9 new/modified files
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/locomotion/env.py` | service/API wrapper | request-response + simulation lifecycle | `src/bridge/sim_bridge.py` | role-match |
| `src/locomotion/scenarios.py` | config/catalog + XML utility | transform + deterministic sampling | `src/bridge/scene_builder.py` + `src/slam/registry.py` | role-match |
| `src/locomotion/actions.py` | utility/config | transform | `src/bridge/sim_bridge.py` + `src/locomotion/gait_controller.py` | exact data-flow |
| `src/locomotion/observations.py` | utility | transform | `src/bridge/sim_bridge.py` | data-flow match |
| `src/locomotion/__init__.py` | package export | request-response/import boundary | `src/locomotion/gait_controller.py` imports from package modules | partial |
| `pyproject.toml` | config | dependency/config | `pyproject.toml` | exact existing file |
| `tests/locomotion/test_argus_go2_env_contract.py` | test | request-response contract | `tests/bridge/test_sim_bridge.py` | role-match |
| `tests/locomotion/test_argus_go2_env_scenarios.py` | test | catalog/transform | `tests/slam/test_registry.py` + `tests/locomotion/test_locomotion.py` | role-match |
| `tests/locomotion/test_argus_go2_env_determinism.py` | test | deterministic sampling | `src/control/random_walk.py` + `tests/locomotion/test_gait_controller.py` | data-flow match |
| `tests/locomotion/test_argus_go2_env_action_modes.py` | test | transform + simulation action dispatch | `tests/locomotion/test_gait_controller.py` + `tests/bridge/test_sim_bridge.py` | role-match |

## Pattern Assignments

### `src/locomotion/env.py` (service/API wrapper, request-response + simulation lifecycle)

**Analog:** `src/bridge/sim_bridge.py`

**Imports pattern** (`src/bridge/sim_bridge.py` lines 10-20):
```python
import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix, IMUReading
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.xml_patcher import patch_actuators_to_position, patch_actuators_to_position_with_floor
```

**Config dataclass pattern** (`src/bridge/env_config.py` lines 7-27):
```python
from dataclasses import dataclass


@dataclass
class MuJoCoEnvConfig:
    """Configuration for the MuJoCo simulation environment.

    Attributes:
        model_path: Path to the MuJoCo XML model file.
        resolution: Render resolution as (width, height).
        camera_name: Camera name for rendering. Use -1 for free camera.
        sim_steps_per_frame: Number of physics steps per sensor frame.
            Higher = more stable physics but slower frame rate.
        target_step_hz: Target sensor frame rate in Hz.
    """

    model_path: str = "models/unitree_go2/scene.xml"
    resolution: tuple[int, int] = (320, 240)
    camera_name: int | str = "front_cam"  # named camera attached to robot base
    sim_steps_per_frame: int = 10  # 10 steps * 0.002s dt = 50Hz physics, 5Hz frames
    target_step_hz: float = 10.0
```

**MuJoCo lifecycle pattern** (`src/bridge/sim_bridge.py` lines 64-132):
```python
def start(self) -> SensorFrame:
    """Load the MuJoCo model and initialize the simulation.

    Returns:
        The first SensorFrame from the environment.
    """
    import mujoco

    model_path = Path(self._config.model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"MuJoCo model not found: {model_path}")

    # Locate go2.xml in the model directory for patching
    model_dir = model_path.parent
    go2_xml_path = model_dir / "go2.xml"

    # Patch actuators to position-controlled servos and add floor/light
    # so the model can be loaded standalone (no scene.xml <include> needed)
    patched_xml = patch_actuators_to_position_with_floor(str(go2_xml_path))

    # Load mesh assets for from_xml_string
    asset_dir = model_dir / "assets"
    assets: dict[str, bytes] = {}
    if asset_dir.exists():
        for f in asset_dir.iterdir():
            if f.is_file():
                assets[f.name] = f.read_bytes()

    self._model = mujoco.MjModel.from_xml_string(patched_xml, assets)
    self._data = mujoco.MjData(self._model)
    self._dt = self._model.opt.timestep * self._config.sim_steps_per_frame

    # Look up IMU sensor addresses (will be -1 if sensors not in XML)
    accel_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_SENSOR, "accelerometer")
    gyro_id = mujoco.mj_name2id(self._model, mujoco.mjtObj.mjOBJ_SENSOR, "gyro")
    if accel_id >= 0 and gyro_id >= 0:
        self._accel_adr = self._model.sensor_adr[accel_id]
        self._gyro_adr = self._model.sensor_adr[gyro_id]
        self._has_imu = True
        logger.info("IMU sensors found: accel_adr=%d, gyro_adr=%d", self._accel_adr, self._gyro_adr)
    else:
        self._has_imu = False
        self._accel_adr = 0
        self._gyro_adr = 0

    # Set initial standing pose (skip the 7 free-joint qpos: 3 pos + 4 quat)
    if self._model.nq >= 19:  # 7 (freejoint) + 12 (actuators)
        self._data.qpos[7:19] = STANDING_QPOS

    # Settle the robot (let it land on ground)
    standing = self._gait.compute(0.0, 0.0, 0.0, 0.0)
    for _ in range(200):
        self._data.ctrl[:] = standing
        mujoco.mj_step(self._model, self._data)

    # Create offscreen renderer
    w, h = self._config.resolution
    self._renderer = mujoco.Renderer(self._model, height=h, width=w)
```

**Step/action dispatch pattern** (`src/bridge/sim_bridge.py` lines 134-172):
```python
def step(self, action: np.ndarray | None = None) -> SensorFrame:
    """Step the simulation and return a new SensorFrame.

    Args:
        action: Optional 12-element joint position target. If None,
            uses the velocity command from set_velocity().

    Returns:
        SensorFrame with RGB, depth, and ground-truth pose.
    """
    import mujoco

    if self._model is None:
        raise RuntimeError("Bridge not started -- call start() first")

    if action is not None:
        self._data.ctrl[:] = action
    else:
        # Convert velocity command to joint targets for a simple walk
        ctrl = self._velocity_to_ctrl()
        self._data.ctrl[:] = ctrl

    # Step physics multiple times per frame, collecting IMU at each sub-step
    imu_readings: list[IMUReading] = []
    sim_time_base = self._step_count * self._dt

    for i in range(self._config.sim_steps_per_frame):
        mujoco.mj_step(self._model, self._data)

        if self._has_imu:
            accel = self._data.sensordata[self._accel_adr:self._accel_adr + 3].copy()
            gyro = self._data.sensordata[self._gyro_adr:self._gyro_adr + 3].copy()
            t = sim_time_base + (i + 1) * self._model.opt.timestep
            imu_readings.append(IMUReading(accel=accel, gyro=gyro, timestamp=t))

    self._step_count += 1
    frame = self._capture_frame()
    frame.imu_readings = imu_readings
    return frame
```

**Error handling / lifecycle guard** (`src/bridge/sim_bridge.py` lines 72-74, 146-147, 174-181):
```python
if not model_path.exists():
    raise FileNotFoundError(f"MuJoCo model not found: {model_path}")

if self._model is None:
    raise RuntimeError("Bridge not started -- call start() first")

def stop(self) -> None:
    """Clean up MuJoCo resources."""
    if self._renderer is not None:
        self._renderer.close()
        self._renderer = None
    self._model = None
    self._data = None
    self._step_count = 0
```

**Apply to new env:** Keep `ArgusGo2Env` as a thin separate boundary. Copy the import locality (`import mujoco` inside methods), `Any` for MuJoCo handles, explicit model file guard, model/data lifecycle, and direct `TrotGaitController` use. Add Gymnasium-specific `Env`, `spaces`, `reset(seed, options)`, and five-value `step` return around this pattern.

---

### `src/locomotion/scenarios.py` (config/catalog + XML utility, transform + deterministic sampling)

**Analogs:** `src/bridge/scene_builder.py`, `src/slam/registry.py`, `src/locomotion/xml_patcher.py`, `src/control/random_walk.py`

**XML transform imports and helpers** (`src/bridge/scene_builder.py` lines 17-23 and 35-44):
```python
import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.locomotion.xml_patcher import patch_actuators_to_position


def _prefix_element(elem: ET.Element, prefix: str) -> None:
    """Recursively prefix name-bearing attributes on elem and children."""
    for attr in list(elem.attrib.keys()):
        if attr in _NAME_ATTRS:
            elem.attrib[attr] = prefix + elem.attrib[attr]
        # Handle mesh references in geom elements -- do NOT prefix mesh names
        # as they reference shared assets
    for child in elem:
        _prefix_element(child, prefix)
```

**Scene-building pattern** (`src/bridge/scene_builder.py` lines 46-66 and 129-166):
```python
def build_two_robot_scene(
    model_dir: str,
    spawn_positions: dict[str, tuple[float, float, float]],
) -> str:
    """Build a MuJoCo XML scene containing N Go2 robots.

    Reads go2.xml from model_dir, duplicates the robot body and actuators
    with per-robot prefixes, and inserts them into a scene with floor
    and lighting.
    """
    model_path = Path(model_dir)
    # Patch actuators to position-controlled servos before building scene
    patched_xml = patch_actuators_to_position(str(model_path / "go2.xml"))
    go2_root = ET.fromstring(patched_xml)
```

```python
# Worldbody: floor + light + N robot bodies
wb = ET.SubElement(scene, "worldbody")
ET.SubElement(wb, "light", pos="0 0 3", dir="0 0 -1", directional="true")
ET.SubElement(wb, "geom", name="floor", size="100 100 0.05", type="plane",
              material="groundplane")
# Boundary walls with textures for ORB feature extraction
ET.SubElement(wb, "geom", name="wall_north", type="box",
              size="10 0.1 2", pos="0 10 1", material="wall_checker")
ET.SubElement(wb, "geom", name="wall_south", type="box",
              size="10 0.1 2", pos="0 -10 1", material="wall_gradient")
ET.SubElement(wb, "geom", name="wall_east", type="box",
              size="0.1 10 2", pos="10 0 1", material="wall_checker")
ET.SubElement(wb, "geom", name="wall_west", type="box",
              size="0.1 10 2", pos="-10 0 1", material="wall_gradient")

# Create N robot bodies from spawn_positions
for robot_id, (sx, sy, sz) in spawn_positions.items():
    prefix = f"{robot_id}_"
    body = copy.deepcopy(robot_body)
    _prefix_element(body, prefix)
    body.attrib["pos"] = f"{sx} {sy} {sz}"
    ET.SubElement(body, "camera", name=f"{robot_id}_cam",
                  pos="0.4 0 0.05", xyaxes="0 -1 0 0 0 1", fovy="70")
    wb.append(body)

# Actuators: duplicate with prefixes for each robot
act_section = ET.SubElement(scene, "actuator")
for robot_id in spawn_positions:
    prefix = f"{robot_id}_"
    for motor in actuator_elem:
        new_motor = copy.deepcopy(motor)
        for attr in ("name", "joint", "tendon", "site"):
            if attr in new_motor.attrib:
                new_motor.attrib[attr] = prefix + new_motor.attrib[attr]
        # Do NOT prefix "class" on actuators -- they reference shared defaults
        act_section.append(new_motor)

return ET.tostring(scene, encoding="unicode")
```

**Named catalog/registry error pattern** (`src/slam/registry.py` lines 15-29 and 57-86):
```python
class SLAMRegistry:
    """Central registry for SLAM backend discovery and instantiation.

    Backends are stored by name as class path strings and lazily loaded
    on demand. The default backend is 'icp'.
    """

    _backends: dict[str, dict] = {}
    _default: str = "icp"

    @classmethod
    def register(cls, name: str, display: str, class_path: str) -> None:
        """Register a backend by name and importable class path."""
        cls._backends[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered SLAM backend: %s (%s)", name, class_path)
```

```python
@classmethod
def create(cls, name: str | None = None, **kwargs: Any) -> Any:
    """Create a backend instance by name.

    Raises:
        ValueError: If backend name is not registered.
        ImportError: If backend class cannot be loaded.
    """
    if name is None:
        name = cls._default

    if name not in cls._backends:
        raise ValueError(
            f"Unknown SLAM backend '{name}'. "
            f"Available: {list(cls._backends.keys())}"
        )

    info = cls._backends[name]
    klass = cls._load_class(info["class_path"])
    if klass is None:
        raise ImportError(f"Cannot load backend class: {info['class_path']}")

    return klass(**kwargs)
```

**Deterministic RNG pattern** (`src/control/random_walk.py` lines 31-50 and 71-102):
```python
def __init__(
    self,
    linear_speed: float = 0.3,
    angular_speed: float = 0.8,
    direction_change_interval: float = 3.0,
    seed: int | None = None,
) -> None:
    """Initialize the random walk controller."""
    self._linear_speed = linear_speed
    self._angular_speed = angular_speed
    self._direction_change_interval = direction_change_interval
    self._rng = np.random.default_rng(seed)
```

```python
def _sample_new_direction(self) -> None:
    """Randomly sample new velocity, biased toward forward motion."""
    if self._rng.random() < 0.8:
        vx = self._rng.uniform(0.1, 1.0) * self._linear_speed
    else:
        vx = self._rng.uniform(-0.5, 0.0) * self._linear_speed

    vy = self._rng.uniform(-0.3, 0.3) * self._linear_speed
    angular = self._rng.uniform(-1.0, 1.0) * self._angular_speed

    self._current_linear = np.array([vx, vy])
    self._current_angular = angular

def reset(self, seed: int | None = None) -> None:
    """Reset the controller state, optionally with a new seed."""
    if seed is not None:
        self._rng = np.random.default_rng(seed)
    self._last_change_time = -self._direction_change_interval
    self._current_linear = np.zeros(2)
    self._current_angular = 0.0
```

**Apply to new scenarios:** Use a central catalog with `flat_ground`, `low_friction`, `slope`, `rough_heightfield`, and `push_disturbance`. Keep scenario selection in one module, raise `ValueError` with available names for unknown scenarios, return deterministic sampled parameters/schedules, and mutate MJCF through `ElementTree` without modifying source XML on disk.

---

### `src/locomotion/actions.py` (utility/config, transform)

**Analogs:** `src/locomotion/gait_controller.py`, `src/bridge/sim_bridge.py`, `src/locomotion/gait_params.py`

**Frozen config/dataclass style for immutable parameters** (`src/locomotion/gait_params.py` lines 4-17):
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class GaitParams:
    """Tunable parameters for TrotGaitController.

    Default values are derived from the Go2 mujoco_menagerie keyframe
    and community controller experience. The standing pose uses the
    keyframe joint angles (0, 0.9, -1.8) rather than the older
    code values (0, 0.8, -1.5).
    """

    frequency: float = 3.0
```

**Input validation/clipping pattern** (`src/locomotion/gait_controller.py` lines 39-86):
```python
def compute(
    self, vx: float, vy: float, omega: float, dt: float,
) -> np.ndarray:
    """Compute 12 joint position targets for one timestep.

    Args:
        vx: Forward velocity command (m/s, positive = forward).
        vy: Lateral velocity command (m/s, positive = left).
        omega: Yaw rate command (rad/s, positive = turn left).
        dt: Time since last call (seconds).

    Returns:
        (12,) array of joint position targets in actuator order.
    """
    p = self._params

    # Input validation: clamp to safe ranges
    dt = float(np.clip(dt, 0.001, 1.0))
    vx = float(np.clip(vx, -p.max_speed, p.max_speed))
    vy = float(np.clip(vy, -p.max_speed, p.max_speed))
    omega = float(np.clip(omega, -3.0, 3.0))

    # Clamp speed
    speed = min(float(np.sqrt(vx ** 2 + vy ** 2)), p.max_speed)
```

**Velocity-to-control dispatch pattern** (`src/bridge/sim_bridge.py` lines 187-207):
```python
def set_velocity(self, linear: np.ndarray, angular: float) -> None:
    """Buffer a velocity command for the next step.

    Args:
        linear: np.ndarray of shape (2,) representing [vx, vy].
        angular: Angular velocity (positive = turn left).
    """
    self._linear_vel = np.asarray(linear, dtype=np.float64)
    self._angular_vel = float(angular)

def _velocity_to_ctrl(self) -> np.ndarray:
    """Convert buffered velocity to joint position targets.

    Uses TrotGaitController for proper trot gait with position-controlled
    actuators, producing actual locomotion via diagonal pair alternation
    and differential stride turning.
    """
    dt = self._dt  # self._dt already includes sim_steps_per_frame
    vx = float(self._linear_vel[0]) if len(self._linear_vel) > 0 else 0.0
    vy = float(self._linear_vel[1]) if len(self._linear_vel) > 1 else 0.0
    return self._gait.compute(vx, vy, self._angular_vel, dt)
```

**Apply to actions:** Define action-mode constants/specs in one place. Decode `velocity_command` into `(vx, vy, omega)` and call `TrotGaitController.compute`; validate `joint_position` as finite 12-vector before writing `data.ctrl`; decode `residual_baseline` by computing the baseline and adding clipped finite residuals. Match `action_space` shape to mode at `ArgusGo2Env.__init__` time.

---

### `src/locomotion/observations.py` (utility, transform)

**Analog:** `src/bridge/sim_bridge.py`

**Observation extraction pattern** (`src/bridge/sim_bridge.py` lines 213-256):
```python
def _capture_frame(self) -> SensorFrame:
    """Render RGB + depth and extract ground-truth pose."""
    import mujoco

    self._renderer.update_scene(self._data, camera=self._config.camera_name)

    # RGB
    rgb = self._renderer.render().copy()  # (H, W, 3) uint8

    # Depth (metric, in meters)
    self._renderer.enable_depth_rendering()
    depth_raw = self._renderer.render().copy()  # (H, W) float32
    self._renderer.disable_depth_rendering()

    # MuJoCo depth: convert based on value range
    extent = self._model.stat.extent
    znear = self._model.vis.map.znear * extent
    zfar = self._model.vis.map.zfar * extent

    if depth_raw.max() <= 1.0 + 1e-6:
        depth = znear * zfar / (zfar - depth_raw * (zfar - znear))
        depth[depth_raw >= 0.999] = 0.0
    else:
        depth = depth_raw.copy()
        depth[depth_raw >= zfar * 0.99] = 0.0

    depth = np.clip(depth, 0, 20.0).astype(np.float32)

    # Ground-truth pose from camera transform (not body qpos).
    # Depth is rendered from the camera, so the pose must match the
    # camera's position and orientation -- not the robot body's.
    # cam_xmat is R_world_from_cam (columns = camera axes in world).
    pose = np.eye(4, dtype=np.float64)
    pose[:3, 3] = self._data.cam_xpos[self._cam_id]
    pose[:3, :3] = self._data.cam_xmat[self._cam_id].reshape(3, 3)

    sim_time = self._step_count * self._dt

    return SensorFrame(
        rgb=rgb,
        depth=depth,
        ground_truth_pose=pose,
        sim_time=sim_time,
    )
```

**Base pose extraction pattern** (`src/bridge/sim_bridge.py` lines 258-272):
```python
def _extract_pose(self) -> np.ndarray:
    """Extract 4x4 homogeneous transform from the robot's freejoint."""
    pose = np.eye(4, dtype=np.float64)

    if self._data is None:
        return pose

    # Position: first 3 elements of qpos (freejoint)
    pose[:3, 3] = self._data.qpos[:3]

    # Orientation: quaternion in qpos[3:7] (w, x, y, z in MuJoCo convention)
    quat = self._data.qpos[3:7]
    pose[:3, :3] = quat_to_rotation_matrix(quat)

    return pose
```

**Apply to observations:** Prefer state-only proprioceptive observations for Phase 1 tests: copy arrays out of MuJoCo state, preserve dtype expectations (`np.float32`/`np.float64` deliberately), and avoid renderer dependency in contract tests unless required.

---

### `src/locomotion/__init__.py` (package export, import boundary)

**Analog:** existing locomotion imports from sibling modules

**Import style** (`src/locomotion/gait_controller.py` lines 14-17):
```python
import numpy as np

from src.locomotion.gait_params import GaitParams
```

**Apply to package export:** Keep package imports explicit and absolute (`from src.locomotion.env import ArgusGo2Env`). Avoid side effects: do not build MuJoCo models or import heavy optional packages at package import time if avoidable.

---

### `pyproject.toml` (config, dependency/config)

**Analog:** `pyproject.toml`

**Core dependency block** (`pyproject.toml` lines 1-16):
```toml
[project]
name = "argus"
version = "1.0.0"
description = "Multi-robot, multi-camera perception pipeline manager for MuJoCo environments"
requires-python = ">=3.10,<3.13"
dependencies = [
    "mujoco>=3.0.0",
    "open3d>=0.18.0",
    "rerun-sdk>=0.30.0",
    "evo>=1.0.0",
    "numpy>=1.26.0",
    "scipy>=1.15.0",
    "opencv-python-headless>=4.0.0",
    "pyzmq>=26.0",
    "msgpack>=1.0",
]
```

**Optional/dev dependency block** (`pyproject.toml` lines 28-44):
```toml
[project.optional-dependencies]
perception = [
    "torch>=2.10.0",
    "transformers>=5.3.0",
    "ultralytics>=8.4.24",
    "scikit-learn>=1.4.0",
    "onnx>=1.17.0",
    "onnxruntime>=1.19.0",
    "PyYAML>=6.0",
]
teleop = ["pynput>=1.7.6"]
web = ["fastapi>=0.100.0", "uvicorn>=0.20.0", "websockets>=12.0"]
dev = [
    "pytest>=8.0.0",
    "pytest-timeout>=2.0.0",
    "pytest-asyncio>=0.23.0",
]
```

**Apply to dependency change:** Add `gymnasium>=1.3.0` to the main dependencies if `ArgusGo2Env` subclasses `gymnasium.Env`. Keep Python bound unchanged unless separately approved; current shell Python 3.14 is outside project support.

---

### `tests/locomotion/test_argus_go2_env_contract.py` (test, request-response contract)

**Analog:** `tests/bridge/test_sim_bridge.py`

**Unit/integration split and imports** (`tests/bridge/test_sim_bridge.py` lines 1-15):
```python
"""Tests for MuJoCo bridge (SIM-01 through SIM-04).

Integration tests require MuJoCo and the Go2 model. Unit-level tests
use mocks and can run anywhere.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame
from src.bridge.sim_bridge import MuJoCoBridge
```

**Basic contract/unit assertions** (`tests/bridge/test_sim_bridge.py` lines 21-44):
```python
class TestMuJoCoBridgeUnit:
    """Unit tests using mocked MuJoCo."""

    def test_import(self):
        """MuJoCoBridge can be imported."""
        assert MuJoCoBridge is not None

    def test_init_default_config(self):
        """Bridge initialises with default MuJoCoEnvConfig."""
        bridge = MuJoCoBridge()
        assert not bridge.is_running
        assert bridge.step_count == 0

    def test_init_custom_config(self):
        """Bridge accepts a custom config."""
        config = MuJoCoEnvConfig(model_path="custom/path.xml", target_step_hz=5.0)
        bridge = MuJoCoBridge(config)
        assert not bridge.is_running

    def test_step_without_start_raises(self):
        """Calling step() before start() raises RuntimeError."""
        bridge = MuJoCoBridge()
        with pytest.raises(RuntimeError, match="not started"):
            bridge.step()
```

**Integration fixture cleanup** (`tests/bridge/test_sim_bridge.py` lines 72-80):
```python
@pytest.fixture
def bridge():
    """Create and yield a MuJoCo bridge, ensuring cleanup."""
    config = MuJoCoEnvConfig()
    b = MuJoCoBridge(config)
    yield b
    if b.is_running:
        b.stop()
```

**Apply to env contract tests:** Add import/default config tests, `reset(seed=...)` shape/tuple tests, `step(action)` five-tuple tests, `action_space.contains(action)` smoke checks, and cleanup fixture closing env/renderer. Mark MuJoCo-loading tests as `@pytest.mark.integration`.

---

### `tests/locomotion/test_argus_go2_env_scenarios.py` (test, catalog/transform)

**Analogs:** `tests/slam/test_registry.py`, `tests/locomotion/test_locomotion.py`

**Registry/catalog test pattern** (`tests/slam/test_registry.py` lines 11-18 and 48-58):
```python
@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before and after each test."""
    SLAMRegistry._clear()
    yield
    SLAMRegistry._clear()
```

```python
def test_register_and_list():
    """Register a mock backend, verify it appears in list_backends()."""
    SLAMRegistry.register(
        "test", "Test Backend",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    backends = SLAMRegistry.list_backends()
    assert len(backends) == 1
    assert backends[0]["name"] == "test"
    assert backends[0]["display"] == "Test Backend"
    assert backends[0]["available"] is True
```

**Unknown name error test** (`tests/slam/test_registry.py` lines 82-85):
```python
def test_create_unknown_raises():
    """create('nonexistent') raises ValueError."""
    with pytest.raises(ValueError, match="nonexistent"):
        SLAMRegistry.create("nonexistent")
```

**XML patch tests** (`tests/locomotion/test_locomotion.py` lines 21-41 and 85-99):
```python
class TestPatchActuators:
    """patch_actuators_to_position converts motor -> position with PD gains."""

    def test_patch_actuators_converts_motors(self):
        """All 12 actuators should have tag 'position' instead of 'motor'."""
        import xml.etree.ElementTree as ET

        from src.locomotion.xml_patcher import patch_actuators_to_position

        xml_str = patch_actuators_to_position(GO2_XML)
        root = ET.fromstring(xml_str)
        actuator_elem = root.find("actuator")
        assert actuator_elem is not None

        children = list(actuator_elem)
        assert len(children) == 12
        for child in children:
            assert child.tag == "position", (
                f"Expected tag 'position', got '{child.tag}' for {child.get('name')}"
            )
```

```python
def test_original_xml_not_modified(self):
    """The original go2.xml on disk must NOT be modified."""
    import xml.etree.ElementTree as ET

    # Read original content hash before
    original = Path(GO2_XML).read_text()

    from src.locomotion.xml_patcher import patch_actuators_to_position

    _ = patch_actuators_to_position(GO2_XML)

    # File must be unchanged
    after = Path(GO2_XML).read_text()
    assert original == after, "go2.xml was modified on disk!"
```

**Apply to scenario tests:** Verify all required names list/select, unknown scenario raises with available choices, scenario XML mutations parse with `ElementTree`, low friction changes floor friction, slope/heightfield are present when selected, source Go2 XML remains unchanged, and push scenario exposes a deterministic disturbance schedule.

---

### `tests/locomotion/test_argus_go2_env_determinism.py` (test, deterministic sampling)

**Analogs:** `src/control/random_walk.py`, `tests/locomotion/test_gait_controller.py`

**Seeded reset source pattern** (`src/control/random_walk.py` lines 96-102):
```python
def reset(self, seed: int | None = None) -> None:
    """Reset the controller state, optionally with a new seed."""
    if seed is not None:
        self._rng = np.random.default_rng(seed)
    self._last_change_time = -self._direction_change_interval
    self._current_linear = np.zeros(2)
    self._current_angular = 0.0
```

**Many-step deterministic assertion style** (`tests/locomotion/test_gait_controller.py` lines 33-38 and 155-163):
```python
def test_returns_12_elements_after_many_steps(self):
    """Shape is consistent across many timesteps."""
    ctrl = TrotGaitController()
    for _ in range(100):
        result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.02)
    assert result.shape == (12,)
```

```python
def test_phase_accumulates_proportionally_to_dt(self):
    """Phase increment is proportional to frequency * dt."""
    params = GaitParams(frequency=3.0)
    ctrl = TrotGaitController(params)

    ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.1)
    expected_phase = (3.0 * 0.1) % 1.0
    np.testing.assert_allclose(ctrl._phase, expected_phase, atol=1e-9)
```

**Apply to determinism tests:** Call `reset(seed=123)` twice and compare spawn pose, sampled terrain params, command schedule, disturbance schedule, and initial observation with `np.testing.assert_allclose`. Use a different seed and assert at least one randomized field changes for rough/push scenarios. Avoid global `random` and direct `np.random` sampling in implementation.

---

### `tests/locomotion/test_argus_go2_env_action_modes.py` (test, transform + simulation action dispatch)

**Analogs:** `tests/locomotion/test_gait_controller.py`, `tests/bridge/test_sim_bridge.py`, `tests/locomotion/test_locomotion.py`

**Action output shape and finite validation** (`tests/locomotion/test_gait_controller.py` lines 18-31 and 85-98):
```python
def test_returns_12_element_array(self):
    """compute returns a numpy array of shape (12,)."""
    ctrl = TrotGaitController()
    result = ctrl.compute(vx=0.3, vy=0.0, omega=0.0, dt=0.02)

    assert isinstance(result, np.ndarray)
    assert result.shape == (12,)

def test_returns_12_elements_with_all_inputs_nonzero(self):
    """compute returns (12,) even with lateral and angular inputs."""
    ctrl = TrotGaitController()
    result = ctrl.compute(vx=0.5, vy=0.2, omega=0.8, dt=0.02)

    assert result.shape == (12,)
```

```python
def test_dt_zero_gets_clamped_to_minimum(self):
    """dt=0 is clamped to 0.001, avoiding division issues."""
    ctrl = TrotGaitController()
    # Should not raise
    result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=0.0)
    assert result.shape == (12,)
    assert np.all(np.isfinite(result))

def test_negative_dt_gets_clamped(self):
    """Negative dt is clamped to 0.001."""
    ctrl = TrotGaitController()
    result = ctrl.compute(vx=0.5, vy=0.0, omega=0.0, dt=-1.0)
    assert result.shape == (12,)
    assert np.all(np.isfinite(result))
```

**Direct action path unit/integration pattern** (`src/bridge/sim_bridge.py` lines 149-154):
```python
if action is not None:
    self._data.ctrl[:] = action
else:
    # Convert velocity command to joint targets for a simple walk
    ctrl = self._velocity_to_ctrl()
    self._data.ctrl[:] = ctrl
```

**Joint-limit assertion pattern** (`tests/locomotion/test_locomotion.py` lines 224-241):
```python
assert result.shape == (12,)

# Go2 joint limits (from go2.xml defaults)
hip_limits = (-1.0472, 1.0472)
thigh_limits = (-1.5708, 4.5379)  # union of front_hip and back_hip
knee_limits = (-2.7227, -0.83776)

for leg in range(4):
    base = leg * 3
    assert hip_limits[0] <= result[base] <= hip_limits[1], (
        f"Leg {leg} hip {result[base]} out of range"
    )
    assert thigh_limits[0] <= result[base + 1] <= thigh_limits[1], (
        f"Leg {leg} thigh {result[base + 1]} out of range"
    )
    assert knee_limits[0] <= result[base + 2] <= knee_limits[1], (
        f"Leg {leg} calf {result[base + 2]} out of range"
    )
```

**Apply to action-mode tests:** For each configured mode, assert `env.action_space.shape` matches expected mode, sampled actions are accepted, decoded controls are finite 12-element arrays, direct joint targets pass through to `data.ctrl`, velocity mode uses `TrotGaitController`, and residual mode clips/combines baseline plus residual without exceeding configured bounds.

## Shared Patterns

### Absolute imports from `src.*`

**Source:** `src/bridge/sim_bridge.py` lines 16-20 and `tests/bridge/test_sim_bridge.py` lines 12-14

**Apply to:** all new modules and tests

```python
from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame, STANDING_QPOS, quat_to_rotation_matrix, IMUReading
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.xml_patcher import patch_actuators_to_position, patch_actuators_to_position_with_floor
```

```python
from src.bridge.env_config import MuJoCoEnvConfig
from src.bridge.sensor_types import SensorFrame
from src.bridge.sim_bridge import MuJoCoBridge
```

### Dataclass configuration

**Source:** `src/locomotion/gait_params.py` lines 7-17 and `src/bridge/multi_robot_config.py` lines 8-37

**Apply to:** `ArgusGo2EnvConfig`, `ScenarioSpec`, action specs

```python
from dataclasses import dataclass, field


@dataclass
class MultiRobotConfig:
    """Configuration for a multi-robot MuJoCo scene.

    Attributes:
        robot_ids: Tuple of robot identifier strings.
        spawn_positions: Mapping from robot_id to (x, y, z) world spawn position.
        resolution: Render resolution as (width, height).
        sim_steps_per_frame: Number of MuJoCo physics steps per sensor frame.
        model_dir: Path to the directory containing go2.xml and assets.
        boot_phase_steps: Number of physics steps for initial settling.
        scene: Scene type: "flat" for checkerboard floor, "office" for DimOS office.
    """

    robot_ids: tuple[str, ...] = ("robot_a", "robot_b")
    spawn_positions: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: {
            "robot_a": (0.0, 0.0, 0.3),
            "robot_b": (5.0, 0.0, 0.3),
        }
    )
```

### MuJoCo XML patching without modifying source files

**Source:** `src/locomotion/xml_patcher.py` lines 23-62 and `tests/locomotion/test_locomotion.py` lines 85-99

**Apply to:** scenario XML construction

```python
def patch_actuators_to_position(xml_path: str) -> str:
    """Convert torque motors to position actuators in Go2 MJCF.

    Parses the XML at *xml_path*, changes every ``<motor>`` element
    inside ``<actuator>`` to ``<position>`` with appropriate ``kp``/``kv``
    gains, and removes the ``ctrlrange`` attribute (position actuators
    use joint limits instead).
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    actuator_elem = root.find("actuator")
    if actuator_elem is None:
        return ET.tostring(root, encoding="unicode")
```

```python
original = Path(GO2_XML).read_text()

from src.locomotion.xml_patcher import patch_actuators_to_position

_ = patch_actuators_to_position(GO2_XML)

after = Path(GO2_XML).read_text()
assert original == after, "go2.xml was modified on disk!"
```

### Lifecycle cleanup for simulation resources

**Source:** `src/bridge/sim_bridge.py` lines 174-181 and `tests/bridge/test_sim_bridge.py` lines 72-80

**Apply to:** `ArgusGo2Env.close()` and env test fixtures

```python
def stop(self) -> None:
    """Clean up MuJoCo resources."""
    if self._renderer is not None:
        self._renderer.close()
        self._renderer = None
    self._model = None
    self._data = None
    self._step_count = 0
```

```python
@pytest.fixture
def bridge():
    """Create and yield a MuJoCo bridge, ensuring cleanup."""
    config = MuJoCoEnvConfig()
    b = MuJoCoBridge(config)
    yield b
    if b.is_running:
        b.stop()
```

### Pytest markers and timeout configuration

**Source:** `pytest.ini` lines 1-17

**Apply to:** new MuJoCo/Gymnasium tests

```ini
[pytest]
testpaths = tests
timeout = 30
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
addopts = -m "not slow_boxer and not network"
filterwarnings =
    ignore::DeprecationWarning:pytest_asyncio
markers =
    integration: tests requiring SimWorld running
    unit: pure unit tests with no external deps
    slow_boxer: tests requiring a real BoxeR subprocess (skipped unless explicitly selected; CI runs nightly)
    network: tests requiring network access to HuggingFace or GitHub (skipped by default)
```

### Integration test gating and cleanup

**Source:** `tests/bridge/test_sim_bridge.py` lines 82-95

**Apply to:** tests that load MuJoCo model or step physics

```python
@pytest.mark.integration
def test_lifecycle(bridge):
    """SIM-01: Bridge starts, steps, and stops correctly."""
    frame = bridge.start()
    assert bridge.is_running
    assert isinstance(frame, SensorFrame)

    frame2 = bridge.step()
    assert isinstance(frame2, SensorFrame)
    assert bridge.step_count == 1

    bridge.stop()
    assert not bridge.is_running
    assert bridge.step_count == 0
```

## No Analog Found

All likely Phase 1 files have usable analogs. Two gaps remain because the codebase has no existing Gymnasium `Env` subclass and no scenario-specific heightfield/slope generator:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/locomotion/env.py` Gymnasium-specific base-class methods | service/API wrapper | request-response | No existing `gymnasium.Env` subclass; use official Gymnasium API from research for `super().reset(seed=seed)`, `observation_space`, `action_space`, and five-value step return. |
| `src/locomotion/scenarios.py` heightfield/slope details | config/XML utility | transform | Existing XML builders cover floor/walls/robots but not heightfields or tilted terrain; use MuJoCo XML reference plus existing `ElementTree` style. |

## Metadata

**Analog search scope:** `src/locomotion`, `src/bridge`, `src/slam`, `src/control`, `tests/locomotion`, `tests/bridge`, `tests/slam`, root config (`pyproject.toml`, `pytest.ini`).
**Files scanned:** 17 directly read plus roadmap/research/requirements/project instructions.
**Strong analogs used:** 10 (`sim_bridge.py`, `scene_builder.py`, `xml_patcher.py`, `gait_controller.py`, `gait_params.py`, `env_config.py`, `multi_robot_config.py`, `random_walk.py`, bridge/locomotion/registry tests, `pyproject.toml`, `pytest.ini`).
**Pattern extraction date:** 2026-04-30
