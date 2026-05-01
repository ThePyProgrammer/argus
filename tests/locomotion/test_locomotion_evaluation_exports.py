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

    def step(self, action):
        self._step_count += 1
        info = {
            "seed": 101,
            "scenario_id": self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "controller_id": self.config.controller_id,
            "step_count": self._step_count,
            "sim_time": 0.02 * self._step_count,
            "spawn_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
            "sampled_parameters": {"terrain_kind": "plane"},
            "command_schedule": ({"time": 0.0, "vx": 0.4, "vy": 0.0, "omega": 0.0},),
            "disturbance_schedule": (),
            "current_command": {"vx": 0.4, "vy": 0.0, "omega": 0.0, "source": "scenario_schedule"},
            "locomotion_metrics": {
                "command_tracking": {"tracking_error": 0.01},
                "stability": {"base_height_m": 0.32},
                "action_quality": {"action_delta_norm": 0.02},
                "contact_terrain": {"foot_slip": 0.001},
            },
            "locomotion_metrics_summary": {
                "command_tracking": {"tracking_error_rmse": 0.01, "distance_xy_m": 0.2},
                "stability": {
                    "success": self.success,
                    "base_height_min_m": 0.30,
                    "base_height_max_deviation_m": 0.04,
                    "roll_abs_max_rad": 0.03,
                    "pitch_abs_max_rad": 0.02,
                },
                "action_quality": {
                    "action_smoothness_mean": 0.02,
                    "position_servo_effort_mean": 0.08,
                    "joint_limit_violation_count": 0,
                    "actuator_saturation_count": 0,
                },
                "contact_terrain": {
                    "foot_slip_mean": 0.001,
                    "foot_clearance_mean": 0.05,
                    "duty_factor_mean": 0.5,
                },
                "success": self.success,
                "failure_reason": self.failure_reason,
                "step_count": self._step_count,
            },
        }
        return {"observation": 2}, 0.0, not self.success, self.success, info

    def close(self):
        return None


def _factory(*, success: bool = True, failure_reason: str | None = None):
    def make(config):
        return _FakeExportEnv(config, success=success, failure_reason=failure_reason)

    return make


def _single_cell_matrix() -> EvaluationMatrix:
    return EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=(101,),
        action_mode="velocity_command",
        max_episode_steps=2,
    )


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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

    lines = (result.run_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    step = json.loads(lines[0])
    # LOC-METRICS-05 / D-06 / D-08: compact ids plus nested metrics and command context.
    assert set(step) >= {
        "run_id",
        "controller_id",
        "scenario_id",
        "seed",
        "step_count",
        "sim_time",
        "commanded_velocity",
        "command_source",
        "command_schedule",
        "locomotion_metrics",
    }
    assert step["commanded_velocity"] == [0.4, 0.0, 0.0]
    assert step["command_source"] == "scenario_schedule"
    assert step["locomotion_metrics"]["command_tracking"]["tracking_error"] == 0.01

    with (result.run_dir / "episodes.csv").open(newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    assert len(rows) == 1
    row = rows[0]
    # LOC-EVAL-02 / D-07: spreadsheet-safe flattened episode scorecard row.
    for header in [
        "run_id",
        "controller_id",
        "scenario_id",
        "seed",
        "commanded_velocity",
        "command_source",
        "success",
        "failure_reason",
        "tracking_rmse",
        "distance_xy_m",
        "base_height_min_m",
        "action_smoothness_mean",
        "position_servo_effort_mean",
        "foot_slip_mean",
    ]:
        assert header in row
    assert row["commanded_velocity"] == "[0.4,0.0,0.0]"
    assert row["command_source"] == "scenario_schedule"

    summary = _read_json(result.run_dir / "summary.json")
    # D-09 / D-10 / D-12: direction labels, aggregate groups, no composite score.
    assert summary["metric_directions"] == {
        "success_rate": "success_rate ↑",
        "tracking_rmse": "tracking_rmse ↓",
        "distance_xy_m": "distance_xy_m ↑",
        "action_smoothness_mean": "action_smoothness_mean ↓",
        "position_servo_effort_mean": "position_servo_effort_mean ↓",
        "foot_slip_mean": "foot_slip_mean ↓",
    }
    assert "overall_by_controller" in summary
    assert "by_controller_and_scenario" in summary
    assert "composite_score" not in json.dumps(summary)

    markdown = (result.run_dir / "comparison.md").read_text(encoding="utf-8")
    assert "# Locomotion Evaluation Comparison" in markdown
    assert "## Overall by Controller" in markdown
    assert "## By Controller and Scenario" in markdown
    assert "tracking_rmse ↓" in markdown
    assert "success_rate ↑" in markdown


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


def test_regenerate_comparison_reads_saved_artifacts_without_env(tmp_path, monkeypatch):
    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_factory(),
    )

    def fail_env(*_args, **_kwargs):
        raise AssertionError("offline comparison must not construct env")

    monkeypatch.setattr("src.locomotion.evaluation.ArgusGo2Env", fail_env)
    summary = regenerate_comparison(result.run_dir)

    # LOC-EVAL-02 / D-11 / T-04-03: reload saved artifacts only, no simulation rerun.
    assert summary["run_dir"] == str(result.run_dir)
    assert (result.run_dir / "summary.json").is_file()
    assert (result.run_dir / "comparison.md").is_file()


def test_csv_string_cells_are_formula_safe(tmp_path):
    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_factory(success=False, failure_reason="=cmd|' /C calc'!A0"),
    )

    with (result.run_dir / "episodes.csv").open(newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))

    # LOC-METRICS-05 / D-07 / T-04-04: formula-like string cells are prefixed.
    assert rows[0]["failure_reason"].startswith("'=cmd")


