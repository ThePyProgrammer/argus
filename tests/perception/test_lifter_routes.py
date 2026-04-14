"""Tests for backend/web/detector_routes.py lifter endpoints — D-10 REST surface.

Mirrors test_detector_routes.py pattern:
  GET   /api/detectors/lifters        — list (incl. side-effect-triggered registry pop)
  GET   /api/detectors/active-lifter  — active lifter metadata
  PATCH /api/detectors/lifter-params  — live_tunable / requires_restart / unknown

Phase 4 D-09 (supersedes Phase 3 D-09): `POST /lifter-select` is REMOVED;
replaced by `POST /lifter-hotswap` (atomic ref swap, no restart). Route-level
tests for the hot-swap endpoint live in ``test_lifter_hotswap.py`` — this
file retains the list / active / params surface plus a regression lock that
asserts `/lifter-select` is no longer registered.

All tests run torch-free — they register module-level FakeLifter / UnavailableLifter
and never instantiate the real MedianDepthLifter (except cold-boot test which
relies on the handler's `import src.perception.lifters` side-effect to register
median_depth — Pitfall #4 regression guard).

NOTE on fake placement: fakes are module-level (not nested in a fixture)
because Detection3DRegistry.list_backends() resolves backends via
importlib.import_module(module_path) + getattr(module, class_name). Nested
classes ("register_fakes.<locals>.FakeLifter") fail that lookup and get
reported as available=False, which would defeat POST /lifter-select tests.
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Module-level fake lifters — must be importable via class_path for
# Detection3DRegistry.list_backends() -> _load_class() -> getattr(module, name).
# CAPABILITIES MUST contain every key in
# src/perception/registry.py::_DETECTION_3D_REQUIRED_KEYS
# (requires_depth, requires_point_cloud, outputs_oriented, license)
# or Detection3DRegistry.register() raises ValueError synchronously.
# ---------------------------------------------------------------------------


class FakeLifter:
    CAPABILITIES = {
        "requires_depth": True,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA = {
        "type": "object",
        "properties": {
            "depth_near_m": {
                "type": "number",
                "live_tunable": True,
                "default": 0.1,
            },
            "smoothing_mode": {
                "type": "string",
                "live_tunable": False,
                "default": "median",
            },
        },
    }

    def __init__(self, **kwargs):
        pass

    def lift(self, *args, **kwargs):
        pass

    def reset(self):
        pass

    @classmethod
    def available(cls):
        return True, None


class UnavailableLifter:
    CAPABILITIES = dict(FakeLifter.CAPABILITIES)
    PARAMETER_SCHEMA = {}

    def __init__(self, **kwargs):
        pass

    def lift(self, *args, **kwargs):
        pass

    def reset(self):
        pass

    @classmethod
    def available(cls):
        return False, "run scripts/install_fake_lifter.sh"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registries():
    """Wipe DetectorRegistry + Detection3DRegistry around every test, then
    restore the natural baseline (median_depth re-registered via reload).

    Mirrors test_detector_routes._clean_registries: some test processes may
    have triggered detector or lifter registration via side-effect imports
    (e.g. main.py path); we reset to a known state per test so fake_lifter
    registrations do not collide. At teardown we re-trigger the
    @detection_3d decorator on src.perception.lifters.median_depth so the
    NEXT test module that does `import src.perception.lifters` (e.g.
    test_median_depth_lifter.py) finds median_depth registered as expected
    on a normal module-import path. Without this reload the registry would
    stay empty after this file's tests run because Python's module cache
    suppresses decorator re-execution on subsequent `import` statements
    (Pitfall #4 — same root cause as the cold-boot test below).
    """
    import importlib
    import sys

    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()

    # Restore baseline: re-run @detection_3d decorators on built-in lifters
    # so we do not leak an empty Detection3DRegistry into downstream tests
    # whose `import src.perception.lifters` would otherwise be a no-op.
    if "src.perception.lifters.median_depth" in sys.modules:
        importlib.reload(sys.modules["src.perception.lifters.median_depth"])
    else:
        import src.perception.lifters.median_depth  # noqa: F401


@pytest.fixture
def register_fakes():
    """Register the module-level FakeLifter + UnavailableLifter so
    Detection3DRegistry.list_backends() reports them available / unavailable
    respectively. Exercises all three PATCH /lifter-params status paths via
    the FakeLifter parameter schema."""
    from src.perception.registry import Detection3DRegistry

    Detection3DRegistry.register(
        name="fake_lifter",
        display="Fake Lifter",
        class_path=f"{FakeLifter.__module__}.{FakeLifter.__qualname__}",
        klass=FakeLifter,
    )
    Detection3DRegistry.register(
        name="unavailable_lifter",
        display="Unavailable Lifter",
        class_path=f"{UnavailableLifter.__module__}.{UnavailableLifter.__qualname__}",
        klass=UnavailableLifter,
    )
    yield


@pytest.fixture
def app_client(register_fakes):
    """Build a TestClient around create_app with a MagicMock command callback.

    Forces app.state.active_lifter = 'fake_lifter' so PATCH /lifter-params +
    GET /active-lifter resolve against the fake schema instead of the default
    'median_depth' (which was cleared by _clean_registries).
    """
    from backend.web.server import create_app

    command_cb = MagicMock()
    app, _viz = create_app(robot_ids=["r0"], command_cb=command_cb)
    app.state.active_lifter = "fake_lifter"
    app.state.pending_lifter = None
    app.state.pending_lifter_params = {}
    client = TestClient(app)
    return client, command_cb, app


# ---------------------------------------------------------------------------
# GET /api/detectors/lifters
# ---------------------------------------------------------------------------


def test_list_lifters_returns_fake_lifter(app_client):
    client, _cb, _app = app_client
    r = client.get("/api/detectors/lifters")
    assert r.status_code == 200
    lifters = r.json()["lifters"]
    names = {l["name"] for l in lifters}
    assert "fake_lifter" in names
    assert "unavailable_lifter" in names
    fake_entry = next(l for l in lifters if l["name"] == "fake_lifter")
    assert fake_entry["available"] is True
    unavail_entry = next(l for l in lifters if l["name"] == "unavailable_lifter")
    assert unavail_entry["available"] is False
    assert "install_fake_lifter" in unavail_entry["reason"]


def test_list_lifters_cold_boot_triggers_registry_population():
    """Pitfall 4: handler's `import src.perception.lifters` MUST populate registry.

    This test skips register_fakes so only the handler's side-effect import
    can surface median_depth. We simulate a TRULY cold boot by evicting
    `src.perception.lifters` (and its sub-modules) from sys.modules so the
    handler's `import` statement actually re-runs the @detection_3d decorators
    instead of hitting Python's module cache. A bare Detection3DRegistry
    starts empty (the autouse _clean_registries fixture clears both registries
    at setup); if any handler forgets the side-effect import, /lifters returns
    []. This is the T-03-14 regression lock.

    Mirror of tests/web/test_merge_routes.py::_ensure_icp_union_registered
    pattern (importlib.reload after MergeRegistry._clear()).
    """
    import sys

    from backend.web.server import create_app

    # Evict the lifters package + every sub-module so the handler's
    # `import src.perception.lifters` actually re-runs decorator
    # side-effects (instead of being a sys.modules cache hit).
    for mod_name in [
        m for m in list(sys.modules) if m == "src.perception.lifters" or m.startswith("src.perception.lifters.")
    ]:
        sys.modules.pop(mod_name, None)

    app, _ = create_app(robot_ids=["r0"])
    client = TestClient(app)
    r = client.get("/api/detectors/lifters")
    assert r.status_code == 200
    names = {l["name"] for l in r.json()["lifters"]}
    assert "median_depth" in names, (
        "Handler is missing `import src.perception.lifters` side-effect (Pitfall #4)"
    )


# ---------------------------------------------------------------------------
# POST /api/detectors/lifter-select — REMOVED in Phase 4 D-09
# ---------------------------------------------------------------------------
#
# The Phase 3 restart-driven route is gone. The contract for the replacement
# `POST /lifter-hotswap` lives in tests/perception/test_lifter_hotswap.py.
# The single test below is the regression lock for the supersession.


def test_lifter_select_route_removed(app_client):
    """Phase 4 D-09: /lifter-select must return 404/405 (no handler registered)."""
    client, _cb, _app = app_client
    r = client.post(
        "/api/detectors/lifter-select", json={"lifter": "fake_lifter"}
    )
    assert r.status_code in (404, 405), (
        f"/lifter-select should be removed, got {r.status_code}"
    )


# ---------------------------------------------------------------------------
# GET /api/detectors/active-lifter
# ---------------------------------------------------------------------------


def test_get_active_lifter_reflects_state(app_client):
    client, _cb, app = app_client
    app.state.active_lifter = "fake_lifter"
    r = client.get("/api/detectors/active-lifter")
    assert r.status_code == 200
    data = r.json()
    assert data["lifter"] == "fake_lifter"
    assert data["display"] == "Fake Lifter"
    assert "depth_near_m" in data["parameters"].get("properties", {})


# ---------------------------------------------------------------------------
# PATCH /api/detectors/lifter-params
# ---------------------------------------------------------------------------


def test_patch_lifter_params_live_restart_unknown(app_client):
    client, _cb, app = app_client
    app.state.active_lifter = "fake_lifter"
    r = client.patch(
        "/api/detectors/lifter-params",
        json={
            "params": {
                "depth_near_m": 0.2,
                "smoothing_mode": "mean",
                "bogus_key": "nope",
            }
        },
    )
    assert r.status_code == 200
    results = r.json()["results"]
    assert results["depth_near_m"]["status"] == "applied"
    assert results["smoothing_mode"]["status"] == "requires_restart"
    assert results["bogus_key"]["status"] == "unknown_parameter"
    # Live + requires_restart keys are buffered; unknown is NOT buffered (T-03-12).
    assert app.state.pending_lifter_params.get("depth_near_m") == 0.2
    assert app.state.pending_lifter_params.get("smoothing_mode") == "mean"
    assert "bogus_key" not in app.state.pending_lifter_params
