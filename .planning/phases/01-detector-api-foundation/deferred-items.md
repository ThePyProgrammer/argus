# Deferred Items — Phase 01 detector-api-foundation

Out-of-scope discoveries logged by executor agents. Must be addressed before phase verification signs off.

---

## From 01-03 executor (registry)

### test_protocol_contracts torch dependency

- **File:** `tests/perception/test_protocol_contracts.py`
- **Tests:** `test_torch_backend_mixin_enforces_eval_and_freeze`, `test_torch_backend_mixin_inference_contextmanager`
- **Failure:** `ModuleNotFoundError: No module named 'torch'` when running under the project uv venv.
- **Cause:** These two Plan 02 tests instantiate `TorchBackendMixin`, which lazy-imports `torch` inside `__init__`. The uv venv used by CI for this worktree does not currently resolve the `perception` extra (or equivalent) that pulls torch in.
- **Pre-existing:** YES — present on base commit `3558bdb` (Wave 1 merge-back). Not caused by registry work.
- **Scope:** Out of Plan 03 scope per executor deviation rules ("Only auto-fix issues DIRECTLY caused by the current task's changes").
- **Proposed resolution:** Either (a) ensure Plan 05 (YOLOv11 backend) installs torch as part of its `uv sync` step so these tests pass end-to-end, or (b) guard the two test functions with `pytest.importorskip("torch")` so they skip gracefully when torch is not available. Phase 1 end-state requires YOLOv11 to be importable, so option (a) is the natural fix.
- **Impact if left alone:** 2/18 perception-protocol tests fail under a torch-less env; does not block Plan 03, 04, or 05 code correctness (those plans either don't import torch at module scope or install torch themselves). Phase-level verification must confirm torch is available before declaring the phase complete.
