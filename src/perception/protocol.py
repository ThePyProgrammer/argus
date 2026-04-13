"""Detector and 3D-lifter protocols + TorchBackendMixin.

Per CONTEXT.md "Known tricky bits" and Pitfall P9, the module-order rule is:
  src/perception/types.py  ->  src/perception/protocol.py  ->  src/perception/registry.py
                                                            ->  src/perception/backends/...
This module sits at layer 2: it may import `types` and `src.bridge.sensor_types`,
but NOT `registry`, any `backends/*`, torch, ultralytics, or transformers.
(`torch` appears lazily inside TorchBackendMixin method bodies only.)

Locked decisions from CONTEXT.md:
- D-01: process_frame(frame: SensorFrame) -> Detections2D -- no text_prompt arg.
- D-02: five required methods: process_frame, reset, warmup, get_metrics, apply_params.
- D-04: Detection3DProtocol.lift(..., slam_cloud) -- slam_cloud REQUIRED positional.
- D-05: each backend exposes @classmethod available() -> tuple[bool, str | None].
- D-06: MANDATORY CAPABILITIES keys (enforcement in Plan 03's registry):
    framework: str, license: str, cpu_latency_hint_ms: int,
    outputs_3d_natively: bool, input_type: DetectorInput.
- D-08: TorchBackendMixin.__init__ calls model.eval() + freezes params;
        _inference() contextmanager wraps torch.inference_mode().

Pitfalls addressed:
- P1: warmup() is mandatory on the Protocol. No-op warmup is a bug, not an optimization.
- P5: TorchBackendMixin makes eval() + inference_mode() compile-time-hard-to-forget.
- P9: zero heavy imports at module scope.
"""

from __future__ import annotations

import contextlib
from typing import Protocol, runtime_checkable

import numpy as np

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import Detections2D, Detections3D, DetectorInput  # noqa: F401 -- DetectorInput re-exported for registry convenience


@runtime_checkable
class DetectorProtocol(Protocol):
    """Contract for every 2D object detector backend.

    MANDATORY `CAPABILITIES` keys (enforced by DetectorRegistry.register in Plan 03):
      framework: str                 -- "ultralytics" | "transformers" | "onnxruntime" | "subprocess"
      license: str                   -- SPDX string, e.g. "AGPL-3.0" | "Apache-2.0" | "CC-BY-NC-4.0"
      cpu_latency_hint_ms: int       -- p50 hint, replaced by live metrics in Phase 6
      outputs_3d_natively: bool      -- if True, DetectorWorker (Phase 2) bypasses lifter
      input_type: DetectorInput      -- RGB_ONLY | RGBD | RGB_TEXT_PROMPT

    A backend missing any of these keys MUST fail registration at import time.
    """

    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def process_frame(self, frame: SensorFrame) -> Detections2D:
        """Run detection on one sensor frame. No text_prompt arg (D-01).

        Open-vocab text prompts and class filters are configured per-model via
        apply_params(), NOT per-query. This keeps the call site identical across
        every backend (Pitfall P16 -- preserve YOLO baseline; future backends
        conform to this shape or don't land).
        """
        ...

    def reset(self) -> None:
        """Clear any accumulated state (rolling metrics, trackers, etc.)."""
        ...

    def warmup(self, dummy_frame: SensorFrame) -> None:
        """Run one inference on a representative frame to eliminate first-call stall.

        Per Pitfall P1, transformer backends need 5-30 s on CPU for their first
        inference due to oneDNN kernel selection and lazy parameter materialization.
        The registry MUST call warmup() on the worker thread BEFORE the UI reports
        "ready". No-op warmup is a bug (CONTEXT.md D-02): every backend, including
        the small YOLOv11, must exercise its real inference path here.
        """
        ...

    def get_metrics(self) -> dict:
        """Return rolling timing / quality metrics for the MetricsPanel.

        Recommended keys (Phase 6 formalizes): inference_ms_p50, inference_ms_p95,
        first_inference_ms, steady_state_inference_ms, detections_per_frame,
        mean_confidence. Phase 1 backends may return any subset.
        """
        ...

    def apply_params(self, params: dict) -> dict:
        """Apply a dict of schema-validated params. Returns echo of accepted params.

        Per research (Pitfall P18 / CONTEXT.md D-02), returns per-key status so the
        WS layer can surface live-tunable vs reload-required vs unknown keys.
        Phase 1 YOLOv11 treats all params as live-tunable.
        """
        ...

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """Probe whether this backend can run in the current environment (D-05).

        Returns (True, None) when dependencies are satisfied.
        Returns (False, "<install hint>") when not -- the registry surfaces the
        hint verbatim. Examples:
          (False, "pip install ultralytics>=8.4.24")
          (False, "run scripts/setup_boxer_subprocess.sh")
        The registry NEVER invents hint text.
        """
        ...


