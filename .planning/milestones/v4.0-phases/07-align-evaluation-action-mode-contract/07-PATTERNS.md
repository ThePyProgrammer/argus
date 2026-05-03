# Phase 7: align-evaluation-action-mode-contract - Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 7 new/modified files
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/locomotion/evaluation.py` | service | request-response + file-I/O | `src/locomotion/evaluation.py` | exact-self |
| `src/main.py` | CLI/controller | request-response | `src/main.py` | exact-self |
| `docs/locomotion-benchmark.md` | documentation | transform | `docs/locomotion-benchmark.md` | exact-self |
| `tests/locomotion/test_locomotion_evaluation_runner.py` | test | request-response | `tests/locomotion/test_locomotion_evaluation_runner.py` | exact-self |
| `tests/locomotion/test_locomotion_evaluation_exports.py` | test | file-I/O | `tests/locomotion/test_locomotion_evaluation_exports.py` | exact-self |
| `tests/test_main_args.py` | test | request-response | `tests/test_main_args.py` | exact-self |
| `tests/test_locomotion_benchmark_docs.py` | test | file-I/O | `tests/test_locomotion_benchmark_docs.py` | exact-self |

## Pattern Assignments

### `src/locomotion/evaluation.py` (service, request-response + file-I/O)

**Analog:** `src/locomotion/evaluation.py`

**Imports pattern** (lines 5-18):
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
```

**Matrix contract pattern** (lines 20-30, 77-85):
```python
_ALLOWED_MATRIX_CONFIG_KEYS = {
    "controllers",
    "scenarios",
    "seeds",
    "action_mode",
    "max_episode_steps",
    "sim_steps_per_frame",
    "heightfield_size",
}
_MAX_SEED = 2**32 - 1
_ARTIFACT_FILES = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")

@dataclass(frozen=True)
class EvaluationMatrix:
    controllers: tuple[str, ...] = ("analytical_trot",)
    scenarios: tuple[str, ...] = ("flat_ground",)
    seeds: tuple[int, ...] = (101, 202)
    action_mode: str = "velocity_command"
    max_episode_steps: int = 500
    sim_steps_per_frame: int = 10
    heightfield_size: int = 16
```

**Validation-before-side-effects pattern** (lines 142-183, 206-218):
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
    action_mode = matrix.action_mode
    if not isinstance(action_mode, str) or not action_mode:
        raise ValueError("action_mode must be a non-empty string")
    max_episode_steps = _positive_int(matrix.max_episode_steps, "max_episode_steps")
    sim_steps_per_frame = _positive_int(matrix.sim_steps_per_frame, "sim_steps_per_frame")
    heightfield_size = _positive_int(matrix.heightfield_size, "heightfield_size")
    max_runs = _positive_int(max_matrix_runs, "max_matrix_runs")

    controller_entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    for controller_id in controllers:
        if controller_id not in controller_entries:
            raise ValueError(
                f"Unknown locomotion controller '{controller_id}'. Available: {sorted(controller_entries)}"
            )
        entry = controller_entries[controller_id]
        if not entry.get("available", False):
            raise UnavailableControllerError(
                f"Controller '{controller_id}' is unavailable: "
                f"{entry.get('reason') or 'availability probe reported unavailable'}"
            )

    available_scenarios = set(list_scenarios())
    for scenario_id in scenarios:
        if scenario_id not in available_scenarios:
            raise ValueError(
                f"Unknown locomotion scenario '{scenario_id}'. Available: {sorted(available_scenarios)}"
            )

    total_runs = len(controllers) * len(scenarios) * len(seeds)
    if total_runs > max_runs:
        raise ValueError(f"Evaluation matrix has {total_runs} runs; maximum is {max_runs}")
```

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
```

