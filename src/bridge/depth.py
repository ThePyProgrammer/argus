"""Sanitize the metric camera-axis depth returned by MuJoCo Renderer (3.6+)."""

from __future__ import annotations

import math
from numbers import Real

import numpy as np


def clean_metric_depth(depth: np.ndarray, far_clip_m: float, max_depth_m: float = 20.0) -> np.ndarray:
    """Keep valid distances; use zero for missing, far-plane, or out-of-range pixels.

    Renderer.render() already undoes the OpenGL projection. Image content must
    never be used to infer a different encoding, including for sub-meter scenes.
    Far readings are invalidated rather than clamped into artificial surfaces.
    """
    for name, value in (("far_clip_m", far_clip_m), ("max_depth_m", max_depth_m)):
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    depth = np.asarray(depth)
    if depth.ndim != 2 or not np.issubdtype(depth.dtype, np.floating):
        raise ValueError("Metric depth must be a two-dimensional floating-point image")
    valid = np.isfinite(depth) & (depth > 0) & (depth < far_clip_m * .99) & (depth <= max_depth_m)
    return np.where(valid, depth, 0).astype(np.float32)
