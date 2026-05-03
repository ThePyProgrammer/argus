# Phase 04: evaluation-runner-and-regression - Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 6
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/main.py` | route / CLI controller | request-response | `src/main.py` | exact-existing-file |
| `src/locomotion/evaluation.py` | service / utility | batch + file-I/O + request-response | `src/locomotion/env.py`; `src/metrics/detection_export.py`; `src/locomotion/controllers.py` | composite-exact |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | test | batch + request-response | `tests/locomotion/test_argus_go2_env_contract.py`; `tests/test_main_args.py` | role-match |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | test | file-I/O + transform | `tests/metrics/test_detection_export.py`; `tests/integration/test_detections_export.py` | exact-role |
| `tests/locomotion/test_locomotion_baseline_regression.py` | test | batch + request-response | `tests/locomotion/test_argus_go2_env_contract.py`; `tests/locomotion/test_argus_go2_env_metrics.py` | role-match |
| `pytest.ini` | config | request-response | `pytest.ini` | exact-existing-file |

## Pattern Assignments

### `src/main.py` (route / CLI controller, request-response)

**Analog:** `src/main.py`

**Imports and lazy-heavy-import pattern** (lines 27-42, 62-86):
```python
import argparse
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
try:
    import rerun as rr
except ImportError:  # pragma: no cover - optional visualization dependency
    rr = None
# Phase 6 DET-METRICS-03: uvicorn is imported lazily inside ``run_web_mode``
# so ``src.main`` can be imported ... in environments that lack the web-server deps.
```
```python
class _RobotInstanceProxy:
    """Lazy module-level seam for tests without importing heavy robot deps."""

    @staticmethod
    def create(*args, **kwargs):
        from src.coordination.robot_instance import RobotInstance as _RobotInstance

        return _RobotInstance.create(*args, **kwargs)
```

**Parser extension pattern** (lines 89-193):
```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Single-robot SLAM in MuJoCo")
    parser.add_argument(
        "--control",
        choices=["teleop", "waypoint", "random", "explore", "multi", "web"],
        default="web",
        help="Control mode (default: web)",
    )
    ...
    parser.add_argument(
        "--labeled-eval-set",
        dest="labeled_eval_set",
        default=None,
        metavar="PATH",
        help="(RESERVED -- future milestone) Path to a committed labeled "
             "evaluation set. Passing this flag currently raises "
             "NotImplementedError per DET-METRICS-03 / CONTEXT D-10.",
    )
    return parser.parse_args()
```

**Dispatch / fail-fast branch pattern** (lines 787-810):
```python
def main() -> None:
    """Run the single-robot SLAM loop."""
    args = parse_args()

    # DET-METRICS-03 / CONTEXT D-10: --labeled-eval-set is reserved for a
    # future milestone. Raising BEFORE any heavy init ... keeps the subprocess CLI test fast and deterministic.
    if getattr(args, "labeled_eval_set", None) is not None:
        raise NotImplementedError(
            "Labeled eval set ingestion arrives in a future milestone"
        )

    if args.control == "web":
        run_web_mode(args)
        return

    if args.control == "multi":
        run_multi_mode(args)
        return
```

**Apply to Phase 4:** Add `eval-locomotion` as a distinct top-level subcommand/branch, not another `--control` choice. Keep heavy locomotion/evaluation imports lazy in the dispatch branch so `src.main` remains importable and parser tests stay fast.

---

### `src/locomotion/evaluation.py` (service / utility, batch + file-I/O + request-response)

**Analogs:** `src/locomotion/env.py`, `src/metrics/detection_export.py`, `src/locomotion/controllers.py`, `src/locomotion/scenarios.py`, `src/locomotion/metrics.py`

**Dataclass/config and absolute import pattern** (`src/locomotion/env.py` lines 3-23, 26-37):
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
...

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
    metrics_config: LocomotionMetricsConfig | None = None
```

**Fail-fast validation pattern for controller ids and unavailable placeholders** (`src/locomotion/controllers.py` lines 288-312):
```python
@classmethod
def create(cls, name: str | None = None, **kwargs: Any) -> LocomotionController:
    """Instantiate an available controller by id.

    Unknown ids are deterministic errors and never fall back to the default.
    Unavailable entries raise before constructor execution.
    """

    if name is None:
        name = cls._default
    if name not in cls._controllers:
        raise ValueError(
            f"Unknown locomotion controller '{name}'. Available: {list(cls._controllers.keys())}"
        )
    info = cls._controllers[name]
    klass = _load_class(info["class_path"])
    if klass is None:
        raise ImportError(f"Cannot load locomotion controller class: {info['class_path']}")
    available, reason = _probe_availability(klass)
    if not available:
        raise UnavailableControllerError(
            f"Controller '{name}' is unavailable: "
            f"{reason or f'{klass.__qualname__}.available() reported unavailable'}"
        )
    return klass(**kwargs)
```

