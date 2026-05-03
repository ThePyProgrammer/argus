# Phase 06: repair-evaluation-runner-semantics - Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/locomotion/env.py` | service / simulation environment | event-driven + request-response | `src/locomotion/env.py` | exact-self |
| `src/locomotion/evaluation.py` | service / artifact runner | batch + file-I/O | `src/locomotion/evaluation.py` | exact-self |
| `src/locomotion/metrics.py` | model / collector | transform | `src/locomotion/metrics.py` | exact-self |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | test | batch + request-response | `tests/locomotion/test_locomotion_evaluation_runner.py` | exact-self |
| `tests/locomotion/test_argus_go2_env_contract.py` | test | event-driven + request-response | `tests/locomotion/test_argus_go2_env_contract.py` | exact-self |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | test | file-I/O + transform | `tests/locomotion/test_locomotion_evaluation_exports.py` | exact-self |
| `tests/locomotion/test_locomotion_baseline_regression.py` | test | batch + transform | `tests/locomotion/test_locomotion_baseline_regression.py` | exact-self |
| `src/locomotion/scenarios.py` | model / scenario catalog | transform | `src/locomotion/scenarios.py` | supporting |

## Pattern Assignments

### `src/locomotion/env.py` (service / simulation environment, event-driven + request-response)

**Analog:** `src/locomotion/env.py`

**Imports pattern** (lines 3-23):
```python
import copy
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
from src.locomotion.metrics import (
    Go2FootMapping,
    LocomotionMetricsCollector,
    LocomotionMetricsConfig,
    foot_contact_payload_from_mujoco,
)
from src.locomotion.observations import build_observation_space, extract_observation
from src.locomotion.scenarios import ScenarioSample, build_scenario_xml, sample_scenario
```

**Reset / info payload pattern** (lines 76-112, 454-471):
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
    ...
    observation = extract_observation(self._data, self._command, self._previous_action)
    return observation, self._info()

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
```

**Active command schedule pattern** (lines 313-323, 430-433):
```python
def _command_at_time(self, sim_time: float) -> np.ndarray:
    sample = self._scenario_sample
    if sample is None or not sample.command_schedule:
        return self._command
    active = sample.command_schedule[0]
    for command in sample.command_schedule:
        if float(command["time"]) <= sim_time + 1e-12:
            active = command
        else:
            break
    return np.array([active["vx"], active["vy"], active["omega"]], dtype=np.float32)

def _current_sim_time(self) -> float:
    if self._data is not None and hasattr(self._data, "time") and float(self._data.time) > 0.0:
        return float(self._data.time)
    return self._step_count * self._dt
```

**Core step / metrics pattern** (lines 163-183):
```python
pose_after = self._base_pose_snapshot()
self._step_count += 1
metrics_step = self._record_locomotion_metrics(
    desired_command=self._command,
    pose_before=pose_before,
    pose_after=pose_after,
    action_target=action_target,
    previous_action_target=previous_action,
    previous_previous_action_target=previous_previous_action,
)
observation = extract_observation(self._data, self._command, self._previous_action)
reward = 0.0
terminated = metrics_step.failure_reason is not None
truncated = self._step_count >= self.config.max_episode_steps
info = self._info()
info["locomotion_metrics"] = self._metrics.latest_info_payload()
if terminated or truncated:
    summary = self._locomotion_summary_payload()
    self._last_locomotion_metrics_summary = copy.deepcopy(summary)
    info["locomotion_metrics_summary"] = summary
return observation, reward, terminated, truncated, info
```

**Validation / error handling pattern** (lines 44-51, 211-221):
```python
if self.config.sim_steps_per_frame < 1:
    raise ValueError("sim_steps_per_frame must be >= 1")
if self.config.max_episode_steps < 1:
    raise ValueError("max_episode_steps must be >= 1")
if self.config.heightfield_size > 64:
    raise ValueError("heightfield_size must be <= 64")
...
if vector.shape != (3,):
    raise ValueError(f"Velocity command action must have shape (3,), got {vector.shape}")
if not np.all(np.isfinite(vector)):
    raise ValueError("Velocity command action values must be finite")
```

**Planner instruction:** Add `current_command` in `_info()` using `_current_sim_time()` and `_command_at_time()`. Keep command-selection semantics env-owned; do not duplicate schedule iteration in `evaluation.py`.

---

### `src/locomotion/evaluation.py` (service / artifact runner, batch + file-I/O)

**Analog:** `src/locomotion/evaluation.py`

**Imports and constants pattern** (lines 5-18, 30-55):
```python
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Callable, Iterable

