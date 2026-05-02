---
phase: 07
slug: align-evaluation-action-mode-contract
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-01
updated: 2026-05-02
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest in the uv-managed Python environment |
| **Config file** | `pytest.ini`; project pytest metadata also exists in `pyproject.toml` |
| **Quick run command** | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` |
| **Full suite command** | `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q` |
| **Estimated runtime** | ~40 seconds for the focused Phase 7 gate; full locomotion/bridge gate may take longer |

---

## Sampling Rate

- **After every task commit:** Run the focused Phase 7 gate: `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q`
- **After every plan wave:** Run `uv run python -m pytest tests/locomotion tests/bridge/test_sim_bridge.py tests/bridge/test_multi_bridge.py -q`
- **Before `/gsd-verify-work`:** Full locomotion plus bridge regression gate must be green
- **Max feedback latency:** ~60 seconds for the focused phase gate

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | LOC-ENV-04, LOC-EVAL-03 | T-07-01, T-07-03 | Unknown and unsupported action modes fail before environment construction or artifact writes; completed `velocity_command` runs record action-mode metadata | runner/export contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` | ✅ | ✅ green |
| 07-01-02 | 01 | 1 | LOC-ENV-04, LOC-EVAL-03 | T-07-01, T-07-02, T-07-03, T-07-04 | `validate_evaluation_matrix()` accepts only evaluator-runnable `velocity_command`, rejects env-supported seams with actionable errors, and preserves no-artifact ordering | runner/export contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` | ✅ | ✅ green |
| 07-01-03 | 01 | 1 | LOC-EVAL-03 | T-07-03, T-07-04 | Completed artifact metadata records the stepped action mode; rejected modes write no manifest, steps, episodes, summary, comparison, or diagnostics | export contract | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_exports.py -q` | ✅ | ✅ green |
| 07-02-01 | 02 | 1 | LOC-ENV-04, LOC-EVAL-03 | T-07-05, T-07-06, T-07-07 | CLI help and benchmark docs state the evaluator-runnable/deferred action-mode contract | CLI/docs contract | `uv run python -m pytest tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` | ✅ | ✅ green |
| 07-02-02 | 02 | 1 | LOC-ENV-04 | T-07-05 | `argus eval-locomotion --help` exposes `velocity_command` as evaluator-runnable and `joint_position`/`residual_baseline` as fail-fast seams | CLI contract | `uv run python -m pytest tests/test_main_args.py -q` | ✅ | ✅ green |
| 07-02-03 | 02 | 1 | LOC-ENV-04, LOC-EVAL-03 | T-07-06, T-07-07 | Benchmark documentation keeps all env action modes visible without claiming non-default evaluator support | docs contract | `uv run python -m pytest tests/test_locomotion_benchmark_docs.py -q` | ✅ | ✅ green |
| 07-03-01 | 03 | 2 | LOC-ENV-04, LOC-EVAL-03 | T-07-09, T-07-10, T-07-11, T-07-12 | CLI matrix-config regressions prove absent scalar flags preserve JSON values, unsupported JSON action modes fail before artifacts, explicit scalar flags override JSON, and subprocess tests use `sys.executable` | CLI matrix-config contract | `uv run python -m pytest tests/test_main_args.py -q` | ✅ | ✅ green |
| 07-03-02 | 03 | 2 | LOC-ENV-04, LOC-EVAL-03 | T-07-09, T-07-10, T-07-11 | `eval-locomotion` parser defaults use `None` for scalar override sentinels and merge loaded matrix scalars only when CLI values are explicit | CLI/evaluation contract | `uv run python -m pytest tests/test_main_args.py -q` | ✅ | ✅ green |
| 07-03-03 | 03 | 2 | LOC-ENV-04, LOC-EVAL-03 | T-07-13, T-07-14 | Docs markup is valid, hardcoded interpreter paths are absent, and focused Phase 7 regression gate is green | focused phase gate | `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Requirement Coverage

| Requirement | Status | Automated Evidence |
|-------------|--------|--------------------|
| LOC-ENV-04 | COVERED | `tests/locomotion/test_argus_go2_env_action_modes.py`, `tests/locomotion/test_locomotion_evaluation_runner.py`, `tests/test_main_args.py`, and `tests/test_locomotion_benchmark_docs.py` cover env action-mode spaces, evaluator fail-fast behavior, CLI help, matrix-config preservation, and docs contract. |
| LOC-EVAL-03 | COVERED | `tests/locomotion/test_locomotion_evaluation_exports.py`, `tests/locomotion/test_locomotion_evaluation_runner.py`, and `tests/test_main_args.py` cover completed-run action-mode metadata, no-artifact rejection, matrix-config preservation, and explicit CLI overrides. |

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. The original Wave 0 rows are implemented and passing in the current test suite.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Audit 2026-05-02

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |

Audit commands run:

- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py tests/locomotion/test_argus_go2_env_action_modes.py tests/test_main_args.py tests/test_locomotion_benchmark_docs.py -q` → 77 passed
- `uv run python -m pytest tests/test_main_args.py -q` → 11 passed
- `uv run python -m pytest tests/locomotion/test_locomotion_evaluation_runner.py tests/locomotion/test_locomotion_evaluation_exports.py -q` → 26 passed

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-02
