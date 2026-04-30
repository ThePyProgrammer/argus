"""Tests for shared locomotion controller dispatch and control-target application."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from src.locomotion.controllers import ControllerResult, LocomotionCommand
from src.locomotion.controller_dispatch import (
    apply_controller_target,
    command_from_velocity,
    dispatch_controller,
)


class FakeData:
    def __init__(self, size: int = 12) -> None:
        self.ctrl = np.full(size, -1.0, dtype=np.float64)


class FakeController:
    CAPABILITIES = {"family": "fake", "action_mode": "velocity_command"}
    PARAMETER_SCHEMA: dict[str, Any] = {}

    def __init__(self, action: np.ndarray | None = None) -> None:
        self.action = np.arange(12, dtype=np.float64) if action is None else action
        self.calls: list[tuple[dict[str, Any], LocomotionCommand, float]] = []

    def reset(self, seed: int | None = None) -> None:
        del seed

    def compute(
        self,
        observation: dict[str, Any],
        command: LocomotionCommand,
        dt: float,
    ) -> ControllerResult:
        self.calls.append((observation, command, dt))
        return ControllerResult(
            action=self.action,
            metadata={"controller_id": "fake", "action_mode": "velocity_command"},
        )

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


def test_command_from_velocity_preserves_bridge_defaults() -> None:
    command = command_from_velocity(np.array([0.4, -0.2]), 0.3)
    assert command == LocomotionCommand(vx=0.4, vy=-0.2, yaw_rate=0.3, metadata=None)

    empty = command_from_velocity([], 0.1)
    assert empty.vx == 0.0
    assert empty.vy == 0.0
    assert empty.yaw_rate == 0.1

    short = command_from_velocity([0.5], -0.2)
    assert short.vx == 0.5
    assert short.vy == 0.0
    assert short.yaw_rate == -0.2


def test_command_from_velocity_preserves_metadata_copy() -> None:
    metadata = {"robot_id": "go2_0"}
    command = command_from_velocity([0.1, 0.2], 0.3, metadata=metadata)

    assert command.metadata == metadata
    assert command.metadata is not metadata


def test_apply_controller_target_writes_full_ctrl_slice() -> None:
    fake_data = FakeData()
    target = np.arange(12, dtype=np.float64)

    validated = apply_controller_target(fake_data, target)

    np.testing.assert_allclose(validated, target)
    np.testing.assert_allclose(fake_data.ctrl, target)
    assert validated.dtype == np.float64


def test_apply_controller_target_writes_ctrl_indices_only() -> None:
    fake_data = FakeData(size=20)
    original = fake_data.ctrl.copy()
    target = np.arange(12, dtype=np.float64)
    ctrl_indices = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    validated = apply_controller_target(fake_data, target, ctrl_indices=ctrl_indices)

    np.testing.assert_allclose(validated, target)
    for i, act_id in enumerate(ctrl_indices):
        assert fake_data.ctrl[act_id] == target[i]
    untouched = [idx for idx in range(fake_data.ctrl.shape[0]) if idx not in ctrl_indices]
    np.testing.assert_allclose(fake_data.ctrl[untouched], original[untouched])


@pytest.mark.parametrize(
    "bad_target",
    [
        np.arange(3, dtype=np.float64),
        np.arange(13, dtype=np.float64),
        np.array([np.nan] + [0.0] * 11, dtype=np.float64),
        np.array([np.inf] + [0.0] * 11, dtype=np.float64),
    ],
)
def test_apply_controller_target_rejects_invalid_without_mutating_ctrl(bad_target: np.ndarray) -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError):
        apply_controller_target(
            fake_data,
            bad_target,
            ctrl_indices=[3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        )

    np.testing.assert_allclose(fake_data.ctrl, before)


def test_apply_controller_target_rejects_wrong_ctrl_indices_count_without_mutating_ctrl() -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError, match="ctrl_indices"):
        apply_controller_target(fake_data, np.arange(12, dtype=np.float64), ctrl_indices=[3, 4])

    np.testing.assert_allclose(fake_data.ctrl, before)


@pytest.mark.parametrize(
    "bad_indices, message",
    [
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20], "out of range"),
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1], "out of range"),
        ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10], "duplicates"),
    ],
)
def test_apply_controller_target_rejects_bad_ctrl_indices_without_mutating_ctrl(
    bad_indices: list[int], message: str
) -> None:
    fake_data = FakeData(size=20)
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError, match=message):
        apply_controller_target(fake_data, np.arange(12, dtype=np.float64), ctrl_indices=bad_indices)

    np.testing.assert_allclose(fake_data.ctrl, before)


def test_dispatch_controller_computes_validates_applies_and_preserves_metadata() -> None:
    controller = FakeController()
    fake_data = FakeData()
    observation = {"qpos": np.zeros(19, dtype=np.float64)}
    command = LocomotionCommand(vx=0.2, vy=0.1, yaw_rate=-0.3)

    result = dispatch_controller(controller, observation, command, 0.02, data=fake_data)

    assert controller.calls == [(observation, command, 0.02)]
    np.testing.assert_allclose(result.action, np.arange(12, dtype=np.float64))
    np.testing.assert_allclose(fake_data.ctrl, np.arange(12, dtype=np.float64))
    assert result.metadata == {"controller_id": "fake", "action_mode": "velocity_command"}


def test_dispatch_controller_uses_ctrl_indices_for_multi_robot_sink() -> None:
    controller = FakeController()
    fake_data = FakeData(size=20)
    ctrl_indices = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    result = dispatch_controller(
        controller,
        {},
        LocomotionCommand(),
        0.02,
        data=fake_data,
        ctrl_indices=ctrl_indices,
    )

    for i, act_id in enumerate(ctrl_indices):
        assert fake_data.ctrl[act_id] == result.action[i]


def test_dispatch_controller_rejects_invalid_result_without_mutating_ctrl() -> None:
    controller = FakeController(action=np.array([np.nan] + [0.0] * 11, dtype=np.float64))
    fake_data = FakeData()
    before = fake_data.ctrl.copy()

    with pytest.raises(ValueError, match="finite"):
        dispatch_controller(controller, {}, LocomotionCommand(), 0.02, data=fake_data)

    np.testing.assert_allclose(fake_data.ctrl, before)


def test_dispatch_phase2_threat_gate_blocks_non_finite_targets_before_data_ctrl_write() -> None:
    """D-09/D-12 and T-2-03 require the shared seam to validate before mutation."""
    for bad_value in (np.nan, np.inf):
        controller = FakeController(action=np.array([bad_value] + [0.0] * 11, dtype=np.float64))
        fake_data = FakeData()
        before = fake_data.ctrl.copy()

        with pytest.raises(ValueError, match="finite"):
            dispatch_controller(controller, {}, LocomotionCommand(), 0.02, data=fake_data)

        np.testing.assert_allclose(fake_data.ctrl, before)
