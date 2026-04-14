# Phase 3 Deferred Items

Out-of-scope discoveries logged during plan execution per GSD scope-boundary rule.

## From 03-05 (Lifter REST routes)

- **`tests/perception/test_subprocess_bridge.py` + `test_subprocess_bridge_skeleton.py` collection error:** `ModuleNotFoundError: No module named 'msgpack'`. Pre-existing on baseline (verified via `git stash`-clean run). Subprocess bridge isn't in 03-05 scope.
- **`tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_*` (2 tests):** `ModuleNotFoundError: No module named 'torch'`. Pre-existing — Plan 01-05 was supposed to install perception extra including torch but fixture needs investigation. Not Plan 03-05's responsibility.
- **`tests/web/test_slam_routes.py` + `test_streaming_viz.py` + `test_merge_routes.py` failures:** Pre-existing on baseline (verified clean checkout — no local changes when reproducing). Out of scope for Plan 03-05 which only touches `backend/web/detector_routes.py` + `server.py`.
