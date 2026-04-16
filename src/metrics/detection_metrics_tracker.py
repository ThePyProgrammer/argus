"""Per-robot detection metrics accumulation with ring buffers.

Parallel sibling to the SLAM metrics tracker in ``src/metrics/metrics_tracker.py``
(per CONTEXT D-01 — NO inheritance; zero shared fields with the SLAM tracker).
Consumes ``latest`` (Detections3D | None), ``inspect`` (DetectorWorker.inspect()
return), and ``backend_metrics`` (DetectorProtocol.get_metrics() return) per tick
per robot per CONTEXT D-02. Nearest-neighbor jitter with 0.5m gate per CONTEXT
D-03.

Phase 6 SC#2 revision (2026-04-15) adds ``record_gt_match`` + ``reset_gt`` +
``detection_gt_metrics`` in the stats payload (per CONTEXT D-09): accumulates
per-robot per-class ``center_error_m`` (mean over last 60 matched frames) and
``per_class_recall`` (matched_count / frames_observed).
"""

from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np


# CONTEXT D-03 — nearest-neighbor gate + history window for stddev math.
_JITTER_GATE_M = 0.5
_JITTER_HISTORY = 30

# CONTEXT D-09 — per-class center-error ring buffer length for SC#2 stability.
_GT_ERR_RING_LEN = 60