**Scenario catalog validation pattern** (`src/locomotion/scenarios.py` lines 62-64, 106-124):
```python
def list_scenarios() -> list[str]:
    """Return the available named scenario ids in deterministic order."""
    return sorted(SCENARIOS.keys())
```
```python
def sample_scenario(
    scenario_id: str,
    rng: np.random.Generator,
    heightfield_size: int = 16,
) -> ScenarioSample:
    """Sample reset-time metadata for a named locomotion scenario.
    ...
    Raises:
        ValueError: If ``scenario_id`` is not a fixed catalog key.
    """
    if scenario_id not in SCENARIOS:
        raise ValueError(
            f"Unknown locomotion scenario '{scenario_id}'. Available: {list_scenarios()}"
        )
```

**Runner loop source of truth pattern** (`src/locomotion/env.py` lines 76-112, 114-183):
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
```
```python
def step(
    self,
    action: np.ndarray,
) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
    """Apply a mode-specific action and return the Gymnasium five-tuple."""
    ...
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

**Per-episode summary payload pattern** (`src/locomotion/env.py` lines 413-425):
```python
def _locomotion_summary_payload(self) -> dict[str, Any]:
    summary = self._metrics.episode_summary()
    payload = {
        "command_tracking": dict(summary.command_tracking),
        "stability": dict(summary.stability),
        "action_quality": dict(summary.action_quality),
        "contact_terrain": dict(summary.contact_terrain),
        "success": bool(summary.success),
        "failure_reason": summary.failure_reason,
        "step_count": int(summary.step_count),
    }
    payload["stability"]["success"] = bool(summary.success)
    return payload
```

**Reproducibility info pattern** (`src/locomotion/env.py` lines 454-471):
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

**File writer pattern for JSONL/session artifacts** (`src/metrics/detection_export.py` lines 67-95, 109-134, 147-152):
```python
def __init__(self, session_id: str, base_dir: Path | None = None) -> None:
    self._base_dir: Path = Path(base_dir) if base_dir is not None else Path(tempfile.gettempdir())
    self._lock = threading.Lock()
    self._fp: TextIO | None = None
    self._file_path: Path | None = None
    self._session_id: str = str(session_id)
    self._open_for_session(self._session_id)
```
```python
def _open_for_session(self, session_id: str) -> None:
    session_dir = self._base_dir / "argus_sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / "detections.jsonl"
    self._fp = open(path, "a", buffering=1, encoding="utf-8")
    self._file_path = path
    self._session_id = session_id
```
```python
def append(...):
    record = {
        "robot_id": str(robot_id),
        "backend_id": str(backend_id),
        "capture_timestamp": float(capture_timestamp),
        "obb": obb.to_wire(),
    }
    line = json.dumps(record, separators=(",", ":")) + "\n"
    with self._lock:
        if self._fp is None:
            return
        self._fp.write(line)
```

**Metric aggregation source pattern** (`src/locomotion/metrics.py` lines 254-269, 351-365, 367-391, 393-432):
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
```

**Apply to Phase 4:** Keep `src/locomotion/evaluation.py` as a thin orchestration/export layer. It should validate the entire matrix first, instantiate `ArgusGo2Env(ArgusGo2EnvConfig(...))` only after validation, copy `info["locomotion_metrics"]` into JSONL, flatten terminal `info["locomotion_metrics_summary"]` into CSV, write manifest/summary/Markdown under one timestamped run dir, and aggregate from saved episode rows for reload.

---

### `tests/locomotion/test_locomotion_evaluation_runner.py` (test, batch + request-response)

**Analogs:** `tests/locomotion/test_argus_go2_env_contract.py`, `tests/test_main_args.py`, `tests/locomotion/test_argus_go2_env_metrics.py`

**Fake MuJoCo/env seam pattern** (`tests/locomotion/test_argus_go2_env_contract.py` lines 26-62):
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
```

