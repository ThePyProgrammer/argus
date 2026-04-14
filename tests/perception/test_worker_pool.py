"""DetectorWorkerPool tests (Plan 02-04, DET-API-04 + DET-MODELS-05).

Six invariants under test (matching Plan 02-04 must-haves):

1. **One worker per robot_id** — Pool with N robot_ids owns exactly N workers;
   each worker has its OWN detector + lifter instance (per-robot isolation,
   not a shared model — supports Phase 8 stretch DET-STRETCH-04 per-robot
   param tuning).

2. **Submit dispatches by rid** — submit("r1", ...) only touches r1's worker;
   other workers' latest() remain None.

3. **Unknown rid is a safe no-op** — submit("rX", ...) never raises;
   latest("rX") returns None. D-05 / Pattern 4 defensive no-op protects the
   pool from Coordinator-side stale-rid races during restart.

4. **warmup_all is synchronous** — warmup_all returns only after every
   worker.warmup has completed. Wave 4's main.py restart block relies on
   this before emitting detector_restart_complete (D-03).

5. **inspect_worker_queues shape** — returns {rid: {queue_depth,
   drops_since_session_start, last_submit_sim_time}} for every rid. Phase 6
   MetricsPanel depends on this exact shape.

6. **Per-robot instance separation** — mutating one worker's detector does
   NOT affect another worker's detector. Proves the pool constructs fresh
   instances per rid via DetectorRegistry.create(), not a shared singleton.

Pitfall P9: this module imports ``src.perception.worker_pool`` but that
module must stay torch-free. Tests register fake backends via the registry
decorator API (same pattern as test_registry.py) and assert construction
dispatches through DetectorRegistry.create / Detection3DRegistry.create.
"""

from __future__ import annotations

import sys
import time

import numpy as np
import pytest

from src.bridge.sensor_types import CameraIntrinsics, SensorFrame
from src.perception.types import Detections2D, Detections3D, DetectorInput


# ---------------------------------------------------------------------------
# Registry isolation + fake backend registration
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_registries():
    """Isolate tests — clear both registries before and after each test.

    Matches the pattern from tests/perception/test_registry.py so the fake
    backends registered here do not leak into other test modules.
    """
    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry._clear()
    Detection3DRegistry._clear()
    yield
    DetectorRegistry._clear()
    Detection3DRegistry._clear()


