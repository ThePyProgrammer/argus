"""Integration tests for /api/pipeline/* REST endpoints."""

import json
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.slam.registry import SLAMRegistry
from src.coordination.merge_registry import MergeRegistry


@pytest.fixture(autouse=True)
def _reset_registries():
    """Clear and re-register mock backends for each test."""
    SLAMRegistry._clear()
    MergeRegistry._clear()
    SLAMRegistry.register(
        "icp", "ICP Odometry", "src.slam.backends.icp_backend.ICPBackend"
    )
    MergeRegistry.register(
        "icp_union", "ICP Union",
        "src.coordination.merge_strategies.icp_union.ICPUnionStrategy",
    )
    yield
    SLAMRegistry._clear()
    MergeRegistry._clear()


@pytest.fixture
def tmp_presets(tmp_path, monkeypatch):
    """Create temp preset dirs and monkeypatch pipeline_routes to use them."""
    builtin_dir = tmp_path / "builtin"
    user_dir = tmp_path / "user"
    builtin_dir.mkdir()
    user_dir.mkdir()

    # Write built-in presets
    for name, filename in [
        ("Default ICP", "default_icp.json"),
        ("PGO High Quality", "pgo_high_quality.json"),
        ("Comparison Mode", "comparison_mode.json"),
    ]:
        preset = {
            "name": name,
            "nodes": [{"id": "s1", "type": "sensor_rgbd", "params": {}}],
            "edges": [],
        }
        (builtin_dir / filename).write_text(json.dumps(preset))

    import backend.web.pipeline_routes as routes_mod

    monkeypatch.setattr(routes_mod, "PRESET_DIR", tmp_path)
    monkeypatch.setattr(routes_mod, "BUILTIN_DIR", builtin_dir)
    monkeypatch.setattr(routes_mod, "USER_DIR", user_dir)

    return tmp_path


@pytest.fixture
def client(tmp_presets):
    from backend.web.pipeline_routes import router

    app = FastAPI()
    app.include_router(router)
    app.state.command_callback = lambda cmd: None
    app.state.pending_pipeline_config = None
    return TestClient(app)


def _valid_graph():
    return {
        "nodes": [
            {"id": "sensor_1", "type": "sensor_rgbd", "params": {}},
            {"id": "slam_1", "type": "slam_icp", "params": {}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {
                "source": "sensor_1",
                "sourceHandle": "image_out",
                "target": "slam_1",
                "targetHandle": "image_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "cloud_out",
                "target": "merger_1",
                "targetHandle": "cloud_in",
            },
            {
                "source": "slam_1",
                "sourceHandle": "pose_out",
                "target": "merger_1",
                "targetHandle": "pose_in",
            },
            {
                "source": "merger_1",
                "sourceHandle": "merged_out",
                "target": "viz_1",
                "targetHandle": "cloud_in",
            },
        ],
    }


def test_apply_valid_config(client):
    """POST /api/pipeline/apply with valid graph returns restarting status."""
    resp = client.post("/api/pipeline/apply", json=_valid_graph())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "restarting"


def test_reject_cycle(client):
    """POST /api/pipeline/apply with cyclic graph returns 422."""
    graph = {
        "nodes": [
            {"id": "a", "type": "sensor_rgbd", "params": {}},
            {"id": "b", "type": "slam_icp", "params": {}},
        ],
        "edges": [
            {"source": "a", "sourceHandle": "image_out", "target": "b", "targetHandle": "image_in"},
            {"source": "b", "sourceHandle": "pose_out", "target": "a", "targetHandle": "image_in"},
        ],
    }
    resp = client.post("/api/pipeline/apply", json=graph)
    assert resp.status_code == 422


def test_reject_unconnected(client):
    """POST /api/pipeline/apply with unconnected required port returns 422."""
    graph = {
        "nodes": [
            {"id": "slam_1", "type": "slam_icp", "params": {}},
            {"id": "merger_1", "type": "merger_icp_union", "params": {}},
            {"id": "viz_1", "type": "viz_output", "params": {}},
        ],
        "edges": [
            {"source": "slam_1", "sourceHandle": "cloud_out", "target": "merger_1", "targetHandle": "cloud_in"},
            {"source": "merger_1", "sourceHandle": "merged_out", "target": "viz_1", "targetHandle": "cloud_in"},
        ],
    }
    resp = client.post("/api/pipeline/apply", json=graph)
    assert resp.status_code == 422


def test_preset_crud(client, tmp_presets):
    """POST saves, GET lists, GET by name loads a user preset."""
    # Save
    save_resp = client.post(
        "/api/pipeline/presets",
        json={"name": "my_test", "nodes": [{"id": "s1", "type": "sensor_rgbd", "params": {}}], "edges": []},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "saved"

    # List
    list_resp = client.get("/api/pipeline/presets")
    assert list_resp.status_code == 200
    names = [p["name"] for p in list_resp.json()["presets"]]
    assert "my_test" in names

    # Load by name
    load_resp = client.get("/api/pipeline/presets/my_test")
    assert load_resp.status_code == 200
    assert load_resp.json()["name"] == "my_test"


def test_node_catalog(client):
    """GET /api/pipeline/node-catalog returns list with key node types."""
    resp = client.get("/api/pipeline/node-catalog")
    assert resp.status_code == 200
    types = [n["type"] for n in resp.json()["nodes"]]
    assert "sensor_rgbd" in types
    assert "filter_voxel_downsample" in types
    assert "viz_output" in types


def test_builtin_presets(client):
    """GET /api/pipeline/presets includes 3 built-in presets with builtIn=true."""
    resp = client.get("/api/pipeline/presets")
    assert resp.status_code == 200
    presets = resp.json()["presets"]
    builtin_names = [p["name"] for p in presets if p.get("builtIn")]
    assert "Default ICP" in builtin_names
    assert "PGO High Quality" in builtin_names
    assert "Comparison Mode" in builtin_names
