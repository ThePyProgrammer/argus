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

## Plan 04-05 discoveries (2026-04-14)

### Pre-existing SLAM `supports_imu` capability schema mismatch

- **Tests affected:**
  - `tests/web/test_slam_routes.py::test_list_backends_icp_capabilities`
  - `tests/web/test_slam_routes.py::test_list_backends_icp_parameter_schema`
  - `tests/web/test_slam_routes.py::test_select_valid_backend`
  - `tests/web/test_slam_routes.py::test_patch_params_startup_only`
- **Symptom:** `KeyError: 'supports_imu'` when reading ICP capabilities.
- **Scope:** Pre-existing on the base commit `5056293` — unrelated to
  the lifter hot-swap cutover. Verified by re-running on the base.
- **Decision:** DEFERRED — owned by SLAM-capability refactor; tracked here
  so the Phase 4 verifier does not attribute the failures to 04-05.

### Pre-existing msgpack missing (subprocess_bridge)

- **Tests affected:**
  - `tests/perception/test_subprocess_bridge.py` (collection error)
  - `tests/perception/test_subprocess_bridge_skeleton.py` (collection error)
  - `tests/web/test_merge_routes.py::*` (ModuleNotFoundError: msgpack)
- **Symptom:** `ModuleNotFoundError: No module named 'msgpack'`.
- **Scope:** Dev-env dependency gap — `msgpack` not installed in the
  current agent venv. Pre-existing on base `5056293`.
- **Decision:** DEFERRED — environment setup, not a plan 04-05 issue.

### Pre-existing streaming_viz encode failures

- **Tests affected:**
  - `tests/web/test_streaming_viz.py::TestCameraFrame::test_encode_produces_header_bytes`
  - `tests/web/test_streaming_viz.py::TestCameraFrame::test_encode_decode_roundtrip`
- **Scope:** Pre-existing on base `5056293`. Likely msgpack/encoding
  dependency gap in the same vein as the subprocess_bridge collection
  errors above.
- **Decision:** DEFERRED.

