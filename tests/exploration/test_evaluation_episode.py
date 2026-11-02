"""Real headless episode traces, failure accounting, and resource ownership."""

import json
from unittest.mock import patch

import mujoco
import numpy as np
import pytest

from src.coordination.transport import _topic_registry
from src.exploration.evaluation.episode import ExplorationEpisode, _benchmark_model
from src.exploration.evaluation.scenarios import load_scenario
from src.exploration.exploration_loop import StuckRecovery
from src.exploration.exploration_loop import StepMetrics
from src.bridge.platforms.types import RobotRuntimeState, RobotRuntimeStatus


def episode(*, collect=True, seed=101, horizon=.04):
    return ExplorationEpisode.from_scenario("branching_corridor", seed, horizon_s=horizon, collect=collect)


def run_episode(**kwargs):
    with episode(**kwargs) as run:
        while run.inspect()["state"] == "running":
            run.advance()
        return run.inspect(include_history=True)


def test_collector_attachment_and_episode_order_preserve_commands_and_motion():
    before_callbacks = {key: list(value) for key, value in _topic_registry.items() if value}
    first = run_episode()
    unobserved = run_episode(collect=False)
    run_episode(seed=102)
    repeated = run_episode()
    assert first["commands"] == unobserved["commands"] == repeated["commands"]
    assert first["trajectory"] == unobserved["trajectory"] == repeated["trajectory"]
    assert first["steps"] == repeated["steps"]
    assert first["result"]["coverage"] == repeated["result"]["coverage"]
    assert first["result"]["valid"]
    assert first["result"]["elapsed_s"] == .04
    assert first["result"]["settling_sim_seconds"] == pytest.approx(.4)
    assert first["trajectory"][0]["elapsed_s"] == first["commands"][0]["elapsed_s"] == 0
    assert first["result"]["coverage"]["sensor_frames"] == {"robot_a": 5, "robot_b": 5}
    assert first["result"]["wall_seconds"] >= first["result"]["measurement_wall_seconds"] > 0
    assert first["result"]["peak_process_rss_bytes"] > 0
    assert before_callbacks == {key: list(value) for key, value in _topic_registry.items() if value}
    json.dumps(first, allow_nan=False)


@pytest.mark.timeout(120)
def test_frontier_planning_succeeds_and_trace_is_observer_invariant():
    observed = run_episode(horizon=.35)
    unobserved = run_episode(horizon=.35, collect=False)
    assert observed["commands"] == unobserved["commands"]
    assert observed["trajectory"] == unobserved["trajectory"]
    result = observed["result"]
    assert result["valid"]
    assert result["termination_reason"] == "horizon"
    assert result["elapsed_s"] == pytest.approx(.35)
    assert result["reliability"]["allocator_calls"] > 0
    assert all(r["goal_assignments"] >= 1 for r in result["reliability"]["per_robot"].values())
    assert sum(r["planning_failures"] for r in result["reliability"]["per_robot"].values()) == 0
    assert result["coverage"]["capped_time_s"] == .35
    assert all(r["recovery_entries"] == 0 for r in result["reliability"]["per_robot"].values())


def test_dashboard_cloud_setting_cannot_change_evaluation_maps():
    from src.bridge.cloud_config import get_active_config, set_active_config
    previous = get_active_config()
    try:
        set_active_config("1")
        with episode(horizon=.01) as first:
            first.advance()
            expected = first.coordinator.robots["robot_a"].slam.get_global_cloud()[0]
        set_active_config("4")
        with episode(horizon=.01) as second:
            second.advance()
            actual = second.coordinator.robots["robot_a"].slam.get_global_cloud()[0]
        np.testing.assert_array_equal(actual, expected)
        assert get_active_config() == "4"  # Evaluation does not change interactive configuration.
    finally:
        set_active_config(previous)


@pytest.mark.parametrize("scenario_id", ["branching_corridor", "connected_rooms", "cluttered_room"])
def test_inserted_scene_preserves_environment_geometry(scenario_id):
    scene = load_scenario(scenario_id)
    positions = {p.robot_id: (p.x, p.y, p.z) for p in scene.sample(101).spawn_poses}
    environment = mujoco.MjModel.from_xml_string(scene.mjcf_xml)
    combined = _benchmark_model(scene, positions)
    for i in range(environment.ngeom):
        name = environment.geom(i).name
        j = combined.geom(name).id
        for field in ("geom_type", "geom_pos", "geom_quat", "geom_size", "geom_contype", "geom_conaffinity", "geom_friction"):
            np.testing.assert_array_equal(getattr(environment, field)[i], getattr(combined, field)[j])


def test_resolved_heading_and_capture_pose_match_current_physics():
    with episode(horizon=.01) as run:
        for rid in run.bridge.robot_ids:
            heading = run.provenance["sample"]["spawn_poses"][run.bridge.robot_ids.index(rid)]["yaw_rad"]
            assert run.bridge.get_body_yaw(rid) == pytest.approx(heading, abs=1e-5)
            frame = run.bridge.get_frame(rid)
            before = frame.ground_truth_pose.copy()
            mujoco.mj_forward(run.bridge.mj_model, run.bridge.mj_data)
            camera = run.bridge.mj_model.camera(f"{rid}_cam").id
            np.testing.assert_allclose(before[:3, 3], run.bridge.mj_data.cam_xpos[camera], atol=1e-12)
        assert run.bridge._viewer_handle is None
        assert run.bridge._overview_renderer is None