**Action builder call-site pattern to preserve and make mode-aware** (lines 223-251):
```python
for cell in cells:
    env_config = ArgusGo2EnvConfig(
        scenario_id=cell["scenario_id"],
        action_mode=cell["action_mode"],
        controller_id=cell["controller_id"],
        sim_steps_per_frame=cell["sim_steps_per_frame"],
        max_episode_steps=cell["max_episode_steps"],
        heightfield_size=cell["heightfield_size"],
    )
    env = env_factory(env_config)
    reset_info: dict[str, Any] = {}
    latest_info: dict[str, Any] = {}
    commanded_velocity = [0.0, 0.0, 0.0]
    command_source = "default_zero"
    command_context: dict[str, Any] = {"command_schedule": []}
    try:
        _observation, reset_info = env.reset(seed=cell["seed"])
        latest_info = dict(reset_info)
        terminated = False
        truncated = False
        runner_step_count = 0
        while not (terminated or truncated):
            action, source, initial_context = _action_from_command_context(latest_info)
            executed_commanded_velocity = list(action)
            executed_command_source = source
            executed_command_context = dict(initial_context)
            _observation, _reward, terminated, truncated, info = env.step(
                np.asarray(action, dtype=np.float32)
            )
```

**Current command extraction pattern to keep for `velocity_command`** (lines 423-443):
```python
def _action_from_command_context(info: dict[str, Any]) -> tuple[list[float], str, dict[str, Any]]:
    current_command = info.get("current_command")
    command_schedule = _serializable_sequence(info.get("command_schedule", ()))
    if isinstance(current_command, dict):
        return _command_vector(current_command), str(current_command.get("source", "current_command")), {
            "current_command": dict(current_command),
            "command_schedule": command_schedule,
        }
    if command_schedule:
        sim_time = float(info.get("sim_time") or 0.0)
        active = command_schedule[0]
        for command in command_schedule:
            if float(command.get("time", 0.0)) <= sim_time + 1e-12:
                active = command
            else:
                break
        return _command_vector(active), "scenario_schedule", {
            "current_command": dict(active) | {"source": "scenario_schedule"},
            "command_schedule": command_schedule,
        }
    return [0.0, 0.0, 0.0], "default_zero", {"command_schedule": []}
```

**Completed-run metadata pattern** (lines 282-309, 569-594):
```python
summary = latest_info.get("locomotion_metrics_summary")
if summary is None:
    summary = getattr(env, "last_locomotion_metrics_summary", None) or {}
success = summary.get("success") if isinstance(summary, dict) else None
if success is not True:
    had_locomotion_failure = True
episode_row = _episode_csv_row(cell, summary, commanded_velocity, command_source)
episode_row["summary"] = _jsonable(summary)
episode_rows.append(episode_row)
manifest_runs.append(
    _manifest_run_row(
        cell,
        reset_info,
        latest_info,
        commanded_velocity,
        command_source,
        command_context,
        success,
    )
)
```

```python
def _manifest_run_row(
    cell: dict[str, Any],
    reset_info: dict[str, Any],
    latest_info: dict[str, Any],
    commanded_velocity: list[float],
    command_source: str,
    command_context: dict[str, Any],
    success: Any,
) -> dict[str, Any]:
    return _jsonable(
        {
            **_base_row(cell),
            "spawn_pose": latest_info.get("spawn_pose", reset_info.get("spawn_pose")),
            "sampled_parameters": latest_info.get("sampled_parameters", reset_info.get("sampled_parameters", {})),
            "command_schedule": latest_info.get("command_schedule", reset_info.get("command_schedule", ())),
            "disturbance_schedule": latest_info.get("disturbance_schedule", reset_info.get("disturbance_schedule", ())),
            "controller_metadata": latest_info.get(
                "controller_metadata",
                reset_info.get("controller_metadata", {}),
            ),
            "commanded_velocity": commanded_velocity,
            "command_source": command_source,
            "command_context": command_context,
            "success": success,
        }
    )
```

