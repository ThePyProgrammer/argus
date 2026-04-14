"""Concurrency + pool-level tests for DetectorWorkerPool.swap_lifter (Plan 04-05).

Task 1 tests (pool-level):
  - swap_lifter replaces every worker's `_lifter` ref with a FRESH instance.
  - swap_lifter does NOT synchronously warm up lifters (must be fast).
  - swap_lifter rejects unknown lifter names (ValueError via registry.create).
  - swap_lifter under sustained 30Hz submit load does not drop frames or raise.

Task 2 tests (route-level, appended below the Task 1 block):
  - POST /api/detectors/lifter-hotswap returns {"status": "swapped", ...} on 200.
  - Unknown lifter → 404.
  - app.state.detector_pool is None → 503.
  - Pool is called with `(req.lifter, req.params or {})`.
  - app.state.active_lifter is updated after a successful swap.
  - /lifter-select route is REMOVED (404/405).

All tests use `pytest.importorskip("ultralytics")` when the pool is actually
constructed (per-worker YOLOv11 backend creation would otherwise require
torch + ultralytics installed). Route-level tests use a fake pool and do not
need ultralytics.
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame


@pytest.fixture
def dummy_frame():
    return SensorFrame(
        rgb=np.zeros((480, 640, 3), dtype=np.uint8),
        depth=np.zeros((480, 640), dtype=np.float32),
        ground_truth_pose=np.eye(4),
        sim_time=0.0,
    )


def _make_pool(robot_ids, lifter_params=None):
    # Force registration
    import src.perception.lifters  # noqa: F401
    import src.perception.backends  # noqa: F401
    from src.perception.worker_pool import DetectorWorkerPool

    intr = CameraIntrinsics.from_fov(640, 480, 70.0)
    return DetectorWorkerPool(
        robot_ids=list(robot_ids),
        backend_name="yolov11",
        backend_params=None,
        lifter_name="median_depth",
        intrinsics_per_robot={rid: intr for rid in robot_ids},
        lifter_params=lifter_params,
    )


# ---------------------------------------------------------------------------
# Task 1: Pool-level swap_lifter contract
# ---------------------------------------------------------------------------


def test_swap_lifter_replaces_every_workers_lifter_ref():
    pytest.importorskip("ultralytics")
    pool = _make_pool(["r0", "r1", "r2"])
    pre = {rid: pool.get_worker(rid)._lifter for rid in pool.robot_ids}
    pool.swap_lifter("median_depth", {"depth_near_m": 0.2})
    for rid in pool.robot_ids:
        new = pool.get_worker(rid)._lifter
        assert new is not pre[rid], f"{rid} lifter was not replaced"
        assert new.depth_near_m == 0.2, f"{rid} params not applied"
    assert pool.lifter_name == "median_depth"


def test_swap_lifter_is_fast_no_warmup():
    pytest.importorskip("ultralytics")
    pool = _make_pool(["r0", "r1", "r2"])
    t0 = time.perf_counter()
    pool.swap_lifter("median_depth", {})
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 100.0, f"swap took {elapsed_ms:.2f}ms — warmup must not fire"


def test_swap_lifter_rejects_unknown_name():
    pytest.importorskip("ultralytics")
    pool = _make_pool(["r0"])
    with pytest.raises(ValueError):
        pool.swap_lifter("definitely_not_a_lifter", {})


def test_hotswap_under_30hz_submit(dummy_frame):
    pytest.importorskip("ultralytics")
    pool = _make_pool(["r0"])
    pool.warmup_all({"r0": dummy_frame})
    pool.start()

    errors: list[BaseException] = []
    stop = threading.Event()

    def submitter():
        try:
            while not stop.is_set():
                pool.submit("r0", dummy_frame, np.eye(4), None)
                time.sleep(1.0 / 30.0)
        except BaseException as exc:  # noqa: BLE001 — surface any error
            errors.append(exc)

    t = threading.Thread(target=submitter, daemon=True)
    t.start()
    try:
        time.sleep(0.3)
        pool.swap_lifter("median_depth", {"depth_near_m": 0.3})
        time.sleep(0.3)
    finally:
        stop.set()
        t.join(timeout=2.0)
        pool.shutdown()

    assert errors == [], f"submitter raised during hot-swap: {errors}"
    assert pool.get_worker("r0")._lifter.depth_near_m == 0.3
    assert pool.lifter_name == "median_depth"


# ---------------------------------------------------------------------------
# Task 2: REST /api/detectors/lifter-hotswap route contract
# ---------------------------------------------------------------------------


class _FakePool:
    """Minimal stand-in for DetectorWorkerPool that records swap calls."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.raise_on_swap: Exception | None = None

    def swap_lifter(self, name: str, params: dict) -> None:
        if self.raise_on_swap is not None:
            raise self.raise_on_swap
        self.calls.append((name, dict(params)))


@pytest.fixture
def client_and_pool():
    from fastapi.testclient import TestClient

    from backend.web.server import create_app

    app, _viz = create_app(["r0"])
    pool = _FakePool()
    app.state.detector_pool = pool
    return TestClient(app), pool


def test_lifter_hotswap_returns_swapped(client_and_pool):
    import src.perception.lifters  # noqa: F401
    client, _pool = client_and_pool
    res = client.post(
        "/api/detectors/lifter-hotswap", json={"lifter": "median_depth"}
    )
    assert res.status_code == 200, res.text
    assert res.json() == {"status": "swapped", "lifter": "median_depth"}


def test_lifter_hotswap_unknown_returns_404(client_and_pool):
    import src.perception.lifters  # noqa: F401
    client, _ = client_and_pool
    res = client.post(
        "/api/detectors/lifter-hotswap", json={"lifter": "not_a_lifter"}
    )
    assert res.status_code == 404


def test_lifter_hotswap_no_pool_returns_503():
    import src.perception.lifters  # noqa: F401
    from fastapi.testclient import TestClient

    from backend.web.server import create_app

    app, _ = create_app(["r0"])
    app.state.detector_pool = None
    client = TestClient(app)
    res = client.post(
        "/api/detectors/lifter-hotswap", json={"lifter": "median_depth"}
    )
    assert res.status_code == 503


def test_lifter_hotswap_calls_pool_swap_lifter(client_and_pool):
    import src.perception.lifters  # noqa: F401
    client, pool = client_and_pool
    client.post(
        "/api/detectors/lifter-hotswap",
        json={"lifter": "median_depth", "params": {"depth_near_m": 0.25}},
    )
    assert pool.calls == [("median_depth", {"depth_near_m": 0.25})]


def test_lifter_hotswap_updates_active_lifter_state(client_and_pool):
    import src.perception.lifters  # noqa: F401
    client, _ = client_and_pool
    client.post(
        "/api/detectors/lifter-hotswap", json={"lifter": "median_depth"}
    )
    res = client.get("/api/detectors/active-lifter")
    assert res.status_code == 200
    assert res.json()["lifter"] == "median_depth"


def test_lifter_select_route_removed():
    from fastapi.testclient import TestClient

    from backend.web.server import create_app

    app, _ = create_app(["r0"])
    client = TestClient(app)
    res = client.post(
        "/api/detectors/lifter-select", json={"lifter": "median_depth"}
    )
    assert res.status_code in (404, 405), (
        f"/lifter-select should be removed, got {res.status_code}"
    )
