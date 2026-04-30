"""Wave 0 tests for the locomotion controller protocol and analytical adapter."""

from __future__ import annotations

import numpy as np

from src.locomotion.gait_controller import TrotGaitController


def test_locomotion_command_defaults_and_metadata_are_immutable():
    from src.locomotion.controllers import LocomotionCommand

    command = LocomotionCommand()

    assert command.vx == 0.0
    assert command.vy == 0.0
    assert command.yaw_rate == 0.0
    assert command.metadata is None


def test_locomotion_command_carries_velocity_and_metadata():
    from src.locomotion.controllers import LocomotionCommand

    command = LocomotionCommand(vx=0.3, vy=0.1, yaw_rate=0.2, metadata={"source": "test"})

    assert command.vx == 0.3
    assert command.vy == 0.1
    assert command.yaw_rate == 0.2
    assert command.metadata == {"source": "test"}


def test_analytical_trot_controller_matches_locomotion_controller_protocol():
    from src.locomotion.controllers import AnalyticalTrotController, LocomotionController

    assert isinstance(AnalyticalTrotController(), LocomotionController)


def test_analytical_trot_controller_compute_matches_existing_gait_controller():
    from src.locomotion.controllers import AnalyticalTrotController, LocomotionCommand

    command = LocomotionCommand(vx=0.3, vy=0.1, yaw_rate=0.2)
    controller = AnalyticalTrotController()

    result = controller.compute({}, command, 0.02)
    expected = TrotGaitController().compute(0.3, 0.1, 0.2, 0.02)

    assert result.action.shape == (12,)
    assert np.all(np.isfinite(result.action))
    np.testing.assert_allclose(result.action, expected)
    assert result.metadata["controller_id"] == "analytical_trot"
    assert result.metadata["action_mode"] == "joint_position"


def test_analytical_trot_controller_reset_isolates_state_for_same_command_sequence():
    from src.locomotion.controllers import AnalyticalTrotController, LocomotionCommand

    command = LocomotionCommand(vx=0.3, vy=0.1, yaw_rate=0.2)
    first = AnalyticalTrotController()
    second = AnalyticalTrotController()

    first.compute({}, command, 0.02)
    first.compute({}, command, 0.02)
    first.reset(seed=123)
    second.reset(seed=123)

    first_after_reset = first.compute({}, command, 0.02).action
    second_after_reset = second.compute({}, command, 0.02).action

    np.testing.assert_allclose(first_after_reset, second_after_reset)


def test_controller_result_rejects_non_finite_or_wrong_shape_actions():
    import pytest

    from src.locomotion.controllers import validate_controller_target

    with pytest.raises(ValueError, match="shape"):
        validate_controller_target(np.zeros(11))

    bad = np.zeros(12)
    bad[3] = np.nan
    with pytest.raises(ValueError, match="finite"):
        validate_controller_target(bad)

    good = validate_controller_target([0.0] * 12)
    assert good.dtype == np.float64
    assert good.shape == (12,)
