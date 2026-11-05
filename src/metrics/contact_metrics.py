"""Passive physics-step contact records and a versioned descriptive severity policy.

The legacy sensor-frame counters remain available separately. Nothing in this
module changes commands, declares a fall, or terminates an exploration episode.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import math

import numpy as np

from src.metrics.exploration_metrics import ContactClassifier


CONTACT_VERSION = "physics-geom-contact-v1"
SEVERITY_VERSION = "go2-descriptive-contact-v1"
KINDS = ("foot_floor", "leg_floor", "body_floor", "robot_obstacle", "robot_robot", "robot_self")


def _reaches(value: float, threshold: float) -> bool:
    """Keep inclusive boundaries stable under accumulated float roundoff."""
    return value >= threshold or math.isclose(value, threshold, rel_tol=1e-12, abs_tol=1e-12)


@dataclass(frozen=True)
class ContactSeverityPolicy:
    """Development reporting thresholds, not hardware damage or safety limits."""

    clear_interval_s: float = .2
    incidental_max_duration_s: float = .05
    incidental_max_normal_force_n: float = 20.
    incidental_max_normal_impulse_ns: float = .5
    sustained_min_duration_s: float = .1
    forceful_min_normal_force_n: float = 100.
    forceful_min_normal_impulse_ns: float = 2.

    def __post_init__(self):
        if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in asdict(self).values()):
            raise ValueError("Contact thresholds must be finite and positive")
        if (self.incidental_max_duration_s >= self.sustained_min_duration_s
                or self.incidental_max_normal_force_n >= self.forceful_min_normal_force_n
                or self.incidental_max_normal_impulse_ns >= self.forceful_min_normal_impulse_ns):
            raise ValueError("Incidental thresholds must be below sustained/forceful thresholds")

    def classify(self, event: dict) -> str:
        if event["kind"] == "foot_floor":
            return "expected_support"
        if (_reaches(event["peak_normal_force_n"], self.forceful_min_normal_force_n)
                or _reaches(event["normal_impulse_ns"], self.forceful_min_normal_impulse_ns)):
            return "forceful_contact"
        if _reaches(event["touch_duration_s"], self.sustained_min_duration_s):
            return "sustained_contact"
        if (event["kind"] == "leg_floor" and not event["left_censored"] and not event["right_censored"]
                and _reaches(self.incidental_max_duration_s, event["touch_duration_s"])
                and not _reaches(event["peak_normal_force_n"], self.incidental_max_normal_force_n)
                and not _reaches(event["normal_impulse_ns"], self.incidental_max_normal_impulse_ns)):
            return "incidental_leg_contact"
        return "unclassified_contact"


class ContactCatalog:
    """Explicit ownership/part labels plus names for every compiled geometry."""

    def __init__(self, model, robot_geom_ids, *, floor_geom_ids, foot_geom_ids, leg_geom_ids):
        owners = {robot: tuple(geoms) for robot, geoms in robot_geom_ids.items()}
        floor, feet, legs = set(floor_geom_ids), set(foot_geom_ids), set(leg_geom_ids)
        self.legacy_classifier = ContactClassifier(model, owners, floor_geom_ids=floor, foot_geom_ids=feet)
        by_geom = {geom: robot for robot, geoms in owners.items() for geom in geoms}
        if (any(isinstance(g, bool) or not isinstance(g, (int, np.integer)) for g in legs)
                or not legs <= by_geom.keys() or legs & feet):
            raise ValueError("Leg geoms must belong to robots and exclude feet")
        self.geometries = tuple({
            "geom_id": g, "geom_name": model.geom(g).name,
            "body_id": int(model.geom_bodyid[g]), "body_name": model.body(int(model.geom_bodyid[g])).name,
            "robot_id": by_geom.get(g),
            "part": ("foot" if g in feet else "leg" if g in legs else "body" if g in by_geom
                     else "floor" if g in floor else "environment"),
        } for g in range(model.ngeom))

    def kind(self, a: int, b: int) -> str | None:
        first, second = self.geometries[a], self.geometries[b]
        ra, rb = first["robot_id"], second["robot_id"]
        if ra is not None and rb is not None:
            return "robot_self" if ra == rb else "robot_robot"
        if ra is None and rb is None:
            return None
        robot, other = (first, second) if ra is not None else (second, first)
        return robot["part"] + "_floor" if other["part"] == "floor" else "robot_obstacle"


@dataclass(frozen=True)
class ContactSample:
    """One manifold point; wrench and frame retain MuJoCo's original geom order."""

    contact_index: int
    geom1: int
    geom2: int
    distance_m: float
    position_xyz: tuple[float, float, float]
    frame: tuple[float, ...]
    wrench: tuple[float, ...]

    def __post_init__(self):
        for name in ("contact_index", "geom1", "geom2"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("Contact indices must be nonnegative integers")
        if not math.isfinite(self.distance_m):
            raise ValueError("Contact distance must be finite")
        for name, length in (("position_xyz", 3), ("frame", 9), ("wrench", 6)):
            value = tuple(float(x) for x in getattr(self, name))
            if len(value) != length or not all(math.isfinite(x) for x in value):
                raise ValueError(f"Invalid contact {name}")
            object.__setattr__(self, name, value)


class PhysicsContactCollector:
    """Copy each solver sample, then aggregate unordered geom-pair episodes.

    Samples describe [start, end) using the force solve retained by mj_step.
    Capture must precede the frame-end mj_forward. Euler/implicit integration
    is supported; RK4's internal stage forces are not a step-average force.
    """

    def __init__(self, catalog: ContactCatalog, *, start_sim_time: float,
                 policy: ContactSeverityPolicy = ContactSeverityPolicy()):
        if not math.isfinite(start_sim_time):
            raise ValueError("Contact time origin must be finite")
        self.catalog, self.policy = catalog, policy
        self.start_sim_time = start_sim_time
        self._end = start_sim_time
        self._steps: list[dict] = []
        self._episodes: list[dict] = []
        self._active: dict[tuple[int, int], dict] = {}
        self._finished = False

    @staticmethod
    def validate_integrator(model):
        import mujoco
        if model.opt.integrator not in (mujoco.mjtIntegrator.mjINT_EULER,
                                        mujoco.mjtIntegrator.mjINT_IMPLICIT,
                                        mujoco.mjtIntegrator.mjINT_IMPLICITFAST):
            raise ValueError("Physics contact measurement supports Euler/implicit integrators only")

    def observe_step(self, model, data, start: float, end: float) -> None:
        import mujoco
        self.validate_integrator(model)
        samples = []
        for index, contact in enumerate(data.contact):
            a, b = int(contact.geom1), int(contact.geom2)
            if self.catalog.kind(a, b) is None:
                continue
            wrench = np.zeros(6)
            mujoco.mj_contactForce(model, data, index, wrench)
            samples.append(ContactSample(index, a, b, float(contact.dist),
                                         tuple(contact.pos), tuple(contact.frame), tuple(wrench)))
        self.record_step(start, end, samples)

    def record_step(self, start: float, end: float, samples) -> None:
        """Consume a complete step, including empty steps (needed for clearance)."""
        samples = tuple(samples)
        if (self._finished or not math.isfinite(start) or not math.isfinite(end) or end <= start
                or not math.isclose(start, self._end, rel_tol=0, abs_tol=1e-9)):
            raise ValueError("Contact steps must be contiguous, increasing, and unfinished")
        groups = {}
        indices = set()
        for sample in samples:
            if (not isinstance(sample, ContactSample) or sample.contact_index in indices
                    or max(sample.geom1, sample.geom2) >= len(self.catalog.geometries)):
                raise ValueError("Invalid or duplicated contact sample")
            indices.add(sample.contact_index)
            kind = self.catalog.kind(sample.geom1, sample.geom2)
            if kind is None:
                raise ValueError("Contact samples must involve a robot")
            if sample.distance_m > 0:
                continue  # Retained raw, but a positive-distance margin is not touching.
            key = tuple(sorted((sample.geom1, sample.geom2)))
            group = groups.setdefault(key, {"kind": kind, "force": 0., "penetration": 0., "points": 0})
            group["force"] += max(0., sample.wrench[0])
            group["penetration"] = max(group["penetration"], -sample.distance_m)
            group["points"] += 1

        # A recurrence at exactly the clear interval starts a new episode.
        for key, event in list(self._active.items()):
            if start - event["last_touch_end_sim_s"] >= self.policy.clear_interval_s - 1e-9:
                del self._active[key]
        dt = end - start
        for key, group in sorted(groups.items()):
            if key not in self._active:
                event = {"event_id": len(self._episodes), "kind": group["kind"], "geom_ids": list(key),
                         "start_sim_s": start, "last_touch_end_sim_s": end,
                         "touch_duration_s": 0., "peak_normal_force_n": 0., "normal_impulse_ns": 0.,
                         "max_penetration_m": 0., "point_samples": 0, "touch_steps": 0,
                         "left_censored": math.isclose(start, self.start_sim_time, rel_tol=0, abs_tol=1e-9)}
                self._active[key] = event
                self._episodes.append(event)
            event = self._active[key]
            event["last_touch_end_sim_s"] = end
            event["touch_duration_s"] += dt
            event["peak_normal_force_n"] = max(event["peak_normal_force_n"], group["force"])
            event["normal_impulse_ns"] += group["force"] * dt
            event["max_penetration_m"] = max(event["max_penetration_m"], group["penetration"])
            event["point_samples"] += group["points"]
            event["touch_steps"] += 1
        for key, event in list(self._active.items()):
            if key not in groups and end - event["last_touch_end_sim_s"] >= self.policy.clear_interval_s - 1e-9:
                del self._active[key]
        self._steps.append({"start_elapsed_s": start - self.start_sim_time,
                            "end_elapsed_s": end - self.start_sim_time,
                            "contacts": [asdict(sample) for sample in samples]})
        self._end = end

    def finish(self) -> None:
        self._finished = True  # Do not invent clearance time after an early stop.

    def samples(self) -> list[dict]:
        return copy.deepcopy(self._steps)

    def summary(self) -> dict:
        events = copy.deepcopy(self._episodes)
        active_ids = {e["event_id"] for e in self._active.values()}
        by_kind = dict.fromkeys(KINDS, 0)
        by_severity = {}
        for event in events:
            event["start_elapsed_s"] = event.pop("start_sim_s") - self.start_sim_time
            event["last_touch_end_elapsed_s"] = event.pop("last_touch_end_sim_s") - self.start_sim_time
            event["span_s"] = event["last_touch_end_elapsed_s"] - event["start_elapsed_s"]
            event["right_censored"] = event["event_id"] in active_ids
            event["severity"] = self.policy.classify(event)
            by_kind[event["kind"]] += 1
            by_severity[event["severity"]] = by_severity.get(event["severity"], 0) + 1
        return {"version": CONTACT_VERSION, "severity_version": SEVERITY_VERSION,
                "severity_policy": asdict(self.policy), "termination_policy": "report_only",
                "cadence": "physics_steps", "force_sample": "step_solver_before_frame_forward",
                "force_aggregation": "sum_nonnegative_normal_force_per_geom_pair",
                "impulse_rule": "sum_force_times_step_duration", "time_origin_sim_s": self.start_sim_time,
                "elapsed_s": self._end - self.start_sim_time, "physics_steps": len(self._steps),
                "finished": self._finished, "geometries": copy.deepcopy(self.catalog.geometries),
                "episodes_by_kind": by_kind, "episodes_by_severity": by_severity, "episodes": events}