import numpy as np

from src.locomotion.controllers import ControllerRegistry, UnavailableControllerError
from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.scenarios import list_scenarios
...
_ARTIFACT_FILES = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
_EPISODE_CSV_FIELDS = (
    "run_id",
    "controller_id",
    "scenario_id",
    "seed",
    "action_mode",
    "commanded_velocity",
    "command_source",
    "success",
    "failure_reason",
    "step_count",
    "tracking_rmse",
    "distance_xy_m",
```

**Matrix validation pattern** (lines 142-203):
```python
def validate_evaluation_matrix(
    matrix: EvaluationMatrix,
    *,
    max_matrix_runs: int = 1000,
) -> tuple[dict[str, Any], ...]:
    """Validate an entire controller/scenario/seed matrix before side effects."""

    controllers = _tuple_of_str(matrix.controllers, "controllers")
    scenarios = _tuple_of_str(matrix.scenarios, "scenarios")
    seeds = _tuple_of_int(matrix.seeds, "seeds")
    _validate_seed_values(seeds)
    ...
    total_runs = len(controllers) * len(scenarios) * len(seeds)
    if total_runs > max_runs:
        raise ValueError(f"Evaluation matrix has {total_runs} runs; maximum is {max_runs}")
```

**Core runner pattern** (lines 206-303):
```python
def run_evaluation_matrix(
    matrix: EvaluationMatrix,
    config: EvaluationRunConfig | None = None,
    *,
    env_factory: Callable[[ArgusGo2EnvConfig], Any] = ArgusGo2Env,
) -> EvaluationResult:
    """Run an evaluation matrix with validation before artifacts or env construction."""

    run_config = config or EvaluationRunConfig()
    cells = validate_evaluation_matrix(matrix, max_matrix_runs=run_config.max_matrix_runs)
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = _prepare_run_dir(run_config.output_root)
    ...
    try:
        _observation, reset_info = env.reset(seed=cell["seed"])
        latest_info = dict(reset_info)
        terminated = False
        truncated = False
        while not (terminated or truncated):
            action, source, initial_context = _action_from_command_context(latest_info)
            _observation, _reward, terminated, truncated, info = env.step(
                np.asarray(action, dtype=np.float32)
            )
            latest_info = dict(info)
            commanded_velocity, command_source, command_context = _command_fields(
                latest_info,
                reset_info,
                default_action=action,
                default_source=source,
                default_context=initial_context,
            )
```

**Command context pattern to fix** (lines 410-447):
```python
def _action_from_command_context(info: dict[str, Any]) -> tuple[list[float], str, dict[str, Any]]:
    command_schedule = _serializable_sequence(info.get("command_schedule", ()))
    if command_schedule:
        first = command_schedule[0]
        return _command_vector(first), "scenario_schedule", {"command_schedule": command_schedule}
    current_command = info.get("current_command")
    if isinstance(current_command, dict):
        return _command_vector(current_command), str(current_command.get("source", "current_command")), {
            "current_command": dict(current_command),
            "command_schedule": [],
        }
    return [0.0, 0.0, 0.0], "default_zero", {"command_schedule": []}

def _command_fields(
    info: dict[str, Any],
    reset_info: dict[str, Any],
    *,
    default_action: list[float],
    default_source: str,
    default_context: dict[str, Any],
) -> tuple[list[float], str, dict[str, Any]]:
    current_command = info.get("current_command")
    if isinstance(current_command, dict):
        source = str(current_command.get("source", default_source))
        context = dict(default_context)
        context["current_command"] = dict(current_command)
        context["command_schedule"] = _serializable_sequence(
            info.get("command_schedule", reset_info.get("command_schedule", ()))
        )
        return _command_vector(current_command), source, context
```

**Artifact flattening pattern to fix** (lines 468-522):
```python
def _episode_csv_row(
    cell: dict[str, Any],
    summary: Any,
    commanded_velocity: list[float],
    command_source: str,
) -> dict[str, Any]:
    payload = summary if isinstance(summary, dict) else {}
    command_tracking = payload.get("command_tracking", {}) if isinstance(payload.get("command_tracking", {}), dict) else {}
    stability = payload.get("stability", {}) if isinstance(payload.get("stability", {}), dict) else {}
    ...
            "tracking_rmse": _metric_value(command_tracking, "tracking_error_rmse", default=0.0),
            "distance_xy_m": _metric_value(command_tracking, "distance_xy_m", default=0.0),
            "base_height_min_m": _metric_alias(stability, "base_height_min_m", "min_base_height_m"),
```

**Planner instruction:** Change `_action_from_command_context()` to prefer `current_command` before schedule fallback. Change `_episode_csv_row()` to source `distance_xy_m` from `stability` with alias compatibility, not from `command_tracking`.

**Path safety and CSV hardening patterns** (lines 384-397, 623-638, 645-648):
```python
def _prepare_run_dir(output_root: Path) -> Path:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in [""] + [f"-{idx:02d}" for idx in range(1, 1000)]:
        candidate = (root / f"{timestamp}{suffix}").resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"Run directory escapes output root: {candidate}")
