"""YOLOv11-nano detector backend — fresh DetectorProtocol implementation.

Per CONTEXT.md D-11 and Pitfall P16: this is NOT a delegate to
src.perception.detector.ObjectDetector._detect. It is a FRESH implementation
against DetectorProtocol using TorchBackendMixin. Both paths coexist during
Phase 1 (the old ObjectDetector stays wired into Coordinator; this backend
is exercised only by Registry-driven callers and the D-12 regression test).
Phase 2's DetectorWorkerPool rewire is what actually retires ObjectDetector.

Parity contract (CONTEXT.md D-12): bbox + class_id + count output of
this backend on a fixture frame MUST match ObjectDetector._detect on the
same fixture frame bit-exactly (or ±2 pixels if NMS non-determinism creeps in
on a CI runner, with documented reason).

Pitfalls addressed:
  P1  — warmup(dummy_frame) runs one real inference; first_inference_ms logged separately
  P5  — TorchBackendMixin enforces model.eval() + torch.inference_mode()
  P16 — ObjectDetector preserved; this is a parallel path, not a replacement
  P22 — INDOOR_CLASSES surfaced as a runtime class_filter parameter (schema-driven)
"""

from __future__ import annotations

import collections
import logging
import time
from typing import Any

import numpy as np

from src.bridge.sensor_types import SensorFrame
from src.perception.protocol import TorchBackendMixin
from src.perception.registry import detector_backend
from src.perception.types import Detection2D, Detections2D, DetectorInput

logger = logging.getLogger(__name__)


# COCO class IDs considered for indoor office scenes. Carried verbatim from
# the pre-refactor src/perception/detector.py INDOOR_CLASSES dict to preserve
# D-12 regression parity. Moving this to the backend (rather than a hardcoded
# module constant elsewhere) closes Pitfall P22 — the class set is now
# backend-specific and surfaced through PARAMETER_SCHEMA as a runtime param.
INDOOR_CLASSES: dict[int, str] = {
    56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
    64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone",
    72: "refrigerator", 73: "book", 74: "clock", 75: "vase",
    0: "person", 24: "backpack", 25: "umbrella", 26: "handbag",
    39: "bottle", 41: "cup", 42: "fork", 43: "knife",
    44: "spoon", 45: "bowl",
}


# Runtime drift guard (CONTEXT.md — duplicated INDOOR_CLASSES must not drift
# from src/perception/detector.py). Raises RuntimeError naming both module
# paths if the two copies disagree. Deferred import to avoid circularity at
# module-load time; the check runs the first time YOLOv11Backend is imported
# AND src.perception.detector has also been imported.
def _assert_indoor_classes_drift_guard() -> None:
    """Raise RuntimeError if INDOOR_CLASSES here differs from detector.py's."""
    try:
        from src.perception.detector import ObjectDetector as _OD
    except Exception:
        # detector.py may not import in a torch-less env; skip guard in that case.
        return
    legacy = getattr(_OD, "INDOOR_CLASSES", None)
    if legacy is None:
        return
    if dict(legacy) != dict(INDOOR_CLASSES):
        raise RuntimeError(
            "INDOOR_CLASSES drift detected between "
            "src.perception.backends.yolov11_backend.INDOOR_CLASSES and "
            "src.perception.detector.ObjectDetector.INDOOR_CLASSES. "
            "These two dicts MUST stay bit-identical (see CONTEXT.md D-11 + D-12)."
        )


_assert_indoor_classes_drift_guard()


