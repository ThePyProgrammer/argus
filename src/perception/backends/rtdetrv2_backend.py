"""RT-DETRv2-S ONNX backend — in-process, real-time transformer detector.

DET-MODELS-02 implementation. Pinned via RT_DETRV2_SHA (module constant).

Framework note: unlike YOLOv11Backend, this backend does NOT use
TorchBackendMixin — ORT has its own graph/inference lifecycle and there is
no torch.nn.Module here. The DetectorProtocol contract is satisfied by
implementing process_frame, reset, warmup, get_metrics, CAPABILITIES,
PARAMETER_SCHEMA directly. eval()/inference_mode() are no-ops for ORT
(the session is always in inference mode by construction).

D-07 invariant: ort.SessionOptions.intra_op_num_threads reads from
src._thread_config.get_default_budget() — DO NOT hardcode thread counts
in this file (Phase 1 D-04 invariant).

D-08 invariant: static input shape [1, 3, 320, 320]. Backend letterbox-
resizes MuJoCo 480×640 RGB frames to 320×320 preserving aspect ratio with
black padding, then scales output bboxes back to 480×640 coords.
"""

from __future__ import annotations

import collections
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from src._thread_config import get_default_budget
from src.bridge.sensor_types import SensorFrame
from src.perception.registry import detector_backend
from src.perception.types import Detection2D, Detections2D, DetectorInput

logger = logging.getLogger(__name__)

# --- Pinned checkpoint metadata (D-12) — DO NOT DRIFT ---
# Verified via HF API 2026-04-15 (Plan 05 research session).
# Mirrors the same constants in scripts/download_models.py.
RT_DETRV2_SHA: str = "5650961749fa93567c0d46fc7f43ea4f9e914107"
RT_DETRV2_REPO: str = "PekingU/rtdetr_v2_r18vd"
RT_DETRV2_MODEL_DIR: Path = Path("models") / "rtdetrv2" / RT_DETRV2_SHA

# Static input size per D-08. ONNX export uses [1, 3, 320, 320].
_INPUT_H: int = 320
_INPUT_W: int = 320

# COCO 80-class name mapping for human-readable class_name field in Detection2D.
# Sourced from the standard COCO 80 class set (RT-DETRv2 trained on COCO).
_COCO_NAMES: dict[int, str] = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus",
    6: "train", 7: "truck", 8: "boat", 9: "traffic light", 10: "fire hydrant",
    11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat",
    16: "dog", 17: "horse", 18: "sheep", 19: "cow", 20: "elephant", 21: "bear",
    22: "zebra", 23: "giraffe", 24: "backpack", 25: "umbrella", 26: "handbag",
    27: "tie", 28: "suitcase", 29: "frisbee", 30: "skis", 31: "snowboard",
    32: "sports ball", 33: "kite", 34: "baseball bat", 35: "baseball glove",
    36: "skateboard", 37: "surfboard", 38: "tennis racket", 39: "bottle",
    40: "wine glass", 41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli",
    51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut", 55: "cake", 56: "chair",
    57: "couch", 58: "potted plant", 59: "bed", 60: "dining table", 61: "toilet",
    62: "tv", 63: "laptop", 64: "mouse", 65: "remote", 66: "keyboard",
    67: "cell phone", 68: "microwave", 69: "oven", 70: "toaster", 71: "sink",
    72: "refrigerator", 73: "book", 74: "clock", 75: "vase", 76: "scissors",
    77: "teddy bear", 78: "hair drier", 79: "toothbrush",
}


