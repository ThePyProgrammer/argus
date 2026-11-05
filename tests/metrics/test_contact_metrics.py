"""Contact identity, measured severity, solver capture, and raw-data retention."""

from dataclasses import replace
import json

import mujoco
import numpy as np
import pytest

from src.metrics.contact_metrics import (
    ContactCatalog, ContactSample, ContactSeverityPolicy, PhysicsContactCollector,
)
from src.metrics.exploration_metrics import ReliabilityCollector, RobotMetricState


def model_and_catalog():
    model = mujoco.MjModel.from_xml_string('''<mujoco>
      <option timestep="0.002"/>
      <worldbody>
        <geom name="floor" type="plane" size="5 5 .1"/>
        <geom name="wall" type="box" size=".1 2 1" pos="3 0 1"/>
        <body name="a" pos="0 0 .3"><freejoint/>
          <geom name="body" type="box" size=".1 .1 .1" mass="1"/>
          <geom name="calf" type="capsule" size=".02 .05" pos="0 0 -.1"/>
          <geom name="foot" type="sphere" size=".05" pos="0 0 -.25"/>
        </body>
        <body name="b" pos="2 0 .3"><freejoint/>
          <geom name="other_robot" type="sphere" size=".1"/>
        </body>
      </worldbody></mujoco>''')
    catalog = ContactCatalog(model, {"a": [2, 3, 4], "b": [5]},
                             floor_geom_ids=[0], foot_geom_ids=[4], leg_geom_ids=[3])
    return model, catalog


def sample(a=3, b=0, force=5., index=0, distance=-.0008):
    return ContactSample(index, a, b, distance, (0., 0., 0.), tuple(np.eye(3).ravel()),
                         (force, 0., 0., 0., 0., 0.))


def collector():
    return PhysicsContactCollector(model_and_catalog()[1], start_sim_time=10.)


def record_contact(samples, duration=.01):
    result = collector()
    result.record_step(10., 10.002, [])
    result.record_step(10.002, 10.002 + duration, samples)
    result.record_step(10.002 + duration, 10.302 + duration, [])
    result.finish()
    return result


@pytest.mark.parametrize("a,b,kind", [
    (4, 0, "foot_floor"), (3, 0, "leg_floor"), (2, 0, "body_floor"),
    (2, 1, "robot_obstacle"), (3, 1, "robot_obstacle"), (2, 5, "robot_robot"),
    (2, 3, "robot_self"), (0, 1, None),
])
def test_contact_identity_is_explicit_and_order_independent(a, b, kind):
    _, catalog = model_and_catalog()
    assert catalog.kind(a, b) == catalog.kind(b, a) == kind


@pytest.mark.parametrize("samples,duration,severity", [
    ([sample(a=4, force=150)], .01, "expected_support"),
    ([sample()], .01, "incidental_leg_contact"),
    ([sample(force=5)], .12, "sustained_contact"),
    ([sample(a=2, b=1, force=120)], .002, "forceful_contact"),
    ([sample(force=50)], .05, "forceful_contact"),  # Impulse exceeds 2 Ns.
    ([sample(a=2)], .01, "unclassified_contact"),  # Body-floor is not a calf brush.
    ([sample(force=20)], .01, "unclassified_contact"),
    ([sample(force=1)], .1, "sustained_contact"),  # Inclusive duration boundary.
    ([sample(force=100)], .002, "forceful_contact"),
    ([sample(force=40)], .05, "forceful_contact"),  # Exactly 2 Ns.
    ([sample(force=1)], .05, "incidental_leg_contact"),
    ([sample(force=10)], .05, "unclassified_contact"),  # Exactly 0.5 Ns is excluded.
])
def test_support_brush_sustained_contact_and_impact_have_distinct_reports(samples, duration, severity):
    result = record_contact(samples, duration)
    summary = result.summary()
    event, = summary["episodes"]
    assert event["severity"] == severity
    assert event["touch_duration_s"] == pytest.approx(duration)
    assert not event["left_censored"] and not event["right_censored"]
    assert len(result.samples()[1]["contacts"]) == len(samples)
    assert summary["termination_policy"] == "report_only"
    json.dumps(summary, allow_nan=False)


def test_manifold_points_sum_force_but_do_not_multiply_duration_or_events():
    result = record_contact([sample(force=3), sample(a=0, b=3, force=7, index=1)], .02)
    event, = result.summary()["episodes"]
    assert event["geom_ids"] == [0, 3]
    assert event["touch_duration_s"] == pytest.approx(.02)
    assert event["peak_normal_force_n"] == 10
    assert event["normal_impulse_ns"] == pytest.approx(.2)
    assert event["point_samples"] == 2
    assert event["touch_steps"] == 1
    assert event["max_penetration_m"] == .0008


def test_debounce_excludes_clear_gaps_from_force_integral_and_touch_duration():
    result = collector()
    result.record_step(10, 10.002, [])
    result.record_step(10.002, 10.012, [sample()])
    result.record_step(10.012, 10.112, [])
    result.record_step(10.112, 10.122, [sample(a=0, b=3)])
    result.record_step(10.122, 10.322, [])
    result.record_step(10.322, 10.332, [sample()])
    events = result.summary()["episodes"]
    assert len(events) == 2
    assert events[0]["touch_duration_s"] == pytest.approx(.02)
    assert events[0]["span_s"] == pytest.approx(.12)
    assert events[0]["normal_impulse_ns"] == pytest.approx(.1)
    assert events[0]["severity"] == "incidental_leg_contact"
    assert events[1]["right_censored"]


