import numpy as np

from src.bridge.collision_state import compute_collision_summaries


def test_separated_robots_have_zero_counts():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([5.0, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"] == {"collision_count": 0, "near_miss_count": 0}
    assert summaries["robot_b"] == {"collision_count": 0, "near_miss_count": 0}


def test_collision_counts_for_both_robots():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([0.4, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"]["collision_count"] == 1
    assert summaries["robot_b"]["collision_count"] == 1
    assert summaries["robot_a"]["near_miss_count"] == 0


def test_near_miss_counts_without_collision():
    summaries = compute_collision_summaries(
        positions={"robot_a": np.array([0.0, 0.0, 0.0]), "robot_b": np.array([0.8, 0.0, 0.0])},
        footprint_radius=0.33,
        near_miss_margin=0.25,
    )

    assert summaries["robot_a"]["collision_count"] == 0
    assert summaries["robot_a"]["near_miss_count"] == 1
    assert summaries["robot_b"]["near_miss_count"] == 1