...
with (run_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as fp:
    writer = csv.DictWriter(fp, fieldnames=list(_EPISODE_CSV_FIELDS), extrasaction="ignore")
    writer.writeheader()
    for row in episode_rows:
        writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})
...
def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
```

---

### `src/locomotion/metrics.py` (model / collector, transform)

**Analog:** `src/locomotion/metrics.py`

**Imports and dataclass pattern** (lines 3-14, 60-120):
```python
from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.locomotion.actions import joint_position_bounds
from src.locomotion.scenarios import ScenarioSample
...
@dataclass(frozen=True)
class LocomotionEpisodeSummary:
    """Aggregated locomotion metrics for one episode."""

    command_tracking: dict[str, Any]
    stability: dict[str, Any]
    action_quality: dict[str, Any]
    contact_terrain: dict[str, Any]
    success: bool
    failure_reason: str | None
    step_count: int
```

**Source-of-truth distance pattern** (lines 254-269, 367-391):
```python
def episode_summary(self) -> LocomotionEpisodeSummary:
    """Aggregate retained episode records into summary families."""
    steps = list(self._steps)
    command_tracking = self._command_tracking_summary(steps)
    stability = self._stability_summary(steps)
    action_quality = self._action_quality_summary(steps)
    contact_terrain = self._contact_terrain_summary(steps)
    return LocomotionEpisodeSummary(
        command_tracking=command_tracking,
        stability=stability,
        action_quality=action_quality,
        contact_terrain=contact_terrain,
        success=self._failure_reason is None,
        failure_reason=self._failure_reason,
        step_count=self._total_steps_seen,
    )

def _stability_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
    if not steps:
        return {
            "max_abs_roll_rad": 0.0,
            "max_abs_pitch_rad": 0.0,
            "min_base_height_m": 0.0,
            "max_base_height_deviation_m": 0.0,
            "distance_xy_m": 0.0,
            "distance_before_failure_m": None,
            "fall_count": 0,
            "fall_rate": 0.0,
        }
    ...
    return {
        "max_abs_roll_rad": float(max(abs(step.stability["roll_rad"]) for step in steps)),
        "max_abs_pitch_rad": float(max(abs(step.stability["pitch_rad"]) for step in steps)),
        "min_base_height_m": float(min(step.stability["base_height_m"] for step in steps)),
        "max_base_height_deviation_m": float(
            max(abs(step.stability["base_height_deviation_m"]) for step in steps)
        ),
        "distance_xy_m": float(steps[-1].stability["distance_xy_m"]),
        "distance_before_failure_m": self._distance_before_failure_m,
        "fall_count": fall_count,
        "fall_rate": 1.0 if fall_count else 0.0,
    }
```

**Validation pattern** (lines 613-619, 622-626):
```python
def _as_finite_vector(value: Sequence[float] | np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64).copy()
    if vector.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector

def _as_finite_scalar(value: float, name: str) -> float:
    scalar = float(value)
    if not np.isfinite(scalar):
        raise ValueError(f"{name} must be finite")
    return scalar
```

**Planner instruction:** Do not move `distance_xy_m` to `command_tracking`. Preserve metrics model schema; fix evaluator flattening instead.

---

### `tests/locomotion/test_locomotion_evaluation_runner.py` (test, batch + request-response)

**Analog:** `tests/locomotion/test_locomotion_evaluation_runner.py`

**Imports and fake env fixture pattern** (lines 1-15, 18-78):
```python
"""Evaluation runner matrix validation and fake-env execution tests."""