**Artifact writer pattern** (lines 597-628, 645-660):
```python
def _build_manifest(
    matrix: EvaluationMatrix,
    run_config: EvaluationRunConfig,
    cells: tuple[dict[str, Any], ...],
    created_at: str,
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    git_info = _git_commit_info()
    manifest: dict[str, Any] = {
        "git_commit": git_info["git_commit"],
        "invocation_args": list(run_config.invocation_args),
        "matrix": _jsonable(
            {
                "controllers": matrix.controllers,
                "scenarios": matrix.scenarios,
                "seeds": matrix.seeds,
            }
        ),
        "environment_config": {
            "max_episode_steps": matrix.max_episode_steps,
            "sim_steps_per_frame": matrix.sim_steps_per_frame,
            "heightfield_size": matrix.heightfield_size,
        },
        "action_mode": matrix.action_mode,
        "created_at": created_at,
        "files": list(_ARTIFACT_FILES),
        "runs": runs,
        "validated_cells": _jsonable(cells),
    }
```

```python
def _write_artifacts(
    run_dir: Path,
    step_rows: list[dict[str, Any]],
    episode_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    _write_json(run_dir / "manifest.json", manifest)
    with (run_dir / "steps.jsonl").open("w", encoding="utf-8") as fp:
        for row in step_rows:
            fp.write(json.dumps(_jsonable(row), separators=(",", ":"), sort_keys=True) + "\n")
    with (run_dir / "episodes.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(_EPISODE_CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in episode_rows:
            writer.writerow({field: _csv_safe(row.get(field, "")) for field in _EPISODE_CSV_FIELDS})
    write_comparison_artifacts(run_dir, episode_rows, manifest)
```

**Planner guidance:** Add evaluator action-mode validation in `validate_evaluation_matrix()` before `run_dir = _prepare_run_dir(...)`. If non-default modes remain unsupported by the evaluator, reject `joint_position` and `residual_baseline` with actionable `ValueError`s there. If supporting them, route every `env.step()` through a helper that receives `cell["action_mode"]` and produces an action whose shape matches `build_action_space(mode)`.

---

### `src/main.py` (CLI/controller, request-response)

**Analog:** `src/main.py`

**Argparse subcommand pattern** (lines 89-149):
```python
def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Single-robot SLAM in MuJoCo")
    subparsers = parser.add_subparsers(dest="command")
    eval_parser = subparsers.add_parser(
        "eval-locomotion",
        help="Run offline locomotion controller/scenario/seed evaluations",
    )
    eval_parser.add_argument(
        "--controller",
        action="append",
        default=None,
        help="Controller id to evaluate; repeat for a matrix (default: analytical_trot)",
    )
    eval_parser.add_argument(
        "--scenario",
        action="append",
        default=None,
        help="Scenario id to evaluate; repeat for a matrix (default: flat_ground)",
    )
    eval_parser.add_argument(
        "--seed",
        action="append",
        type=int,
        default=None,
        help="Seed to evaluate; repeat for a matrix (default: 101, 202)",
    )
    eval_parser.add_argument(
        "--matrix-config",
        default=None,
        metavar="PATH",
        help="Optional JSON matrix config; repeated CLI flags override matrix dimensions",
    )
    eval_parser.add_argument(
        "--from-run-dir",
        default=None,
        metavar="PATH",
        help="Regenerate summary.json and comparison.md from a saved run directory",
    )
    eval_parser.add_argument(
        "--output-root",
        default="outputs/locomotion-evals",
        metavar="PATH",
        help="Directory for timestamped evaluation artifacts (default: outputs/locomotion-evals)",
    )
    eval_parser.add_argument("--max-episode-steps", type=int, default=500)
    eval_parser.add_argument("--sim-steps-per-frame", type=int, default=10)
    eval_parser.add_argument("--heightfield-size", type=int, default=16)
    eval_parser.add_argument("--action-mode", default="velocity_command")
```