def _letterbox_320(rgb: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Letterbox-resize a (H,W,3) uint8 RGB to (1,3,320,320) float32 / 255.

    Preserves aspect ratio; pads with black. Returns (chw_float32, scale,
    (pad_top, pad_left)) so process_frame can reverse the transform.

    D-08: normalization is rescale-only (/255) — RT-DETR family uses
    do_normalize=False by default in RTDetrImageProcessor. See 05-RESEARCH.md
    Assumption A5 — verify against actual preprocessor_config.json in smoke test.
    """
    import cv2  # noqa: PLC0415 -- opencv-python-headless core dep (Phase 4)
    H, W = rgb.shape[:2]
    scale = float(min(_INPUT_H / H, _INPUT_W / W))
    new_h = int(round(H * scale))
    new_w = int(round(W * scale))
    resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_top = (_INPUT_H - new_h) // 2
    pad_left = (_INPUT_W - new_w) // 2
    canvas = np.zeros((_INPUT_H, _INPUT_W, 3), dtype=np.uint8)
    canvas[pad_top:pad_top + new_h, pad_left:pad_left + new_w] = resized
    chw = canvas.transpose(2, 0, 1).astype(np.float32) / 255.0
    return chw[None, ...], scale, (pad_top, pad_left)


def _decode_boxes(
    pred_boxes_norm: np.ndarray,
    logits: np.ndarray,
    scale: float,
    pad: tuple[int, int],
    orig_hw: tuple[int, int],
    score_threshold: float,
) -> list[Detection2D]:
    """Decode (N_queries, 4) cxcywh-normalized boxes + (N_queries, 80) logits.

    RT-DETRv2 outputs pred_boxes normalized to [0,1] in the 320×320 letterboxed
    canvas. Reverses letterbox scale+pad to produce pixel coords in orig_hw.
    """
    from scipy.special import expit as sigmoid  # noqa: PLC0415 -- lazy numeric import
    # class_id = argmax over logits; score = sigmoid of max logit
    class_ids = np.argmax(logits, axis=-1).astype(np.int32)         # (N,)
    max_logits = np.take_along_axis(
        logits, class_ids[..., None], axis=-1
    ).squeeze(-1)
    scores = sigmoid(max_logits)                                     # (N,)
    keep = scores >= score_threshold
    if not np.any(keep):
        return []
    cxcywh = pred_boxes_norm[keep] * float(_INPUT_W)  # un-normalize to 320×320
    cids = class_ids[keep]
    scs = scores[keep]
    x0 = cxcywh[:, 0] - cxcywh[:, 2] / 2 - pad[1]
    y0 = cxcywh[:, 1] - cxcywh[:, 3] / 2 - pad[0]
    x1 = cxcywh[:, 0] + cxcywh[:, 2] / 2 - pad[1]
    y1 = cxcywh[:, 1] + cxcywh[:, 3] / 2 - pad[0]
    # Reverse letterbox scale
    x0 = (x0 / scale).clip(0, orig_hw[1] - 1)
    y0 = (y0 / scale).clip(0, orig_hw[0] - 1)
    x1 = (x1 / scale).clip(0, orig_hw[1] - 1)
    y1 = (y1 / scale).clip(0, orig_hw[0] - 1)
    items: list[Detection2D] = []
    for i in range(len(cids)):
        cid = int(cids[i])
        items.append(Detection2D(
            class_id=cid,
            class_name=_COCO_NAMES.get(cid, f"class_{cid}"),
            score=float(scs[i]),
            bbox_xyxy=(int(x0[i]), int(y0[i]), int(x1[i]), int(y1[i])),
        ))
    return items


@detector_backend(name="rtdetrv2", display="RT-DETRv2-S (ONNX)")
class RTDETRv2Backend:
    """RT-DETRv2-S backend via onnxruntime CPU EP (DET-MODELS-02).

    Construction is cheap once the ONNX artifact exists — just an ORT
    InferenceSession. If the artifact is missing, construction raises with
    a `make download-models-rtdetrv2` hint (D-06 — no auto-download).
    """

    CAPABILITIES: dict[str, Any] = {
        "framework": "onnxruntime",
        "license": "Apache-2.0",
        "cpu_latency_hint_ms": 120,     # research estimate A1; smoke-confirm in Wave 2
        "outputs_3d_natively": False,   # needs PointClusterLifter downstream
        "input_type": DetectorInput.RGB_ONLY,
        "track_id_support": False,
    }

    PARAMETER_SCHEMA: dict[str, Any] = {
        "score_threshold": {
            "type": "float",
            "min": 0.0,
            "max": 1.0,
            "default": 0.5,
            "description": "Per-detection score floor (below → filtered out).",
        },
    }

    def __init__(self, score_threshold: float = 0.5) -> None:
        # Import here to avoid pulling onnxruntime into sys.modules when
        # the backend is enumerated but not instantiated (Phase 1 D-09
        # lazy-import hygiene).
        import onnxruntime as ort  # noqa: PLC0415

        onnx_path = RT_DETRV2_MODEL_DIR / "model.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(
                f"RT-DETRv2 ONNX artifact missing at {onnx_path}. "
                f"Run `make download-models-rtdetrv2` to fetch + export. "
                f"(pin: revision={RT_DETRV2_SHA}, repo={RT_DETRV2_REPO})"
            )

        sess_options = ort.SessionOptions()
        # D-07 invariant: read thread budget from _thread_config, never hardcode.
        sess_options.intra_op_num_threads = get_default_budget()
        sess_options.inter_op_num_threads = 1
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self._session = ort.InferenceSession(
            str(onnx_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self._score_threshold = float(score_threshold)
        self._inference_times: collections.deque[float] = collections.deque(maxlen=100)
        self._first_inference_ms: float | None = None

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        onnx_path = RT_DETRV2_MODEL_DIR / "model.onnx"
        if onnx_path.exists():
            return True, None
        return False, (
            f"Run `make download-models-rtdetrv2` to fetch + export the "
            f"pinned {RT_DETRV2_REPO} checkpoint to {onnx_path}."
        )

    def warmup(self, dummy_frame: SensorFrame) -> None:
        """Run one real inference so first production inference is hot."""
        t0 = time.perf_counter()
        _ = self.process_frame(dummy_frame)
        self._first_inference_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "RT-DETRv2 warmup complete (first_inference_ms=%.1f)",
            self._first_inference_ms,
        )

    def process_frame(self, frame: SensorFrame) -> Detections2D:
        rgb = frame.rgb
        H, W = rgb.shape[:2]
        x, scale, pad = _letterbox_320(rgb)

        t0 = time.perf_counter()
        logits, pred_boxes = self._session.run(None, {"pixel_values": x})
        inference_ms = (time.perf_counter() - t0) * 1000.0
        self._inference_times.append(inference_ms)

        # Strip batch dim
        logits = logits[0]          # (N, 80)
        pred_boxes = pred_boxes[0]  # (N, 4) cxcywh normalized

        items = _decode_boxes(
            pred_boxes, logits, scale, pad, orig_hw=(H, W),
            score_threshold=self._score_threshold,
        )
        return Detections2D(items=items, inference_ms=inference_ms, image_hw=(H, W))

    def reset(self) -> None:
        """No-op: ORT sessions are stateless across calls."""
        self._inference_times.clear()

    def get_metrics(self) -> dict[str, Any]:
        if not self._inference_times:
            return {
                "inference_ms_p50": 0.0,
                "inference_ms_p95": 0.0,
                "first_inference_ms": self._first_inference_ms,
            }
        arr = np.asarray(self._inference_times, dtype=np.float64)
        return {
            "inference_ms_p50": float(np.median(arr)),
            "inference_ms_p95": float(np.percentile(arr, 95)),
            "first_inference_ms": self._first_inference_ms,
        }

    def apply_params(self, params: dict[str, Any]) -> dict[str, str]:
        status: dict[str, str] = {}
        for key, val in params.items():
            if key == "score_threshold":
                self._score_threshold = float(val)
                status[key] = "applied"
            else:
                status[key] = "unknown_parameter"
        return status
