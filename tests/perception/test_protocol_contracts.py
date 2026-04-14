"""Contract tests for src.perception.types and src.perception.protocol.

Locks the Phase 1 surface:
- DetectorProtocol / Detection3DProtocol method sets (CONTEXT.md D-01, D-02, D-04).
- Dataclass field order and frozen-ness (CONTEXT.md D-03).
- DetectorInput enum values (Claude's Discretion -- Enum picked over Literal).
- TorchBackendMixin eval + freeze behaviour (CONTEXT.md D-08, Pitfall P5).
- No heavy imports leaking into sys.modules on import (Pitfall P9).
- OrientedBox3D skeleton-only (no to_wire/from_wire -- Phase 2 work).
"""

from __future__ import annotations

import dataclasses
import inspect
import sys
import unittest.mock as um

import pytest


HEAVY_DEPS = ("torch", "ultralytics", "transformers", "onnxruntime")


def test_perception_types_import_does_not_load_heavy_deps() -> None:
    """src.perception.types must be importable without torch/ultralytics/transformers.

    W-02 fix (Plan 02-12): the delta-measuring approach used to ``del
    sys.modules["src.perception.types"]`` and re-import without restoring.
    That mutation created a second ``DetectorInput`` enum class identity
    in sys.modules — any previously-imported module (registry, worker_pool,
    ...) still held a reference to the FIRST class, so later
    ``isinstance(value, DetectorInput)`` checks compared two same-named but
    different-identity classes and failed. The fix: snapshot the original
    module object, pop for the delta measurement, then restore it before
    the test returns, leaving sys.modules bit-identical afterward.
    """
    pre_modules = dict(sys.modules)
    pre = set(pre_modules.keys())
    saved = {m: pre_modules[m] for m in pre if m.startswith("src.perception.types")}
    for mod in list(sys.modules):
        if mod.startswith("src.perception.types"):
            del sys.modules[mod]
    try:
        import src.perception.types  # noqa: F401
        post = set(sys.modules.keys())
        delta = post - pre
        for fw in HEAVY_DEPS:
            assert fw not in delta or fw in pre, (
                f"Importing src.perception.types pulled {fw} into sys.modules. "
                f"Pitfall P9: types.py must have zero heavy-dep imports."
            )
    finally:
        # W-02: restore the ORIGINAL module object so downstream modules
        # (registry, worker_pool, ...) that captured references to it at
        # their own import time keep matching identities.
        for mod in list(sys.modules):
            if mod.startswith("src.perception.types"):
                del sys.modules[mod]
        sys.modules.update(saved)


def test_perception_protocol_import_does_not_load_heavy_deps() -> None:
    """src.perception.protocol must be importable without torch/ultralytics/transformers.

    W-02 fix (Plan 02-12): same restore-original-module pattern as
    test_perception_types_import_does_not_load_heavy_deps above — see that
    test's docstring for the full rationale. Without the restore the
    protocol module identity splits, breaking @runtime_checkable protocol
    isinstance() checks in downstream tests.
    """
    pre_modules = dict(sys.modules)
    pre = set(pre_modules.keys())
    saved = {m: pre_modules[m] for m in pre if m.startswith("src.perception.protocol")}
    for mod in list(sys.modules):
        if mod.startswith("src.perception.protocol"):
            del sys.modules[mod]
    try:
        import src.perception.protocol  # noqa: F401
        post = set(sys.modules.keys())
        delta = post - pre
        for fw in HEAVY_DEPS:
            assert fw not in delta or fw in pre, (
                f"Importing src.perception.protocol pulled {fw} into sys.modules. "
                f"Pitfall P9: torch imports must be lazy inside TorchBackendMixin method bodies only."
            )
    finally:
        for mod in list(sys.modules):
            if mod.startswith("src.perception.protocol"):
                del sys.modules[mod]
        sys.modules.update(saved)


def test_detector_input_enum() -> None:
    from src.perception.types import DetectorInput

    values = {m.value for m in DetectorInput}
    assert values == {"rgb_only", "rgbd", "rgb_text_prompt"}, (
        f"DetectorInput members drifted from CONTEXT.md: {values}"
    )


