"""Evaluation matrix contracts and runner loop for locomotion benchmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np

from src.locomotion.controllers import ControllerRegistry, UnavailableControllerError
from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig
from src.locomotion.scenarios import list_scenarios

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


@dataclass(frozen=True)
class EvaluationMatrix:
    controllers: tuple[str, ...] = ("analytical_trot",)
    scenarios: tuple[str, ...] = ("flat_ground",)
    seeds: tuple[int, ...] = (101, 202)
    action_mode: str = "velocity_command"
    max_episode_steps: int = 500
    sim_steps_per_frame: int = 10
    heightfield_size: int = 16


@dataclass(frozen=True)
class EvaluationRunConfig:
    output_root: Path = Path("outputs/locomotion-evals")
    max_matrix_runs: int = 1000
    fail_on_locomotion_failure: bool = True
    verbose: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    run_dir: Path
    step_rows: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    episode_rows: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    had_locomotion_failure: bool = False
    exit_code: int = 0


def load_matrix_config(path: Path) -> EvaluationMatrix:
    """Load an evaluation matrix JSON config using the plan's strict schema."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Matrix config must be a JSON object")
    unknown_keys = sorted(set(payload) - _ALLOWED_MATRIX_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"Unknown matrix config keys: {unknown_keys}")

    controllers = _tuple_of_str(payload.get("controllers", EvaluationMatrix.controllers), "controllers")
    scenarios = _tuple_of_str(payload.get("scenarios", EvaluationMatrix.scenarios), "scenarios")
    seeds = _tuple_of_int(payload.get("seeds", EvaluationMatrix.seeds), "seeds")
    action_mode = payload.get("action_mode", EvaluationMatrix.action_mode)
    if not isinstance(action_mode, str) or not action_mode:
        raise ValueError("action_mode must be a non-empty string")
    return EvaluationMatrix(
        controllers=controllers,
        scenarios=scenarios,
        seeds=seeds,
        action_mode=action_mode,
        max_episode_steps=_positive_int(
            payload.get("max_episode_steps", EvaluationMatrix.max_episode_steps),
            "max_episode_steps",
        ),
        sim_steps_per_frame=_positive_int(
            payload.get("sim_steps_per_frame", EvaluationMatrix.sim_steps_per_frame),
            "sim_steps_per_frame",
        ),
        heightfield_size=_positive_int(
            payload.get("heightfield_size", EvaluationMatrix.heightfield_size),
            "heightfield_size",
        ),
    )


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

    cells: list[dict[str, Any]] = []
    run_index = 1
    for controller_id in controllers:
        for scenario_id in scenarios:
            for seed in seeds:
                cells.append(
                    {
                        "run_id": f"r{run_index:04d}",
                        "controller_id": controller_id,
                        "scenario_id": scenario_id,
                        "seed": seed,
                        "action_mode": action_mode,
                        "max_episode_steps": max_episode_steps,
                        "sim_steps_per_frame": sim_steps_per_frame,
                        "heightfield_size": heightfield_size,
                    }
                )
                run_index += 1
    return tuple(cells)


