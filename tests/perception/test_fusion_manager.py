"""DetectionFusionManager cross-robot fusion (DET-STRETCH-02 SC#2).

Tests validate class-gated nearest-neighbor clustering across robots,
highest-confidence representative selection, and fused_track_id monotonicity.
"""
from __future__ import annotations

import numpy as np
import pytest

from src.perception.fusion import DetectionFusionManager
from src.perception.types import Detections3D, OrientedBox3D


def _make_obb(
    center: tuple[float, float, float],
    class_name: str = "chair",
    class_id: int = 0,
    score: float = 0.9,
    track_id: int | None = None,
) -> OrientedBox3D:
    """Helper: build an OrientedBox3D at given world-frame center."""
    return OrientedBox3D(
        center=np.array(center, dtype=np.float64),
        half_extents=np.array([0.3, 0.4, 0.5], dtype=np.float64),
        quaternion=np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float64),
        class_id=class_id,
        class_name=class_name,
        score=score,
        track_id=track_id,
    )


def _make_detections3d(boxes: list[OrientedBox3D]) -> Detections3D:
    """Helper: wrap OrientedBox3D list into a Detections3D."""
    return Detections3D(
        items=boxes,
        lifter_ms=1.0,
        detector_ms=2.0,
        n_raw=len(boxes),
        n_final=len(boxes),
        image_hw=(480, 640),
    )


class TestFusionWithinRadius:
    """SC#2: two robots detecting same chair within 0.5m produce single fused entry."""

    def test_two_robots_same_chair_within_radius_fuse(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8), score=0.92, track_id=10),
            ]),
            "robot_1": _make_detections3d([
                _make_obb((1.1, 0.5, 0.8), score=0.85, track_id=20),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 1
        entry = fused[0]
        assert sorted(entry["robot_ids"]) == ["robot_0", "robot_1"]
        assert entry["class_name"] == "chair"

    def test_both_source_track_ids_present(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8), track_id=10),
            ]),
            "robot_1": _make_detections3d([
                _make_obb((1.1, 0.5, 0.8), track_id=20),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 1
        assert sorted(fused[0]["source_track_ids"]) == [10, 20]


class TestFusionBeyondRadius:
    """Detections >0.5m apart remain separate fused entries."""

    def test_two_robots_different_locations_no_fuse(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8)),
            ]),
            "robot_1": _make_detections3d([
                _make_obb((5.0, 0.5, 0.8)),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 2


class TestClassGate:
    """Chair and table at same location are NOT fused (class gate)."""

    def test_class_gate_prevents_cross_class_fusion(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((0.0, 0.0, 0.0), class_name="chair", class_id=0),
            ]),
            "robot_1": _make_detections3d([
                _make_obb((0.0, 0.0, 0.0), class_name="table", class_id=1),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 2
        class_names = sorted(e["class_name"] for e in fused)
        assert class_names == ["chair", "table"]


class TestHighestConfidenceRepresentative:
    """Fused entry picks highest-confidence detection as representative OBB."""

    def test_highest_confidence_is_representative(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8), score=0.92, track_id=10),
            ]),
            "robot_1": _make_detections3d([
                _make_obb((1.1, 0.5, 0.8), score=0.85, track_id=20),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 1
        assert fused[0]["score"] == pytest.approx(0.92)


class TestSingleRobotPassthrough:
    """With one robot, all detections pass through as single-source fused entries."""

    def test_single_robot_passthrough(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8), class_name="chair"),
                _make_obb((3.0, 0.5, 0.8), class_name="table"),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert len(fused) == 2
        for entry in fused:
            assert entry["robot_ids"] == ["robot_0"]


class TestEmptyInput:
    """Empty per_robot_detections -> empty fused list."""

    def test_empty_per_robot_detections(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        fused = fm.fuse({}, sim_time=1.0)
        assert fused == []

    def test_none_detections_ignored(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        fused = fm.fuse({"robot_0": None}, sim_time=1.0)  # type: ignore[dict-item]
        assert fused == []


class TestFusedTrackIdMonotonic:
    """fused_track_id is monotonically increasing across calls."""

    def test_monotonic_ids_across_calls(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8)),
            ]),
        }
        fused1 = fm.fuse(per_robot, sim_time=1.0)
        fused2 = fm.fuse(per_robot, sim_time=2.0)
        assert fused2[0]["fused_track_id"] > fused1[0]["fused_track_id"]

    def test_ids_start_from_zero(self) -> None:
        fm = DetectionFusionManager(cluster_radius=0.5)
        per_robot = {
            "robot_0": _make_detections3d([
                _make_obb((1.0, 0.5, 0.8)),
            ]),
        }
        fused = fm.fuse(per_robot, sim_time=1.0)
        assert fused[0]["fused_track_id"] == 0
