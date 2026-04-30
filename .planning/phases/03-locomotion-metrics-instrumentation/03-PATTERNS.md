# Phase 3: locomotion-metrics-instrumentation - Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/locomotion/env.py` | env/controller boundary | request-response + event-driven simulation step | `src/locomotion/env.py` | exact existing integration point |
| `src/locomotion/metrics.py` | metrics collector / utility | batch + transform + MuJoCo contact access | `src/metrics/metrics_tracker.py`, `src/metrics/detection_metrics_tracker.py`, `src/metrics/mujoco_gt.py` | role-match |
| `src/locomotion/actions.py` | utility/config | request-response validation + transform | `src/locomotion/actions.py`, `src/locomotion/controller_dispatch.py` | exact existing validation point |
| `tests/locomotion/test_locomotion_metrics_collector.py` | test | fake-data batch/transform | `tests/metrics/test_metrics_tracker.py`, `tests/metrics/test_detection_metrics_tracker.py` | role-match |
| `tests/locomotion/test_locomotion_metrics_foot_mapping.py` | test | MuJoCo file-I/O/contact integration + fake validation | `tests/metrics/test_mujoco_gt.py` | role-match |
| `tests/locomotion/test_argus_go2_env_metrics.py` | test | fake-data env request-response/integration | `tests/locomotion/test_argus_go2_env_contract.py` | exact role-match |
| `models/unitree_go2/go2.xml` | model fixture/reference | file-I/O MuJoCo contact names | `models/unitree_go2/go2.xml` | exact reference, read-only |

## Pattern Assignments

### `src/locomotion/env.py` (env/controller boundary, request-response + event-driven simulation step)

**Analog:** `src/locomotion/env.py`

**Imports/config pattern** (lines 3-17, 19-29):
```python
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import gymnasium
import numpy as np
from src.locomotion.actions import ACTION_MODE_VELOCITY, build_action_space, decode_action
from src.locomotion.controller_dispatch import command_from_velocity, dispatch_controller
from src.locomotion.controllers import ControllerRegistry
from src.locomotion.gait_controller import TrotGaitController
from src.locomotion.gait_params import GaitParams
from src.locomotion.observations import build_observation_space, extract_observation
from src.locomotion.scenarios import ScenarioSample, build_scenario_xml, sample_scenario

@dataclass
class ArgusGo2EnvConfig:
    scenario_id: str = "flat_ground"
    action_mode: str = "velocity_command"
    controller_id: str = "analytical_trot"
    model_dir: str | None = None
    sim_steps_per_frame: int = 10
    max_episode_steps: int = 500
    render_mode: str | None = None
    heightfield_size: int = 16
```
Copy this local style: dataclass config, absolute `src.*` imports, and config validation in `__init__`. Add `metrics_config: LocomotionMetricsConfig | None = None` or equivalent and validate threshold ranges before use.

**Reset lifecycle pattern** (lines 64-95):
```python
def reset(
    self,
    *,
    seed: int | None = None,
    options: dict[str, Any] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Reset the episode and return an observation plus reproducibility info."""
    super().reset(seed=seed)
    self._seed = seed
    self._last_seed = seed
    self._scenario_sample = sample_scenario(self.config.scenario_id, self.np_random,
                                            heightfield_size=self.config.heightfield_size)
    if self._model is not None and self._data is not None and self._is_real_mujoco_model():
        self._model = None
        self._data = None
        self._dt = 0.002 * self.config.sim_steps_per_frame
    self._step_count = 0
    first_command = self._scenario_sample.command_schedule[0]
    self._command = np.array(
        [first_command["vx"], first_command["vy"], first_command["omega"]],
        dtype=np.float32,
    )
    self._previous_action = np.zeros(12, dtype=np.float32)
    self._active_push = None
    self._controller.reset(seed=seed)
    self._gait = TrotGaitController()

    self._try_initialize_mujoco()
    self._reset_mujoco_state()

    observation = extract_observation(self._data, self._command, self._previous_action)
    return observation, self._info()
```
Metrics integration should reset the episode buffer after scenario/controller reset and MuJoCo state initialization, preserving explicit baseline/reference snapshots per `MetricsTracker.reset()` semantics. Resolve/validate Go2 foot mapping after `_try_initialize_mujoco()` when a real model exists.