@runtime_checkable
class Detection3DProtocol(Protocol):
    """Contract for every 2D->3D lifter backend.

    MANDATORY `CAPABILITIES` keys (enforced by Detection3DRegistry.register in Plan 03):
      requires_depth: bool
      requires_point_cloud: bool
      outputs_oriented: bool         -- False for MedianDepthLifter (identity quat);
                                        True for Phase 4 PointClusterLifter (PCA-OBB)
      license: str                   -- SPDX string
    """

    CAPABILITIES: dict
    PARAMETER_SCHEMA: dict

    def lift(
        self,
        detections_2d: Detections2D,
        frame: SensorFrame,
        pose: np.ndarray,
        intrinsics: CameraIntrinsics,
        slam_cloud: np.ndarray | None,
    ) -> Detections3D:
        """Lift 2D detections to oriented 3D boxes.

        Per CONTEXT.md D-04, `slam_cloud` is REQUIRED (may be None).
        MedianDepthLifter (Plan 04) ignores it; PointClusterLifter (Phase 4)
        consumes it when the depth frustum is sparse.

        `pose` is the 4x4 camera-to-world transform at frame capture time.
        `intrinsics` carries fx/fy/cx/cy -- never assume a hardcoded FoV
        (Pitfall P21 / P3).
        """
        ...

    def reset(self) -> None: ...

    def get_metrics(self) -> dict: ...

    def apply_params(self, params: dict) -> dict: ...

    @classmethod
    def available(cls) -> tuple[bool, str | None]: ...


class TorchBackendMixin:
    """Abstract base that makes model.eval() + torch.inference_mode() compile-time-hard-to-forget.

    Per CONTEXT.md D-08 and Pitfall P5.

    Contract:
      1. Subclasses MUST set `self.model` BEFORE calling `super().__init__()`.
      2. `super().__init__()` calls `self.model.eval()` and freezes all parameters.
      3. Subclasses wrap inference code in `with self._inference(): ...`.

    Example (Plan 05 YOLOv11Backend):
        class YOLOv11Backend(TorchBackendMixin):
            def __init__(self, ...):
                self.model = YOLO("yolo11n.pt")  # set BEFORE super
                super().__init__()
            def process_frame(self, frame):
                with self._inference():
                    results = self.model(frame.rgb, ...)
                ...

    Lazy torch import (inside method bodies, not module scope) is required by
    Pitfall P9: importing this file must not pull torch into sys.modules.
    """

    def __init__(self) -> None:
        if not hasattr(self, "model"):
            raise TypeError(
                f"{type(self).__name__} must set self.model BEFORE calling "
                f"TorchBackendMixin.__init__(). Per CONTEXT.md D-08."
            )
        # Lazy torch import -- keeps src.perception.protocol torch-free at module scope.
        import torch  # noqa: PLC0415 -- intentional lazy import (P9)

        self.model.eval()
        for p in self.model.parameters():
            p.requires_grad_(False)
        # Torch version varies across backends; no explicit dtype pin here --
        # subclass decides via .to(torch.float32) if needed (research STACK.md).
        self._torch = torch  # cache for _inference to avoid re-import each call

    @contextlib.contextmanager
    def _inference(self):
        """Context manager wrapping torch.inference_mode() per D-08.

        Using contextmanager (not decorator) so backends can scope the guard
        precisely around forward passes while leaving post-processing /
        metric updates outside the guard (CONTEXT.md "Specifics" section).
        """
        with self._torch.inference_mode():
            yield
