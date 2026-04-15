---
phase: 05-second-backends-boxer-rtdetr-owlv2
plan: 04
subsystem: perception/tests
tags: [wave-0, test-scaffolding, skip-stubs, pytest, phase-5]
dependency-graph:
  requires: []
  provides:
    - tests/perception/test_rtdetrv2_backend.py (DET-MODELS-02)
    - tests/perception/test_boxer_backend.py (DET-MODELS-03, DET-MODELS-08)
    - tests/perception/test_crash_fallback.py (DET-MODELS-06)
    - tests/integration/test_download_models.py (DET-MODELS-07)
    - tests/integration/test_offline_boot.py (DET-MODELS-07)
    - tests/integration/test_boxer_crash_fallback.py (DET-MODELS-06)
    - tests/test_licenses_md.py (DET-MODELS-08)
  affects:
    - Plan 05-05 (will remove skip on test_bridge_hang_raises + test_subprocess_died_raises)
    - Plan 05-07 (will remove skips on all test_rtdetrv2_backend.py tests)
    - Plan 05-08 (will remove skips on all test_boxer_backend.py tests)
    - Plan 05-09 (will remove skips on pool swap tests in test_crash_fallback.py)
    - Plan 05-11 (will remove skips on test_download_models.py + test_offline_boot.py)
    - Plan 05-12 (will remove skip on test_boxer_crash_fallback.py)
    - Plan 05-02 (will remove skips on test_licenses_md.py)
tech-stack:
  added: []
  patterns:
    - "pytest.skip() as first statement in test body — not xfail — so tests count as skipped not failed"
    - "Marker propagation via @pytest.mark.slow_boxer / @pytest.mark.network on integration/E2E tests"
    - "Docstrings on each test describe the real behavior to be asserted, so reviewers of later plans see both skip reason and intent"
key-files:
  created:
    - tests/perception/test_rtdetrv2_backend.py
    - tests/perception/test_boxer_backend.py
    - tests/perception/test_crash_fallback.py
    - tests/integration/test_download_models.py
    - tests/integration/test_offline_boot.py
    - tests/integration/test_boxer_crash_fallback.py
    - tests/test_licenses_md.py
  modified: []
decisions:
  - "Skip-stubs use pytest.skip(reason) as the first (and only) statement — not @pytest.mark.skip decorator — matching RESEARCH.md § Validation Architecture guidance so each later plan removes a skip in a small, reviewable diff"
  - "test_rtdetrv2_backend.py ships 7 stubs (not only the 2 strictly required by VALIDATION.md's per-task map) to cover all DET-MODELS-02 behaviors referenced in the plan's verify block (test_construct_no_onnx_file_raises, test_construct_with_onnx_file_succeeds, test_preprocess_letterbox_480x640_to_320x320, test_warmup_runs_one_inference, test_latency_p95_under_250ms, test_capabilities_include_framework_and_license, test_thread_budget_inherits_from_thread_config)"
  - "test_boxer_backend.py ships 7 stubs covering the 4 VALIDATION.md-named tests plus 3 additional invariants (quaternion passthrough no handcraft, capability outputs_3d_natively, available when ready marker missing)"
  - "test_crash_fallback.py ships 5 stubs — 2 for Wave 1 Plan 05-05 (bridge exceptions), 3 for Wave 2 Plan 05-09 (pool swap). Matches VALIDATION.md per-task map"
metrics:
  duration: ~4min
  completed: 2026-04-14
---

# Phase 05 Plan 04: Wave 0 Test Skeletons Summary

Seven pytest test files created as `pytest.skip(reason)` stubs so `pytest --collect-only` reveals the complete Phase 5 coverage map while the full suite stays green. Each function's skip reason cites the downstream plan that will replace the stub, making each later RED-to-GREEN diff minimal and reviewable.

## What Was Built

29 test functions across 7 files, all currently skipped with plan-referencing reasons. Integration and end-to-end tests carry `@pytest.mark.slow_boxer` / `@pytest.mark.network` markers per VALIDATION.md's Per-Task Verification Map "Test Type" column.

### File-by-File

**tests/perception/test_rtdetrv2_backend.py (7 tests)** — DET-MODELS-02 skeleton, activated by Plan 05-07 (Wave 2)
- test_construct_no_onnx_file_raises
- test_construct_with_onnx_file_succeeds
- test_preprocess_letterbox_480x640_to_320x320
- test_warmup_runs_one_inference
- test_latency_p95_under_250ms
- test_capabilities_include_framework_and_license
- test_thread_budget_inherits_from_thread_config

**tests/perception/test_boxer_backend.py (7 tests)** — DET-MODELS-03 + DET-MODELS-08, activated by Plan 05-08 (Wave 2)
- test_construct_no_spawn
- test_extent_halving
- test_quaternion_passthrough_no_handcraft
- test_capability_license
- test_capability_outputs_3d_natively
- test_available_when_ready_marker_missing
- test_warmup_returns_3d (`@pytest.mark.slow_boxer`)

