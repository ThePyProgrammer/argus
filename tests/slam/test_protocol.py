"""Tests for SLAM protocol types: SLAMProtocol, SLAMResult, TrackingStatus."""

import numpy as np
import pytest

from src.slam.protocol import SLAMProtocol, SLAMResult, TrackingStatus


class TestTrackingStatus:
    def test_tracking_status_values(self):
        """TrackingStatus has exactly 4 members: OK, LOST, INITIALIZING, RELOCALIZING."""
        assert TrackingStatus.OK.value == "ok"
        assert TrackingStatus.LOST.value == "lost"
        assert TrackingStatus.INITIALIZING.value == "initializing"
        assert TrackingStatus.RELOCALIZING.value == "relocalizing"
        assert len(TrackingStatus) == 4


class TestSLAMResult:
    def test_slam_result_construction(self):
        """SLAMResult constructs with valid arrays and fields are accessible."""
        pose = np.eye(4)
        points = np.zeros((10, 3))
        colors = np.zeros((10, 3))
        result = SLAMResult(
            pose=pose,
            points=points,
            colors=colors,
            metrics={"fitness": 0.95},
            tracking_status=TrackingStatus.OK,
        )
        assert result.pose.shape == (4, 4)
        assert result.points.shape == (10, 3)
        assert result.colors.shape == (10, 3)
        assert result.metrics == {"fitness": 0.95}
        assert result.tracking_status == TrackingStatus.OK

    def test_slam_result_default_tracking_status(self):
        """SLAMResult defaults to TrackingStatus.OK."""
        result = SLAMResult(
            pose=np.eye(4),
            points=np.zeros((5, 3)),
            colors=np.zeros((5, 3)),
            metrics={},
        )
        assert result.tracking_status == TrackingStatus.OK


class TestSLAMProtocol:
    def test_protocol_runtime_check(self):
        """A class implementing all required methods satisfies isinstance check."""
        from src.bridge.sensor_types import SensorFrame

        class FakeBackend:
            CAPABILITIES: dict = {}
            PARAMETER_SCHEMA: dict = {}

            def process_frame(self, frame: SensorFrame) -> SLAMResult:
                ...

            def reset(self) -> None:
                ...

            def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
                ...

            def get_poses(self) -> list[np.ndarray]:
                ...

            @property
            def num_frames_processed(self) -> int:
                return 0

        assert isinstance(FakeBackend(), SLAMProtocol)

    def test_protocol_rejects_incomplete(self):
        """A class missing process_frame fails isinstance check."""

        class IncompleteBackend:
            CAPABILITIES: dict = {}
            PARAMETER_SCHEMA: dict = {}

            def reset(self) -> None:
                ...

            def get_global_cloud(self) -> tuple[np.ndarray, np.ndarray]:
                ...

            def get_poses(self) -> list[np.ndarray]:
                ...

            @property
            def num_frames_processed(self) -> int:
                return 0

        assert not isinstance(IncompleteBackend(), SLAMProtocol)