**Monkeypatch dispatch pattern** (`tests/locomotion/test_argus_go2_env_contract.py` lines 296-335):
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
        ...
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
```

**Subprocess CLI fail-fast pattern** (`tests/test_main_args.py` lines 206-228):
```python
def test_labeled_eval_set_flag_raises_not_implemented(tmp_path):
    """--labeled-eval-set <path> must raise NotImplementedError + exit non-zero."""
    dummy = tmp_path / "eval.json"
    dummy.write_text("{}", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "src.main", "--labeled-eval-set", str(dummy)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode != 0, (...)
    combined = proc.stdout + proc.stderr
    assert "Labeled eval set ingestion arrives in a future milestone" in combined
    assert "NotImplementedError" in combined
```

**Apply to Phase 4:** Unit-test matrix validation without creating envs for invalid controller/scenario input; monkeypatch/fake env construction for happy-path matrix runs; assert locomotion failures still write artifacts but return a nonzero/failed result.

---

### `tests/locomotion/test_locomotion_evaluation_exports.py` (test, file-I/O + transform)

**Analogs:** `tests/metrics/test_detection_export.py`, `tests/integration/test_detections_export.py`

**`tmp_path` artifact layout pattern** (`tests/metrics/test_detection_export.py` lines 63-74):
```python
def test_writer_creates_session_directory(tmp_path):
    session_id = "abc123"
    writer = DetectionExportWriter(session_id=session_id, base_dir=tmp_path)
    try:
        session_dir = tmp_path / "argus_sessions" / session_id
        assert session_dir.is_dir(), "session directory should be created"
        file_path = session_dir / "detections.jsonl"
        assert file_path.is_file(), "detections.jsonl should exist (may be empty)"
        assert writer.session_id == session_id
        assert writer.file_path == file_path
    finally:
        writer.close()
```

**JSONL parse-and-shape assertions** (`tests/metrics/test_detection_export.py` lines 82-97, 104-131):
```python
def test_append_writes_one_line_per_call(tmp_path):
    writer = DetectionExportWriter(session_id="s1", base_dir=tmp_path)
    try:
        obb = FakeOBB()
        writer.append(obb, robot_id="robot_0", backend_id="yolov11", capture_timestamp=12.345)
        writer.append(obb, robot_id="robot_1", backend_id="yolov11", capture_timestamp=12.5)
    finally:
        writer.close()

    content = (tmp_path / "argus_sessions" / "s1" / "detections.jsonl").read_text()
    lines = [ln for ln in content.split("\n") if ln.strip()]
    assert len(lines) == 2, f"expected 2 lines, got {len(lines)}"
    for ln in lines:
        parsed = json.loads(ln)
        assert isinstance(parsed, dict)
```

**Round-trip saved artifact pattern** (`tests/integration/test_detections_export.py` lines 94-124):
```python
def test_endpoint_streams_ndjson_and_round_trips(app_with_streaming_viz):
    ...
    lines = [line for line in r.text.split("\n") if line.strip()]
    assert len(lines) == 30, f"expected 30 lines, got {len(lines)}"

    for line, original in zip(lines, originals):
        rec = json.loads(line)
        assert set(rec.keys()) >= {
            "robot_id", "backend_id", "capture_timestamp", "obb",
        }, rec.keys()
        reconstructed = OrientedBox3D.from_wire(rec["obb"])
```

**Apply to Phase 4:** Use `tmp_path` for hermetic run dirs. Assert `manifest.json`, step JSONL, episode CSV, `summary.json`, and Markdown are present; parse JSONL line-by-line; parse CSV rows with compact ids; regenerate comparison from saved artifacts and assert no env constructor is called.

---

### `tests/locomotion/test_locomotion_baseline_regression.py` (test, batch + request-response)

**Analogs:** `tests/locomotion/test_argus_go2_env_contract.py`, `tests/locomotion/test_argus_go2_env_metrics.py`, `pytest.ini`

**Integration skip and marker pattern** (`tests/locomotion/test_argus_go2_env_contract.py` lines 17-24, 202-217):
```python
def _skip_if_mujoco_python_unsupported() -> None:
    if not ((3, 10) <= sys.version_info < (3, 13)):
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
    try:
        import mujoco  # noqa: F401
    except ImportError:
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")
```
```python
@pytest.mark.integration
@pytest.mark.parametrize("scenario_id", list_scenarios())
def test_reset_can_initialize_and_close_mujoco_for_each_named_scenario(scenario_id):
    _skip_if_mujoco_python_unsupported()
    if not (Path("models/unitree_go2") / "go2.xml").exists():
        pytest.skip("MuJoCo integration requires Python >=3.10,<3.13 and mujoco installed")

    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id=scenario_id))
    try:
        obs, info = env.reset(seed=123)
        assert isinstance(obs, dict)
        assert info["scenario_id"] == scenario_id
        assert env._model is not None
        assert env._data is not None
    finally:
        env.close()
