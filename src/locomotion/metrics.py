"""Core locomotion benchmark metrics and episode summaries."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.locomotion.actions import joint_position_bounds


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

    def _contact_terrain_summary(self, steps: list[LocomotionMetricStep]) -> dict[str, Any]:
        if not steps:
            return {}
        return dict(steps[-1].contact_terrain)


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
