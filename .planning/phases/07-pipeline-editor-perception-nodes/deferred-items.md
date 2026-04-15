# Phase 07 — Deferred Items

Pre-existing issues discovered during plan execution but out of scope.

## open3d ModuleNotFoundError cascade (discovered Plan 07-09)

**Symptom:** `tests/web/test_web_server.py`, `tests/coordination/test_map_merger.py`,
`tests/coordination/test_merge_registry.py`, `tests/coordination/test_merge_strategies.py`,
`tests/perception/test_subprocess_bridge_skeleton.py`,
`tests/web/test_merge_routes.py`, `tests/perception/test_detector_routes.py`,
`tests/perception/test_lifter_hotswap.py`, `tests/perception/test_lifter_routes.py`
all fail at import time with `ModuleNotFoundError: No module named 'open3d'`.

**Root cause:** `src/slam/backends/__init__.py` unconditionally imports
`icp_backend`, which transitively imports `src/slam/slam_pipeline.py` which
requires `open3d`. Any test that imports `src.slam.backends` (directly or
through the server entrypoint) errors at collection.

**Scope:** Pre-existing on `main` at `fc2dc24`. Reproduced under `git stash`
of Plan 07-09 changes.

**Deferred because:** Environment setup / dependency management — not
introduced by DET-PIPELINE-05 and not blocking Plan 07-09 acceptance
(test_pipeline_apply_hot.py bypasses by registering backends directly into
the registry rather than importing src.slam.backends).

**Recommended resolution:** Either (a) install open3d in the test
environment, or (b) make icp_backend import lazy (move `import open3d`
inside methods) so import-time registration no longer depends on it.
