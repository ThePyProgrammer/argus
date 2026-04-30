"""Deterministic reset tests for Argus Go2 locomotion scenarios."""

from src.locomotion.env import ArgusGo2Env, ArgusGo2EnvConfig


DETERMINISTIC_KEYS = (
    "spawn_pose",
    "sampled_parameters",
    "command_schedule",
    "disturbance_schedule",
)


def _reset_metadata(scenario_id: str, seed: int):
    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id=scenario_id))
    try:
        _obs, info = env.reset(seed=seed)
    finally:
        env.close()
    return {key: info[key] for key in DETERMINISTIC_KEYS}


def test_rough_heightfield_same_seed_reproduces_reset_metadata():
    first = _reset_metadata("rough_heightfield", seed=123)
    second = _reset_metadata("rough_heightfield", seed=123)

    assert first == second


def test_rough_heightfield_different_seed_changes_sampled_parameters():
    first = _reset_metadata("rough_heightfield", seed=123)
    second = _reset_metadata("rough_heightfield", seed=124)

    assert first["sampled_parameters"] != second["sampled_parameters"]


def test_push_disturbance_same_seed_reproduces_reset_metadata():
    first = _reset_metadata("push_disturbance", seed=123)
    second = _reset_metadata("push_disturbance", seed=123)

    assert first == second


def test_push_disturbance_different_seed_changes_disturbance_schedule():
    first = _reset_metadata("push_disturbance", seed=123)
    second = _reset_metadata("push_disturbance", seed=124)

    assert first["disturbance_schedule"] != second["disturbance_schedule"]


def test_step_info_preserves_reset_sample_metadata_until_next_reset():
    env = ArgusGo2Env(ArgusGo2EnvConfig(scenario_id="push_disturbance"))
    try:
        _obs, reset_info = env.reset(seed=123)
        _obs, _reward, _terminated, _truncated, step_info = env.step(env.action_space.sample())
    finally:
        env.close()

    assert step_info["spawn_pose"] == reset_info["spawn_pose"]
    assert step_info["sampled_parameters"] == reset_info["sampled_parameters"]
    assert step_info["command_schedule"] == reset_info["command_schedule"]
    assert step_info["disturbance_schedule"] == reset_info["disturbance_schedule"]
