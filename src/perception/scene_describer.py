"""VLM-based scene description for robot camera feeds.

Runs a vision-language model on camera frames to generate natural
language descriptions of what each robot sees. Useful for semantic
understanding and logging.

Supports multiple backends:
- moondream (local, CPU-friendly, ~3-5s per image)
- openai (cloud, fast, requires API key)

Requires: pip install transformers torch
Falls back gracefully if not installed.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)

VLM_AVAILABLE = False
_vlm_backend = None

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    VLM_AVAILABLE = True
except ImportError:
    logger.info("transformers/torch not installed -- VLM scene description disabled.")


@dataclass
class SceneDescription:
    """A scene description for one robot."""
    robot_id: str
    description: str
    timestamp: float
    objects: list[str]  # extracted object names


class SceneDescriber:
    """Background VLM that describes what each robot sees.

    Runs at a configurable interval (default every 10 seconds)
    to avoid overwhelming the CPU.

    Usage:
        describer = SceneDescriber()
        describer.start()
        describer.submit_frame("robot_a", rgb_image)
        desc = describer.get_description("robot_a")
        describer.stop()
    """

    def __init__(
        self,
        model_name: str = "vikhyatk/moondream2",
        interval_s: float = 10.0,
        device: str = "cpu",
    ):
        self._model_name = model_name
        self._interval_s = interval_s
        self._device = device
        self._model = None
        self._tokenizer = None
        self._running = False
        self._thread: threading.Thread | None = None

        self._pending_frames: dict[str, np.ndarray] = {}
        self._results: dict[str, SceneDescription] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """Load model and start background description thread."""
        if not VLM_AVAILABLE:
            logger.warning("VLM not available -- scene describer not started")
            return

        try:
            logger.info("Loading VLM model %s (this may take a moment)...", self._model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name, trust_remote_code=True,
                torch_dtype=torch.float32,
            ).to(self._device)
            logger.info("VLM model loaded on %s", self._device)
        except Exception as e:
            logger.warning("Failed to load VLM model: %s", e)
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)

    def submit_frame(self, robot_id: str, rgb: np.ndarray) -> None:
        """Submit a frame for description. Only latest per robot is kept."""
        with self._lock:
            self._pending_frames[robot_id] = rgb

    def get_description(self, robot_id: str) -> SceneDescription | None:
        with self._lock:
            return self._results.get(robot_id)

    def get_all_descriptions(self) -> dict[str, SceneDescription]:
        with self._lock:
            return dict(self._results)

    def _run_loop(self) -> None:
        while self._running:
            with self._lock:
                frames = dict(self._pending_frames)
                self._pending_frames.clear()

            for robot_id, rgb in frames.items():
                try:
                    desc = self._describe(rgb)
                    objects = self._extract_objects(desc)
                    with self._lock:
                        self._results[robot_id] = SceneDescription(
                            robot_id=robot_id,
                            description=desc,
                            timestamp=time.monotonic(),
                            objects=objects,
                        )
                    logger.info("[%s] Scene: %s", robot_id, desc[:100])
                except Exception as e:
                    logger.warning("VLM failed for %s: %s", robot_id, e)

            time.sleep(self._interval_s)

    def _describe(self, rgb: np.ndarray) -> str:
        """Run VLM on one image."""
        if self._model is None:
            return ""

        from PIL import Image
        img = Image.fromarray(rgb)

        # Moondream2 API
        enc_image = self._model.encode_image(img)
        result = self._model.answer_question(
            enc_image,
            "Describe what you see in this image in one sentence. Focus on furniture, walls, and room layout.",
            self._tokenizer,
        )
        return result.strip()

    def _extract_objects(self, description: str) -> list[str]:
        """Extract object names from a description string."""
        # Simple keyword extraction
        common_objects = [
            "chair", "table", "desk", "wall", "door", "window", "floor",
            "shelf", "cabinet", "monitor", "computer", "lamp", "plant",
            "couch", "sofa", "bed", "pillar", "column", "box", "room",
        ]
        found = []
        desc_lower = description.lower()
        for obj in common_objects:
            if obj in desc_lower:
                found.append(obj)
        return found
