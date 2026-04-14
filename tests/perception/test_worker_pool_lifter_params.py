"""Plan 03-06 coverage: DetectorWorkerPool.lifter_params kwarg forwarding.

Verifies the new ``lifter_params: dict | None = None`` keyword on
``DetectorWorkerPool.__init__`` is forwarded into
``Detection3DRegistry.create(lifter_name, **lifter_params)`` per-robot, and that
the default-None path is equivalent to passing an empty dict (no crash on
existing callers — Phase 2 callers omit the new kwarg).
"""

from __future__ import annotations

import pytest

from src.perception.registry import Detection3DRegistry, DetectorRegistry
from src.perception.types import DetectorInput
from src.perception.worker_pool import DetectorWorkerPool


class FakeYolo:
    """Minimal DetectorProtocol stand-in (capabilities + no-op methods)."""

    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 5,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA: dict = {"type": "object", "properties": {}}

    def __init__(self, **kwargs):
        self.init_kwargs = dict(kwargs)

    def process_frame(self, f):
        return None

    def reset(self):
        return None

    def warmup(self, f):
        return None

    def get_metrics(self):
        return {}

    def apply_params(self, p):
        return {}

    @classmethod
    def available(cls):
        return True, None


class FakeLifter:
    """Minimal Detection3DProtocol stand-in capturing __init__ kwargs."""

    CAPABILITIES = {
        "requires_depth": True,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {"type": "object", "properties": {}}
    instances: list = []

    def __init__(self, **kwargs):
        self.init_kwargs = dict(kwargs)
        FakeLifter.instances.append(self)

    def lift(self, *a, **kw):
        return None

    def reset(self):
        return None

    @classmethod
    def available(cls):
        return True, None


@pytest.fixture(autouse=True)
def _registries():
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    FakeLifter.instances.clear()
    DetectorRegistry.register(
        "fake_yolo",
        "Fake",
        f"{FakeYolo.__module__}.{FakeYolo.__qualname__}",
        FakeYolo,
    )
    Detection3DRegistry.register(
        "fake_lifter",
        "Fake Lifter",
        f"{FakeLifter.__module__}.{FakeLifter.__qualname__}",
        FakeLifter,
    )
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    FakeLifter.instances.clear()


def _fake_intrinsics():
    """Minimal duck-type — worker pool only forwards intrinsics, never inspects."""

    class _I:
        fx = fy = 500.0
        cx = 320.0
        cy = 240.0
        width = 640
        height = 480

    return _I()


def test_lifter_params_forwarded_to_create():
    """lifter_params kwargs flow into FakeLifter.__init__ unchanged."""
    DetectorWorkerPool(
        robot_ids=["r0"],
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot={"r0": _fake_intrinsics()},
        lifter_params={"depth_near_m": 0.3, "smoothing": "median"},
    )
    assert len(FakeLifter.instances) == 1
    assert FakeLifter.instances[0].init_kwargs == {
        "depth_near_m": 0.3,
        "smoothing": "median",
    }


def test_lifter_params_defaults_to_empty_dict():
    """Omitting the new kwarg behaves identically to passing {}."""
    DetectorWorkerPool(
        robot_ids=["r0"],
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot={"r0": _fake_intrinsics()},
    )
    assert len(FakeLifter.instances) == 1
    assert FakeLifter.instances[0].init_kwargs == {}


def test_lifter_params_none_treated_as_empty():
    """Explicit ``lifter_params=None`` matches the default."""
    DetectorWorkerPool(
        robot_ids=["r0"],
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot={"r0": _fake_intrinsics()},
        lifter_params=None,
    )
    assert len(FakeLifter.instances) == 1
    assert FakeLifter.instances[0].init_kwargs == {}


def test_per_robot_fresh_lifter_instance():
    """Sanity: 2 robots yield 2 distinct lifter instances; each gets the kwargs."""
    DetectorWorkerPool(
        robot_ids=["r0", "r1"],
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot={"r0": _fake_intrinsics(), "r1": _fake_intrinsics()},
        lifter_params={"k": 1},
    )
    assert len(FakeLifter.instances) == 2
    assert FakeLifter.instances[0] is not FakeLifter.instances[1]
    assert all(inst.init_kwargs == {"k": 1} for inst in FakeLifter.instances)