class FakeDetector:
    """Fake DetectorProtocol backend: fast, introspectable, torch-free.

    Registered by the ``register_fakes`` fixture via ``DetectorRegistry.register``
    with a ``class_path`` of ``f"{__name__}.FakeDetector"``. Defined at module
    scope (NOT inside the fixture) so ``registry._load_class`` can re-import
    it from the dotted path at ``create()`` time.

    Per-instance state (``threshold``, ``warmup_count``) is what the instance-
    separation test asserts never crosses between workers.
    """

    CAPABILITIES = {
        "framework": "fake",
        "license": "MIT",
        "cpu_latency_hint_ms": 10,
        "outputs_3d_natively": False,
        "input_type": DetectorInput.RGB_ONLY,
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.threshold = 0.5  # mutable per-instance state (separation test)
        self.warmup_count = 0
        self.init_kwargs = dict(kwargs)

    def process_frame(self, f: SensorFrame) -> Detections2D:
        return Detections2D(items=[], inference_ms=1.0, image_hw=(480, 640))

    def reset(self) -> None:
        return None

    def warmup(self, f: SensorFrame) -> None:
        self.warmup_count += 1

    def get_metrics(self) -> dict:
        return {}

    def apply_params(self, p: dict) -> dict:
        return {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


class FakeLifter:
    """Fake Detection3DProtocol backend: returns an empty Detections3D envelope."""

    CAPABILITIES = {
        "requires_depth": False,
        "requires_point_cloud": False,
        "outputs_oriented": False,
        "license": "MIT",
    }
    PARAMETER_SCHEMA: dict = {}

    def __init__(self, **kwargs):
        self.init_kwargs = dict(kwargs)

    def lift(
        self,
        d2d: Detections2D,
        f: SensorFrame,
        pose: np.ndarray,
        intr: CameraIntrinsics,
        cloud: np.ndarray | None,
    ) -> Detections3D:
        return Detections3D(
            items=[],
            lifter_ms=0.0,
            detector_ms=d2d.inference_ms,
            n_raw=0,
            n_final=0,
            image_hw=d2d.image_hw,
            capture_pose=np.eye(4),
            capture_timestamp=0.0,
        )

    def reset(self) -> None:
        return None

    def get_metrics(self) -> dict:
        return {}

    def apply_params(self, p: dict) -> dict:
        return {}

    @classmethod
    def available(cls) -> tuple[bool, str | None]:
        return True, None


@pytest.fixture
def register_fakes():
    """Register the module-scope FakeDetector + FakeLifter in both registries.

    The ``_clean_registries`` autouse fixture wipes the registries before +
    after each test, so we re-register each run. We call ``register()`` with
    an explicit ``class_path`` (not the decorator) so the stored path resolves
    back to this test module via ``importlib``.
    """
    from src.perception.registry import DetectorRegistry, Detection3DRegistry

    DetectorRegistry.register(
        name="fake_yolo",
        display="Fake YOLO",
        class_path=f"{__name__}.FakeDetector",
        klass=FakeDetector,
    )
    Detection3DRegistry.register(
        name="fake_lifter",
        display="Fake Lifter",
        class_path=f"{__name__}.FakeLifter",
        klass=FakeLifter,
    )
    yield


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_frame(sim_time: float = 0.0) -> SensorFrame:
    rgb = np.zeros((480, 640, 3), dtype=np.uint8)
    depth = np.full((480, 640), 2.0, dtype=np.float32)
    return SensorFrame(
        rgb=rgb,
        depth=depth,
        ground_truth_pose=np.eye(4),
        sim_time=sim_time,
    )


def _make_pool(robot_ids=("r0", "r1", "r2")):
    """Construct a DetectorWorkerPool wired to the fake_yolo + fake_lifter registry entries."""
    from src.perception.worker_pool import DetectorWorkerPool

    intr = {rid: CameraIntrinsics.from_fov(640, 480, 70.0) for rid in robot_ids}
    return DetectorWorkerPool(
        robot_ids=list(robot_ids),
        backend_name="fake_yolo",
        backend_params={},
        lifter_name="fake_lifter",
        intrinsics_per_robot=intr,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pool_constructs_one_worker_per_robot(register_fakes) -> None:
    """Pool with 3 robot_ids owns 3 workers with 3 DISTINCT detector/lifter instances."""
    pool = _make_pool(("r0", "r1", "r2"))
    try:
        assert set(pool.robot_ids) == {"r0", "r1", "r2"}
        # Each worker must hold its own detector + lifter instance (not a shared
        # singleton) — this is the per-robot-instance-separation guarantee that
        # Phase 8 stretch param tuning relies on.
        detectors = [pool._workers[rid]._detector for rid in ("r0", "r1", "r2")]
        lifters = [pool._workers[rid]._lifter for rid in ("r0", "r1", "r2")]
        assert len({id(d) for d in detectors}) == 3, "detectors must be distinct instances"
        assert len({id(lift) for lift in lifters}) == 3, "lifters must be distinct instances"
    finally:
        pool.shutdown()


def test_submit_dispatches_to_correct_worker(register_fakes) -> None:
    """Submitting to r1 only yields a Detections3D on r1; r0 and r2 latest() stay None."""
    pool = _make_pool(("r0", "r1", "r2"))
    pool.start()
    try:
        pool.submit("r1", _make_frame(sim_time=0.5), np.eye(4), None)
        # Wait briefly for the r1 worker thread to drain _pending and write _latest.
        deadline = time.time() + 2.0
        while time.time() < deadline and pool.latest("r1") is None:
            time.sleep(0.01)
        assert pool.latest("r1") is not None, "r1 worker never produced a Detections3D"
        assert pool.latest("r0") is None, "r0 must stay idle"
        assert pool.latest("r2") is None, "r2 must stay idle"
    finally:
        pool.shutdown()


def test_unknown_rid_safe_noop(register_fakes) -> None:
    """Submit / latest with unknown rid must not raise; latest returns None (D-05)."""
    pool = _make_pool(("r0", "r1"))
    try:
        # Must not raise
        pool.submit("rX", _make_frame(), np.eye(4), None)
        assert pool.latest("rX") is None
        # Also: inspect on unknown rid is NOT on the API (only inspect_worker_queues),
        # but calling latest twice is still safe.
        assert pool.latest("r_does_not_exist") is None
    finally:
        pool.shutdown()


def test_warmup_all_is_synchronous(register_fakes) -> None:
    """warmup_all(...) blocks until every worker.warmup returns.

    After warmup_all, the sum of FakeDetector.warmup_count across all workers
    must equal len(robot_ids) — proving the call was synchronous (not queued
    to the worker thread). D-03: Wave 4's restart block relies on this
    before emitting detector_restart_complete.
    """
    robot_ids = ("r0", "r1", "r2")
    pool = _make_pool(robot_ids)
    try:
        dummy_frames = {rid: _make_frame(sim_time=0.0) for rid in robot_ids}
        pool.warmup_all(dummy_frames)
        total = sum(w._detector.warmup_count for w in pool._workers.values())
        assert total == len(robot_ids), (
            f"warmup_all must synchronously call every worker's warmup; "
            f"expected {len(robot_ids)}, got {total}"
        )
    finally:
        pool.shutdown()


def test_warmup_all_tolerates_missing_rid(register_fakes) -> None:
    """Missing key in dummy_frames must log a warning, NOT raise.

    Wave 4's main.py restart path calls warmup_all with whatever the bridge
    has captured so far; if a robot has not produced a first real frame yet,
    warmup_all must continue past that robot instead of hanging the restart.
    """
    robot_ids = ("r0", "r1")
    pool = _make_pool(robot_ids)
    try:
        # Only supply a dummy for r0; r1 is deliberately missing.
        pool.warmup_all({"r0": _make_frame(sim_time=0.0)})
        assert pool._workers["r0"]._detector.warmup_count == 1
        assert pool._workers["r1"]._detector.warmup_count == 0
    finally:
        pool.shutdown()


def test_inspect_worker_queues_has_entry_per_robot(register_fakes) -> None:
    """Returns {rid: {queue_depth, drops_since_session_start, last_submit_sim_time}}."""
    pool = _make_pool(("r0", "r1", "r2"))
    try:
        snap = pool.inspect_worker_queues()
        assert set(snap.keys()) == {"r0", "r1", "r2"}
        for rid, entry in snap.items():
            assert set(entry.keys()) == {
                "queue_depth",
                "drops_since_session_start",
                "last_submit_sim_time",
            }, f"inspect entry for {rid} shape mismatch: {entry}"
            assert entry["queue_depth"] == 0
            assert entry["drops_since_session_start"] == 0
            assert entry["last_submit_sim_time"] == 0.0
    finally:
        pool.shutdown()


def test_instance_separation_backend_mutations_do_not_leak(register_fakes) -> None:
    """Mutating r0's detector.threshold must NOT affect r1's detector.threshold.

    This is the core guarantee that Phase 8 stretch DET-STRETCH-04 depends on:
    per-robot detector instances allow per-robot param tuning without cross-talk.
    """
    pool = _make_pool(("r0", "r1"))
    try:
        pool._workers["r0"]._detector.threshold = 0.9
        assert pool._workers["r0"]._detector.threshold == 0.9
        assert pool._workers["r1"]._detector.threshold == 0.5, (
            "per-robot instance separation violated — r1 threshold moved when r0 was mutated"
        )
    finally:
        pool.shutdown()


def test_reset_all_clears_every_worker(register_fakes) -> None:
    """reset_all() must call worker.reset() on every worker.

    After submitting to r0, reset_all() clears _pending + _latest on r0 AND
    does not raise on r1/r2 (which have nothing queued). Drop counter stays
    session-lifetime per DetectorWorker contract (reset does not reset drops).
    """
    pool = _make_pool(("r0", "r1", "r2"))
    pool.start()
    try:
        pool.submit("r0", _make_frame(sim_time=0.1), np.eye(4), None)
        # Give the worker a moment to drain; then reset.
        time.sleep(0.05)
        pool.reset_all()
        for rid in ("r0", "r1", "r2"):
            assert pool.latest(rid) is None, f"{rid} latest must be None after reset_all"
    finally:
        pool.shutdown()


def test_pool_exposes_backend_and_lifter_names_as_public_attrs(register_fakes) -> None:
    """Phase 6 MetricsPanel surfaces backend_name + lifter_name on the pool for observability."""
    pool = _make_pool(("r0",))
    try:
        assert pool.backend_name == "fake_yolo"
        assert pool.lifter_name == "fake_lifter"
    finally:
        pool.shutdown()


def test_pool_module_does_not_import_torch() -> None:
    """P9 invariant: importing ``src.perception.worker_pool`` must not pull torch."""
    # Drop any cached worker_pool import so we measure a fresh module load.
    for mod in list(sys.modules):
        if mod == "src.perception.worker_pool":
            del sys.modules[mod]
    import src.perception.worker_pool  # noqa: F401

    assert "torch" not in sys.modules, (
        "Importing src.perception.worker_pool pulled torch into sys.modules — "
        "Pitfall P9: heavy deps must be reached via lazy class-path loading only."
    )
