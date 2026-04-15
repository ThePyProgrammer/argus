"""Plan 07-11 target — DET-PIPELINE-05 SC#4 (hot-apply PID stability).

End-to-end: boot a test FastAPI client with a stubbed DetectorWorkerPool,
apply a baseline perception pipeline (yolov11 + point_cluster), capture the
coordinator's os.getpid() via app.state. Change ONLY the detector node's
backend param from yolov11 to rtdetrv2 and apply again. Assert:
  - Response status_code == 200
  - Response body == {"status": "hot-applied", "changed": ["detector_name", ...]}
  - os.getpid() unchanged (no subprocess restart)
  - app.state.active_detector_backend == "rtdetrv2"
  - pool.swap_backend was called exactly once
"""
import pytest

pytest.skip(
    "Wave 0 stub — DET-PIPELINE-05 SC#4 (implemented in Plan 07-11)",
    allow_module_level=True,
)


def test_apply_baseline_sets_last_applied_config() -> None:
    # TODO Plan 07-11: first apply returns {"status": "restarting"},
    # app.state.last_applied_pipeline_config is set after restart completes.
    assert False, "implemented in Plan 07-11"


def test_detector_backend_change_triggers_hot_apply() -> None:
    # TODO Plan 07-11: change detector_1.params["backend"] yolov11 → rtdetrv2;
    # assert response == {"status": "hot-applied", "changed": ["detector_name", ...]}.
    assert False, "implemented in Plan 07-11"


def test_topology_change_triggers_restart() -> None:
    # TODO Plan 07-11: delete tracker_1 node; assert response == {"status": "restarting"}.
    assert False, "implemented in Plan 07-11"


def test_slam_backend_change_triggers_restart() -> None:
    # TODO Plan 07-11: change slam_1.type from slam_icp to slam_orbslam3;
    # assert response == {"status": "restarting"}.
    assert False, "implemented in Plan 07-11"


def test_hot_apply_updates_last_applied_config() -> None:
    # TODO Plan 07-11: after hot-apply, app.state.last_applied_pipeline_config.detector_name == "rtdetrv2".
    assert False, "implemented in Plan 07-11"


def test_hot_apply_swap_backend_failure_returns_400() -> None:
    # TODO Plan 07-11: stub pool.swap_backend to raise ValueError; assert 400 + "swap_backend failed".
    assert False, "implemented in Plan 07-11"
