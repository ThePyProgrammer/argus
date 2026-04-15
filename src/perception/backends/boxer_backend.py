"""facebook/BoxeR subprocess composer backend (DET-MODELS-03).

BoxeR runs in its own Python venv (subprocess_venvs/boxer/) with its own
torch/DINOv3/BoxerNet/moderngl stack. This class is the IN-PROCESS composer
— it owns a SubprocessDetectorBridge, spawns scripts/boxer_worker.py as
the worker, and translates msgpack replies into Detections3D.

Invariants (per 05-CONTEXT.md):
  * D-05 — __init__ is CHEAP. Bridge spawn happens on first warmup() call.
  * D-02 — msgpack reply carries FULL extents (w,h,d); composer DIVIDES BY 2
           to produce OrientedBox3D.half_extents. Failing to halve renders
           boxes 2x real size in Three.js.
  * Phase 1 D-10 — OrientedBox3D(...) is the ONLY quaternion construction
           site. Composer passes qx,qy,qz,qw from the wire dict directly;
           no rotation-matrix math, no Rotation import here.
  * D-14 — CAPABILITIES['license'] == 'CC-BY-NC-4.0' surfaces in the
           Phase 3 DetectorDropdown badge.

Operational:
  * outputs_3d_natively=True -> Phase 3 D-08 auto-hides LifterDropdown.
  * BoxeR is a SINGLE-PROCESS detector — one subprocess serves all robots.
    Per-robot fan-out is sequential through the shared bridge (see
    DetectorWorkerPool for routing). This contrasts with RT-DETRv2 which
    has per-worker ORT sessions.
"""

from __future__ import annotations

import collections
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from src.bridge.sensor_types import SensorFrame
from src.perception.registry import detector_backend
from src.perception.subprocess_bridge import (
    BridgeHangError,  # noqa: F401 -- re-exported for pool crash handler (Plan 09)
    SubprocessDetectorBridge,
    SubprocessDiedError,  # noqa: F401 -- re-exported for pool crash handler (Plan 09)
)
from src.perception.types import (
    Detection2D,
    Detections3D,
    DetectorInput,
    OrientedBox3D,
)

logger = logging.getLogger(__name__)

# --- Pinned checkpoint metadata (D-12) — DO NOT DRIFT ---
# Verified via GitHub API 2026-04-15. Mirrored in scripts/boxer_worker.py +
# scripts/setup_boxer_subprocess.sh + scripts/download_models.py.
BOXER_SHA: str = "df474128a76ba42b05bc81feca7ac1a53fab41af"
BOXER_REPO_URL: str = "https://github.com/facebookresearch/boxer"
BOXER_MODEL_DIR: Path = Path("models") / "boxer" / BOXER_SHA

# Subprocess venv location (D-01).
_VENV_DIR: Path = Path("subprocess_venvs") / "boxer"
_READY_MARKER: Path = _VENV_DIR / ".ready"
_WORKER_PYTHON: Path = _VENV_DIR / "bin" / "python"
_WORKER_SCRIPT: Path = Path("scripts") / "boxer_worker.py"

# COCO 80-class name mapping. BoxeR outputs COCO-class ids via its internal
# OWLv2 proposal network; composer falls back to f"class_{id}" for uncovered ids.
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

# Handshake budget: BoxeR's DINOv3+BoxerNet+OWLv2 weight load can take 5-15 s;
# allow 60 s to cover worst-case cold disk + slow CPU (Open Risk #3 mitigation).
_HANDSHAKE_TIMEOUT_S: float = 60.0