def test_episode_export_reads_distance_xy_m_from_stability_summary(tmp_path):
    class ProductionSummaryEnv(_FakeExportEnv):
        def step(self, action):
            _observation, reward, terminated, truncated, info = super().step(action)
            info["locomotion_metrics_summary"] = {
                "command_tracking": {"tracking_error_rmse": 0.11, "distance_xy_m": 0.0},
                "stability": {
                    "distance_xy_m": 0.42,
                    "min_base_height_m": 0.27,
                    "max_base_height_deviation_m": 0.055,
                    "max_abs_roll_rad": 0.12,
                    "max_abs_pitch_rad": 0.13,
                },
                "action_quality": {
                    "action_delta_norm_mean": 0.021,
                    "position_servo_effort_proxy_mean": 0.082,
                    "commanded_joint_limit_violation_count_total": 2,
                    "position_target_saturation_proxy_total": 3,
                },
                "contact_terrain": {
                    "slip_mean_m_per_s": {"FL": 0.01, "FR": 0.03, "RL": 0.05, "RR": 0.07},
                    "clearance_min_m": {"FL": 0.02, "FR": 0.04, "RL": 0.06, "RR": 0.08},
                    "duty_factor": {"FL": 0.4, "FR": 0.6, "RL": 0.5, "RR": 0.7},
                },
                "success": True,
                "failure_reason": None,
                "step_count": self._step_count,
            }
            return _observation, reward, terminated, truncated, info

    result = run_evaluation_matrix(
        _single_cell_matrix(),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=lambda config: ProductionSummaryEnv(config),
    )

    assert result.episode_rows[0]["distance_xy_m"] == 0.42

    with (result.run_dir / "episodes.csv").open(newline="", encoding="utf-8") as fp:
        row = next(csv.DictReader(fp))

    assert float(row["distance_xy_m"]) == 0.42
    assert float(row["base_height_min_m"]) == 0.27
    assert float(row["base_height_max_deviation_m"]) == 0.055
    assert float(row["roll_abs_max_rad"]) == 0.12
    assert float(row["pitch_abs_max_rad"]) == 0.13
    assert float(row["action_smoothness_mean"]) == 0.021
    assert float(row["position_servo_effort_mean"]) == 0.082
    assert float(row["joint_limit_violation_count"]) == 2.0
    assert float(row["actuator_saturation_count"]) == 3.0
    assert float(row["foot_slip_mean"]) == 0.04
    assert float(row["foot_clearance_mean"]) == 0.05
    assert float(row["duty_factor_mean"]) == 0.55

    summary = _read_json(result.run_dir / "summary.json")
    assert summary["overall_by_controller"][0]["distance_xy_m_mean"] == 0.42
    comparison = (result.run_dir / "comparison.md").read_text(encoding="utf-8")
    assert "0.42" in comparison
