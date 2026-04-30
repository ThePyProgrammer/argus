"""Shared controller dispatch and control-target application helpers.

This module is intentionally MuJoCo-free. Callers own bridge/environment
lifecycle and physics stepping; these helpers only construct typed commands,
validate controller outputs, and apply already validated targets to opaque
``data.ctrl`` sinks.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from src.locomotion.controllers import (
    ControllerResult,
    LocomotionCommand,
    LocomotionController,
    validate_controller_target,
)


def command_from_velocity(
    linear: Sequence[float] | np.ndarray,
    angular: float,
    metadata: dict[str, Any] | None = None,
) -> LocomotionCommand:
    """Build a typed command from bridge velocity buffers.

    Short linear velocity arrays preserve the current bridge semantics:
    missing ``vx`` and ``vy`` entries default independently to ``0.0``.
    """

    vx = float(linear[0]) if len(linear) > 0 else 0.0
    vy = float(linear[1]) if len(linear) > 1 else 0.0
    return LocomotionCommand(
        vx=vx,
        vy=vy,
        yaw_rate=float(angular),
        metadata=None if metadata is None else dict(metadata),
    )


def compute_controller_action(
    controller: LocomotionController,
    observation: dict[str, Any],
    command: LocomotionCommand,
    dt: float,
) -> ControllerResult:
    """Call a controller and return a copied, validated result.

    Validation happens at the controller-to-dispatch trust boundary before any
    caller can write the target to physics controls.
    """

    result = controller.compute(observation, command, dt)
    validated = validate_controller_target(result.action)
    return ControllerResult(action=validated, metadata=dict(result.metadata))


def apply_controller_target(
    data: Any,
    target: Sequence[float] | np.ndarray,
    ctrl_indices: Sequence[int] | None = None,
) -> np.ndarray:
    """Validate and apply one Go2 controller target to a control sink.

    With ``ctrl_indices is None``, the full target is written to ``data.ctrl[:]``.
    With indices supplied, exactly twelve actuator indices are required and each
    target element is written to the paired actuator slot. All validation is done
    before the first ``data.ctrl`` mutation.
    """

    validated = validate_controller_target(target)
    if ctrl_indices is not None and len(ctrl_indices) != validated.shape[0]:
        raise ValueError(
            f"ctrl_indices must contain exactly {validated.shape[0]} entries, "
            f"got {len(ctrl_indices)}."
        )

    if ctrl_indices is None:
        data.ctrl[:] = validated
    else:
        indices = [int(idx) for idx in ctrl_indices]
        if len(set(indices)) != len(indices):
            raise ValueError("ctrl_indices must not contain duplicates.")
        ctrl_size = int(data.ctrl.shape[0])
        bad_indices = [idx for idx in indices if idx < 0 or idx >= ctrl_size]
        if bad_indices:
            raise ValueError(f"ctrl_indices out of range for data.ctrl size {ctrl_size}: {bad_indices}")
        for i, act_id in enumerate(indices):
            data.ctrl[act_id] = validated[i]
    return validated


def dispatch_controller(
    controller: LocomotionController,
    observation: dict[str, Any],
    command: LocomotionCommand,
    dt: float,
    data: Any | None = None,
    ctrl_indices: Sequence[int] | None = None,
) -> ControllerResult:
    """Compute a validated controller action and optionally apply it to ``data.ctrl``."""

    result = compute_controller_action(controller, observation, command, dt)
    if data is not None:
        applied = apply_controller_target(data, result.action, ctrl_indices=ctrl_indices)
        return ControllerResult(action=applied, metadata=dict(result.metadata))
    return result