**tests/perception/test_crash_fallback.py (5 tests)** — DET-MODELS-06 unit scaffolds
- test_bridge_hang_raises (activated by Plan 05-05, Wave 1)
- test_subprocess_died_raises (activated by Plan 05-05, Wave 1)
- test_pool_on_backend_crash_emits_ws_message (activated by Plan 05-09, Wave 2)
- test_pool_swaps_to_yolo (activated by Plan 05-09, Wave 2)
- test_pool_marks_crashed_backend_unavailable (activated by Plan 05-09, Wave 2)

**tests/integration/test_download_models.py (4 tests, all `@pytest.mark.network`)** — DET-MODELS-07, activated by Plan 05-11 (Wave 3)
- test_download_rtdetrv2
- test_setup_boxer_idempotent
- test_sha256_manifest_verification
- test_rollback_on_partial_failure

**tests/integration/test_offline_boot.py (1 test, `@pytest.mark.slow_boxer`)** — DET-MODELS-07, activated by Plan 05-11 (Wave 3)
- test_all_backends_boot_with_hf_hub_offline

**tests/integration/test_boxer_crash_fallback.py (1 test, `@pytest.mark.slow_boxer`)** — DET-MODELS-06 e2e, activated by Plan 05-12 (Wave 3)
- test_kill_nine_triggers_fallback_within_5s

**tests/test_licenses_md.py (4 tests)** — DET-MODELS-08, activated by Plan 05-02 (Wave 0)
- test_licenses_md_exists
- test_boxer_cc_by_nc_present
- test_agpl_apache_mit_entries_present
- test_nc_compliance_section_present

## Verification Results

```
uv run pytest tests/perception/test_rtdetrv2_backend.py \
              tests/perception/test_boxer_backend.py \
              tests/perception/test_crash_fallback.py \
              tests/integration/test_download_models.py \
              tests/integration/test_offline_boot.py \
              tests/integration/test_boxer_crash_fallback.py \
              tests/test_licenses_md.py --collect-only -q
  => 29 tests collected in 0.07s (no errors)

uv run pytest [same 7 files] -x
  => 29 skipped, 8 warnings in 0.09s
```

Acceptance criteria:
- 7 test files exist: PASS
- Collect shows ≥10 test functions: PASS (29)
- `pytest -x` exits 0 with all skipped: PASS
- ≥25 `pytest.skip` occurrences across the 7 files: PASS (31 total grep hits — 29 skip calls + 2 docstring mentions)
- rtdetrv2 has all 7 named functions: PASS
- boxer has all 7 named functions: PASS
- crash_fallback has all 5 named functions: PASS

## Deviations from Plan

### Execution-Order Warnings (expected, not a defect)

**1. PytestUnknownMarkWarning on slow_boxer / network markers**
- **Found during:** Task 1 verification
- **Issue:** Plan 05-04 acceptance criteria mention "No PytestUnknownMarkWarning (markers registered by Plan 01)". Plan 01 has not yet been executed in this worktree, so pytest emits 8 UnknownMarkWarnings during collection.
- **Why not a defect:** Plan 04 declares `depends_on: []` and Plan 01 separately registers the markers in `pyproject.toml [tool.pytest.ini_options]`. Warnings are informational, not failures; all 29 tests still skip cleanly and pytest exits 0. Plan 01 will register `slow_boxer` and `network` markers, silencing the warnings when both plans have landed.
- **Fix:** None required — resolved by Plan 05-01 execution.

No other deviations — plan executed exactly as written.

## Plan Execution Order Note

Per plan frontmatter `depends_on: []`, Plan 05-04 is order-independent within Wave 0 (alongside Plans 05-01, 05-02, 05-03). This plan landed before Plans 01/02/03 in this worktree; their landing will:
- Plan 05-01: register `slow_boxer` and `network` markers (silences the warnings above)
- Plan 05-02: remove skip stubs on all 4 `test_licenses_md.py` tests (Wave 0 green → Wave 0 green-with-impl)

## Self-Check: PASSED

Files created (all confirmed):
- FOUND: tests/perception/test_rtdetrv2_backend.py
- FOUND: tests/perception/test_boxer_backend.py
- FOUND: tests/perception/test_crash_fallback.py
- FOUND: tests/integration/test_download_models.py
- FOUND: tests/integration/test_offline_boot.py
- FOUND: tests/integration/test_boxer_crash_fallback.py
- FOUND: tests/test_licenses_md.py

Commits verified:
- FOUND: 108a2cd (test(05-04): Wave 0 skip-stub test skeletons for 7 Phase 5 files)
