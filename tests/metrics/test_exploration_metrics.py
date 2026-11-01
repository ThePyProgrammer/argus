"""Contact episodes and body-state transitions, independent of control code."""

from dataclasses import replace
from types import SimpleNamespace

import mujoco
import numpy as np
import pytest

from src.metrics.exploration_metrics import ContactClassifier, ContactPair, ReliabilityCollector, RobotMetricState


def states(**kwargs):
    return {"a": RobotMetricState((0, 0, .3), **kwargs), "b": RobotMetricState((1, 0, .3))}


def collector():
    return ReliabilityCollector(("a", "b"), start_sim_time=10, contact_clear_interval_s=.25)


def test_body_xy_distance_excludes_vertical_motion_and_initial_position():
    metrics = collector()
    current = states()
    current["a"] = RobotMetricState((100, 100, .3))
    metrics.update(10, current)
    current["a"] = RobotMetricState((103, 104, 10))
    metrics.update(11, current)
    current["a"] = RobotMetricState((103, 104, 11))
    metrics.update(12, current)
    assert metrics.summary()["total_travel_m"] == 5
    assert metrics.summary()["per_robot"]["b"]["travel_m"] == 0


def test_sustained_contacts_debounce_flicker_and_count_reentry():
    metrics = collector()
    contact = ContactPair("robot_obstacle", "a", "wall")
    metrics.update(10, states(), [contact, contact])
    metrics.update(11, states(), [contact])  # Sparse samples of sustained contact count once.
    metrics.update(12, states(), [])
    metrics.update(12.125, states(), [contact])  # Brief loss does not split the episode.
    assert metrics.summary()["contact_episodes"]["robot_obstacle"] == 1
    metrics.update(13, states(), [])
    metrics.update(13.25, states(), [contact])
    assert metrics.summary()["contact_episodes"]["robot_obstacle"] == 2


def test_robot_pair_order_is_canonical_and_independent_contacts_stay_separate():
    metrics = collector()
    metrics.update(10, states(), [ContactPair("robot_robot", "a", "b"),
                                 ContactPair("robot_robot", "b", "a"),
                                 ContactPair("robot_obstacle", "a", "wall"),
                                 ContactPair("robot_obstacle", "b", "wall")])
    assert metrics.summary()["contact_episodes"] == {"robot_robot": 1, "robot_obstacle": 2}


def test_fall_recovery_and_goals_are_transitions_not_frame_counts():
    metrics = collector()
    metrics.update(10, states(goal_id="f1"))
    metrics.update(11, states(recovering=True, fallen=True, goal_id="f1"))
    metrics.update(12, states(recovering=True, fallen=True, goal_id="f1"))
    metrics.update(13, states(goal_id="f2"))
    metrics.update(14, states())
    metrics.update(15, states(recovering=True, fallen=True, goal_id="f3"))
    result = metrics.summary()["per_robot"]["a"]
    assert result == {"travel_m": 0, "recovery_entries": 2, "falls": 2,
                      "goal_assignments": 3, "goal_switches": 1, "planning_failures": 0}


def test_initial_failure_is_visible_and_input_mappings_are_copied():
    metrics = collector()
    current = states(recovering=True, fallen=True)
    metrics.update(10, current)
    current["a"] = RobotMetricState((100, 100, 100))
    metrics.update(11, states(recovering=True, fallen=True))
    assert metrics.summary()["per_robot"]["a"]["recovery_entries"] == 1
    assert metrics.summary()["per_robot"]["a"]["falls"] == 1
    assert metrics.summary()["total_travel_m"] == 0


def test_planning_failure_deduplication_and_latency():
    metrics = collector()
    metrics.update(10, states())
    for _ in range(3):
        metrics.record_planning_attempt(10, "a", "decision-1", success=False)
    metrics.record_planning_attempt(10, "b", "decision-1", success=False)
    metrics.record_planning_attempt(10, "a", "decision-2", success=True)
    with pytest.raises(ValueError):
        metrics.record_planning_attempt(10, "a", "decision-1", success=True)
    for ms in (1, 2, 3):
        metrics.record_allocator_latency(10, ms)
    result = metrics.summary()
    assert result["per_robot"]["a"]["planning_failures"] == 1
    assert result["per_robot"]["b"]["planning_failures"] == 1
    assert result["allocator_calls"] == 3
    assert result["allocator_latency_mean_ms"] == 2
    assert result["allocator_latency_p95_ms"] == pytest.approx(2.9)
    events = metrics.events()
    events[0]["kind"] = "overwritten"
    assert metrics.events()[0]["kind"] == "planning_attempt"


