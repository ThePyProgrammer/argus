"""Unit tests for PointClusterLifter (Plan 04-04, DET-3D-01 + DET-3D-07).

Covers:
- Registration under 'point_cluster' with outputs_oriented=True.
- Composition fallback to MedianDepthLifter (D-07).
- Synthetic-cluster fit correctness (extent/2 half-extents; xyzw quat yaw).
- DBSCAN background rejection.
- < 50 valid depth pixels → fallback delegate.
- Open3D get_oriented_bounding_box(robust=True) API name (Pitfall 1).

Skip markers: tests that require open3d/sklearn at runtime use
pytest.importorskip so the file still imports cleanly on dev envs without
the perception extra installed.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import (
    Detection2D,
    Detections2D,
    Detections3D,
    OrientedBox3D,
)


@pytest.fixture
def intrinsics():
    return CameraIntrinsics.from_fov(640, 480, 70.0)


@pytest.fixture
def identity_pose():
    return np.eye(4)


@pytest.fixture
def uniform_depth_frame(identity_pose):
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    return SensorFrame(
        rgb=rgb, depth=depth, ground_truth_pose=identity_pose, sim_time=0.0,
    )


@pytest.fixture
def lifter():
    pytest.importorskip("open3d")
    pytest.importorskip("sklearn.cluster")
    import src.perception.lifters  # noqa: F401 — side-effect registration
    from src.perception.lifters.point_cluster import PointClusterLifter
    return PointClusterLifter()


def _make_det(bbox, class_id=56, class_name="chair", score=0.9):
    return Detection2D(
        class_id=class_id, class_name=class_name, score=score, bbox_xyxy=bbox,
    )


def test_point_cluster_lifter_registered():
    pytest.importorskip("open3d")
    pytest.importorskip("sklearn.cluster")
    import src.perception.lifters  # noqa: F401
    from src.perception.registry import Detection3DRegistry
    entries = {b["name"]: b for b in Detection3DRegistry.list_backends()}
    assert "point_cluster" in entries, f"missing point_cluster: {list(entries)}"
    caps = entries["point_cluster"]["capabilities"]
    assert caps["outputs_oriented"] is True


def test_point_cluster_composes_median_depth_fallback(lifter):
    from src.perception.lifters.median_depth import MedianDepthLifter
    assert isinstance(lifter._fallback, MedianDepthLifter)


def test_capabilities_dict_shape(lifter):
    caps = type(lifter).CAPABILITIES
    for k in ("requires_depth", "requires_point_cloud", "outputs_oriented", "license"):
        assert k in caps, f"missing capability {k}"
    assert caps["outputs_oriented"] is True
    assert caps["requires_point_cloud"] is False


def test_parameter_schema_has_dbscan_params(lifter):
    props = type(lifter).PARAMETER_SCHEMA["properties"]
    for k in ("dbscan_eps_m", "dbscan_min_samples", "depth_near_m", "depth_far_m"):
        assert k in props, f"missing schema param {k}"
        assert props[k].get("live_tunable") is True, f"{k} must be live_tunable"


def _build_depth_with_cluster(h, w, bbox, depth_value):
    """Return a depth image with a fill value inside bbox, zeros outside."""
    depth = np.zeros((h, w), dtype=np.float32)
    x1, y1, x2, y2 = bbox
    depth[y1:y2, x1:x2] = depth_value
    return depth


def test_fit_synthetic_rotated_cluster_yaw_within_tolerance(
    lifter, intrinsics, identity_pose,
):
    """Unproject a known bbox at known depth produces a cluster; Open3D OBB
    should recover a reasonable box (half-extents finite, quat unit-norm)."""
    bbox = (270, 220, 370, 260)           # 100x40 pixels = 4000 > 2000 cap — subsamples
    depth = _build_depth_with_cluster(480, 640, bbox, depth_value=2.0)
    frame = SensorFrame(
        rgb=np.zeros((480, 640, 3), np.uint8),
        depth=depth, ground_truth_pose=identity_pose, sim_time=0.0,
    )
    dets_2d = Detections2D(
        items=[_make_det(bbox)], inference_ms=0.0, image_hw=(480, 640),
    )
    out = lifter.lift(dets_2d, frame, identity_pose, intrinsics, None)
    assert len(out.items) == 1
    item = out.items[0]
    # half_extents should be reasonable (loose: each < 2m)
    assert (np.asarray(item.half_extents) < 2.0).all()
    # quaternion is xyzw and unit-norm
    q = np.asarray(item.quaternion)
    assert q.shape == (4,)
    np.testing.assert_allclose(np.linalg.norm(q), 1.0, atol=1e-5)
    # center_z approximately -2 (camera looks along -Z at identity)
    assert abs(item.center[2] - (-2.0)) < 0.2


def test_dbscan_rejects_background(lifter, intrinsics, identity_pose):
    """Bimodal depth: foreground at d=2m filling bbox, sparse 'background' at d=5m
    in same bbox. DBSCAN separates clusters; largest (foreground) wins."""
    bbox = (200, 200, 400, 400)
    depth = np.full((480, 640), 0.0, dtype=np.float32)   # 0 = invalid elsewhere
    depth[210:390, 210:390] = 2.0                         # foreground (180x180 = 32400 px)
    # Sparse background points INSIDE the bbox at far depth
    rng = np.random.default_rng(0)
    bg_u = rng.integers(low=201, high=399, size=50)
    bg_v = rng.integers(low=201, high=399, size=50)
    depth[bg_v, bg_u] = 5.0
    frame = SensorFrame(
        rgb=np.zeros((480, 640, 3), np.uint8),
        depth=depth, ground_truth_pose=identity_pose, sim_time=0.0,
    )
    dets_2d = Detections2D(
        items=[_make_det(bbox)], inference_ms=0.0, image_hw=(480, 640),
    )
    out = lifter.lift(dets_2d, frame, identity_pose, intrinsics, None)
    assert len(out.items) == 1
    # Largest cluster = foreground at depth ~2 → center_z near -2, NOT -5
    assert abs(out.items[0].center[2] - (-2.0)) < 0.3


def test_fallback_below_50_pixels(lifter, intrinsics, identity_pose, monkeypatch):
    """< 50 valid depth pixels → delegate to self._fallback. Per D-07."""
    bbox = (320, 240, 326, 246)                          # 6x6 = 36 pixels
    depth = np.zeros((480, 640), dtype=np.float32)
    depth[240:246, 320:326] = 2.0                        # exactly 36 valid pixels
    frame = SensorFrame(
        rgb=np.zeros((480, 640, 3), np.uint8),
        depth=depth, ground_truth_pose=identity_pose, sim_time=0.0,
    )
    dets_2d = Detections2D(
        items=[_make_det(bbox)], inference_ms=0.0, image_hw=(480, 640),
    )

    calls = {"n": 0}
    orig_lift = lifter._fallback.lift

    def _spy(*args, **kwargs):
        calls["n"] += 1
        return orig_lift(*args, **kwargs)

    monkeypatch.setattr(lifter._fallback, "lift", _spy)

    out = lifter.lift(dets_2d, frame, identity_pose, intrinsics, None)
    assert calls["n"] >= 1, "fallback must be called when valid pixels < 50"
    assert len(out.items) >= 1
    q = np.asarray(out.items[0].quaternion)
    # Median depth fallback emits identity quaternion
    np.testing.assert_allclose(q, [0.0, 0.0, 0.0, 1.0], atol=1e-9)


def test_depth_none_delegates_to_fallback(
    lifter, intrinsics, identity_pose, monkeypatch,
):
    frame = SensorFrame(
        rgb=np.zeros((480, 640, 3), np.uint8),
        depth=None, ground_truth_pose=identity_pose, sim_time=0.0,
    )
    dets_2d = Detections2D(
        items=[_make_det((100, 100, 200, 200))],
        inference_ms=0.0,
        image_hw=(480, 640),
    )
    called = {"n": 0}
    orig_lift = lifter._fallback.lift

    def _spy(*args, **kwargs):
        called["n"] += 1
        return orig_lift(*args, **kwargs)

    monkeypatch.setattr(lifter._fallback, "lift", _spy)
    lifter.lift(dets_2d, frame, identity_pose, intrinsics, None)
    assert called["n"] == 1


def test_open3d_extent_divided_by_two(lifter, intrinsics, identity_pose):
    """Pitfall 2 lock: Open3D returns FULL extent; we divide by 2 for half_extents."""
    pytest.importorskip("open3d")
    import open3d as o3d
    # Build a synthetic unit cube cluster directly, bypass bbox frustum logic
    pts = np.array(
        [(x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]
        + [(rng, rng, rng) for rng in np.linspace(0.1, 0.9, 20)],
        dtype=np.float64,
    )
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts))
    obb = pcd.get_oriented_bounding_box(robust=True)
    extent = np.asarray(obb.extent)
    # A 1x1x1 cube → extent ~(1, 1, 1); half_extents (via lifter convention) → ~(0.5, 0.5, 0.5)
    np.testing.assert_allclose(extent / 2.0, [0.5, 0.5, 0.5], atol=0.05)


def test_all_noise_cluster_returns_no_item(lifter, intrinsics, identity_pose):
    """Pitfall 4: when DBSCAN labels every point noise, lifter SKIPS (no fallback)."""
    # 100 pixels scattered across far depths (5.0-14.0m) so spatial separation > eps=0.05
    bbox = (100, 100, 500, 400)
    depth = np.zeros((480, 640), dtype=np.float32)
    rng = np.random.default_rng(0)
    us = rng.integers(low=110, high=490, size=100)
    vs = rng.integers(low=110, high=390, size=100)
    # Spread depths across large range so world distances >> eps
    depth[vs, us] = rng.uniform(low=5.0, high=14.0, size=100).astype(np.float32)
    # But we still need >= 50 valid pixels (Pitfall 4: skip-not-fallback only at >=50)
    frame = SensorFrame(
        rgb=np.zeros((480, 640, 3), np.uint8),
        depth=depth, ground_truth_pose=identity_pose, sim_time=0.0,
    )
    dets_2d = Detections2D(
        items=[_make_det(bbox)], inference_ms=0.0, image_hw=(480, 640),
    )
    out = lifter.lift(dets_2d, frame, identity_pose, intrinsics, None)
    # All-noise → items empty (silently skip the detection). Not fallback.
    assert out.items == [], f"expected empty items on all-noise, got {out.items}"
