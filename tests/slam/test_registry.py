"""Tests for SLAMRegistry and slam_backend decorator."""

import numpy as np
import pytest

from src.slam.registry import SLAMRegistry, slam_backend
from src.slam.protocol import SLAMProtocol, SLAMResult, TrackingStatus
from src.bridge.sensor_types import CameraIntrinsics, SensorFrame


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear registry before and after each test."""
    SLAMRegistry._clear()
    yield
    SLAMRegistry._clear()


class _MockBackend:
    """Mock backend for testing registration."""

    CAPABILITIES = {"supports_imu": False}
    PARAMETER_SCHEMA = {"type": "object", "properties": {"speed": {"type": "number"}}}

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def process_frame(self, frame):
        return SLAMResult(
            pose=np.eye(4), points=np.zeros((1, 3)),
            colors=np.zeros((1, 3)), metrics={},
        )

    def reset(self):
        pass

    def get_global_cloud(self):
        return np.zeros((1, 3)), np.zeros((1, 3))

    def get_poses(self):
        return []

    @property
    def num_frames_processed(self):
        return 0


def test_register_and_list():
    """Register a mock backend, verify it appears in list_backends()."""
    SLAMRegistry.register(
        "test", "Test Backend",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    backends = SLAMRegistry.list_backends()
    assert len(backends) == 1
    assert backends[0]["name"] == "test"
    assert backends[0]["display"] == "Test Backend"
    assert backends[0]["available"] is True


def test_create_backend():
    """Register mock, create instance, assert type correct."""
    SLAMRegistry.register(
        "test", "Test Backend",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    instance = SLAMRegistry.create("test", some_kwarg="hello")
    assert isinstance(instance, _MockBackend)
    assert instance.kwargs == {"some_kwarg": "hello"}


def test_create_default():
    """Register 'icp' mock, call create(None), verify ICP is returned."""
    SLAMRegistry.register(
        "icp", "ICP Odometry",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    instance = SLAMRegistry.create(None)
    assert isinstance(instance, _MockBackend)


def test_create_unknown_raises():
    """create('nonexistent') raises ValueError."""
    with pytest.raises(ValueError, match="nonexistent"):
        SLAMRegistry.create("nonexistent")


def test_decorator_registers():
    """@slam_backend decorator registers a class in SLAMRegistry._backends."""

    @slam_backend("decorated", "Decorated Backend")
    class _DecoratedBackend:
        CAPABILITIES = {}
        PARAMETER_SCHEMA = {}

    assert "decorated" in SLAMRegistry._backends
    assert SLAMRegistry._backends["decorated"]["display"] == "Decorated Backend"


def test_unavailable_backend():
    """Register with bad class_path, verify available=False with reason."""
    SLAMRegistry.register("bad", "Bad Backend", "nonexistent.module.BadClass")
    backends = SLAMRegistry.list_backends()
    assert len(backends) == 1
    assert backends[0]["name"] == "bad"
    assert backends[0]["available"] is False
    assert "reason" in backends[0]


def test_parameter_schema_in_listing():
    """Register class with PARAMETER_SCHEMA, verify in listing."""
    SLAMRegistry.register(
        "test", "Test Backend",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    backends = SLAMRegistry.list_backends()
    assert backends[0]["parameter_schema"] == _MockBackend.PARAMETER_SCHEMA


def test_capabilities_in_listing():
    """Register class with CAPABILITIES, verify in listing."""
    SLAMRegistry.register(
        "test", "Test Backend",
        f"{_MockBackend.__module__}.{_MockBackend.__qualname__}",
    )
    backends = SLAMRegistry.list_backends()
    assert backends[0]["capabilities"] == _MockBackend.CAPABILITIES