**Step dispatch/control/physics pattern** (lines 97-147):
```python
def step(
    self,
    action: np.ndarray,
) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
    """Apply a mode-specific action and return the Gymnasium five-tuple."""
    command = self._command
    if self.config.action_mode != ACTION_MODE_VELOCITY:
        command = self._command_at_time(self._current_sim_time())
    if self.config.action_mode == ACTION_MODE_VELOCITY:
        velocity_action = self._validate_velocity_action(action)
        command_obj = command_from_velocity(
            velocity_action[:2],
            float(velocity_action[2]),
            metadata={"controller_id": self.config.controller_id},
        )
        result = dispatch_controller(
            self._controller,
            extract_observation(self._data, self._command, self._previous_action),
            command_obj,
            self._dt,
            data=self._data,
        )
        ctrl = result.action
        self._command = velocity_action.copy()
    else:
        ctrl = decode_action(
            action,
            self.config.action_mode,
            self._gait,
            self._dt,
            command,
        )
        self._command = command
    self._previous_action = ctrl.astype(np.float32)

    if self._data is not None:
        import mujoco

        if self.config.action_mode != ACTION_MODE_VELOCITY:
            self._data.ctrl[:] = self._previous_action
        self._apply_push_disturbance()
        for _ in range(self.config.sim_steps_per_frame):
            mujoco.mj_step(self._model, self._data)

    self._step_count += 1
    observation = extract_observation(self._data, self._command, self._previous_action)
    reward = 0.0
    terminated = False
    truncated = self._step_count >= self.config.max_episode_steps
    info = self._info()
    return observation, reward, terminated, truncated, info
```
Record locomotion metrics after MuJoCo stepping and before final `info` construction. Replace hardcoded `terminated = False` with collector failure result (`roll`, `pitch`, `base_height`, progress/recovery gates). Keep `truncated` as max-step logic.

**Info payload pattern** (lines 306-323):
```python
def _info(self) -> dict[str, Any]:
    sample = self._scenario_sample
    info = {
        "seed": self._last_seed,
        "scenario_id": sample.scenario_id if sample is not None else self.config.scenario_id,
        "action_mode": self.config.action_mode,
        "controller_id": self.config.controller_id,
        "step_count": self._step_count,
        "sim_time": self._current_sim_time(),
        "spawn_pose": sample.spawn_pose if sample is not None else None,
        "sampled_parameters": dict(sample.terrain_parameters) if sample is not None else {},
        "command_schedule": tuple(dict(item) for item in sample.command_schedule) if sample is not None else (),
        "disturbance_schedule": tuple(dict(item) for item in sample.disturbance_schedule) if sample is not None else (),
        "active_push": dict(self._active_push) if self._active_push is not None else None,
    }
    if self._step_count == 0:
        info["controller_metadata"] = dict(self._controller_metadata)
    return info
```
Add compact nested per-step metrics as `info["locomotion_metrics"] = collector.latest_info_payload()`. Add `info["locomotion_metrics_summary"]` only on termination/truncation or provide a read-only accessor for latest completed summary. Do not scatter top-level metric keys.

---

### `src/locomotion/metrics.py` (metrics collector / utility, batch + transform + MuJoCo contact access)

**Analogs:** `src/metrics/metrics_tracker.py`, `src/metrics/detection_metrics_tracker.py`, `src/metrics/mujoco_gt.py`, `src/locomotion/controllers.py`

**Collector imports/history pattern** from `src/metrics/detection_metrics_tracker.py` (lines 16-21, 47-76):
```python
from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

class DetectionMetricsTracker:
    def __init__(self, history_size: int = 60) -> None:
        self._history_size = history_size
        self._per_robot: dict[str, dict[str, Any]] = {}
        # SC#2 / D-09: isolated from `_per_robot` so `reset_gt()` is surgical.
        self._gt_state: dict[str, dict[str, dict[str, Any]]] = {}

    def _ensure_robot(self, robot_id: str) -> dict:
        if robot_id not in self._per_robot:
            self._per_robot[robot_id] = {
                "inference_ms_p50": 0.0,
                "inference_ms_p95": 0.0,
                "detections_per_frame": 0,
                "mean_confidence": 0.0,
                "queue_depth": 0,
                "freshness_s": 0.0,
                "jitter_m": 0.0,
                "inference_ms_history": deque(maxlen=self._history_size),
                "det_per_frame_history": deque(maxlen=self._history_size),
                "confidence_history": deque(maxlen=self._history_size),
                "freshness_history": deque(maxlen=self._history_size),
                "jitter_history": deque(maxlen=self._history_size),
                "_tracked_centers": {},
            }
        return self._per_robot[robot_id]
```
Use `deque(maxlen=config.history_size)` for step records and family histories. For locomotion, a single-episode collector is probably not per-robot, but the bounded-history and lazy initialization pattern is the local idiom.

