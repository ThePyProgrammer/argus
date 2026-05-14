from __future__ import annotations

import pytest
import numpy as np

from src.exploration.frontier_detector import FrontierCluster
from src.exploration.skills.state import SkillStateEncoder
from src.exploration.skills.types import SkillTermination


def _cluster(centroid: tuple[float, float, float], count: int) -> FrontierCluster:
    return FrontierCluster(
        centroid=np.array(centroid),
        voxel_count=count,
        voxels=np.empty((0, 2), dtype=int),
    )


def test_state_encoder_summarizes_frontiers_deterministically() -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=2, scenario_id="office", seed=42)
    frontiers = [_cluster((1.0, 0.0, 0.0), 5), _cluster((4.0, 0.0, 0.0), 15)]

    state = encoder.encode(
        coverage_pct=20.0,
        previous_coverage_pct=18.0,
        robot_position=np.array([0.0, 0.0, 0.0]),
        frontiers=frontiers,
        is_stuck=False,
        no_progress_steps=2,
        blocked_path_count=1,
        recent_skill_ids=("frontier_pursuit",),
        recent_termination_reasons=(SkillTermination.SUCCESS,),
    )

    assert state.coverage_pct == 20.0
    assert state.recent_coverage_delta == 2.0
    assert state.frontier_count == 2
    assert state.mean_frontier_distance == 2.5
    assert state.largest_frontier_size == 15
    assert state.robot_id == "robot-1"
    assert state.robot_count == 2
    assert state.scenario_id == "office"
    assert state.seed == 42


def test_state_encoder_handles_no_frontiers() -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=1)

    state = encoder.encode(
        coverage_pct=10.0,
        previous_coverage_pct=10.0,
        robot_position=np.array([0.0, 0.0, 0.0]),
        frontiers=[],
        is_stuck=True,
        no_progress_steps=12,
        blocked_path_count=0,
        recent_skill_ids=(),
        recent_termination_reasons=(),
    )

    assert state.frontier_count == 0
    assert state.mean_frontier_distance == 0.0
    assert state.largest_frontier_size == 0
    assert state.is_stuck is True


def test_state_encoder_preserves_optional_health_fields() -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=1)

    state = encoder.encode(
        coverage_pct=10.0,
        previous_coverage_pct=8.0,
        robot_position=np.array([0.0, 0.0, 0.0]),
        frontiers=[_cluster((1.0, 1.0, 0.0), 4)],
        is_stuck=False,
        no_progress_steps=0,
        blocked_path_count=0,
        recent_skill_ids=(),
        recent_termination_reasons=(),
        overlap_score=0.25,
        idle_robot_count=3,
        connectivity_health=0.8,
        localization_health=0.9,
        map_quality_health=0.7,
    )

    assert state.overlap_score == 0.25
    assert state.idle_robot_count == 3
    assert state.connectivity_health == 0.8
    assert state.localization_health == 0.9
    assert state.map_quality_health == 0.7


@pytest.mark.parametrize("field_name,bad_value", [("no_progress_steps", True), ("no_progress_steps", 0.9), ("blocked_path_count", True), ("blocked_path_count", 0.9)])
def test_state_encoder_rejects_invalid_counter_inputs(field_name: str, bad_value: object) -> None:
    encoder = SkillStateEncoder(robot_id="robot-1", robot_count=1)

    kwargs = {
        "coverage_pct": 10.0,
        "previous_coverage_pct": 10.0,
        "robot_position": np.array([0.0, 0.0, 0.0]),
        "frontiers": [],
        "is_stuck": False,
        "no_progress_steps": 0,
        "blocked_path_count": 0,
        "recent_skill_ids": (),
        "recent_termination_reasons": (),
    }
    kwargs[field_name] = bad_value

    with pytest.raises((TypeError, ValueError)):
        encoder.encode(**kwargs)
