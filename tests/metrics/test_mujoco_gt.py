"""Unit tests for `src.metrics.mujoco_gt.MuJoCoGTExtractor` (DET-METRICS-02).

Exercises:
- mj_name2id chair body resolution
- geom_xpos world-frame extraction (Research F1 correction)
- fail-fast on missing body (raises ValueError)
- center_error math + 1.0m correct-instance gate (CONTEXT D-09)
- per_class_recall denominator (len(mapping[class_name]))

Fixture: tests/perception/fixtures/scene_rotated_chair.xml — chair body
at pos="0 0 0.45"; first geom of chair (chair_seat) has geom_xpos ~= (0, 0, 0.45)
post mj_forward.
"""
from __future__ import annotations

from pathlib import Path

import mujoco
import numpy as np
import pytest
import yaml

from src.metrics.mujoco_gt import MuJoCoGTExtractor

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "perception" / "fixtures"
FIXTURE_XML = _FIXTURE_DIR / "scene_rotated_chair.xml"
FIXTURE_MAPPING = _FIXTURE_DIR / "scene_rotated_chair_gt.yaml"


@pytest.fixture
def mj_pair():
    """Load fixture and run mj_forward so geom_xpos is populated (Research A2)."""
    model = mujoco.MjModel.from_xml_path(str(FIXTURE_XML))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    return model, data


@pytest.fixture
def extractor(mj_pair):
    model, data = mj_pair
    return MuJoCoGTExtractor(FIXTURE_MAPPING, model, data)


def test_resolves_chair_body(mj_pair, extractor):
    """mj_name2id finds the chair body; `all_classes` lists "chair"."""
    model, _ = mj_pair
    bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "chair")
    assert bid >= 0, "fixture chair body must resolve via mj_name2id"
    assert extractor.all_classes() == ["chair"]
    # gt_positions must return exactly one position for chair
    positions = extractor.gt_positions("chair")
    assert len(positions) == 1
    assert positions[0].shape == (3,)


def test_geom_xpos_world_coords(extractor):
    """Research F1: extractor uses geom_xpos, returning z ~= 0.45 (fixture pos).

    Loose tolerance — first geom (chair_seat) is at local `(0,0,0)` so its
    world xpos equals the body's pos=(0,0,0.45). 0.1m tolerance accommodates
    any future geom reordering.
    """
    positions = extractor.gt_positions("chair")
    z = float(positions[0][2])
    assert abs(z - 0.45) < 0.1, f"expected z~=0.45 (body pos), got {z}"


def test_missing_body_raises(mj_pair, tmp_path):
    """Fail-fast at construction when mapping references an unknown body."""
    model, data = mj_pair
    bad_yaml = tmp_path / "bad_mapping.yaml"
    bad_yaml.write_text("chair:\n  - nonexistent_body_xyz\n")
    with pytest.raises(ValueError, match="nonexistent_body_xyz"):
        MuJoCoGTExtractor(bad_yaml, model, data)


def test_center_error_known_offset(extractor):
    """match_detection returns distance ~= 0.1 inside the 1.0m gate; (None, None) outside."""
    # Chair is at ~(0, 0, 0.45). Detection 0.1m away on +x must match.
    gid, dist = extractor.match_detection("chair", np.array([0.1, 0.0, 0.45]))
    assert gid is not None
    assert dist is not None
    assert abs(dist - 0.1) < 1e-6, f"expected distance ~=0.1, got {dist}"

    # Detection 5m+ away must fall outside the 1.0m gate -> (None, None).
    gid_miss, dist_miss = extractor.match_detection(
        "chair", np.array([5.0, 5.0, 5.0])
    )
    assert gid_miss is None
    assert dist_miss is None


def test_per_class_recall_denominator(extractor):
    """expected_count returns len(mapping[class_name]); unknown class -> 0 (no ZeroDivisionError upstream)."""
    assert extractor.expected_count("chair") == 1
    assert extractor.expected_count("nonexistent_class") == 0
    # gt_positions for unknown class must be an empty list (not None, not KeyError)
    assert extractor.gt_positions("nonexistent_class") == []
    # match_detection for unknown class must return (None, None), not raise.
    gid, dist = extractor.match_detection(
        "nonexistent_class", np.array([0.0, 0.0, 0.0])
    )
    assert gid is None and dist is None