def test_detection_2d_dataclass_contract() -> None:
    from src.perception.types import Detection2D

    fields = [f.name for f in dataclasses.fields(Detection2D)]
    assert fields == ["class_id", "class_name", "score", "bbox_xyxy", "extras"], fields
    d = Detection2D(class_id=56, class_name="chair", score=0.9, bbox_xyxy=(10, 20, 100, 200))
    assert d.extras is None
    assert dataclasses.is_dataclass(d) and d.__dataclass_params__.frozen


def test_detections_2d_dataclass_contract() -> None:
    from src.perception.types import Detections2D

    fields = [f.name for f in dataclasses.fields(Detections2D)]
    assert fields == ["items", "inference_ms", "image_hw"], fields
    dets = Detections2D(items=[], inference_ms=0.0, image_hw=(480, 640))
    assert dets.image_hw == (480, 640)


def test_oriented_box_3d_skeleton_contract() -> None:
    """Phase 2 Plan 02-01 extends the OBB with bbox_xyxy (02-RESEARCH W-01 / Pitfall 8).

    Field order is locked: the seven Phase 1 fields come first (unchanged order),
    bbox_xyxy is appended as the LAST optional field so Phase 1 construction sites
    (median_depth lifter, coordinator) keep working without kwargs churn.
    """
    from src.perception.types import OrientedBox3D

    fields = [f.name for f in dataclasses.fields(OrientedBox3D)]
    assert fields == [
        "center", "half_extents", "quaternion",
        "class_id", "class_name", "score", "track_id", "bbox_xyxy",
    ], fields


def test_oriented_box_3d_has_to_wire_and_from_wire() -> None:
    """Phase 2 Plan 02-01 ships to_wire / from_wire per DET-3D-03 / DET-3D-04."""
    from src.perception.types import OrientedBox3D

    assert hasattr(OrientedBox3D, "to_wire"), (
        "OrientedBox3D.to_wire is Phase 2 Plan 02-01 scope (DET-3D-03)."
    )
    assert hasattr(OrientedBox3D, "from_wire"), (
        "OrientedBox3D.from_wire is Phase 2 Plan 02-01 scope (DET-3D-04)."
    )


def test_detections_3d_dataclass_contract() -> None:
    """Phase 2 Plan 02-01 adds envelope-level capture_pose + capture_timestamp (D-11, D-12).

    Defaults exist ONLY to keep Phase 1 construction sites working during the Wave 2 cutover;
    the Detections3D.to_wire() serializes capture_pose as a flat 16-float row-major list (D-14).
    """
    from src.perception.types import Detections3D

    fields = [f.name for f in dataclasses.fields(Detections3D)]
    assert fields == [
        "items", "lifter_ms", "detector_ms", "n_raw", "n_final", "image_hw",
        "capture_pose", "capture_timestamp",
    ], fields


def test_detector_protocol_is_runtime_checkable() -> None:
    from src.perception.protocol import DetectorProtocol

    assert getattr(DetectorProtocol, "_is_runtime_protocol", False), (
        "DetectorProtocol must be decorated with @runtime_checkable per D-01 pattern from SLAMProtocol."
    )


def test_detection_3d_protocol_is_runtime_checkable() -> None:
    from src.perception.protocol import Detection3DProtocol

    assert getattr(Detection3DProtocol, "_is_runtime_protocol", False)


def test_detector_protocol_method_set_locked() -> None:
    """Locks the Phase 1 DetectorProtocol surface per CONTEXT.md D-02 + D-05."""
    from src.perception.protocol import DetectorProtocol

    expected = {"process_frame", "reset", "warmup", "get_metrics", "apply_params", "available"}
    for name in expected:
        assert hasattr(DetectorProtocol, name), f"DetectorProtocol missing {name}"

    # Forbid any surprise public methods beyond the locked set
    public = {
        name for name in vars(DetectorProtocol)
        if not name.startswith("_") and callable(vars(DetectorProtocol)[name])
    }
    extras = public - expected
    assert not extras, f"DetectorProtocol has unexpected public methods: {extras} (Phase 1 locks surface)"


