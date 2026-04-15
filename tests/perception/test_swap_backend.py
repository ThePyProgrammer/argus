"""Plan 07-05 target — DET-PIPELINE-05 SC#4 (DetectorWorkerPool.swap_backend).

Asserts pool.swap_backend:
  - Mirrors swap_lifter atomicity (construct per-worker OUTSIDE lock).
  - Emits detector_swap_complete via streaming_viz._message_queue.
  - Per-worker-instance separation (each worker gets its own backend instance).
  - Warmup-failure rollback (any worker's warmup raising leaves pool unchanged).
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-05 swap_backend (implemented in Plan 07-05)",
    allow_module_level=True,
)


def test_swap_backend_atomic_rebind() -> None:
    # TODO Plan 07-05: construct pool with yolov11; call swap_backend("rtdetrv2");
    # assert every worker._detector is the new backend, pool.backend_name updated.
    assert False, "implemented in Plan 07-05"


def test_swap_backend_per_worker_instance_separation() -> None:
    # TODO Plan 07-05: assert worker_a._detector is not worker_b._detector after swap.
    assert False, "implemented in Plan 07-05"


def test_swap_backend_emits_detector_swap_complete_ws() -> None:
    # TODO Plan 07-05: mock streaming_viz; after swap, assert _message_queue.append
    # called with {"type": "detector_swap_complete", "payload": {"backend": ..., "reason": "hot_swap"}}.
    assert False, "implemented in Plan 07-05"


def test_swap_backend_warmup_failure_rollback() -> None:
    # TODO Plan 07-05: Pitfall 8 — stub DetectorRegistry.create to raise on
    # third worker; assert no worker's _detector was mutated, pool.backend_name unchanged.
    assert False, "implemented in Plan 07-05"


def test_swap_backend_unknown_name_raises_before_mutation() -> None:
    # TODO Plan 07-05: swap_backend("bogus") raises ValueError, pool.backend_name preserved.
    assert False, "implemented in Plan 07-05"
