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
        command_schedule = (
            {"time": 0.0, "vx": 0.0, "vy": 0.0, "omega": 0.0},
            {"time": 0.25, "vx": 0.4, "vy": 0.0, "omega": 0.0},
        ) if self.transition_commands else (
            {"time": 0.0, "vx": 0.4, "vy": 0.0, "omega": 0.0},
        )
        info = {
            "seed": seed,
            "scenario_id": self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "controller_id": self.config.controller_id,
            "step_count": 0,
            "sim_time": 0.0,
            "command_schedule": command_schedule,
            "sampled_parameters": {"terrain_kind": "plane"},
            "controller_metadata": {"controller_id": self.config.controller_id},
        }
        return {"observation": 1}, info

    def step(self, action):
        self.calls.append(("step", list(action)))
        self._step_count += 1
        command_schedule = (
            {"time": 0.0, "vx": 0.0, "vy": 0.0, "omega": 0.0},
            {"time": 0.25, "vx": 0.4, "vy": 0.0, "omega": 0.0},
        ) if self.transition_commands else (
            {"time": 0.0, "vx": 0.4, "vy": 0.0, "omega": 0.0},
        )
        terminated = self._step_count >= (2 if self.transition_commands else 1)
        info = {
            "seed": 101,
            "scenario_id": self.config.scenario_id,
            "action_mode": self.config.action_mode,
            "controller_id": self.config.controller_id,
            "step_count": self._step_count,
            "sim_time": 0.30 if self.transition_commands else 0.02,
            "command_schedule": command_schedule,
            "current_command": {"vx": 0.4, "vy": 0.0, "omega": 0.0, "source": "scenario_schedule"},
            "locomotion_metrics": {"command_tracking": {"tracking_error": 0.01}},
            "locomotion_metrics_summary": {
                "command_tracking": {"tracking_error_rmse": 0.01, "distance_xy_m": 0.2},
                "stability": {"success": self.success},
                "action_quality": {},
                "contact_terrain": {},
                "success": self.success,
                "failure_reason": None if self.success else "fell",
                "step_count": self._step_count,
            },
        }
        return {"observation": 2}, 0.0, False, terminated, info

    def close(self):
        self.calls.append(("close", self.config.controller_id))


def _fake_env_factory(calls, *, success=True, transition_commands=False):
    def factory(config):
        return _FakeEvaluationEnv(config, calls, success=success, transition_commands=transition_commands)

    return factory


def test_validate_matrix_accepts_repeatable_flags_before_simulation(tmp_path):
    matrix = EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=(101, 202),
        action_mode="velocity_command",
        max_episode_steps=5,
    )

    cells = validate_evaluation_matrix(matrix)

    assert len(cells) == 2  # LOC-EVAL-01 / D-02: full matrix expands before simulation.
    assert [cell["run_id"] for cell in cells] == ["r0001", "r0002"]
    assert {cell["seed"] for cell in cells} == {101, 202}
    assert all(cell["action_mode"] == "velocity_command" for cell in cells)
    assert all(cell["max_episode_steps"] == 5 for cell in cells)

    config_path = tmp_path / "matrix.json"
    config_path.write_text(
        json.dumps(
            {
                "controllers": ["analytical_trot"],
                "scenarios": ["flat_ground"],
                "seeds": [101, 202],
                "action_mode": "velocity_command",
                "max_episode_steps": 5,
            }
        ),
        encoding="utf-8",
    )
    loaded = load_matrix_config(config_path)
    assert loaded == matrix


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


def test_unknown_scenario_fails_before_env_construction(tmp_path):
    calls = []
    matrix = EvaluationMatrix(controllers=("analytical_trot",), scenarios=("moon_crater",), seeds=(101,))

    with pytest.raises(ValueError, match="Unknown locomotion scenario"):
        run_evaluation_matrix(
            matrix,
            EvaluationRunConfig(output_root=tmp_path),
            env_factory=_fake_env_factory(calls),
        )

    assert calls == []
    assert not any(tmp_path.iterdir())


@pytest.mark.parametrize(
    "seeds, message",
    [
        ((-1,), "seed must be between 0 and 4294967295"),
        ((101, 101), "seeds must be unique"),
    ],
)
def test_invalid_seed_values_fail_before_simulation(seeds, message):
    matrix = EvaluationMatrix(controllers=("analytical_trot",), scenarios=("flat_ground",), seeds=seeds)

    with pytest.raises(ValueError, match=message):
        validate_evaluation_matrix(matrix)


def test_non_integer_json_seeds_fail_before_simulation(tmp_path):
    config_path = tmp_path / "matrix.json"
    config_path.write_text(
        json.dumps({"controllers": ["analytical_trot"], "scenarios": ["flat_ground"], "seeds": ["101"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="seeds must contain integers"):
        load_matrix_config(config_path)


def test_oversized_matrix_fails_before_simulation():
    matrix = EvaluationMatrix(
        controllers=("analytical_trot",),
        scenarios=("flat_ground",),
        seeds=tuple(range(1001)),
    )

    with pytest.raises(ValueError, match="Evaluation matrix has 1001 runs; maximum is 1000"):
        validate_evaluation_matrix(matrix)
    # T-04-05: Evaluation matrix has 1001 runs; maximum is 1000.


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
    assert row["commanded_velocity"] == [0.4, 0.0, 0.0]  # D-16: non-stationary debug context.
    assert row["command_source"] == "scenario_schedule"
    assert row["command_context"]["command_schedule"][0]["vx"] == 0.4
    assert ("step", [0.4, 0.0, 0.0]) in calls


def test_locomotion_failure_returns_nonzero_after_rows_exist(tmp_path):
    calls = []
    result = run_evaluation_matrix(
        EvaluationMatrix(controllers=("analytical_trot",), scenarios=("flat_ground",), seeds=(101,)),
        EvaluationRunConfig(output_root=tmp_path, fail_on_locomotion_failure=True),
        env_factory=_fake_env_factory(calls, success=False),
    )

    assert result.had_locomotion_failure is True  # D-16: finish matrix, then return failure status.
    assert result.exit_code == 1
    assert result.step_rows
    assert result.episode_rows[0]["summary"]["success"] is False


def test_runner_uses_active_current_command_after_schedule_transition(tmp_path):
    calls = []
    result = run_evaluation_matrix(
        EvaluationMatrix(
            controllers=("analytical_trot",),
            scenarios=("flat_ground",),
            seeds=(101,),
            max_episode_steps=5,
        ),
        EvaluationRunConfig(output_root=tmp_path),
        env_factory=_fake_env_factory(calls, transition_commands=True),
    )

    assert result.exit_code == 0
    assert ("step", [0.0, 0.0, 0.0]) in calls
    assert ("step", [0.4, 0.0, 0.0]) in calls
    row = result.step_rows[-1]
    assert row["commanded_velocity"] == [0.4, 0.0, 0.0]
    assert row["command_source"] == "scenario_schedule"
    assert row["command_context"]["current_command"]["vx"] == 0.4
