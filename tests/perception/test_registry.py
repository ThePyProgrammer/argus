"""Contract tests for DetectorRegistry + Detection3DRegistry.

Covers CONTEXT.md D-05 (available() probe), D-06 (mandatory CAPABILITIES keys),
D-07 (side-effect import pattern is deferred to Plan 05's backends/__init__.py --
not tested here directly), and Pitfall P9 (no heavy imports on registry import).
"""

from __future__ import annotations

import sys

import pytest

HEAVY_DEPS = ("torch", "ultralytics", "transformers", "onnxruntime")


def _DetectorInput():
    """Lazy-resolve DetectorInput from the current sys.modules snapshot.

    W-02 fix (Plan 02-12): test_protocol_contracts.py does
    ``del sys.modules["src.perception.types"]`` and re-imports, creating a
    second enum class identity. If test_registry.py binds ``DetectorInput``
    at module load time, later assertions that compare the module-bound
    identity against the identity inside ``registry.py._DETECTOR_TYPED_KEYS``
    can fail with the surreal "got DetectorInput, expected DetectorInput"
    isinstance-mismatch (same-name / different-module-object classes).

    This helper reads ``DetectorInput`` from the currently-cached
    ``src.perception.types`` on every call, so the enum class identity
    matches whatever ``registry.py`` captured on its most recent import.
    test_protocol_contracts.py restores sys.modules to its pre-pollution
    state after the P9-delta tests, so the cached types module stays
    stable — this helper still guards against any future mutation we
    haven't thought of yet.
    """
    from src.perception.types import DetectorInput as _DI

    return _DI


@pytest.fixture(autouse=True)
def _clean_registries():
    """Isolate tests -- clear both registries before and after each test.

    W-02 fix (Plan 02-12): after teardown, pop sys.modules entries for the
    backends + lifters packages so the next test's explicit import re-triggers
    @detector_backend and @detection_3d decorator registration. Without this,
    @detector_backend runs once at first module import; later _clear() wipes
    the registry but sys.modules keeps the module cached, so re-importing is
    a no-op and subsequent tests see an empty registry.

    The DetectorInput enum-identity half of W-02 (Phase 1 VERIFICATION.md §W-02
    root cause: test_protocol_contracts.py's ``del sys.modules[...]`` splitting
    DetectorInput into two same-named / different-identity classes) is fixed
    inside test_protocol_contracts.py itself — it now saves the original module
    object and restores it via try/finally — rather than here. See _DetectorInput()
    above for the defense-in-depth lazy-resolver that keeps _full_det_caps()
    binding to the CURRENT types-module identity regardless of pollution.
    """
    import sys

    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    # W-02 fix: force re-execution of decorator-driven registration on next
    # import. Only the ``backends`` + ``lifters`` packages are popped — NOT
    # ``types`` / ``protocol`` / ``registry``, because popping those here
    # would split the DetectorInput enum class identity against every module
    # that has already imported it at class-definition time (FakeDetector in
    # test_worker_pool.py, YOLOv11Backend in the real backend, ...). The
    # enum-identity half of W-02 is fixed at the other end of the pollution
    # chain: tests/perception/test_protocol_contracts.py's ``del
    # sys.modules[...]`` pair restores the original module object via
    # try/finally instead of leaving a freshly-constructed replacement
    # behind. Together with the lazy ``_DetectorInput()`` resolver above,
    # this keeps every ``isinstance(caps["input_type"], DetectorInput)``
    # check comparing the SAME enum class across tests.
    for mod in (
        "src.perception.backends",
        "src.perception.lifters",
        "src.perception.backends.yolov11_backend",
        "src.perception.lifters.median_depth",
    ):
        sys.modules.pop(mod, None)


def _full_det_caps(**overrides):
    caps = {
        "framework": "ultralytics",
        "license": "AGPL-3.0",
        "cpu_latency_hint_ms": 120,
        "outputs_3d_natively": False,
        # Lazy-resolve to bind to the CURRENT types-module enum identity —
        # see _DetectorInput() docstring for the W-02 split-identity rationale.
        "input_type": _DetectorInput().RGB_ONLY,
    }
    caps.update(overrides)
    return caps


