"""Plan 07-04 — DET-PIPELINE-05 SC#5 PipelineConfig + NodeCatalog lockdown."""
from __future__ import annotations

import pytest

from src.coordination.merge_registry import MergeRegistry
from src.coordination.pipeline_builder import NodeCatalog, PipelineBuilder, PipelineConfig
from src.slam.registry import SLAMRegistry


@pytest.fixture(autouse=True)
def _populate_registries():
    """Ensure all five registries are populated for every test.

    SLAM + merger registries need explicit registration (the existing test
    pattern in test_pipeline_builder.py). Perception + tracking registries
    are populated by side-effect imports of their decorator-registered
    modules.
    """
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    MergeRegistry.register(
        "icp_union",
        "ICP Union",
        "src.coordination.merge_strategies.icp_union.ICPUnionStrategy",
    )
    import src.perception.backends  # noqa: F401
    import src.perception.lifters  # noqa: F401
    import src.tracking.trackers  # noqa: F401
    yield
    SLAMRegistry._clear()
    MergeRegistry._clear()


def _perception_graph() -> dict:
    """Minimal valid graph with all three perception node types."""
    return {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "slam_1", "type": "slam_icp", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "detector_1", "type": "detector_yolov11", "params": {"conf_threshold": 0.3}, "position": {"x": 0, "y": 0}},
            {"id": "detection3d_1", "type": "detection3d_point_cluster", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "tracker_1", "type": "tracker_none", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "viz_1", "type": "viz_output", "params": {}, "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"source": "sensor_1", "sourceHandle": "image_out", "target": "slam_1", "targetHandle": "image_in"},
            {"source": "slam_1", "sourceHandle": "cloud_out", "target": "merger_1", "targetHandle": "cloud_in"},
            {"source": "slam_1", "sourceHandle": "pose_out", "target": "merger_1", "targetHandle": "pose_in"},
            {"source": "merger_1", "sourceHandle": "merged_out", "target": "viz_1", "targetHandle": "cloud_in"},
            {"source": "sensor_1", "sourceHandle": "image_out", "target": "detector_1", "targetHandle": "image_in"},
            {"source": "sensor_1", "sourceHandle": "depth_out", "target": "detection3d_1", "targetHandle": "depth_in"},
            {"source": "detector_1", "sourceHandle": "detections_2d_out", "target": "detection3d_1", "targetHandle": "detections_2d_in"},
            {"source": "detection3d_1", "sourceHandle": "detections_3d_out", "target": "tracker_1", "targetHandle": "detections_3d_in"},
        ],
    }


def test_pipeline_builder_populates_perception_fields() -> None:
    config = PipelineBuilder().build(_perception_graph())
    assert config.detector_name == "yolov11"
    assert config.detector_params == {"conf_threshold": 0.3}
    assert config.lifter_name == "point_cluster"
    assert config.lifter_params == {}
    assert config.tracker_name == "none"
    assert config.tracker_params == {}


def test_missing_perception_nodes_fall_back_to_defaults() -> None:
    # SLAM-only graph (no detector/lifter/tracker nodes present).
    graph = {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "slam_1", "type": "slam_icp", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "viz_1", "type": "viz_output", "params": {}, "position": {"x": 0, "y": 0}},
        ],
        "edges": [
            {"source": "sensor_1", "sourceHandle": "image_out", "target": "slam_1", "targetHandle": "image_in"},
            {"source": "slam_1", "sourceHandle": "cloud_out", "target": "merger_1", "targetHandle": "cloud_in"},
            {"source": "slam_1", "sourceHandle": "pose_out", "target": "merger_1", "targetHandle": "pose_in"},
            {"source": "merger_1", "sourceHandle": "merged_out", "target": "viz_1", "targetHandle": "cloud_in"},
        ],
    }
    config = PipelineBuilder().build(graph)
    assert config.detector_name == "yolov11"
    assert config.lifter_name == "point_cluster"
    assert config.tracker_name == "none"


def test_unknown_detector_raises_value_error() -> None:
    graph = _perception_graph()
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] != "detector_1"]
    graph["nodes"].append(
        {"id": "detector_bad", "type": "detector_bogusname", "params": {}, "position": {"x": 0, "y": 0}}
    )
    # rewire edges that referenced detector_1 so the ValueError comes from the
    # name check, not from the unconnected-required-input guard.
    graph["edges"] = [
        e for e in graph["edges"]
        if e["source"] != "detector_1" and e["target"] != "detector_1"
    ]
    graph["edges"].append(
        {"source": "sensor_1", "sourceHandle": "image_out", "target": "detector_bad", "targetHandle": "image_in"}
    )
    with pytest.raises(ValueError, match="Unknown detector backend: bogusname"):
        PipelineBuilder().build(graph)


def test_unknown_lifter_raises_value_error() -> None:
    graph = _perception_graph()
    for n in graph["nodes"]:
        if n["id"] == "detection3d_1":
            n["type"] = "detection3d_bogusname"
    with pytest.raises(ValueError, match="Unknown 3D lifter: bogusname"):
        PipelineBuilder().build(graph)


def test_unknown_tracker_raises_value_error() -> None:
    graph = _perception_graph()
    for n in graph["nodes"]:
        if n["id"] == "tracker_1":
            n["type"] = "tracker_bogusname"
    with pytest.raises(ValueError, match="Unknown tracker: bogusname"):
        PipelineBuilder().build(graph)


def test_node_catalog_lists_perception_entries() -> None:
    catalog = NodeCatalog.get_catalog()

    # Detector entries present with category=perception.
    detector_entries = [e for e in catalog if e["type"].startswith("detector_")]
    assert len(detector_entries) >= 1
    assert all(e["category"] == "perception" for e in detector_entries)
    assert any(e["type"] == "detector_yolov11" for e in catalog)

    # 3D lifter entries present.
    lifter_entries = [e for e in catalog if e["type"].startswith("detection3d_")]
    assert len(lifter_entries) >= 1
    assert all(e["category"] == "perception" for e in lifter_entries)
    assert any(e["type"] == "detection3d_point_cluster" for e in catalog)

    # Tracker entries present — exactly "none" in Phase 7.
    tracker_entries = [e for e in catalog if e["type"].startswith("tracker_")]
    assert len(tracker_entries) == 1
    assert tracker_entries[0]["type"] == "tracker_none"
    assert tracker_entries[0]["category"] == "perception"

    # Each detector entry exposes capabilities (critical for UI gating via outputs_3d_natively).
    yolov11 = next(e for e in catalog if e["type"] == "detector_yolov11")
    assert "capabilities" in yolov11
    assert "outputs_3d_natively" in yolov11["capabilities"]


def test_detector_and_detection3d_do_not_alias() -> None:
    """Pitfall 1 lockdown: ensure detector_ prefix-check does not swallow detection3d_ nodes."""
    graph = _perception_graph()
    # Keep both detector_yolov11 and detection3d_point_cluster present (already in fixture).
    config = PipelineBuilder().build(graph)
    # detection3d_point_cluster must produce lifter_name="point_cluster", NOT detector_name="3d_point_cluster".
    assert config.lifter_name == "point_cluster"
    assert config.detector_name == "yolov11"
