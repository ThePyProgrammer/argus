"""YOLO-based object detection for robot camera feeds.

Runs YOLOv11-nano on CPU in a background thread. Detections are
stored per-robot and can be queried by the coordinator for
semantic labeling of the point cloud and web UI overlays.

Requires: pip install ultralytics
Falls back gracefully if not installed.
"""

from __future__ import annotations

import os
os.environ["NNPACK_DISABLE"] = "1"  # suppress NNPACK warnings on unsupported hardware

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

try:
    import warnings
    warnings.filterwarnings("ignore", message=".*NNPACK.*")
    import torch
    torch.set_num_threads(2)  # limit CPU usage for background detection
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.info("ultralytics not installed -- YOLO detection disabled. pip install ultralytics to enable.")


@dataclass
class Detection:
    """A single 2D object detection."""
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    center_3d: np.ndarray | None = None  # (3,) world position if depth available


@dataclass
class RobotDetections:
    """Latest detections for one robot."""
    robot_id: str
    detections: list[Detection] = field(default_factory=list)
    timestamp: float = 0.0


class ObjectDetector:
    """Background YOLO detector that processes robot camera frames.

    Usage:
        detector = ObjectDetector()
        detector.start()
        detector.submit_frame("robot_a", rgb_image, depth_image, camera_pose)
        detections = detector.get_detections("robot_a")
        detector.stop()
    """

    # COCO classes relevant to indoor/office scenes
    INDOOR_CLASSES = {
        56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
        60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
        64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone",
        72: "refrigerator", 73: "book", 74: "clock", 75: "vase",
        0: "person", 24: "backpack", 25: "umbrella", 26: "handbag",
        39: "bottle", 41: "cup", 42: "fork", 43: "knife",
        44: "spoon", 45: "bowl",
    }

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence: float = 0.5,  # higher threshold for synthetic images
        device: str = "cpu",
        max_fps: float = 2.0,
    ):
        self._model_name = model_name
        self._confidence = confidence
        self._device = device
        self._min_interval = 1.0 / max_fps
        self._model = None
        self._running = False
        self._thread: threading.Thread | None = None

        # Per-robot state
        self._pending_frames: dict[str, tuple[np.ndarray, np.ndarray | None, np.ndarray]] = {}
        self._results: dict[str, RobotDetections] = {}
        self._lock = threading.Lock()
        self._last_cloud: np.ndarray | None = None  # latest SLAM frame cloud

    def start(self) -> None:
        """Load model and start background detection thread."""
        if not YOLO_AVAILABLE:
            logger.warning("YOLO not available -- detector not started")
            return

        try:
            self._model = YOLO(self._model_name)
            self._model.to(self._device)
            logger.info("YOLO model loaded: %s on %s", self._model_name, self._device)
        except Exception as e:
            logger.warning("Failed to load YOLO model: %s", e)
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the detection thread."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)

    def submit_frame(
        self,
        robot_id: str,
        rgb: np.ndarray,
        depth: np.ndarray | None = None,
        pose: np.ndarray | None = None,
        slam_cloud: np.ndarray | None = None,
    ) -> None:
        """Submit a frame for detection. Only latest frame per robot is kept."""
        with self._lock:
            self._pending_frames[robot_id] = (rgb, depth, pose if pose is not None else np.eye(4))
            if slam_cloud is not None:
                self._last_cloud = slam_cloud

    def get_detections(self, robot_id: str) -> list[Detection]:
        """Get latest detections for a robot."""
        with self._lock:
            result = self._results.get(robot_id)
            return result.detections if result else []

    def get_all_detections(self) -> dict[str, list[Detection]]:
        """Get detections for all robots."""
        with self._lock:
            return {rid: r.detections for rid, r in self._results.items()}

    def _run_loop(self) -> None:
        """Background loop: process pending frames."""
        while self._running:
            # Grab pending frames
            with self._lock:
                frames = dict(self._pending_frames)
                self._pending_frames.clear()

            if not frames:
                time.sleep(0.05)
                continue

            for robot_id, (rgb, depth, pose) in frames.items():
                try:
                    detections = self._detect(rgb, depth, pose)
                    with self._lock:
                        self._results[robot_id] = RobotDetections(
                            robot_id=robot_id,
                            detections=detections,
                            timestamp=time.monotonic(),
                        )
                except Exception as e:
                    logger.warning("Detection failed for %s: %s", robot_id, e)

            time.sleep(self._min_interval)

    def _detect(
        self,
        rgb: np.ndarray,
        depth: np.ndarray | None,
        pose: np.ndarray,
    ) -> list[Detection]:
        """Run YOLO on one frame."""
        if self._model is None:
            return []

        results = self._model(rgb, conf=self._confidence, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])

                # Filter: only keep indoor-relevant classes
                if cls_id not in self.INDOOR_CLASSES:
                    continue

                cls_name = self.INDOOR_CLASSES[cls_id]
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                # Filter: skip tiny detections (likely noise)
                if (x2 - x1) < 20 or (y2 - y1) < 20:
                    continue

                det = Detection(
                    class_id=cls_id,
                    class_name=cls_name,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                )

                # Estimate 3D position using per-pixel ray from camera intrinsics
                if depth is not None:
                    cx_px, cy_px = (x1 + x2) // 2, (y1 + y2) // 2
                    h_img, w_img = depth.shape
                    cx_px = min(max(cx_px, 0), w_img - 1)
                    cy_px = min(max(cy_px, 0), h_img - 1)

                    # Median depth in bbox
                    roi = depth[max(0,y1):min(h_img,y2), max(0,x1):min(w_img,x2)]
                    valid_roi = roi[(roi > 0.1) & (roi < 15.0)]
                    if len(valid_roi) > 0:
                        d = float(np.median(valid_roi))

                        # Unproject bbox center to camera-frame ray using intrinsics
                        # Same math as Open3D create_from_depth_image:
                        # OpenCV convention: X=right, Y=down, Z=forward
                        import math as _math
                        fov_rad = _math.radians(70.0)
                        f = h_img / (2.0 * _math.tan(fov_rad / 2.0))
                        cam_x = (cx_px - w_img / 2.0) * d / f
                        cam_y = (cy_px - h_img / 2.0) * d / f

                        # Apply same Y/Z flip as SLAM cloud (config 1: Y- Z-)
                        cam_pt = np.array([cam_x, -cam_y, -d])

                        # Transform to world: cam_mat @ cam_pt + cam_pos
                        # pose is cam_xmat (no transpose) + cam_xpos
                        world_pt = pose[:3, :3] @ cam_pt + pose[:3, 3]
                        det.center_3d = world_pt

                detections.append(det)

        return detections