def test_detector_protocol_runtime_checkable_with_stub() -> None:
    """Stub class implementing all 5 methods + classmethod should pass isinstance check."""
    from src.perception.protocol import DetectorProtocol
    from src.perception.types import Detections2D, DetectorInput

    class YoloTestStub:
        CAPABILITIES: dict = {
            "framework": "ultralytics",
            "license": "AGPL-3.0",
            "cpu_latency_hint_ms": 50,
            "outputs_3d_natively": False,
            "input_type": DetectorInput.RGB_ONLY,
        }
        PARAMETER_SCHEMA: dict = {}

        def process_frame(self, frame):
            return Detections2D(items=[], inference_ms=0.0, image_hw=(0, 0))

        def reset(self) -> None: ...

        def warmup(self, dummy_frame) -> None: ...

        def get_metrics(self) -> dict:
            return {}

        def apply_params(self, params: dict) -> dict:
            return {}

        @classmethod
        def available(cls):
            return (True, None)

    stub = YoloTestStub()
    assert isinstance(stub, DetectorProtocol), (
        "A stub implementing the locked DetectorProtocol surface must pass "
        "isinstance(stub, DetectorProtocol). @runtime_checkable is required."
    )


def test_detector_protocol_process_frame_no_text_prompt() -> None:
    """CONTEXT.md D-01: process_frame signature is (frame: SensorFrame) -> Detections2D.
    No text_prompt, no class_filter, no additional args."""
    from src.perception.protocol import DetectorProtocol

    sig = inspect.signature(DetectorProtocol.process_frame)
    params = list(sig.parameters.keys())
    assert params == ["self", "frame"], (
        f"process_frame params drifted from D-01: {params}. "
        f"Open-vocab prompts go through apply_params(), NOT per-call."
    )


def test_detection_3d_protocol_lift_signature_locked() -> None:
    """CONTEXT.md D-04: lift(detections_2d, frame, pose, intrinsics, slam_cloud)."""
    from src.perception.protocol import Detection3DProtocol

    sig = inspect.signature(Detection3DProtocol.lift)
    params = list(sig.parameters.keys())
    assert params == ["self", "detections_2d", "frame", "pose", "intrinsics", "slam_cloud"], params


def test_detection_3d_protocol_slam_cloud_annotation_optional() -> None:
    """CONTEXT.md D-04: slam_cloud must allow None (e.g., `np.ndarray | None`)."""
    from src.perception.protocol import Detection3DProtocol

    sig = inspect.signature(Detection3DProtocol.lift)
    annotation = sig.parameters["slam_cloud"].annotation
    annotation_str = str(annotation).lower()
    assert "none" in annotation_str, (
        f"slam_cloud annotation must include None (D-04: may be None): {annotation_str}"
    )
    assert "ndarray" in annotation_str, (
        f"slam_cloud annotation must reference ndarray (D-04: numpy point cloud): {annotation_str}"
    )


def test_torch_backend_mixin_enforces_eval_and_freeze() -> None:
    """CONTEXT.md D-08: __init__ calls model.eval() + freezes params."""
    from src.perception.protocol import TorchBackendMixin

    class FakeBackend(TorchBackendMixin):
        def __init__(self):
            self.model = um.MagicMock()
            fake_param = um.MagicMock()
            self.model.parameters.return_value = [fake_param]
            super().__init__()
            self._fake_param = fake_param

    backend = FakeBackend()
    assert backend.model.eval.called, "TorchBackendMixin must call self.model.eval()"
    assert backend._fake_param.requires_grad_.called, (
        "TorchBackendMixin must freeze parameters (p.requires_grad_(False))"
    )
    backend._fake_param.requires_grad_.assert_called_with(False)


def test_torch_backend_mixin_raises_when_model_unset() -> None:
    from src.perception.protocol import TorchBackendMixin

    class Bad(TorchBackendMixin):
        def __init__(self):
            super().__init__()  # forgot to set self.model

    with pytest.raises(TypeError, match="self.model"):
        Bad()


def test_torch_backend_mixin_inference_contextmanager() -> None:
    from src.perception.protocol import TorchBackendMixin

    class FakeBackend(TorchBackendMixin):
        def __init__(self):
            self.model = um.MagicMock()
            self.model.parameters.return_value = []
            super().__init__()

    backend = FakeBackend()
    ctx = backend._inference()
    assert hasattr(ctx, "__enter__") and hasattr(ctx, "__exit__"), (
        "_inference must be a context manager (CONTEXT.md 'Specifics')"
    )
    with backend._inference():
        pass  # no crash
