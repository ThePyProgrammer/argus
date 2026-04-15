"""Plan 07-09 — DET-PIPELINE-05 SC#4 hot-apply end-to-end lockdown.

End-to-end: boot a test FastAPI client with a stubbed DetectorWorkerPool,
apply a baseline perception pipeline (yolov11 + point_cluster), then change
ONLY the detector node's backend and apply again. Assert:
  - Response status_code == 200
  - Response body == {"status": "hot-applied", "changed": ["detector_name", ...]}
  - pool.swap_backend was called exactly once
  - app.state.command_callback NOT called (no restart => PID stability)
  - app.state.active_detector_backend updated
  - app.state.last_applied_pipeline_config updated
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.web.pipeline_routes import router as pipeline_router
from src.coordination.merge_registry import MergeRegistry
from src.coordination.pipeline_builder import PipelineConfig
from src.slam.registry import SLAMRegistry


@pytest.fixture(autouse=True)
def _populate_registries():
    """Register minimal SLAM + merger entries (without importing open3d).

    The `test_slam_backend_change_triggers_restart` test swaps slam_icp →
    slam_orbslam3, so we register BOTH backend names here. We do NOT import
    src.slam.backends (transitive open3d dep); class paths are never resolved
    in the apply-path — only registry membership matters for PipelineBuilder.
    """
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    SLAMRegistry.register(
        "orbslam3", "ORB-SLAM3",
        "src.slam.backends.orbslam3_backend.ORBSLAM3Backend",
    )
    MergeRegistry.register(
        "icp_union", "ICP Union",
        "src.coordination.merge_strategies.icp_union.ICPUnionStrategy",
    )
    # Perception registries (no heavy deps at import time).
    # Force re-import of registry-populating packages so @decorators re-run
    # after any prior test's _clear. Python caches modules by default — a
    # second `import` is a no-op, so we drop cached entries first.
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


def test_apply_baseline_sets_last_applied_config(app_with_pool) -> None:
    app, pool = app_with_pool
    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=_baseline_graph())
    assert res.status_code == 200
    assert res.json() == {"status": "restarting"}
    assert app.state.last_applied_topology_digest is not None
    assert app.state.command_callback.call_count == 1
    # Pool swap must NOT have been called on the restart path.
    assert pool.swap_backend.call_count == 0
    assert pool.swap_lifter.call_count == 0


def test_detector_backend_change_triggers_hot_apply(app_with_pool) -> None:
    app, pool = app_with_pool
    # Simulate main.py having committed the baseline after restart (Plan 11 behavior).
    baseline = _baseline_graph()
    from backend.web.pipeline_routes import _digest_topology
    app.state.last_applied_pipeline_config = PipelineConfig(
        detector_name="yolov11", lifter_name="point_cluster", tracker_name="none",
    )
    app.state.last_applied_topology_digest = _digest_topology(baseline["nodes"], baseline["edges"])

    # Change ONLY the detector node type: detector_yolov11 → detector_rtdetrv2.
    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "detector_1":
            n["type"] = "detector_rtdetrv2"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "hot-applied"
    assert "detector_name" in body["changed"]
    assert body["active_detector"] == "rtdetrv2"
    pool.swap_backend.assert_called_once_with("rtdetrv2", {})
    # Lifter unchanged — swap_lifter must NOT be called.
    assert pool.swap_lifter.call_count == 0
    # Restart callback must NOT be called (PID stability SC#4).
    assert app.state.command_callback.call_count == 0
    # last_applied_pipeline_config updated immediately.
    assert app.state.last_applied_pipeline_config.detector_name == "rtdetrv2"


def test_topology_change_triggers_restart(app_with_pool) -> None:
    app, pool = app_with_pool
    baseline = _baseline_graph()
    from backend.web.pipeline_routes import _digest_topology
    app.state.last_applied_pipeline_config = PipelineConfig(tracker_name="none")
    app.state.last_applied_topology_digest = _digest_topology(baseline["nodes"], baseline["edges"])

    # Delete the tracker_1 node + its edges (topology changed).
    changed = _baseline_graph()
    changed["nodes"] = [n for n in changed["nodes"] if n["id"] != "tracker_1"]
    changed["edges"] = [
        e for e in changed["edges"]
        if e["source"] != "tracker_1" and e["target"] != "tracker_1"
    ]

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 200
    assert res.json() == {"status": "restarting"}
    assert app.state.command_callback.call_count == 1
    assert pool.swap_backend.call_count == 0


def test_slam_backend_change_triggers_restart(app_with_pool) -> None:
    app, pool = app_with_pool
    baseline = _baseline_graph()
    from backend.web.pipeline_routes import _digest_topology
    app.state.last_applied_pipeline_config = PipelineConfig()
    app.state.last_applied_topology_digest = _digest_topology(baseline["nodes"], baseline["edges"])

    # Change ONLY the slam node type: slam_icp → slam_orbslam3.
    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "slam_1":
            n["type"] = "slam_orbslam3"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 200
    assert res.json() == {"status": "restarting"}
    assert app.state.command_callback.call_count == 1
    assert pool.swap_backend.call_count == 0


def test_hot_apply_updates_last_applied_config(app_with_pool) -> None:
    app, pool = app_with_pool
    baseline = _baseline_graph()
    from backend.web.pipeline_routes import _digest_topology
    app.state.last_applied_pipeline_config = PipelineConfig(detector_name="yolov11")
    app.state.last_applied_topology_digest = _digest_topology(baseline["nodes"], baseline["edges"])

    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "detector_1":
            n["type"] = "detector_rtdetrv2"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 200
    assert app.state.last_applied_pipeline_config.detector_name == "rtdetrv2"


def test_hot_apply_swap_backend_failure_returns_400(app_with_pool) -> None:
    app, pool = app_with_pool
    baseline = _baseline_graph()
    from backend.web.pipeline_routes import _digest_topology
    app.state.last_applied_pipeline_config = PipelineConfig(detector_name="yolov11")
    app.state.last_applied_topology_digest = _digest_topology(baseline["nodes"], baseline["edges"])

    pool.swap_backend.side_effect = ValueError("simulated swap failure")

    changed = _baseline_graph()
    for n in changed["nodes"]:
        if n["id"] == "detector_1":
            n["type"] = "detector_rtdetrv2"

    client = TestClient(app)
    res = client.post("/api/pipeline/apply", json=changed)
    assert res.status_code == 400
    assert "swap_backend failed" in res.json()["detail"]
    # Restart path NOT triggered (hot-apply attempted but failed cleanly).
    assert app.state.command_callback.call_count == 0
