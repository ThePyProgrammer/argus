"""Evaluation matrix contracts, artifact exports, and comparison generation."""

from __future__ import annotations

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
    "base_height_min_m",
    "base_height_max_deviation_m",
    "roll_abs_max_rad",
    "pitch_abs_max_rad",
    "action_smoothness_mean",
    "position_servo_effort_mean",
    "joint_limit_violation_count",
    "actuator_saturation_count",
    "foot_slip_mean",
    "foot_clearance_mean",
    "duty_factor_mean",
)
_SCORECARD_METRICS = (
    "success_rate",
    "failure_count",
    "tracking_rmse",
    "distance_xy_m",
    "base_height_min_m",
    "action_smoothness_mean",
    "position_servo_effort_mean",
    "foot_slip_mean",
)
METRIC_DIRECTIONS = {
    "success_rate": "success_rate ↑",
    "tracking_rmse": "tracking_rmse ↓",
    "distance_xy_m": "distance_xy_m ↑",
    "action_smoothness_mean": "action_smoothness_mean ↓",
    "position_servo_effort_mean": "position_servo_effort_mean ↓",
    "foot_slip_mean": "foot_slip_mean ↓",
}
_FORMULA_PREFIXES = ("=", "+", "-", "@")


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
    invocation_args: tuple[str, ...] = ()


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
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_dir = _prepare_run_dir(run_config.output_root)
    step_rows: list[dict[str, Any]] = []
    episode_rows: list[dict[str, Any]] = []
    manifest_runs: list[dict[str, Any]] = []
    had_locomotion_failure = False

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
                row = _base_row(cell)
                row.update(
                    {
                        "step_count": latest_info.get("step_count"),
                        "sim_time": latest_info.get("sim_time"),
                        "commanded_velocity": commanded_velocity,
                        "command_source": command_source,
                        "command_schedule": command_context.get("command_schedule", []),
                        "command_context": command_context,
                        "locomotion_metrics": latest_info.get("locomotion_metrics", {}),
                    }
                )
                step_rows.append(_jsonable(row))
            summary = latest_info.get("locomotion_metrics_summary")
            if summary is None:
                summary = getattr(env, "last_locomotion_metrics_summary", None) or {}
            success = summary.get("success") if isinstance(summary, dict) else None
            if success is False:
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
        finally:
            close = getattr(env, "close", None)
            if callable(close):
                close()

    manifest = _build_manifest(matrix, run_config, cells, created_at, manifest_runs)
    _write_artifacts(run_dir, step_rows, episode_rows, manifest)
    exit_code = 1 if had_locomotion_failure and run_config.fail_on_locomotion_failure else 0
    return EvaluationResult(
        run_dir=run_dir,
        step_rows=tuple(step_rows),
        episode_rows=tuple(episode_rows),
        had_locomotion_failure=had_locomotion_failure,
        exit_code=exit_code,
    )


def aggregate_episode_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate flattened episode rows by controller and controller/scenario."""

    materialized = [_coerce_episode_row(row) for row in rows]
    return {
        "metric_directions": dict(METRIC_DIRECTIONS),
        "overall_by_controller": _aggregate_groups(materialized, ("controller_id",)),
        "by_controller_and_scenario": _aggregate_groups(materialized, ("controller_id", "scenario_id")),
    }


def write_comparison_artifacts(
    run_dir: Path,
    rows: Iterable[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Write summary.json and comparison.md for saved episode rows."""

    run_path = Path(run_dir)
    episode_rows = list(rows)
    aggregates = aggregate_episode_rows(episode_rows)
    summary = {
        "run_dir": str(run_path),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "manifest_created_at": manifest.get("created_at"),
        "run_count": len(episode_rows),
        **aggregates,
    }
    _write_json(run_path / "summary.json", summary)
    (run_path / "comparison.md").write_text(_comparison_markdown(summary), encoding="utf-8")
    return summary