**Dataclass/frozen record pattern** from `src/locomotion/controllers.py` (lines 72-88):
```python
@dataclass(frozen=True)
class LocomotionCommand:
    """Typed velocity command consumed by locomotion controllers."""

    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class ControllerResult:
    """Validated controller action plus reproducibility metadata."""

    action: np.ndarray
    metadata: dict[str, Any]
```
Define `LocomotionMetricsConfig`, `Go2FootMapping`, `LocomotionMetricStep`, and `LocomotionEpisodeSummary` as dataclasses. Use frozen dataclasses for immutable records/config if mutation is not required.

**Stats/history payload pattern** from `src/metrics/detection_metrics_tracker.py` (lines 214-268):
```python
def get_stats_payload(self) -> dict:
    """Build the detection-tracker portion of the stats WebSocket message."""
    detection_metrics: dict[str, dict] = {}
    detection_history: dict[str, dict] = {}
    for rid, entry in self._per_robot.items():
        detection_metrics[rid] = {
            "inference_ms_p50": entry["inference_ms_p50"],
            "inference_ms_p95": entry["inference_ms_p95"],
            "detections_per_frame": entry["detections_per_frame"],
            "mean_confidence": entry["mean_confidence"],
            "queue_depth": entry["queue_depth"],
            "freshness_s": entry["freshness_s"],
            "jitter_m": entry["jitter_m"],
        }
        detection_history[rid] = {
            "inference_ms": list(entry["inference_ms_history"]),
            "det_per_frame": list(entry["det_per_frame_history"]),
            "confidence": list(entry["confidence_history"]),
            "freshness": list(entry["freshness_history"]),
            "jitter": list(entry["jitter_history"]),
        }
    return {
        "detection_metrics": detection_metrics,
        "detection_history": detection_history,
        "detection_gt_metrics": detection_gt_metrics,
    }
```
Locomotion payload should use the required families: `command_tracking`, `stability`, `action_quality`, and `contact_terrain`. Convert deques/arrays to lists or scalars before exposing info/summary.

**Baseline-preserving reset pattern** from `src/metrics/metrics_tracker.py` (lines 129-168):
```python
def capture_baseline(self) -> None:
    """Snapshot current per-robot metrics as baseline.

    The baseline is None if no robots have recorded any metrics.
    """
    if not self._per_robot:
        self._baseline = None
        return
    baseline: dict[str, dict] = {}
    for robot_id in self._per_robot:
        baseline[robot_id] = self.get_robot_metrics(robot_id)
    self._baseline = baseline if baseline else None

@property
def baseline(self) -> dict | None:
    """The last captured baseline, or None."""
    return self._baseline

def reset(self) -> None:
    """Clear all per-robot data and frame counts.

    Baseline is intentionally preserved across sessions for comparison.
    """
    self._per_robot.clear()
    self._frame_counts.clear()
```
Implement `reset_episode()` to clear current episode records/history while preserving explicit baseline/reference state. If a full reset exists, keep it separate from episode reset.

**Fail-fast MuJoCo mapping pattern** from `src/metrics/mujoco_gt.py` (lines 54-103):
```python
def __init__(
    self,
    mapping_yaml_path: Path,
    mj_model,  # mujoco.MjModel
    mj_data,   # mujoco.MjData
) -> None:
    self._model = mj_model
    self._data = mj_data

    self._class_to_geom_ids: dict[str, list[int]] = {}
    for class_name, body_names in mapping.items():
        if not isinstance(body_names, list):
            raise ValueError(
                f"GT mapping class '{class_name}' must map to a list of body names "
                f"(CONTEXT D-08); got {type(body_names).__name__}"
            )
        geom_ids: list[int] = []
        for body_name in body_names:
            bid = mujoco.mj_name2id(
                mj_model, mujoco.mjtObj.mjOBJ_BODY, body_name
            )
            if bid < 0:
                raise ValueError(
                    f"GT mapping references unknown body '{body_name}' "
                    f"(class={class_name}); run an `mj_id2name` audit on the "
                    f"scene XML to list valid body names"
                )
            gid = -1
            for g in range(mj_model.ngeom):
                if int(mj_model.geom_bodyid[g]) == bid:
                    gid = g
                    break
            if gid < 0:
                raise ValueError(
                    f"Body '{body_name}' has no geom — GT extraction requires "
                    f"geom_xpos (Research F1). Verify scene XML."
                )
            geom_ids.append(gid)
        self._class_to_geom_ids[class_name] = geom_ids
```
For Go2 feet, resolve explicit geom names `FL`, `FR`, `RL`, `RR` with `mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)`, raise `ValueError` on missing ids or duplicate ids, and do not fall back to substring guessing.