```

**Terminal summary assertion pattern** (`tests/locomotion/test_argus_go2_env_metrics.py` lines 145-169):
```python
def test_terminal_or_truncated_step_contains_episode_summary():
    """D-04 D-07: survival to truncation is successful episode summary semantics."""
    env, _data = _make_env(ArgusGo2EnvConfig(sim_steps_per_frame=1, max_episode_steps=1))
    ...
    assert terminated is False
    assert truncated is True
    assert "locomotion_metrics_summary" in info
    assert set(info["locomotion_metrics_summary"]) >= {
        "command_tracking",
        "stability",
        "action_quality",
        "contact_terrain",
    }
    assert info["locomotion_metrics_summary"]["success"] is True
    assert info["locomotion_metrics_summary"]["failure_reason"] is None
```

**Failure semantics pattern** (`tests/locomotion/test_argus_go2_env_metrics.py` lines 122-142):
```python
def test_failure_threshold_sets_terminated_true():
    """LOC-METRICS-02: D-05 D-06 D-08 threshold overrides terminate immediately."""
    config = ArgusGo2EnvConfig(
        sim_steps_per_frame=1,
        metrics_config=LocomotionMetricsConfig(min_base_height_m=0.25, min_progress_m_per_s=0.001),
    )
    env, data = _make_env(config)
    ...
    assert terminated is True
    assert truncated is False
    assert info["locomotion_metrics_summary"]["stability"]["success"] is False
    assert info["locomotion_metrics_summary"]["stability"]["fall_rate"] == pytest.approx(1.0)
```

**Apply to Phase 4:** Mark the real analytical flat-ground regression as `@pytest.mark.integration` unless a new marker is explicitly introduced. Use 2-3 fixed seeds. Assert no locomotion failure and thresholds over `tracking_error_rmse`, stability height/roll/pitch, and `distance_xy_m`. Keep synthetic/unit threshold-failure tests separate from real MuJoCo tests.

---

### `pytest.ini` (config, request-response)

**Analog:** `pytest.ini`

**Marker registration pattern** (lines 1-17):
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
    x2_asset: tests requiring licensed local AGIBOT X2 MuJoCo assets
```

**Apply to Phase 4:** Prefer existing `integration` for the real MuJoCo baseline regression. Only modify `pytest.ini` if implementation chooses a new dedicated marker; if so, add it under `markers =` and decide whether default `addopts` excludes it.

## Shared Patterns

### Absolute `src.*` imports and dataclass configs
**Source:** `src/locomotion/env.py` lines 3-23, 26-37  
**Apply to:** `src/locomotion/evaluation.py`, tests importing production modules.

Use project-local absolute imports (`from src.locomotion...`) and dataclasses for configs/results. Avoid relative imports.

### Matrix validation before side effects
**Source:** `src/locomotion/controllers.py` lines 288-312; `src/locomotion/scenarios.py` lines 62-64, 121-124  
**Apply to:** CLI dispatch and evaluation runner.

Validate controllers via `ControllerRegistry` and scenarios via `list_scenarios()` before creating run directories or constructing `ArgusGo2Env`. Placeholder controllers must raise `UnavailableControllerError` before any simulation cell runs.

### Existing metrics are the export API
**Source:** `src/locomotion/env.py` lines 177-183, 413-425; `src/locomotion/metrics.py` lines 237-269  
**Apply to:** JSONL export, CSV export, summary aggregation, regression assertions.

Copy `info["locomotion_metrics"]` for per-step rows and terminal `info["locomotion_metrics_summary"]` for episode rows. Do not recompute Phase 3 metric semantics in the exporter.

### File artifact writing
**Source:** `src/metrics/detection_export.py` lines 80-95, 109-134  
**Apply to:** step JSONL, manifest JSON, summary JSON, Markdown scorecard, CSV writer.

Create parent directories explicitly, use `encoding="utf-8"`, use compact JSON (`separators=(",", ":")`) for JSONL, and test by parsing artifacts back from disk.

### Test fakes and monkeypatching
**Source:** `tests/locomotion/test_argus_go2_env_contract.py` lines 26-62, 296-335; `tests/metrics/test_detection_export.py` lines 63-97  
**Apply to:** fake-env runner tests, exporter tests, reload-without-rerun tests.

Use small fake classes for MuJoCo/env seams, `patch`/`monkeypatch` to intercept construction, `tmp_path` for artifacts, and parse artifacts instead of snapshotting raw strings.

## No Analog Found

None. Every planned file has a same-role or composite same-flow analog in the current codebase.

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src`, `/home/prannayag/pragnition/robotics/argus/tests`, `/home/prannayag/pragnition/robotics/argus/pytest.ini`  
**Files scanned:** 9 core analog files plus project skill index  
**Pattern extraction date:** 2026-05-01