class DetectionMetricsTracker:
    """Per-robot detection-metrics tracker (parallel to the SLAM tracker).

    Live metrics per robot (7 keys, all emitted in the stats payload):
      inference_ms_p50, inference_ms_p95, detections_per_frame,
      mean_confidence, queue_depth, freshness_s, jitter_m.

    History rings (per robot, bounded at ``history_size``):
      inference_ms, det_per_frame, confidence, freshness, jitter.

    SC#2 GT state (per robot per class — isolated from live state so
    ``reset_gt()`` is surgical):
      center_err_ring (deque maxlen=60), matched_count, frames_observed.
    """

    def __init__(self, history_size: int = 60) -> None:
        self._history_size = history_size
        self._per_robot: dict[str, dict[str, Any]] = {}
        # SC#2 / D-09: isolated from `_per_robot` so `reset_gt()` is surgical.
        self._gt_state: dict[str, dict[str, dict[str, Any]]] = {}

    # ────────────────────────────────────────────────────────────
    # Per-robot live state (CONTEXT D-01, D-02, D-03)
    # ────────────────────────────────────────────────────────────
    def _ensure_robot(self, robot_id: str) -> dict:
        if robot_id not in self._per_robot:
            self._per_robot[robot_id] = {
                # Current live values (D-02 SC#1 literal).
                "inference_ms_p50": 0.0,
                "inference_ms_p95": 0.0,
                "detections_per_frame": 0,
                "mean_confidence": 0.0,
                "queue_depth": 0,
                "freshness_s": 0.0,
                "jitter_m": 0.0,
                # Bounded ring buffers (deque maxlen=history_size).
                "inference_ms_history": deque(maxlen=self._history_size),
                "det_per_frame_history": deque(maxlen=self._history_size),
                "confidence_history": deque(maxlen=self._history_size),
                "freshness_history": deque(maxlen=self._history_size),
                "jitter_history": deque(maxlen=self._history_size),
                # Internal NN-jitter state: class_name -> deque[np.ndarray] maxlen=30 (D-03).
                "_tracked_centers": {},
            }
        return self._per_robot[robot_id]

    # ────────────────────────────────────────────────────────────
    # SC#2 GT-match state (Phase 6 revision 2026-04-15)
    # Separate dict from `_per_robot` so `reset_gt()` can clear GT
    # without touching live-metric history (SC#1 continuity).
    # ────────────────────────────────────────────────────────────
    def _ensure_gt(self, robot_id: str, class_name: str) -> dict:
        rid_state = self._gt_state.setdefault(robot_id, {})
        if class_name not in rid_state:
            rid_state[class_name] = {
                "center_err_ring": deque(maxlen=_GT_ERR_RING_LEN),
                "matched_count": 0,
                "frames_observed": 0,
            }
        return rid_state[class_name]

    # ────────────────────────────────────────────────────────────
    # Ingest one tick's-worth of per-robot detection state.
    # ────────────────────────────────────────────────────────────
    def record_frame(
        self,
        robot_id: str,
        sim_now: float,
        latest,  # Detections3D | None
        inspect: dict,  # DetectorWorker.inspect() return
        backend_metrics: dict,  # DetectorProtocol.get_metrics() return
    ) -> None:
        """Record one coordinator-tick's-worth of detection telemetry.

        Args:
            robot_id: Robot identifier.
            sim_now: Current sim-clock seconds (Pitfall 4 — NOT time.time()).
            latest: Most-recent ``Detections3D`` (or ``None`` if pipeline empty).
            inspect: ``DetectorWorker.inspect()`` dict (queue_depth, ...).
            backend_metrics: ``DetectorProtocol.get_metrics()`` dict
                (inference_ms_p50, inference_ms_p95, ...).
        """
        entry = self._ensure_robot(robot_id)

        # Backend-sourced latency (CONTEXT D-02 — tracker does not recompute).
        p50 = float(backend_metrics.get("inference_ms_p50", 0.0))
        p95 = float(backend_metrics.get("inference_ms_p95", 0.0))
        entry["inference_ms_p50"] = p50
        entry["inference_ms_p95"] = p95
        entry["inference_ms_history"].append(p50)

        # Queue depth from inspect().
        entry["queue_depth"] = int(inspect.get("queue_depth", 0))

        # detections_per_frame + mean_confidence + freshness from `latest`.
        if latest is not None:
            items = getattr(latest, "items", None)
            if items is None:
                items = getattr(latest, "boxes", [])
            dpf = len(items)
            confs = [float(obb.score) for obb in items] if items else []
            mean_conf = float(np.mean(confs)) if confs else 0.0
            capture_ts = float(getattr(latest, "capture_timestamp", sim_now))
            freshness = max(0.0, float(sim_now) - capture_ts)
        else:
            dpf = 0
            mean_conf = 0.0
            items = []
            freshness = 0.0
        entry["detections_per_frame"] = dpf
        entry["mean_confidence"] = mean_conf
        entry["freshness_s"] = freshness
        entry["det_per_frame_history"].append(dpf)
        entry["confidence_history"].append(mean_conf)
        entry["freshness_history"].append(freshness)

        # Jitter: per-key nearest-neighbor against last tracked center, 0.5m gate (D-03).
        # Phase 8 D-06: track_id-based jitter lookup (stable across frames).
        tracked = entry["_tracked_centers"]
        class_jitters: list[float] = []
        for obb in items:
            cls = getattr(obb, "class_name", "")
            center = np.asarray(obb.center, dtype=np.float64).reshape(3)
            # Phase 8 D-06: use track_id when available for stable cross-frame jitter.
            track_id = getattr(obb, "track_id", None)
            if track_id is not None:
                key = f"_tid_{track_id}"
            else:
                # Fallback: class-name-based nearest-neighbor proxy (pre-Phase-8 / tracker_none)
                key = cls
            if key not in tracked:
                tracked[key] = deque(maxlen=_JITTER_HISTORY)
                tracked[key].append(center)
            else:
                history = tracked[key]
                last = history[-1]
                if np.linalg.norm(center - last) <= _JITTER_GATE_M:
                    history.append(center)
                else:
                    # NN gate failed — re-seed this key (D-03 step 2).
                    history.clear()
                    history.append(center)
            hist = tracked[key]
            if len(hist) >= 2:
                arr = np.stack(list(hist), axis=0)
                mean = arr.mean(axis=0)
                dists = np.linalg.norm(arr - mean, axis=1)
                class_jitters.append(float(dists.std()))
        # UI shows one number per robot per frame → max over classes (D-03 step 3).
        jitter_max = max(class_jitters) if class_jitters else entry["jitter_m"]
        entry["jitter_m"] = jitter_max
        entry["jitter_history"].append(jitter_max)

    # ────────────────────────────────────────────────────────────
    # SC#2 / CONTEXT D-09: GT-match accumulation.
    # ────────────────────────────────────────────────────────────
    def record_gt_match(
        self,
        robot_id: str,
        class_name: str,
        center_err_m: float | None,
        matched: bool,
    ) -> None:
        """Accumulate one GT-match outcome (SC#2 / CONTEXT D-09).

        ``matched=False`` + ``center_err_m=None`` → unmatched detection /
        false positive (frames_observed increments; ring unchanged).
        ``matched=True`` + ``center_err_m=<float>`` → GT match within gate
        (frames_observed + matched_count increment; ring appends err).

        Per-robot per-class state grows on first call; unknown classes
        are auto-created.
        """
        entry = self._ensure_gt(robot_id, class_name)
        entry["frames_observed"] += 1
        if matched and center_err_m is not None:
            entry["center_err_ring"].append(float(center_err_m))
            entry["matched_count"] += 1

    # ────────────────────────────────────────────────────────────
    # Stats payload (consumed by WebStreamingViz in Plan 08).
    # ────────────────────────────────────────────────────────────
    def get_stats_payload(self) -> dict:
        """Build the detection-tracker portion of the stats WebSocket message.

        Returns three top-level keys:
          - ``detection_metrics``: per-robot current-tick values (7 live keys)
          - ``detection_history``: per-robot ring-buffered history lists
          - ``detection_gt_metrics``: per-robot per-class center_error_m +
            per_class_recall (SC#2). Empty dict before first ``record_gt_match``.
        """
        detection_metrics: dict[str, dict] = {}
        detection_history: dict[str, dict] = {}
        for rid, entry in self._per_robot.items():
            detection_metrics[rid] = {
                "inference_ms_p50": entry["inference_ms_p50"],
                "inference_ms_p95": entry["inference_ms_p95"],
                "detections_per_frame": entry["detections_per_frame"],
                "mean_confidence": entry["mean_confidence"],
                "queue_depth": entry["queue_depth"],
                "freshness_s": entry["freshness_s"],
                "jitter_m": entry["jitter_m"],
            }
            detection_history[rid] = {
                "inference_ms": list(entry["inference_ms_history"]),
                "det_per_frame": list(entry["det_per_frame_history"]),
                "confidence": list(entry["confidence_history"]),
                "freshness": list(entry["freshness_history"]),
                "jitter": list(entry["jitter_history"]),
            }

        # SC#2: per-robot per-class GT aggregates.
        detection_gt_metrics: dict[str, dict] = {}
        for rid, classes in self._gt_state.items():
            per_class: dict[str, dict] = {}
            for cls, st in classes.items():
                ring = st["center_err_ring"]
                center_err: float | None = (
                    float(np.mean(ring)) if len(ring) > 0 else None
                )
                frames_observed = st["frames_observed"]
                recall = (
                    st["matched_count"] / frames_observed
                    if frames_observed > 0
                    else 0.0
                )
                per_class[cls] = {
                    "center_error_m": center_err,
                    "per_class_recall": float(recall),
                }
            detection_gt_metrics[rid] = per_class

        return {
            "detection_metrics": detection_metrics,
            "detection_history": detection_history,
            "detection_gt_metrics": detection_gt_metrics,
        }

    # ────────────────────────────────────────────────────────────
    # Resets.
    # ────────────────────────────────────────────────────────────
    def reset(self) -> None:
        """Clear all per-robot state (live + GT).

        Per RESEARCH §"Anti-patterns": do NOT call on cloud-tracking reset
        unless explicitly invoked — detection history continuity is useful
        across session rotation for debugging.
        """
        self._per_robot.clear()
        self._gt_state.clear()

    def reset_gt(self) -> None:
        """Clear ONLY per-robot GT-match state.

        Preserves live-metric history (SC#1 continuity). Called on explicit
        session rotation when the caller wants recall counters to restart
        from zero without losing detection history.
        """
        self._gt_state.clear()
