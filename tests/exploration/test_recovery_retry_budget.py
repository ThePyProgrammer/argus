"""The last permitted recovery must still get a bounded chance to replan."""
import numpy as np
import pytest

from src.exploration.blocked_navigation import BlockedNavigation
from src.exploration.config import ExplorationConfig


@pytest.mark.parametrize("replans,recoveries", [(4, 2), (3, 2), (2, 2), (1, 2)])
def test_replan_budget_reserves_a_route_check_after_each_recovery(replans, recoveries):
    state = BlockedNavigation(ExplorationConfig(blocked_max_replans=replans,
                                               blocked_max_recoveries=recoveries))
    now = 0.
    state.block("fixture_route_failure", now)
    after_recovery = False
    checks_after_recovery = 0
    for _ in range(12):
        now += 1.01
        action = state.next_action(now)
        if action == "replan":
            if after_recovery:
                checks_after_recovery += 1
                after_recovery = False
            state.block("fixture_route_failure", now)
        elif action == "recover":
            assert not after_recovery, "A prior recovery never got its route check"
            pose = np.eye(4)
            state.start_recovery((-.6, 0., 0.), pose, now)
            pose[0, 3] = -.11
            now += .5
            state.observe(pose, now)
            assert state.recovery_outcome == "progress"
            after_recovery = True
        elif state.state == "failed":
            break
    assert state.recoveries == min(recoveries, replans - 1)
    assert checks_after_recovery == state.recoveries
    assert state.replans <= state.config.blocked_max_replans
    assert state.state == "failed" and state.reason == "retry_budget_exhausted"
