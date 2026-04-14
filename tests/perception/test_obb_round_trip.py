"""1000-randomized-OBB wire round-trip + edge case + envelope tests (Plan 02-01).

Locks the canonical OBB wire format per 02-CONTEXT.md D-06..D-14 and DET-3D-04.

Test matrix:
    test_round_trip_1000_boxes           -- 1000 seeded random OBBs (scipy Rotation.random,
                                            Haar-uniform), 50% with negated quaternions
                                            to exercise D-06 auto-flip, 50% with track_id,
                                            every-3rd with bbox_xyxy; round-trips to ±1e-6.
    test_wire_shape_matches_d09          -- emitted keys match D-09 field set; qw>=0;
                                            all numerics plain Python float/int (D-08).
    test_from_wire_rejects_negative_qw   -- ValueError with "qw" in message.
    test_from_wire_rejects_missing_keys  -- each of the 6 required keys missing triggers
                                            ValueError that names the key.
    test_edge_cases_identity_and_180_yaw -- identity (qw=1) and 180 deg yaw (qw=0 boundary)
                                            both survive round-trip.
    test_track_id_omitted_when_none      -- wire dict lacks "track_id" key when obb.track_id
                                            is None (D-07); present and integer-typed when set.
    test_bbox_xyxy_optional_field        -- wire key absent when None; present and int-tuple
                                            when set (tuple of 4 ints).
    test_detections3d_envelope_round_trip -- Detections3D.to_wire produces {items, capture_pose
                                            (flat 16-float row-major), capture_timestamp,
                                            image_hw, metrics}; row-major matches
                                            np.ndarray.reshape(-1).tolist().

Determinism: SEED = 42 pins the numpy default_rng + scipy Rotation.random stream. Re-runs
produce bit-exact inputs on the same platform; round-trip tolerance is TOL = 1e-6.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("scipy")  # scipy is in base deps per RESEARCH Standard Stack; guard for resilience.
from scipy.spatial.transform import Rotation  # noqa: E402 -- after importorskip guard

from src.perception.types import Detections3D, OrientedBox3D  # noqa: E402

SEED = 42
TOL = 1e-6


def _quaternion_equivalent(q_a, q_b, tol: float = TOL) -> bool:
    """Two unit quaternions represent the same rotation iff q_a ~ +/- q_b (D-06 auto-flip)."""
    a = np.asarray(q_a, dtype=np.float64)
    b = np.asarray(q_b, dtype=np.float64)
    return min(np.linalg.norm(a - b), np.linalg.norm(a + b)) < tol


def _generate_random_obbs(n: int = 1000, seed: int = SEED) -> list[OrientedBox3D]:
    """Generate n deterministically-random OBBs exercising the full wire matrix.

    - centers uniform in [-10, 10]^3
    - half_extents log-uniform in [0.05, 2.0]^3
    - quaternions via Rotation.random (Haar-uniform unit quats); 50% negated to hit qw<0
    - class_ids uniform in [56, 76) (COCO indoor classes: 56=chair..75=vase)
    - track_id on even indices (int), None on odd indices -- exercises D-07 omission
    - bbox_xyxy on every 3rd index (int tuple in [0, 640) x [0, 480)), None otherwise
    """
    rng = np.random.default_rng(seed)
    centers = rng.uniform(-10.0, 10.0, size=(n, 3))
    half_extents = np.exp(rng.uniform(np.log(0.05), np.log(2.0), size=(n, 3)))
    rots = Rotation.random(num=n, rng=rng).as_quat()  # xyzw; unit quats
    # Negate half of them (P ~ 0.5) to exercise D-06 qw<0 auto-flip path.
    negate_mask = rng.random(n) < 0.5
    rots[negate_mask] *= -1.0
    class_ids = rng.integers(56, 76, size=n)
    scores = rng.uniform(0.5, 1.0, size=n)

    boxes: list[OrientedBox3D] = []
    for i in range(n):
        track_id = int(i) if i % 2 == 0 else None
        bbox_xyxy: tuple[int, int, int, int] | None
        if i % 3 == 0:
            # Deterministic bbox from rng (not random -- we want reproducibility alongside the geometry).
            x1 = int(rng.integers(0, 600))
            y1 = int(rng.integers(0, 440))
            x2 = int(x1 + rng.integers(1, 40))
            y2 = int(y1 + rng.integers(1, 40))
            bbox_xyxy = (x1, y1, x2, y2)
        else:
            bbox_xyxy = None
        boxes.append(
            OrientedBox3D(
                center=centers[i],
                half_extents=half_extents[i],
                quaternion=rots[i],
                class_id=int(class_ids[i]),
                class_name=f"class_{int(class_ids[i])}",
                score=float(scores[i]),
                track_id=track_id,
                bbox_xyxy=bbox_xyxy,
            )
        )
    return boxes


def test_round_trip_1000_boxes() -> None:
    """DET-3D-04: 1000 randomized OBBs survive to_wire -> from_wire within ±1e-6."""
    boxes = _generate_random_obbs(n=1000)
    for i, obb in enumerate(boxes):
        wire = obb.to_wire()
        # D-06: qw must be >= 0 on the wire
        assert wire["quaternion"][3] >= 0.0, (
            f"box {i}: qw={wire['quaternion'][3]} < 0 after to_wire() (D-06 auto-flip failed)"
        )
        # D-07: track_id key omission
        if obb.track_id is None:
            assert "track_id" not in wire, f"box {i}: track_id present for None input (D-07)"
        else:
            assert wire["track_id"] == obb.track_id, f"box {i}: track_id not round-tripped"
        # bbox_xyxy omission / presence
        if obb.bbox_xyxy is None:
            assert "bbox_xyxy" not in wire, f"box {i}: bbox_xyxy present for None input"
        else:
            assert list(wire["bbox_xyxy"]) == list(obb.bbox_xyxy)
        # D-08: every numeric is a plain Python float / int (no numpy scalars leak)
        assert all(type(c) is float for c in wire["center"]), f"box {i}: non-float in center"
        assert all(type(h) is float for h in wire["half_extents"]), f"box {i}: non-float in half_extents"
        assert all(type(q) is float for q in wire["quaternion"]), f"box {i}: non-float in quaternion"
        assert type(wire["class_id"]) is int
        assert type(wire["score"]) is float

        round_tripped = OrientedBox3D.from_wire(wire)
        np.testing.assert_allclose(round_tripped.center, obb.center, atol=TOL)
        np.testing.assert_allclose(round_tripped.half_extents, obb.half_extents, atol=TOL)
        assert _quaternion_equivalent(round_tripped.quaternion, obb.quaternion, tol=TOL), (
            f"box {i}: quaternion mismatch input={obb.quaternion} output={round_tripped.quaternion}"
        )
        assert round_tripped.class_id == obb.class_id
        assert round_tripped.class_name == obb.class_name
        assert abs(round_tripped.score - obb.score) < TOL
        assert round_tripped.track_id == obb.track_id
        assert round_tripped.bbox_xyxy == obb.bbox_xyxy


def test_wire_shape_matches_d09() -> None:
    """D-09: to_wire emits exactly the locked key set; optional keys only when populated."""
    # Minimal OBB (no track_id, no bbox_xyxy) -> 6 required keys only.
    obb_min = OrientedBox3D(
        center=np.array([1.0, 2.0, 3.0]),
        half_extents=np.array([0.5, 0.5, 0.5]),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56,
        class_name="chair",
        score=0.9,
    )
    wire_min = obb_min.to_wire()
    assert set(wire_min.keys()) == {
        "center", "half_extents", "quaternion", "class_id", "class_name", "score",
    }
    # Key-order follows D-09 (dict preserves insertion order in 3.7+).
    assert list(wire_min.keys()) == [
        "center", "half_extents", "quaternion", "class_id", "class_name", "score",
    ]
    assert wire_min["quaternion"][3] >= 0.0  # D-06 invariant

    # Fully populated OBB (with optional fields) -> 8 keys.
    obb_full = OrientedBox3D(
        center=np.zeros(3),
        half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56,
        class_name="chair",
        score=0.9,
        track_id=7,
        bbox_xyxy=(10, 20, 100, 200),
    )
    wire_full = obb_full.to_wire()
    assert set(wire_full.keys()) == {
        "center", "half_extents", "quaternion", "class_id", "class_name", "score",
        "track_id", "bbox_xyxy",
    }


def test_from_wire_rejects_negative_qw() -> None:
    """D-06 wire invariant: qw<0 is a protocol violation; from_wire refuses."""
    bad = {
        "center": [0.0, 0.0, 0.0],
        "half_extents": [1.0, 1.0, 1.0],
        "quaternion": [0.0, 0.0, 0.0, -1.0],  # qw < 0
        "class_id": 0,
        "class_name": "x",
        "score": 0.9,
    }
    with pytest.raises(ValueError, match="qw"):
        OrientedBox3D.from_wire(bad)


def test_from_wire_rejects_missing_required_keys() -> None:
    """Each of the 6 required keys, if missing, triggers a ValueError naming that key."""
    base = {
        "center": [0.0, 0.0, 0.0],
        "half_extents": [1.0, 1.0, 1.0],
        "quaternion": [0.0, 0.0, 0.0, 1.0],
        "class_id": 0,
        "class_name": "x",
        "score": 0.9,
    }
    required = ("center", "half_extents", "quaternion", "class_id", "class_name", "score")
    for key in required:
        bad = {k: v for k, v in base.items() if k != key}
        with pytest.raises(ValueError, match=key):
            OrientedBox3D.from_wire(bad)


def test_edge_cases_identity_and_180_yaw() -> None:
    """Identity rotation and 180 deg yaw (qw=0 boundary) both survive round-trip."""
    # Identity rotation (qw=1)
    obb = OrientedBox3D(
        center=np.zeros(3),
        half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56,
        class_name="chair",
        score=0.9,
    )
    rt = OrientedBox3D.from_wire(obb.to_wire())
    np.testing.assert_allclose(rt.quaternion, [0.0, 0.0, 0.0, 1.0], atol=TOL)

    # 180 deg yaw: xyzw = [0, 0, 1, 0] -- qw=0 on the hemisphere boundary (>=0 passes)
    q_180 = np.array([0.0, 0.0, 1.0, 0.0])
    obb2 = OrientedBox3D(
        center=np.zeros(3),
        half_extents=np.ones(3),
        quaternion=q_180,
        class_id=0,
        class_name="p",
        score=0.5,
    )
    wire2 = obb2.to_wire()
    assert wire2["quaternion"][3] >= 0.0  # boundary: qw=0 is acceptable
    rt2 = OrientedBox3D.from_wire(wire2)
    assert _quaternion_equivalent(rt2.quaternion, q_180)


def test_track_id_omitted_when_none() -> None:
    """D-07: key ABSENT (not null, not -1) when obb.track_id is None; present & int-typed when set."""
    obb_none = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56, class_name="chair", score=0.9, track_id=None,
    )
    wire_none = obb_none.to_wire()
    assert "track_id" not in wire_none

    obb_set = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56, class_name="chair", score=0.9, track_id=42,
    )
    wire_set = obb_set.to_wire()
    assert wire_set["track_id"] == 42
    assert type(wire_set["track_id"]) is int


def test_bbox_xyxy_optional_field() -> None:
    """bbox_xyxy wire key absent when None; present & int-tuple when set."""
    obb_none = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56, class_name="chair", score=0.9,
    )
    wire_none = obb_none.to_wire()
    assert "bbox_xyxy" not in wire_none

    obb_set = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56, class_name="chair", score=0.9,
        bbox_xyxy=(10, 20, 100, 200),
    )
    wire_set = obb_set.to_wire()
    assert "bbox_xyxy" in wire_set
    assert wire_set["bbox_xyxy"] == [10, 20, 100, 200]
    assert all(type(v) is int for v in wire_set["bbox_xyxy"])

    # from_wire should rehydrate to a tuple of ints
    rt = OrientedBox3D.from_wire(wire_set)
    assert rt.bbox_xyxy == (10, 20, 100, 200)
    assert isinstance(rt.bbox_xyxy, tuple)
    assert all(type(v) is int for v in rt.bbox_xyxy)


def test_detections3d_envelope_round_trip() -> None:
    """D-11, D-14: Detections3D.to_wire emits envelope shape with flat row-major 16-float pose."""
    pose = np.array(
        [
            [1.0, 0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0, 2.0],
            [0.0, 0.0, 1.0, 3.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    obb = OrientedBox3D(
        center=np.array([0.5, 0.5, 0.5]),
        half_extents=np.array([0.25, 0.25, 0.25]),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=56,
        class_name="chair",
        score=0.9,
        bbox_xyxy=(10, 20, 100, 200),
    )
    d3 = Detections3D(
        items=[obb],
        lifter_ms=2.5,
        detector_ms=12.3,
        n_raw=2,
        n_final=1,
        image_hw=(480, 640),
        capture_pose=pose,
        capture_timestamp=1234.5,
    )
    wire = d3.to_wire()

    # Envelope shape (D-14): items + capture_pose (flat-16) + capture_timestamp + image_hw + metrics
    assert set(wire.keys()) == {"items", "capture_pose", "capture_timestamp", "image_hw", "metrics"}

    # capture_pose flat-16 row-major
    assert isinstance(wire["capture_pose"], list)
    assert len(wire["capture_pose"]) == 16
    assert all(type(v) is float for v in wire["capture_pose"])
    # Row-major expectation: first row = [1.0, 0.0, 0.0, 1.0]; reshape back must match pose.
    expected_flat = pose.reshape(-1).tolist()
    assert wire["capture_pose"] == expected_flat
    assert wire["capture_pose"][:4] == [1.0, 0.0, 0.0, 1.0]
    assert wire["capture_pose"][4:8] == [0.0, 1.0, 0.0, 2.0]

    # capture_timestamp is a plain float
    assert type(wire["capture_timestamp"]) is float
    assert wire["capture_timestamp"] == 1234.5

    # image_hw is a list of ints [H, W]
    assert wire["image_hw"] == [480, 640]
    assert all(type(v) is int for v in wire["image_hw"])

    # metrics sub-dict with plain python scalars
    assert wire["metrics"] == {
        "detector_ms": 12.3,
        "lifter_ms": 2.5,
        "n_raw": 2,
        "n_final": 1,
    }
    assert type(wire["metrics"]["n_raw"]) is int
    assert type(wire["metrics"]["detector_ms"]) is float

    # items is a list of OrientedBox3D.to_wire dicts
    assert len(wire["items"]) == 1
    assert wire["items"][0]["class_name"] == "chair"
    assert wire["items"][0]["bbox_xyxy"] == [10, 20, 100, 200]


def test_detections3d_envelope_rejects_non_4x4_pose() -> None:
    """T-02-02 mitigation: malformed capture_pose (not flattening to 16) fails fast."""
    obb = OrientedBox3D(
        center=np.zeros(3), half_extents=np.ones(3),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0]),
        class_id=0, class_name="x", score=0.5,
    )
    bad_pose = np.eye(3, dtype=np.float64)  # 3x3 instead of 4x4 -> flattens to 9
    d3 = Detections3D(
        items=[obb], lifter_ms=0.0, detector_ms=0.0,
        n_raw=0, n_final=0, image_hw=(480, 640),
        capture_pose=bad_pose, capture_timestamp=0.0,
    )
    with pytest.raises(ValueError, match="16"):
        d3.to_wire()


def test_generator_is_deterministic_under_seed() -> None:
    """Re-running _generate_random_obbs with the same SEED must produce bit-exact inputs."""
    a = _generate_random_obbs(n=50, seed=SEED)
    b = _generate_random_obbs(n=50, seed=SEED)
    for oa, ob in zip(a, b, strict=True):
        np.testing.assert_array_equal(oa.center, ob.center)
        np.testing.assert_array_equal(oa.half_extents, ob.half_extents)
        np.testing.assert_array_equal(oa.quaternion, ob.quaternion)
        assert oa.class_id == ob.class_id
        assert oa.track_id == ob.track_id
        assert oa.bbox_xyxy == ob.bbox_xyxy