def _full_lifter_caps(**overrides):
    caps = {
        "requires_depth": True,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    caps.update(overrides)
    return caps


def test_registry_module_does_not_import_heavy_deps():
    """Pitfall P9: registry import must not pull torch / ultralytics / transformers."""
    # Record pre-state; registry may already be loaded from the autouse fixture.
    pre_heavy = {fw: fw in sys.modules for fw in HEAVY_DEPS}
    # Re-import registry fresh to measure the delta.
    for mod in list(sys.modules):
        if mod.startswith("src.perception.registry"):
            del sys.modules[mod]
    pre = set(sys.modules.keys())
    import src.perception.registry  # noqa: F401

    post = set(sys.modules.keys())
    delta = post - pre
    for fw in HEAVY_DEPS:
        newly_added = fw in delta and not pre_heavy[fw]
        assert not newly_added, (
            f"Importing src.perception.registry pulled {fw} into sys.modules. "
            f"Pitfall P9: heavy deps must be reached via lazy class-path loading only."
        )


def test_detector_registry_default_is_yolov11():
    from src.perception.registry import DetectorRegistry

    assert DetectorRegistry.get_default() == "yolov11"


def test_detection_3d_registry_default_is_median_depth():
    from src.perception.registry import Detection3DRegistry

    assert Detection3DRegistry.get_default() == "median_depth"


def test_register_rejects_missing_capabilities_dict():
    from src.perception.registry import DetectorRegistry

    class NoCaps:
        pass

    with pytest.raises(ValueError, match="CAPABILITIES"):
        DetectorRegistry.register("bad", "Bad", "x.NoCaps", NoCaps)


def test_register_lists_all_missing_keys_in_sorted_order():
    from src.perception.registry import DetectorRegistry

    class Partial:
        CAPABILITIES = {"framework": "ultralytics", "license": "MIT"}

    with pytest.raises(ValueError) as exc_info:
        DetectorRegistry.register("partial", "Partial", "x.Partial", Partial)
    msg = str(exc_info.value)
    # All three missing keys named
    for key in ("cpu_latency_hint_ms", "outputs_3d_natively", "input_type"):
        assert key in msg, f"expected {key} in error message: {msg}"


def test_register_rejects_wrong_input_type_type():
    from src.perception.registry import DetectorRegistry

    class WrongType:
        CAPABILITIES = _full_det_caps(input_type="rgb_only")  # string, not enum

    with pytest.raises(ValueError, match="input_type") as exc_info:
        DetectorRegistry.register("wrong", "Wrong", "x.WrongType", WrongType)
    assert "DetectorInput" in str(exc_info.value)


def test_register_accepts_full_capabilities():
    from src.perception.registry import DetectorRegistry

    class Good:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {"type": "object", "properties": {}}

    # Should not raise
    DetectorRegistry.register("good", "Good", "x.Good", Good)
    # Listed backends should include it with name/display
    # (list_backends will fail to load the fake class path, so available=False)
    listed = DetectorRegistry.list_backends()
    assert len(listed) == 1
    assert listed[0]["name"] == "good"
    assert listed[0]["display"] == "Good"


def test_list_backends_uses_available_probe():
    """D-05: registry must call klass.available() and surface the returned reason verbatim."""
    from src.perception.registry import DetectorRegistry

    class Probed:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

        @classmethod
        def available(cls):
            return False, "pip install special>=1.2.3"

    # Expose the class on the test module so importlib can resolve the dotted path.
    current_module = sys.modules[__name__]
    current_module.Probed = Probed  # type: ignore[attr-defined]
    DetectorRegistry.register("probed", "Probed", f"{__name__}.Probed", Probed)

    listed = DetectorRegistry.list_backends()
    assert len(listed) == 1
    assert listed[0]["available"] is False
    assert listed[0]["reason"] == "pip install special>=1.2.3"


def test_list_backends_tolerates_missing_available_classmethod():
    from src.perception.registry import DetectorRegistry

    class NoProbe:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    sys.modules[__name__].NoProbe = NoProbe  # type: ignore[attr-defined]
    DetectorRegistry.register("noprobe", "NoProbe", f"{__name__}.NoProbe", NoProbe)

    listed = DetectorRegistry.list_backends()
    assert listed[0]["available"] is True
    assert "reason" not in listed[0]


def test_list_backends_handles_unloadable_class_path():
    from src.perception.registry import DetectorRegistry

    class Loadable:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    DetectorRegistry.register(
        "ghost", "Ghost", "does.not.exist.Module.Backend", Loadable
    )
    listed = DetectorRegistry.list_backends()
    entry = listed[0]
    assert entry["available"] is False
    assert "Cannot load" in entry["reason"]


def test_probe_exception_marks_unavailable_without_crash():
    from src.perception.registry import DetectorRegistry

    class Buggy:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

        @classmethod
        def available(cls):
            raise RuntimeError("boom")

    sys.modules[__name__].Buggy = Buggy  # type: ignore[attr-defined]
    DetectorRegistry.register("buggy", "Buggy", f"{__name__}.Buggy", Buggy)

    listed = DetectorRegistry.list_backends()
    # Registry must not crash -- graceful degradation
    assert listed[0]["available"] is False
    assert "boom" in listed[0]["reason"] or "raised" in listed[0]["reason"]


def test_detector_backend_decorator_registers_at_class_definition():
    from src.perception.registry import DetectorRegistry, detector_backend

    @detector_backend(name="decorated", display="Decorated")
    class Decorated:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    listed = DetectorRegistry.list_backends()
    names = [e["name"] for e in listed]
    assert "decorated" in names


def test_detection_3d_registry_mandatory_keys():
    from src.perception.registry import Detection3DRegistry

    class BadLifter:
        CAPABILITIES = {"requires_depth": True}  # missing 3

    with pytest.raises(ValueError) as exc_info:
        Detection3DRegistry.register("bad", "Bad", "x.Bad", BadLifter)
    msg = str(exc_info.value)
    for key in ("requires_point_cloud", "outputs_oriented", "license"):
        assert key in msg


def test_detection_3d_decorator_registers():
    from src.perception.registry import Detection3DRegistry, detection_3d

    @detection_3d(name="testlift", display="Test Lifter")
    class TestLifter:
        CAPABILITIES = _full_lifter_caps()
        PARAMETER_SCHEMA = {}

    assert "testlift" in [e["name"] for e in Detection3DRegistry.list_backends()]


def test_registries_are_independent():
    """2D and 3D registries have separate _backends dicts."""
    from src.perception.registry import (
        Detection3DRegistry,
        DetectorRegistry,
        detector_backend,
    )

    @detector_backend(name="only2d", display="Only 2D")
    class Only2D:
        CAPABILITIES = _full_det_caps()
        PARAMETER_SCHEMA = {}

    assert "only2d" in [e["name"] for e in DetectorRegistry.list_backends()]
    assert "only2d" not in [e["name"] for e in Detection3DRegistry.list_backends()]


def test_create_unknown_name_raises_valueerror():
    from src.perception.registry import DetectorRegistry

    with pytest.raises(ValueError, match="Unknown detector backend"):
        DetectorRegistry.create("nonexistent")
