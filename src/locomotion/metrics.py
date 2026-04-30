"""Core locomotion benchmark metrics and episode summaries."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.locomotion.actions import joint_position_bounds
from src.locomotion.scenarios import ScenarioSample


FOOT_GEOM_NAMES: tuple[str, ...] = ("FL", "FR", "RL", "RR")


@dataclass(frozen=True)
class Go2FootMapping:
    """Strict mapping from canonical Go2 foot names to MuJoCo geom ids."""

    foot_geom_ids: dict[str, int]

    @classmethod
    def from_mujoco_model(cls, model: Any) -> "Go2FootMapping":
        """Resolve exactly FL, FR, RL, and RR foot geoms from a MuJoCo model."""
        import mujoco

        foot_geom_ids: dict[str, int] = {}
        for name in FOOT_GEOM_NAMES:
            geom_id = int(mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name))
            if geom_id < 0:
                raise ValueError(f"Missing required Go2 foot geom '{name}'")
            foot_geom_ids[name] = geom_id
        ids = list(foot_geom_ids.values())
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate Go2 foot geom ids resolved: {ids}")
        return cls(foot_geom_ids=foot_geom_ids)


_JOINT_NAMES: tuple[str, ...] = (
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
)
_COMMAND_KEYS: tuple[str, ...] = ("vx", "vy", "yaw_rate")
_REQUIRED_FAMILIES: tuple[str, ...] = ("command_tracking", "stability", "action_quality", "contact_terrain")


@dataclass(frozen=True)
class LocomotionMetricsConfig:
    """Configurable thresholds for locomotion metric collection."""

    history_size: int = 1000
    max_abs_roll_rad: float = 0.8
    max_abs_pitch_rad: float = 0.8
    nominal_base_height_m: float = 0.30
    min_base_height_m: float = 0.18
    base_height_tolerance_m: float = 0.12
    min_progress_m_per_s: float = 0.03
    progress_window_steps: int = 25
    joint_limit_tolerance_rad: float = 1e-3
    saturation_margin_fraction: float = 0.05

    def __post_init__(self) -> None:
        if self.history_size < 1:
            raise ValueError("history_size must be >= 1")
        positive_fields = {
            "max_abs_roll_rad": self.max_abs_roll_rad,
            "max_abs_pitch_rad": self.max_abs_pitch_rad,
            "nominal_base_height_m": self.nominal_base_height_m,
            "min_base_height_m": self.min_base_height_m,
            "base_height_tolerance_m": self.base_height_tolerance_m,
            "min_progress_m_per_s": self.min_progress_m_per_s,
            "joint_limit_tolerance_rad": self.joint_limit_tolerance_rad,
        }
        for name, value in positive_fields.items():
            if not np.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be a positive finite value")
        if self.progress_window_steps < 1:
            raise ValueError("progress_window_steps must be >= 1")
        if not (0.0 < self.saturation_margin_fraction < 0.5):
            raise ValueError("saturation_margin_fraction must be between 0.0 and 0.5")


@dataclass(frozen=True)
class LocomotionMetricStep:
    """One compact, immutable per-step locomotion metrics record."""

    command_tracking: dict[str, Any]
    stability: dict[str, Any]
    action_quality: dict[str, Any]
    contact_terrain: dict[str, Any]
    failure_reason: str | None = None


@dataclass(frozen=True)
class LocomotionEpisodeSummary:
    """Aggregated locomotion metrics for one episode."""

    command_tracking: dict[str, Any]
    stability: dict[str, Any]
    action_quality: dict[str, Any]
    contact_terrain: dict[str, Any]
    success: bool
    failure_reason: str | None
    step_count: int


class LocomotionMetricsCollector:
    """Collect bounded per-step locomotion records and episode summaries."""

    def __init__(self, config: LocomotionMetricsConfig | None = None) -> None:
        self.config = config or LocomotionMetricsConfig()
        self._steps: deque[LocomotionMetricStep] = deque(maxlen=self.config.history_size)
        self._baseline: LocomotionEpisodeSummary | None = None
        self._failure_reason: str | None = None
        self._distance_before_failure_m: float | None = None
        self._total_steps_seen = 0
        self._previous_foot_positions: dict[str, np.ndarray] | None = None
        self._previous_foot_contacts: dict[str, bool] | None = None
        self._contact_counts: dict[str, int] = dict.fromkeys(FOOT_GEOM_NAMES, 0)
        self._slip_history: dict[str, list[float]] = {name: [] for name in FOOT_GEOM_NAMES}
        self._clearance_history: dict[str, list[float]] = {name: [] for name in FOOT_GEOM_NAMES}
        self._scenario_failed = False

    @property
    def baseline(self) -> LocomotionEpisodeSummary | None:
        """The last captured episode-summary baseline, preserved across resets."""
        return self._baseline

    @property
    def history_length(self) -> int:
        """Number of retained per-step records in the bounded history."""
        return len(self._steps)

    def reset_episode(self) -> None:
        """Start a new episode while preserving any captured baseline snapshot."""
        self._steps.clear()
        self._failure_reason = None
        self._distance_before_failure_m = None
        self._total_steps_seen = 0
        self._previous_foot_positions = None
        self._previous_foot_contacts = None
        self._contact_counts = dict.fromkeys(FOOT_GEOM_NAMES, 0)
        self._slip_history = {name: [] for name in FOOT_GEOM_NAMES}
        self._clearance_history = {name: [] for name in FOOT_GEOM_NAMES}
        self._scenario_failed = False

    def capture_baseline(self) -> None:
        """Snapshot the current episode summary as the comparison baseline."""
        self._baseline = self.episode_summary() if self._steps else None

    def record_step(
        self,
        *,
        desired_command: Sequence[float] | np.ndarray,
        measured_base_velocity: Sequence[float] | np.ndarray,
        roll_rad: float,
        pitch_rad: float,
        base_height_m: float,
        base_xy_position: Sequence[float] | np.ndarray,
        action_target: Sequence[float] | np.ndarray,
        previous_action_target: Sequence[float] | np.ndarray,
        previous_previous_action_target: Sequence[float] | np.ndarray,
        joint_qpos: Sequence[float] | np.ndarray,
        joint_qvel: Sequence[float] | np.ndarray,
        dt: float,
        contact_terrain_payload: Mapping[str, Any] | None = None,
        foot_positions_world: Mapping[str, Sequence[float] | np.ndarray] | None = None,
        foot_contacts: Mapping[str, bool] | None = None,
        terrain_height_m: float | Mapping[str, float] = 0.0,
        scenario_failed: bool | None = None,
    ) -> LocomotionMetricStep:
        """Validate a simulation snapshot and append one locomotion metric record."""
        desired = _as_finite_vector(desired_command, (3,), "desired_command")
        measured = _as_finite_vector(measured_base_velocity, (3,), "measured_base_velocity")
        xy = _as_finite_vector(base_xy_position, (2,), "base_xy_position")
        action = _as_finite_vector(action_target, (12,), "action_target")
        previous = _as_finite_vector(previous_action_target, (12,), "previous_action_target")
        previous_previous = _as_finite_vector(
            previous_previous_action_target,
            (12,),
            "previous_previous_action_target",
        )
        qpos = _as_finite_vector(joint_qpos, (12,), "joint_qpos")
        qvel = _as_finite_vector(joint_qvel, (12,), "joint_qvel")
        roll = _as_finite_scalar(roll_rad, "roll_rad")
        pitch = _as_finite_scalar(pitch_rad, "pitch_rad")
        height = _as_finite_scalar(base_height_m, "base_height_m")
        delta_t = _as_finite_scalar(dt, "dt")
        if delta_t <= 0.0:
            raise ValueError("dt must be positive")

        command_tracking = _command_tracking_payload(desired, measured)
        stability, failure_reason = self._stability_payload(roll, pitch, height, xy, delta_t)
        action_quality = self._action_quality_payload(action, previous, previous_previous, qpos, qvel, delta_t)
        if foot_positions_world is not None or foot_contacts is not None:
            contact_terrain = self._contact_terrain_payload(
                foot_positions_world=foot_positions_world,
                foot_contacts=foot_contacts,
                terrain_height_m=terrain_height_m,
                scenario_failed=scenario_failed,
                dt=delta_t,
            )
        else:
            contact_terrain = _compact_mapping(contact_terrain_payload or {})

        if self._failure_reason is None and failure_reason is not None:
            self._failure_reason = failure_reason
            self._distance_before_failure_m = float(stability["distance_xy_m"])

        step = LocomotionMetricStep(
            command_tracking=command_tracking,
            stability=stability,
            action_quality=action_quality,
            contact_terrain=contact_terrain,
            failure_reason=failure_reason,
        )
        self._steps.append(step)
        self._total_steps_seen += 1
        return step

    def latest_info_payload(self) -> dict[str, Any]:
        """Return compact nested per-step metrics for Gymnasium info."""
        if not self._steps:
            return {
                "command_tracking": {},
                "stability": {},
                "action_quality": {},
                "contact_terrain": {},
            }
        latest = self._steps[-1]
        return {
            "command_tracking": dict(latest.command_tracking),
            "stability": dict(latest.stability),
            "action_quality": dict(latest.action_quality),
            "contact_terrain": dict(latest.contact_terrain),
        }

    def episode_summary(self) -> LocomotionEpisodeSummary:
        """Aggregate retained episode records into summary families."""
        steps = list(self._steps)
        command_tracking = self._command_tracking_summary(steps)
        stability = self._stability_summary(steps)
        action_quality = self._action_quality_summary(steps)
        contact_terrain = self._contact_terrain_summary(steps)
        return LocomotionEpisodeSummary(
            command_tracking=command_tracking,
            stability=stability,
            action_quality=action_quality,
            contact_terrain=contact_terrain,
            success=self._failure_reason is None,
            failure_reason=self._failure_reason,
            step_count=self._total_steps_seen,
        )

    def _stability_payload(
        self,
        roll: float,
        pitch: float,
        height: float,
        xy: np.ndarray,
        dt: float,
    ) -> tuple[dict[str, Any], str | None]:
        distance = float(np.linalg.norm(xy))
        failure_reason: str | None = None
        if abs(roll) > self.config.max_abs_roll_rad:
            failure_reason = "roll_limit"
        elif abs(pitch) > self.config.max_abs_pitch_rad:
            failure_reason = "pitch_limit"
        elif height < self.config.min_base_height_m:
            failure_reason = "base_height_low"
        elif self._progress_stalled(distance, dt):
            failure_reason = "progress_stalled"

        return {
            "roll_rad": roll,
            "pitch_rad": pitch,
            "base_height_m": height,
            "base_height_deviation_m": height - self.config.nominal_base_height_m,
            "distance_xy_m": distance,
            "failure_reason": failure_reason,
        }, failure_reason

    def _progress_stalled(self, current_distance: float, dt: float) -> bool:
        if len(self._steps) < self.config.progress_window_steps:
            return False
        window = list(self._steps)[-self.config.progress_window_steps :]
        start_distance = float(window[0].stability["distance_xy_m"])
        elapsed = max(float(len(window)) * dt, dt)
        return (current_distance - start_distance) / elapsed < self.config.min_progress_m_per_s

    def _action_quality_payload(
        self,
        action: np.ndarray,
        previous: np.ndarray,
        previous_previous: np.ndarray,
        qpos: np.ndarray,
        qvel: np.ndarray,
        dt: float,
    ) -> dict[str, Any]:
        low, high = joint_position_bounds()
        low64 = low.astype(np.float64)
        high64 = high.astype(np.float64)
        tolerance = self.config.joint_limit_tolerance_rad
        action_delta = action - previous
        jerk_proxy = action - (2.0 * previous) + previous_previous
        commanded_violations = (action < (low64 - tolerance)) | (action > (high64 + tolerance))
        observed_violations = (qpos < (low64 - tolerance)) | (qpos > (high64 + tolerance))
        ranges = high64 - low64
        margin = ranges * self.config.saturation_margin_fraction
        near_limit = (action <= (low64 + margin)) | (action >= (high64 - margin))
        clipped_targets = (action < (low64 - tolerance)) | (action > (high64 + tolerance))
        effort_proxy = float(np.sum(np.abs(action_delta) * np.abs(qvel) * dt))
        saturation_count = int(np.count_nonzero(near_limit))
        return {
            "action_delta_norm": float(np.linalg.norm(action_delta)),
            "action_jerk_proxy_norm": float(np.linalg.norm(jerk_proxy)),
            "commanded_joint_limit_violation_count": int(np.count_nonzero(commanded_violations)),
            "observed_joint_limit_violation_count": int(np.count_nonzero(observed_violations)),
            "commanded_joint_limit_violations_by_joint": _counts_by_joint(commanded_violations),
            "observed_joint_limit_violations_by_joint": _counts_by_joint(observed_violations),
            "near_joint_limit_count": saturation_count,
            "clipped_target_count": int(np.count_nonzero(clipped_targets)),
            "position_servo_effort_proxy": effort_proxy,
            "position_target_saturation_proxy": saturation_count,
        }

    def _command_tracking_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
        if not steps:
            return {f"{key}_rmse": 0.0 for key in _COMMAND_KEYS} | {"tracking_error_rmse": 0.0}
        summary: dict[str, Any] = {}
        rmse_values = []
        for key in _COMMAND_KEYS:
            errors = np.array([step.command_tracking["signed_error"][key] for step in steps], dtype=np.float64)
            absolute = np.abs(errors)
            rmse = float(np.sqrt(np.mean(np.square(errors))))
            rmse_values.append(rmse)
            summary[f"{key}_rmse"] = rmse
            summary[f"{key}_mean_abs_error"] = float(np.mean(absolute))
            summary[f"{key}_max_abs_error"] = float(np.max(absolute))
        summary["tracking_error_rmse"] = float(np.linalg.norm(rmse_values))
        return summary

    def _stability_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
        if not steps:
            return {
                "max_abs_roll_rad": 0.0,
                "max_abs_pitch_rad": 0.0,
                "min_base_height_m": 0.0,
                "max_base_height_deviation_m": 0.0,
                "distance_xy_m": 0.0,
                "distance_before_failure_m": None,
                "fall_count": 0,
                "fall_rate": 0.0,
            }
        fall_count = 1 if self._failure_reason is not None else 0
        return {
            "max_abs_roll_rad": float(max(abs(step.stability["roll_rad"]) for step in steps)),
            "max_abs_pitch_rad": float(max(abs(step.stability["pitch_rad"]) for step in steps)),
            "min_base_height_m": float(min(step.stability["base_height_m"] for step in steps)),
            "max_base_height_deviation_m": float(
                max(abs(step.stability["base_height_deviation_m"]) for step in steps)
            ),
            "distance_xy_m": float(steps[-1].stability["distance_xy_m"]),
            "distance_before_failure_m": self._distance_before_failure_m,
            "fall_count": fall_count,
            "fall_rate": 1.0 if fall_count else 0.0,
        }

    def _action_quality_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
        if not steps:
            return {
                "action_delta_norm_mean": 0.0,
                "action_jerk_proxy_norm_mean": 0.0,
                "position_servo_effort_proxy_mean": 0.0,
                "position_servo_effort_proxy_total": 0.0,
                "position_target_saturation_proxy_total": 0,
                "near_joint_limit_count_total": 0,
                "clipped_target_count_total": 0,
                "commanded_joint_limit_violation_count_total": 0,
                "observed_joint_limit_violation_count_total": 0,
                "commanded_joint_limit_violations_by_joint": dict.fromkeys(_JOINT_NAMES, 0),
                "observed_joint_limit_violations_by_joint": dict.fromkeys(_JOINT_NAMES, 0),
            }
        return {
            "action_delta_norm_mean": _mean_metric(steps, "action_delta_norm"),
            "action_delta_norm_max": _max_metric(steps, "action_delta_norm"),
            "action_jerk_proxy_norm_mean": _mean_metric(steps, "action_jerk_proxy_norm"),
            "action_jerk_proxy_norm_max": _max_metric(steps, "action_jerk_proxy_norm"),
            "position_servo_effort_proxy_mean": _mean_metric(steps, "position_servo_effort_proxy"),
            "position_servo_effort_proxy_total": _sum_metric(steps, "position_servo_effort_proxy"),
            "position_target_saturation_proxy_total": int(_sum_metric(steps, "position_target_saturation_proxy")),
            "near_joint_limit_count_total": int(_sum_metric(steps, "near_joint_limit_count")),
            "clipped_target_count_total": int(_sum_metric(steps, "clipped_target_count")),
            "commanded_joint_limit_violation_count_total": int(
                _sum_metric(steps, "commanded_joint_limit_violation_count")
            ),
            "observed_joint_limit_violation_count_total": int(
                _sum_metric(steps, "observed_joint_limit_violation_count")
            ),
            "commanded_joint_limit_violations_by_joint": _sum_joint_counts(
                steps,
                "commanded_joint_limit_violations_by_joint",
            ),
            "observed_joint_limit_violations_by_joint": _sum_joint_counts(
                steps,
                "observed_joint_limit_violations_by_joint",
            ),
        }

    def _contact_terrain_payload(
        self,
        *,
        foot_positions_world: Mapping[str, Sequence[float] | np.ndarray] | None,
        foot_contacts: Mapping[str, bool] | None,
        terrain_height_m: float | Mapping[str, float],
        scenario_failed: bool | None,
        dt: float,
    ) -> dict[str, Any]:
        positions = _validate_foot_positions(foot_positions_world)
        contacts = _validate_foot_contacts(foot_contacts)
        terrain_heights = _terrain_heights_by_foot(terrain_height_m)
        if scenario_failed is not None:
            self._scenario_failed = self._scenario_failed or bool(scenario_failed)

        per_foot_contact: dict[str, bool] = {}
        slip: dict[str, float] = {}
        clearance: dict[str, float] = {}
        transition: dict[str, str] = {}
        previous_positions = self._previous_foot_positions
        previous_contacts = self._previous_foot_contacts or dict.fromkeys(FOOT_GEOM_NAMES, False)

        for name in FOOT_GEOM_NAMES:
            current_contact = bool(contacts[name])
            per_foot_contact[name] = current_contact
            if current_contact:
                self._contact_counts[name] += 1
            terrain_height = terrain_heights[name]
            clearance[name] = float(positions[name][2] - terrain_height)
            self._clearance_history[name].append(clearance[name])

            if current_contact and previous_positions is not None:
                delta_xy = positions[name][:2] - previous_positions[name][:2]
                slip[name] = float(np.linalg.norm(delta_xy) / dt)
            else:
                slip[name] = 0.0
            self._slip_history[name].append(slip[name])

            was_contact = bool(previous_contacts[name])
            if current_contact and not was_contact:
                transition[name] = "touchdown"
            elif was_contact and not current_contact:
                transition[name] = "liftoff"
            else:
                transition[name] = "none"

        self._previous_foot_positions = {name: positions[name].copy() for name in FOOT_GEOM_NAMES}
        self._previous_foot_contacts = dict(per_foot_contact)
        return {
            "per_foot_contact": per_foot_contact,
            "foot_xy_velocity_when_contact": slip,
            "foot_clearance_m": clearance,
            "contact_transition": transition,
        }

    def _contact_terrain_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
        if not steps:
            return {}
        step_count = max(self._total_steps_seen, 1)
        duty_factor = {
            name: float(self._contact_counts[name] / step_count) for name in FOOT_GEOM_NAMES
        }
        slip_mean = {
            name: float(np.mean(self._slip_history[name])) if self._slip_history[name] else 0.0
            for name in FOOT_GEOM_NAMES
        }
        slip_max = {
            name: float(np.max(self._slip_history[name])) if self._slip_history[name] else 0.0
            for name in FOOT_GEOM_NAMES
        }
        clearance_min = {
            name: float(np.min(self._clearance_history[name])) if self._clearance_history[name] else 0.0
            for name in FOOT_GEOM_NAMES
        }
        clearance_max = {
            name: float(np.max(self._clearance_history[name])) if self._clearance_history[name] else 0.0
            for name in FOOT_GEOM_NAMES
        }
        return {
            **dict(steps[-1].contact_terrain),
            "duty_factor": duty_factor,
            "slip_mean_m_per_s": slip_mean,
            "slip_max_m_per_s": slip_max,
            "clearance_min_m": clearance_min,
            "clearance_max_m": clearance_max,
            "gait_symmetry_contact_balance": float(max(duty_factor.values()) - min(duty_factor.values())),
            "scenario_success": self._failure_reason is None and not self._scenario_failed,
        }


def terrain_height_at(sample: ScenarioSample | None, x: float, y: float) -> float:
    """Return terrain height at world XY for a sampled locomotion scenario."""
    x_value = _as_finite_scalar(x, "x")
    y_value = _as_finite_scalar(y, "y")
    if sample is None:
        return 0.0
    params = sample.terrain_parameters
    terrain_kind = str(params.get("terrain_kind", "plane"))
    if terrain_kind == "plane":
        return 0.0
    if terrain_kind == "slope":
        slope = _as_finite_scalar(params.get("slope_radians", 0.0), "slope_radians")
        z_offset = _as_finite_scalar(params.get("slope_z_offset", -0.04), "slope_z_offset")
        return float(np.tan(slope) * x_value + z_offset)
    if terrain_kind == "heightfield":
        return _heightfield_height_at(params, x_value, y_value)
    raise ValueError(f"Unknown terrain_kind: {terrain_kind}")


def foot_contact_payload_from_mujoco(
    mapping: Go2FootMapping,
    data: Any,
    sample: ScenarioSample | None,
) -> dict[str, Any]:
    """Build collector contact inputs from MuJoCo geom positions and contacts."""
    inverse = {geom_id: name for name, geom_id in mapping.foot_geom_ids.items()}
    foot_positions_world = {
        name: np.asarray(data.geom_xpos[geom_id], dtype=np.float64).copy()
        for name, geom_id in mapping.foot_geom_ids.items()
    }
    foot_contacts = dict.fromkeys(FOOT_GEOM_NAMES, False)
    for idx in range(int(getattr(data, "ncon", 0))):
        contact = data.contact[idx]
        for geom_id in (int(contact.geom1), int(contact.geom2)):
            foot_name = inverse.get(geom_id)
            if foot_name is not None:
                foot_contacts[foot_name] = True
    terrain_height_m = {
        name: terrain_height_at(sample, float(position[0]), float(position[1]))
        for name, position in foot_positions_world.items()
    }
    return {
        "foot_positions_world": foot_positions_world,
        "foot_contacts": foot_contacts,
        "terrain_height_m": terrain_height_m,
    }


def _heightfield_height_at(params: Mapping[str, Any], x: float, y: float) -> float:
    size = int(params.get("heightfield_size", 0))
    data = params.get("heightfield_data")
    if size <= 0 or data is None:
        raise ValueError("heightfield terrain requires heightfield_size and heightfield_data")
    heights = np.asarray(data, dtype=np.float64).reshape((size, size))
    extent_x = _as_finite_scalar(params.get("heightfield_extent_x", 5.0), "heightfield_extent_x")
    extent_y = _as_finite_scalar(params.get("heightfield_extent_y", 5.0), "heightfield_extent_y")
    if extent_x <= 0.0 or extent_y <= 0.0:
        raise ValueError("heightfield extents must be positive")
    u = np.clip((x + extent_x) / (2.0 * extent_x), 0.0, 1.0) * (size - 1)
    v = np.clip((y + extent_y) / (2.0 * extent_y), 0.0, 1.0) * (size - 1)
    x0 = int(np.floor(u))
    y0 = int(np.floor(v))
    x1 = min(x0 + 1, size - 1)
    y1 = min(y0 + 1, size - 1)
    tx = float(u - x0)
    ty = float(v - y0)
    z00 = heights[y0, x0]
    z10 = heights[y0, x1]
    z01 = heights[y1, x0]
    z11 = heights[y1, x1]
    return float((1.0 - tx) * (1.0 - ty) * z00 + tx * (1.0 - ty) * z10 + (1.0 - tx) * ty * z01 + tx * ty * z11)


def _command_tracking_payload(desired: np.ndarray, measured: np.ndarray) -> dict[str, Any]:
    signed_error = measured - desired
    absolute_error = np.abs(signed_error)
    return {
        "desired": _vector_dict(desired),
        "measured": _vector_dict(measured),
        "signed_error": _vector_dict(signed_error),
        "absolute_error": _vector_dict(absolute_error),
        "tracking_error_norm": float(np.linalg.norm(signed_error)),
    }


def _vector_dict(values: np.ndarray) -> dict[str, float]:
    return {key: float(values[idx]) for idx, key in enumerate(_COMMAND_KEYS)}


def _as_finite_vector(value: Sequence[float] | np.ndarray, shape: tuple[int, ...], name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=np.float64).copy()
    if vector.shape != shape:
        raise ValueError(f"{name} must have shape {shape}, got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def _as_finite_scalar(value: float, name: str) -> float:
    scalar = float(value)
    if not np.isfinite(scalar):
        raise ValueError(f"{name} must be finite")
    return scalar


def _counts_by_joint(mask: np.ndarray) -> dict[str, int]:
    return {joint: int(bool(mask[idx])) for idx, joint in enumerate(_JOINT_NAMES)}


def _validate_foot_positions(
    foot_positions_world: Mapping[str, Sequence[float] | np.ndarray] | None,
) -> dict[str, np.ndarray]:
    if foot_positions_world is None:
        raise ValueError("foot_positions_world is required when recording contact terrain metrics")
    positions: dict[str, np.ndarray] = {}
    for name in FOOT_GEOM_NAMES:
        if name not in foot_positions_world:
            raise ValueError(f"Missing foot position for {name}")
        positions[name] = _as_finite_vector(foot_positions_world[name], (3,), f"foot_positions_world[{name}]")
    return positions


def _validate_foot_contacts(foot_contacts: Mapping[str, bool] | None) -> dict[str, bool]:
    if foot_contacts is None:
        raise ValueError("foot_contacts is required when recording contact terrain metrics")
    contacts: dict[str, bool] = {}
    for name in FOOT_GEOM_NAMES:
        if name not in foot_contacts:
            raise ValueError(f"Missing foot contact for {name}")
        contacts[name] = bool(foot_contacts[name])
    return contacts


def _terrain_heights_by_foot(terrain_height_m: float | Mapping[str, float]) -> dict[str, float]:
    if isinstance(terrain_height_m, Mapping):
        heights: dict[str, float] = {}
        for name in FOOT_GEOM_NAMES:
            if name not in terrain_height_m:
                raise ValueError(f"Missing terrain height for {name}")
            heights[name] = _as_finite_scalar(terrain_height_m[name], f"terrain_height_m[{name}]")
        return heights
    scalar = _as_finite_scalar(terrain_height_m, "terrain_height_m")
    return dict.fromkeys(FOOT_GEOM_NAMES, scalar)


def _compact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in payload.items():
        compact[str(key)] = _compact_value(value)
    return compact


def _compact_value(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        if not np.all(np.isfinite(value)):
            raise ValueError("contact_terrain_payload arrays must contain only finite values")
        return value.astype(float).tolist()
    if isinstance(value, Mapping):
        return _compact_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_compact_value(item) for item in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    scalar = float(value)
    if not np.isfinite(scalar):
        raise ValueError("contact_terrain_payload scalars must be finite")
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return scalar


def _mean_metric(steps: list[LocomotionMetricStep], key: str) -> float:
    return float(np.mean([step.action_quality[key] for step in steps]))


def _max_metric(steps: list[LocomotionMetricStep], key: str) -> float:
    return float(np.max([step.action_quality[key] for step in steps]))


def _sum_metric(steps: list[LocomotionMetricStep], key: str) -> float:
    return float(np.sum([step.action_quality[key] for step in steps]))


def _sum_joint_counts(steps: list[LocomotionMetricStep], key: str) -> dict[str, int]:
    totals = dict.fromkeys(_JOINT_NAMES, 0)
    for step in steps:
        for joint, count in step.action_quality[key].items():
            totals[joint] += int(count)
    return totals