**Geom world-position access pattern** from `src/metrics/mujoco_gt.py` (lines 104-116):
```python
def gt_positions(self, class_name: str) -> list[np.ndarray]:
    """Return list of world-frame (x, y, z) for every GT instance of this class.

    F1: reads `data.geom_xpos`, NOT `data.xpos`.
    """
    geom_ids = self._class_to_geom_ids.get(class_name, [])
    return [
        np.array(self._data.geom_xpos[gid], dtype=np.float64)
        for gid in geom_ids
    ]
```
Use `data.geom_xpos[foot_geom_id]` for clearance/world positions. For contacts, iterate `data.contact[:data.ncon]` and classify if either geom id is a foot id.

---

### `src/locomotion/actions.py` (utility/config, request-response validation + transform)

**Analog:** `src/locomotion/actions.py`, plus `src/locomotion/controller_dispatch.py`

**Action bound constants and public action-space construction pattern** (lines 12-18, 61-82):
```python
ACTION_MODE_VELOCITY = "velocity_command"
ACTION_MODE_JOINT_POSITION = "joint_position"
ACTION_MODE_RESIDUAL_BASELINE = "residual_baseline"

_VELOCITY_LOW = np.array([-1.0, -1.0, -3.0], dtype=np.float32)
_VELOCITY_HIGH = np.array([1.0, 1.0, 3.0], dtype=np.float32)

def available_action_modes() -> list[str]:
    """Return sorted action mode names supported by the benchmark wrapper."""
    return sorted(_ACTION_MODES)


def build_action_space(mode: str) -> spaces.Box:
    """Build the Gymnasium action space for an action mode."""
    if mode == ACTION_MODE_VELOCITY:
        return spaces.Box(low=_VELOCITY_LOW.copy(), high=_VELOCITY_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_JOINT_POSITION:
        return spaces.Box(low=_JOINT_LOW.copy(), high=_JOINT_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_RESIDUAL_BASELINE:
        return spaces.Box(low=_RESIDUAL_LOW.copy(), high=_RESIDUAL_HIGH.copy(), dtype=np.float32)
    raise _unknown_mode_error(mode)
```
Expose a public copied joint-bounds helper (for example `joint_position_bounds() -> tuple[np.ndarray, np.ndarray]`) rather than duplicating private `_JOINT_LOW/_JOINT_HIGH` inside metrics.

**Validation pattern** (lines 125-148):
```python
def _as_finite_vector(action: Sequence[float] | np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    """Convert *action* to a finite float64 vector with an exact shape."""
    vector = np.asarray(action, dtype=np.float64)
    if vector.shape != shape:
        raise ValueError(f"Action must have shape {shape}, got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError("Action values must be finite")
    return vector


def _as_bounded_vector(
    action: Sequence[float] | np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
) -> np.ndarray:
    vector = _as_finite_vector(action, low.shape)
    if np.any(vector < low.astype(np.float64)) or np.any(vector > high.astype(np.float64)):
        raise ValueError("Action values must be within the action space bounds")
    return vector


def _ensure_decoded_control(control: Sequence[float] | np.ndarray) -> np.ndarray:
    """Validate decoded controller output before it can reach physics controls."""
    return _as_finite_vector(control, (12,))
```
Metrics should use the same shape/finite/bounds semantics for commanded target violation and saturation proxy tests. If adding helper APIs, return copies to avoid mutable global arrays leaking.

**Controller-target mutation guard pattern** from `src/locomotion/controller_dispatch.py` (lines 67-94):
```python
def apply_controller_target(
    data: Any,
    target: Sequence[float] | np.ndarray,
    ctrl_indices: Sequence[int] | None = None,
) -> np.ndarray:
    """Validate and apply one Go2 controller target to a control sink.

    With ``ctrl_indices is None``, the full target is written to ``data.ctrl[:]``.
    With indices supplied, exactly twelve actuator indices are required and each
    target element is written to the paired actuator slot. All validation is done
    before the first ``data.ctrl`` mutation.
    """

    validated = validate_controller_target(target)
    if ctrl_indices is not None and len(ctrl_indices) != validated.shape[0]:
        raise ValueError(
            f"ctrl_indices must contain exactly {validated.shape[0]} entries, "
            f"got {len(ctrl_indices)}."
        )

    if ctrl_indices is None:
        data.ctrl[:] = validated
    else:
        indices = [int(idx) for idx in ctrl_indices]
        if len(set(indices)) != len(indices):
            raise ValueError("ctrl_indices must not contain duplicates.")
        ctrl_size = int(data.ctrl.shape[0])
        bad_indices = [idx for idx in indices if idx < 0 or idx >= ctrl_size]
        if bad_indices:
            raise ValueError(f"ctrl_indices out of range for data.ctrl size {ctrl_size}: {bad_indices}")
        for i, act_id in enumerate(indices):
            data.ctrl[act_id] = validated[i]
    return validated
```
When adding bound helpers or metric validation, keep the same rule: validate all shapes/finite/ranges before mutating state or recording benchmark metrics.