**CLI-to-service assembly pattern** (lines 269-309):
```python
def run_eval_locomotion_mode(args: argparse.Namespace) -> int:
    """Run the dedicated locomotion evaluation CLI branch with lazy imports."""

    from src.locomotion.evaluation import (
        EvaluationMatrix,
        EvaluationRunConfig,
        load_matrix_config,
        regenerate_comparison,
        run_evaluation_matrix,
    )

    if getattr(args, "from_run_dir", None):
        run_dir = Path(args.from_run_dir)
        regenerate_comparison(run_dir)
        print(f"summary: {run_dir / 'summary.json'}")
        print(f"comparison: {run_dir / 'comparison.md'}")
        return 0

    if getattr(args, "matrix_config", None):
        matrix = load_matrix_config(Path(args.matrix_config))
    else:
        matrix = EvaluationMatrix()

    matrix = EvaluationMatrix(
        controllers=_defaulted_eval_sequence(args.controller, matrix.controllers),
        scenarios=_defaulted_eval_sequence(args.scenario, matrix.scenarios),
        seeds=_defaulted_eval_sequence(args.seed, matrix.seeds),
        action_mode=args.action_mode,
        max_episode_steps=args.max_episode_steps,
        sim_steps_per_frame=args.sim_steps_per_frame,
        heightfield_size=args.heightfield_size,
    )
    config = EvaluationRunConfig(
        output_root=Path(args.output_root),
        max_matrix_runs=args.max_matrix_runs,
        fail_on_locomotion_failure=not args.allow_locomotion_failures,
        verbose=args.verbose,
        invocation_args=tuple(sys.argv[1:]),
    )
    result = run_evaluation_matrix(matrix, config=config)
```

**Planner guidance:** Keep lazy imports inside `run_eval_locomotion_mode()`. Update `--action-mode` help in `parse_args()` so help text names the implemented evaluator contract, not just env support. Do not add heavy imports at module import time.

---

### `docs/locomotion-benchmark.md` (documentation, transform)

**Analog:** `docs/locomotion-benchmark.md`

**Smoke command pattern** (lines 9-18):
```markdown
## First smoke benchmark

Run the flat-ground analytical baseline with explicit controller, scenario, and seed flags:

```bash
uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

The command evaluates the supported `analytical_trot` controller in the `flat_ground` scenario for seeds `101` and `202`, then writes a timestamped run directory under `outputs/locomotion-evals/<timestamp>/`.
```

**Action-mode table pattern to update** (lines 37-44):
```markdown
The supported action modes are:

| Action mode | Use |
|-------------|-----|
| `velocity_command` | Three-value planar velocity command routed through the selected controller. This is the default benchmark mode for `analytical_trot`. |
| `joint_position` | Twelve direct joint-position targets for controller families that own joint target generation. |
| `residual_baseline` | Twelve residuals applied over the analytical baseline seam for future residual-policy work. |
```

**Matrix config pattern** (lines 68-88):
```markdown
## Matrix config workflow

For larger comparisons, put the matrix in JSON and pass it to the same CLI:

```json
{
  "controllers": ["analytical_trot"],
  "scenarios": ["flat_ground"],
  "seeds": [101, 202],
  "action_mode": "velocity_command",
  "max_episode_steps": 500,
  "sim_steps_per_frame": 10,
  "heightfield_size": 16
}
```

```bash
uv run argus eval-locomotion --matrix-config path/to/matrix.json
```

Repeated CLI flags can still be used for quick runs; use JSON when the matrix needs to be saved, reviewed, or regenerated.
```

**Controller boundary pattern** (lines 112-123):
```markdown
## Controller-family boundary matrix

The matrix is intentionally hard-edged. If a family is unavailable or deferred, do not describe it as supported just because there is a seam. v4.0 does not ship trained RL policies, MPC, WBC, ROS/hardware behavior, torque-control locomotion, or perception-conditioned locomotion.