@detector_backend(name="boxer", display="facebook/BoxeR (subprocess)")
class BoxeRBackend:
    """Composer for BoxeR running in a subprocess venv (DET-MODELS-03)."""

    CAPABILITIES: dict[str, Any] = {
        "framework": "subprocess",
        "license": "CC-BY-NC-4.0",       # D-14 — badged by Phase 3
        "cpu_latency_hint_ms": 15000,    # 5–30 s/frame per STACK.md; midpoint for UI hint
        "outputs_3d_natively": True,     # Phase 3 D-08 -> LifterDropdown auto-hidden
        "input_type": DetectorInput.RGBD,
        "track_id_support": False,
    }

    PARAMETER_SCHEMA: dict[str, Any] = {
        "score_threshold": {
            "type": "float", "min": 0.0, "max": 1.0, "default": 0.3,
            "description": "Per-detection score floor (below -> filtered out).",
        },
    }

    def __init__(self, score_threshold: float = 0.3) -> None:
        """D-05: CHEAP constructor — no Popen, no socket, no filesystem I/O."""
        self._score_threshold = float(score_threshold)
        self._bridge: SubprocessDetectorBridge | None = None
        self._inference_times: collections.deque[float] = collections.deque(maxlen=100)
        self._first_inference_ms: float | None = None

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        if _READY_MARKER.exists():
            return True, None
        return False, (
            "Run `make download-models-boxer` (scripts/setup_boxer_subprocess.sh) "
            f"to create {_VENV_DIR}/.ready and fetch pinned checkpoints."
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_bridge(self) -> SubprocessDetectorBridge:
        """Lazy-spawn the bridge on first use (D-05)."""
        if self._bridge is not None:
            return self._bridge
        if not _READY_MARKER.exists():
            raise RuntimeError(
                f"BoxeR subprocess venv not set up: {_READY_MARKER} missing. "
                f"Run `make download-models-boxer` first."
            )
        bridge = SubprocessDetectorBridge(
            binary_path=str(_WORKER_PYTHON),
            args=[str(_WORKER_SCRIPT)],
        )
        bridge.start()
        # Open Risk #3 mitigation — wait for worker to connect AFTER its
        # model-load completes. Without this, the first send_frame races
        # BoxeR's 5–15 s weight load and fires a spurious BridgeHangError.
        bridge.wait_for_handshake(timeout_s=_HANDSHAKE_TIMEOUT_S)
        self._bridge = bridge
        logger.info(
            "BoxeRBackend bridge ready (pid=%s)",
            getattr(bridge, "_process", None) and bridge._process.pid,
        )
        return bridge

    def warmup(self, dummy_frame: SensorFrame) -> None:
        """D-05: lazy spawn happens HERE, not in __init__."""
        self._ensure_bridge()
        t0 = time.perf_counter()
        _ = self.process_frame(dummy_frame)
        self._first_inference_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "BoxeR warmup complete (first_inference_ms=%.1f)",
            self._first_inference_ms,
        )

    def process_frame(self, frame: SensorFrame) -> Detections3D:
        """Send frame to BoxeR worker, translate reply into Detections3D.

        Reply schema per 05-CONTEXT.md D-02. Extent halving per D-02 gotcha line.
        """
        bridge = self._ensure_bridge()
        reply = bridge.send_frame(
            rgb=frame.rgb,
            depth=frame.depth,
            timestamp=float(frame.sim_time),
            params={"score_threshold": self._score_threshold},
        )
        # send_frame raises BridgeHangError / SubprocessDiedError on failure
        # (Plan 05) — no None-return path to handle here. The exceptions
        # propagate to DetectorWorker.process_frame -> pool.on_backend_crash.
        assert reply is not None  # narrow for type checker

        inference_ms = float(reply.get("inference_ms", 0.0))
        self._inference_times.append(inference_ms)

        items_3d: list[OrientedBox3D] = []
        items_2d: list[Detection2D] = []  # noqa: F841 -- reserved for CameraFeed overlay surfacing in future plans
        boxes_3d = reply.get("boxes_3d") or []
        classes = reply.get("classes") or []
        scores = reply.get("scores") or []
        bboxes = reply.get("bboxes") or []
        H, W = frame.rgb.shape[:2]

        for idx, b3 in enumerate(boxes_3d):
            cid = int(classes[idx]) if idx < len(classes) else 0
            score = float(scores[idx]) if idx < len(scores) else 0.0
            if score < self._score_threshold:
                continue
            cname = _COCO_NAMES.get(cid, f"class_{cid}")
            bb2d = bboxes[idx] if idx < len(bboxes) else None
            bbox_xyxy: tuple[int, int, int, int] | None = (
                (int(bb2d[0]), int(bb2d[1]), int(bb2d[2]), int(bb2d[3]))
                if bb2d and len(bb2d) >= 4
                else None
            )
            # D-02 gotcha: reply sends FULL extents (w, h, d).
            # OrientedBox3D.half_extents wants HALF. Divide by 2.
            # This is the CRITICAL correctness line — missing it renders boxes 2x size.
            half_extents = np.array(
                [float(b3["w"]) / 2.0, float(b3["h"]) / 2.0, float(b3["d"]) / 2.0],
                dtype=np.float64,
            )
            # Phase 1 D-10 invariant: OrientedBox3D is the ONLY quaternion
            # construction site. Composer passes wire-dict values straight
            # through — NO matrix math, NO Rotation import.
            items_3d.append(OrientedBox3D(
                center=np.array(
                    [float(b3["tx"]), float(b3["ty"]), float(b3["tz"])],
                    dtype=np.float64,
                ),
                half_extents=half_extents,
                quaternion=np.array(
                    [float(b3["qx"]), float(b3["qy"]), float(b3["qz"]), float(b3["qw"])],
                    dtype=np.float64,
                ),
                class_id=cid,
                class_name=cname,
                score=score,
                track_id=None,
                bbox_xyxy=bbox_xyxy,
            ))

        # Detections3D envelope. DetectorWorker overwrites capture_pose +
        # capture_timestamp post-return (Phase 2 D-11) — we leave defaults.
        return Detections3D(
            items=items_3d,
            detector_ms=inference_ms,
            lifter_ms=0.0,    # native — no lifter in the path
            n_raw=len(boxes_3d),
            n_final=len(items_3d),
            image_hw=(int(H), int(W)),
        )

    def reset(self) -> None:
        self._inference_times.clear()

    def shutdown(self) -> None:
        """Tear down bridge + worker. Idempotent."""
        if self._bridge is not None:
            try:
                self._bridge.shutdown()
            except Exception:  # noqa: BLE001 — shutdown must never raise
                logger.exception("Error during BoxeRBackend.shutdown")
            finally:
                self._bridge = None

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