def run_evaluation_matrix(
    matrix: EvaluationMatrix,
    config: EvaluationRunConfig | None = None,
    *,
    env_factory: Callable[[ArgusGo2EnvConfig], Any] = ArgusGo2Env,
) -> EvaluationResult:
    """Run an evaluation matrix with validation before artifacts or env construction."""

    run_config = config or EvaluationRunConfig()
    cells = validate_evaluation_matrix(matrix, max_matrix_runs=run_config.max_matrix_runs)
    run_dir = _prepare_run_dir(run_config.output_root)
    step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    had_locomotion_failure = False

    for cell in cells:
        env = env_factory(
            ArgusGo2EnvConfig(
                scenario_id=cell["scenario_id"],
                action_mode=cell["action_mode"],
                controller_id=cell["controller_id"],
                sim_steps_per_frame=cell["sim_steps_per_frame"],
                max_episode_steps=cell["max_episode_steps"],
                heightfield_size=cell["heightfield_size"],
            )
        )
        reset_info: dict[str, Any] = {}
        try:
            _observation, reset_info = env.reset(seed=cell["seed"])
            terminated = False
            truncated = False
            latest_info = dict(reset_info)
            while not (terminated or truncated):
                action, source, command_context = _action_from_command_context(latest_info)
                _observation, _reward, terminated, truncated, info = env.step(
                    np.asarray(action, dtype=np.float32)
                )
                latest_info = dict(info)
                commanded_velocity, command_source, merged_context = _command_fields(
                    latest_info,
                    reset_info,
                    default_action=action,
                    default_source=source,
                    default_context=command_context,
                )
                row = _base_row(cell)
                row.update(
                    {
                        "step_count": latest_info.get("step_count"),
                        "sim_time": latest_info.get("sim_time"),
                        "commanded_velocity": commanded_velocity,
                        "command_source": command_source,
                        "command_context": merged_context,
                        "locomotion_metrics": latest_info.get("locomotion_metrics", {}),
                    }
                )
                step_rows.append(row)
            summary = latest_info.get("locomotion_metrics_summary")
            if summary is None:
                summary = getattr(env, "last_locomotion_metrics_summary", None) or {}
            success = summary.get("success") if isinstance(summary, dict) else None
            if success is False:
                had_locomotion_failure = True
            episode_row = _base_row(cell)
            episode_row.update(
                {
                    "summary": summary,
                    "success": success,
                    "failure_reason": summary.get("failure_reason") if isinstance(summary, dict) else None,
                }
            )
            episode_rows.append(episode_row)
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()

    _write_noop_artifacts(run_dir, step_rows, episode_rows)
    exit_code = 1 if had_locomotion_failure and run_config.fail_on_locomotion_failure else 0
    return EvaluationResult(
        run_dir=run_dir,
        step_rows=tuple(step_rows),
        episode_rows=tuple(episode_rows),
        had_locomotion_failure=had_locomotion_failure,
        exit_code=exit_code,
    )


def _tuple_of_str(value: Any, name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple of strings")
    result = tuple(value)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if not all(isinstance(item, str) and item for item in result):
        raise ValueError(f"{name} must contain non-empty strings")
    return result


def _tuple_of_int(value: Any, name: str) -> tuple[int, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be a list or tuple of integers")
    result = tuple(value)
    if not result:
        raise ValueError(f"{name} must not be empty")
    if not all(type(item) is int for item in result):
        raise ValueError(f"{name} must contain integers")
    return result


def _validate_seed_values(seeds: tuple[int, ...]) -> None:
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")
    for seed in seeds:
        if seed < 0 or seed > _MAX_SEED:
            raise ValueError(f"seed must be between 0 and {_MAX_SEED}")


def _positive_int(value: Any, name: str) -> int:
    if type(value) is not int or not math.isfinite(float(value)) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _prepare_run_dir(output_root: Path) -> Path:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _base_row(cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": cell["run_id"],
        "controller_id": cell["controller_id"],
        "scenario_id": cell["scenario_id"],
        "seed": cell["seed"],
        "action_mode": cell["action_mode"],
    }


def _action_from_command_context(info: dict[str, Any]) -> tuple[list[float], str, dict[str, Any]]:
    command_schedule = _serializable_sequence(info.get("command_schedule", ()))
    if command_schedule:
        first = command_schedule[0]
        return _command_vector(first), "scenario_schedule", {"command_schedule": command_schedule}
    current_command = info.get("current_command")
    if isinstance(current_command, dict):
        return _command_vector(current_command), str(current_command.get("source", "current_command")), {
            "current_command": dict(current_command)
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

    schedule = _serializable_sequence(info.get("command_schedule", reset_info.get("command_schedule", ())))
    if schedule:
        context = dict(default_context)
        context["command_schedule"] = schedule
        return _command_vector(schedule[0]), "scenario_schedule", context
    return list(default_action), default_source, dict(default_context)


def _command_vector(command: dict[str, Any]) -> list[float]:
    return [
        float(command.get("vx", 0.0)),
        float(command.get("vy", 0.0)),
        float(command.get("omega", command.get("yaw_rate", 0.0))),
    ]


def _serializable_sequence(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, tuple):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _write_noop_artifacts(
    run_dir: Path,
    step_rows: list[dict[str, Any]],
    episode_rows: list[dict[str, Any]],
) -> None:
    """Private no-op hook reserved for Plan 02 artifact writers."""

    del run_dir, step_rows, episode_rows