def test_events_must_match_current_state_time():
    metrics = collector()
    with pytest.raises(ValueError):
        metrics.record_allocator_latency(10, 1)
    metrics.update(10, states())
    with pytest.raises(ValueError):
        metrics.record_planning_attempt(11, "a", "p1", success=False)
    for ms in (-1, np.nan, np.inf):
        with pytest.raises(ValueError):
            metrics.record_allocator_latency(10, ms)
    assert metrics.summary()["allocator_calls"] == 0
    assert metrics.summary()["allocator_latency_mean_ms"] is None


@pytest.mark.parametrize("time,current,contacts", [
    (9, states(), []), (10, states(), []), (np.nan, states(), []),
    (11, {"a": RobotMetricState((100, 0, 0))}, []),
    (11, states(), [ContactPair("robot_robot", "a", "unknown")]),
])
def test_invalid_samples_do_not_partially_mutate_metrics(time, current, contacts):
    metrics = collector()
    metrics.update(10, states())
    before = metrics.summary()
    with pytest.raises(ValueError):
        metrics.update(time, current, contacts)
    assert metrics.summary() == before


def contact_model():
    return mujoco.MjModel.from_xml_string('''<mujoco><worldbody>
      <geom name="floor" type="plane" size="5 5 .1"/>
      <geom name="wall" type="box" size=".1 2 1" pos="3 0 1"/>
      <body name="a" pos="0 0 .2"><freejoint/>
        <geom name="a_body" type="box" size=".3 .3 .1"/>
        <geom name="a_foot" type="sphere" size=".1" pos="0 0 -.15"/>
      </body>
      <body name="b" pos="2 0 .2"><freejoint/>
        <geom name="b_body" type="box" size=".3 .3 .1"/>
      </body>
      <body name="obstacle" pos="-2 0 1">
        <geom name="obstacle_1" type="box" size=".1 .1 .1"/>
        <geom name="obstacle_2" type="box" size=".1 .1 .1" pos=".3 0 0"/>
      </body>
    </worldbody></mujoco>''')


def classifier(model):
    return ContactClassifier(model, {"a": [2, 3], "b": [4]}, floor_geom_ids=[0], foot_geom_ids=[3])


def test_real_mujoco_contacts_exclude_feet_but_keep_body_floor_and_robot_robot():
    model = contact_model()
    data = mujoco.MjData(model)
    contacts = classifier(model)
    mujoco.mj_forward(model, data)
    assert data.ncon > 0
    assert not contacts.pairs(data)  # Only the expected foot penetrates the floor.
    data.qpos[2] = .05
    mujoco.mj_forward(model, data)
    pairs = contacts.pairs(data)
    assert len(pairs) == 1  # Several box-floor points collapse to one episode.
    assert next(iter(pairs)).kind == "robot_obstacle"
    data.qpos[7] = .2
    mujoco.mj_forward(model, data)
    assert ContactPair("robot_robot", "a", "b") in contacts.pairs(data)


def test_classifier_aggregates_composite_objects_and_ignores_self_contacts_and_margins():
    model = contact_model()
    data = SimpleNamespace(contact=[SimpleNamespace(geom1=a, geom2=b, dist=d) for a, b, d in
                                   [(2, 5, -.1), (6, 2, -.1), (2, 3, -.1), (2, 1, .01), (0, 1, -.1)]])
    pairs = classifier(model).pairs(data)
    assert len(pairs) == 1
    assert next(iter(pairs)).second.endswith(":obstacle")


@pytest.mark.parametrize("owners,floor,feet", [
    ({"a": [2], "b": [2]}, [0], []), ({"a": [200]}, [0], []),
    ({"a": [2]}, [0], [3]), ({"a": [2]}, [2], []),
])
def test_invalid_contact_ownership_is_rejected(owners, floor, feet):
    with pytest.raises(ValueError):
        ContactClassifier(contact_model(), owners, floor_geom_ids=floor, foot_geom_ids=feet)


def test_robot_state_copies_mutable_positions():
    position = [1, 2, 3]
    state = RobotMetricState(position)
    position[0] = 10
    assert state.position_xyz == (1, 2, 3)
    with pytest.raises(ValueError):
        replace(state, position_xyz=(np.nan, 0, 0))
    with pytest.raises(ValueError):
        replace(state, recovering="yes")
