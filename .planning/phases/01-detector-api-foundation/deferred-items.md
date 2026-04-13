# Deferred Items — Phase 01 detector-api-foundation

Out-of-scope discoveries logged by executor agents. Must be addressed before phase verification signs off.

---

## From 01-03 executor (registry)

### test_protocol_contracts torch dependency — RESOLVED by Plan 05

- **File:** `tests/perception/test_protocol_contracts.py`
- **Tests:** `test_torch_backend_mixin_enforces_eval_and_freeze`, `test_torch_backend_mixin_inference_contextmanager`
- **Original failure:** `ModuleNotFoundError: No module named 'torch'` when running under the project uv venv.
- **Resolution:** Plan 05 executor installs the `perception` extra (`uv sync --extra perception --extra dev --extra web`) as part of the YOLOv11 backend workflow. Both tests now PASS — all 18/18 protocol contract tests green. Closed: 2026-04-13.

---

## From 01-04 executor (MedianDepthLifter)

### test_registry.py sys.modules-pollution failures (7 tests)

- **File:** `tests/perception/test_registry.py`
- **Tests failing when full suite runs:** `test_register_accepts_full_capabilities`, `test_list_backends_uses_available_probe`, `test_list_backends_tolerates_missing_available_classmethod`, `test_list_backends_handles_unloadable_class_path`, `test_probe_exception_marks_unavailable_without_crash`, `test_detector_backend_decorator_registers_at_class_definition`, `test_registries_are_independent`.
- **Failure:** `ValueError: Detector 'only2d' CAPABILITIES['input_type'] must be DetectorInput, got DetectorInput (<DetectorInput.RGB_ONLY: 'rgb_only'>).` Same class name; two distinct class objects in memory.
- **Cause:** `tests/perception/test_protocol_contracts.py::test_perception_types_import_does_not_load_heavy_deps` (and its sibling `..._protocol_import_..._heavy_deps`) delete `src.perception.types` entries from `sys.modules` and re-import. This creates a NEW `DetectorInput` Enum class. Tests already-loaded via `from src.perception.types import DetectorInput` at module top (e.g. `test_registry.py:14`) hold the OLD enum identity. When those tests register a backend, `registry._validate_capabilities` uses the NEW `DetectorInput` (from a fresh `src.perception.types`) for the `isinstance` check → returns False.
- **Pre-existing:** YES — confirmed by removing `tests/perception/test_median_depth_lifter.py` (Plan 04's test file) and re-running the suite: same 9 failures (2 torch + 7 registry). Plan 04 did not introduce or aggravate this issue; it was latent at base commit `377d994`.
- **In-isolation status:** All 16 tests in `test_registry.py` pass when run alone (`uv run pytest tests/perception/test_registry.py`). Plan 04's own 13 tests pass both in isolation and with the full suite, regardless of order.
- **Scope:** Out of Plan 04 scope per executor deviation rules. The root cause is in `test_protocol_contracts.py`'s sys.modules manipulation, not in registry or lifter code.
- **Proposed resolution:** (a) Fix the heavy-deps tests to use `importlib.reload()` in a try/finally that restores `sys.modules` state without invalidating `DetectorInput` identity — OR — (b) switch `_validate_capabilities`' `input_type` check from `isinstance(value, DetectorInput)` to a structural check (e.g. `type(value).__name__ == 'DetectorInput' and value.value in {"rgb_only", "rgbd", "rgb_text_prompt"}`). Option (a) is cleaner.
- **Impact if left alone:** Perception test suite reports 9 failures when run as a whole. Plan 04 + Plan 05 code remains correct; Plan 05's YOLOv11 backend uses the registry via decorator at class definition time (single `DetectorInput` identity, no pollution path), so this doesn't block the phase.