@detector_backend(name="yolov11", display="YOLOv11-nano")
class YOLOv11Backend(TorchBackendMixin):
    """Fresh DetectorProtocol implementation wrapping Ultralytics YOLO.

    Construction flow (CONTEXT.md D-08 TorchBackendMixin contract):
      1. self._yolo = YOLO(model_name)             # ultralytics wrapper
      2. self._yolo.to(device)
      3. self.model = self._yolo.model             # underlying nn.Module
      4. super().__init__()                        # TorchBackendMixin: eval + freeze

    Inference flow (process_frame):
      with self._inference():                      # torch.inference_mode() via mixin
          results = self._yolo(rgb, conf=..., verbose=False)

    Availability probe (D-05): classmethod returns (False, install-hint) when
    either ultralytics or torch is missing from the env, so the registry's
    list_backends() can surface a clean "pip install ..." message to the UI.
    """

    CAPABILITIES: dict = {
        "framework": "ultralytics",
        "license": "AGPL-3.0",
        "cpu_latency_hint_ms": 120,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }

    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "confidence": {
                "type": "number",
                "default": 0.5,
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Score threshold below which detections are dropped",
                "live_tunable": True,
            },
            "min_bbox_size_px": {
                "type": "integer",
                "default": 20,
                "minimum": 0,
                "maximum": 200,
                "description": "Drop detections with width or height below this (pixels)",
                "live_tunable": True,
            },
            "class_filter": {
                "type": ["array", "null"],
                "default": None,
                "items": {"type": "integer"},
                "description": "List of COCO class IDs to keep (null = INDOOR_CLASSES default)",
                "live_tunable": True,
            },
        },
    }

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence: float = 0.5,
        device: str = "cpu",
        min_bbox_size_px: int = 20,
        class_filter: list[int] | None = None,
    ) -> None:
        # Lazy import — keeps the backends package importable when ultralytics
        # isn't installed (registry.available() still works).
        try:
            from ultralytics import YOLO  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "YOLOv11Backend requires ultralytics>=8.4.24 and torch>=2.10.0. "
                "Install via: pip install -e '.[perception]'"
            ) from exc

        self._model_name = model_name
        self._confidence = float(confidence)
        self._device = device
        self._min_bbox_size_px = int(min_bbox_size_px)
        self._class_filter = class_filter  # None → use INDOOR_CLASSES

        # Construct YOLO wrapper; pull out underlying nn.Module for TorchBackendMixin.
        self._yolo = YOLO(model_name)
        self._yolo.to(device)
        self.model = self._yolo.model  # nn.Module — TorchBackendMixin freezes it

        super().__init__()  # TorchBackendMixin: self.model.eval() + freeze params

        # Rolling timing buffers (separate first-inference from steady-state per P1).
        self._timings: collections.deque[float] = collections.deque(maxlen=100)
        self._first_inference_ms: float | None = None

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        """CONTEXT.md D-05 availability probe.

        Returns (True, None) when both ultralytics and torch import cleanly;
        else (False, install hint). The registry never invents this text.
        """
        try:
            import importlib
            importlib.import_module("ultralytics")
            importlib.import_module("torch")
        except ImportError as exc:
            return False, f"pip install ultralytics>=8.4.24 torch>=2.10.0 ({exc})"
        return True, None

    def _effective_class_filter(self) -> set[int]:
        if self._class_filter is None:
            return set(INDOOR_CLASSES.keys())
        return set(self._class_filter)

    def _run_inference(self, rgb: np.ndarray) -> Detections2D:
        """Shared forward path for process_frame + warmup."""
        t0 = time.perf_counter()
        with self._inference():
            results = self._yolo(rgb, conf=self._confidence, verbose=False)
        inference_ms = (time.perf_counter() - t0) * 1000.0

        items: list[Detection2D] = []
        allowed = self._effective_class_filter()

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                if cls_id not in allowed:
                    continue
                score = float(box.conf[0])
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                if (x2 - x1) < self._min_bbox_size_px or (y2 - y1) < self._min_bbox_size_px:
                    continue
                cls_name = INDOOR_CLASSES.get(cls_id, f"class_{cls_id}")
                items.append(
                    Detection2D(
                        class_id=cls_id,
                        class_name=cls_name,
                        score=score,
                        bbox_xyxy=(x1, y1, x2, y2),
                        extras=None,
                    )
                )

        h, w = rgb.shape[:2]
        return Detections2D(items=items, inference_ms=inference_ms, image_hw=(h, w))

    def process_frame(self, frame: SensorFrame) -> Detections2D:
        """Run YOLOv11 detection on frame.rgb. No text_prompt (CONTEXT.md D-01)."""
        out = self._run_inference(frame.rgb)
        self._timings.append(out.inference_ms)
        return out

    def warmup(self, dummy_frame: SensorFrame) -> None:
        """One real inference to eliminate first-call stall (Pitfall P1).

        Records the duration into self._first_inference_ms but does NOT add it
        to the steady-state timings deque — CONTEXT.md requires these two
        numbers to be reported separately so a 5 s first call doesn't skew
        the live p50 metric.
        """
        out = self._run_inference(dummy_frame.rgb)
        self._first_inference_ms = out.inference_ms

    def reset(self) -> None:
        self._timings.clear()

    def get_metrics(self) -> dict:
        if self._timings:
            arr = np.asarray(self._timings, dtype=np.float64)
            p50 = float(np.percentile(arr, 50))
            p95 = float(np.percentile(arr, 95))
        else:
            p50 = p95 = 0.0
        return {
            "inference_ms_p50": p50,
            "inference_ms_p95": p95,
            "first_inference_ms": self._first_inference_ms,
            "n_samples": len(self._timings),
            "framework": "ultralytics",
            "model_name": self._model_name,
        }

    def apply_params(self, params: dict[str, Any]) -> dict[str, str]:
        status: dict[str, str] = {}
        for key, val in params.items():
            if key == "confidence":
                self._confidence = float(val)
                status[key] = "applied"
            elif key == "min_bbox_size_px":
                self._min_bbox_size_px = int(val)
                status[key] = "applied"
            elif key == "class_filter":
                if val is None or isinstance(val, list):
                    self._class_filter = val
                    status[key] = "applied"
                else:
                    status[key] = "invalid_value"
            else:
                status[key] = "unknown_parameter"
        return status
