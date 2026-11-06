"""Continuous geometry certificate plus independent compiled-model pose checks."""

from itertools import product

import mujoco
import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from src.bridge.sensor_types import SensorFrame, fixed_camera_mount
from src.exploration.config import ExplorationConfig
from src.exploration.evaluation.episode import _benchmark_model
from src.exploration.evaluation.geometry_audit import (
    CALF_RANGE_RAD, _maximum_rotated_norm, audit_go2_envelope, primitive_radius,
)
from src.exploration.evaluation.scenarios import load_scenario
from src.locomotion.gait_controller import TrotGaitController


@pytest.fixture(scope="module")
def model():
    return _benchmark_model(load_scenario("connected_rooms"), {"robot_a": (0., 0., .3)})


def test_continuous_articulated_bound_includes_all_collision_primitives(model):
    report = audit_go2_envelope(model)
    assert len(report["geometries"]) == 23  # Three base primitives, five per leg (including feet).
    assert report["contained"]
    assert .54 < report["collision_radius_bound_m"] < .55
    assert report["containment_slack_m"] > .003
    assert report["collision_radius_bound_m"] > ExplorationConfig().footprint_radius_m
    # Extending to the model's full knee range cannot be certified by this circle.
    full = audit_go2_envelope(model, calf_range=(-2.7227, -.83776))
    assert not full["contained"]


@pytest.mark.parametrize("lower,upper", [(-2.7227, -1.5), (-2., 2.), (4., 9.)])
def test_analytic_extrema_bound_dense_independent_rotation_samples(lower, upper):
    a, b = np.array([.06, -.0955, -.213]), np.array([.02, .005, -.148])
    angles = np.linspace(lower, upper, 10001)
    rotated = Rotation.from_euler("y", angles[:, None]).apply(np.tile(b, (len(angles), 1)))
    samples = np.linalg.norm(a + rotated, axis=1)
    bound = _maximum_rotated_norm(a, b, lower, upper)
    assert bound >= samples.max() - 1e-12
    assert bound - samples.max() < 1e-7


def test_certificate_bounds_compiled_forward_kinematics_over_gait_and_attitudes(model):
    report = audit_go2_envelope(model)
    data = mujoco.MjData(model)
    base = model.body("robot_a_base").id
    cam = model.camera("robot_a_cam").id
    gait = TrotGaitController()
    # Standing, walking, pure turns, reverse/recovery, and both turn directions.
    commands = [(0, 0, 0), (.8, 0, 0), (.8, 0, -1), (.8, 0, 1),
                (0, 0, -1.5), (0, 0, 1.5), (-.8, 0, 0)]
    attitudes = [(0, 0, 0), (.3, -.3, 1.1), (-.3, .3, -2.3), (1.2, -.8, .4)]
    for command, phase, attitude in product(commands, np.linspace(0, 1, 33), attitudes):
        gait._phase = (phase - gait._params.frequency * .01) % 1
        gait._active_yaw = None
        targets = gait.compute(*command, .01)
        assert np.all(targets[2::3] >= CALF_RANGE_RAD[0])
        assert np.all(targets[2::3] <= CALF_RANGE_RAD[1])
        data.qpos[:3] = [1.2, -2.3, .4]
        data.qpos[3:7] = np.roll(Rotation.from_euler("xyz", attitude).as_quat(), 1)
        data.qpos[7:] = targets
        mujoco.mj_forward(model, data)
        for row in report["geometries"]:
            geom = row["geom_id"]
            # Entire enclosing sphere, independently positioned by MuJoCo.
            radius = (np.linalg.norm(data.geom_xpos[geom] - data.xpos[base])
                      + primitive_radius(model, geom) + model.geom_margin[geom])
            assert radius <= row["root_radius_bound_m"] + 1e-12
        camera_reach = np.linalg.norm((data.cam_xpos[cam] - data.xpos[base])[:2])
        assert camera_reach + .15 <= report["body_camera_envelope_m"] + 1e-12