| Controller family | Status now | Argus hook/seam | Why supported/deferred | Prerequisite to unlock | R&D rationale link |
|-------------------|------------|-----------------|------------------------|------------------------|--------------------|
| analytical gait | supported now | Controller id `analytical_trot`; `argus eval-locomotion`; default `velocity_command` action mode | Existing deterministic Raibert-style analytical trot produces Go2 joint-position targets through MuJoCo position actuators. | Keep regression and metrics gates green before changing baseline behavior. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
| residual RL | registered placeholder unavailable | Controller id `residual_policy`; residual-over-baseline seam via `residual_baseline` action mode | Placeholder exists so the benchmark boundary is stable, but no trained residual policy artifact ships in v4.0. | Train/evaluate residual policy artifacts and define promotion criteria against the analytical baseline. | `outputs/locomotion-rd-systems.md`; `docs/adr/0019-benchmark-locomotion-before-adding-new-controller-families.md` |
```

**Planner guidance:** Document env action modes separately from evaluator-runnable modes. If Phase 7 rejects non-default evaluator modes, say that the env supports `joint_position`/`residual_baseline` seams but `argus eval-locomotion` currently fails fast for them until explicit policy/action sources exist.

---

### `tests/locomotion/test_locomotion_evaluation_runner.py` (test, request-response)

**Analog:** `tests/locomotion/test_locomotion_evaluation_runner.py`

**Imports and fake env pattern** (lines 1-15, 18-49):
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
    def __init__(self, config, calls, *, success=True, transition_commands=False) -> None:
        self.config = config
        self.calls = calls
        self.success = success
        self.transition_commands = transition_commands
        self.calls.append(("construct", config))
        self._step_count = 0

    def reset(self, *, seed=None):
        self.calls.append(("reset", seed))
```

**Pre-env-construction rejection pattern** (lines 125-167):
```python
def test_unknown_controller_fails_before_env_construction(tmp_path):
    calls = []
    matrix = EvaluationMatrix(controllers=("missing_controller",), scenarios=("flat_ground",), seeds=(101,))

    with pytest.raises(ValueError, match="Unknown locomotion controller"):
        run_evaluation_matrix(
            matrix,
            EvaluationRunConfig(output_root=tmp_path),
            env_factory=_fake_env_factory(calls),
        )

    assert calls == []  # T-04-01: invalid controllers fail before env constructor.
    assert not any(tmp_path.iterdir())


def test_unavailable_placeholder_controller_fails_before_env_construction(tmp_path):
    calls = []
    matrix = EvaluationMatrix(controllers=("residual_policy",), scenarios=("flat_ground",), seeds=(101,))

    with pytest.raises(UnavailableControllerError, match="Controller 'residual_policy' is unavailable"):
        run_evaluation_matrix(
            matrix,
            EvaluationRunConfig(output_root=tmp_path),
            env_factory=_fake_env_factory(calls),
        )

    assert calls == []  # D-04: placeholder controllers fail before simulation.
    assert not any(tmp_path.iterdir())
```

**Executed-command row semantics pattern** (lines 268-293):
```python
def test_runner_records_each_step_commanded_velocity_from_executed_action(tmp_path):
    calls = []
    result = run_evaluation_matrix(
        EvaluationMatrix(
            controllers=("analytical_trot",),
            scenarios=("flat_ground",),
            seeds=(101,),
            action_mode="velocity_command",
            max_episode_steps=5,
        ),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_fake_env_factory(calls, transition_commands=True),
    )

    captured_actions = [call[1] for call in calls if call[0] == "step"]
    assert captured_actions == [[0.0, 0.0, 0.0], [0.4, 0.0, 0.0]]
    assert len(result.step_rows) == 2

    row0 = result.step_rows[0]
    assert row0["commanded_velocity"] == [0.0, 0.0, 0.0]
    assert row0["command_source"] == "scenario_schedule"
    assert row0["command_context"]["command_schedule"][0]["vx"] == 0.0

    row1 = result.step_rows[1]
    assert row1["commanded_velocity"] == [0.4, 0.0, 0.0]
    assert row1["command_context"]["current_command"]["vx"] == 0.4
```

**Planner guidance:** Add tests here for unknown action mode and any unsupported evaluator modes. Follow the existing pre-side-effect assertion shape: `calls == []` and `not any(tmp_path.iterdir())`. If `joint_position` or `residual_baseline` are supported instead of rejected, extend the fake env to assert the action shape passed to `step()`.

---

