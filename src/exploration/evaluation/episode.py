"""One sequential exploration episode using the interactive coordinator's ticks.

This is the existing Voronoi control path, not the future allocator comparison.
No reference grid or measurement result is supplied to the coordinator.
"""

from __future__ import annotations

import copy
from dataclasses import asdict
import math
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np

from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.multi_robot_config import MultiRobotConfig
from src.bridge.platforms.go2 import Go2Platform
from src.bridge.scene_builder import build_multi_robot_scene
from src.coordination.coordinator import Coordinator
from src.coordination.robot_instance import RobotInstance
from src.exploration.config import ExplorationConfig
from src.exploration.evaluation.scenarios import DEFAULTS, load_scenario
from src.metrics.exploration_coverage import CoverageCollector, CoverageConfig, DepthObservation
from src.metrics.exploration_metrics import ContactClassifier, ReliabilityCollector, RobotMetricState
from src.locomotion.gait_params import GaitParams


def _benchmark_model(scene, positions):
    """Insert Go2 bodies into one of the authored static benchmark environments."""
    import mujoco
    xml, assets = build_multi_robot_scene(Go2Platform(), positions)
    root, environment = ET.fromstring(xml), ET.fromstring(scene.mjcf_xml)
    world = root.find("worldbody")
    for child in list(world):
        if child.tag != "body":
            world.remove(child)
    defaults = environment.find("default/geom").attrib
    for child in environment.find("worldbody"):
        item = copy.deepcopy(child)
        if item.tag == "geom":
            item.attrib = {**defaults, **item.attrib}
        world.append(item)
    for tag in ("option", "statistic", "visual"):
        source = environment.find(tag)
        if source is not None:
            existing = root.find(tag)
            if existing is not None:
                root.remove(existing)
            root.append(copy.deepcopy(source))
    return mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"), assets)


def _contacts(bridge: MultiRobotBridge) -> ContactClassifier:
    model = bridge.mj_model
    owners = {rid: [] for rid in bridge.robot_ids}
    for geom in range(model.ngeom):
        body = int(model.geom_bodyid[geom])
        while body:
            matched = next((rid for rid in owners if model.body(body).name == f"{rid}_base"), None)
            if matched is not None:
                owners[matched].append(geom)
                break
            body = int(model.body_parentid[body])
    if any(not geoms for geoms in owners.values()):
        raise ValueError("Benchmark contact ownership requires Go2 root bodies")
    feet = [model.geom(f"{rid}_{foot}").id for rid in owners for foot in ("FL", "FR", "RL", "RR")]
    return ContactClassifier(model, owners, floor_geom_ids=[model.geom("floor").id], foot_geom_ids=feet)