def test_certificate_covers_knee_interval_endpoints_and_independent_joint_extremes(model):
    report = audit_go2_envelope(model)
    data = mujoco.MjData(model)
    for hip, thigh, calf in product((-1.0472, 0, 1.0472), (-1.5708, 0, 4.5379), CALF_RANGE_RAD):
        # The geometric proof even permits thigh angles outside individual joint
        # limits; forward kinematics does not simulate joint-limit enforcement.
        data.qpos[7:] = np.tile([hip, thigh, calf], 4)
        mujoco.mj_forward(model, data)
        for row in report["geometries"]:
            g = row["geom_id"]
            radius = np.linalg.norm(data.geom_xpos[g] - data.xpos[model.body("robot_a_base").id])
            radius += primitive_radius(model, g) + model.geom_margin[g]
            assert radius <= row["root_radius_bound_m"] + 1e-12


def test_geometry_changes_cannot_silently_reuse_certificate(model):
    geom = model.geom("robot_a_FL").id
    size = model.geom_size[geom].copy()
    axis = model.jnt_axis[2].copy()
    try:
        model.geom_size[geom, 0] = .2
        assert not audit_go2_envelope(model)["contained"]
        model.geom_size[geom] = size
        model.jnt_axis[2] = [1, 0, 0]
        with pytest.raises(ValueError, match="hinge axis"):
            audit_go2_envelope(model)
    finally:
        model.geom_size[geom] = size
        model.jnt_axis[2] = axis


def test_more_extended_knee_has_actual_counterexample_outside_declared_range(model):
    data = mujoco.MjData(model)
    data.qpos[7:] = np.tile([0., .9, -1.8], 4)
    # A physically permitted front-leg configuration, beyond the certified knee
    # range. A real point on the foot sphere exceeds the camera-inclusive circle.
    data.qpos[7:10] = [0., -1.2, -.83776]
    mujoco.mj_forward(model, data)
    foot, base = model.geom("robot_a_FL").id, model.body("robot_a_base").id
    reach = np.linalg.norm((data.geom_xpos[foot] - data.xpos[base])[:2]) + model.geom_size[foot, 0]
    assert reach > .6
    assert reach > audit_go2_envelope(model)["body_camera_envelope_m"]


def test_nominal_radius_alone_misses_real_calf_geometry_even_when_standing(model):
    data = mujoco.MjData(model)
    data.qpos[7:] = TrotGaitController().compute(0, 0, 0, .01)
    mujoco.mj_forward(model, data)
    base = model.body("robot_a_base").id
    calf = model.body("robot_a_RL_calf").id
    points = []
    for geom in range(model.ngeom):
        if model.geom_bodyid[geom] == calf and model.geom_type[geom] == mujoco.mjtGeom.mjGEOM_CYLINDER:
            axis = data.geom_xmat[geom].reshape(3, 3)[:, 2]
            # End-face centers are actual points on the cylinder, not an upper bound.
            points.extend(data.geom_xpos[geom] + sign * model.geom_size[geom, 1] * axis
                          for sign in (-1, 1))
    reach = max(np.linalg.norm((p - data.xpos[base])[:2]) for p in points)
    assert reach > ExplorationConfig().footprint_radius_m
    assert reach < audit_go2_envelope(model)["body_camera_envelope_m"]


@pytest.mark.parametrize("yaw", [-2.1, 0., 1.3])
def test_fixed_camera_calibration_recovers_same_body_origin_used_by_geometry(model, yaw):
    data = mujoco.MjData(model)
    data.qpos[:3] = [1.2, -2.3, .4]
    data.qpos[3:7] = np.roll(Rotation.from_euler("xyz", [.2, -.3, yaw]).as_quat(), 1)
    mujoco.mj_forward(model, data)
    base, camera = model.body("robot_a_base").id, model.camera("robot_a_cam").id
    mount = fixed_camera_mount(model, camera, base)
    world_camera = np.eye(4)
    world_camera[:3, :3] = data.cam_xmat[camera].reshape(3, 3)
    world_camera[:3, 3] = data.cam_xpos[camera]
    frame = SensorFrame(np.zeros((1, 1, 3)), None, np.eye(4), 0., body_from_camera=mount)
    body = frame.body_pose_from_camera(world_camera)
    np.testing.assert_allclose(body[:3, 3], data.xpos[base], atol=1e-12)
    np.testing.assert_allclose(body[:3, :3], data.xmat[base].reshape(3, 3), atol=1e-12)
    assert np.linalg.norm(mount[:3, 3]) == pytest.approx(audit_go2_envelope(model)["camera_offset_m"])
