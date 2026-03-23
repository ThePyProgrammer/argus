"""Integration tests for /api/slam/* REST endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.web.slam_routes import router
from src.slam.registry import SLAMRegistry

# Ensure ICP backend is registered
import src.slam.backends  # noqa: F401


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    # Set up minimal app.state
    app.state.active_slam_backend = "icp"
    app.state.pending_slam_backend = None
    app.state.pending_slam_params = {}
    app.state.command_callback = lambda cmd: None  # no-op
    return TestClient(app)


def test_list_backends(client):
    """GET /api/slam/backends returns 200 with backends list containing ICP."""
    resp = client.get("/api/slam/backends")
    assert resp.status_code == 200
    data = resp.json()
    assert "backends" in data
    names = [b["name"] for b in data["backends"]]
    assert "icp" in names


def test_list_backends_icp_capabilities(client):
    """ICP entry has correct capabilities."""
    resp = client.get("/api/slam/backends")
    icp = next(b for b in resp.json()["backends"] if b["name"] == "icp")
    assert icp["capabilities"]["supports_imu"] is False
    assert icp["capabilities"]["outputs_dense"] is True


def test_list_backends_icp_parameter_schema(client):
    """ICP entry has parameter_schema with voxel_size and max_cloud_points."""
    resp = client.get("/api/slam/backends")
    icp = next(b for b in resp.json()["backends"] if b["name"] == "icp")
    props = icp["parameter_schema"]["properties"]
    assert "voxel_size" in props
    assert "max_cloud_points" in props


def test_select_valid_backend(client):
    """POST /api/slam/select with valid backend returns 200 restarting."""
    resp = client.post("/api/slam/select", json={"backend": "icp"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "restarting"
    assert data["backend"] == "icp"


def test_select_unknown_backend(client):
    """POST /api/slam/select with unknown backend returns 404."""
    resp = client.post("/api/slam/select", json={"backend": "nonexistent"})
    assert resp.status_code == 404


def test_get_active(client):
    """GET /api/slam/active returns current backend info."""
    resp = client.get("/api/slam/active")
    assert resp.status_code == 200
    data = resp.json()
    assert data["backend"] == "icp"
    assert data["display"] == "ICP Odometry"
    assert "parameters" in data


def test_patch_params_startup_only(client):
    """PATCH /api/slam/params with startup-only param returns requires_restart."""
    resp = client.patch("/api/slam/params", json={"params": {"voxel_size": 0.05}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]["voxel_size"]["status"] == "requires_restart"


def test_patch_params_unknown(client):
    """PATCH /api/slam/params with unknown param returns unknown_parameter."""
    resp = client.patch("/api/slam/params", json={"params": {"nonexistent": 1}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"]["nonexistent"]["status"] == "unknown_parameter"
