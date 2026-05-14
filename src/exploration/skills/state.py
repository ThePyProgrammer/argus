from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.exploration.frontier_detector import FrontierCluster

from .types import SkillState, SkillTermination


@dataclass(frozen=True)
class _StateSummary:
    frontier_count: int
    mean_frontier_distance: float
    largest_frontier_size: int


class SkillStateEncoder:
    def __init__(
        self,
        robot_id: str = "robot",
        robot_count: int = 1,
        scenario_id: str | None = None,
        seed: int | None = None,
    ) -> None:
        self._robot_id = robot_id
        self._robot_count = robot_count
        self._scenario_id = scenario_id
        self._seed = seed

    def encode(
        self,
        *,
        coverage_pct: float,
        previous_coverage_pct: float,
        robot_position: np.ndarray,
        frontiers: list[FrontierCluster],
        is_stuck: bool,
        no_progress_steps: int,
        blocked_path_count: int,
        recent_skill_ids: tuple[str, ...],
        recent_termination_reasons: tuple[SkillTermination, ...],
        overlap_score: float = 0.0,
        idle_robot_count: int = 0,
        connectivity_health: float = 1.0,
        localization_health: float = 1.0,
        map_quality_health: float = 1.0,
    ) -> SkillState:
        summary = self._summarize_frontiers(robot_position=robot_position, frontiers=frontiers)
        recent_coverage_delta = float(coverage_pct) - float(previous_coverage_pct)

        return SkillState(
            coverage_pct=float(coverage_pct),
            recent_coverage_delta=recent_coverage_delta,
            frontier_count=summary.frontier_count,
            mean_frontier_distance=summary.mean_frontier_distance,
            largest_frontier_size=summary.largest_frontier_size,
            robot_id=self._robot_id,
            robot_count=self._robot_count,
            is_stuck=bool(is_stuck),
            no_progress_steps=no_progress_steps,
            blocked_path_count=blocked_path_count,
            overlap_score=float(overlap_score),
            idle_robot_count=idle_robot_count,
            connectivity_health=float(connectivity_health),
            localization_health=float(localization_health),
            map_quality_health=float(map_quality_health),
            recent_skill_ids=tuple(recent_skill_ids),
            recent_termination_reasons=tuple(recent_termination_reasons),
            scenario_id=self._scenario_id,
            seed=self._seed,
        )

    @staticmethod
    def _summarize_frontiers(
        *,
        robot_position: np.ndarray,
        frontiers: list[FrontierCluster],
    ) -> _StateSummary:
        frontier_count = len(frontiers)
        if frontier_count == 0:
            return _StateSummary(frontier_count=0, mean_frontier_distance=0.0, largest_frontier_size=0)

        robot_xy = SkillStateEncoder._xy_coords("robot_position", robot_position)
        distances = [float(np.linalg.norm(SkillStateEncoder._xy_coords("frontier.centroid", frontier.centroid) - robot_xy)) for frontier in frontiers]
        largest_frontier_size = max(int(frontier.voxel_count) for frontier in frontiers)
        mean_frontier_distance = float(np.mean(distances)) if distances else 0.0

        return _StateSummary(
            frontier_count=frontier_count,
            mean_frontier_distance=mean_frontier_distance,
            largest_frontier_size=largest_frontier_size,
        )

    @staticmethod
    def _xy_coords(field_name: str, value: np.ndarray) -> np.ndarray:
        coords = np.asarray(value, dtype=float)
        if coords.ndim != 1 or coords.shape[0] < 2:
            raise ValueError(f"{field_name} must contain at least two coordinates")
        return coords[:2]


__all__ = ["SkillStateEncoder"]
