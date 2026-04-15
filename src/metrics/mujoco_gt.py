"""MuJoCo ground-truth extractor for detection metrics (DET-METRICS-02).

Resolves COCO class names to MuJoCo body positions via a committed YAML
mapping (CONTEXT D-08). Matching policy: nearest-neighbor in world frame,
class-gated (CONTEXT D-09 — 1.0m correct-instance gate, NOT an accuracy gate).

CRITICAL — Research F1:
    Reads `data.geom_xpos[first_geom_of_body]`. The body-origin accessor
    (``data.xpos`` indexed by body id) is NOT used. Bodies in
    scene_office1.xml declare `euler=` only with no `pos=` so the
    body-origin accessor returns (0, 0, 0) for every labeled body. The
    visible world-frame position lives in the geom's `geom_xpos`, populated
    by `mj_forward` / `mj_step`. The unit-test fixture
    scene_rotated_chair.xml has an explicit `pos="0 0 0.45"` on the chair
    body — both paths would work there — but we use `geom_xpos` everywhere
    for consistency with the production scene.

Security (T-6-04):
    Uses `yaml.safe_load`. The non-safe YAML loader would accept
    `!!python/object` tags and allow arbitrary code execution on a
    tampered mapping file; `safe_load` blocks that class of constructors.

Usage (CONTEXT D-08):
    >>> from pathlib import Path
    >>> import mujoco
    >>> model = mujoco.MjModel.from_xml_path('scene_office1.xml')
    >>> data = mujoco.MjData(model)
    >>> mujoco.mj_forward(model, data)
    >>> ext = MuJoCoGTExtractor(Path('scene_office1_gt.yaml'), model, data)
    >>> ext.all_classes()
    ['chair', 'tv', 'laptop']
    >>> ext.gt_positions('chair')  # list[np.ndarray] — world-frame (x,y,z)
"""
from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np
import yaml

# CONTEXT D-09 — 1.0m correct-instance gate (not accuracy gate).
_DEFAULT_GATE_M = 1.0


class MuJoCoGTExtractor:
    """Ground-truth body-position extractor for detection metrics.

    Fails fast at construction on missing body or malformed mapping.
    Callers (Plan 08 WebStreamingViz) wrap construction in try/except so
    coordinator boot does not crash on bad mapping (T-6-07 mitigation).
    """

    def __init__(
        self,
        mapping_yaml_path: Path,
        mj_model,  # mujoco.MjModel
        mj_data,   # mujoco.MjData
    ) -> None:
        self._model = mj_model
        self._data = mj_data

        # T-6-04: safe_load ONLY — the non-safe loader accepts !!python/object tags.
        with open(mapping_yaml_path, "r", encoding="utf-8") as f:
            mapping = yaml.safe_load(f) or {}
        if not isinstance(mapping, dict):
            raise ValueError(
                f"GT mapping file {mapping_yaml_path} must be a YAML mapping at top level; "
                f"got {type(mapping).__name__}"
            )

        self._class_to_geom_ids: dict[str, list[int]] = {}
        for class_name, body_names in mapping.items():
            if not isinstance(body_names, list):
                raise ValueError(
                    f"GT mapping class '{class_name}' must map to a list of body names "
                    f"(CONTEXT D-08); got {type(body_names).__name__}"
                )
            geom_ids: list[int] = []
            for body_name in body_names:
                bid = mujoco.mj_name2id(
                    mj_model, mujoco.mjtObj.mjOBJ_BODY, body_name
                )
                if bid < 0:
                    raise ValueError(
                        f"GT mapping references unknown body '{body_name}' "
                        f"(class={class_name}); run an `mj_id2name` audit on the "
                        f"scene XML to list valid body names"
                    )
                # F1: locate first geom belonging to this body.
                gid = -1
                for g in range(mj_model.ngeom):
                    if int(mj_model.geom_bodyid[g]) == bid:
                        gid = g
                        break
                if gid < 0:
                    raise ValueError(
                        f"Body '{body_name}' has no geom — GT extraction requires "
                        f"geom_xpos (Research F1). Verify scene XML."
                    )
                geom_ids.append(gid)
            self._class_to_geom_ids[class_name] = geom_ids

    def gt_positions(self, class_name: str) -> list[np.ndarray]:
        """Return list of world-frame (x, y, z) for every GT instance of this class.

        Empty list if the class is not in the mapping — callers treat that as
        "no GT present for this class" (per-class recall denominator = 0).

        F1: reads `data.geom_xpos`, NOT `data.xpos`.
        """
        geom_ids = self._class_to_geom_ids.get(class_name, [])
        return [
            np.array(self._data.geom_xpos[gid], dtype=np.float64)
            for gid in geom_ids
        ]

    def expected_count(self, class_name: str) -> int:
        """Per-class recall denominator = len(mapping[class_name]) per CONTEXT D-09.

        Returns 0 for unknown class (upstream must guard against division-by-zero).
        """
        return len(self._class_to_geom_ids.get(class_name, []))

    def all_classes(self) -> list[str]:
        """COCO class names declared in the mapping (preserves insertion order)."""
        return list(self._class_to_geom_ids.keys())

    def match_detection(
        self,
        class_name: str,
        detection_center: np.ndarray,
        gate_m: float = _DEFAULT_GATE_M,
    ) -> tuple[int | None, float | None]:
        """Match a detection center to the nearest GT body of this class.

        Per CONTEXT D-09: the 1.0m default is the *correct-instance* gate —
        used to associate a detection with a GT body before computing
        `center_error_m`, NOT an accuracy threshold that the detector must
        meet. Returns `(geom_id, distance_m)` when inside the gate, else
        `(None, None)`.
        """
        positions = self.gt_positions(class_name)
        if not positions:
            return (None, None)
        det = np.asarray(detection_center, dtype=np.float64).reshape(3)
        dists = [float(np.linalg.norm(det - p)) for p in positions]
        idx = int(np.argmin(dists))
        if dists[idx] <= gate_m:
            return (self._class_to_geom_ids[class_name][idx], dists[idx])
        return (None, None)
