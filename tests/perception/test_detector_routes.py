"""Tests for backend/web/detector_routes.py — DET-MODELS-05 REST surface.

Exercises the 4-endpoint contract cloned from slam_routes.py:
  GET  /api/detectors/backends   — list
  POST /api/detectors/select     — pending write + restart command (D-02)
  GET  /api/detectors/active     — active backend metadata
  PATCH /api/detectors/params    — live_tunable / requires_restart / unknown

Plus the WS `detector_param_update` handler inside server.py's
_dispatch_ws_message (mirrors slam_param_update).

All tests run torch-free — they register module-level FakeYolo /
Unavailable backends and never instantiate the real YOLOv11Backend.

NOTE on fake placement: fakes are module-level (not nested in a fixture)
because DetectorRegistry.list_backends() resolves backends via
importlib.import_module(module_path) + getattr(module, class_name). Nested
classes ("register_fakes.<locals>.FakeYolo") fail that lookup and get
reported as available=False, which would defeat POST /select tests.
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.perception.types import DetectorInput


# ---------------------------------------------------------------------------
# Module-level fake backends — must be importable via class_path for
# DetectorRegistry.list_backends() -> _load_class() -> getattr(module, name).
# ---------------------------------------------------------------------------


class FakeYolo:
    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 10,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "confidence_threshold": {
                "type": "number",
                "live_tunable": True,
                "default": 0.5,
            },
            "model_path": {
                "type": "string",
                "live_tunable": False,
                "default": "yolo11n.pt",
            },
        },
    }

    def __init__(self, **kwargs):
        pass

    def process_frame(self, f):
        pass

    def reset(self):
        pass

    def warmup(self, f):
        pass

    def get_metrics(self):
        return {}

    def apply_params(self, p):
        return {}

    @classmethod
    def available(cls):
        return True, None


class UnavailableBackend:
    CAPABILITIES = dict(FakeYolo.CAPABILITIES)
    PARAMETER_SCHEMA = {}

    def __init__(self, **kwargs):
        pass

    def process_frame(self, f):
        pass

    def reset(self):
        pass

    def warmup(self, f):
        pass

    def get_metrics(self):
        return {}

    def apply_params(self, p):
        return {}

    @classmethod
    def available(cls):
        return False, "run scripts/install_unavailable.sh"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registries():
    """Wipe DetectorRegistry + Detection3DRegistry around every test.

    Some test processes may have imported src.perception.backends at import
    time (which registers yolov11). We clear up-front so each test sees a
    known registry state, and clear again at teardown so we do not leak
    fake backends into unrelated tests.
    """
    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()


@pytest.fixture
def register_fakes():
    """Register the module-level FakeYolo + UnavailableBackend so
    DetectorRegistry.list_backends() reports them available / unavailable
    respectively. Exercises all three PATCH /params status paths via the
    FakeYolo parameter schema."""
    from src.perception.registry import DetectorRegistry

    DetectorRegistry.register(
        name="fake_yolo",
        display="Fake YOLO",
        class_path=f"{FakeYolo.__module__}.{FakeYolo.__qualname__}",
        klass=FakeYolo,
    )
    DetectorRegistry.register(
        name="unavailable_backend",
        display="Unavailable",
        class_path=f"{UnavailableBackend.__module__}.{UnavailableBackend.__qualname__}",
        klass=UnavailableBackend,
    )
    yield


@pytest.fixture
def app_client(register_fakes):
    """Build a TestClient around create_app with a MagicMock command callback.

    The fixture forces app.state.active_detector_backend = "fake_yolo" so
    PATCH /params + GET /active + WS detector_param_update resolve against
    the fake schema instead of the default "yolov11" (which was cleared by
    _clean_registries).
    """
    from backend.web.server import create_app

    command_cb = MagicMock()
    app, _viz = create_app(robot_ids=["r0"], command_cb=command_cb)
    app.state.active_detector_backend = "fake_yolo"
    # Reset pending state in case a previous test mutated the module-level app.
    app.state.pending_detector_backend = None
    app.state.pending_detector_params = {}
    client = TestClient(app)
    return client, command_cb, app


# ---------------------------------------------------------------------------
# GET /api/detectors/backends
# ---------------------------------------------------------------------------


def test_list_backends_returns_fake_yolo(app_client):
    client, _cb, _app = app_client
    r = client.get("/api/detectors/backends")
    assert r.status_code == 200
    backends = r.json()["backends"]
    names = {b["name"] for b in backends}
    assert "fake_yolo" in names
    assert "unavailable_backend" in names
    fake_entry = next(b for b in backends if b["name"] == "fake_yolo")
    assert fake_entry["available"] is True
    unavail_entry = next(b for b in backends if b["name"] == "unavailable_backend")
    assert unavail_entry["available"] is False
    assert "install_unavailable.sh" in unavail_entry["reason"]


# ---------------------------------------------------------------------------
# POST /api/detectors/select
# ---------------------------------------------------------------------------


def test_select_sets_pending_backend(app_client):
    client, cb, app = app_client
    r = client.post("/api/detectors/select", json={"backend": "fake_yolo"})
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "restarting", "backend": "fake_yolo"}
    assert app.state.pending_detector_backend == "fake_yolo"
    cb.assert_called_with({"action": "restart"})


def test_select_unknown_backend_returns_404(app_client):
    client, _cb, _app = app_client
    r = client.post("/api/detectors/select", json={"backend": "nonexistent"})
    assert r.status_code == 404
    assert "nonexistent" in r.json()["detail"]


def test_select_unavailable_backend_returns_400(app_client):
    client, _cb, _app = app_client
    r = client.post(
        "/api/detectors/select", json={"backend": "unavailable_backend"}
    )
    assert r.status_code == 400
    assert "unavailable" in r.json()["detail"].lower()


def test_select_with_params_stashes_pending_params(app_client):
    client, _cb, app = app_client
    r = client.post(
        "/api/detectors/select",
        json={"backend": "fake_yolo", "params": {"confidence_threshold": 0.9}},
    )
    assert r.status_code == 200
    assert app.state.pending_detector_params == {"confidence_threshold": 0.9}


# ---------------------------------------------------------------------------
# GET /api/detectors/active
# ---------------------------------------------------------------------------


def test_get_active_reflects_state(app_client):
    client, _cb, app = app_client
    app.state.active_detector_backend = "fake_yolo"
    r = client.get("/api/detectors/active")
    assert r.status_code == 200
    data = r.json()
    assert data["backend"] == "fake_yolo"
    assert data["display"] == "Fake YOLO"
    assert "confidence_threshold" in data["parameters"].get("properties", {})


# ---------------------------------------------------------------------------
# PATCH /api/detectors/params
# ---------------------------------------------------------------------------


def test_patch_params_live_tunable_and_requires_restart(app_client):
    client, _cb, app = app_client
    app.state.active_detector_backend = "fake_yolo"
    r = client.patch(
        "/api/detectors/params",
        json={
            "params": {
                "confidence_threshold": 0.8,
                "model_path": "yolo11s.pt",
                "bogus_key": "nope",
            }
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results["confidence_threshold"]["status"] == "applied"
    assert results["model_path"]["status"] == "requires_restart"
    assert results["bogus_key"]["status"] == "unknown_parameter"
    # Live + requires_restart keys are buffered; unknown is NOT buffered.
    assert app.state.pending_detector_params.get("confidence_threshold") == 0.8
    assert app.state.pending_detector_params.get("model_path") == "yolo11s.pt"
    assert "bogus_key" not in app.state.pending_detector_params


# ---------------------------------------------------------------------------
# WS detector_param_update (server.py _dispatch_ws_message)
# ---------------------------------------------------------------------------


def _recv_until_detector_ack(ws, tries: int = 10):
    """Drain initial broadcasts (robot_list, cloud_configs, …) until we find
    the detector_param_ack frame. Fail with a clear assertion otherwise."""
    for _ in range(tries):
        msg = ws.receive_json()
        if msg.get("type") == "detector_param_ack":
            return msg
    pytest.fail("No detector_param_ack received")


def test_ws_detector_param_update_applied(app_client):
    client, _cb, app = app_client
    app.state.active_detector_backend = "fake_yolo"
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "type": "detector_param_update",
                "param": "confidence_threshold",
                "value": 0.7,
            }
        )
        msg = _recv_until_detector_ack(ws)
        assert msg["payload"]["status"] == "applied"
        assert msg["payload"]["param"] == "confidence_threshold"
        assert msg["payload"]["value"] == 0.7
        # The live_tunable branch buffers the new value for coordinator pickup.
        assert app.state.pending_detector_params.get("confidence_threshold") == 0.7


def test_ws_detector_param_update_requires_restart(app_client):
    client, _cb, app = app_client
    app.state.active_detector_backend = "fake_yolo"
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "type": "detector_param_update",
                "param": "model_path",
                "value": "yolo11s.pt",
            }
        )
        msg = _recv_until_detector_ack(ws)
        assert msg["payload"]["status"] == "requires_restart"
        assert msg["payload"]["param"] == "model_path"


def test_ws_detector_param_update_unknown_parameter(app_client):
    client, _cb, app = app_client
    app.state.active_detector_backend = "fake_yolo"
    with client.websocket_connect("/ws") as ws:
        ws.send_json(
            {
                "type": "detector_param_update",
                "param": "nonexistent_param",
                "value": 42,
            }
        )
        msg = _recv_until_detector_ack(ws)
        assert msg["payload"]["status"] == "unknown_parameter"
        assert msg["payload"]["param"] == "nonexistent_param"
        # No mutation for unknown params.
        assert "nonexistent_param" not in app.state.pending_detector_params