---

### `tests/locomotion/test_locomotion_metrics_collector.py` (test, fake-data batch/transform)

**Analogs:** `tests/metrics/test_metrics_tracker.py`, `tests/metrics/test_detection_metrics_tracker.py`

**Plain unit-test structure pattern** from `tests/metrics/test_metrics_tracker.py` (lines 15-43):
```python
class TestMetricsTracker:
    def test_record_frame_stores_ms_and_status(self):
        """Test 1: record_frame stores ms_per_frame and tracking_status."""
        tracker = MetricsTracker()
        tracker.record_frame("robot_a", {"processing_time_ms": 12.5}, "ok")
        m = tracker.get_robot_metrics("robot_a")
        assert m["ms_per_frame"] == 12.5
        assert m["tracking_status"] == "ok"

    def test_ring_buffer_evicts_oldest(self):
        """Test 3: ring buffer evicts oldest entry when exceeding history_size."""
        tracker = MetricsTracker(history_size=3)
        tracker.record_frame("robot_a", {}, "ok")
        for i in range(5):
            tracker.record_drift("robot_a", float(i), float(i), float(i), float(i))
        histories = tracker.get_histories()
        assert len(histories["robot_a"]["ate_rmse"]) == 3
        assert histories["robot_a"]["ate_rmse"][0] == 2.0
        assert histories["robot_a"]["ate_rmse"][-1] == 4.0
```
Use focused tests for command tracking, stability failure, action delta/jerk, effort proxy, joint-limit counts, bounded history eviction, and episode summary fields.

**Duck-typed fake-data pattern** from `tests/metrics/test_detection_metrics_tracker.py` (lines 17-51):
```python
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import pytest

from src.metrics.detection_metrics_tracker import DetectionMetricsTracker

@dataclass
class FakeOBB:
    center: np.ndarray
    score: float
    class_name: str


@dataclass
class FakeDetections3D:
    items: list
    capture_timestamp: float = 0.0


def _make_det(centers: list[tuple[float, float, float]], classes: list[str], scores: list[float],
              capture_timestamp: float = 0.0) -> FakeDetections3D:
    items = [
        FakeOBB(center=np.asarray(c, dtype=np.float64), score=s, class_name=cn)
        for c, cn, s in zip(centers, classes, scores)
    ]
    return FakeDetections3D(items=items, capture_timestamp=capture_timestamp)
```
Use local dataclass fakes for metric inputs instead of pulling in full MuJoCo/Gym env. Keep collector unit tests decoupled.

**Payload shape and finite-value assertions** from `tests/metrics/test_detection_metrics_tracker.py` (lines 104-134, 190-213):
```python
def test_empty_state_no_nan():
    tracker = DetectionMetricsTracker(history_size=60)

    payload = tracker.get_stats_payload()
    assert payload == {
        "detection_metrics": {},
        "detection_history": {},
        "detection_gt_metrics": {},
    }

    tracker.record_frame(
        robot_id="robot_0",
        sim_now=0.0,
        latest=None,
        inspect={},
        backend_metrics={},
    )
    payload = tracker.get_stats_payload()
    live = payload["detection_metrics"]["robot_0"]
    for k, v in live.items():
        assert math.isfinite(v), f"{k} is not finite: {v}"
        assert not (isinstance(v, float) and math.isnan(v)), f"{k} is NaN"
```
Assert exact family keys for `locomotion_metrics`: `command_tracking`, `stability`, `action_quality`, `contact_terrain`; reject NaN payloads.

**Reset-scope semantics pattern** from `tests/metrics/test_detection_metrics_tracker.py` (lines 243-275):
```python
def test_reset_gt_clears_only_gt_state():
    tracker = DetectionMetricsTracker(history_size=60)
    # Populate both live and GT state.
    for i in range(3):
        tracker.record_frame(
            robot_id="robot_0",
            sim_now=float(i) * 0.1,
            latest=det,
            inspect=inspect,
            backend_metrics=backend,
        )
    tracker.record_gt_match("robot_0", "chair", 0.05, True)
    tracker.record_gt_match("robot_0", "chair", 0.15, True)

    payload_before = tracker.get_stats_payload()
    live_before = dict(payload_before["detection_metrics"]["robot_0"])
    hist_before = {k: list(v) for k, v in payload_before["detection_history"]["robot_0"].items()}

    tracker.reset_gt()

    payload_after = tracker.get_stats_payload()
    assert payload_after["detection_gt_metrics"] == {}
    assert payload_after["detection_metrics"]["robot_0"] == live_before
    for k, v in hist_before.items():
        assert list(payload_after["detection_history"]["robot_0"][k]) == v
```
Add a locomotion equivalent: `reset_episode()` clears step records/current episode but preserves captured baseline/reference snapshot.