### `tests/locomotion/test_locomotion_evaluation_exports.py` (test, file-I/O)

**Analog:** `tests/locomotion/test_locomotion_evaluation_exports.py`

**Artifact inventory pattern** (lines 21-44, 104-111):
```python
_ARTIFACT_NAMES = {"manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md"}

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

```python
def _single_cell_matrix() -> EvaluationMatrix:
    return EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=(101,),
        action_mode="velocity_command",
        max_episode_steps=2,
    )
```

**Manifest metadata assertions pattern** (lines 118-144):
```python
def test_run_writes_self_contained_locomotion_eval_artifacts(tmp_path):
    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_factory(),
    )

    assert result.exit_code == 0
    assert result.run_dir.parent == tmp_path
    assert {path.name for path in result.run_dir.iterdir()} == _ARTIFACT_NAMES  # D-05 / T-04-02.

    manifest = _read_json(result.run_dir / "manifest.json")
    # LOC-EVAL-03 / D-08 / T-04-03: reproducibility metadata is top-level manifest data.
    assert set(manifest) >= {
        "git_commit",
        "invocation_args",
        "matrix",
        "environment_config",
        "action_mode",
        "created_at",
        "files",
        "runs",
    }
    assert set(manifest["files"]) == _ARTIFACT_NAMES
    assert manifest["runs"][0]["commanded_velocity"] == [0.4, 0.0, 0.0]
    assert manifest["runs"][0]["command_source"] == "scenario_schedule"
```

**Failed episode still writes artifacts pattern** (lines 212-225):
```python
def test_failed_episode_still_writes_all_artifacts_before_nonzero_exit(tmp_path):
    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path, fail_on_locomotion_failure=True),
        env_factory=_factory(success=False, failure_reason="fell"),
    )

    assert result.exit_code == 1  # D-16: nonzero after artifacts are persisted.
    assert result.had_locomotion_failure is True
    assert {path.name for path in result.run_dir.iterdir()} == _ARTIFACT_NAMES  # D-05 / T-04-03.
    with (result.run_dir / "episodes.csv").open(newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert rows[0]["success"] == "False"
    assert rows[0]["failure_reason"] == "fell"
```

**Planner guidance:** Add export assertions that completed `velocity_command` runs record `action_mode` consistently at top-level manifest, validated cells, run rows, step rows, and episode CSV. Add a preflight rejection test that proves no artifact directory exists for rejected action modes.

---

### `tests/test_main_args.py` (test, request-response)

**Analog:** `tests/test_main_args.py`

**Parser flag test pattern** (lines 206-233):
```python
def test_eval_locomotion_parser_accepts_repeatable_matrix_flags(monkeypatch):
    """LOC-EVAL-01 D-01 D-02: eval-locomotion is a dedicated CLI subcommand."""
    import src.main as main_module

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "argus",
            "eval-locomotion",
            "--controller",
            "analytical_trot",
            "--scenario",
            "flat_ground",
            "--seed",
            "101",
            "--seed",
            "202",
        ],
    )

    args = main_module.parse_args()

    assert args.command == "eval-locomotion"
    assert args.controller == ["analytical_trot"]
    assert args.scenario == ["flat_ground"]
    assert args.seed == [101, 202]
