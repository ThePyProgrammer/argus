"""A repeatability check must expose small changes and matching failures."""

import copy
import json

import pytest

from scripts.compare_exploration_traces import compare, load_episode


def trace():
    return {
        "state": "finished",
        "result": {"valid": True, "termination_reason": "horizon", "elapsed_s": .01,
                   "frame_dt": .01, "settling_sim_seconds": .4,
                   "provenance": {"seed": 101}, "wall_seconds": 10},
        "commands": [{"elapsed_s": 0, "commands": {"robot_a": {"linear": [.8, 0]}}}],
        "trajectory": [{"elapsed_s": 0, "positions": {"robot_a": [0, 0, .3]}},
                       {"elapsed_s": .01, "positions": {"robot_a": [.001, 0, .3]}}],
        "events": [],
    }


def test_collector_and_wall_time_differences_do_not_change_control_comparison():
    left, right = trace(), trace()
    right["result"].update(wall_seconds=20, coverage=None, reliability=None)
    left["result"].update(coverage={"coverage": .4}, reliability={"travel_m": .001})
    assert compare(left, right)["equal"]


@pytest.mark.parametrize("field", ["commands", "trajectory"])
def test_tiny_numeric_difference_is_reported_without_tolerance(field):
    left, right = trace(), trace()
    if field == "commands":
        right[field][0]["commands"]["robot_a"]["linear"][0] += 1e-12
    else:
        right[field][1]["positions"]["robot_a"][0] += 1e-12
    report = compare(left, right)
    assert not report["equal"]
    assert field in report["differences"]
    assert "robot_a" in report["differences"][field]["path"]


def test_missing_tail_and_different_seed_are_reported():
    left, right = trace(), trace()
    right["trajectory"].pop()
    right["result"]["provenance"]["seed"] = 102
    report = compare(left, right)
    assert not report["equal"]
    assert report["differences"]["trajectory"]["right_length"] == 1
    assert report["differences"]["provenance"]["path"] == "provenance.seed"


def test_matching_algorithm_failures_are_repeatable_but_reported_as_failures():
    left = trace()
    left["result"]["termination_reason"] = "algorithm_error"
    left["events"] = [{"kind": "backend_failure"}]
    report = compare(left, copy.deepcopy(left))
    assert report["equal"]
    assert report["outcomes"] == ["algorithm_error", "algorithm_error"]


def test_load_accepts_smoke_and_diagnosis_exports(tmp_path):
    path = tmp_path / "trace.json"
    for data in (trace(), {"episode": trace()}):
        path.write_text(json.dumps(data), encoding="utf-8")
        assert load_episode(path) == trace()


@pytest.mark.parametrize("problem", ["invalid", "empty", "truncated", "nonfinite"])
def test_load_rejects_unusable_traces(tmp_path, problem):
    data = trace()
    if problem == "invalid":
        data["result"]["valid"] = False
    elif problem == "empty":
        data["commands"] = []
    elif problem == "truncated":
        data["trajectory"].pop()
    else:
        data["trajectory"][0]["positions"]["robot_a"][0] = float("nan")
    path = tmp_path / "trace.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_episode(path)