---

### `tests/locomotion/test_locomotion_metrics_foot_mapping.py` (test, MuJoCo file-I/O/contact integration + fake validation)

**Analog:** `tests/metrics/test_mujoco_gt.py`

**MuJoCo fixture/forward pattern** (lines 16-42):
```python
from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

from src.metrics.mujoco_gt import MuJoCoGTExtractor

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "perception" / "fixtures"
FIXTURE_XML = _FIXTURE_DIR / "scene_rotated_chair.xml"
FIXTURE_MAPPING = _FIXTURE_DIR / "scene_rotated_chair_gt.yaml"

@pytest.fixture
def mj_pair():
    """Load fixture and run mj_forward so geom_xpos is populated (Research A2)."""
    model = mujoco.MjModel.from_xml_path(str(FIXTURE_XML))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data
```
For Go2, point fixture to `models/unitree_go2/go2.xml` or load through the env scenario builder if scene patching matters. Run `mujoco.mj_forward(model, data)` before checking `geom_xpos`.

**Named-resolution and fail-fast pattern** (lines 45-75):
```python
def test_resolves_chair_body(mj_pair, extractor):
    """mj_name2id finds the chair body; `all_classes` lists "chair"."""
    model, _ = mj_pair
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "chair")
    assert bid >= 0, "fixture chair body must resolve via mj_name2id"
    assert extractor.all_classes() == ["chair"]
    positions = extractor.gt_positions("chair")
    assert len(positions) == 1
    assert positions[0].shape == (3,)


def test_missing_body_raises(mj_pair, tmp_path):
    """Fail-fast at construction when mapping references an unknown body."""
    model, data = mj_pair
    bad_yaml = tmp_path / "bad_mapping.yaml"
    bad_yaml.write_text("chair:\n  - nonexistent_body_xyz\n")
    with pytest.raises(ValueError, match="nonexistent_body_xyz"):
        MuJoCoGTExtractor(bad_yaml, model, data)
```
Implement tests for `FL`, `FR`, `RL`, `RR` resolving to four distinct geom ids, missing required foot name raising, duplicate id/mapping raising, and no heuristic fallback.

**World-position and gate math style** (lines 57-91):
```python
def test_geom_xpos_world_coords(extractor):
    """Research F1: extractor uses geom_xpos, returning z ~= 0.45 (fixture pos)."""
    positions = extractor.gt_positions("chair")
    z = float(positions[0][2])
    assert abs(z - 0.45) < 0.1, f"expected z~=0.45 (body pos), got {z}"


def test_center_error_known_offset(extractor):
    """match_detection returns distance ~= 0.1 inside the 1.0m gate; (None, None) outside."""
    gid, dist = extractor.match_detection("chair", np.array([0.1, 0.0, 0.45]))
    assert gid is not None
    assert dist is not None
    assert abs(dist - 0.1) < 1e-6, f"expected distance ~=0.1, got {dist}"
```
Mirror for foot clearance/slip: controlled fake `geom_xpos`/previous `geom_xpos` should produce known XY velocity and clearance.

---

### `tests/locomotion/test_argus_go2_env_metrics.py` (test, fake-data env request-response/integration)

**Analog:** `tests/locomotion/test_argus_go2_env_contract.py`

**MuJoCo skip pattern** (lines 17-23):
```python
def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
    try:
        import mujoco  # noqa: F401
    except ImportError:
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
```
Use the same helper for integration smoke tests. Run with `/home/prannayag/pragnition/robotics/argus/.venv/bin/python -m pytest` because the global Python is outside project support.

**Fake control/model/data pattern** (lines 26-62):
```python
class _FakeCtrl:
    def __init__(self, size: int = 12) -> None:
        self.values = np.zeros(size, dtype=np.float64)

    @property
    def shape(self) -> tuple[int, ...]:
        return self.values.shape

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value) -> None:
        if key == slice(None, None, None):
            self.values[:] = value
        else:
            self.values[key] = value

    def copy(self) -> np.ndarray:
        return self.values.copy()


class _FakeData:
    def __init__(self) -> None:
        self.qpos = np.zeros(19, dtype=np.float64)
        self.qvel = np.ones(18, dtype=np.float64)
        self.ctrl = _FakeCtrl(12)
        self.xfrc_applied = np.zeros((1, 6), dtype=np.float64)
        self.time = 0.0


class _FakeModel:
    nq = 19
    nv = 18
    nu = 12
    nbody = 1
    opt = SimpleNamespace(timestep=0.002)
```
Extend fake data for metrics with `ncon`, `contact`, `geom_xpos`, and any minimal geom id arrays needed by foot mapping tests. Keep fakes small and duck-typed.

