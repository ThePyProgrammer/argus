"""Pose support is consumed before both navigation and occupancy insertion."""
from unittest.mock import Mock

import numpy as np
import pytest

from src.exploration.exploration_loop import ExplorationLoop
from src.slam.pose_support import SUPPORT_VERSION, PoseChainSupport
from src.slam.protocol import SLAMResult, TrackingStatus
from tests.control.test_motion_clearance import room, pose
from tests.exploration.test_exploration_loop import MockBridge, MockOctoMap, MockSLAM
from tests.exploration.test_motion_clearance_integration import frame


def setup_loop(monkeypatch):
    slam = MockSLAM()
    slam.CAPABILITIES = {'pose_map_support': SUPPORT_VERSION}
    octomap = MockOctoMap()
    octomap.insert_scan = Mock(wraps=octomap.insert_scan)
    loop = ExplorationLoop(MockBridge(), slam, octomap)
    monkeypatch.setattr(loop, 'planning_grid', lambda *a: room())
    support = PoseChainSupport()
    support.update(0., accepted=True, rank=0, seeded=True)
    evidence = [support.snapshot()]
    monkeypatch.setattr(slam, 'process_frame', lambda f: SLAMResult(
        pose=pose(), points=np.array([[0., 0., .5]]), colors=np.zeros((1, 3)),
        metrics={'pose_map_support': evidence[0]}, tracking_status=TrackingStatus.OK))
    loop.step_once(frame(0.), 0)
    return loop, support, evidence


def test_pose_history_loss_stops_only_affected_robot_and_cannot_be_reset_by_goal(monkeypatch):
    bad, bad_support, bad_evidence = setup_loop(monkeypatch)
    good, good_support, good_evidence = setup_loop(monkeypatch)
    inserted = bad._octomap.insert_scan.call_count
    bad_support.update(.05, accepted=True, rank=5)
    bad_evidence[0] = bad_support.snapshot()
    good_support.update(.05, accepted=True, rank=6)
    good_evidence[0] = good_support.snapshot()
    linear, angular, metrics = bad.step_once(frame(.05), 1)
    assert not linear.any() and angular == 0
    assert metrics.terminated
    assert bad.measurement_state['motion_clearance']['reason'] == 'pose_history_unobservable'
    assert bad._octomap.insert_scan.call_count == inserted
    assert good.step_once(frame(.05), 1)[0][0] > 0
    # Backend-only reset and a new goal cannot authorize the existing map.
    fresh_support = PoseChainSupport()
    fresh_support.update(.1, accepted=True, rank=0, seeded=True)
    bad_evidence[0] = fresh_support.snapshot()
    bad.set_waypoint_target([np.array([2., 0., 0.])])
    linear, angular, metrics = bad.step_once(frame(.1), 2)
    assert not linear.any() and angular == 0 and metrics.terminated
    assert bad._octomap.insert_scan.call_count == inserted
    assert bad.measurement_state['navigation']['pose_map_error'] == 'pose_history_unobservable'


@pytest.mark.parametrize('evidence', [None, {}, {'version': 'future'}])
def test_required_but_missing_support_blocks_motion_and_map(monkeypatch, evidence):
    loop, _, current = setup_loop(monkeypatch)
    inserted = loop._octomap.insert_scan.call_count
    current[0] = evidence
    linear, angular, _ = loop.step_once(frame(.05), 1)
    assert not linear.any() and angular == 0
    assert loop._octomap.insert_scan.call_count == inserted
    assert loop.measurement_state['motion_clearance']['reason'] == 'pose_support_unavailable'


def test_stale_support_blocks_without_mutating_map(monkeypatch):
    loop, _, current = setup_loop(monkeypatch)
    inserted = loop._octomap.insert_scan.call_count
    current[0]['observed_at_s'] = -1.
    linear, angular, _ = loop.step_once(frame(.05), 1)
    assert not linear.any() and angular == 0
    assert loop._octomap.insert_scan.call_count == inserted
    assert loop.measurement_state['motion_clearance']['reason'] == 'pose_support_stale'
