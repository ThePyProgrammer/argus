from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Callable

import numpy as np

from .types import SkillDecision

_TARGET_REQUIRED_SKILLS = frozenset(
    {
        "frontier_pursuit",
        "coverage_sweep",
        "viewpoint_shift",
        "loop_closure_probe",
    }
)


@dataclass(frozen=True)
class SkillExecutionResult:
    score_fn: Callable[[np.ndarray], float] | None
    fallback_used: bool
    termination_reason: str | None
    reason_codes: tuple[str, ...]


class SkillExecutor:
    def apply(self, decision: SkillDecision) -> SkillExecutionResult:
        if decision.selected_proposal is None:
            return SkillExecutionResult(
                score_fn=None,
                fallback_used=True,
                termination_reason="baseline_fallback",
                reason_codes=decision.reason_codes,
            )

        proposal = decision.selected_proposal
        if proposal.target is None:
            if proposal.skill_id in _TARGET_REQUIRED_SKILLS:
                return SkillExecutionResult(
                    score_fn=None,
                    fallback_used=True,
                    termination_reason="precondition_invalidated",
                    reason_codes=decision.reason_codes,
                )
            return SkillExecutionResult(
                score_fn=None,
                fallback_used=False,
                termination_reason=None,
                reason_codes=decision.reason_codes,
            )

        target_xy = (float(proposal.target[0]), float(proposal.target[1]))

        def score_fn(candidate: np.ndarray) -> float:
            candidate_xy = np.asarray(candidate, dtype=float)
            if candidate_xy.ndim != 1:
                raise ValueError("candidate must be a 1-D vector with at least two finite coordinates")
            if candidate_xy.size < 2:
                raise ValueError("candidate must be a 1-D vector with at least two finite coordinates")
            if not np.isfinite(candidate_xy).all():
                raise ValueError("candidate coordinates must be finite")

            distance = hypot(candidate_xy[0] - target_xy[0], candidate_xy[1] - target_xy[1])
            return -distance

        return SkillExecutionResult(
            score_fn=score_fn,
            fallback_used=False,
            termination_reason=None,
            reason_codes=decision.reason_codes,
        )


__all__ = ["SkillExecutionResult", "SkillExecutor"]