def test_recovery_streams_are_owned_and_turn_duration_uses_simulated_time():
    first = StuckRecovery(reverse_duration_s=.01, rng=np.random.default_rng([101, 2, 0]))
    second = StuckRecovery(reverse_duration_s=.01, rng=np.random.default_rng([101, 2, 0]))
    np.random.seed(99)
    first.trigger()
    np.random.random(1000)
    second.trigger()
    trace_a, trace_b = [], []
    for _ in range(200):
        trace_a.append(first.step(.01))
        trace_b.append(second.step(.01))
    assert trace_a == trace_b
    assert 145 <= sum(command is not None and command[2] != 0 for command in trace_a) <= 160


def test_control_exception_is_an_absorbing_algorithm_outcome():
    with episode() as run:
        run.coordinator.robots["robot_a"].exploration.step_once = lambda *a, **kw: (_ for _ in ()).throw(ValueError("bad goal"))
        state = run.advance()
        assert state["result"]["valid"]
        assert state["result"]["termination_reason"] == "algorithm_error"
        assert state["elapsed_s"] == 0
        assert run.bridge.mj_model is None
        assert run.inspect(include_history=True)["events"][0]["kind"] == "exploration_error"
        with pytest.raises(RuntimeError):
            run.advance()


@pytest.mark.parametrize("frontiers,reason", [(0, "no_frontiers"), (2, "all_unreachable")])
def test_global_exhaustion_freezes_observations_before_further_motion(frontiers, reason):
    with episode() as run:
        initial = run.coverage.snapshot()
        for robot in run.coordinator.robots.values():
            robot.exploration.step_once = lambda *a, **kw: (
                np.zeros(2), 0., StepMetrics(frontiers, 100., True, 0, True))
        state = run.advance()
        assert state["result"]["termination_reason"] == reason
        assert state["result"]["elapsed_s"] == 0
        assert state["result"]["coverage"]["coverage"] == initial["coverage"]
        assert state["result"]["coverage"]["normalized_auc"] == pytest.approx(initial["coverage"])


def test_backend_loss_is_explicit_and_does_not_advance_physics():
    from dataclasses import replace
    from src.slam.protocol import TrackingStatus
    with episode() as run:
        slam = run.coordinator.robots["robot_a"].slam
        original = slam.process_frame
        slam.process_frame = lambda frame: replace(original(frame), tracking_status=TrackingStatus.LOST)
        state = run.advance()
        assert state["result"]["termination_reason"] == "algorithm_error"
        assert state["result"]["elapsed_s"] == 0
        assert any(event["kind"] == "backend_failure" for event in run.inspect(include_history=True)["events"])


def test_renderer_failure_closes_partial_startup(monkeypatch):
    original = mujoco.Renderer
    created = []
    def renderer(*args, **kwargs):
        if created:
            raise RuntimeError("renderer unavailable")
        value = original(*args, **kwargs)
        created.append(value)
        return value
    monkeypatch.setattr(mujoco, "Renderer", renderer)
    run = episode()
    with pytest.raises(RuntimeError, match="renderer unavailable"):
        run.start()
    assert not run.inspect()["result"]["valid"]
    assert run.bridge.mj_model is None
    assert not run.bridge._renderers
    assert not any(_topic_registry.values())
    assert created[0]._mjr_context is None


def test_unexpected_runtime_error_is_invalid_and_closes_everything():
    with episode() as run:
        run.coordinator.robots["robot_a"].exploration.step_once = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("backend crashed"))
        with pytest.raises(RuntimeError, match="backend crashed"):
            run.advance()
        assert run.inspect()["result"]["termination_reason"] == "infrastructure_error"
        assert not run.inspect()["result"]["valid"]
        assert run.bridge.mj_model is None
        assert not any(_topic_registry.values())


def test_disabled_robot_stays_stopped_while_survivor_continues():
    with episode() as run:
        original = run.bridge.get_runtime_status
        disabled = RobotRuntimeStatus(state=RobotRuntimeState.DISABLED)
        run.bridge.get_runtime_status = lambda rid: disabled if rid == "robot_a" else original(rid)
        run.advance()
        run.bridge.get_runtime_status = original
        run.advance()
        state = run.inspect(include_history=True)
        assert state["commands"][-1]["commands"]["robot_a"]["mode"] == "stop"
        assert state["commands"][-1]["commands"]["robot_b"]["mode"] == "velocity"
        assert run.coverage.snapshot()["sensor_frames"] == {"robot_a": 1, "robot_b": 3}


def test_cleanup_continues_after_a_resource_fails():
    run = episode()
    run.start()
    renderer = run.bridge._renderers["robot_a"]
    original = renderer.close
    def failed_close():
        original()
        raise RuntimeError("close failed")
    with patch.object(renderer, "close", failed_close):
        run.close()
    assert run.bridge.mj_model is None
    assert not run.bridge._renderers
    assert not any(_topic_registry.values())
    assert not run.inspect()["result"]["valid"]
    assert run.inspect()["result"]["cleanup_errors"]
    run.close()


def test_fractional_sensor_horizon_is_rejected_and_closed():
    run = episode(horizon=.015)
    with pytest.raises(ValueError, match="whole number"):
        run.start()
    assert not run.inspect()["result"]["valid"]
    assert run.bridge.mj_model is None