def regenerate_comparison(run_dir: Path) -> dict[str, Any]:
    """Regenerate summary and Markdown comparison from saved artifacts only."""

    run_path = Path(run_dir)
    manifest = json.loads((run_path / "manifest.json").read_text(encoding="utf-8"))
    rows = _read_episode_csv(run_path / "episodes.csv")
    return write_comparison_artifacts(run_path, rows, manifest)


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
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in [""] + [f"-{idx:02d}" for idx in range(1, 1000)]:
        candidate = (root / f"{timestamp}{suffix}").resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError(f"Run directory escapes output root: {candidate}")
        try:
            candidate.mkdir()
        except FileExistsError:
            continue
        return candidate
    raise FileExistsError(f"Could not create unique evaluation run directory under {root}")


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
        return [_jsonable(dict(item)) for item in value if isinstance(item, dict)]
    if isinstance(value, list):
        return [_jsonable(dict(item)) for item in value if isinstance(item, dict)]
    return []


def _episode_csv_row(
    cell: dict[str, Any],
    summary: Any,
    commanded_velocity: list[float],
    command_source: str,
) -> dict[str, Any]:
    payload = summary if isinstance(summary, dict) else {}
    command_tracking = payload.get("command_tracking", {}) if isinstance(payload.get("command_tracking", {}), dict) else {}
    stability = payload.get("stability", {}) if isinstance(payload.get("stability", {}), dict) else {}
    action_quality = payload.get("action_quality", {}) if isinstance(payload.get("action_quality", {}), dict) else {}
    contact_terrain = payload.get("contact_terrain", {}) if isinstance(payload.get("contact_terrain", {}), dict) else {}
    row = _base_row(cell)
    row.update(
        {
            "commanded_velocity": _compact_json(commanded_velocity),
            "command_source": command_source,
            "success": bool(payload.get("success", False)),
            "failure_reason": payload.get("failure_reason") or "",
            "step_count": _metric_value(payload, "step_count", default=0.0),
            "tracking_rmse": _metric_value(command_tracking, "tracking_error_rmse", default=0.0),
            "distance_xy_m": _metric_value(command_tracking, "distance_xy_m", default=0.0),
            "base_height_min_m": _metric_alias(stability, "base_height_min_m", "min_base_height_m"),
            "base_height_max_deviation_m": _metric_alias(
                stability,
                "base_height_max_deviation_m",
                "max_base_height_deviation_m",
            ),
            "roll_abs_max_rad": _metric_alias(stability, "roll_abs_max_rad", "max_abs_roll_rad"),
            "pitch_abs_max_rad": _metric_alias(stability, "pitch_abs_max_rad", "max_abs_pitch_rad"),
            "action_smoothness_mean": _metric_alias(
                action_quality,
                "action_smoothness_mean",
                "action_delta_norm_mean",
            ),
            "position_servo_effort_mean": _metric_alias(
                action_quality,
                "position_servo_effort_mean",
                "position_servo_effort_proxy_mean",
            ),
            "joint_limit_violation_count": _metric_alias(
                action_quality,
                "joint_limit_violation_count",
                "commanded_joint_limit_violation_count_total",
            ),
            "actuator_saturation_count": _metric_alias(
                action_quality,
                "actuator_saturation_count",
                "position_target_saturation_proxy_total",
            ),
            "foot_slip_mean": _contact_metric_mean(contact_terrain, "foot_slip_mean", "slip_mean_m_per_s"),
            "foot_clearance_mean": _contact_metric_mean(contact_terrain, "foot_clearance_mean", "clearance_min_m"),
            "duty_factor_mean": _contact_metric_mean(contact_terrain, "duty_factor_mean", "duty_factor"),
        }
    )
    return row


def _metric_value(mapping: dict[str, Any], key: str, *, default: float) -> Any:
    value = mapping.get(key, default)
    if value is None:
        return default
    return _jsonable(value)