**Step fake/patch pattern** (lines 271-290):
```python
def test_step_decodes_action_writes_ctrl_and_calls_mj_step_configured_count():
    env = ArgusGo2Env(ArgusGo2EnvConfig(action_mode="joint_position", sim_steps_per_frame=3))
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    env._scenario_sample = None
    expected_ctrl = np.linspace(-0.1, 0.1, 12, dtype=np.float64)
    mj_step = MagicMock(side_effect=lambda _model, data: setattr(data, "time", data.time + 0.002))

    with patch("src.locomotion.env.decode_action", return_value=expected_ctrl) as decode_action_mock:
        with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
            obs, _reward, _terminated, _truncated, info = env.step(np.array([0.0] * 12, dtype=np.float32))

    decode_action_mock.assert_called_once()
    np.testing.assert_allclose(fake_data.ctrl.copy(), expected_ctrl)
    assert mj_step.call_count == env.config.sim_steps_per_frame
    assert info["controller_id"] == "analytical_trot"
    assert info["action_mode"] == "joint_position"
    assert info["sim_time"] == pytest.approx(fake_data.time)
```
Add tests that patch collector behavior or use fake MuJoCo state to assert: nested `info["locomotion_metrics"]`, `terminated=True` when threshold fails, terminal/truncated summary present, and no top-level metric sprawl.

**Controller dispatch preservation pattern** (lines 293-331):
```python
def test_velocity_command_step_dispatches_controller_preserving_yaw_rate_and_writes_before_mj_step():
    env = ArgusGo2Env(ArgusGo2EnvConfig(sim_steps_per_frame=2))
    fake_data = _FakeData()
    env._model = _FakeModel()
    env._data = fake_data
    env._scenario_sample = None
    expected_ctrl = np.linspace(0.2, 0.4, 12, dtype=np.float64)
    action = np.array([0.25, -0.1, 0.35], dtype=np.float32)
    calls: list[str] = []

    def dispatch_controller(_controller, observation, command, dt, data=None, ctrl_indices=None):
        assert observation["command"].shape == (3,)
        assert command.vx == pytest.approx(0.25)
        assert command.vy == pytest.approx(-0.1)
        assert command.yaw_rate == pytest.approx(0.35)
        assert dt == pytest.approx(env._dt)
        data.ctrl[:] = expected_ctrl
        calls.append("dispatch")
        return ControllerResult(action=expected_ctrl, metadata={"source": "test"})

    def mj_step(_model, data):
        calls.append("mj_step")
        np.testing.assert_allclose(data.ctrl.copy(), expected_ctrl)
        data.time += 0.002

    with patch("src.locomotion.env.dispatch_controller", side_effect=dispatch_controller):
        with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
            obs, _reward, _terminated, _truncated, info = env.step(action)

    assert calls == ["dispatch", "mj_step", "mj_step"]
```
Metrics tests should assert collector records the validated `expected_ctrl`, not raw velocity command action.

---

### `models/unitree_go2/go2.xml` (model fixture/reference, file-I/O MuJoCo contact names)

**Analog:** `models/unitree_go2/go2.xml`

**Foot/joint names from XML grep**:
```text
80:        <joint name="FL_hip_joint" class="abduction"/>
87:          <joint name="FL_thigh_joint" class="front_hip"/>
94:            <joint name="FL_calf_joint" class="knee"/>
100:            <geom name="FL" class="foot"/>
107:        <joint name="FR_hip_joint" class="abduction"/>
114:          <joint name="FR_thigh_joint" class="front_hip"/>
121:            <joint name="FR_calf_joint" class="knee"/>
127:            <geom name="FR" class="foot"/>
134:        <joint name="RL_hip_joint" class="abduction"/>
141:          <joint name="RL_thigh_joint" class="back_hip"/>
148:            <joint name="RL_calf_joint" class="knee"/>
154:            <geom name="RL" class="foot"/>
161:        <joint name="RR_hip_joint" class="abduction"/>
168:          <joint name="RR_thigh_joint" class="back_hip"/>
175:            <joint name="RR_calf_joint" class="knee"/>
181:            <geom name="RR" class="foot"/>
```
Do not modify this file for Phase 3 unless implementation discovers the existing model is wrong. Use these explicit geom names for strict mapping. Joint order for action metrics should match existing action arrays and tests: `FL_hip`, `FL_thigh`, `FL_calf`, `FR_hip`, `FR_thigh`, `FR_calf`, `RL_hip`, `RL_thigh`, `RL_calf`, `RR_hip`, `RR_thigh`, `RR_calf`.