def _peak_process_rss_bytes() -> int | None:
    """OS process high-water mark, not an isolated episode's memory allocation."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_process.restype = wintypes.HANDLE
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if query(get_process(), ctypes.byref(counters), counters.cb):
            return int(counters.PeakWorkingSetSize)
        return None
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


class ExplorationEpisode:
    """Fresh, single-use runtime; always use as a context manager or call close.

    Collector attachment is optional for command-trace invariance checks. Errors
    in control become valid algorithm outcomes; unexpected runtime exceptions
    become invalid infrastructure attempts and propagate after cleanup.
    """

    def __init__(self, coordinator, bridge, reference, *, coverage_config=CoverageConfig(),
                 collect: bool = True, provenance: dict | None = None):
        self.coordinator, self.bridge = coordinator, bridge
        self.reference, self.config = reference, coverage_config
        self.collect = collect
        self.provenance = copy.deepcopy(provenance or {})
        self.coverage = None
        self.reliability = None
        self._classifier = None
        self._state = "new"
        self._result = None
        self._elapsed = 0.0
        self._origin = 0.0
        self._wall_start = 0.0
        self._measurement_wall_start = 0.0
        self._stopped: set[str] = set()
        self._backend_types = {rid: type(robot.slam) for rid, robot in coordinator.robots.items()}
        self._commands: list[dict] = []
        self._events: list[dict] = []
        self._steps: list[dict] = []
        self._trajectory: list[dict] = []

    @classmethod
    def from_scenario(cls, scenario_id: str, seed: int, *, horizon_s: float = DEFAULTS.horizon_sim_seconds,
                      collect: bool = True):
        """Construct the current ICP/Voronoi baseline with owned recovery streams."""
        from src.coordination.merge_strategies.icp_union import ICPUnionStrategy
        import src.slam.backends  # Register the requested backend; never use registry defaults.
        scene = load_scenario(scenario_id)
        sample = scene.sample(seed)
        positions = {p.robot_id: (p.x, p.y, p.z) for p in sample.spawn_poses}
        headings = {p.robot_id: p.yaw_rad for p in sample.spawn_poses}
        config = MultiRobotConfig(spawn_positions=positions, spawn_headings=headings,
                                  robot_ids=tuple(positions), launch_viewer=False,
                                  resolution=(DEFAULTS.sensor_width, DEFAULTS.sensor_height),
                                  sim_steps_per_frame=DEFAULTS.sim_steps_per_frame)
        bridge = MultiRobotBridge(config, model_factory=lambda: _benchmark_model(scene, positions))
        from src.bridge.sensor_types import CameraIntrinsics
        intrinsics = CameraIntrinsics.from_fov(*config.resolution)
        physics_dt = float(ET.fromstring(scene.mjcf_xml).find("option").get("timestep"))
        frame_dt = physics_dt * config.sim_steps_per_frame
        robots = {}
        try:
            for index, rid in enumerate(config.robot_ids):
                robots[rid] = RobotInstance.create(
                    rid, bridge, intrinsics, backend_name=DEFAULTS.slam_backend,
                    config=ExplorationConfig(voxel_resolution=DEFAULTS.map_resolution_m,
                                             skill_learning_enabled=False),
                    spawn_position=positions[rid], frame_dt=frame_dt,
                    recovery_rng=np.random.default_rng(np.random.SeedSequence([seed, 2, index])),
                    backend_kwargs={"cloud_config_key": "1"},
                )
            coordinator = Coordinator(bridge, robots, config,
                                      merger=ICPUnionStrategy(resolution=DEFAULTS.map_resolution_m))
            return cls(coordinator, bridge, scene.compiled_reference(),
                       coverage_config=CoverageConfig(horizon_s=horizon_s), collect=collect,
                       provenance={"sample": sample.to_dict(), "method": "legacy_voronoi",
                                   "recovery_streams": {rid: [seed, 2, i] for i, rid in enumerate(config.robot_ids)},
                                   "slam_backend": "icp", "merge_strategy": "icp_union", "cloud_config_key": "1",
                                   "odometry_rule": "body_origin_surface_svd_v2",
                                   "registration_sampling_rule": "bounded_voxel_refinement_v1",
                                   "exploration_config": asdict(robots[config.robot_ids[0]].exploration.config),
                                   "navigation_target_rule": "reachable_unreached_frontier_member_v2",
                                   "planned_goal": "preserve_exact_endpoint_v1",
                                   "route_lifecycle": "invalidate_on_rescan_v1",
                                   "navigation_pose": "estimated_body_from_camera_mount_v1",
                                   "gait_config": asdict(GaitParams()),
                                   "gait_rule": "bounded_swing_thigh_lift_v1",
                                   "gait_idle_rule": "standing_pose_phase_reset_v1",
                                   "floor_filter": "supported_observation_plane_v2",
                                   "planning_free_space": "observed_floor_and_trajectory_v1",
                                   "planning_clearance": "body_camera_envelope_continuous_segments_v2",
                                   "path_following": "align_heading_before_translation_v1",
                                   "recovery_rule": "commanded_progress_sim_time_v1"})
        except BaseException:
            bridge.stop()
            for robot in robots.values():
                robot.publisher.stop()
            raise

    def start(self) -> dict:
        if self._state != "new":
            raise RuntimeError("Episodes are single-use")
        self._wall_start = time.perf_counter()
        try:
            frames = self.coordinator.start()
            self._origin = self._frame_time(frames)
            ticks = self.config.horizon_s / self.bridge.frame_dt
            if not math.isclose(ticks, round(ticks), rel_tol=0, abs_tol=1e-8):
                raise ValueError("Horizon must be a whole number of sensor intervals")
            self._horizon_ticks = round(ticks)
            self._measurement_wall_start = time.perf_counter()
            if self.collect:
                ids = tuple(self.coordinator.robots)
                self.coverage = CoverageCollector(self.reference, ids, start_sim_time=self._origin, config=self.config)
                self.reliability = ReliabilityCollector(ids, start_sim_time=self._origin)
                self._classifier = _contacts(self.bridge)
            self._state = "running"
            self._capture(frames)
            return self.inspect()
        except BaseException as exc:
            self._invalid(exc)
            raise

    def _frame_time(self, frames) -> float:
        if set(frames) != set(self.coordinator.robots):
            raise ValueError("Every robot must have a synchronized sensor frame")
        times = {frame.sim_time for frame in frames.values()}
        if len(times) != 1 or not math.isfinite(next(iter(times))):
            raise ValueError("Sensor frames must share a finite capture time")
        return float(next(iter(times)))

    def _capture(self, frames) -> None:
        timestamp = self._frame_time(frames)
        self._elapsed = timestamp - self._origin
        states, observations = {}, {}
        positions = {rid: self.bridge.get_body_position(rid) for rid in self.coordinator.robots}
        self._trajectory.append({"elapsed_s": self._elapsed,
                                 "positions": {rid: p.tolist() for rid, p in positions.items()}})
        for rid, robot in self.coordinator.robots.items():
            status = self.bridge.get_runtime_status(rid)
            diagnostic = robot.exploration.measurement_state
            if status.disabled and rid not in self._stopped:
                self._stopped.add(rid)
                self.coordinator.deactivate_robot(rid)
                self._events.append({"elapsed_s": self._elapsed, "kind": "robot_disabled", "robot_id": rid})
                if self.collect:
                    self.coverage.stop_robot(rid, timestamp)
            if self.collect:
                states[rid] = RobotMetricState(
                    tuple(positions[rid]),
                    recovering=diagnostic["recovering"] or status.state.value == "recovering",
                    fallen=status.state.value == "fallen", goal_id=diagnostic["goal_id"],
                )
                if rid not in self._stopped:
                    observations[rid] = DepthObservation.from_frame(frames[rid], self.bridge.camera_intrinsics(rid))
        if self.collect:
            self.coverage.observe_batch(timestamp, observations)
            self.reliability.update(timestamp, states, self._classifier.pairs(self.bridge.mj_data))
            self._steps.append(self.coverage.snapshot())

    def advance(self) -> dict:
        if self._state != "running":
            raise RuntimeError("Episode is not running")
        try:
            tick = self.coordinator.advance(stop_on_termination=True)
            self._commands.append({"elapsed_s": tick.decision_sim_time - self._origin,
                                   "commands": {rid: command.to_wire() for rid, command in tick.commands.items()}})
            for rid, metrics in tick.metrics.items():
                robot = self.coordinator.robots[rid]
                diagnostic = robot.exploration.measurement_state
                if metrics.error:
                    self._events.append({"elapsed_s": self._elapsed, "kind": "exploration_error",
                                         "robot_id": rid, "message": metrics.error})
                if robot.exploration.slam_backend_type is not self._backend_types[rid] or diagnostic["tracking_status"] == "lost":
                    self._events.append({"elapsed_s": self._elapsed, "kind": "backend_failure", "robot_id": rid})
                    tick.termination_reason = "algorithm_error"
                if self.collect:
                    for attempt_id, success in diagnostic["planning_attempts"]:
                        self.reliability.record_planning_attempt(tick.decision_sim_time, rid, attempt_id, success=success)
                    for milliseconds in diagnostic["selection_latency_ms"]:
                        self.reliability.record_allocator_latency(tick.decision_sim_time, milliseconds)
            if tick.termination_reason is not None:
                self._finish(tick.termination_reason)
            else:
                self._capture(tick.frames)
                if self.coordinator.step_count == self._horizon_ticks:
                    self._finish("horizon")
            return self.inspect()
        except BaseException as exc:
            self._invalid(exc)
            raise

    def _finish(self, reason: str) -> None:
        wall = time.perf_counter()
        self._result = {
            "valid": True, "termination_reason": reason, "elapsed_s": self._elapsed,
            "coverage": self.coverage.finalize(reason) if self.collect else None,
            "reliability": self.reliability.summary() if self.collect else None,
            "wall_seconds": wall - self._wall_start,
            "measurement_wall_seconds": wall - self._measurement_wall_start,
            "real_time_factor": self._elapsed / max(wall - self._measurement_wall_start, 1e-12),
            "peak_process_rss_bytes": _peak_process_rss_bytes(), "memory_scope": "process_lifetime",
            "settling_sim_seconds": self.bridge.settled_sim_time,
            "frame_dt": self.bridge.frame_dt, "contact_cadence": "sensor_frames",
            "allocator_latency_scope": "per_robot_frontier_candidate_selection",
            "provenance": self.provenance,
        }
        self._state = "finished"
        self.close()

    def _invalid(self, exc) -> None:
        self._result = {"valid": False, "termination_reason": "infrastructure_error",
                        "error_type": type(exc).__name__, "error": str(exc), "elapsed_s": self._elapsed}
        self._state = "failed"
        self.close()

    def inspect(self, *, include_history: bool = False) -> dict:
        state = {"state": self._state, "elapsed_s": self._elapsed, "result": self._result}
        if include_history:
            state.update(commands=self._commands, events=self._events, steps=self._steps,
                         trajectory=self._trajectory)
        return copy.deepcopy(state)

    def close(self) -> None:
        self.coordinator.close()
        if self._state in {"new", "running"}:
            self._state = "closed"
            self._result = {"valid": False, "termination_reason": "interrupted", "elapsed_s": self._elapsed}
        if self.coordinator.cleanup_errors:
            self._result = {**(self._result or {}), "valid": False,
                            "cleanup_errors": list(self.coordinator.cleanup_errors)}

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
