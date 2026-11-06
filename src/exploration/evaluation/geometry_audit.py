"""Offline Go2 collision-envelope certificate; never supplies simulator poses to control.

The certificate bounds a sphere about the navigation body origin, so its XY
projection is contained for every heading, roll, and pitch. Hip/thigh rotation
is unrestricted; knee extension is explicitly bounded. This is a geometric
claim, not a claim that arbitrary poses are dynamically stable or reachable.
"""

from __future__ import annotations

import math

import mujoco
import numpy as np

from src.exploration.config import ExplorationConfig


CALF_RANGE_RAD = (-2.7227, -1.5)


def _maximum_rotated_norm(offset, point, lower, upper):
    """Exact max ||offset + Ry(angle) point|| on a closed angle interval."""
    a, b = np.asarray(offset), np.asarray(point)
    cosine = a[0] * b[0] + a[2] * b[2]
    sine = a[0] * b[2] - a[2] * b[0]
    peak = math.atan2(sine, cosine)
    candidates = [lower, upper]
    candidates.extend(peak + 2 * math.pi * k for k in range(
        math.ceil((lower - peak) / (2 * math.pi)),
        math.floor((upper - peak) / (2 * math.pi)) + 1))
    dot = max(cosine * math.cos(t) + sine * math.sin(t) for t in candidates)
    return math.sqrt(max(0., float(a @ a + b @ b + 2 * (a[1] * b[1] + dot))))


def primitive_radius(model, geom):
    """A containing sphere for the entire collision primitive, not its center."""
    kind, size = model.geom_type[geom], model.geom_size[geom]
    if kind == mujoco.mjtGeom.mjGEOM_SPHERE:
        return float(size[0])
    if kind == mujoco.mjtGeom.mjGEOM_BOX:
        return float(np.linalg.norm(size))
    if kind == mujoco.mjtGeom.mjGEOM_CYLINDER:
        return float(np.hypot(size[0], size[1]))
    if kind == mujoco.mjtGeom.mjGEOM_CAPSULE:
        return float(size[0] + size[1])
    raise ValueError(f"Unsupported collision primitive {kind}; extend the audit")


def audit_go2_envelope(model, robot_id="robot_a", config=None,
                       calf_range=CALF_RANGE_RAD):
    """Certify every collidable descendant, failing if kinematic assumptions change.

    Triangle inequality adds root-to-hip distance to a sphere about the hip.
    The thigh origin lies on its hinge axis, so thigh rotation cannot change
    distance from the hip. Calf-center reach is maximized analytically over its
    angle interval; a sphere encloses each complete primitive in any rotation.
    Joint/body layout checks below are part of the proof, not optional metadata.
    """
    config = config or ExplorationConfig()
    lower, upper = map(float, calf_range)
    if not all(map(math.isfinite, (lower, upper))) or lower > upper:
        raise ValueError("Invalid calf angle interval")
    root = model.body(f"{robot_id}_base").id
    parts = {root: (None, "base")}
    for leg in ("FL", "FR", "RL", "RR"):
        parent = root
        for part in ("hip", "thigh", "calf"):
            body = model.body(f"{robot_id}_{leg}_{part}").id
            joint = model.joint(f"{robot_id}_{leg}_{part}_joint").id
            if (model.body_parentid[body] != parent or model.body_jntnum[body] != 1
                    or model.jnt_bodyid[joint] != body
                    or model.jnt_type[joint] != mujoco.mjtJoint.mjJNT_HINGE
                    or not np.allclose(model.body_quat[body], [1, 0, 0, 0], atol=1e-12, rtol=0)
                    or not np.allclose(model.jnt_pos[joint], 0, atol=1e-12, rtol=0)
                    or model.qpos0[model.jnt_qposadr[joint]] != 0):
                raise ValueError("Go2 joint layout changed; rederive the envelope bound")
            axis = [1, 0, 0] if part == "hip" else [0, 1, 0]
            if not np.allclose(model.jnt_axis[joint], axis, atol=1e-12, rtol=0):
                raise ValueError("Go2 hinge axis changed; rederive the envelope bound")
            if part == "thigh" and not np.allclose(model.body_pos[body][[0, 2]], 0, atol=1e-12, rtol=0):
                raise ValueError("Thigh offset must lie on its hinge axis")
            if part == "calf" and (lower < model.jnt_range[joint, 0] - 1e-12
                                    or upper > model.jnt_range[joint, 1] + 1e-12):
                raise ValueError("Audit interval exceeds model calf limits")
            parts[body] = (leg, part)
            parent = body
    rows = []
    for geom in range(model.ngeom):
        if not (model.geom_contype[geom] or model.geom_conaffinity[geom]):
            continue
        body = int(model.geom_bodyid[geom])
        ancestor = body
        while ancestor and ancestor != root:
            ancestor = int(model.body_parentid[ancestor])
        if ancestor != root:
            continue
        if body not in parts:
            raise ValueError("Unaudited collidable body attached to Go2")
        leg, part = parts[body]
        center = model.geom_pos[geom]
        if part == "base":
            reach = float(np.linalg.norm(center))
        else:
            hip = model.body(f"{robot_id}_{leg}_hip").id
            reach = float(np.linalg.norm(model.body_pos[hip]))
            if part == "hip":
                reach += float(np.linalg.norm(center))
            else:
                thigh = model.body(f"{robot_id}_{leg}_thigh").id
                offset = model.body_pos[thigh]
                if part == "thigh":
                    reach += float(np.linalg.norm(offset + center))
                else:
                    offset = offset + model.body_pos[body]
                    reach += _maximum_rotated_norm(offset, center, lower, upper)
        radius = primitive_radius(model, geom)
        margin = max(0., float(model.geom_margin[geom]))
        rows.append({"geom_id": geom, "body": model.body(body).name,
                     "geom_name": model.geom(geom).name,
                     "primitive_radius_m": radius, "contact_margin_m": margin,
                     "root_radius_bound_m": reach + radius + margin})
    camera = model.camera(f"{robot_id}_cam").id
    if model.cam_bodyid[camera] != root or model.cam_mode[camera] != 0:
        raise ValueError("Audit requires a camera fixed to the navigation root")
    camera_offset = float(np.linalg.norm(model.cam_pos[camera]))
    envelope = max(config.footprint_radius_m, camera_offset + config.camera_standoff_m)
    worst = max(rows, key=lambda r: r["root_radius_bound_m"])
    return {"scope": "offline continuous kinematic bound; no dynamics or new exploration coverage",
            "calf_range_rad": [lower, upper],
            "hip_thigh_range": "all rotations (includes the full model joint ranges)",
            "body_attitude_range": "all headings, roll and pitch; geometry only",
            "camera_offset_m": camera_offset,
            "body_camera_envelope_m": envelope,
            "collision_radius_bound_m": worst["root_radius_bound_m"],
            "containment_slack_m": envelope - worst["root_radius_bound_m"],
            "contained": worst["root_radius_bound_m"] <= envelope,
            "worst_geometry": worst,
            "planning_radius_m": {str(r): config.planning_radius(camera_offset, r) for r in (.05, .1)},
            "geometries": rows}