@pytest.mark.parametrize("at_start", [True, False])
def test_censored_brush_is_not_declared_incidental(at_start):
    result = collector()
    result.record_step(10, 10.002, [sample()] if at_start else [])
    result.record_step(10.002, 10.004, [] if at_start else [sample()])
    if at_start:
        result.record_step(10.004, 10.304, [])
    result.finish()
    event, = result.summary()["episodes"]
    assert event["severity"] == "unclassified_contact"
    assert event["left_censored"] == at_start
    assert event["right_censored"] != at_start


def test_raw_records_include_support_self_contacts_and_positive_distance_margins():
    result = record_contact([sample(a=4), sample(a=2, b=3, index=1), sample(index=2, distance=.01)])
    assert len(result.samples()[1]["contacts"]) == 3
    assert result.summary()["episodes_by_kind"]["leg_floor"] == 0
    assert result.summary()["episodes_by_kind"]["foot_floor"] == 1
    assert result.summary()["episodes_by_kind"]["robot_self"] == 1
    detached = result.samples()
    detached[1]["contacts"][0]["geom1"] = 999
    assert result.samples()[1]["contacts"][0]["geom1"] == 4


def test_fall_is_a_separate_state_transition_and_preserves_contact_events():
    contacts = record_contact([sample(a=2, force=120)])
    reliability = ReliabilityCollector(("a",), start_sim_time=10)
    reliability.update(10, {"a": RobotMetricState((0, 0, .3))})
    reliability.update(10.01, {"a": RobotMetricState((0, 0, .05), fallen=True)})
    reliability.update(10.02, {"a": RobotMetricState((0, 0, .05), fallen=True)})
    assert reliability.summary()["per_robot"]["a"]["falls"] == 1
    assert contacts.summary()["episodes"][0]["kind"] == "body_floor"
    assert contacts.summary()["episodes"][0]["severity"] == "forceful_contact"


@pytest.mark.parametrize("start,end,samples", [
    (9., 10., []), (10., 10., []), (10., float("nan"), []),
    (10., 10.01, [sample(), sample()]), (10., 10.01, [sample(a=999)]),
    (10., 10.01, [sample(a=0, b=1)]),
])
def test_invalid_step_does_not_partially_mutate_measurements(start, end, samples):
    result = collector()
    before = result.summary()
    with pytest.raises(ValueError):
        result.record_step(start, end, samples)
    assert result.summary() == before
    assert result.samples() == []


def test_finished_collector_cannot_extend_contacts_beyond_termination():
    result = collector()
    result.finish()
    with pytest.raises(ValueError):
        result.record_step(10, 10.002, [sample()])


@pytest.mark.parametrize("value", [-1, 0, float("nan"), float("inf"), True])
def test_invalid_severity_policy_is_rejected(value):
    with pytest.raises(ValueError):
        ContactSeverityPolicy(clear_interval_s=value)


def test_contradictory_thresholds_and_invalid_raw_data_are_rejected():
    with pytest.raises(ValueError):
        ContactSeverityPolicy(incidental_max_duration_s=.2)
    with pytest.raises(ValueError):
        replace(sample(), wrench=(float("nan"),) * 6)
    with pytest.raises(ValueError):
        replace(sample(), geom1=-1)


@pytest.mark.parametrize("integrator", ["Euler", "implicit", "implicitfast"])
def test_real_solver_forces_are_copied_and_capture_does_not_change_physics(integrator):
    model, catalog = model_and_catalog()
    model.opt.integrator = getattr(mujoco.mjtIntegrator, "mjINT_" + integrator.upper())
    observed, baseline = mujoco.MjData(model), mujoco.MjData(model)
    result = PhysicsContactCollector(catalog, start_sim_time=0.)
    expected_impulse = 0.
    for _ in range(10):
        start = float(observed.time)
        mujoco.mj_step(model, observed)
        mujoco.mj_step(model, baseline)
        for index, contact in enumerate(observed.contact):
            if set((int(contact.geom1), int(contact.geom2))) == {0, 4} and contact.dist <= 0:
                wrench = np.zeros(6)
                mujoco.mj_contactForce(model, observed, index, wrench)
                expected_impulse += max(0., wrench[0]) * model.opt.timestep
        result.observe_step(model, observed, start, float(observed.time))
        np.testing.assert_array_equal(observed.qpos, baseline.qpos)
        np.testing.assert_array_equal(observed.qvel, baseline.qvel)
        np.testing.assert_array_equal(observed.qacc_warmstart, baseline.qacc_warmstart)
    event, = result.summary()["episodes"]
    assert event["kind"] == "foot_floor"
    assert event["normal_impulse_ns"] == pytest.approx(expected_impulse)
    assert expected_impulse > 0
    saved = result.samples()
    observed.qpos[2] = 2
    mujoco.mj_forward(model, observed)
    assert result.samples() == saved  # MuJoCo reuses its contact buffer.


def test_rk4_is_rejected_before_claiming_step_average_forces():
    model, _ = model_and_catalog()
    model.opt.integrator = mujoco.mjtIntegrator.mjINT_RK4
    with pytest.raises(ValueError, match="Euler/implicit"):
        PhysicsContactCollector.validate_integrator(model)


def test_real_wall_impact_preserves_geometry_and_measures_force():
    model, catalog = model_and_catalog()
    model.opt.gravity[:] = 0
    data = mujoco.MjData(model)
    data.qpos[:3] = (2.799, 0, 1.)
    data.qvel[0] = 3.
    result = PhysicsContactCollector(catalog, start_sim_time=0)
    for _ in range(20):
        start = float(data.time)
        mujoco.mj_step(model, data)
        result.observe_step(model, data, start, float(data.time))
    impacts = [e for e in result.summary()["episodes"] if e["geom_ids"] == [1, 2]]
    assert impacts
    assert impacts[0]["kind"] == "robot_obstacle"
    assert impacts[0]["severity"] == "forceful_contact"
    assert impacts[0]["normal_impulse_ns"] > 0