def _metric_alias(mapping: dict[str, Any], *keys: str, default: float = 0.0) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return _jsonable(mapping[key])
    return default


def _contact_metric_mean(mapping: dict[str, Any], *keys: str, default: float = 0.0) -> Any:
    value = _metric_alias(mapping, *keys, default=default)
    if isinstance(value, dict):
        numeric_values = [float(item) for item in value.values() if item is not None]
        return sum(numeric_values) / len(numeric_values) if numeric_values else default
    return value


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
    if git_info.get("git_commit_error"):
        manifest["git_commit_error"] = git_info["git_commit_error"]
    return manifest


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _read_episode_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def _coerce_episode_row(row: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(row)
    coerced["success"] = _to_bool(coerced.get("success"))
    for field in _EPISODE_CSV_FIELDS:
        if field in {"run_id", "controller_id", "scenario_id", "action_mode", "commanded_velocity", "command_source", "failure_reason", "success"}:
            continue
        coerced[field] = _to_float(coerced.get(field))
    return coerced


def _aggregate_groups(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row.get(key) for key in keys), []).append(row)
    aggregates: list[dict[str, Any]] = []
    for group_key in sorted(grouped):
        group_rows = grouped[group_key]
        item = {key: value for key, value in zip(keys, group_key)}
        successes = [bool(row.get("success")) for row in group_rows]
        item["episode_count"] = len(group_rows)
        item["success_rate"] = sum(1 for success in successes if success) / len(successes) if successes else 0.0
        item["failure_count"] = sum(1 for success in successes if not success)
        for metric in (
            "tracking_rmse",
            "distance_xy_m",
            "base_height_min_m",
            "action_smoothness_mean",
            "position_servo_effort_mean",
            "foot_slip_mean",
        ):
            values = [_to_float(row.get(metric)) for row in group_rows]
            item[f"{metric}_mean"] = _mean(values)
            item[f"{metric}_std"] = _std(values)
        aggregates.append(item)
    return aggregates


def _comparison_markdown(summary: dict[str, Any]) -> str:
    directions = summary["metric_directions"]
    lines = [
        "# Locomotion Evaluation Comparison",
        "",
        f"Run count: {summary['run_count']}",
        "",
        "## Overall by Controller",
        "",
    ]
    lines.extend(_markdown_table(summary["overall_by_controller"], ("controller_id",), directions))
    lines.extend(["", "## By Controller and Scenario", ""])
    lines.extend(_markdown_table(summary["by_controller_and_scenario"], ("controller_id", "scenario_id"), directions))
    return "\n".join(lines) + "\n"


def _markdown_table(rows: list[dict[str, Any]], key_fields: tuple[str, ...], directions: dict[str, str]) -> list[str]:
    headers = [
        *key_fields,
        "episodes",
        directions["success_rate"],
        "failure_count",
        directions["tracking_rmse"],
        directions["distance_xy_m"],
        "base_height_min_m",
        directions["action_smoothness_mean"],
        directions["position_servo_effort_mean"],
        directions["foot_slip_mean"],
    ]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        values = [str(row.get(field, "")) for field in key_fields]
        values.extend(
            [
                str(row.get("episode_count", 0)),
                _fmt(row.get("success_rate")),
                str(row.get("failure_count", 0)),
                _fmt(row.get("tracking_rmse_mean")),
                _fmt(row.get("distance_xy_m_mean")),
                _fmt(row.get("base_height_min_m_mean")),
                _fmt(row.get("action_smoothness_mean_mean")),
                _fmt(row.get("position_servo_effort_mean_mean")),
                _fmt(row.get("foot_slip_mean_mean")),
            ]
        )
        lines.append("| " + " | ".join(values) + " |")
    return lines


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = _mean(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _fmt(value: Any) -> str:
    return f"{_to_float(value):.6g}"


def _compact_json(value: Any) -> str:
    return json.dumps(_jsonable(value), separators=(",", ":"))


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
