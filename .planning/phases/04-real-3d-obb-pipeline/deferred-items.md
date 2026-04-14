# Phase 4 Deferred Items

Out-of-scope discoveries surfaced during plan execution. These MUST NOT be
auto-fixed during plan runs; they are flagged here for future planning.

## Plan 04-04 discoveries (2026-04-14)

### Pre-existing torch-missing failures in test_protocol_contracts.py

- **Tests affected:**
  - `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_enforces_eval_and_freeze`
  - `tests/perception/test_protocol_contracts.py::test_torch_backend_mixin_inference_contextmanager`
- **Symptom:** `ModuleNotFoundError: No module named 'torch'` at
  `src/perception/protocol.py:188` inside `TorchBackendMixin.__init__`.
- **Scope:** Dev-env dependency gap — `torch` is declared in
  `pyproject.toml` but not installed in this agent's venv. Plan 04-05
  (YOLOv11 backend + regression harness) installed the perception extra
  for backend tests; this test module exercises the mixin directly and
  would need the same install.
- **Decision:** DEFERRED — not introduced by plan 04-04. Tracked for
  Phase 4 verification / Phase 5 setup.
