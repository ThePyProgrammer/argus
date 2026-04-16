"""ByteTrack pipeline hot-apply integration (DET-STRETCH-01 + Phase 8 Pitfall 8).

Verifies that pipeline_routes.py correctly detects tracker changes and calls
pool.swap_tracker() on the hot-apply path (tracker_name/tracker_params are
no longer in the structural_unchanged check).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.web.pipeline_routes import router as pipeline_router, _digest_topology
from src.coordination.merge_registry import MergeRegistry
from src.coordination.pipeline_builder import PipelineConfig
from src.slam.registry import SLAMRegistry


@pytest.fixture(autouse=True)
def _populate_registries():
    """Register minimal SLAM + merger + perception entries."""
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    MergeRegistry.register(
        "icp_union", "ICP Union",
        "src.coordination.merge_strategies.icp_union.ICPUnionStrategy",
    )
    import sys
    for _prefix in ("src.perception.backends", "src.perception.lifters", "src.tracking.trackers"):
        for _key in list(sys.modules):
            if _key == _prefix or _key.startswith(_prefix + "."):
                del sys.modules[_key]
    import src.perception.backends  # noqa: F401
    import src.perception.lifters   # noqa: F401
    import src.tracking.trackers    # noqa: F401
    yield
    SLAMRegistry._clear()
    MergeRegistry._clear()


def _baseline_graph() -> dict:
    return {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "slam_1", "type": "slam_icp", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}, "position": {"x": 0, "y": 0}},
            {"id": "detector_1", "type": "detector_yolov11", "params": {}, "position": {"x": 0, "y": 0}},
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


@pytest.fixture
def app_with_pool() -> tuple[FastAPI, MagicMock]:
    app = FastAPI()
    app.include_router(pipeline_router)
    pool = MagicMock()
    app.state.detector_pool = pool
    app.state.command_callback = MagicMock()
    app.state.pending_pipeline_config = None
    app.state.last_applied_pipeline_config = None
    app.state.last_applied_topology_digest = None
    app.state.active_detector_backend = "yolov11"
    app.state.active_lifter = "point_cluster"
    app.state.pending_detector_params = {}
    app.state.pending_lifter_params = {}
    return app, pool


def test_tracker_change_triggers_hot_apply_swap_tracker(app_with_pool) -> None:
    """Changing only the tracker node triggers swap_tracker on the hot-apply path."""
    app, pool = app_with_pool
    baseline = _baseline_graph()
    app.state.last_applied_pipeline_config = PipelineConfig(
        detector_name="yolov11",
        lifter_name="point_cluster",
        tracker_name="none",
    )
    app.state.last_applied_topology_digest = _digest_topology(
        baseline["nodes"], baseline["edges"]
    )

    # Change ONLY the tracker node: tracker_none -> tracker_bytetrack.
    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "tracker_1":
            n["type"] = "tracker_bytetrack"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "hot-applied"
    assert "tracker_name" in body["changed"]
    assert body["active_tracker"] == "bytetrack"
    pool.swap_tracker.assert_called_once_with("bytetrack", {})
    # Detector and lifter unchanged — swap_backend/swap_lifter must NOT be called.
    assert pool.swap_backend.call_count == 0
    assert pool.swap_lifter.call_count == 0
    # Restart callback must NOT be called (hot-apply path).
    assert app.state.command_callback.call_count == 0
    # last_applied_pipeline_config updated immediately.
    assert app.state.last_applied_pipeline_config.tracker_name == "bytetrack"


def test_tracker_swap_failure_returns_400(app_with_pool) -> None:
    """swap_tracker failure returns HTTP 400 without triggering restart."""
    app, pool = app_with_pool
    baseline = _baseline_graph()
    app.state.last_applied_pipeline_config = PipelineConfig(
        detector_name="yolov11",
        lifter_name="point_cluster",
        tracker_name="none",
    )
    app.state.last_applied_topology_digest = _digest_topology(
        baseline["nodes"], baseline["edges"]
    )
    pool.swap_tracker.side_effect = ValueError("simulated tracker swap failure")

    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "tracker_1":
            n["type"] = "tracker_bytetrack"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 400
    assert "swap_tracker failed" in res.json()["detail"]
    assert app.state.command_callback.call_count == 0
