"""Passive travel, reliability events, and measured allocator cost.

The episode runner supplies body poses and real contact samples. Dashboard
proximity warnings and camera trajectories are not substitutes for these inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np

from src.metrics.exploration_coverage import _number


RELIABILITY_VERSION = "body-contact-events-v1"


@dataclass(frozen=True)
class RobotMetricState:
    position_xyz: tuple[float, float, float]
    recovering: bool = False
    fallen: bool = False
    goal_id: str | None = None

    def __post_init__(self):
        if len(self.position_xyz) != 3:
            raise ValueError("Body position must have three coordinates")
        object.__setattr__(self, "position_xyz", tuple(_number(v, "position") for v in self.position_xyz))
        if not isinstance(self.recovering, bool) or not isinstance(self.fallen, bool):
            raise ValueError("Recovery and fall states must be booleans")
        if self.goal_id is not None and (not isinstance(self.goal_id, str) or not self.goal_id):
            raise ValueError("Goal identity must be nonempty or None")


@dataclass(frozen=True, order=True)
class ContactPair:
    kind: str
    first: str
    second: str

    def __post_init__(self):
        if self.kind not in {"robot_robot", "robot_obstacle"}:
            raise ValueError("Unknown contact kind")
        if any(not isinstance(v, str) or not v for v in (self.first, self.second)):
            raise ValueError("Contact identities must be nonempty strings")
        if self.kind == "robot_robot":
            if self.first == self.second:
                raise ValueError("Self-contact is not a team contact")
            first, second = sorted((self.first, self.second))
            object.__setattr__(self, "first", first)
            object.__setattr__(self, "second", second)


class ContactClassifier:
    """Resolve contact manifolds to robot/object pairs using explicit geom ownership.

    Construct once per compiled robot scene. Foot geoms and floor geoms must be
    supplied explicitly; all other robot/environment contacts remain measurable.
    """

    def __init__(self, model, robot_geom_ids: Mapping[str, Iterable[int]], *,
                 floor_geom_ids: Iterable[int], foot_geom_ids: Iterable[int]):
        self._owners = {}
        for robot, geoms in robot_geom_ids.items():
            if not isinstance(robot, str) or not robot:
                raise ValueError("Robot identity must be nonempty")
            for geom in geoms:
                if geom in self._owners:
                    raise ValueError("Robot geom ownership must be disjoint")
                self._owners[geom] = robot
        self._floor, self._feet = set(floor_geom_ids), set(foot_geom_ids)
        all_ids = set(self._owners) | self._floor | self._feet
        if any(isinstance(g, bool) or not isinstance(g, (int, np.integer)) or not 0 <= g < model.ngeom
               for g in all_ids):
            raise ValueError("Geom IDs must be in the compiled model")
        if not self._feet <= self._owners.keys() or self._floor & self._owners.keys():
            raise ValueError("Feet must belong to robots; floor must belong to the environment")
        self._objects = {}
        for geom in range(model.ngeom):
            body = int(model.geom_bodyid[geom])
            # World geoms often represent distinct walls. Other bodies group a
            # composite obstacle's geoms into one contact episode.
            self._objects[geom] = (f"body:{body}:{model.body(body).name}" if body
                                   else f"geom:{geom}:{model.geom(geom).name}")

    def pairs(self, data) -> frozenset[ContactPair]:
        result = set()
        for contact in data.contact:
            if contact.dist > 0:
                continue  # Positive-distance margins are not physical touching.
            a, b = int(contact.geom1), int(contact.geom2)
            if (a in self._feet and b in self._floor) or (b in self._feet and a in self._floor):
                continue
            ra, rb = self._owners.get(a), self._owners.get(b)
            if ra is not None and rb is not None:
                if ra != rb:
                    result.add(ContactPair("robot_robot", ra, rb))
            elif ra is not None:
                result.add(ContactPair("robot_obstacle", ra, self._objects[b]))
            elif rb is not None:
                result.add(ContactPair("robot_obstacle", rb, self._objects[a]))
        return frozenset(result)


class ReliabilityCollector:
    def __init__(self, robot_ids: tuple[str, ...], *, start_sim_time: float,
                 contact_clear_interval_s: float = .2):
        self.robot_ids = tuple(robot_ids)
        if (not self.robot_ids or len(set(self.robot_ids)) != len(self.robot_ids)
                or any(not isinstance(r, str) or not r for r in self.robot_ids)):
            raise ValueError("Unique nonempty robot IDs are required")
        self.start_sim_time = _number(start_sim_time, "start_sim_time")
        self.contact_clear_interval_s = _number(contact_clear_interval_s, "contact_clear_interval_s")
        if self.contact_clear_interval_s <= 0:
            raise ValueError("Contact clearance interval must be positive")
        self._last_time: float | None = None
        self._states: dict[str, RobotMetricState] = {}
        self._travel = dict.fromkeys(self.robot_ids, 0.0)
        self._counts = {robot: dict.fromkeys(("recovery_entries", "falls", "goal_assignments",
                                             "goal_switches", "planning_failures"), 0)
                        for robot in self.robot_ids}
        self._contact_counts = {"robot_robot": 0, "robot_obstacle": 0}
        self._active_contacts: dict[ContactPair, float | None] = {}
        self._attempts: dict[tuple[str, str], bool] = {}
        self._latencies: list[float] = []
        self._events: list[dict] = []

    def _event(self, sim_time: float, kind: str, **fields) -> None:
        self._events.append({"elapsed_s": sim_time - self.start_sim_time, "kind": kind, **fields})

    def update(self, sim_time: float, states: Mapping[str, RobotMetricState],
               contacts: Iterable[ContactPair] = ()) -> None:
        sim_time = _number(sim_time, "sim_time")
        contacts = frozenset(contacts)
        if sim_time < self.start_sim_time or (self._last_time is not None and sim_time <= self._last_time):
            raise ValueError("Samples must have increasing post-settling simulation times")
        if set(states) != set(self.robot_ids) or any(not isinstance(s, RobotMetricState) for s in states.values()):
            raise ValueError("Each sample must include every robot's body state")
        for pair in contacts:
            if (not isinstance(pair, ContactPair) or pair.first not in self._counts
                    or (pair.kind == "robot_robot" and pair.second not in self._counts)):
                raise ValueError("Contact references an unknown robot")
        for robot, state in states.items():
            previous = self._states.get(robot)
            if previous is not None:
                self._travel[robot] += float(np.linalg.norm(
                    np.subtract(state.position_xyz[:2], previous.position_xyz[:2])))
            for flag, counter in (("recovering", "recovery_entries"), ("fallen", "falls")):
                if getattr(state, flag) and (previous is None or not getattr(previous, flag)):
                    self._counts[robot][counter] += 1
                    self._event(sim_time, counter, robot_id=robot)
            old_goal = previous.goal_id if previous else None
            if state.goal_id is not None and state.goal_id != old_goal:
                self._counts[robot]["goal_assignments"] += 1
                if old_goal is not None:
                    self._counts[robot]["goal_switches"] += 1
                self._event(sim_time, "goal_assignment", robot_id=robot, previous_goal=old_goal, goal_id=state.goal_id)
        for pair, absent_since in list(self._active_contacts.items()):
            if absent_since is not None and sim_time - absent_since >= self.contact_clear_interval_s:
                del self._active_contacts[pair]
        for pair in sorted(contacts):
            if pair not in self._active_contacts:
                self._contact_counts[pair.kind] += 1
                self._event(sim_time, pair.kind + "_contact", first=pair.first, second=pair.second)
            self._active_contacts[pair] = None
        for pair in self._active_contacts.keys() - contacts:
            if self._active_contacts[pair] is None:
                self._active_contacts[pair] = sim_time
        self._states, self._last_time = dict(states), sim_time

    def _current_event(self, sim_time: float) -> None:
        if _number(sim_time, "sim_time") != self._last_time:
            raise ValueError("Decision events must use the current state sample time")

    def record_planning_attempt(self, sim_time: float, robot_id: str, attempt_id: str, *, success: bool) -> None:
        self._current_event(sim_time)
        if (robot_id not in self._counts or not isinstance(attempt_id, str) or not attempt_id
                or not isinstance(success, bool)):
            raise ValueError("A known robot, nonempty attempt ID, and boolean outcome are required")
        key = robot_id, attempt_id
        if key in self._attempts:
            if self._attempts[key] != success:
                raise ValueError("Planning attempt outcome changed")
            return
        self._attempts[key] = success
        if not success:
            self._counts[robot_id]["planning_failures"] += 1
        self._event(sim_time, "planning_attempt", robot_id=robot_id, attempt_id=attempt_id, success=success)

    def record_allocator_latency(self, sim_time: float, milliseconds: float) -> None:
        self._current_event(sim_time)
        milliseconds = _number(milliseconds, "milliseconds")
        if milliseconds < 0:
            raise ValueError("Latency cannot be negative")
        self._latencies.append(milliseconds)

    def events(self) -> list[dict]:
        return [dict(event) for event in self._events]

    def summary(self) -> dict:
        """Wall time and peak memory are runtime measurements, added by the runner."""
        return {
            "reliability_version": RELIABILITY_VERSION,
            "elapsed_s": 0.0 if self._last_time is None else self._last_time - self.start_sim_time,
            "contact_clear_interval_s": self.contact_clear_interval_s,
            "total_travel_m": sum(self._travel.values()),
            "per_robot": {robot: {"travel_m": self._travel[robot], **self._counts[robot]} for robot in self.robot_ids},
            "contact_episodes": dict(self._contact_counts),
            "allocator_calls": len(self._latencies),
            "allocator_latency_mean_ms": float(np.mean(self._latencies)) if self._latencies else None,
            "allocator_latency_p95_ms": float(np.percentile(self._latencies, 95)) if self._latencies else None,
        }
