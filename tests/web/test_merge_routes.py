"""Integration tests for /api/slam/merge-* REST endpoints."""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.web.slam_routes import router
from src.coordination.merge_registry import MergeRegistry


@pytest.fixture(autouse=True)
def _ensure_icp_union_registered():
    """Re-register icp_union strategy if another test cleared the registry."""
    MergeRegistry._clear()
    import src.coordination.merge_strategies.icp_union as _icp

    importlib.reload(_icp)
    yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    # Set up minimal app.state for merge strategy endpoints
    app.state.active_merge_strategy = "icp_union"
    app.state.pending_merge_strategy = None
    app.state.pending_merge_params = {}
    app.state.command_callback = lambda cmd: None  # no-op
    # Also set SLAM state to avoid errors on shared router
    app.state.active_slam_backend = "icp"
    app.state.pending_slam_backend = None
    app.state.pending_slam_params = {}
    return TestClient(app)


def test_list_merge_strategies(client):
    """GET /api/slam/merge-strategies returns 200 with strategies list containing icp_union."""
    resp = client.get("/api/slam/merge-strategies")
    assert resp.status_code == 200
    data = resp.json()
    assert "strategies" in data
    names = [s["name"] for s in data["strategies"]]
    assert "icp_union" in names


def test_list_merge_strategies_icp_union_fields(client):
    """icp_union entry has name, display, available, capabilities, parameter_schema."""
    resp = client.get("/api/slam/merge-strategies")
    icp = next(s for s in resp.json()["strategies"] if s["name"] == "icp_union")
    assert icp["available"] is True
    assert "display" in icp
    assert "capabilities" in icp
    assert "parameter_schema" in icp


def test_select_merge_strategy_valid(client):
    """POST /api/slam/merge-strategy with valid strategy returns 200 restarting."""
    resp = client.post("/api/slam/merge-strategy", json={"strategy": "icp_union"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "restarting"
    assert data["strategy"] == "icp_union"


def test_select_merge_strategy_unknown_returns_404(client):
    """POST /api/slam/merge-strategy with unknown strategy returns 404."""
    resp = client.post("/api/slam/merge-strategy", json={"strategy": "nonexistent"})
    assert resp.status_code == 404


def test_select_merge_strategy_unavailable_returns_400(client):
    """POST /api/slam/merge-strategy with unavailable strategy returns 400."""
    # Register a fake unavailable strategy
    MergeRegistry.register("broken", "Broken Strategy", "no.such.module.BrokenClass")
    resp = client.post("/api/slam/merge-strategy", json={"strategy": "broken"})
    assert resp.status_code == 400


def test_get_active_merge_strategy(client):
    """GET /api/slam/merge-strategy returns 200 with current active strategy."""
    resp = client.get("/api/slam/merge-strategy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "icp_union"
    assert "display" in data
    assert "parameters" in data


def test_patch_merge_params(client):
    """PATCH /api/slam/merge-params returns per-param status."""
    resp = client.patch("/api/slam/merge-params", json={"params": {"resolution": 0.2}})
    assert resp.status_code == 200
    data = resp.json()
    assert "resolution" in data["results"]
    # resolution is not live_tunable, so should require restart
    assert data["results"]["resolution"]["status"] == "requires_restart"


def test_select_merge_strategy_sets_pending_and_calls_callback(client):
    """POST /api/slam/merge-strategy sets app.state.pending_merge_strategy and calls command_callback."""
    calls = []
    client.app.state.command_callback = lambda cmd: calls.append(cmd)
    resp = client.post("/api/slam/merge-strategy", json={"strategy": "icp_union"})
    assert resp.status_code == 200
    assert client.app.state.pending_merge_strategy == "icp_union"
    assert len(calls) == 1
    assert calls[0] == {"action": "restart"}