## Shared Patterns

### Action and Controller Validation
**Source:** `src/locomotion/actions.py` lines 125-148; `src/locomotion/controller_dispatch.py` lines 67-94
**Apply to:** `src/locomotion/metrics.py`, `src/locomotion/env.py`, `src/locomotion/actions.py`, all locomotion tests
```python
vector = np.asarray(action, dtype=np.float64)
if vector.shape != shape:
    raise ValueError(f"Action must have shape {shape}, got {vector.shape}")
if not np.all(np.isfinite(vector)):
    raise ValueError("Action values must be finite")
```
Validate shape and finite values before writing `data.ctrl`, mutating env fields, or recording metric state.

### Collector Reset/History/Baseline Semantics
**Source:** `src/metrics/metrics_tracker.py` lines 129-168; `src/metrics/detection_metrics_tracker.py` lines 47-76, 273-290
**Apply to:** `src/locomotion/metrics.py`, env reset integration, collector tests
```python
def reset(self) -> None:
    """Clear all per-robot data and frame counts.

    Baseline is intentionally preserved across sessions for comparison.
    """
    self._per_robot.clear()
    self._frame_counts.clear()
```
Phase 3 reset should start a fresh episode buffer without clearing explicit baseline/reference snapshots.

### MuJoCo Fail-Fast Name Mapping
**Source:** `src/metrics/mujoco_gt.py` lines 81-103
**Apply to:** `src/locomotion/metrics.py`, foot mapping tests
```python
bid = mujoco.mj_name2id(
    mj_model, mujoco.mjtObj.mjOBJ_BODY, body_name
)
if bid < 0:
    raise ValueError(
        f"GT mapping references unknown body '{body_name}' "
        f"(class={class_name}); run an `mj_id2name` audit on the "
        f"scene XML to list valid body names"
    )
```
Use `mjtObj.mjOBJ_GEOM` for Go2 feet. Missing/duplicate `FL`, `FR`, `RL`, `RR` is an implementation/test failure.

### MuJoCo World-Frame Position Access
**Source:** `src/metrics/mujoco_gt.py` lines 104-116
**Apply to:** foot clearance, slip, contact tests
```python
return [
    np.array(self._data.geom_xpos[gid], dtype=np.float64)
    for gid in geom_ids
]
```
Use `data.geom_xpos` for foot world positions. Do not use body origin as a substitute for foot geom position.

### Gymnasium Reset/Step/Info Surface
**Source:** `src/locomotion/env.py` lines 64-147, 306-323
**Apply to:** env metrics integration and env metrics tests
```python
observation = extract_observation(self._data, self._command, self._previous_action)
reward = 0.0
terminated = False
truncated = self._step_count >= self.config.max_episode_steps
info = self._info()
return observation, reward, terminated, truncated, info
```
Set `terminated=True` for Phase 3 failure thresholds before returning. Add nested `info["locomotion_metrics"]`; add summary at terminal/truncated boundary.

### Pytest Fake MuJoCo Pattern
**Source:** `tests/locomotion/test_argus_go2_env_contract.py` lines 26-62, 271-331
**Apply to:** `tests/locomotion/test_argus_go2_env_metrics.py`
```python
with patch("src.locomotion.env.decode_action", return_value=expected_ctrl) as decode_action_mock:
    with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
        obs, _reward, _terminated, _truncated, info = env.step(np.array([0.0] * 12, dtype=np.float32))
```
Prefer fake data and patched `mujoco.mj_step` for fast env wiring tests; reserve real MuJoCo smoke tests for foot mapping/contact integration.

## No Analog Found

No files are fully without analog. The locomotion-specific metric formulas are new, but every structural pattern has a local analog:

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `src/locomotion/metrics.py` metric formulas | utility/collector | transform | No prior locomotion metric formulas exist, but collector/history/reset and MuJoCo mapping patterns exist. Use RESEARCH.md metric definitions for arithmetic. |

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src/locomotion`, `/home/prannayag/pragnition/robotics/argus/src/metrics`, `/home/prannayag/pragnition/robotics/argus/tests/locomotion`, `/home/prannayag/pragnition/robotics/argus/tests/metrics`, `/home/prannayag/pragnition/robotics/argus/models/unitree_go2/go2.xml`
**Files scanned:** 13 files plus test file listing
**Pattern extraction date:** 2026-04-30