```

**Help subprocess pattern** (lines 235-263):
```python
def test_eval_locomotion_help_lists_artifact_flags():
    """LOC-EVAL-01 D-01 D-02 D-03: help is quiet and artifact-focused."""
    proc = subprocess.run(
        [
            "/home/prannayag/pragnition/robotics/argus/.venv/bin/python",
            "-m",
            "src.main",
            "eval-locomotion",
            "--help",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, combined
    for expected in (
        "eval-locomotion",
        "--controller",
        "--scenario",
        "--seed",
        "--matrix-config",
        "--from-run-dir",
        "--output-root",
        "--verbose",
    ):
        assert expected in combined
```

**Planner guidance:** Extend the help test to require `--action-mode` and the same runnable/deferred wording chosen for docs. Keep subprocess style for real argparse help behavior.

---

### `tests/test_locomotion_benchmark_docs.py` (test, file-I/O)

**Analog:** `tests/test_locomotion_benchmark_docs.py`

**Content guard constants pattern** (lines 7-20):
```python
ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "locomotion-benchmark.md"
SMOKE_COMMAND = "uv run argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202"
ARTIFACTS = ("manifest.json", "steps.jsonl", "episodes.csv", "summary.json", "comparison.md")
FAMILIES = (
    "analytical gait",
    "residual RL",
    "direct RL",
    "MPC",
    "WBC",
    "ROS/hardware",
    "perception-conditioned locomotion",
)
```

**Guide required content pattern** (lines 32-56):
```python
def test_locomotion_benchmark_guide_required_content():
    guide = GUIDE.read_text(encoding="utf-8")
    guide_lower = guide.lower()

    assert SMOKE_COMMAND in guide
    assert "--matrix-config" in guide
    assert "--from-run-dir" in guide
    for token in ("qpos", "qvel", "command", "previous_action"):
        assert token in guide
    for mode in ("velocity_command", "joint_position", "residual_baseline"):
        assert mode in guide
    for scenario in ("flat_ground", "low_friction", "slope", "rough_heightfield", "push_disturbance"):
        assert scenario in guide
    for artifact in ARTIFACTS:
        assert artifact in guide
    for metric_token in (
        "command tracking",
        "stability",
        "action quality",
        "contact/terrain proxies",
        "reward `0.0`",
        "position-servo",
    ):
        assert metric_token in guide_lower
```

**Controller/action-mode drift guard pattern** (lines 91-106):
```python
def test_residual_policy_documentation_matches_registry_action_mode():
    from src.locomotion.actions import available_action_modes
    from src.locomotion.controllers import ControllerRegistry

    guide = GUIDE.read_text(encoding="utf-8")
    entries = {entry["name"]: entry for entry in ControllerRegistry.list_controllers()}
    residual = entries["residual_policy"]
    action_mode = residual["capabilities"]["action_mode"]

    assert residual["available"] is False
    assert action_mode == "residual_baseline"
    assert action_mode in available_action_modes()
    assert (
        f"Controller id `residual_policy`; residual-over-baseline seam via `{action_mode}` action mode"
        in guide
    )
```

**Planner guidance:** Add a guard that docs state the same evaluator action-mode contract asserted by `tests/test_main_args.py`. Keep this file content-only; preserve the existing `test_doc_guard_source_stays_content_only()` constraint.

---

## Shared Patterns

### Authoritative action-mode source
**Source:** `src/locomotion/actions.py` lines 12-17, 54-64, 71-87
**Apply to:** `src/locomotion/evaluation.py`, `src/main.py`, docs/tests that mention action mode names
```python
ACTION_MODE_VELOCITY = "velocity_command"
ACTION_MODE_JOINT_POSITION = "joint_position"
ACTION_MODE_RESIDUAL_BASELINE = "residual_baseline"

_ACTION_MODES: Final[tuple[str, ...]] = (
    ACTION_MODE_JOINT_POSITION,
    ACTION_MODE_RESIDUAL_BASELINE,
    ACTION_MODE_VELOCITY,
)


def available_action_modes() -> list[str]:
    """Return sorted action mode names supported by the benchmark wrapper."""
    return sorted(_ACTION_MODES)
```

```python
def build_action_space(mode: str) -> spaces.Box:
    """Build the Gymnasium action space for an action mode.

    Args:
        mode: One of ``velocity_command``, ``joint_position``, or
            ``residual_baseline``.

    Raises:
        ValueError: If *mode* is not registered.
    """
    if mode == ACTION_MODE_VELOCITY:
        return spaces.Box(low=_VELOCITY_LOW.copy(), high=_VELOCITY_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_JOINT_POSITION:
        return spaces.Box(low=_JOINT_LOW.copy(), high=_JOINT_HIGH.copy(), dtype=np.float32)
    if mode == ACTION_MODE_RESIDUAL_BASELINE:
        return spaces.Box(low=_RESIDUAL_LOW.copy(), high=_RESIDUAL_HIGH.copy(), dtype=np.float32)
    raise _unknown_mode_error(mode)
```

### Environment enforces action shape before state mutation
**Source:** `src/locomotion/env.py` lines 114-150, 211-221
**Apply to:** evaluator action builder tests and validation strategy
```python
def step(
    self,
    action: np.ndarray,
) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
    """Apply a mode-specific action and return the Gymnasium five-tuple."""
    previous_action = self._previous_action.copy()
    previous_previous_action = self._previous_previous_action.copy()
    pose_before = self._base_pose_snapshot()
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
```

```python
def _validate_velocity_action(self, action: np.ndarray) -> np.ndarray:
    vector = np.asarray(action, dtype=np.float32)
    if vector.shape != (3,):
        raise ValueError(f"Velocity command action must have shape (3,), got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError("Velocity command action values must be finite")
    low = self.action_space.low.astype(np.float32)
    high = self.action_space.high.astype(np.float32)
    if np.any(vector < low) or np.any(vector > high):
        raise ValueError("Velocity command action values must be within the action space bounds")
    return vector.copy()
```

### Controller availability and deferred placeholder pattern
**Source:** `src/locomotion/controllers.py` lines 54-69, 467-488
**Apply to:** evaluator action-mode capability validation and docs wording
```python
RESIDUAL_POLICY_UNAVAILABLE_REASON = (
    "Residual policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
DIRECT_POLICY_UNAVAILABLE_REASON = (
    "Direct policy controllers require trained policy artifacts and are deferred "
    "until a future RL milestone."
)
MPC_UNAVAILABLE_REASON = (
    "MPC controllers require dynamics/contact solver infrastructure and are deferred "
    "until a future model-based-control milestone."
)
WBC_UNAVAILABLE_REASON = (
    "WBC controllers require torque/whole-body-control infrastructure and are deferred "
    "until a future model-based-control milestone."
)
```

```python
@locomotion_controller(name="residual_policy", display="Residual Policy")
class ResidualPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("residual_policy", "residual_baseline")
    UNAVAILABLE_REASON = RESIDUAL_POLICY_UNAVAILABLE_REASON


@locomotion_controller(name="direct_policy", display="Direct Policy")
class DirectPolicyController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("direct_policy", "joint_position")
    UNAVAILABLE_REASON = DIRECT_POLICY_UNAVAILABLE_REASON


@locomotion_controller(name="mpc", display="Model Predictive Control")
class MPCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("mpc", "joint_position")
    UNAVAILABLE_REASON = MPC_UNAVAILABLE_REASON


@locomotion_controller(name="wbc", display="Whole-Body Control")
class WBCController(_UnavailableControllerBase):
    CAPABILITIES = _placeholder_capabilities("wbc", "torque_or_joint_position")
    UNAVAILABLE_REASON = WBC_UNAVAILABLE_REASON
```

### JSON/CSV safety and reproducibility metadata
**Source:** `src/locomotion/evaluation.py` lines 631-642, 663-670, 800-809
**Apply to:** any artifact metadata field added for action-mode contract
```python
def _git_commit_info() -> dict[str, str | None]:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 - manifest records unavailable git metadata.
        return {"git_commit": None, "git_commit_error": str(exc)}
    return {"git_commit": proc.stdout.strip(), "git_commit_error": None}
```

```python
def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
```

```python
def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    return value
```

## No Analog Found

No files are without a close analog. This is a gap-closure phase modifying existing evaluation, CLI, docs, and test surfaces.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| — | — | — | All planned files have exact in-place analogs. |

## Metadata

**Analog search scope:** `/home/prannayag/pragnition/robotics/argus/src`, `/home/prannayag/pragnition/robotics/argus/tests`, `/home/prannayag/pragnition/robotics/argus/docs`
**Files scanned:** source/test/doc inventory plus 11 focused files read
**Pattern extraction date:** 2026-05-01