import json
from pathlib import Path

import pytest

from src.locomotion.controllers import UnavailableControllerError
from src.locomotion.evaluation import (
    EvaluationMatrix,
    EvaluationRunConfig,
    load_matrix_config,
    run_evaluation_matrix,
    validate_evaluation_matrix,
)

class _FakeEvaluationEnv:
    def __init__(self, config, calls, *, success=True) -> None:
        self.config = config
        self.calls = calls
        self.success = success
        self.calls.append(("construct", config))
        self._step_count = 0
```

**Fake reset/step info pattern** (lines 26-68):
```python
def reset(self, *, seed=None):
    self.calls.append(("reset", seed))
    info = {
        "seed": seed,
        "scenario_id": self.config.scenario_id,
        "action_mode": self.config.action_mode,
        "controller_id": self.config.controller_id,
        "step_count": 0,
        "sim_time": 0.0,
        "command_schedule": (
            {"time": 0.0, "vx": 0.4, "vy": 0.0, "omega": 0.0},
        ),
        "sampled_parameters": {"terrain_kind": "plane"},
        "controller_metadata": {"controller_id": self.config.controller_id},
    }
    return {"observation": 1}, info

def step(self, action):
    self.calls.append(("step", list(action)))
    self._step_count += 1
    info = {
        ...
        "current_command": {"vx": 0.4, "vy": 0.0, "omega": 0.0, "source": "scenario_schedule"},
        "locomotion_metrics": {"command_tracking": {"tracking_error": 0.01}},
        "locomotion_metrics_summary": {
            "command_tracking": {"tracking_error_rmse": 0.01, "distance_xy_m": 0.2},
            "stability": {"success": self.success},
```

**Runner assertion pattern** (lines 197-219):
```python
def test_runner_uses_scenario_command_schedule_and_records_command_context(tmp_path):
    calls = []
    matrix = EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=(101,),
        action_mode="velocity_command",
        max_episode_steps=5,
    )

    result = run_evaluation_matrix(
        matrix,
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_fake_env_factory(calls),
    )

    assert result.exit_code == 0
    assert len(result.step_rows) == 1
    row = result.step_rows[0]
    assert row["commanded_velocity"] == [0.4, 0.0, 0.0]
    assert row["command_source"] == "scenario_schedule"
    assert row["command_context"]["command_schedule"][0]["vx"] == 0.4
    assert ("step", [0.4, 0.0, 0.0]) in calls
```

**Planner instruction:** Extend fake env with zero command at reset and nonzero `current_command` after schedule transition. Assert `env.step()` receives the nonzero vector and row command context matches the same vector.

---

### `tests/locomotion/test_argus_go2_env_contract.py` (test, event-driven + request-response)

**Analog:** `tests/locomotion/test_argus_go2_env_contract.py`

**Imports and optional MuJoCo skip pattern** (lines 1-23):
```python
"""Contract tests for the Gymnasium-style Argus Go2 locomotion environment."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.locomotion.controllers import ControllerResult
from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.scenarios import list_scenarios


def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
    try:
        import mujoco  # noqa: F401
    except ImportError:
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
```

**Reset info contract assertion pattern** (lines 112-142):
```python
def test_reset_returns_observation_and_info():
    """reset(seed=...) returns a Gymnasium two-tuple and reproducibility info."""
    _skip_if_mujoco_python_unsupported()
    env = ArgusGo2Env()
    try:
        obs, info = env.reset(seed=123)
    finally:
        env.close()

    assert isinstance(obs, dict)
    assert info["seed"] == 123
    assert info["scenario_id"] == "flat_ground"
    assert info["action_mode"] == "velocity_command"
    assert info["controller_id"] == "analytical_trot"
    assert "sampled_parameters" in info
    assert "command_schedule" in info
    assert "disturbance_schedule" in info
    assert info["step_count"] == 0
    assert "sim_time" in info
```

**Mocked env step pattern not requiring real MuJoCo** (lines 296-335):
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
    ...
    with patch("src.locomotion.env.dispatch_controller", side_effect=dispatch_controller):
        with patch.dict("sys.modules", {"mujoco": SimpleNamespace(mj_step=mj_step)}):
            obs, _reward, _terminated, _truncated, info = env.step(action)

    assert calls == ["dispatch", "mj_step", "mj_step"]
    np.testing.assert_allclose(fake_data.ctrl.copy(), expected_ctrl)
    np.testing.assert_allclose(obs["command"], action)
    np.testing.assert_allclose(obs["previous_action"], expected_ctrl.astype(np.float32))
    assert info["controller_id"] == "analytical_trot"
    assert info["action_mode"] == "velocity_command"
    assert "controller_metadata" not in info
```

**Planner instruction:** Add a contract test for `current_command` at reset and after forcing simulation time past the sampled schedule transition. Prefer mock/fake-data pattern over requiring real MuJoCo where possible.

---

### `tests/locomotion/test_locomotion_evaluation_exports.py` (test, file-I/O + transform)

**Analog:** `tests/locomotion/test_locomotion_evaluation_exports.py`

**Imports and artifact constants pattern** (lines 1-22):
```python
"""Artifact export and offline comparison tests for locomotion evaluation.

Covers LOC-METRICS-05, LOC-EVAL-02, LOC-EVAL-03 and Phase 04 export
requirements D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-12.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.locomotion.evaluation import (
    EvaluationMatrix,
    EvaluationRunConfig,
    regenerate_comparison,
    run_evaluation_matrix,
)

_ARTIFACT_NAMES = {"manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md"}
```

**Fake export env pattern** (lines 24-91):
```python
class _FakeExportEnv:
    def __init__(self, config, *, success: bool = True, failure_reason: str | None = None) -> None:
        self.config = config
        self.success = success
        self.failure_reason = failure_reason
        self._step_count = 0

    def reset(self, *, seed=None):
        return {"observation": 1}, {
            "seed": seed,
            "scenario_id": self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "controller_id": self.config.controller_id,
            "step_count": 0,
            "sim_time": 0.0,
            "spawn_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "sampled_parameters": {"terrain_kind": "plane"},
            "command_schedule": ({"time": 0.0, "vx": 0.4, "vy": 0.0, "omega": 0.0},),
            "disturbance_schedule": (),
            "controller_metadata": {"controller_id": self.config.controller_id, "label": "baseline"},
        }
```

**Artifact assertion pattern** (lines 118-210):
```python
def test_run_writes_self_contained_locomotion_eval_artifacts(tmp_path):
    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_factory(),
    )

    assert result.exit_code == 0
    assert result.run_dir.parent == tmp_path
    assert {path.name for path in result.run_dir.iterdir()} == _ARTIFACT_NAMES
    ...
    with (result.run_dir / "episodes.csv").open(newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert len(rows) == 1
    row = rows[0]
    ...
    assert row["commanded_velocity"] == "[0.4,0.0,0.0]"
    assert row["command_source"] == "scenario_schedule"
```

**Production schema mapping test pattern** (lines 261-309):
```python
def test_episode_export_maps_production_locomotion_summary_schema(tmp_path):
    class ProductionSummaryEnv(_FakeExportEnv):
        def step(self, action):
            _observation, reward, terminated, truncated, info = super().step(action)
            info["locomotion_metrics_summary"] = {
                "command_tracking": {"tracking_error_rmse": 0.11, "distance_xy_m": 0.42},
                "stability": {
                    "min_base_height_m": 0.27,
                    "max_base_height_deviation_m": 0.055,
                    "max_abs_roll_rad": 0.12,
                    "max_abs_pitch_rad": 0.13,
                },
...
    assert float(row["base_height_min_m"]) == 0.27
    assert float(row["base_height_max_deviation_m"]) == 0.055
    assert float(row["roll_abs_max_rad"]) == 0.12
    assert float(row["pitch_abs_max_rad"]) == 0.13
```

**Planner instruction:** Tighten this mapping test so `command_tracking` omits or zeroes `distance_xy_m`, `stability.distance_xy_m` is nonzero, and `episodes.csv`, `result.episode_rows`, `summary.json`, and `comparison.md` all preserve the stability-sourced distance.

---

### `tests/locomotion/test_locomotion_baseline_regression.py` (test, batch + transform)

**Analog:** `tests/locomotion/test_locomotion_baseline_regression.py`

**Imports and thresholds pattern** (lines 1-21):
```python
"""Analytical trot flat-ground regression thresholds.

LOC-EVAL-04 / D-13 / D-14 / D-15: keep the current analytical
baseline guarded by robust thresholds, not golden snapshots. T-04-03 keeps
calibration context explicit when thresholds change.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.locomotion.evaluation import EvaluationMatrix, EvaluationRunConfig, run_evaluation_matrix

TRACKING_RMSE_MAX = 1.50
DISTANCE_XY_MIN_M = 0.01
BASE_HEIGHT_MIN_M = 0.15
ROLL_ABS_MAX_RAD = 0.90
PITCH_ABS_MAX_RAD = 0.90
```

**Threshold helper pattern** (lines 34-70):
```python
def assert_analytical_flat_ground_thresholds(rows):
    """Assert robust threshold bounds for analytical_trot flat_ground episodes."""

    materialized = list(rows)
    assert materialized, "expected at least one analytical flat-ground episode row"
    for index, row in enumerate(materialized):
        label = row.get("run_id", f"row[{index}]")
        assert row.get("success") is True, f"{label}: locomotion success must be true"
        assert not row.get("failure_reason"), f"{label}: failure_reason must be empty"
        assert "commanded_velocity" in row, f"{label}: commanded_velocity is required"
        assert "command_source" in row, f"{label}: command_source is required"
        assert row["command_source"], f"{label}: command_source must be non-empty"

        commanded_velocity = _coerce_commanded_velocity(row["commanded_velocity"])
        translational_speed = (commanded_velocity[0] ** 2 + commanded_velocity[1] ** 2) ** 0.5
        tracking_rmse = _coerce_float(row, "tracking_rmse")
        distance_xy_m = _coerce_float(row, "distance_xy_m")
        base_height_min_m = _coerce_float(row, "base_height_min_m")
        roll_abs_max_rad = _coerce_float(row, "roll_abs_max_rad")
        pitch_abs_max_rad = _coerce_float(row, "pitch_abs_max_rad")

        assert tracking_rmse <= TRACKING_RMSE_MAX, f"{label}: tracking_rmse {tracking_rmse} > {TRACKING_RMSE_MAX}"
        if translational_speed > 0.0:
            assert distance_xy_m >= DISTANCE_XY_MIN_M, (
                f"{label}: distance_xy_m {distance_xy_m} < {DISTANCE_XY_MIN_M} "
                f"for commanded_velocity={commanded_velocity}"
            )
```

**Negative fixture pattern** (lines 115-145, 132-136):
```python
@pytest.mark.parametrize(
    "overrides",
    [
        {"success": False},
        {"failure_reason": "base_height_below_threshold"},
    ],
)
def test_threshold_helper_rejects_locomotion_failure(overrides):
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([_good_row(**overrides)])
...
def test_threshold_helper_rejects_zero_distance_for_translational_command():
    with pytest.raises(AssertionError):
        assert_analytical_flat_ground_thresholds([
            _good_row(commanded_velocity=[0.4, 0.0, 0.0], distance_xy_m=DISTANCE_XY_MIN_M - 0.001)
        ])
```

**Real smoke pattern with skip** (lines 179-205):
```python
@pytest.mark.integration
def test_analytical_trot_flat_ground_fixed_seed_regression(tmp_path):
    """D-14/D-15: real MuJoCo smoke gate for analytical_trot flat_ground."""

    _skip_if_mujoco_python_unsupported()
    if not (Path("models/unitree_go2") / "go2.xml").exists():
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")

    matrix = EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=(101, 202, 303),
        action_mode="velocity_command",
        max_episode_steps=25,
    )
    config = EvaluationRunConfig(
        output_root=tmp_path,
        fail_on_locomotion_failure=True,
        verbose=False,
    )

    result = run_evaluation_matrix(matrix, config)

    assert result.exit_code == 0
    assert result.had_locomotion_failure is False
    assert (result.run_dir / "summary.json").exists()
    assert_analytical_flat_ground_thresholds(result.episode_rows)
```

**Planner instruction:** Add a fake/stationary env fixture that emits nonzero `current_command` but zero `distance_xy_m`; assert the baseline gate fails. Keep real MuJoCo smoke optional via existing skip conditions.

---

### `src/locomotion/scenarios.py` (model / scenario catalog, transform)

**Analog:** `src/locomotion/scenarios.py`

**Scenario sample schema pattern** (lines 12-27):
```python
@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    display_name: str
    terrain_kind: str
    randomizes_terrain: bool = False
    has_disturbance: bool = False


@dataclass(frozen=True)
class ScenarioSample:
    scenario_id: str
    spawn_pose: tuple[float, float, float, float]
    terrain_parameters: dict[str, float | int | str | tuple[float, ...]]
    command_schedule: tuple[dict[str, float], ...]
    disturbance_schedule: tuple[dict[str, float], ...]
```

**Schedule generation pattern** (lines 244-255):
```python
def _sample_command_schedule(
    rng: np.random.Generator,
) -> tuple[dict[str, float], dict[str, float]]:
    return (
        {"time": 0.0, "vx": 0.0, "vy": 0.0, "omega": 0.0},
        {
            "time": float(rng.uniform(0.2, 0.6)),
            "vx": float(rng.uniform(0.1, 0.4)),
            "vy": float(rng.uniform(-0.1, 0.1)),
            "omega": float(rng.uniform(-0.4, 0.4)),
        },
    )
```

**Planner instruction:** Treat this as supporting evidence. Do not change schedule generation unless a boundary bug is proven; Phase 6 should make runner/env consume the existing zero-to-nonzero schedule correctly.

## Shared Patterns

### Env-owned command timing
**Source:** `src/locomotion/env.py` lines 313-323 and `src/locomotion/scenarios.py` lines 244-255  
**Apply to:** `src/locomotion/env.py`, `src/locomotion/evaluation.py`, runner/env tests
```python
active = sample.command_schedule[0]
for command in sample.command_schedule:
    if float(command["time"]) <= sim_time + 1e-12:
        active = command
    else:
        break
return np.array([active["vx"], active["vy"], active["omega"]], dtype=np.float32)
```

### Artifact path containment
**Source:** `src/locomotion/evaluation.py` lines 384-397  
**Apply to:** Any artifact-writing changes in `evaluation.py`
```python
root = Path(output_root).expanduser().resolve()
root.mkdir(parents=True, exist_ok=True)
candidate = (root / f"{timestamp}{suffix}").resolve()
if root != candidate and root not in candidate.parents:
    raise ValueError(f"Run directory escapes output root: {candidate}")
```

### CSV formula safety
**Source:** `src/locomotion/evaluation.py` lines 633-638 and 645-648  
**Apply to:** `episodes.csv` write path and export tests
```python
writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})

def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
```

### Production metrics family ownership
**Source:** `src/locomotion/metrics.py` lines 367-391  
**Apply to:** `src/locomotion/evaluation.py`, `tests/locomotion/test_locomotion_evaluation_exports.py`, baseline tests
```python
return {
    "max_abs_roll_rad": float(max(abs(step.stability["roll_rad"]) for step in steps)),
    "max_abs_pitch_rad": float(max(abs(step.stability["pitch_rad"]) for step in steps)),
    "min_base_height_m": float(min(step.stability["base_height_m"] for step in steps)),
    "max_base_height_deviation_m": float(
        max(abs(step.stability["base_height_deviation_m"]) for step in steps)
    ),
    "distance_xy_m": float(steps[-1].stability["distance_xy_m"]),
    "distance_before_failure_m": self._distance_before_failure_m,
    "fall_count": fall_count,
    "fall_rate": 1.0 if fall_count else 0.0,
}
```

### Deterministic pytest fake-env pattern
**Source:** `tests/locomotion/test_locomotion_evaluation_runner.py` lines 18-78 and `tests/locomotion/test_locomotion_evaluation_exports.py` lines 24-101  
**Apply to:** New Phase 6 tests that should not require MuJoCo/Gymnasium availability
```python
def _fake_env_factory(calls, *, success=True):
    def factory(config):
        return _FakeEvaluationEnv(config, calls, success=success)

    return factory
```

## No Analog Found

All required files have exact or supporting analogs in the current codebase. No planner fallback to research-only patterns is required.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src/locomotion`, `/home/prannayag/pragnition/robotics/argus/tests/locomotion`  
**Files scanned:** 22 listed, 8 read for extraction  
**Pattern extraction date:** 2026-05-01

## Planner Checklist

- Prefer `info["current_command"]` for action generation before any schedule fallback.
- Emit `current_command` from `ArgusGo2Env._info()` at reset and every step.
- Preserve `command_schedule` as metadata, not as the runtime command source after reset.
- Flatten `distance_xy_m` from `summary["stability"]`; keep aggregate comparison fed by that corrected row.
- Keep `_prepare_run_dir()` containment and `_csv_safe()` writer behavior unchanged.
- Prove repairs with fake-env pytest fixtures first; leave real MuJoCo smoke conditional on existing skip behavior.
